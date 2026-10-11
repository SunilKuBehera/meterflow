import os
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("SECRET_KEY", "test-secret-key")


async def _seed_plans(session: AsyncSession) -> None:
    """Seed Free and Pro plans."""
    from models.billing import Plan, PlanName

    free_plan = Plan(
        name=PlanName.FREE,
        display_name="Free",
        description="Perfect for getting started with AI API metering",
        price_paise=0,
        currency="INR",
        billing_period="monthly",
        api_calls_limit=1000,
        ai_tokens_limit=100000,
    )
    session.add(free_plan)

    pro_plan = Plan(
        name=PlanName.PRO,
        display_name="Pro",
        description="For growing teams and production applications",
        price_paise=99900,
        currency="INR",
        billing_period="monthly",
        api_calls_limit=100000,
        ai_tokens_limit=10000000,
        api_call_price_paise=10,
        ai_input_token_price_paise=5,
        ai_cached_input_token_price_paise=1,
        ai_output_token_price_paise=15,
        ai_reasoning_token_price_paise=15,
    )
    session.add(pro_plan)
    await session.commit()


@pytest.fixture(scope="session")
async def engine():
    """Create a test database engine."""
    engine = create_async_engine(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/meterflow",
        poolclass=NullPool,
        echo=False,
    )

    # Import all models BEFORE creating tables to register them with Base.metadata
    from models.base import Base
    from models.billing import Plan, Subscription, Tenant, TenantMember  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session with clean tables."""
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Truncate all tables before each test to ensure clean state
        async with session.begin():
            await session.execute(text("TRUNCATE TABLE subscriptions, plans, tenant_members, tenants RESTART IDENTITY CASCADE"))
        # Re-seed plans after truncate
        await _seed_plans(session)

        yield session


@pytest.fixture
async def client(engine, db_session):
    """Create a test client with test database."""
    # Override the app's database engine and session factory
    from api.deps import get_db
    from main import app

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def anyio_backend():
    return "asyncio"
