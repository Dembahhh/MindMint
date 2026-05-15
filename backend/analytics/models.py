"""
analytics/models.py

Pydantic response models for the dashboard API.
These are API output shapes only — not MongoDB documents.
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class BundleStats(BaseModel):
    bundle_id: str
    title: str
    purchase_count: int
    avg_quality_score: float
    total_earned_usdc: float
    avg_rating: Optional[float] = None
    memory_count: int


class PublisherDashboard(BaseModel):
    publisher_wallet: str
    bundle_count: int
    total_purchase_count: int
    total_earned_usdc: float
    avg_quality_score: float
    top_bundles: list[BundleStats]
    recent_payments: list[dict]


class LeaderboardEntry(BaseModel):
    rank: int
    publisher_wallet: str
    bundle_count: int
    total_purchase_count: int
    total_earned_usdc: float
    avg_quality_score: float


class MarketplaceListing(BaseModel):
    bundle_id: str
    title: str
    description: str
    publisher_wallet: str
    price_usdc: float
    memory_count: int
    avg_quality_score: float
    purchase_count: int
    avg_rating: Optional[float] = None
    tags: list[str]
    is_active: bool