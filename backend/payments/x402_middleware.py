"""
x402_middleware.py

FastAPI/Starlette middleware that implements the x402 payment protocol.

How x402 works (simplified):
  1. Client makes a request to a paid endpoint
  2. Server responds with HTTP 402 and a JSON body describing:
     - How much to pay (in USDC, as integer microunits)
     - Who to pay (the publisher's wallet address)
     - Which network (kite-testnet)
     - Expiry time for the payment authorisation
  3. Client signs a USDC transferWithAuthorization (EIP-3009)
     and re-sends the request with the signed payload in X-PAYMENT header
  4. Server verifies the payment with the Kite facilitator
  5. If valid: process the request normally
  6. If invalid: return 402 again with error detail

This middleware does NOT intercept every request.
Only routes prefixed with PAID_ROUTE_PREFIXES trigger the gate.
All other routes pass through untouched.
"""

import base64
import json
import logging
import time
from decimal import Decimal
from typing import Any

import httpx
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.config import settings

logger = logging.getLogger(__name__)

PAID_ROUTE_PREFIXES: tuple[str, ...] = ("/memory/purchase",)


def _to_microunits(usdc_amount: float) -> int:
    """Convert USDC float to integer microunits. Uses Decimal to avoid float truncation."""
    return int(Decimal(str(usdc_amount)) * 1_000_000)


