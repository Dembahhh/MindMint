"""
utils/cache.py

Simple in-memory TTL cache for dashboard read endpoints.
Cache is process-local — appropriate for single-instance hackathon demo.
"""

import time
from typing import Any, Callable

_cache: dict[str, tuple[Any, float]] = {}
DEFAULT_TTL: float = 30.0


def cached(key: str, ttl: float = DEFAULT_TTL) -> Callable:
    """
    Decorator that caches an async function's return value for ttl seconds.

    The cache key is derived from the provided key plus the function's
    arguments, so calls with different arguments are cached separately.

    Example:
        @cached("leaderboard", ttl=60.0)
        async def get_leaderboard(limit: int = 10) -> list[LeaderboardEntry]:
            ...
    """
    def decorator(fn: Callable) -> Callable:
        async def wrapper(*args, **kwargs) -> Any:
            now = time.monotonic()
            cache_key = f"{key}:{args}:{sorted(kwargs.items())}"
            if cache_key in _cache:
                result, timestamp = _cache[cache_key]
                if now - timestamp < ttl:
                    return result
            result = await fn(*args, **kwargs)
            _cache[cache_key] = (result, now)
            return result
        return wrapper
    return decorator


def invalidate(key: str) -> None:
    """Removes all cache entries matching a key prefix."""
    to_delete = [k for k in _cache if k.startswith(key)]
    for k in to_delete:
        del _cache[k]