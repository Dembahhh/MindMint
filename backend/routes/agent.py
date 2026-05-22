"""
routes/agent.py

Agent identity and status routes.
/agent/publisher  - Publisher agent info
/agent/consumer   - Consumer agent info
/agent/seed-demo  - Seeds the marketplace with demo bundles (one-time setup)
"""
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.security import APIKeyHeader

from backend.config import settings
from backend.agents.publisher_agent import PublisherAgent

router = APIRouter()

_api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)


async def _require_api_key(key: str = Depends(_api_key_header)) -> None:
    """Guard — same pattern as consumer.py."""
    if settings.environment == "development":
        return
    if not settings.demo_api_key:
        raise HTTPException(status_code=500, detail="API key not configured on server")
    if key != settings.demo_api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")


@router.get("/publisher")
async def publisher_info() -> dict[str, Any]:
    """Returns public identity information for the publisher agent."""
    return {
        "name": "MindMint Publisher",
        "wallet": settings.publisher.address,
        "role": "publisher"
    }


@router.get("/consumer")
async def consumer_info() -> dict[str, Any]:
    """Returns public identity information for the consumer agent."""
    return {
        "name": "MindMint Consumer",
        "wallet": settings.consumer.address,
        "role": "consumer"
    }


@router.post("/seed-demo", dependencies=[Depends(_require_api_key)])
async def seed_demo_marketplace(request: Request) -> dict[str, Any]:
    """
    Seeds the marketplace with demo memory bundles.
    Runs the PublisherAgent demo session (3 domains, ~6 memories each).
    Safe to call multiple times — will just add more bundles.
    Requires X-API-KEY header in production.
    """
    memory_store = request.app.state.memory_store

    agent = PublisherAgent(store=memory_store)

    try:
        bundles = await agent.run_demo_session(num_domains=3)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Demo seeding failed: {e}")

    return {
        "status": "ok",
        "bundles_published": len(bundles),
        "bundles": [
            {
                "bundle_id": b.bundle_id,
                "title": b.title,
                "memory_count": len(b.memories),
                "avg_quality_score": b.avg_quality_score,
            }
            for b in bundles
        ]
    }