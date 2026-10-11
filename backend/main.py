from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.billing import router as billing_router
from core.config import get_settings
from core.errors import register_exception_handlers
from core.logging import configure_logging, get_logger
from core.middleware import RequestIDMiddleware
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

app.add_middleware(RequestIDMiddleware)

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


@app.get("/api/v1/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/ready", tags=["health"])
async def ready() -> dict[str, str]:
    return {"status": "ready"}
