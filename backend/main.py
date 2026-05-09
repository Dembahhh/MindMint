"""
main.py

FastAPI application entry point for MindMint.

Startup sequence:
  1. Load config
  2. Connect to MongoDB (via Beanie ODM)
  3. Connect to ChromaDB
  4. Register x402 payment middleware
  5. Mount all route modules
  6. Expose /health endpoint
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import chromadb
import logging
import asyncio
import google.generativeai as genai

from backend.config import settings
from backend.payments.x402_middleware import X402PaymentMiddleware
from backend.db import init_db, close_db
from backend.routes import memory_router, agent_router
from backend.memory.store import MemoryStore


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger("MindMint")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs on startup and shutdown."""
    logger.info("MindMint starting up...")
    
    try:
        await init_db()
        logger.info("MongoDB connected")
    except Exception as e:
        logger.error("Failed to connect to MongoDB: %s", e)
        raise

    genai.configure(api_key=settings.llm.api_key.get_secret_value())
    logger.info("Gemini API configured with model: %s", settings.llm.model)

    try:
        chroma_client = chromadb.HttpClient(
        host=settings.database.chroma_host,
        port=settings.database.chroma_port
        )
        await asyncio.to_thread(chroma_client.heartbeat)
        app.state.chroma = chroma_client
        app.state.chroma_collection = await asyncio.to_thread(
        chroma_client.get_or_create_collection,
        name=settings.database.chroma_collection_name,
        metadata={"hnsw:space": "cosine"}
        )
        app.state.memory_store = MemoryStore(app.state.chroma_collection)
        logger.info("ChromaDB connected")
    except Exception as e:
        logger.critical("Failed to connect to ChromaDB: %s", e)
        raise

    logger.info("MindMint ready. Listening on port %s", settings.api.port)
    logger.info("   Embedding Model:   %s", settings.llm.embedding_model)
    logger.info("   Quality Threshold: %s", settings.marketplace.quality_threshold)

    yield 
    
    try:
        await close_db()
        logger.info("MindMint shutdown complete")
    except Exception as e:
        logger.error("Error during shutdown: %s", e)

APP_VERSION = "0.1.0"
app = FastAPI(
    title="MindMint API",
    description="Marketplace for AI agent memory bundles, powered by x402 micropayments",
    version= APP_VERSION,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   
        "http://localhost:3000",  
        "https://MindMint.up.railway.app",  
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Payment", "X-Payment-Response"],
)

app.add_middleware(X402PaymentMiddleware)

app.include_router(memory_router, prefix="/memory", tags=["Memory"])
app.include_router(agent_router, prefix="/agent", tags=["Agent"])


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Liveness probe. Returns ok if server is running."""
    return {"status": "ok", "version": APP_VERSION}


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": "MindMint",
        "description": "AI agent memory marketplace",
        "docs": "/docs"
    }