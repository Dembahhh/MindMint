"""
register_passports.py

Registers both agent wallets as Kite Agent Passports.
The Passport gives each agent a cryptographic identity on Kite chain
and enables them to make x402 payments.

Required env vars (double-underscore namespace):
  PUBLISHER__ADDRESS
  PUBLISHER__PRIVATE_KEY
  CONSUMER__ADDRESS
  CONSUMER__PRIVATE_KEY
  KITE__API_BASE_URL  (optional — defaults to https://api.testnet.gokite.ai)
"""

import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass
import httpx
from dotenv import load_dotenv
from eth_account import Account
from eth_account.messages import encode_defunct
import rootutils
from web3 import Web3

root = rootutils.setup_root(search_from=__file__, indicator=".env", pythonpath=True, dotenv=True)
_ENV_FILE = root / ".env"
load_dotenv(_ENV_FILE)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

KITE_API_BASE = os.getenv("KITE__API_BASE_URL", "https://api.testnet.gokite.ai")
DEFAULT_DAILY_LIMIT_USDC: float = 10.0
MAX_PER_TRANSACTION_USDC: float = 1.0
KITE_API_TIMEOUT_SECONDS: float = 30.0

@dataclass(frozen=True)
class WalletCredentials:
    """Holds wallet address and private key for an agent.

    Address is validated as a checksummed EVM address at construction time.
    Private key is redacted from repr so it never appears in logs or tracebacks.
    """

    address: str
    private_key: str

    def __post_init__(self) -> None:
        if not Web3.is_checksum_address(self.address):
            raise ValueError(f"Invalid checksum address: {self.address!r}")

    def __repr__(self) -> str:
        return (
            f"WalletCredentials(address={self.address!r}, "
            f"private_key=***REDACTED***)"
        )


def _require_env(key: str) -> str:
    """Return the value of a required environment variable.

    Args:
        key: Environment variable name.

    Returns:
        Non-empty string value of the variable.

    Raises:
        SystemExit: With a descriptive message if the variable is missing.
    """
    value = os.getenv(key)
    if not value:
        logger.error("Required env var '%s' is not set. Check %s", key, _ENV_FILE)
        sys.exit(1)
    return value


async def register_passport(
    credentials: WalletCredentials,
    agent_name: str,
    agent_role: str,
    daily_spend_limit_usdc: float = DEFAULT_DAILY_LIMIT_USDC,
) -> dict:
    """Register a wallet as a Kite Agent Passport.

    Builds a registration payload, signs it with the wallet's private key
    to prove ownership, then POSTs it to the Kite passport API.

    Args:
        credentials:           Wallet address and private key for the agent.
        agent_name:            Human-readable name (e.g. "MindMint Publisher").
        agent_role:            Role identifier (e.g. "publisher" or "consumer").
        daily_spend_limit_usdc: Maximum USDC the agent may spend per day.

    Returns:
        API response dict containing ``passportId`` on success, or
        ``{"passportId": None, "manual_registration_required": True}``
        if the API is unreachable or returns an error.
    """
    payload = {
        "walletAddress": credentials.address,
        "agentName": agent_name,
        "agentRole": agent_role,
        "spendingPolicy": {
            "dailyLimitUsdc": daily_spend_limit_usdc,
            "maxPerTransactionUsdc": MAX_PER_TRANSACTION_USDC,
            "allowedNetworks": ["kite-testnet"],
        },
        "metadata": {
            "project": "MindMint",
            "description": f"MindMint {agent_role} agent",
            "version": "0.1.0",
        },
    }

    message = encode_defunct(text=json.dumps(payload, sort_keys=True))
    account = Account.from_key(credentials.private_key)
    signed = account.sign_message(message)

    try:
        async with httpx.AsyncClient(timeout=KITE_API_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{KITE_API_BASE}/v1/passports/register",
                json={"payload": payload, "signature": signed.signature.hex()},
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(
                    "%s passport registered. ID: %s | Wallet: %s | Daily limit: $%.2f USDC",
                    agent_name,
                    result.get("passportId"),
                    credentials.address,
                    daily_spend_limit_usdc,
                )
                return result

            logger.error(
                "Failed to register %s. Status %d: %s",
                agent_name,
                response.status_code,
                response.text,
            )
            logger.info(
                "Register manually at: testnet.gokite.ai/passport/register"
            )
            return {"passportId": None, "manual_registration_required": True}

    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        logger.error(
            "Network error registering %s: %s. "
            "Register manually at: agentpassport.ai",
            agent_name,
            exc,
        )
        return {"passportId": None, "manual_registration_required": True}


async def main() -> None:
    """Register both Publisher and Consumer agent passports."""
    logger.info("=" * 60)
    logger.info("Registering Kite Agent Passports")
    logger.info("=" * 60)

    publisher_result = await register_passport(
        credentials=WalletCredentials(
            address=_require_env("PUBLISHER__ADDRESS"),
            private_key=_require_env("PUBLISHER__PRIVATE_KEY"),
        ),
        agent_name="MindMint Publisher",
        agent_role="publisher",
    )

    consumer_result = await register_passport(
        credentials=WalletCredentials(
            address=_require_env("CONSUMER__ADDRESS"),
            private_key=_require_env("CONSUMER__PRIVATE_KEY"),
        ),
        agent_name="MindMint Consumer",
        agent_role="consumer",
    )

    logger.info("=" * 60)
    logger.info("Add these to your .env:")
    if publisher_result.get("passportId"):
        logger.info("PUBLISHER__PASSPORT_ID=%s", publisher_result["passportId"])
    if consumer_result.get("passportId"):
        logger.info("CONSUMER__PASSPORT_ID=%s", consumer_result["passportId"])
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())