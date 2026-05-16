"""
routes/agent.py

Agent identity and status routes.
/agent/publisher  - Publisher agent info
/agent/consumer   - Consumer agent info
"""
from typing import Any

from fastapi import APIRouter

from backend.config import settings

router = APIRouter()


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