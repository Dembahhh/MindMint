"""
routes/agent.py

Agent identity and status routes.
/agent/publisher  - Publisher agent info
/agent/consumer   - Consumer agent info
"""

from fastapi import APIRouter
from typing import Any

from backend.config import settings

router = APIRouter()


@router.get("/publisher")
async def publisher_info() -> dict[str, Any]:
    return {
        "name": "AgentMemory Publisher",
        "wallet": settings.publisher.address,
        "passport_id": settings.publisher.passport_id,
        "role": "publisher"
    }


@router.get("/consumer")
async def consumer_info() -> dict[str, Any]:
    return {
        "name": "AgentMemory Consumer",
        "wallet": settings.consumer.address,
        "passport_id": settings.consumer.passport_id,
        "role": "consumer"
    }