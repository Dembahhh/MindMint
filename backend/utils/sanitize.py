"""
backend/utils/sanitize.py

Input sanitization for user-submitted memory text.
Strips all HTML tags to prevent XSS attacks before storing
content in MongoDB and returning it to clients.

Used in the /memory/publish route before passing inputs
to memory_store.save_bundle().
"""

import logging
import nh3

logger = logging.getLogger(__name__)

_DEFAULT_MAX_LENGTH: int = 10_000
_LIST_ITEM_MAX_LENGTH: int = 5_000


def sanitize_text(text: str, max_length: int = _DEFAULT_MAX_LENGTH) -> str:
    """Strip all HTML tags from text and truncate to max_length.

    Args:
        text:       Raw user-submitted string.
        max_length: Hard character limit after sanitization.

    Returns:
        Sanitized string safe for storage and display.
    """
    cleaned = nh3.clean(text, tags=set())
    if len(cleaned) > max_length:
        logger.warning(
            "[sanitize] Input truncated from %d to %d chars", len(cleaned), max_length
        )
    return cleaned[:max_length]


def sanitize_list(texts: list[str], max_length: int = _LIST_ITEM_MAX_LENGTH) -> list[str]:
    """Sanitize a list of strings, applying sanitize_text to each item.

    Args:
        texts:      List of raw user-submitted strings.
        max_length: Per-item character limit.

    Returns:
        List of sanitized strings in the same order as input.
    """
    return [sanitize_text(t, max_length) for t in texts]