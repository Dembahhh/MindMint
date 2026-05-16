"""
utils/gemini.py

Shared utilities for parsing Gemini API responses.
"""

import re
import logging

logger = logging.getLogger(__name__)

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def strip_markdown_fences(raw: str) -> str:
    """
    Strips markdown code fences from a Gemini response string.

    Gemini wraps JSON in ```json ... ``` blocks ~15% of the time
    despite instructions not to. Uses regex to handle preamble text
    and edge cases the split-based approach misses.

    Returns the inner content if fences are found,
    or the original string stripped if no fences are present.
    """
    match = _FENCE_RE.search(raw)
    if match:
        return match.group(1).strip()
    return raw.strip()