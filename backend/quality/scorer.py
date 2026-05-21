"""
quality/scorer.py

Scores agent memories for quality using Groq (was: Gemini Flash).

Quality = how USEFUL is this memory to another agent?

High quality (0.8–1.0):
  - Contains specific, actionable findings
  - Novel information not easily Googleable
  - Clear cause-and-effect reasoning
  - Specific numbers, addresses, or parameters

Medium quality (0.5–0.7):
  - General but correct observations
  - Useful context but not highly specific

Low quality (0.0–0.4):
  - Vague or obvious statements
  - Errors or hallucinations
  - Too short to be useful
  - Duplicate of common knowledge

Memories below QUALITY_THRESHOLD are not stored.
"""

# -- Groq (text generation) --
from groq import AsyncGroq

# -- Gemini (kept for reference; now only used in embedder.py) --
# import google.generativeai as genai
# import google.api_core.exceptions
# _model = genai.GenerativeModel(settings.llm.model)

import json
import logging
import asyncio
from typing import Any

from backend.config import settings
from backend.utils.gemini import strip_markdown_fences
from backend.utils.limits import SCORER_MAX_MEMORY_CHARS

logger = logging.getLogger(__name__)

QUALITY_THRESHOLD: float = settings.marketplace.quality_threshold

_groq = AsyncGroq(api_key=settings.llm.groq_api_key.get_secret_value())


SCORING_PROMPT = """
You are evaluating the quality of an AI agent memory for a marketplace.
Agents buy memories to improve their own decision-making.

Memory to evaluate:
\"\"\"{memory_text}\"\"\"

Score this memory from 0.0 to 1.0 based on:
1. SPECIFICITY — Does it contain specific facts, numbers, addresses, or parameters?
2. NOVELTY — Is this information non-obvious and hard to find elsewhere?
3. ACTIONABILITY — Can another agent use this to make better decisions?
4. ACCURACY — Does the reasoning appear sound?

Respond with ONLY a JSON object in this exact format:
{{
  "score": 0.75,
  "reasoning": "One sentence explaining the score",
  "tags": ["tag1", "tag2", "tag3"]
}}

The tags should be 2-5 topic labels like: DeFi, Ethereum, liquidation, arbitrage, Kite, x402, payment, trading, etc.
Do not include any text outside the JSON object.
"""


async def score_memory(memory_text: str) -> dict[str, Any]:
    """
    Scores a single memory text.
    
    Returns:
      {
        "score": 0.75,          
        "reasoning": "...",     
        "tags": ["DeFi", ...], 
        "passes_threshold": True 
      }
    """
    try:
        prompt = SCORING_PROMPT.format(memory_text=memory_text[:SCORER_MAX_MEMORY_CHARS])
        
        #  response = await _model.generate_content_async(prompt, generation_config={"temperature": 0.1, "max_output_tokens": 200})
        #  raw = strip_markdown_fences(response.text.strip())
        #  except google.api_core.exceptions.GoogleAPIError as e:
        response = await _groq.chat.completions.create(
            model=settings.llm.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.1,
        )
        raw = strip_markdown_fences(response.choices[0].message.content.strip())
        
        result = json.loads(raw)
        score = float(result.get("score", 0.0))
        
        logger.info(
            "Quality score: %.2f | Tags: %s | Reason: %s",
            score,
            result.get("tags", []),
            result.get("reasoning", "")[:60]
        )
        
        return {
            "score": score,
            "reasoning": result.get("reasoning", ""),
            "tags": result.get("tags", []),
            "passes_threshold": score >= QUALITY_THRESHOLD
        }
        
    except Exception as e:
        #  except google.api_core.exceptions.GoogleAPIError as e:
        #  except (json.JSONDecodeError, KeyError) as e:
        logger.warning("[scorer] Error scoring memory: %s. Failing open", e)
        return {
            "score": 0.5,
            "reasoning": str(e),
            "tags": [],
            "passes_threshold": True,
            "unscored": True
        }


async def score_batch(memory_texts: list[str]) -> list[dict[str, Any]]:
    """Score multiple memories. Returns results in same order as input."""
    tasks = [score_memory(text) for text in memory_texts]
    return await asyncio.gather(*tasks)