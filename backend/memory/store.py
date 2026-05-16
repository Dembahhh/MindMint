"""
memory/store.py

Unified read/write layer for memory bundles.

Always use this module to interact with memory data.
Do NOT query MongoDB or ChromaDB directly from routes or agents.

Write path (Publisher):
  store.save_bundle(bundle) →
    1. Compute quality + embeddings for each memory
    2. Save full document to MongoDB
    3. Upsert vectors to ChromaDB

Read path (Consumer):
  store.search(query) →
    1. Embed the query (RETRIEVAL_QUERY task type)
    2. ChromaDB cosine similarity search → bundle_ids
    3. Fetch full bundles from MongoDB by bundle_ids
    4. Return ranked results

  store.get_bundle(bundle_id) →
    1. Fetch full bundle from MongoDB
    2. Return MemoryBundle object
"""

import logging
from typing import Optional
import asyncio

from backend.config import settings
from backend.memory.bundle import MemoryBundle, Memory, _to_microunits
from backend.memory.embedder import embed_batch, embed_for_search
from backend.quality.scorer import score_batch, QUALITY_THRESHOLD
from backend.utils.limits import CHROMA_DOC_MAX_CHARS


logger = logging.getLogger(__name__)


class MemoryStore:
    """
    Manages all reads and writes to the memory storage system.
    Instantiated once at startup and shared across routes.
    """
    
    def __init__(self, collection) -> None:
        self._collection = collection
        logger.info("MemoryStore initialised with collection: %s",settings.database.chroma_collection_name)
            
    async def save_bundle(
        self,
        title: str,
        description: str,
        publisher_wallet: str,
        raw_memories: list[str],
        price_usdc: Optional[float] = None
    ) -> Optional[MemoryBundle]:
        """
        Full pipeline: score → embed → save to MongoDB + ChromaDB.
        
        Args:
          title            — Bundle display name
          description      — Bundle description for marketplace listing
          publisher_wallet — Publisher's wallet address (receives payments)
          raw_memories     — List of raw interaction text strings
          price_usdc       — Price (defaults to config base price)
        
        Returns:
          MemoryBundle if at least one memory passed quality threshold.
          None if all memories were below threshold (nothing saved).
        """
        if price_usdc is None:
            price_usdc = settings.marketplace.memory_base_price_usdc
        
        logger.info("Saving bundle '%s' with %d raw memories...", title, len(raw_memories))
        
        logger.info("Scoring memories for quality...")
        scores = await score_batch(raw_memories)
        
        passing = [
            (text, result)
            for text, result in zip(raw_memories, scores)
            if result["passes_threshold"]
        ]
        
        if not passing:
            logger.warning(
                "All %d memories failed quality threshold (%.1f). Bundle not saved.",
                len(raw_memories), QUALITY_THRESHOLD
            )
            return None
        
        logger.info("%d/%d memories passed quality threshold", len(passing), len(raw_memories))
        
        logger.info("Generating embeddings...")
        texts = [text for text, _ in passing]
        embeddings = await embed_batch(texts)
        
        memories = []
        for (text, score_result), embedding in zip(passing, embeddings):
            memory = Memory(
                text=text,
                embedding=embedding,
                quality_score=score_result["score"],
                tags=score_result["tags"]
            )
            memories.append(memory)
        
        bundle = MemoryBundle(
            title=title,
            description=description,
            publisher_wallet=publisher_wallet,
            price_microunits=_to_microunits(price_usdc),
            memories=memories
        )
        bundle.compute_avg_quality()
        bundle.aggregate_tags()
        
        try:
            await bundle.insert()
            logger.info("Bundle saved to MongoDB. ID: %s", bundle.bundle_id)
        except Exception as e:
            logger.error("MongoDB insert failed for bundle '%s': %s", title, e)
            raise RuntimeError(f"Failed to persist memory bundle: {e}") from e
        
        chroma_ids = []
        chroma_embeddings = []
        chroma_documents = []
        chroma_metadatas = []
        
        for memory in memories:
            chroma_ids.append(f"{bundle.bundle_id}::{memory.memory_id}")
            chroma_embeddings.append(memory.embedding)
            chroma_documents.append(memory.text[:CHROMA_DOC_MAX_CHARS]) 
            chroma_metadatas.append({
                "bundle_id": bundle.bundle_id,
                "memory_id": memory.memory_id,
                "quality_score": memory.quality_score,
                "publisher_wallet": publisher_wallet,
                "price_microunits": _to_microunits(price_usdc),
                "tags": ",".join(memory.tags)  
            })
        
        await asyncio.to_thread(
            self._collection.upsert,
            ids=chroma_ids,
            embeddings=chroma_embeddings,
            documents=chroma_documents,
            metadatas=chroma_metadatas
        )
        
        logger.info(
            "Bundle '%s' saved. %d memories indexed. Avg quality: %.2f",
            bundle.bundle_id, len(memories), bundle.avg_quality_score
        )
        
        return bundle
    
    
    async def search(
        self,
        query: str,
        top_k: int = 5,
        min_quality: float = 0.0
    ) -> list[dict]:
        """
        Semantic search for memory bundles.
        
        Args:
          query       — Natural language search query
          top_k       — Maximum number of results to return
          min_quality — Minimum quality score filter (0.0 = no filter)
        
        Returns:
          List of dicts with bundle preview info, sorted by similarity.
        """
        logger.info("Searching memories for: '%s'", query[:80])
        
        query_embedding = await embed_for_search(query)
        
        where = None
        if min_quality > 0:
            where = {"quality_score": {"$gte": min_quality}}
        
        results = await asyncio.to_thread(
            self._collection.query,
            query_embeddings=[query_embedding],
            n_results=min(top_k * 3, 50),  
            where=where,
            include=["metadatas", "distances", "documents"]
        )
        
        if not results["ids"] or not results["ids"][0]:
            return []
        
        seen_bundles = {}
        for i, (chroma_id, distance, metadata, document) in enumerate(
            zip(
                results["ids"][0],
                results["distances"][0],
                results["metadatas"][0],
                results["documents"][0]
            )
        ):
            bundle_id = metadata["bundle_id"]
            similarity = 1.0 - distance  
            
            if bundle_id not in seen_bundles or similarity > seen_bundles[bundle_id]["similarity"]:
                seen_bundles[bundle_id] = {
                    "bundle_id": bundle_id,
                    "similarity": round(similarity, 4),
                    "best_matching_memory": document,
                    "quality_score": metadata.get("quality_score", 0),
                    "price_microunits": metadata.get("price_microunits", _to_microunits(settings.marketplace.memory_base_price_usdc)),
                    "tags": metadata.get("tags", "").split(",") if metadata.get("tags") else []
                }
        
        ranked = sorted(
            seen_bundles.values(),
            key=lambda x: x["similarity"],
            reverse=True
        )[:top_k]
        
        bundle_ids = [item["bundle_id"] for item in ranked]
        bundles_list = await MemoryBundle.find(
        {"bundle_id": {"$in": bundle_ids}, "is_active": True}).to_list()
        bundles_map = {b.bundle_id: b for b in bundles_list}


        enriched = []
        for item in ranked:
            bundle = bundles_map.get(item["bundle_id"])
            if bundle:
                enriched.append({
                    "bundle_id": bundle.bundle_id,
                    "title": bundle.title,
                    "description": bundle.description,
                    "price_microunits": bundle.price_microunits,
                    "avg_quality_score": bundle.avg_quality_score,
                    "memory_count": len(bundle.memories),
                    "tags": bundle.tags,
                    "similarity": item["similarity"],
                    "best_matching_memory_preview": item["best_matching_memory"][:150] + "...",
                    "purchase_endpoint": f"/memory/purchase/{bundle.bundle_id}"
                })
        
        logger.info("Search returned %d results for: '%s'", len(enriched), query[:40])
        return enriched
    
    async def get_bundle(self, bundle_id: str) -> Optional[MemoryBundle]:
        """Fetch a full bundle by ID. Returns None if not found."""
        return await MemoryBundle.find_one(
            MemoryBundle.bundle_id == bundle_id
        )
    
    async def list_bundles(
        self,
        limit: int = 20,
        min_quality: float = 0.0
    ) -> list[MemoryBundle]:
        """List active bundles, sorted by quality score descending."""
        query = MemoryBundle.find(
            MemoryBundle.is_active == True
        )
        if min_quality > 0:
            query = MemoryBundle.find(
                MemoryBundle.is_active == True,
                MemoryBundle.avg_quality_score >= min_quality
            )
        
        return await query.sort("-avg_quality_score").limit(limit).to_list()
    
    async def increment_purchase_count(self, bundle_id: str) -> None:
        """Increment purchase_count after a successful sale."""
        bundle = await MemoryBundle.find_one(MemoryBundle.bundle_id == bundle_id)
        if bundle is None:
            logger.warning("increment purchase count: bundle %s not found", bundle_id)
            return
        await bundle.update({"$inc": {"purchase_count": 1}})