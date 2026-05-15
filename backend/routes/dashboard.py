"""
routes/dashboard.py

Analytics and marketplace endpoints.

Publisher analytics:
  GET /dashboard/publisher/{wallet}   — full stats for a publisher
  GET /dashboard/leaderboard          — top publishers by earnings
  GET /dashboard/platform             — platform-level aggregate stats

Marketplace:
  GET /dashboard/marketplace          — paginated bundle listings
  POST /dashboard/rate/{bundle_id}    — submit a quality rating after purchase
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional
import logging

from backend.analytics.store import (
    get_publisher_dashboard,
    get_leaderboard,
    get_marketplace_listings
)
from backend.memory.bundle import MemoryBundle
from backend.payments.royalty import RoyaltyPayment
from backend.utils.sanitize import sanitize_text

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/publisher/{wallet}")
async def publisher_dashboard(wallet: str):
    """
    Full analytics for a publisher wallet.

    Returns:
      - bundle_count: how many bundles published
      - total_purchase_count: total times any bundle was bought
      - total_earned_usdc: lifetime publisher earnings (80% share)
      - avg_quality_score: average across all bundles
      - top_bundles: top 5 by earnings
      - recent_payments: last 10 royalty events
    """
    dashboard = await get_publisher_dashboard(wallet)
    if not dashboard:
        raise HTTPException(
            status_code=404,
            detail=f"No bundles found for wallet {wallet[:16]}..."
        )
    return dashboard


@router.get("/leaderboard")
async def leaderboard(
    limit: int = Query(default=10, ge=1, le=50)
):
    """Top publishers ranked by total earnings."""
    entries = await get_leaderboard(limit=limit)
    return {
        "leaderboard": [e.model_dump() for e in entries],
        "total_publishers": len(entries)
    }


@router.get("/platform")
async def platform_stats():
    """Platform-level aggregate statistics."""
    total_bundles = await MemoryBundle.find(
        MemoryBundle.is_active == True
    ).count()

    all_payments = await RoyaltyPayment.find_all().to_list()
    total_payments = len(all_payments)
    total_volume = sum(float(p.gross_amount_usdc) for p in all_payments)
    platform_earned = sum(float(p.platform_share_usdc) for p in all_payments)
    unique_publishers = len(set(p.publisher_wallet for p in all_payments))

    return {
        "total_bundles": total_bundles,
        "total_purchases": total_payments,
        "total_volume_usdc": round(total_volume, 6),
        "platform_earned_usdc": round(platform_earned, 6),
        "unique_publishers": unique_publishers,
        "royalty_split": "80% publisher / 20% platform"
    }


@router.get("/marketplace")
async def marketplace_listing(
    sort: str = Query(default="newest", pattern="^(newest|top_rated|popular|cheapest)$"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    min_quality: float = Query(default=0.0, ge=0.0, le=1.0)
):
    """
    Paginated marketplace listing.

    Query params:
      sort        — newest | top_rated | popular | cheapest
      limit       — results per page (max 100)
      offset      — pagination offset
      min_quality — filter below this quality score
    """
    listings = await get_marketplace_listings(
        sort=sort,
        limit=limit,
        offset=offset,
        min_quality=min_quality
    )
    return {
        "listings": [l.model_dump() for l in listings],
        "count": len(listings),
        "sort": sort,
        "offset": offset
    }


class RateRequest(BaseModel):
    rating: float = Field(..., ge=0.0, le=5.0)
    consumer_wallet: str
    comment: Optional[str] = None


@router.post("/rate/{bundle_id}")
async def rate_bundle(bundle_id: str, req: RateRequest):
    """
    Submits a quality rating for a purchased bundle.

    Rating scale: 0.0 (terrible) to 5.0 (excellent).
    Normalized to 0-1 range before updating bundle avg_rating.
    """
    bundle = await MemoryBundle.find_one(
        MemoryBundle.bundle_id == bundle_id
    )
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")

    if req.comment:
        req.comment = sanitize_text(req.comment, max_length=500)

    normalized = req.rating / 5.0

    current_avg = getattr(bundle, "avg_rating", None)
    current_count = getattr(bundle, "rating_count", 0)

    if current_avg is None:
        new_avg = normalized
        new_count = 1
    else:
        new_avg = (current_avg * current_count + normalized) / (current_count + 1)
        new_count = current_count + 1

    await bundle.set({
        "avg_rating": round(new_avg, 3),
        "rating_count": new_count
    })

    logger.info(
        "[rating] Bundle %s rated %.1f/5.0 by %s. New avg: %.3f (%d ratings)",
        bundle_id[:20], req.rating, req.consumer_wallet[:16], new_avg, new_count
    )

    return {
        "bundle_id": bundle_id,
        "your_rating": req.rating,
        "new_avg_rating": round(new_avg * 5.0, 2),
        "total_ratings": new_count
    }