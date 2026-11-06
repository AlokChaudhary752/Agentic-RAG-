"""Core configuration module for Enterprise Knowledge Agent.

Loads settings from environment variables and provides strictly typed configurations
using Pydantic Settings v2.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings with environment variable fallbacks."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Core Application
    app_name: str = Field(default="Enterprise Knowledge Agent", description="Application name")
    app_env: Literal["development", "test", "staging", "production"] = Field(
        default="development", description="Runtime environment"
    )
    app_debug: bool = Field(default=False, description="Debug mode")
    app_host: str = Field(default="0.0.0.0", description="Bind host")
    app_port: int = Field(default=8000, description="Bind port")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Logging verbosity level"
    )
    log_format: Literal["json", "console"] = Field(default="json", description="Log output format")
    default_tenant_id: str = Field(
        default="tenant-nimbus-default", description="Default tenant identifier"
    )

    # Security & Auth
    jwt_secret_key: str = Field(
        default="insecure-default-development-key-32-chars-minimum",
        description="JWT HMAC signing secret key",
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(
        default=60, description="JWT validity duration in minutes"
    )

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./enterprise_agent.db",
        description="Async database connection string",
    )
    database_test_url: str = Field(
        default="sqlite+aiosqlite:///./test_enterprise_agent.db",
        description="Test async database connection string",
    )

    # Vector Store (Qdrant)
    qdrant_host: str = Field(default="localhost", description="Qdrant host")
    qdrant_port: int = Field(default=6333, description="Qdrant HTTP port")
    qdrant_api_key: str | None = Field(default=None, description="Qdrant API key")
    qdrant_collection: str = Field(
        default="enterprise_documents", description="Qdrant collection name"
    )
    qdrant_vector_size: int = Field(default=1024, description="Vector embedding dimension")
    qdrant_use_in_memory: bool = Field(
        default=False, description="Use in-memory Qdrant client for testing and offline runs"
    )

    # Redis Cache & Broker
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    semantic_cache_enabled: bool = Field(
        default=True, description="Enable semantic caching for queries"
    )
    semantic_cache_ttl_seconds: int = Field(
        default=3600, description="Semantic cache TTL in seconds"
    )
    semantic_cache_similarity_threshold: float = Field(
        default=0.92, description="Cosine similarity threshold for semantic cache hit"
    )

    # LLM Settings
    llm_provider: str = Field(default="litellm", description="LLM provider router")
    llm_primary_model: str = Field(
        default="gemini/gemini-1.5-pro", description="Primary generation model"
    )
    llm_fast_model: str = Field(
        default="gemini/gemini-1.5-flash", description="Fast classification/grading model"
    )
    llm_local_ollama_url: str = Field(
        default="http://localhost:11434", description="Ollama local fallback endpoint"
    )
    openai_api_key: str | None = Field(default=None, description="OpenAI API Key")
    gemini_api_key: str | None = Field(default=None, description="Gemini API Key")
    anthropic_api_key: str | None = Field(default=None, description="Anthropic API Key")

    # Embeddings & Reranker
    embedding_model_name: str = Field(default="BAAI/bge-m3", description="Embedding model name")
    reranker_model_name: str = Field(
        default="BAAI/bge-reranker-v2-m3", description="Cross-encoder reranker model"
    )

    # Corpus & Ingestion
    sample_corpus_dir: str = Field(
        default="./data/sample_corpus", description="Sample corpus root path"
    )

    # Observability
    otel_enabled: bool = Field(default=False, description="Enable OpenTelemetry tracing")
    otel_exporter_otlp_endpoint: str = Field(
        default="http://localhost:4317", description="OTLP endpoint"
    )
    langfuse_enabled: bool = Field(default=False, description="Enable Langfuse observability")
    langfuse_public_key: str | None = Field(default=None, description="Langfuse public key")
    langfuse_secret_key: str | None = Field(default=None, description="Langfuse secret key")
    langfuse_host: str = Field(default="http://localhost:3000", description="Langfuse host URL")

    # Tool & MCP
    mcp_server_host: str = Field(default="0.0.0.0", description="MCP server host")
    mcp_server_port: int = Field(default=8005, description="MCP server port")

    # Budgets & Limits
    rate_limit_requests_per_minute: int = Field(
        default=60, description="Max allowed requests per user per minute"
    )
    agent_max_iterations: int = Field(
        default=5, description="Maximum iterative reasoning cycles in LangGraph"
    )
    agent_max_execution_time_seconds: int = Field(
        default=45, description="Agent execution timeout in seconds"
    )
    agent_budget_usd_per_query: float = Field(
        default=0.10, description="Maximum permitted monetary cost per query in USD"
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
