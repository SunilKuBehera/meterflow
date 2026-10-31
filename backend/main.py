from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware

from api.ai import router as ai_router
from api.billing import router as billing_router
from api.usage import router as usage_router
from core.config import get_settings
from core.errors import register_exception_handlers
from core.logging import configure_logging, get_logger
from core.middleware import add_middleware
from db.session import close_db, init_db

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging()
    logger.info("Starting application", app_name=settings.APP_NAME, env=settings.APP_ENV)
    await init_db()
    yield
    logger.info("Shutting down application")
    await close_db()


settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="MeterFlow API - Multi-tenant AI/API Usage Metering & Billing",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

add_middleware(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

register_exception_handlers(app)

# Include routers
app.include_router(billing_router, prefix="/api/v1")
app.include_router(usage_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Per-IP rate limiting applied at the framework level."""
    from core.middleware import _rate_limit_store

    client_host = request.client.host if request.client else "unknown"
    now = time.time()
    window_key = f"{client_host}:{int(now // settings.RATE_LIMIT_WINDOW_SECONDS)}"
    store = _rate_limit_store[window_key]
    count = store.get("count", 0) + 1
    store["count"] = count
    store["first"] = store.get("first", now)

    remaining = max(0, settings.RATE_LIMIT_REQUESTS - count)
    reset_time = int(store["first"] + settings.RATE_LIMIT_WINDOW_SECONDS)

    if count > settings.RATE_LIMIT_REQUESTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "RATE_LIMITED",
                "message": f"Rate limit exceeded: {settings.RATE_LIMIT_REQUESTS} requests per {settings.RATE_LIMIT_WINDOW_SECONDS}s",
                "retry_after": reset_time,
            },
        )

    response = await call_next(request)
    response.headers["X-Rate-Limit-Limit"] = str(settings.RATE_LIMIT_REQUESTS)
    response.headers["X-Rate-Limit-Remaining"] = str(remaining)
    response.headers["X-Rate-Limit-Reset"] = str(reset_time)
    return response


@app.get("/api/v1/health", tags=["health"])
async def health() -> dict[str, str]:
    """Health check that also reports database and provider readiness.

    Distinguishes app health from database/provider readiness.
    Returns 200 when the app is running; /ready is preferred for orchestration
    because it can distinguish downstream failures.
    """
    from core.config import get_settings
    from integrations.ai.factory import describe_provider

    s = get_settings()
    provider_status = describe_provider(s)

    return {
        "status": "ok",
        "app": s.APP_NAME,
        "env": s.APP_ENV,
        "database": "configured" if settings.DATABASE_URL else "not_configured",
        "provider": provider_status["provider"],
        "usage_mode": provider_status["usage_mode"],
        "provider_available": provider_status["available"],
        "detail": provider_status["detail"],
    }


@app.get("/api/v1/ready", tags=["health"])
async def ready() -> dict[str, str]:
    """Readiness check that distinguishes app health from downstream readiness.

    Returns 200 only when the app can serve requests.  The ``provider_available``
    field tells orchestrators whether the AI provider (mock or Ollama) is ready.
    """
    from core.config import get_settings
    from integrations.ai.factory import describe_provider

    s = get_settings()
    provider_status = describe_provider(s)

    return {
        "status": "ready" if provider_status["available"] or s.USAGE_MODE == "simulated" else "degraded",
        "provider_available": provider_status["available"],
        "usage_mode": provider_status["usage_mode"],
        "detail": provider_status["detail"],
    }
