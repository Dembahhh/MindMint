"""
memory/embedder.py

Generates vector embeddings for memory text using Gemini text-embedding-004.

text-embedding-004 produces 768-dimensional vectors.
We use RETRIEVAL_DOCUMENT task type when storing (publisher side)
and RETRIEVAL_QUERY task type when searching (consumer side).

This distinction is important: it tells Gemini how to optimise the embedding.
Retrieval-optimised embeddings cluster semantically similar content closer together,
which improves search quality vs generic embeddings.
"""

import asyncio
import logging

import google.api_core.exceptions
import google.generativeai as genai

from backend.config import settings
from backend.utils.limits import EMBEDDER_MAX_TEXT_CHARS

logger = logging.getLogger(__name__)

EMBEDDING_DIM: int = settings.llm.embedding_dim
_TASK_STORE: str = "RETRIEVAL_DOCUMENT"
_TASK_SEARCH: str = "RETRIEVAL_QUERY"
_ZERO_VECTOR: list[float] = [0.0] * EMBEDDING_DIM


async def embed_text(text: str, task_type: str = _TASK_STORE) -> list[float]:
    """
    Generates an embedding vector for text.

    Args:
        text:      Text to embed. Truncated to EMBEDDER_MAX_TEXT_CHARS.
        task_type: RETRIEVAL_DOCUMENT for storage, RETRIEVAL_QUERY for search.

    Returns:
        List of floats (length = EMBEDDING_DIM), or zero vector on error.
    """
    try:
        result = await asyncio.to_thread(
            genai.embed_content,
            model=settings.llm.embedding_model,
            content=text[:EMBEDDER_MAX_TEXT_CHARS],
            task_type=task_type
        )
        embedding = result["embedding"]
        logger.debug("Embedded %d chars → %d-dim vector", len(text), len(embedding))
        return embedding

    except google.api_core.exceptions.GoogleAPIError as e:
        logger.warning("[embedder] Gemini embedding failed: %s. Returning zero vector.", e)
        return _ZERO_VECTOR.copy()
    except (KeyError, TypeError) as e:
        logger.warning("[embedder] Unexpected response shape: %s. Returning zero vector.", e)
        return _ZERO_VECTOR.copy()


async def embed_for_storage(text: str) -> list[float]:
    """Embed text for storage — uses RETRIEVAL_DOCUMENT task type."""
    return await embed_text(text, task_type=_TASK_STORE)


async def embed_for_search(query: str) -> list[float]:
    """Embed a search query — uses RETRIEVAL_QUERY task type."""
    return await embed_text(query, task_type=_TASK_SEARCH)


async def embed_batch(
    texts: list[str],
    task_type: str = _TASK_STORE
) -> list[list[float]]:
    """Embed multiple texts concurrently. Returns embeddings in same order as input."""
    tasks = [embed_text(text, task_type) for text in texts]
    return await asyncio.gather(*tasks)