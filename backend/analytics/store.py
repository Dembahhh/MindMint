"""
analytics/store.py

Queries MongoDB to compute dashboard and leaderboard analytics.
All functions are read-only — they aggregate existing data from
royalty_payments and memory_bundles collections.
"""

import logging
from collections import defaultdict
from typing import Optional

from backend.memory.bundle import MemoryBundle
from backend.payments.royalty import RoyaltyPayment
from backend.analytics.models import (
    PublisherDashboard, BundleStats, LeaderboardEntry, MarketplaceListing
)
from backend.utils.cache import cached

logger = logging.getLogger(__name__)


@cached("publisher_dashboard", ttl=30.0)
async def get_publisher_dashboard(wallet: str) -> Optional[PublisherDashboard]:
    """
    Builds a full analytics dashboard for a publisher wallet.

    Aggregates all bundles owned by this wallet and all royalty payments
    received. Groups payments by bundle in memory to avoid N+1 queries.

    Returns None if the wallet has no bundles.
    """
    bundles = await MemoryBundle.find(
        MemoryBundle.publisher_wallet == wallet
    ).to_list()

    if not bundles:
        return None

    payments = await RoyaltyPayment.find(
        RoyaltyPayment.publisher_wallet == wallet
    ).sort("-timestamp").to_list()

    payments_by_bundle: dict[str, list] = defaultdict(list)
    for p in payments:
        payments_by_bundle[p.bundle_id].append(p)

    total_earned = sum(float(p.publisher_share_usdc) for p in payments)
    total_purchases = sum(b.purchase_count for b in bundles)
    avg_quality = sum(b.avg_quality_score for b in bundles) / len(bundles)

    bundle_stats = []
    for bundle in bundles:
        bundle_payments = payments_by_bundle[bundle.bundle_id]
        bundle_earned = sum(float(p.publisher_share_usdc) for p in bundle_payments)
        bundle_stats.append(BundleStats(
            bundle_id=bundle.bundle_id,
            title=bundle.title,
            purchase_count=bundle.purchase_count,
            avg_quality_score=bundle.avg_quality_score,
            total_earned_usdc=bundle_earned,
            memory_count=len(bundle.memories)
        ))

    bundle_stats.sort(key=lambda x: x.total_earned_usdc, reverse=True)

    recent = [
        {
            "bundle_id": p.bundle_id[:20],
            "consumer": p.consumer_wallet[:16],
            "gross_usdc": p.gross_amount_usdc,
            "publisher_earned": p.publisher_share_usdc,
            "timestamp": p.timestamp.isoformat()
        }
        for p in payments[:10]
    ]

    return PublisherDashboard(
        publisher_wallet=wallet,
        bundle_count=len(bundles),
        total_purchase_count=total_purchases,
        total_earned_usdc=round(total_earned, 6),
        avg_quality_score=round(avg_quality, 3),
        top_bundles=bundle_stats[:5],
        recent_payments=recent
    )


@cached("leaderboard", ttl=60.0)
async def get_leaderboard(limit: int = 10) -> list[LeaderboardEntry]:
    """
    Returns top publishers ranked by total earnings.

    Loads all payments and all bundles in two queries, then groups
    in memory to avoid one query per publisher wallet.
    """
    all_payments = await RoyaltyPayment.find_all().to_list()
    all_bundles = await MemoryBundle.find_all().to_list()

    bundles_by_wallet: dict[str, list] = defaultdict(list)
    for b in all_bundles:
        bundles_by_wallet[b.publisher_wallet].append(b)

    wallet_stats: dict[str, dict] = {}
    for p in all_payments:
        w = p.publisher_wallet
        if w not in wallet_stats:
            wallet_stats[w] = {"earned": 0.0, "purchases": 0}
        wallet_stats[w]["earned"] += float(p.publisher_share_usdc)
        wallet_stats[w]["purchases"] += 1

    entries = []
    for rank, (wallet, stats) in enumerate(
        sorted(wallet_stats.items(), key=lambda x: x[1]["earned"], reverse=True)[:limit],
        start=1
    ):
        bundles = bundles_by_wallet.get(wallet, [])
        avg_quality = (
            sum(b.avg_quality_score for b in bundles) / len(bundles)
            if bundles else 0.0
        )
        entries.append(LeaderboardEntry(
            rank=rank,
            publisher_wallet=wallet,
            bundle_count=len(bundles),
            total_purchase_count=stats["purchases"],
            total_earned_usdc=round(stats["earned"], 6),
            avg_quality_score=round(avg_quality, 3)
        ))

    return entries


@cached("marketplace", ttl=30.0)
async def get_marketplace_listings(
    sort: str = "newest",
    limit: int = 20,
    offset: int = 0,
    min_quality: float = 0.0
) -> list[MarketplaceListing]:
    """
    Returns paginated marketplace listings.

    sort options:
      "newest"     — most recently created first
      "top_rated"  — highest avg_quality_score first
      "popular"    — most purchased first
      "cheapest"   — lowest price first

    min_quality: filter out bundles below this quality threshold.
    """
    query = MemoryBundle.find(
        MemoryBundle.is_active == True,
        MemoryBundle.avg_quality_score >= min_quality
    )

    if sort == "top_rated":
        query = query.sort("-avg_quality_score")
    elif sort == "popular":
        query = query.sort("-purchase_count")
    elif sort == "cheapest":
        query = query.sort("+price_usdc")
    else:
        query = query.sort("-id")

    bundles = await query.skip(offset).limit(limit).to_list()

    return [
        MarketplaceListing(
            bundle_id=b.bundle_id,
            title=b.title,
            description=b.description,
            publisher_wallet=b.publisher_wallet,
            price_usdc=float(b.price_usdc or 0.002),
            memory_count=len(b.memories),
            avg_quality_score=b.avg_quality_score,
            purchase_count=b.purchase_count,
            tags=b.tags[:5],
            is_active=b.is_active
        )
        for b in bundles
    ]