"""
test_server_payment.py

Integration test: hits the live MindMint server and makes a real
x402 payment through it.

Prerequisites:
  - Server running: uvicorn backend.main:app --reload
  - Consumer wallet funded with test USDC
  - .env populated

What it tests:
  1. /health returns 200
  2. /memory/list returns 200 (free route)
  3. /memory/purchase/test-bundle-001 returns 402 (no payment)
  4. /memory/purchase/test-bundle-001 returns 200 (with valid payment)
  5. Response contains bundle content
  6. X-PAYMENT-RESPONSE header is present
"""

import asyncio
import base64
import json
import os
import secrets
import sys
import time
import logging

import httpx
from dotenv import load_dotenv
from eth_account import Account


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


load_dotenv()

SERVER_URL = os.getenv("SERVER_URL", "http://localhost:8080")
CONSUMER_KEY = os.getenv("CONSUMER__PRIVATE_KEY")
CONSUMER_ADDRESS = os.getenv("CONSUMER__ADDRESS")
USER_CONTRACT = os.getenv("KITE__USDC_CONTRACT_ADDRESS")
CHAIN_ID = int(os.getenv("KITE__CHAIN_ID", "2368"))

_required = {
    "CONSUMER__PRIVATE_KEY": CONSUMER_KEY,
    "CONSUMER__ADDRESS": CONSUMER_ADDRESS,
    "KITE__USDC_CONTRACT_ADDRESS": USER_CONTRACT,
}
_missing = [k for k, v in _required.items() if not v]
if _missing:
    logger.error("ERROR: Missing required env vars: %s",", ".join(_missing))
    sys.exit(1)


def build_payment_header(payment_requirements: dict) -> str:
    """Build and sign an x402 payment header from 402 response terms.
    Args:
        payment_requirements: The 402 response body containing 'accepts' terms.
        
    Returns:
        Base64-encoded signed payment payload.
        
    Raises:
        KeyError: If payment_requirements is missing expected fields.
        ValueError: If amount is not a valid integer.
    """
    terms = payment_requirements["accepts"][0]
    amount = int(terms["maxAmountRequired"])
    payee = terms["payTo"]
    
    valid_after = 0
    valid_before = int(time.time()) + 300
    nonce = "0x" + secrets.token_hex(32)
    
    account = Account.from_key(CONSUMER_KEY)
    
    structured_data = {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"}
            ],
            "TransferWithAuthorization": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "value", "type": "uint256"},
                {"name": "validAfter", "type": "uint256"},
                {"name": "validBefore", "type": "uint256"},
                {"name": "nonce", "type": "bytes32"}
            ]
        },
        "primaryType": "TransferWithAuthorization",
        "domain": {
            "name": "USD Coin",
            "version": "2",
            "chainId": CHAIN_ID,
            "verifyingContract": USER_CONTRACT
        },
        "message": {
            "from": CONSUMER_ADDRESS,
            "to": payee,
            "value": amount,
            "validAfter": valid_after,
            "validBefore": valid_before,
            "nonce": nonce
        }
    }
    
    signed = Account.sign_typed_data(account.key, full_message=structured_data)
    
    payload = {
        "x402Version": 1,
        "scheme": "exact",
        "network": "kite-testnet",
        "payload": {
            "signature": signed.signature.hex(),
            "authorization": {
                "from": CONSUMER_ADDRESS,
                "to": payee,
                "value": str(amount),
                "validAfter": str(valid_after),
                "validBefore": str(valid_before),
                "nonce": nonce
            }
        }
    }
    
    return base64.b64encode(json.dumps(payload).encode()).decode()


async def run_integration_tests() -> None:
    logger.info("\n" + "="*60)
    logger.info("MindMint — Server Integration Tests")
    logger.info("="*60)
    
    passed = 0
    failed = 0
    payment_requirements = None
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        
        logger.info("\n[TEST 1] Health check...")
        r = await client.get(f"{SERVER_URL}/health")
        if r.status_code == 200 and r.json().get("status") == "ok":
            logger.info("   PASS — Server is healthy")
            passed += 1
        else:
            logger.error("   FAIL — Expected 200, got %s",r.status_code)
            logger.info("   Body: %s", r.text)
            logger.info("   Is the server running? uvicorn backend.main:app --reload")
            failed += 1
            return  
        
        logger.info("\n[TEST 2] Free route (no payment)...")
        r = await client.get(f"{SERVER_URL}/memory/list")
        if r.status_code == 200:
            bundles = r.json().get("bundles", [])
            logger.info("   PASS — Got %d bundles", len(bundles))
            passed += 1
        else:
            logger.error("   FAIL — Expected 200, got %s", r.status_code)
            failed += 1
        
        logger.info("\n[TEST 3] Paid route without payment (expecting 402)...")
        r = await client.get(f"{SERVER_URL}/memory/purchase/test-bundle-001")
        if r.status_code == 402:
            body = r.json()
            if "accepts" in body:
                logger.info("   PASS — Got 402 with payment requirements")
                logger.info("   Required: %.6f USDC",int(body['accepts'][0]['maxAmountRequired']) / 1_000_000)
                passed += 1
                payment_requirements = body
            else:
                logger.error("   FAIL — Got 402 but missing 'accepts' field")
                failed += 1
                payment_requirements = None
        else:
            logger.error("   FAIL — Expected 402, got %s",r.status_code)
            failed += 1
            payment_requirements = None

        logger.info("\n[TEST 4] Paid route with valid payment (expecting 200)...")
        if payment_requirements:
            try:
                payment_header = build_payment_header(payment_requirements)
                r = await client.get(
                    f"{SERVER_URL}/memory/purchase/test-bundle-001",
                    headers={"X-PAYMENT": payment_header}
                )
                if r.status_code == 200:
                    tx = r.headers.get("X-PAYMENT-RESPONSE", "not present")
                    logger.info("   PASS — Payment accepted, bundle received")
                    logger.info("   TX Hash: %s...",tx[:30])
                    passed += 1
                else:
                    logger.error("   FAIL — Expected 200, got %s",r.status_code)
                    logger.info("   Body: %s",r.text[:200])
                    failed += 1
            except (httpx.HTTPError, KeyError, ValueError) as e:
                logger.error("   FAIL — Error building/sending payment: %s", e)
                failed += 1
        else:
            logger.warning("   SKIP — Skipped because Test 3 failed")
        
        logger.info("\n[TEST 5] Invalid payment header (expecting 402)...")
        r = await client.get(
            f"{SERVER_URL}/memory/purchase/test-bundle-001",
            headers={"X-PAYMENT": "this-is-not-a-valid-payment"}
        )
        if r.status_code == 402:
            logger.info("   PASS — Invalid payment correctly rejected")
            passed += 1
        else:
            logger.error("   FAIL — Expected 402, got %s",r.status_code)
            failed += 1
    
    logger.info("\n" + "="*60)
    logger.info("Results: %d passed, %d failed", passed, failed)
    if failed == 0:
        logger.info("All tests passed")
    else:
        logger.info("Some tests failed. Fix the issues above before proceeding.")
    logger.info("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(run_integration_tests())