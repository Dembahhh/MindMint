"""
payments/models.py

MongoDB document model for payment records.
Every x402 payment that passes verification gets a record here.
"""

from beanie import Document
from pydantic import Field
from datetime import datetime, timezone
from pymongo import ASCENDING
from pymongo.operations import IndexModel

class PaymentRecord(Document):
    """
    Represents a single verified x402 micropayment.
    
    Fields:
      bundle_id     - Which memory bundle was purchased
      tx_hash       - On-chain transaction hash (or 'local-verified-...' for dev)
      payer         - Wallet address of the buyer (Consumer agent)
      payee         - Wallet address of the seller (Publisher agent)
      amount_microunits - Amount paid in microUSDC  (1 USDC = 1,000,000 microUSDC)
      verified_at   - When payment was verified by middleware
      created_at    - When record was written to the database
      local_only    - True if verified locally (not by Kite facilitator)
    """
    bundle_id: str
    tx_hash: str
    payer: str
    payee: str
    amount_microunits: int
    verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    local_only: bool = False
    
    class Settings:
        name = "payment_records"
        indexes = [
            IndexModel([("tx_hash", ASCENDING)], unique=True),
            IndexModel([("bundle_id", ASCENDING)]),
            IndexModel([("payer", ASCENDING)]),
        ]