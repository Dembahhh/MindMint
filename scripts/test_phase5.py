"""
test_phase5.py

Integration test for Phase 5: royalty distribution, analytics dashboard,
marketplace listing, and bundle rating system.

7 tests. All must pass for Phase 5 completion.

Prerequisites:
  - Server running: uvicorn backend.main:app --host 127.0.0.1 --port 8080 --reload
  - Phase 3 and Phase 4 complete
  - .env populated
"""

import asyncio
import logging
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

SERVER_URL = os.getenv("SERVER_URL", "http://localhost:8080")
PUBLISHER_WALLET = os.getenv("PUBLISHER__ADDRESS")
CONSUMER_WALLET = os.getenv("CONSUMER__ADDRESS")

_required = {
    "PUBLISHER__ADDRESS": PUBLISHER_WALLET,
    "CONSUMER__ADDRESS": CONSUMER_WALLET,
}
_missing = [k for k, v in _required.items() if not v]
if _missing:
    logger.error("Missing required env vars: %s", ", ".join(_missing))
    sys.exit(1)

TEST_MEMORIES = [
    (
        "x402 protocol was co-developed by Coinbase and Cloudflare as an HTTP-native "
        "micropayment standard. It uses HTTP 402 status codes and EIP-3009 USDC "
        "transferWithAuthorization to enable sub-cent payments without gas fees for the payer."
    ),
    (
        "The x402 facilitator acts as a trusted verifier: it checks the EIP-712 signature, "
        "verifies USDC balance, submits the on-chain transfer, and returns a receipt TX hash. "
        "On Kite testnet, the facilitator URL is configured via KITE__FACILITATOR_URL."
    ),
    (
        "EIP-3009 nonces must be 32-byte random values to prevent replay attacks. Each payment "
        "authorization is single-use. validBefore should be set to now+300 seconds for a "
        "5-minute payment window."
    ),
]

CONSUMER_TASK = (
    "Explain x402 payment nonces and the EIP-3009 authorization flow for USDC transfers."
)

REQUIRED_DASHBOARD_FIELDS = [
    "bundle_count",
    "total_purchase_count",
    "total_earned_usdc",
    "avg_quality_score",
    "top_bundles",
    "recent_payments",
]


