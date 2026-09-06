import os
from typing import Any, List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central application configuration.
    Strictly validates types, environment modes, and security thresholds at startup.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # Environment & Server
    APP_ENV: str = Field(default="development", description="development | staging | production")
    APP_NAME: str = Field(default="Enterprise Website Assistant")
    APP_VERSION: str = Field(default="1.0.0")
    PROMPT_VERSION: str = Field(default="company-assistant-v1.4")
    DEBUG: bool = Field(default=False)
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)

    # Security & Cryptography
    SECRET_KEY: str = Field(
        default="change-this-in-production-insecure-default-secret-key-32chars",
        description="Used for signing session cookies and HMAC tokens"
    )
    SESSION_COOKIE_NAME: str = Field(default="sec_chatbot_session")
    SESSION_MAX_AGE_SECONDS: int = Field(default=86400 * 7)  # 7 days
    SECURE_COOKIES: bool = Field(default=False)  # True in HTTPS production
    ADMIN_API_KEY: str = Field(
        default="admin-super-secret-key-change-in-prod",
        description="Dedicated API key for automated ingestion, CI/CD, and webhooks"
    )

    # CORS & Security Headers
    ALLOWED_ORIGINS: Any = Field(
        default=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000", "http://127.0.0.1:5173"],
        description="Allowed CORS origins"
    )
    CSP_FRAME_ANCESTORS: str = Field(default="'self'")

    # Database & Storage
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./chatbot.db",
        description="PostgreSQL asyncpg URL or SQLite aiosqlite for tests/local dev"
    )
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    REDIS_FALLBACK_MEMORY: bool = Field(default=True, description="Fallback to in-memory store if Redis is unavailable")

    # Rate Limiting & Abuse
    RATE_LIMIT_PER_MINUTE: int = Field(default=30)
    RATE_LIMIT_BURST: int = Field(default=10)
    MAX_REQUEST_PAYLOAD_BYTES: int = Field(default=32 * 1024)  # 32 KB maximum payload
    MAX_INPUT_CHARS: int = Field(default=4000)
    MAX_INPUT_TOKENS: int = Field(default=1000)
    MAX_OUTPUT_TOKENS: int = Field(default=1500)
    ABUSE_SCORE_THRESHOLD: int = Field(default=5)

    # LLM Gateway & Providers
    LLM_PROVIDER: str = Field(default="groq", description="groq | openai | mock")
    PRIMARY_MODEL: str = Field(default="groq/compound-mini")
    FALLBACK_MODEL: str = Field(default="mock-model")
    FALLBACK_PROVIDER: str = Field(default="mock")
    GROQ_API_KEY: Optional[str] = Field(default=None, description="Groq Cloud API Key")
    LLM_API_KEY: Optional[str] = Field(default=None)
    LLM_API_BASE: Optional[str] = Field(default="https://api.groq.com/openai/v1")
    LLM_TIMEOUT_SECONDS: float = Field(default=25.0)
    LLM_MAX_RETRIES: int = Field(default=3)
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = Field(default=3)
    CIRCUIT_BREAKER_RECOVERY_TIME: float = Field(default=30.0)

    # Token & Cost Management
    DAILY_COST_BUDGET_USD: float = Field(default=50.0)
    PER_REQUEST_MAX_COST_USD: float = Field(default=0.10)

    # RAG & Retrieval
    EMBEDDING_MODEL: str = Field(default="local-deterministic", description="local-deterministic | bge-small-en")
    EMBEDDING_DIMENSION: int = Field(default=1536)
    VECTOR_TOP_K: int = Field(default=8)
    SIMILARITY_THRESHOLD: float = Field(default=0.45)
    RERANKER_TOP_N: int = Field(default=5)
    CHUNK_SIZE: int = Field(default=500)
    CHUNK_OVERLAP: int = Field(default=75)

    # Observability
    LOG_LEVEL: str = Field(default="INFO")
    ENABLE_OTEL: bool = Field(default=True)
    OTEL_EXPORTER_OTLP_ENDPOINT: Optional[str] = Field(default=None)

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v


# Instantiate singleton settings
settings = Settings()
