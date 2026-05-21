"""
agents/publisher_agent.py

The Publisher Agent captures AI agent interactions and publishes
them as MemoryBundles to the marketplace.

In production: this agent wraps another agent's tool calls and
automatically captures every interaction for potential resale.

For the hackathon demo: generates realistic synthetic memories
to seed the marketplace with demonstrable content.

Architecture:
  PublisherAgent
    ├── _generate_memories()  — Creates realistic interaction texts
    ├── _publish_bundle()     — Scores + embeds + stores via MemoryStore
    └── run_demo_session()    — Runs a full demo capture session
"""

import asyncio
import logging
import json

# -- Groq (text generation) --
from groq import AsyncGroq

# -- Gemini (kept for reference; now only used in embedder.py) --
# import google.generativeai as genai
# import google.api_core.exceptions
# _model = genai.GenerativeModel(settings.llm.model)

from backend.utils.limits import PUBLISHER_TOPIC_MAX_CHARS, LOG_PREVIEW_CHARS
from backend.config import settings
from backend.memory.store import MemoryStore
from backend.memory.bundle import MemoryBundle
from backend.utils.gemini import strip_markdown_fences

logger = logging.getLogger(__name__)

_groq = AsyncGroq(api_key=settings.llm.groq_api_key.get_secret_value())


MEMORY_GENERATION_PROMPT = """
You are an AI agent that has just completed a series of {domain} tasks.
Generate {count} realistic agent memory entries that capture what you learned.

Domain context: {domain_context}

Each memory should:
- Be 2-4 sentences
- Contain specific, actionable findings (numbers, addresses, parameters where relevant)
- Sound like real agent reasoning/observations
- Be useful to another agent working in this domain

Respond with a JSON array of strings, one per memory.
Example format:
[
  "Memory 1 text here.",
  "Memory 2 text here."
]

Do not include any text outside the JSON array.
"""

DEMO_DOMAINS = [
    {
        "domain": "DeFi Protocol Analysis",
        "domain_context": "Analysing Uniswap V3, Aave V3, and Compound liquidity positions on Ethereum mainnet. Focus on optimal LP ranges, liquidation thresholds, and yield opportunities.",
        "bundle_title": "DeFi Protocol Intelligence — Uniswap/Aave/Compound",
        "bundle_description": "Agent memories from deep analysis of top DeFi protocols. Includes LP range optimisation, liquidation risk patterns, and yield strategies."
    },
    {
        "domain": "Kite x402 Payment Integration",
        "domain_context": "Integrating x402 micropayment protocol on Kite Ozone Testnet. Focus on payment flow optimisation, error handling patterns, and gas cost minimisation.",
        "bundle_title": "x402 Payment Integration Patterns",
        "bundle_description": "Agent memories from building x402 payment flows. Covers EIP-3009 signing, facilitator interaction, error recovery, and testnet gotchas."
    },
    {
        "domain": "Crypto Market Microstructure",
        "domain_context": "Analysing order book dynamics, liquidation cascades, and MEV opportunities across major CEX and DEX venues in Q1 2026.",
        "bundle_title": "Market Microstructure Intelligence Q1 2026",
        "bundle_description": "Agent memories from market microstructure analysis. Covers liquidation patterns, arbitrage windows, and order flow dynamics."
    }
]


class PublisherAgent:
    """
    Captures and publishes memory bundles to the marketplace.
    """
    
    def __init__(self, store: MemoryStore) -> None:
        self.store = store
        self.wallet = settings.publisher.address
    
    async def _generate_memories(
        self,
        domain: str,
        domain_context: str,
        count: int = 8
    ) -> list[str]:
        """
        Uses Groq to generate realistic synthetic memories.
        In production this would be replaced by real interaction capture.
        """
        prompt = MEMORY_GENERATION_PROMPT.format(
            domain=domain,
            domain_context=domain_context,
            count=count
        )
        
        try:
            #  response = await _model.generate_content_async(prompt, generation_config={"temperature": 0.8, "max_output_tokens": 2000, "top_k": 40, "top_p": 0.95})
            #  raw = strip_markdown_fences(response.text.strip())
            #  except google.api_core.exceptions.GoogleAPIError as e:
            response = await _groq.chat.completions.create(
                model=settings.llm.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                temperature=0.8,
            )
            raw = strip_markdown_fences(response.choices[0].message.content.strip())

            memories = json.loads(raw)
            logger.info("Generated %d memories for domain: %s", len(memories), domain)
            return memories
        
        except Exception as e:
            #  except google.api_core.exceptions.GoogleAPIError as e:
            logger.error("[publisher] LLM error for domain '%s': %s", domain[:PUBLISHER_TOPIC_MAX_CHARS], e)
            return []

    async def publish_bundle(
        self,
        title: str,
        description: str,
        raw_memories: list[str]
    ) -> MemoryBundle | None:
        """
        Publishes a bundle of memories to the marketplace.
        Runs the full quality scoring + embedding + storage pipeline.
        """
        logger.info("Publishing bundle: '%s'", title)
        
        bundle = await self.store.save_bundle(
            title=title,
            description=description,
            publisher_wallet=self.wallet,
            raw_memories=raw_memories
        )
        
        if bundle:
            logger.info(
                "Published bundle %s | %d memories | avg quality: %.2f",
                bundle.bundle_id, len(bundle.memories), bundle.avg_quality_score
            )
        else:
            logger.warning("Bundle '%s' was not published (all memories below quality threshold)", title)
        
        return bundle
    
    async def run_demo_session(self, num_domains: int = 3) -> list[MemoryBundle]:
        """
        Runs a full demo capture session.
        Generates memories for multiple domains and publishes them.
        
        Returns list of successfully published bundles.
        """
        logger.info("Starting Publisher Agent demo session...")
        published_bundles = []
        
        domains = DEMO_DOMAINS[:num_domains]
        
        for domain_config in domains:
            logger.info("Processing domain: %s", domain_config["domain"])
            
            memories = await self._generate_memories(
                domain=domain_config["domain"],
                domain_context=domain_config["domain_context"],
                count=6
            )
            
            bundle = await self.publish_bundle(
                title=domain_config["bundle_title"],
                description=domain_config["bundle_description"],
                raw_memories=memories
            )
            
            if bundle:
                published_bundles.append(bundle)
            
            await asyncio.sleep(1)
        
        logger.info(
            "Demo session complete. Published %d/%d bundles.",
            len(published_bundles), len(domains)
        )
        
        return published_bundles