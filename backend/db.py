"""
db.py

MongoDB connection and Beanie ODM initialisation.
Beanie is an async ODM (Object Document Mapper) built on Motor.
It gives us Pydantic models that map directly to MongoDB collections.
"""
from __future__ import annotations
import asyncio
import logging
from typing import Optional
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from backend.config import settings

logger = logging.getLogger(__name__)

_mongo_client: Optional[AsyncIOMotorClient] = None #type: ignore[valid-type]

async def init_db() -> None:
    """Initialise MongoDB connection and Beanie ODM with retry logic."""
    global _mongo_client

    from backend.payments.models import PaymentRecord
    from backend.memory.bundle import MemoryBundle
    from backend.payments.royalty import RoyaltyPayment

    for attempt in range(1, 6):
        try:
            _mongo_client = AsyncIOMotorClient(
                settings.database.mongo_db_url,
                serverSelectionTimeoutMS=3000
            )
            await _mongo_client.admin.command("ping")
            logger.info("MongoDB ping successful on attempt %d", attempt)
            break
        except Exception as e:
            logger.warning(
                "MongoDB not ready (attempt %d/5): %s. Retrying in 2s.", attempt, e
            )
            _mongo_client = None
            await asyncio.sleep(2)
    else:
        raise RuntimeError("MongoDB unavailable after 5 attempts. Aborting startup.")
    try:
        await init_beanie(
            database=_mongo_client[settings.database.mongodb_db_name],
            document_models=[MemoryBundle, PaymentRecord, RoyaltyPayment]
        )
        logger.info("Beanie ODM initialised with %s", settings.database.mongodb_db_name)
    except Exception as e:
        _mongo_client.close()
        _mongo_client = None
        raise RuntimeError(f"Beanie ODM initialisation failed: {e}") from e

async def close_db() -> None:
    """Close MongoDB connection."""
    global _mongo_client
    if _mongo_client:
        try:
            _mongo_client.close()
            logger.info("MongoDB connection closed successfully")
        except Exception as e:
            logger.warning("Error closing MongoDB connection: %s", e)
        finally:
            _mongo_client = None