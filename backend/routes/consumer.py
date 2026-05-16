"""
routes/consumer.py

HTTP endpoints that trigger the Consumer Agent.

POST /agent/consumer/run
  Accepts a task description.
  Runs the full autonomous loop.
  Returns the answer + receipts.

GET /agent/consumer/status
  Returns Consumer Agent wallet info and configuration.
"""

from fastapi import APIRouter, HTTPException, Depends, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, field_validator
from typing import Optional, Any
import logging
import asyncio
import httpx

from backend.agents.consumer_agent import ConsumerAgent
from backend.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()
_api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)


class RunTaskRequest(BaseModel):
    task: str
    max_budget_usdc: Optional[float] = 0.01

    @field_validator("max_budget_usdc")
    @classmethod
    def budget_must_be_positive(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v <= 0:
            raise ValueError("max_budget_usdc must be greater than 0")
        if v is not None and v > settings.agent.max_budget_usdc:
            raise ValueError(
                f"max_budget_usdc cannot exceed system maximum of "
                f"{settings.agent.max_budget_usdc}"
            )
        return v


class BundleReceipt(BaseModel):
    bundle_id: str
    title: str
    memory_count: int
    amount_usdc: float
    tx_hash: str
    similarity: float


class RunTaskResponse(BaseModel):
    task: str
    answer: str
    memories_used: int
    total_spent_usdc: float
    bundles_purchased: list[BundleReceipt]
    search_queries: list[str]
    error: Optional[str] = None


_run_semaphore = asyncio.Semaphore(settings.agent.max_concurrent_runs)


async def _require_api_key(key: str = Security(_api_key_header)) -> None:
    """Guard for sensitive endpoints that trigger real payments."""
    if settings.environment == "development":
        return
    if not settings.demo_api_key:
        raise HTTPException(status_code=500, detail="API key not configured on server")
    if key != settings.demo_api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")

@router.post("/run", response_model=RunTaskResponse)
async def run_consumer_task(
    req: RunTaskRequest,
    _: None = Depends(_require_api_key),
) -> RunTaskResponse:
    """
    Runs the Consumer Agent for a given task.

    The agent will:
      1. Plan search queries from the task
      2. Search the marketplace
      3. Autonomously purchase relevant bundles
      4. Return an answer informed by purchased memories

    This is a synchronous endpoint — it blocks until the agent completes.
    Typical runtime: 5-15 seconds depending on number of purchases.
    """
    if not req.task or len(req.task.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Task must be at least 10 characters",
        )

    try:
        await asyncio.wait_for(_run_semaphore.acquire(), timeout=30.0)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=503, detail="Server busy, please retry shortly")

    try:
        agent = ConsumerAgent(
            server_url=settings.agent.api_base_url,
            max_budget_usdc=req.max_budget_usdc,
        )
        result = await agent.run(req.task)

        return RunTaskResponse(
            task=result.task,
            answer=result.answer,
            memories_used=result.memories_used,
            total_spent_usdc=result.total_spent_usdc,
            bundles_purchased=[
                BundleReceipt(
                    bundle_id=b.bundle_id,
                    title=b.title,
                    memory_count=len(b.memories),
                    amount_usdc=b.amount_usdc,
                    tx_hash=b.tx_hash,
                    similarity=b.similarity,
                )
                for b in result.purchased_bundles
            ],
            search_queries=result.search_queries_used,
            error=result.error,
        )

    except (httpx.HTTPError, ValueError, RuntimeError) as e:
        logger.error("Consumer agent run failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Agent run failed: {str(e)}",
        )

    finally:
        _run_semaphore.release()


@router.get("/status")
async def consumer_status(_: None = Depends(_require_api_key)) -> dict[str, Any]:
    """Returns Consumer Agent wallet info and configuration."""
    return {
        "wallet": settings.consumer.address,
        "max_budget_usdc": settings.agent.max_budget_usdc,
        "similarity_threshold": settings.agent.similarity_threshold,
        "quality_threshold": settings.agent.quality_threshold,
        "max_bundles_per_run": settings.agent.max_bundles_per_run,
        "status": "ready",
    }