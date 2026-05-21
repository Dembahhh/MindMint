"""
config.py

Centralised configuration loader.
All environment variables are validated on startup.
If a required variable is missing, the app will raise immediately
with a clear error message — not fail silently later.
"""

from __future__ import annotations
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional, Annotated
from pydantic import SecretStr, Field, BaseModel
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

class KiteConfig(BaseModel):
    rpc_url: str = "https://rpc-testnet.gokite.ai"
    chain_id: Annotated[int, Field(gt=0)] = 2368
    api_base_url: str = "https://api.testnet.gokite.ai"
    facilitator_url: str = "https://x402.testnet.gokite.ai/facilitator"
    is_testnet: bool = True
    
    usdc_contract_address: str
    
class WalletConfig(BaseModel):
    address: str
    private_key: SecretStr
    passport_id: Optional[str] = None

class LLMConfig(BaseModel):    
    api_key: SecretStr
    groq_api_key: SecretStr
    model: str = "llama-3.3-70b-versatile"
    embedding_model: str = "models/text-embedding-004"
    embedding_dim: int = 768
class DatabaseConfig(BaseModel):   
    mongo_db_url: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "MindMint"
    chroma_host: str = "localhost"
    chroma_port: Annotated[int, Field(gt=0, lt=65536)] = 8000
    chroma_ssl: bool = False
    chroma_collection_name: str = "memory_bundles"
    chroma_doc_max_length: int = 500
    
class MarketplaceConfig(BaseModel):
    memory_base_price_usdc: Annotated[float, Field(gt=0)] = 0.002
    publisher_royalty_percent: Annotated[float, Field(ge=0, le=1)]= 0.80
    quality_threshold: Annotated[float, Field(ge=0.0, le=1.0)] = 0.5
class APIConfig(BaseModel):
    port: Annotated[int, Field(gt=0, lt=65536)] = 8000
    host: str = "0.0.0.0"
    debug: bool = False
class AgentConfig(BaseModel):
    similarity_threshold: Annotated[float, Field(ge=0.0, le=1.0)] = 0.70
    quality_threshold: Annotated[float, Field(ge=0.0, le=1.0)] = 0.55
    max_bundles_per_run: Annotated[int, Field(gt=0)] = 3
    max_budget_usdc: Annotated[float, Field(gt=0)] = 0.01
    api_base_url: str = "http://localhost:8080"
    max_concurrent_runs: Annotated[int, Field(gt=0)] = 3

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_nested_delimiter="__",
        extra="ignore",  

    )
    kite: KiteConfig
    publisher: WalletConfig
    consumer: WalletConfig
    llm: LLMConfig
    database: DatabaseConfig = DatabaseConfig()
    marketplace: MarketplaceConfig = MarketplaceConfig()
    api: APIConfig = APIConfig()
    agent: AgentConfig = AgentConfig()
    environment: str = "development"

    # Top-level env vars (not nested)
    demo_api_key: Optional[str] = None
    frontend_url: Optional[str] = None
    sentry_dsn: Optional[str] = None


@lru_cache()
def get_settings() -> Settings:
    """Load and cache application settings from environment / .env file.
    
    Returns:
        Cached Settings instance. Validated on first call; subsequent
        calls return the cached object.
        
    Note:
        Call ``get_settings.cache_clear()`` in tests before overriding
        env vars, otherwise the cached instance will be returned."""
    return Settings()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO
                        , format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    s = get_settings()
    logger.info("Config loaded successfully")
    logger.info("   Kite RPC:          %s", s.kite.rpc_url)
    logger.info("   Chain ID:          %s", s.kite.chain_id)
    logger.info("   Facilitator URL:   %s", s.kite.facilitator_url)
    logger.info("   Testnet:           %s", s.kite.is_testnet)
    logger.info("   Publisher Wallet:  %s", s.publisher.address)
    logger.info("   Consumer Wallet:   %s", s.consumer.address)
    logger.info("   MongoDB:           %s", s.database.mongo_db_url)
    logger.info("   MongoDB DB:        %s", s.database.mongodb_db_name)
    logger.info("   Gemini Model:      %s", s.llm.model)
    logger.info("   Chroma Host:       %s", s.database.chroma_host)
    logger.info("   Chroma Port:       %s", s.database.chroma_port)
    logger.info("   Chroma Collection: %s", s.database.chroma_collection_name)
    logger.info("   Memory Base Price: %s", s.marketplace.memory_base_price_usdc)
    logger.info("   Publisher Royalty: %s", s.marketplace.publisher_royalty_percent)
    logger.info("   Embedding Model:   %s", s.llm.embedding_model)
    logger.info("   Quality Threshold: %s", s.marketplace.quality_threshold)
    logger.info("   Agent API Base URL:        %s", s.agent.api_base_url)
    logger.info("   Agent Similarity Threshold: %s", s.agent.similarity_threshold)
    logger.info("   Agent Max Bundles/Run:      %s", s.agent.max_bundles_per_run)
    logger.info("   Agent Max Concurrent Runs:  %s", s.agent.max_concurrent_runs)
    logger.info("\n All required variables present.")

settings = get_settings()    