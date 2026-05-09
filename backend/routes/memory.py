"""
routes/memory.py

Memory bundle routes — Phase 3.
All routes now use the real MemoryStore (MongoDB + ChromaDB).
"""

from fastapi import APIRouter, Request, HTTPException, Query, Security, Depends
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from typing import Optional, Any
import logging

from backend.config import settings
from backend.payments.models import PaymentRecord
from backend.utils.sanitize import sanitize_text, sanitize_list

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

logger = logging.getLogger(__name__)
router = APIRouter()


class PublishRequest(BaseModel):
    title: str
    description: str
    memories: list[str]
    publisher_wallet: str


class BundlePreview(BaseModel):
    bundle_id: str
    title: str
    description: str
    price_microunits: int
    quality_score: Optional[float] = None
    tags: list[str] = []



@router.get("/list")
async def list_bundles(
    request: Request,
    limit: int = Query(default=20, le=100),
    min_quality: float = Query(default=0.0, ge=0.0, le=1.0)
) -> dict[str, Any]:
    """Lists active memory bundles from MongoDB, sorted by quality."""
    store = request.app.state.memory_store
    bundles = await store.list_bundles(limit=limit, min_quality=min_quality)

    return {
        "bundles": [
            {
                "bundle_id": b.bundle_id,
                "title": b.title,
                "description": b.description,
                "price_microunits": b.price_microunits,
                "avg_quality_score": b.avg_quality_score,
                "memory_count": len(b.memories),
                "purchase_count": b.purchase_count,
                "tags": b.tags,
                "created_at": b.created_at,
                "purchase_endpoint": f"/memory/purchase/{b.bundle_id}"
            }
            for b in bundles
        ],
        "total": len(bundles)
    }


@router.get("/search")
async def search_bundles(
    request: Request,
    q: str = Query(..., description="Natural language search query"),
    top_k: int = Query(default=5, le=20),
    min_quality: float = Query(default=0.0, ge=0.0, le=1.0)
) -> dict[str, Any]:
    """Semantic search over memory bundles using ChromaDB."""
    if len(q.strip()) < 3:
        raise HTTPException(status_code=400, detail="Query must be at least 3 characters")

    store = request.app.state.memory_store
    results = await store.search(query=q, top_k=top_k, min_quality=min_quality)

    return {
        "query": q,
        "results": results,
        "total": len(results)
    }


@router.get("/info/{bundle_id}")
async def bundle_info(bundle_id: str, request: Request) -> dict[str, Any]:
    """Returns metadata about a specific bundle. Does not return full content."""
    store = request.app.state.memory_store
    bundle = await store.get_bundle(bundle_id)

    if not bundle:
        raise HTTPException(status_code=404, detail=f"Bundle {bundle_id} not found")
    if not bundle.is_active:
        raise HTTPException(status_code=410, detail="This bundle has been delisted")

    return {
        "bundle_id": bundle.bundle_id,
        "title": bundle.title,
        "description": bundle.description,
        "price_microunits": bundle.price_microunits,
        "avg_quality_score": bundle.avg_quality_score,
        "memory_count": len(bundle.memories),
        "purchase_count": bundle.purchase_count,
        "tags": bundle.tags,
        "created_at": bundle.created_at,
        "requires_payment": True,
        "purchase_endpoint": f"/memory/purchase/{bundle.bundle_id}",
        "preview": bundle.memories[0].text[:100] + "..." if bundle.memories else None
    }



@router.get("/purchase/{bundle_id}")
async def purchase_bundle(bundle_id: str, request: Request) -> dict[str, Any]:
    """
    PAID ROUTE — requires x402 payment.
    Middleware verifies payment before this handler runs.
    request.state.payment contains tx_hash, amount_microunits, payer, verified_at.
    """
    payment = getattr(request.state, "payment", None)
    if not payment:
        raise HTTPException(status_code=402, detail="Payment information missing")

    payer = payment.get("payer")
    if not payer:
        logger.error("Payer address missing. TX: %s", payment.get("tx_hash"))
        raise HTTPException(status_code=500, detail="Payment verification incomplete — payer address missing")

    store = request.app.state.memory_store
    bundle = await store.get_bundle(bundle_id)

    if not bundle:
        raise HTTPException(status_code=404, detail=f"Bundle {bundle_id} not found")
    if not bundle.is_active:
        raise HTTPException(status_code=410, detail="This bundle has been delisted")

    logger.info(
        "Bundle '%s' purchased by %s (TX: %s)",
        bundle.title,
        payer[:20],
        payment.get("tx_hash", "")[:20]
    )

    existing = await PaymentRecord.find_one(PaymentRecord.tx_hash == payment["tx_hash"])
    if existing:
        raise HTTPException(
            status_code=409,
            detail="This transaction has already been used to purchase a bundle"
        )

    record = PaymentRecord(
        bundle_id=bundle_id,
        tx_hash=payment["tx_hash"],
        payer=payer,
        payee=bundle.publisher_wallet,
        amount_microunits=payment["amount_microunits"],
        local_only=payment.get("localVerificationOnly", False)
    )
    try:
        await record.insert()
        await store.increment_purchase_count(bundle_id)
    except Exception as e:
        logger.error("Failed to record payment for bundle %s TX %s: %s",
                     bundle_id, payment.get("tx_hash", ""), e)
        raise HTTPException(
            status_code=500,
            detail="Payment recorded on-chain but receipt save failed. Contact support with your transaction hash."
        )


    return {
        "bundle_id": bundle.bundle_id,
        "title": bundle.title,
        "payment": {
            "tx_hash": payment["tx_hash"],
            "amount_microunits": payment["amount_microunits"],
            "verified": True
        },
        "content": {
            "memories": [
                {
                    "id": m.memory_id,
                    "text": m.text,
                    "quality_score": m.quality_score,
                    "tags": m.tags,
                    "timestamp": m.timestamp
                }
                for m in bundle.memories
            ],
            "total_memories": len(bundle.memories),
            "avg_quality_score": bundle.avg_quality_score
        }
    }



async def _verify_publisher_key(key: str = Security(_api_key_header)) -> None:
    """Simple API key guard for the publish endpoint."""
    if not settings.demo_api_key:
        return  
    if key != settings.demo_api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")



@router.post("/publish")
async def publish_bundle(req: PublishRequest, request: Request, _: None = Depends(_verify_publisher_key)) -> dict[str, Any]:
    """
    Publisher endpoint: submits raw memories for quality scoring,
    embedding, and storage. Open for hackathon — add auth in production.
    """
    if len(req.memories) == 0:
        raise HTTPException(status_code=400, detail="memories list cannot be empty")
    if len(req.memories) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 memories per bundle")

    req.title = sanitize_text(req.title, max_length=200)
    req.description = sanitize_text(req.description, max_length=2000)
    req.memories = sanitize_list(req.memories, max_length=5000)

    store = request.app.state.memory_store
    bundle = await store.save_bundle(
        title=req.title,
        description=req.description,
        publisher_wallet=req.publisher_wallet,
        raw_memories=req.memories
    )

    if not bundle:
        raise HTTPException(
            status_code=422,
            detail="All submitted memories failed quality threshold. Bundle not created."
        )

    return {
        "bundle_id": bundle.bundle_id,
        "title": bundle.title,
        "memories_submitted": len(req.memories),
        "memories_accepted": len(bundle.memories),
        "avg_quality_score": bundle.avg_quality_score,
        "tags": bundle.tags,
        "price_microunits": bundle.price_microunits,
        "status": "published",
        "purchase_endpoint": f"/memory/purchase/{bundle.bundle_id}"
    }