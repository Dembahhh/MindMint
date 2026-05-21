"""
agents/consumer_agent.py

Autonomous Consumer Agent that:
  1. Receives a task from a human or system
  2. Plans search queries using Groq (was: Gemini)
  3. Searches the memory marketplace
  4. Evaluates results and decides what to buy
  5. Makes x402 payments autonomously
  6. Injects purchased memories into its context
  7. Generates a final answer informed by the purchased memories

This is the full agentic loop. The Consumer Agent acts without
human intervention from task receipt to final answer.

Budget management:
  Each run has a max_budget_usdc (default: 0.01 = 5 bundles at $0.002 each).
  The agent tracks spending and stops buying when the budget is exhausted.
  This prevents runaway spending in production.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Optional, Any
import httpx

from groq import AsyncGroq

# import google.generativeai as genai
# import google.api_core.exceptions
# _model = genai.GenerativeModel(settings.llm.model)

from backend.config import settings
from backend.payments.client import pay_for_resource
from backend.utils.gemini import strip_markdown_fences
from backend.utils.limits import LOG_PREVIEW_CHARS, CONSUMER_TASK_MAX_CHARS

logger = logging.getLogger(__name__)

_groq = AsyncGroq(api_key=settings.llm.groq_api_key.get_secret_value())

SIMILARITY_THRESHOLD = settings.agent.similarity_threshold
QUALITY_THRESHOLD = settings.agent.quality_threshold
MAX_BUNDLES_PER_RUN = settings.agent.max_bundles_per_run


async def _groq_complete(
    prompt: str,
    max_tokens: int = 200,
    temperature: float = 0.3
) -> str:
    """Helper: single-turn Groq completion."""
    response = await _groq.chat.completions.create(
        model=settings.llm.model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content.strip()


@dataclass
class PurchasedBundle:
    bundle_id: str
    title: str
    memories: list[dict]
    tx_hash: str
    amount_usdc: float
    similarity: float


@dataclass
class ConsumerRunResult:
    task: str
    answer: str
    purchased_bundles: list[PurchasedBundle] = field(default_factory=list)
    total_spent_usdc: float = 0.0
    memories_used: int = 0
    search_queries_used: list[str] = field(default_factory=list)
    error: Optional[str] = None


QUERY_PLANNING_PROMPT = """
You are planning search queries for an AI memory marketplace.

Task: {task}

Generate 2-3 focused search queries that would find agent memories
useful for completing this task. Each query should target a different
aspect of the task.

Respond with ONLY a JSON array of query strings:
["query 1", "query 2", "query 3"]

Keep queries short and specific. Do not include explanatory text.
"""

PURCHASE_DECISION_PROMPT = """
You are an AI agent deciding whether to buy a memory bundle.

Your task: {task}

Bundle being evaluated:
  Title: {title}
  Description: {description}
  Similarity to your query: {similarity:.2f} (0=no match, 1=perfect match)
  Quality score: {quality:.2f} (0=low quality, 1=high quality)
  Price: ${price} USDC
  Memory count: {memory_count}
  Preview: "{preview}"

Should you buy this bundle? Consider:
1. Is the similarity high enough to be useful? (>0.7 is good)
2. Is the quality high enough to be reliable? (>0.6 is good)
3. Does the preview suggest relevant, specific information?

Respond with ONLY a JSON object:
"buy": true, "reason": "One sentence explanation"
or
"buy": false, "reason": "One sentence explanation"
"""

ANSWER_GENERATION_PROMPT = """
You are an AI agent that has just purchased memory bundles from a marketplace.

Task you need to complete:
{task}

Purchased memories that inform your answer:
{memories_context}

Using the purchased memories as grounding, provide a detailed, specific answer
to the task. Reference specific facts from the memories where relevant.
If a memory contains specific numbers, addresses, or parameters, use them.

