"""
bundle.py

MongoDB document models for MemoryBundle and individual Memory items.

A MemoryBundle is the unit of sale in the marketplace.
It contains 1–50 individual Memory objects.

Storage split:
  MongoDB  → stores the full document (text, metadata, embeddings)
  ChromaDB → stores only the embedding vectors + bundle_id for fast similarity search

When a consumer searches for memories, ChromaDB finds candidate bundle IDs.
The full content is then fetched from MongoDB by bundle_id.
"""

from beanie import Document
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid
from decimal import Decimal

from pymongo import ASCENDING, DESCENDING
from pymongo.operations import IndexModel

from backend.config import settings

def _to_microunits(usdc: float) -> int:
    return int(Decimal(str(usdc)) * 1_000_000)

class Memory(BaseModel):
    """
    A single agent memory / interaction record.
    
    This is NOT a standalone MongoDB document — it lives inside MemoryBundle.
    """
    memory_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str                         
    embedding: list[float] = Field(default_factory=list)      
    quality_score: float = 0.0        
    tags: list[str] = Field(default_factory=list)            
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    source: str = "publisher_agent"   



class MemoryBundle(Document):
    """
    A collection of related memories, sold as a unit.
    
    Published by the Publisher Agent.
    Purchased by the Consumer Agent via x402 micropayment.
    """
    bundle_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str
    publisher_wallet: str             
    price_microunits: int = Field(default_factory=lambda: _to_microunits(settings.marketplace.memory_base_price_usdc))
    
    memories: list[Memory] = Field(default_factory=list)
    
    avg_quality_score: float = 0.0
    
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    purchase_count: int = 0          
    is_active: bool = True            
    
    tags: list[str] = Field(default_factory=list)
    

    class Settings:
        name = "memory_bundles"
        indexes = [
            IndexModel([("bundle_id", ASCENDING)], unique=True),
            IndexModel([("publisher_wallet", ASCENDING)]),
            IndexModel([("is_active", ASCENDING), ("avg_quality_score", DESCENDING)]),
            IndexModel([("is_active", ASCENDING), ("purchase_count", DESCENDING)]),
            IndexModel([("is_active", ASCENDING), ("created_at", DESCENDING)]),
        ]
    
    def compute_avg_quality(self) -> None:
        """Recompute avg_quality_score from all memories. Call before saving."""
        if self.memories:
            self.avg_quality_score = sum(
                m.quality_score for m in self.memories
            ) / len(self.memories)
        
    def aggregate_tags(self) -> None:
        """Collect unique tags from all memories into bundle-level tags."""
        all_tags = set()
        for memory in self.memories:
            all_tags.update(memory.tags)
        self.tags = sorted(list(all_tags))