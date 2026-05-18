"""
test_x402_payment.py

Proof-of-concept: makes a real x402 micropayment on Kite Ozone Testnet.

This script demonstrates the full payment loop:
  GET protected resource → 402 → pay → GET with receipt → 200

If this script runs successfully, the entire payment infrastructure
for MindMint is confirmed working.
"""

import asyncio
import dotenv
import httpx
import json
import base64
from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3
from dotenv import load_dotenv
import rootutils  
from pathlib import Path
import os
import sys

root = rootutils.setup_root(search_from=__file__, indicator=".env", pythonpath=True, dotenv=True)
load_dotenv(dotenv_path=root / ".env")

print("KEY loaded:", bool(os.getenv("CONSUMER_PRIVATE_KEY")))
print("ADDRESS loaded:", bool(os.getenv("CONSUMER_WALLET_ADDRESS")))
print("USDC loaded:", bool(os.getenv("USDC_CONTRACT_ADDRESS")))

assert os.getenv("CONSUMER_PRIVATE_KEY"), "CONSUMER_PRIVATE_KEY missing from .env!"

RPC_URL = os.getenv("KITE_RPC_URL", "https://rpc.testnet.gokite.ai")
FACILITATOR_URL = os.getenv("KITE_FACILITATOR_URL")
CONSUMER_ADDRESS = os.getenv("CONSUMER_WALLET_ADDRESS")
CONSUMER_KEY = os.getenv("CONSUMER_PRIVATE_KEY")
USDC_ADDRESS = os.getenv("USDC_CONTRACT_ADDRESS")

TEST_ENDPOINT = "https://api.testnet.gokite.ai/x402/example"


w3 = Web3(Web3.HTTPProvider(RPC_URL))
consumer_account = Account.from_key(CONSUMER_KEY)

ERC20_ABI = [
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
        "stateMutability": "view"
    },
    {
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"},
            {"name": "value", "type": "uint256"},
            {"name": "validAfter", "type": "uint256"},
            {"name": "validBefore", "type": "uint256"},
            {"name": "nonce", "type": "bytes32"},
            {"name": "v", "type": "uint8"},
            {"name": "r", "type": "bytes32"},
            {"name": "s", "type": "bytes32"}
        ],
        "name": "transferWithAuthorization",
        "outputs": [],
        "type": "function"
    }
]


def check_usdc_balance() -> float:
    """Check consumer wallet USDC balance on testnet."""
    try:
        usdc = w3.eth.contract(
            address=Web3.to_checksum_address(USDC_ADDRESS),
            abi=ERC20_ABI
        )
        raw_balance = usdc.functions.balanceOf(
            Web3.to_checksum_address(CONSUMER_ADDRESS)
        ).call()
        return raw_balance / 1_000_000 
    except Exception as e:
        print(f"   Could not check balance: {e}")
        return -1

def sign_x402_payment(payment_terms: dict) -> str:
    """
    Signs a USDC transferWithAuthorization for x402.
    
    x402 uses EIP-3009 (transferWithAuthorization) which lets a wallet
    pre-authorise a transfer without submitting the transaction itself.
    The facilitator receives this signed authorisation and submits it
    on-chain, covering the gas fee.
    
    Returns: base64-encoded payment payload for X-PAYMENT header
    """
    import time
    import secrets
    
    amount = int(payment_terms["maxAmountRequired"])
    payee = payment_terms["payTo"]

    valid_after = 0
    valid_before = int(time.time()) + 300  
    nonce = "0x" + secrets.token_hex(32)
    
    domain = {
        "name": "USD Coin",
        "version": "2",
        "chainId": int(os.getenv("KITE_CHAIN_ID", 2368)),
        "verifyingContract": USDC_ADDRESS
    }
    
    message_data = {
        "from": CONSUMER_ADDRESS,
        "to": payee,
        "value": amount,
        "validAfter": valid_after,
        "validBefore": valid_before,
        "nonce": nonce
    }

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
        "domain": domain,
        "message": message_data
    }
    
    signed = Account.sign_typed_data(
        consumer_account.key,
        full_message=structured_data
    )
    
    payment_payload = {
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
    
    return base64.b64encode(
        json.dumps(payment_payload).encode()
    ).decode()


async def run_x402_test():
    print("\n" + "="*60)
    print("MindMint — x402 Payment Test")
    print("="*60)
    
    print("\n[1/5] Checking Kite Testnet connectivity...")
    if w3.is_connected():
        block = w3.eth.block_number
        print(f"   ✅ Connected. Current block: {block}")
    else:
        print("   ❌ Cannot connect to Kite RPC. Check KITE_RPC_URL in .env")
        sys.exit(1)
    
    print("\n[2/5] Checking Consumer wallet USDC balance...")
    balance = check_usdc_balance()
    if balance > 0:
        print(f"   ✅ Balance: ${balance:.4f} USDC")
    elif balance == 0:
        print("   ❌ Balance is 0. Claim test USDC from testnet.gokite.ai faucet first.")
        sys.exit(1)
    else:
        print("   ⚠️  Could not verify balance. Proceeding anyway...")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        
        print(f"\n[3/5] Requesting protected endpoint (expecting 402)...")
        print(f"   URL: {TEST_ENDPOINT}")
        
        response = await client.get(TEST_ENDPOINT)
        
        if response.status_code == 402:
            print(f"   ✅ Got HTTP 402 as expected")
            payment_requirements = response.json()
            terms = payment_requirements["accepts"][0]
            amount_usdc = int(terms["maxAmountRequired"]) / 1_000_000
            print(f"   Payment required: ${amount_usdc:.4f} USDC")
            print(f"   Pay to: {terms['payTo'][:20]}...")
        elif response.status_code == 200:
            print("   ⚠️  Got 200 — endpoint may not be payment-protected on testnet")
            print("   Treating as success for connectivity test purposes")
            print(f"   Content: {response.text[:100]}")
            return
        else:
            print(f"   ❌ Unexpected status: {response.status_code}")
            print(f"   Body: {response.text}")
            sys.exit(1)
        
        print("\n[4/5] Signing x402 payment...")
        try:
            signed_payment = sign_x402_payment(terms)
            print("   ✅ Payment signed successfully")
        except Exception as e:
            print(f"   ❌ Signing failed: {e}")
            sys.exit(1)
        
        print("\n[5/5] Retrying request with payment receipt...")
        paid_response = await client.get(
            TEST_ENDPOINT,
            headers={"X-PAYMENT": signed_payment}
        )
        
        if paid_response.status_code == 200:
            tx_hash = paid_response.headers.get("X-PAYMENT-RESPONSE", "not in headers")
            print(f"   ✅ Payment accepted! HTTP 200 received")
            print(f"   TX Hash: {tx_hash}")
            print(f"   Content: {paid_response.text[:200]}")
        else:
            print(f"   ❌ Payment rejected. Status: {paid_response.status_code}")
            print(f"   Body: {paid_response.text}")
            sys.exit(1)
    
    print("\n" + "="*60)
    print(" Phase 1 Complete — x402 payment pipeline confirmed working")
    print("   You are ready to build Phase 2.")
    print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(run_x402_test())