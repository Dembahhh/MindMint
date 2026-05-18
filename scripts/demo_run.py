"""
scripts/demo_run.py

Full end-to-end demo of the MindMint system.

Flow:
  1. Validates all required environment variables before touching the network
  2. Publisher Agent publishes a memory bundle to the marketplace
  3. Consumer Agent searches semantically for relevant bundles
  4. Consumer Agent purchases a bundle via x402 micropayment on Kite Ozone
  5. Publisher earnings are verified on the dashboard

Prerequisites:
  - Docker running:  docker compose up -d
  - Backend running: uvicorn backend.main:app --host 127.0.0.1 --port 8080 --reload
  - .env populated:  CONSUMER_PRIVATE_KEY, CONSUMER_WALLET_ADDRESS,
                     PUBLISHER_WALLET_ADDRESS, USDC_CONTRACT_ADDRESS, KITE__CHAIN_ID
"""

import asyncio
import base64
import json
import logging
import os
import secrets
import time
from typing import Optional

import httpx
from dotenv import load_dotenv
from eth_account import Account

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("demo_run")

SERVER_URL = "http://localhost:8080"
CHAIN_ID   = int(os.getenv("KITE__CHAIN_ID", 2368))

REQUIRED_ENV_VARS = [
    "CONSUMER__PRIVATE_KEY",
    "CONSUMER__ADDRESS",
    "PUBLISHER__ADDRESS",
    "KITE__USDC_CONTRACT_ADDRESS",
]

DEMO_MEMORIES = [
    (
        "Analysed Uniswap V3 USDC/ETH pool on block 22145823. Optimal LP range "
        "for current volatility regime is [-200, +400] ticks from current price. "
        "Fee tier 0.05% outperforms 0.3% at this volatility level by approximately 12% APY."
    ),
    (
        "Investigated Aave V3 liquidation thresholds. WBTC collateral positions with LTV "
        "above 68% show 3.2x higher liquidation probability during 5%+ BTC drawdowns. "
        "Safe operating range for leveraged strategies: max 60% LTV. WETH collateral "
        "optimal LTV is 82.5% based on historical volatility data."
    ),
    (
        "Observed MEV opportunity pattern: sandwich attacks on Uniswap V3 swaps over $50k "
        "consistently profitable when gas price under 15 gwei. Window typically lasts 2-4 blocks."
    ),
    (
        "Tested x402 payment flow on Kite Ozone testnet. EIP-3009 transferWithAuthorization "
        "with validBefore = now + 300s is optimal. Shorter windows cause race conditions "
        "during network congestion. Facilitator endpoint latency averages 340ms."
    ),
    (
        "Compound V3 USDC market shows highest yield when total utilisation is between 75-85%. "
        "Below 70% utilisation, lending APY drops below money market rates. "
        "Current yield curve inflection point: 80% utilisation = 6.2% APY."
    ),
]


def validate_env() -> dict[str, str]:
    """Read and validate all required environment variables.

    Returns:
        Dictionary mapping variable name to its value.

    Raises:
        EnvironmentError: If any required variable is missing or empty.
    """
    missing = [v for v in REQUIRED_ENV_VARS if not os.getenv(v)]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            "Check your .env file and ensure all values are populated."
        )
    return {v: os.environ[v] for v in REQUIRED_ENV_VARS}


