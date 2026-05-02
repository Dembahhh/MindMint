"""
setup_kite_wallet.py

Generates two EVM-compatible wallet keypairs for:
  - Publisher Agent  (will earn USDC from memory sales)
  - Consumer Agent   (will spend USDC to purchase memories)

Output: Paste the printed values directly into your .env file.
Never commit .env to git.
"""

from eth_account import Account
from typing import TypedDict
import secrets
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WalletInfo(TypedDict):
    name: str
    address: str
    private_key: str
    
def generate_wallet(name: str) -> WalletInfo:
    """Generate a new EVM wallet keypair.

    Uses cryptographically secure randomness via the secrets
    module to produce a private key safe for production use.

    Args:
        name: Human-readable label for the wallet (e.g. "Publisher Agent")

    Returns:
        WalletInfo dict containing name, checksummed address,
        and hex-encoded private key prefixed with 0x.

    Raises:
        ValueError: If key generation or account derivation fails.
    """
    PRIVATE_KEY_BYTES = 32  # 256 bits for EVM private key
    try:
        private_key = "0x" + secrets.token_hex(PRIVATE_KEY_BYTES)
        account= Account.from_key(private_key)
    except  ValueError as e:
        raise ValueError(f"Failed to generate wallet for {name}: {e}") from e
    return {
        "name": name, "address": account.address,"private_key": private_key}

if __name__ == "__main__":
    logger.info("\n" + "="*60)
    logger.info("AGENTMEMORY — Wallet Generation")
    logger.info("="*60)
    logger.info(" SAVE THESE VALUES IN YOUR .env FILE")
    logger.info("  NEVER SHARE OR COMMIT PRIVATE KEYS")
    logger.info("="*60 + "\n")
    
    publisher = generate_wallet("Publisher Agent")
    consumer = generate_wallet("Consumer Agent")
    
    logger.info("# Publisher Agent Wallet")
    logger.info(f"PUBLISHER__ADDRESS={publisher['address']}")
    logger.info(f"PUBLISHER__PRIVATE_KEY={publisher['private_key']}")
    logger.info("")
    logger.info("# Consumer Agent Wallet")
    logger.info(f"CONSUMER__ADDRESS={consumer['address']}")
    logger.info(f"CONSUMER__PRIVATE_KEY={consumer['private_key']}")
    logger.info("")
    logger.info("="*60)
    logger.info("Next steps:")
    logger.info("1. Copy the above into your .env file")
    logger.info("2. Go to testnet.gokite.ai")
    logger.info("3. Connect each wallet and claim test USDC from the faucet")
    logger.info("="*60 + "\n")