from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "meterflow"
    APP_ENV: Literal["development", "staging", "production", "test"] = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["json", "console"] = "console"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database (Supabase PostgreSQL)
    DATABASE_URL: str = Field(default="", description="PostgreSQL connection string")
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_TIMEOUT: int = 30

    # Supabase Auth
    SUPABASE_URL: str = Field(default="", description="Supabase project URL")
    SUPABASE_ANON_KEY: str = Field(default="", description="Supabase anon public key")
    SUPABASE_SERVICE_ROLE_KEY: str = Field(
        default="", description="Supabase service role key (backend only)"
    )
    SUPABASE_JWT_SECRET: str = Field(
        default="", description="Supabase JWT secret for token validation"
    )

    # AI Provider
    AI_PROVIDER: Literal["mock", "ollama", "gemini"] = "mock"
    USAGE_MODE: Literal["simulated", "real"] = "simulated"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1"
    OLLAMA_TIMEOUT: int = 120
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # AI request bounds (applied before any provider call)
    AI_MAX_PROMPT_CHARS: int = 8000
    AI_MAX_OUTPUT_TOKENS: int = 4096
    AI_DEFAULT_MAX_TOKENS: int = 512
    AI_MAX_TEMPERATURE: float = 2.0

    # Razorpay (Test Mode only)
    RAZORPAY_KEY_ID: str | None = None
    RAZORPAY_KEY_SECRET: str | None = None
    RAZORPAY_WEBHOOK_SECRET: str | None = None

    # Redis (for background jobs, rate limiting)
    REDIS_URL: str | None = None

    # CORS
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        description="Allowed CORS origins",
    )

    # Security
    SECRET_KEY: str = Field(default="", description="Secret key for signing")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Rate limiting (distinct from monthly quotas)
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
