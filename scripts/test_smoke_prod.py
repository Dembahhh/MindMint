"""
test_smoke_prod.py

Quick smoke test against the production Render deployment.
Run before demo to confirm all critical endpoints are responding.

Usage:
  PROD_URL=https://mindmint-api.onrender.com python scripts/test_smoke_prod.py
"""

import asyncio
import logging
import os

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

PROD_URL = os.getenv("PROD_URL", "http://localhost:8080")

CHECKS: list[tuple[str, str, str]] = [
    ("Health check",       "GET", "/health"),
    ("Platform stats",     "GET", "/dashboard/platform"),
    ("Marketplace listing","GET", "/dashboard/marketplace?limit=5"),
    ("Leaderboard",        "GET", "/dashboard/leaderboard"),
    ("Memory search",      "GET", "/memory/search?q=DeFi+lending"),
]


async def smoke_test() -> None:
    logger.info("Smoke test against: %s", PROD_URL)
    logger.info("=" * 50)

    passed = 0
    failed = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        for name, method, path in CHECKS:
            try:
                if method == "GET":
                    r = await client.get(f"{PROD_URL}{path}")
                else:
                    r = await client.post(f"{PROD_URL}{path}")

                if r.status_code == 200:
                    logger.info("   PASS  %s (%s)", name, r.status_code)
                    passed += 1
                else:
                    logger.error(
                        "   FAIL  %s — got %s: %s",
                        name, r.status_code, r.text[:80]
                    )
                    failed += 1

            except (httpx.HTTPError, httpx.TimeoutException) as e:
                logger.error("   FAIL  %s — network error: %s", name, e)
                failed += 1
            except Exception as e:
                logger.error("   FAIL  %s — unexpected error: %s", name, e)
                failed += 1

    logger.info("=" * 50)
    logger.info("Results: %d/%d passed", passed, len(CHECKS))
    if failed == 0:
        logger.info("Production is healthy. Ready for demo.")
    else:
        logger.error("%d check(s) failed. Fix before demo day.", failed)
    logger.info("=" * 50)


if __name__ == "__main__":
    asyncio.run(smoke_test())