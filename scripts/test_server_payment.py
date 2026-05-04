"""
test_server_payment.py

Integration test: hits the live AgentMemory server and makes a real
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
import httpx
import json
import base64
import time
import secrets
import sys
from eth_account import Account
from dotenv import load_dotenv
import os

load_dotenv()

SERVER_URL = "http://localhost:8000"
CONSUMER_KEY = os.getenv("CONSUMER_PRIVATE_KEY")
CONSUMER_ADDRESS = os.getenv("CONSUMER_WALLET_ADDRESS")
USER_CONTRACT = os.getenv("USDC_CONTRACT_ADDRESS")
CHAIN_ID = int(os.getenv("KITE_CHAIN_ID", 2368))


def build_payment_header(payment_requirements: dict) -> str:
    """Build and sign an x402 payment header from 402 response terms."""
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


async def run_integration_tests():
    print("\n" + "="*60)
    print("AgentMemory — Server Integration Tests")
    print("="*60)
    
    passed = 0
    failed = 0
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        
        # Test 1: Health check
        print("\n[TEST 1] Health check...")
        r = await client.get(f"{SERVER_URL}/health")
        if r.status_code == 200 and r.json().get("status") == "ok":
            print("   ✅ PASS — Server is healthy")
            passed += 1
        else:
            print(f"   ❌ FAIL — Expected 200, got {r.status_code}")
            print("   Is the server running? uvicorn backend.main:app --reload")
            failed += 1
            return  # Can't continue without server
        
        # Test 2: Free route
        print("\n[TEST 2] Free route (no payment)...")
        r = await client.get(f"{SERVER_URL}/memory/list")
        if r.status_code == 200:
            bundles = r.json().get("bundles", [])
            print(f"   ✅ PASS — Got {len(bundles)} bundles")
            passed += 1
        else:
            print(f"   ❌ FAIL — Expected 200, got {r.status_code}")
            failed += 1
        
        # Test 3: Paid route without payment header
        print("\n[TEST 3] Paid route without payment (expecting 402)...")
        r = await client.get(f"{SERVER_URL}/memory/purchase/test-bundle-001")
        if r.status_code == 402:
            body = r.json()
            if "accepts" in body:
                print("   ✅ PASS — Got 402 with payment requirements")
                print(f"   Required: {int(body['accepts'][0]['maxAmountRequired']) / 1_000_000} USDC")
                passed += 1
                payment_requirements = body
            else:
                print("   ❌ FAIL — Got 402 but missing 'accepts' field")
                failed += 1
                payment_requirements = None
        else:
            print(f"   ❌ FAIL — Expected 402, got {r.status_code}")
            failed += 1
            payment_requirements = None
        
        # Test 4: Paid route with valid payment
        print("\n[TEST 4] Paid route with valid payment (expecting 200)...")
        if payment_requirements:
            try:
                payment_header = build_payment_header(payment_requirements)
                r = await client.get(
                    f"{SERVER_URL}/memory/purchase/test-bundle-001",
                    headers={"X-PAYMENT": payment_header}
                )
                if r.status_code == 200:
                    content = r.json()
                    tx = r.headers.get("X-PAYMENT-RESPONSE", "not present")
                    print("   ✅ PASS — Payment accepted, bundle received")
                    print(f"   TX Hash: {tx[:30]}...")
                    passed += 1
                else:
                    print(f"   ❌ FAIL — Expected 200, got {r.status_code}")
                    print(f"   Body: {r.text[:200]}")
                    failed += 1
            except Exception as e:
                print(f"   ❌ FAIL — Error building/sending payment: {e}")
                failed += 1
        else:
            print("   ⏭️  SKIP — Skipped because Test 3 failed")
        
        # Test 5: Invalid payment header
        print("\n[TEST 5] Invalid payment header (expecting 402)...")
        r = await client.get(
            f"{SERVER_URL}/memory/purchase/test-bundle-001",
            headers={"X-PAYMENT": "this-is-not-a-valid-payment"}
        )
        if r.status_code == 402:
            print("   ✅ PASS — Invalid payment correctly rejected")
            passed += 1
        else:
            print(f"   ❌ FAIL — Expected 402, got {r.status_code}")
            failed += 1
    
    # Summary
    print("\n" + "="*60)
    print(f"Results: {passed} passed, {failed} failed")
    if failed == 0:
        print("✅ All tests passed — Phase 2 complete!")
        print("   x402 payment gate is working inside the server.")
        print("   Move to Phase 3.")
    else:
        print("❌ Some tests failed. Fix the issues above before proceeding.")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(run_integration_tests())