Your answer:
"""


class ConsumerAgent:
    """
    Autonomous agent that searches, buys, and uses memory bundles.
    """
    
    def __init__(
        self,
        server_url: Optional[str] = None,
        max_budget_usdc: Optional[float] = None
    ):
        self.server_url = server_url or settings.agent.api_base_url
        self.max_budget_usdc = max_budget_usdc if max_budget_usdc is not None else settings.agent.max_budget_usdc
        self.wallet = settings.consumer.address
    
    async def _plan_queries(self, task: str) -> list[str]:
        """
        Uses Groq to generate focused search queries from a task description.
        Generating multiple queries improves recall — different phrasings
        find different bundles.
        """
        try:
            prompt = QUERY_PLANNING_PROMPT.format(task=task)
            #  response = await _model.generate_content_async(prompt, generation_config={"temperature": 0.3, "max_output_tokens": 200})
            #  raw = strip_markdown_fences(response.text.strip())
            raw = strip_markdown_fences(
                await _groq_complete(prompt, max_tokens=200, temperature=0.3)
            )
            queries = json.loads(raw)
            logger.info("[consumer] Generated %d search queries", len(queries))
            return queries[:3]
        except Exception as e:
            #  except google.api_core.exceptions.GoogleAPIError as e:
            logger.warning("[consumer] Query planning error: %s", e)
            return [task[:CONSUMER_TASK_MAX_CHARS]]
        
    async def _search_marketplace(
        self,
        queries: list[str],
        top_k: int = 3
    ) -> list[dict]:
        """
        Searches the marketplace for each query.
        Deduplicates results across queries by bundle_id.
        Returns all unique results sorted by similarity.
        """
        seen = {}        
        async with httpx.AsyncClient(timeout=30.0) as client:
            for query in queries:
                logger.info("[consumer] Searching: '%s'", query[:LOG_PREVIEW_CHARS])
                try:
                    r = await client.get(
                        f"{self.server_url}/memory/search",
                        params={"q": query, "top_k": top_k}
                    )
                    if r.status_code == 200:
                        results = r.json().get("results", [])
                        for result in results:
                            bid = result["bundle_id"]
                            if bid not in seen or result["similarity"] > seen[bid]["similarity"]:
                                seen[bid] = result
                        logger.info(
                            "[consumer] Query '%s' → %d results",
                            query[:LOG_PREVIEW_CHARS], len(results)
                        )
                except (httpx.HTTPError, httpx.TimeoutException) as e:
                    logger.warning("[consumer] Search failed for query '%s': %s", query[:LOG_PREVIEW_CHARS], e)
        
        ranked = sorted(seen.values(), key=lambda x: x["similarity"], reverse=True)
        logger.info("[consumer] Total unique bundles found: %d", len(ranked))
        return ranked
    
    async def _decide_purchase(self, result: dict, task: str) -> tuple[bool, str]:
        """
        Decides whether to buy a bundle using rule-based + LLM evaluation.
        
        First applies fast rule-based checks (similarity, quality thresholds).
        If rules pass, asks Groq to evaluate the preview vs the task.
        
        Returns (should_buy: bool, reason: str)
        """
        similarity = result.get("similarity", 0)
        quality = result.get("avg_quality_score", 0)
        
        if similarity < SIMILARITY_THRESHOLD:
            return False, f"Similarity {similarity:.2f} below threshold {SIMILARITY_THRESHOLD}"
        
        if quality < QUALITY_THRESHOLD:
            return False, f"Quality {quality:.2f} below threshold {QUALITY_THRESHOLD}"
        
        price_microunits = result.get(
            "price_microunits", (settings.marketplace.memory_base_price_usdc * 1_000_000)
        )
        price_usdc = price_microunits / 1_000_000
        
        try:
            prompt = PURCHASE_DECISION_PROMPT.format(
                task=task[:CONSUMER_TASK_MAX_CHARS],
                title=result.get("title", ""),
                description=result.get("description", ""),
                similarity=similarity,
                quality=quality,
                price=price_usdc,
                memory_count=result.get("memory_count", 0),
                preview=result.get("best_matching_memory_preview", "")[:200]
            )
            
            #  response = await _model.generate_content_async(prompt, generation_config={"temperature": 0.1, "max_output_tokens": 100})
            #  raw = strip_markdown_fences(response.text.strip())
            raw = strip_markdown_fences(
                await _groq_complete(prompt, max_tokens=100, temperature=0.1)
            )

            decision = json.loads(raw)
            should_buy = decision.get("buy", False)
            reason = decision.get("reason", "")
            
            logger.info(
                "[consumer] Bundle '%s': similarity=%.2f, quality=%.2f, decision=%s — %s",
                result.get("title", "")[:40], similarity, quality,
                "BUY" if should_buy else "SKIP", reason
            )
            
            return should_buy, reason

        except Exception as e:
            #  except google.api_core.exceptions.GoogleAPIError as e:
            logger.warning("[consumer] Purchase decision error: %s", e)
            return similarity > 0.78 and quality > 0.65, "Rule-based fallback (LLM unavailable)"
    
    async def _purchase_bundle(self, bundle_id: str) -> Optional[dict]:
        """
        Executes the x402 payment and returns the full bundle content.
        Returns None if payment fails.
        """
        try:
            logger.info("[consumer] Paying for bundle %s...", bundle_id[:20])
            
            result = await pay_for_resource(
                url=f"/memory/purchase/{bundle_id}",
                base_url=self.server_url
            )
            
            tx = result.get("_payment_meta", {}).get("tx_hash", "unknown")
            amount = result.get("_payment_meta", {}).get("amount_usdc", 0)
            
            logger.info(
                "[consumer] Bundle %s purchased. TX: %s, Amount: $%.4f USDC",
                bundle_id[:20], tx[:20], amount
            )
            return result
        
        except (httpx.HTTPError, ValueError, KeyError) as e:
            logger.error("[consumer] Purchase failed for bundle %s: %s", bundle_id[:20], e)
            return None
    
    def _build_memories_context(self, bundles: list[PurchasedBundle]) -> str:
        """
        Formats purchased memories for injection into the Groq context.
        
        Structure:
          [Bundle 1: Title]
          Memory 1: text
          Memory 2: text
          ...
          [Bundle 2: Title]
          ...
        """
        if not bundles:
            return "No memories purchased for this task."
        
        parts = []
        for i, bundle in enumerate(bundles, 1):
            parts.append(f"[Bundle {i}: {bundle.title}]")
            for j, memory in enumerate(bundle.memories, 1):
                parts.append(f"Memory {j} (quality: {memory.get('quality_score', 0):.2f}):")
                parts.append(memory.get("text", ""))
                parts.append("")
        
        return "\n".join(parts)
    
    async def _generate_answer(
        self,
        task: str,
        purchased_bundles: list[PurchasedBundle]
    ) -> str:
        """
        Generates the final answer using Groq, informed by purchased memories.
        """
        memories_context = self._build_memories_context(purchased_bundles)
        
        if not purchased_bundles:
            prompt = f"Answer this task using your general knowledge:\n\n{task}"
        else:
            prompt = ANSWER_GENERATION_PROMPT.format(
                task=task,
                memories_context=memories_context
            )
        
        try:
            #  response = await _model.generate_content_async(prompt, generation_config={"temperature": 0.4, "max_output_tokens": 1000})
            #  return response.text.strip()
            #  except google.api_core.exceptions.GoogleAPIError as e:
            #  return f"Error generating answer: Gemini unavailable ({e})"
            return await _groq_complete(prompt, max_tokens=1000, temperature=0.4)

        except Exception as e:
            logger.error("[consumer] Answer generation error: %s", e)
            return f"Error generating answer: LLM unavailable ({e})"

    
    async def run(self, task: str) -> ConsumerRunResult:
        """
        Main entry point. Runs the full autonomous loop for a given task.
        
        Returns a ConsumerRunResult with:
          - answer: the final answer to the task
          - purchased_bundles: what was bought
          - total_spent_usdc: how much was spent
          - memories_used: how many individual memories were consumed
        """
        logger.info("[consumer] Starting run. Task: '%s'", task[:80])
        
        result = ConsumerRunResult(task=task, answer="")
        spent = 0.0
        purchased = []
        bundles_bought = 0
        
        queries = await self._plan_queries(task)
        result.search_queries_used = queries
        
        search_results = await self._search_marketplace(queries)
        
        if not search_results:
            logger.info("[consumer] No marketplace results found. Answering from general knowledge.")
        
        for candidate in search_results:
            price_microunits = candidate.get("price_microunits", (settings.marketplace.memory_base_price_usdc * 1_000_000))
            price_usdc = price_microunits / 1_000_000
            
            if spent + price_usdc > self.max_budget_usdc:
                logger.info(
                    "[consumer] Budget limit reached ($%.4f / $%.4f). Stopping purchases.",
                    spent, self.max_budget_usdc
                )
                break
            
            if bundles_bought >= MAX_BUNDLES_PER_RUN:
                logger.info("[consumer] Bundle cap (%d) reached.", MAX_BUNDLES_PER_RUN)
                break
            
            should_buy, reason = await self._decide_purchase(candidate, task)
            
            if not should_buy:
                logger.info(
                    "[consumer] Skipping bundle '%s': %s",
                    candidate.get("title", "")[:40], reason
                )
                continue
            
            bundle_id = candidate["bundle_id"]
            purchase_result = await self._purchase_bundle(bundle_id)
            
            if purchase_result:
                payment_meta = purchase_result.get("_payment_meta", {})
                content = purchase_result.get("content", {})
                
                pb = PurchasedBundle(
                    bundle_id=bundle_id,
                    title=purchase_result.get("title", candidate.get("title", "")),
                    memories=content.get("memories", []),
                    tx_hash=payment_meta.get("tx_hash", ""),
                    amount_usdc=payment_meta.get("amount_usdc", price_usdc),
                    similarity=candidate.get("similarity", 0)
                )
                
                purchased.append(pb)
                spent += pb.amount_usdc
                bundles_bought += 1
                
                logger.info(
                    "[consumer] Purchased bundle '%s' (%d memories, $%.4f USDC)",
                    pb.title[:40], len(pb.memories), pb.amount_usdc
                )
        
        result.purchased_bundles = purchased
        result.total_spent_usdc = spent
        result.memories_used = sum(len(b.memories) for b in purchased)
        
        logger.info(
            "[consumer] Generating answer with %d purchased bundles (%d memories).",
            len(purchased), result.memories_used
        )
        
        result.answer = await self._generate_answer(task, purchased)
        
        logger.info(
            "[consumer] Run complete. Spent: $%.4f USDC | Memories used: %d",
            spent, result.memories_used
        )
        
        return result