class X402PaymentMiddleware(BaseHTTPMiddleware):
    """
    Intercepts requests to paid routes.
    Checks for X-PAYMENT header and verifies payment.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        if not any(path.startswith(prefix) for prefix in PAID_ROUTE_PREFIXES):
            return await call_next(request)

        logger.info("[x402] Payment gate triggered for: %s", path)

        payment_header = request.headers.get("X-PAYMENT")

        if not payment_header:
            logger.info("[x402] No payment header. Returning 402.")
            return self._build_402_response(request)

        verification = await self._verify_payment(payment_header, request)

        if not verification["valid"]:
            logger.warning("[x402] Payment invalid: %s", verification.get("error"))
            return JSONResponse(
                status_code=402,
                content={
                    "error": "payment_invalid",
                    "detail": verification.get("error", "Payment could not be verified"),
                    "x402Version": 1
                }
            )

        request.state.payment = {
            "tx_hash": verification.get("txHash"),
            "amount_microunits": _to_microunits(verification.get("amountUsdc", 0)),
            "payer": verification.get("payer"),
            "verified_at": time.time()
        }
        request.state.consumer_wallet = verification.get("payer", "unknown")

        logger.info(
            "[x402] Payment verified. TX: %s, Amount: $%s USDC",
            verification.get("txHash", "")[:20],
            verification.get("amountUsdc")
        )

        response = await call_next(request)

        if verification.get("txHash"):
            response.headers["X-PAYMENT-RESPONSE"] = verification["txHash"]

        return response

    def _build_402_response(self, request: Request) -> JSONResponse:
        """
        Builds the standard x402 payment-required response.

        The client reads this to know how much to pay, who to pay,
        and in what format to sign the payment.
        """
        price_usdc = settings.marketplace.memory_base_price_usdc
        price_microunits = _to_microunits(price_usdc)

        return JSONResponse(
            status_code=402,
            content={
                "x402Version": 1,
                "accepts": [
                    {
                        "scheme": "exact",
                        "network": "kite-testnet",
                        "maxAmountRequired": str(price_microunits),
                        "resource": str(request.url),
                        "description": "MindMint bundle access",
                        "mimeType": "application/json",
                        "payTo": settings.publisher.address,
                        "maxTimeoutSeconds": 300,
                        "asset": settings.kite.usdc_contract_address,
                        "extra": {
                            "name": "USD Coin",
                            "version": "2"
                        }
                    }
                ],
                "error": "X-PAYMENT header required"
            },
            headers={
                "Access-Control-Expose-Headers": "X-PAYMENT-RESPONSE"
            }
        )

    async def _verify_payment(
        self,
        payment_header: str,
        request: Request
    ) -> dict[str, Any]:
        """
        Verifies a payment by calling the Kite x402 facilitator.

        The facilitator is a Kite-operated service that:
        1. Decodes the signed payment authorisation
        2. Checks the signature is valid
        3. Submits the USDC transferWithAuthorization on-chain
        4. Returns the transaction hash once mined

        If the facilitator is unavailable, falls back to local
        signature verification as a development bypass.
        """
        try:
            decoded = base64.b64decode(payment_header.encode()).decode()
            payment_payload = json.loads(decoded)
        except Exception as e:
            return {"valid": False, "error": f"Could not decode payment header: {e}"}

        if payment_payload.get("x402Version") != 1:
            return {"valid": False, "error": "Unsupported x402 version"}

        if payment_payload.get("network") != "kite-testnet":
            return {"valid": False, "error": "Wrong network"}

        logger.info("[x402] Verifying payment with Kite facilitator...")

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                verify_response = await client.post(
                    f"{settings.kite.facilitator_url}/verify",
                    json={
                        "x402Version": 1,
                        "paymentPayload": payment_payload,
                        "paymentRequirements": {
                            "scheme": "exact",
                            "network": "kite-testnet",
                            "maxAmountRequired": str(_to_microunits(settings.marketplace.memory_base_price_usdc)),
                            "resource": str(request.url),
                            "payTo": settings.publisher.address,
                            "asset": settings.kite.usdc_contract_address
                        }
                    }
                )

                if verify_response.status_code == 200:
                    result = verify_response.json()
                    return {
                        "valid": result.get("isValid", False),
                        "txHash": result.get("txHash"),
                        "amountUsdc": settings.marketplace.memory_base_price_usdc,
                        "payer": payment_payload.get("payload", {}).get("authorization", {}).get("from")
                    }
                else:
                    logger.warning(
                        "[x402] Facilitator returned %s: %s",
                        verify_response.status_code,
                        verify_response.text[:200]
                    )

        except httpx.TimeoutException:
            logger.warning("[x402] Facilitator timeout. Using local verification.")
        except Exception as e:
            logger.warning("[x402] Facilitator error: %s. Using local verification.", e)

        return await self._local_verify_fallback(payment_payload)

    async def _local_verify_fallback(self, payment_payload: dict) -> dict:
        """
        Development bypass — used when Kite facilitator is unreachable.

        WARNING: Does NOT cryptographically verify the signature.
        Checks only that the payload is structurally valid and not expired.
        NEVER runs in production (settings.api.debug must be True).
        """
        if not settings.api.debug:
            return {
                "valid": False,
                "error": "Facilitator unavailable and local bypass is disabled in production"
            }

        try:
            auth = payment_payload.get("payload", {}).get("authorization", {})
            signature = payment_payload.get("payload", {}).get("signature", "")

            if not auth or not signature:
                return {"valid": False, "error": "Missing authorization or signature"}

            valid_before = int(auth.get("validBefore", 0))
            if valid_before < time.time():
                return {"valid": False, "error": "Payment authorisation has expired"}

            amount = int(auth.get("value", 0))
            required = _to_microunits(settings.marketplace.memory_base_price_usdc)
            if amount < required:
                return {
                    "valid": False,
                    "error": f"Payment amount {amount} is less than required {required}"
                }

            logger.warning(
                "[x402] LOCAL BYPASS active (facilitator unavailable). "
                "Signature NOT cryptographically verified. Amount: %s microUSDC", amount
            )

            return {
                "valid": True,
                "txHash": "local-verified-" + signature[:16],
                "amountUsdc": amount / 1_000_000,
                "payer": auth.get("from"),
                "localVerificationOnly": True
            }

        except Exception as e:
            return {"valid": False, "error": f"Local verification failed: {e}"}