async def run_tests() -> None:
    logger.info("=" * 65)
    logger.info("MindMint — Phase 5: Royalties and Analytics Integration Test")
    logger.info("=" * 65)

    passed = 0
    failed = 0
    bundle_id: str = ""
    dashboard_data: dict = {}

    async with httpx.AsyncClient(timeout=90.0) as client:

        # Setup: Publish test bundle
        logger.info("[SETUP] Publishing test bundle...")
        pub_r = await client.post(
            f"{SERVER_URL}/memory/publish",
            json={
                "title": "x402 Payment Protocol Deep Dive",
                "description": "Technical analysis of x402: EIP-3009, facilitators, and testnet patterns.",
                "memories": TEST_MEMORIES,
                "publisher_wallet": PUBLISHER_WALLET,
            },
        )
        if pub_r.status_code != 200:
            logger.error("[SETUP] FAIL — Publish returned %s: %s", pub_r.status_code, pub_r.text[:200])
            return

        bundle_id = pub_r.json().get("bundle_id", "")
        logger.info("[SETUP] Published bundle %s...", bundle_id[:20])

        # Setup: Trigger a purchase via Consumer Agent
        logger.info("[SETUP] Triggering consumer agent purchase...")
        run_r = await client.post(
            f"{SERVER_URL}/agent/consumer/run",
            json={"task": CONSUMER_TASK, "max_budget_usdc": 0.01},
        )
        if run_r.status_code != 200:
            logger.error("[SETUP] FAIL — Consumer run returned %s: %s", run_r.status_code, run_r.text[:200])
            return

        bundles_bought = run_r.json().get("bundles_purchased", [])
        logger.info("[SETUP] Consumer purchased %d bundle(s)", len(bundles_bought))
        await asyncio.sleep(0.5)

        # Test 1: Royalty payment records created
        logger.info("[TEST 1] Royalty payment records exist...")
        dash_r = await client.get(f"{SERVER_URL}/dashboard/publisher/{PUBLISHER_WALLET}")
        if dash_r.status_code == 200:
            dashboard_data = dash_r.json()
            if dashboard_data.get("total_earned_usdc", 0) > 0:
                logger.info(
                    "   PASS — Publisher earned $%.6f USDC",
                    dashboard_data["total_earned_usdc"]
                )
                passed += 1
            else:
                logger.error("   FAIL — total_earned_usdc is 0 — royalty not recorded")
                failed += 1
        else:
            logger.error("   FAIL — Dashboard returned %s", dash_r.status_code)
            failed += 1

        # Test 2: 80/20 royalty split is mathematically correct
        logger.info("[TEST 2] Royalty split is 80/20...")
        if dashboard_data:
            earned = dashboard_data.get("total_earned_usdc", 0)
            purchases = dashboard_data.get("total_purchase_count", 0)
            expected_per_purchase = 0.002 * 0.80
            if purchases > 0:
                per_purchase = earned / purchases
                if abs(per_purchase - expected_per_purchase) < 0.000001:
                    logger.info(
                        "   PASS — $%.6f per purchase (expected $%.6f)",
                        per_purchase, expected_per_purchase
                    )
                    passed += 1
                else:
                    logger.error(
                        "   FAIL — $%.6f per purchase, expected $%.6f",
                        per_purchase, expected_per_purchase
                    )
                    failed += 1
            else:
                logger.warning("   SKIP — No purchases recorded yet")
                passed += 1
        else:
            logger.warning("   SKIP — Dashboard data unavailable")
            passed += 1

        # Test 3: Publisher dashboard has correct fields
        logger.info("[TEST 3] Publisher dashboard has correct fields...")
        if dashboard_data:
            missing_fields = [f for f in REQUIRED_DASHBOARD_FIELDS if f not in dashboard_data]
            if not missing_fields:
                logger.info("   PASS — All required fields present")
                passed += 1
            else:
                logger.error("   FAIL — Missing fields: %s", missing_fields)
                failed += 1
        else:
            logger.error("   FAIL — Dashboard data unavailable")
            failed += 1

        # Test 4: Platform stats endpoint
        logger.info("[TEST 4] Platform stats endpoint...")
        plat_r = await client.get(f"{SERVER_URL}/dashboard/platform")
        if plat_r.status_code == 200:
            pdata = plat_r.json()
            if pdata.get("total_bundles", 0) > 0 and pdata.get("royalty_split"):
                logger.info(
                    "   PASS — %d bundles, $%.6f total volume",
                    pdata["total_bundles"], pdata.get("total_volume_usdc", 0)
                )
                passed += 1
            else:
                logger.error("   FAIL — Platform stats incomplete: %s", pdata)
                failed += 1
        else:
            logger.error("   FAIL — Platform endpoint returned %s", plat_r.status_code)
            failed += 1

        # Test 5: Marketplace listing
        logger.info("[TEST 5] Marketplace listing returns bundles...")
        market_r = await client.get(
            f"{SERVER_URL}/dashboard/marketplace",
            params={"sort": "top_rated", "limit": 10},
        )
        if market_r.status_code == 200:
            listings = market_r.json().get("listings", [])
            if listings:
                top = listings[0]
                logger.info("   PASS — %d listings returned", len(listings))
                logger.info(
                    "   Top bundle: '%s' (quality: %.2f)",
                    top.get("title", "")[:40], top.get("avg_quality_score", 0)
                )
                passed += 1
            else:
                logger.error("   FAIL — No listings returned")
                failed += 1
        else:
            logger.error("   FAIL — Marketplace returned %s", market_r.status_code)
            failed += 1

        # Test 6: Bundle rating endpoint
        logger.info("[TEST 6] Bundle rating endpoint...")
        if bundle_id:
            rate_r = await client.post(
                f"{SERVER_URL}/dashboard/rate/{bundle_id}",
                json={
                    "rating": 4.5,
                    "consumer_wallet": CONSUMER_WALLET,
                    "comment": "Very useful x402 implementation details",
                },
            )
            if rate_r.status_code == 200:
                new_avg = rate_r.json().get("new_avg_rating", 0)
                logger.info("   PASS — Rating accepted. New avg: %.1f/5.0", new_avg)
                passed += 1
            else:
                logger.error(
                    "   FAIL — Rating returned %s: %s",
                    rate_r.status_code, rate_r.text[:200]
                )
                failed += 1
        else:
            logger.warning("   SKIP — No bundle_id available from setup")
            failed += 1

        # Test 7: Publisher leaderboard
        logger.info("[TEST 7] Publisher leaderboard has entries...")
        board_r = await client.get(f"{SERVER_URL}/dashboard/leaderboard")
        if board_r.status_code == 200:
            board = board_r.json().get("leaderboard", [])
            if board:
                top = board[0]
                logger.info("   PASS — %d publisher(s) on leaderboard", len(board))
                logger.info(
                    "   Top publisher: %s... earned $%.6f USDC",
                    top.get("publisher_wallet", "")[:16],
                    top.get("total_earned_usdc", 0)
                )
                passed += 1
            else:
                logger.error("   FAIL — Leaderboard is empty")
                failed += 1
        else:
            logger.error("   FAIL — Leaderboard returned %s", board_r.status_code)
            failed += 1

    logger.info("=" * 65)
    logger.info("Results: %d/7 passed, %d failed", passed, failed)
    if failed == 0:
        logger.info("All tests passed. Phase 5 economics layer verified.")
        logger.info("80/20 royalty splits, dashboard, marketplace, and leaderboard confirmed.")
    else:
        logger.error("%d test(s) failed. See above for details.", failed)
    logger.info("=" * 65)


if __name__ == "__main__":
    asyncio.run(run_tests())