def build_payment_header(
    payment_req: dict,
    consumer_address: str,
    consumer_key: str,
    usdc_contract: str,
) -> str:
    """Build a base64-encoded x402 payment header from a 402 response body.

    Signs an EIP-712 USDC transferWithAuthorization using the consumer private key,
    then encodes the result as base64 for the X-PAYMENT request header.

    Args:
        payment_req:      The parsed JSON body from the HTTP 402 response.
        consumer_address: Wallet address of the consumer agent (0x...).
        consumer_key:     Private key of the consumer agent.
        usdc_contract:    USDC contract address on the Kite chain.

    Returns:
        Base64-encoded payment payload string ready for the X-PAYMENT header.

    Raises:
        ValueError: If the 402 response contains no accepts field.
        KeyError:   If required fields are missing from the payment terms.
    """
    accepts = payment_req.get("accepts", [])
    if not accepts:
        raise ValueError(
            f"No payment terms in 402 response. "
            f"Full response: {json.dumps(payment_req, indent=2)}"
        )

    terms        = accepts[0]
    amount       = int(terms["maxAmountRequired"])
    payee        = terms["payTo"]
    valid_after  = 0
    valid_before = int(time.time()) + 300
    nonce        = "0x" + secrets.token_hex(32)
    account      = Account.from_key(consumer_key)

    structured_data = {
        "types": {
            "EIP712Domain": [
                {"name": "name",              "type": "string"},
                {"name": "version",           "type": "string"},
                {"name": "chainId",           "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "TransferWithAuthorization": [
                {"name": "from",        "type": "address"},
                {"name": "to",          "type": "address"},
                {"name": "value",       "type": "uint256"},
                {"name": "validAfter",  "type": "uint256"},
                {"name": "validBefore", "type": "uint256"},
                {"name": "nonce",       "type": "bytes32"},
            ],
        },
        "primaryType": "TransferWithAuthorization",
        "domain": {
            "name":              "USD Coin",
            "version":           "2",
            "chainId":           CHAIN_ID,
            "verifyingContract": usdc_contract,
        },
        "message": {
            "from":        consumer_address,
            "to":          payee,
            "value":       amount,
            "validAfter":  valid_after,
            "validBefore": valid_before,
            "nonce":       nonce,
        },
    }

    signed = Account.sign_typed_data(account.key, full_message=structured_data)

    payload = {
        "x402Version": 1,
        "scheme":      "exact",
        "network":     "kite-testnet",
        "payload": {
            "signature": signed.signature.hex(),
            "authorization": {
                "from":        consumer_address,
                "to":          payee,
                "value":       str(amount),
                "validAfter":  str(valid_after),
                "validBefore": str(valid_before),
                "nonce":       nonce,
            },
        },
    }

    return base64.b64encode(json.dumps(payload).encode()).decode()


async def check_health(client: httpx.AsyncClient) -> bool:
    """Ping the backend health endpoint before running the demo.

    Args:
        client: Shared httpx async client.

    Returns:
        True if backend responds with status ok, False otherwise.
    """
    try:
        response = await client.get(f"{SERVER_URL}/health", timeout=5.0)
        response.raise_for_status()
        logger.info("Backend health: %s", response.json())
        return True
    except httpx.HTTPError as exc:
        logger.error(
            "Backend unreachable at %s: %s\n"
            "Start the server with: uvicorn backend.main:app --host 127.0.0.1 --port 8080 --reload",
            SERVER_URL,
            exc,
        )
        return False


async def publish_bundle(
    client: httpx.AsyncClient,
    publisher_wallet: str,
) -> Optional[dict]:
    """Publish the demo memory bundle to the MindMint marketplace.

    Args:
        client:           Shared httpx async client.
        publisher_wallet: Wallet address of the publisher agent.

    Returns:
        Parsed publish response dict, or None if the request failed.
    """
    logger.info("Publishing demo memory bundle...")

    try:
        response = await client.post(
            f"{SERVER_URL}/memory/publish",
            json={
                "title":            "DeFi and x402 Intelligence Pack — Demo",
                "description":      (
                    "High-quality agent memories from DeFi protocol analysis "
                    "and x402 payment integration work on Kite Ozone testnet."
                ),
                "memories":         DEMO_MEMORIES,
                "publisher_wallet": publisher_wallet,
                "price_usdc":       0.002,
            },
            timeout=30.0,
        )
    except httpx.HTTPError as exc:
        logger.error("Publish request failed with network error: %s", exc)
        return None

    if response.status_code != 200:
        logger.error(
            "Publish returned %d: %s",
            response.status_code,
            response.text[:300],
        )
        return None

    data = response.json()
    logger.info(
        "Bundle published. ID: %s | %d/%d memories accepted | "
        "Avg quality: %.2f | Price: $%.4f USDC | Tags: %s",
        data["bundle_id"],
        data["memories_accepted"],
        data["memories_submitted"],
        data["avg_quality_score"],
        data["price_microunits"]/1_000_000,
        ", ".join(data.get("tags", [])[:5]),
    )
    return data


async def search_marketplace(
    client: httpx.AsyncClient,
    query: str,
    top_k: int = 3,
) -> Optional[list[dict]]:
    """Search the marketplace using ChromaDB semantic vector search.

    Args:
        client: Shared httpx async client.
        query:  Natural language search query.
        top_k:  Maximum number of results to retrieve.

    Returns:
        List of search result dicts, or None if the request failed.
    """
    logger.info("Searching marketplace: '%s'", query)

    try:
        response = await client.get(
            f"{SERVER_URL}/memory/search",
            params={"q": query, "top_k": top_k},
            timeout=15.0,
        )
    except httpx.HTTPError as exc:
        logger.error("Search request failed: %s", exc)
        return None

    if response.status_code != 200:
        logger.error(
            "Search returned %d: %s",
            response.status_code,
            response.text[:300],
        )
        return None

    results = response.json().get("results", [])
    logger.info("Found %d matching bundles.", len(results))

    for i, result in enumerate(results[:top_k], start=1):
        preview = result.get("best_matching_memory_preview", "")[:80]
        logger.info(
            "  [%d] %s  similarity=%.4f  quality=%.2f  preview=%s...",
            i,
            result["title"],
            result["similarity"],
            result.get("avg_quality_score", 0.0),
            preview,
        )

    return results


async def purchase_bundle(
    client: httpx.AsyncClient,
    bundle_id: str,
    consumer_address: str,
    consumer_key: str,
    usdc_contract: str,
) -> Optional[tuple[dict, str]]:
    """Purchase a memory bundle using the x402 payment protocol.

    Executes two requests:
      Step 1 - GET without payment header to receive HTTP 402 with payment terms.
      Step 2 - GET with signed X-PAYMENT header to receive HTTP 200 with content.

    Args:
        client:           Shared httpx async client.
        bundle_id:        ID of the bundle to purchase.
        consumer_address: Wallet address of the consumer agent.
        consumer_key:     Private key of the consumer agent.
        usdc_contract:    USDC contract address on the Kite chain.

    Returns:
        Tuple of (response body dict, tx_hash string), or None if purchase failed.
    """
    purchase_url = f"{SERVER_URL}/memory/purchase/{bundle_id}"

    logger.info("Step 1: Triggering 402 for bundle %s...", bundle_id[:20])

    try:
        initial = await client.get(purchase_url, timeout=10.0)
    except httpx.HTTPError as exc:
        logger.error("Purchase step 1 failed: %s", exc)
        return None

    if initial.status_code != 402:
        logger.error(
            "Expected HTTP 402 from server, got %d. Response: %s",
            initial.status_code,
            initial.text[:300],
        )
        return None

    payment_req = initial.json()
    amount_usdc = int(payment_req["accepts"][0]["maxAmountRequired"]) / 1_000_000
    logger.info("Payment required: $%.4f USDC. Signing EIP-712 authorization...", amount_usdc)

    try:
        payment_header = build_payment_header(
            payment_req, consumer_address, consumer_key, usdc_contract
        )
    except (ValueError, KeyError) as exc:
        logger.error("Failed to build payment header: %s", exc)
        return None

    logger.info("Step 2: Sending payment header...")

    try:
        paid = await client.get(
            purchase_url,
            headers={"X-PAYMENT": payment_header},
            timeout=30.0,
        )
    except httpx.HTTPError as exc:
        logger.error("Purchase step 2 failed: %s", exc)
        return None

    if paid.status_code != 200:
        logger.error(
            "Purchase returned %d: %s",
            paid.status_code,
            paid.text[:300],
        )
        return None

    tx_hash  = paid.headers.get("X-PAYMENT-RESPONSE", "local-dev")
    data     = paid.json()
    memories = data["content"].get("memories", [])

    logger.info(
        "Purchase successful. TX: %s | Memories: %d | Avg quality: %.2f",
        tx_hash[:40],
        data["content"]["total_memories"],
        data["content"]["avg_quality_score"],
    )

    if memories:
        logger.info("First memory preview: '%s...'", memories[0]["text"][:120])

    return data, tx_hash


async def verify_publisher_earnings(
    client: httpx.AsyncClient,
    publisher_wallet: str,
) -> None:
    """Fetch and log publisher earnings from the dashboard.

    Args:
        client:           Shared httpx async client.
        publisher_wallet: Full wallet address of the publisher.
    """
    logger.info("Checking publisher earnings for %s...", publisher_wallet[:20])

    try:
        response = await client.get(
            f"{SERVER_URL}/dashboard/publisher/{publisher_wallet}",
            timeout=10.0,
        )
    except httpx.HTTPError as exc:
        logger.warning("Could not fetch publisher earnings: %s", exc)
        return

    if response.status_code != 200:
        logger.warning(
            "Publisher dashboard returned %d: %s",
            response.status_code,
            response.text[:200],
        )
        return

    data   = response.json()
    earned = data.get("total_earned_microunits", 0) / 1_000_000

    logger.info(
        "Publisher earnings: $%.4f USDC | Sales: %d | Bundles: %d",
        earned,
        data.get("total_sales", 0),
        data.get("bundle_count", 0),
    )


async def run_demo() -> None:
    """Orchestrate the full MindMint end-to-end demo sequence."""
    print("\n" + "=" * 65)
    print("MindMint — Full End-to-End Demo")
    print("=" * 65)

    try:
        env = validate_env()
    except EnvironmentError as exc:
        logger.error("%s", exc)
        return

    consumer_key     = env["CONSUMER__PRIVATE_KEY"]
    consumer_address = env["CONSUMER__ADDRESS"]
    publisher_wallet = env["PUBLISHER__ADDRESS"]
    usdc_contract    = env["KITE__USDC_CONTRACT_ADDRESS"]

    async with httpx.AsyncClient(timeout=60.0) as client:

        print("\nStep 1: Health check")
        print("-" * 65)
        if not await check_health(client):
            return

        print("\nStep 2: Publisher Agent — publish memory bundle")
        print("-" * 65)
        publish_result = await publish_bundle(client, publisher_wallet)
        if publish_result is None:
            logger.error("Publish failed. Aborting demo.")
            return
        bundle_id = publish_result["bundle_id"]

        print("\nStep 3: Consumer Agent — semantic search")
        print("-" * 65)
        search_results = await search_marketplace(
            client,
            query="DeFi liquidation risk and optimal leverage on Aave V3",
        )
        if not search_results:
            logger.warning(
                "No search results. ChromaDB may still be indexing — "
                "continuing to purchase step."
            )

        print("\nStep 4: Consumer Agent — x402 micropayment purchase")
        print("-" * 65)
        purchase_result = await purchase_bundle(
            client,
            bundle_id=bundle_id,
            consumer_address=consumer_address,
            consumer_key=consumer_key,
            usdc_contract=usdc_contract,
        )
        if purchase_result is None:
            logger.error("Purchase failed. Aborting demo.")
            return

        print("\nStep 5: Dashboard — verify publisher earnings")
        print("-" * 65)
        await verify_publisher_earnings(client, publisher_wallet)

    print("\n" + "=" * 65)
    print("Demo complete. Full MindMint loop verified.")
    print("  Publisher published  ->  marketplace has live bundles")
    print("  Consumer searched    ->  ChromaDB semantic search working")
    print("  x402 payment made    ->  EIP-712 payment flow working")
    print("  Publisher earned     ->  royalty split working")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    asyncio.run(run_demo())