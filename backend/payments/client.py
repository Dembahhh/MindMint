"""
payments/client.py

Reusable x402 payment client for the Consumer Agent.

This module handles the mechanical work of:
  1. Signing a USDC transferWithAuthorization (EIP-3009 / EIP-712)
  2. Encoding the signed payload as base64
  3. Making the HTTP request with X-PAYMENT header
  4. Returning the response or raising on failure

The Consumer Agent calls pay_for_bundle() and gets back
the purchased content. It never touches private keys directly.
"""

import asyncio
import base64
import json
import logging
import secrets
import time
from typing import Optional, Any

import httpx
from eth_account import Account

from backend.config import settings

logger = logging.getLogger(__name__)

_consumer_account: Optional[Account] = None

def _get_consumer_account() -> Account:
    """Returns the consumer signing account, initializing it on first call."""
    global _consumer_account
    if _consumer_account is None:
        _consumer_account = Account.from_key(
            settings.consumer.private_key.get_secret_value()
        )
    return _consumer_account


def _sign_payment(payment_requirements: dict) -> str:
    """
    Signs a USDC transferWithAuthorization for the given payment requirements.
    
    Called internally by pay_for_resource(). Takes the 402 response body
    and returns a base64-encoded X-PAYMENT header value.
    
    The signing uses EIP-712 structured data:
      - domain: USD Coin v2 on Kite testnet
      - message: TransferWithAuthorization
        (from, to, value, validAfter, validBefore, nonce)
    
    The nonce is 32 random bytes to prevent replay attacks.
    validBefore = now + 300 seconds (5 minute payment window).
    """
    try:
        terms = payment_requirements["accepts"][0]
        amount = int(terms["maxAmountRequired"])
        payee = terms["payTo"]
    except (KeyError, IndexError, ValueError) as e:
        raise ValueError(f"Malformed payment requirements from server: {e}") from e
    
    valid_after = 0
    valid_before = int(time.time()) + 300
    nonce = "0x" + secrets.token_hex(32)
    
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
            "chainId": settings.kite.chain_id,
            "verifyingContract": settings.kite.usdc_contract_address
        },
        "message": {
            "from": settings.consumer.address,
            "to": payee,
            "value": amount,
            "validAfter": valid_after,
            "validBefore": valid_before,
            "nonce": nonce
        }
    }
    
    signed = Account.sign_typed_data(
        _get_consumer_account().key,
        full_message=structured_data
    )
    
    payload = {
        "x402Version": 1,
        "scheme": "exact",
        "network": "kite-testnet",
        "payload": {
            "signature": signed.signature.hex(),
            "authorization": {
                "from": settings.consumer.address,
                "to": payee,
                "value": str(amount),
                "validAfter": str(valid_after),
                "validBefore": str(valid_before),
                "nonce": nonce
            }
        }
    }
    
    return base64.b64encode(json.dumps(payload).encode()).decode()


async def pay_for_resource(
    url: str,
    method: str = "GET",
    base_url: Optional[str] = None,
    max_retries: int = 2
) -> dict[str, Any]:
    """
    Makes a payment-gated HTTP request using x402.
    
    Flow:
      1. Make initial request (expect 402)
      2. Read payment requirements from 402 body
      3. Sign the payment
      4. Retry with X-PAYMENT header
      5. Return response body as dict
    
    Args:
      url        — Path on the server (e.g., "/memory/purchase/abc-123")
      method     — HTTP method (GET for memory purchase)
      base_url   — Server base URL
      max_retries — How many times to retry on transient errors
    
    Returns:
      Response JSON as dict
    
    Raises:
      ValueError if payment is rejected after signing
      httpx.HTTPError on network errors
    """
    if base_url is None:
        base_url = settings.api.base_url
    full_url = f"{base_url}{url}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        logger.info("[x402-client] GET %s (no payment)", url)
        
        if method == "GET":
            response = await client.get(full_url)
        else:
            response = await client.request(method, full_url)
        
        if response.status_code == 200:
            logger.debug("[x402-client] Resource was free, no payment needed.")
            return response.json()
        
        if response.status_code != 402:
            response.raise_for_status()
        
        payment_requirements = response.json()
        try:
            amount_usdc = int(
                payment_requirements["accepts"][0]["maxAmountRequired"]
            ) / 1_000_000
        except (KeyError, IndexError, ValueError) as e:
            raise ValueError(f"Malformed payment requirements from server: {e}") from e
        logger.info(
            "[x402-client] Payment required: $%.4f USDC. Signing...",
            amount_usdc
        )
        
        payment_header = _sign_payment(payment_requirements)
        
        for attempt in range(max_retries):
            logger.info(
                "[x402-client] Retrying with payment (attempt %d/%d)...",
                attempt + 1, max_retries
            )
            
            if method == "GET":
                paid_response = await client.get(
                    full_url,
                    headers={"X-PAYMENT": payment_header}
                )
            else:
                paid_response = await client.request(
                    method, full_url,
                    headers={"X-PAYMENT": payment_header}
                )
            
            if paid_response.status_code == 200:
                tx_hash = paid_response.headers.get("X-PAYMENT-RESPONSE", "unknown")
                logger.info(
                    "[x402-client] Payment accepted! TX: %s. Amount: $%.4f USDC",
                    tx_hash[:20], amount_usdc
                )
                result = paid_response.json()
                result["_payment_meta"] = {
                    "tx_hash": tx_hash,
                    "amount_usdc": amount_usdc
                }
                return result
            
            elif paid_response.status_code == 402:
                logger.warning(
                    "[x402-client] Payment rejected on attempt %d: %s",
                    attempt + 1, paid_response.json().get("detail", "unknown")
                )
                if attempt < max_retries - 1:
                    payment_header = _sign_payment(payment_requirements)
                    await asyncio.sleep(0.5)
            else:
                paid_response.raise_for_status()
        
        raise ValueError(
            f"Payment rejected after {max_retries} attempts. "
            f"Bundle may be unavailable or payment amount insufficient."
        )