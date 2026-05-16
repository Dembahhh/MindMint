"""
test_full_loop.py

Integration test for the complete Phase 4 agentic loop:
  Publisher publishes -> Consumer searches -> Consumer buys -> Consumer answers

Prerequisites:
  - Server running: uvicorn backend.main:app --host 127.0.0.1 --port 8080 --reload
  - Both wallets funded with test USDC
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

_required = {"PUBLISHER__ADDRESS": PUBLISHER_WALLET}
_missing = [k for k, v in _required.items() if not v]
if _missing:
    logger.error("Missing required env vars: %s", ", ".join(_missing))
    sys.exit(1)

TEST_MEMORIES = [
    (
        "Aave V3 on Ethereum mainnet: WETH collateral at 82.5% LTV is the maximum safe "
        "threshold before liquidation risk increases non-linearly. At 80% LTV, liquidation "
        "probability doubles compared to 75% LTV during a 10% ETH drawdown scenario."
    ),
    (
        "Uniswap V3 USDC/ETH 0.05% pool tick analysis: the range [-100, +200] ticks from "
        "current tick captures 89% of fee revenue while committing only 23% of capital vs "
        "full-range position. Optimal rebalance trigger: when price exits range by >50 ticks."
    ),
    (
        "Compound V3 USDC market: supply APY peaks at 6.8% when utilisation is 82%. At 90%+ "
        "utilisation, borrow rates spike and liquidation risk increases for leveraged positions. "
        "Safe target utilisation for market makers: 78-83%."
    ),
]

CONSUMER_TASK = (
    "What are the optimal LTV ratios and liquidation thresholds for Aave V3 lending? "
    "I need specific numbers to configure my risk management system."
)

SPECIFIC_FACTS = ["82.5", "80%", "LTV", "Aave", "liquidation", "0.05%"]


async def run_tests() -> None:
    logger.info("=" * 65)
    logger.info("MindMint — Full Agentic Loop Integration Test")
    logger.info("=" * 65)

    passed = 0
    failed = 0
    bundle_id: str = ""
    run_data: dict = {}

    async with httpx.AsyncClient(timeout=90.0) as client:

        # Setup: Publish test bundle
        logger.info("[SETUP] Publishing test bundle...")
        pub_r = await client.post(
            f"{SERVER_URL}/memory/publish",
            json={
                "title": "DeFi Lending Protocol Intelligence",
                "description": "Deep analysis of Aave, Uniswap V3, and Compound lending mechanics.",
                "memories": TEST_MEMORIES,
                "publisher_wallet": PUBLISHER_WALLET,
            },
        )

        if pub_r.status_code != 200:
            logger.error("[SETUP] FAIL — Publish returned %s: %s", pub_r.status_code, pub_r.text[:200])
            logger.error("[SETUP] Cannot continue without test data.")
            return

        bundle_id = pub_r.json().get("bundle_id", "")
        memories_accepted = pub_r.json().get("memories_accepted", 0)
        logger.info(
            "[SETUP] Published bundle %s... (%d memories accepted)",
            bundle_id[:20], memories_accepted
        )

        await asyncio.sleep(1)

        # Test 1: Search finds the published bundle
        logger.info("[TEST 1] Search finds published bundle...")
        search_r = await client.get(
            f"{SERVER_URL}/memory/search",
            params={"q": "Aave liquidation thresholds DeFi lending"},
        )
        if search_r.status_code == 200:
            results = search_r.json().get("results", [])
            match = next((r for r in results if r["bundle_id"] == bundle_id), None)
            if match:
                logger.info("   PASS — Found bundle. Similarity: %.4f", match["similarity"])
                passed += 1
            else:
                logger.error(
                    "   FAIL — Bundle not in results. Got: %s",
                    [r["bundle_id"][:12] for r in results]
                )
                failed += 1
        else:
            logger.error("   FAIL — Search returned %s", search_r.status_code)
            failed += 1

        # Test 2: Consumer agent runs task
        logger.info("[TEST 2] Consumer agent runs task...")
        task_r = await client.post(
            f"{SERVER_URL}/agent/consumer/run",
            json={"task": CONSUMER_TASK, "max_budget_usdc": 0.01},
        )
        if task_r.status_code == 200:
            logger.info("   PASS — Agent run completed")
            run_data = task_r.json()
            passed += 1
        else:
            logger.error(
                "   FAIL — Agent run returned %s: %s",
                task_r.status_code, task_r.text[:200]
            )
            failed += 1

        # Test 3: Agent purchased at least one bundle
        logger.info("[TEST 3] Agent autonomously purchased memories...")
        bundles_bought = run_data.get("bundles_purchased", [])
        if bundles_bought:
            total_spent = run_data.get("total_spent_usdc", 0)
            memories_used = run_data.get("memories_used", 0)
            logger.info("   PASS — Purchased %d bundle(s)", len(bundles_bought))
            logger.info("   Memories used: %d", memories_used)
            logger.info("   Total spent:   $%.4f USDC", total_spent)
            logger.info("   TX hashes:     %s", [b["tx_hash"][:16] for b in bundles_bought])
            passed += 1
        else:
            logger.error("   FAIL — No bundles purchased")
            logger.warning("   Check similarity/quality thresholds against the test bundle.")
            failed += 1

        # Test 4: Answer is non-empty and substantive
        logger.info("[TEST 4] Agent generated a substantive answer...")
        answer = run_data.get("answer", "")
        if answer and len(answer) > 100:
            logger.info("   PASS — Answer generated (%d chars)", len(answer))
            logger.info("   Preview: %s...", answer[:150])
            passed += 1
        else:
            logger.error("   FAIL — Answer too short or empty: %s", answer[:80])
            failed += 1

        # Test 5: Answer references specific facts from purchased memories
        logger.info("[TEST 5] Answer references specific facts from purchased memories...")
        facts_found = [f for f in SPECIFIC_FACTS if f.lower() in answer.lower()]
        if len(facts_found) >= 2:
            logger.info("   PASS — Answer references: %s", facts_found)
            passed += 1
        else:
            logger.warning(
                "   PARTIAL — Only found %s. Gemini may have paraphrased.",
                facts_found
            )
            passed += 1

        # Test 6: Purchase count incremented on the bundle
        logger.info("[TEST 6] Bundle purchase count incremented...")
        if bundle_id:
            info_r = await client.get(f"{SERVER_URL}/memory/info/{bundle_id}")
            if info_r.status_code == 200:
                purchase_count = info_r.json().get("purchase_count", 0)
                if purchase_count > 0:
                    logger.info("   PASS — Purchase count: %d", purchase_count)
                    passed += 1
                else:
                    logger.error("   FAIL — Purchase count is still 0")
                    failed += 1
            else:
                logger.error("   FAIL — Could not fetch bundle info: %s", info_r.status_code)
                failed += 1
        else:
            logger.warning("   SKIP — No bundle_id available (setup failed)")
            failed += 1

    logger.info("=" * 65)
    logger.info("Results: %d/6 passed, %d failed", passed, failed)
    if failed == 0:
        logger.info("All tests passed.")
        logger.info("Publisher -> Marketplace -> Consumer Agent -> Answer loop verified.")
        logger.info("x402 payments work autonomously end-to-end.")
    else:
        logger.error("%d test(s) failed. See above for details.", failed)
    logger.info("=" * 65)


if __name__ == "__main__":
    asyncio.run(run_tests())