"""
payments/royalty.py

Royalty distribution engine.

On every successful x402 purchase, this module:
  1. Calculates the 80/20 split from the gross payment
  2. Transfers the publisher's share to their wallet
  3. Transfers the platform share to the platform wallet
  4. Records both transactions in MongoDB
  5. Returns the royalty record for audit/display

In testnet mode (kite.is_testnet=true), the on-chain transfers
are simulated — we record them as fake TX hashes.
For hackathon demo this is sufficient. In production, you would
call the USDC contract's transfer() method directly.
"""

import logging
import secrets
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, timezone

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, DESCENDING
from pymongo.operations import IndexModel

from backend.config import settings

logger = logging.getLogger(__name__)


class RoyaltyPayment(Document):
    """
    Immutable record of a single royalty distribution event.
    One RoyaltyPayment is created per successful bundle purchase.
    """
    bundle_id: str
    publisher_wallet: str
    consumer_wallet: str
    gross_amount_usdc: str
    publisher_share_usdc: str
    platform_share_usdc: str
    publisher_tx_hash: str
    platform_tx_hash: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    class Settings:
        name = "royalty_payments"
        indexes = [
            IndexModel([("publisher_wallet", ASCENDING), ("timestamp", DESCENDING)]),
            IndexModel([("consumer_wallet", ASCENDING), ("timestamp", DESCENDING)]),
            IndexModel([("bundle_id", ASCENDING)]),
        ]


class RoyaltyEngine:
    """
    Handles revenue distribution for memory bundle purchases.

    Usage:
        engine = RoyaltyEngine()
        record = await engine.distribute(
            bundle_id="abc-123",
            publisher_wallet="0xPublisher...",
            consumer_wallet="0xConsumer...",
            gross_amount_usdc=0.002
        )
    """

    PUBLISHER_SHARE = Decimal(str(settings.marketplace.publisher_royalty_percent))
    PLATFORM_SHARE = Decimal("1") - PUBLISHER_SHARE

    def __init__(self):
        self.platform_wallet = settings.publisher.address
        self.testnet = settings.kite.is_testnet

    def _calculate_split(self, gross: float) -> tuple[Decimal, Decimal]:
        """
        Calculates publisher and platform shares using Decimal arithmetic.

        Publisher always gets the floor value; platform gets the remainder.
        This ensures gross = publisher + platform exactly.

        Example:
            gross=0.002, split 80/20
            publisher = floor(0.002 * 0.80, 6 decimals) = 0.001600
            platform  = 0.002 - 0.001600               = 0.000400
        """
        gross_d = Decimal(str(gross))
        publisher = (gross_d * self.PUBLISHER_SHARE).quantize(
            Decimal("0.000001"), rounding=ROUND_DOWN
        )
        platform = gross_d - publisher
        return publisher, platform

    async def _transfer(self, to_wallet: str, amount: Decimal, memo: str) -> str:
        """
        Executes a USDC transfer to a wallet.

        In testnet mode: generates a fake TX hash for demo purposes.
        In production: would call USDC contract transfer() via web3.py.

        Returns TX hash string.
        """
        if self.testnet:
            fake_hash = "0x" + secrets.token_hex(32)
            logger.info(
                "[royalty] TESTNET transfer: $%s USDC -> %s (%s) | TX: %s",
                amount, to_wallet[:12], memo, fake_hash[:20]
            )
            return fake_hash

        raise NotImplementedError("Production transfers not implemented")

    async def distribute(
        self,
        bundle_id: str,
        publisher_wallet: str,
        consumer_wallet: str,
        gross_amount_usdc: float
    ) -> RoyaltyPayment:
        """
        Distributes revenue from a bundle purchase.

        Steps:
          1. Calculate 80/20 split
          2. Transfer publisher share on-chain (or simulate)
          3. Transfer platform share on-chain (or simulate)
          4. Save RoyaltyPayment record to MongoDB
          5. Return the record

        Called by the purchase route after successful payment verification.
        """
        publisher_share, platform_share = self._calculate_split(gross_amount_usdc)

        logger.info(
            "[royalty] Distributing: bundle=%s, gross=$%s, publisher=$%s, platform=$%s",
            bundle_id[:20], gross_amount_usdc, publisher_share, platform_share
        )

        publisher_tx = await self._transfer(
            publisher_wallet, publisher_share, "publisher-royalty"
        )
        platform_tx = await self._transfer(
            self.platform_wallet, platform_share, "platform-fee"
        )

        record = RoyaltyPayment(
            bundle_id=bundle_id,
            publisher_wallet=publisher_wallet,
            consumer_wallet=consumer_wallet,
            gross_amount_usdc=str(gross_amount_usdc),
            publisher_share_usdc=str(publisher_share),
            platform_share_usdc=str(platform_share),
            publisher_tx_hash=publisher_tx,
            platform_tx_hash=platform_tx
        )
        await record.insert()

        logger.info(
            "[royalty] Distribution complete. Publisher TX: %s | Platform TX: %s",
            publisher_tx[:20], platform_tx[:20]
        )

        return record


royalty_engine = RoyaltyEngine()