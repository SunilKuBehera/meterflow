"""
Tests for billing models and schema constraints.
These tests verify the model definitions and constraints.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models.billing import (
    Plan,
    PlanName,
    Subscription,
    SubscriptionStatus,
    Tenant,
    TenantMember,
    TenantRole,
)


class TestTenantModel:
    """Tests for Tenant model."""

    @pytest.mark.asyncio
    async def test_create_tenant(self, db_session: AsyncSession):
        tenant = Tenant(name="Test Tenant", slug="test-tenant")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        assert tenant.id is not None
        assert tenant.name == "Test Tenant"
        assert tenant.slug == "test-tenant"
        assert tenant.created_at is not None
        assert tenant.updated_at is not None

    @pytest.mark.asyncio
    async def test_tenant_slug_unique(self, db_session: AsyncSession):
        tenant1 = Tenant(name="Tenant 1", slug="unique-slug")
        tenant2 = Tenant(name="Tenant 2", slug="unique-slug")
        db_session.add_all([tenant1, tenant2])

        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_tenant_slug_index(self, db_session: AsyncSession):
        """Verify slug column has index (implicitly tested by unique constraint)."""
        tenant = Tenant(name="Indexed Tenant", slug="indexed-tenant")
        db_session.add(tenant)
        await db_session.commit()

        result = await db_session.execute(
            select(Tenant).where(Tenant.slug == "indexed-tenant")
        )
        found = result.scalar_one()
        assert found.id == tenant.id


class TestTenantMemberModel:
    """Tests for TenantMember model."""

    @pytest.mark.asyncio
    async def test_create_member(self, db_session: AsyncSession):
        tenant = Tenant(name="Test Tenant", slug="test-tenant-member")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        member = TenantMember(
            tenant_id=tenant.id,
            user_id="user-123",
            role=TenantRole.OWNER,
        )
        db_session.add(member)
        await db_session.commit()
        await db_session.refresh(member)

        assert member.id is not None
        assert member.tenant_id == tenant.id
        assert member.user_id == "user-123"
        assert member.role == TenantRole.OWNER

    @pytest.mark.asyncio
    async def test_member_default_role(self, db_session: AsyncSession):
        tenant = Tenant(name="Test Tenant", slug="test-default-role")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        member = TenantMember(tenant_id=tenant.id, user_id="user-456")
        db_session.add(member)
        await db_session.commit()
        await db_session.refresh(member)

        assert member.role == TenantRole.MEMBER

    @pytest.mark.asyncio
    async def test_unique_tenant_user(self, db_session: AsyncSession):
        tenant = Tenant(name="Test Tenant", slug="test-unique-member")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        member1 = TenantMember(tenant_id=tenant.id, user_id="user-789", role=TenantRole.OWNER)
        member2 = TenantMember(tenant_id=tenant.id, user_id="user-789", role=TenantRole.ADMIN)
        db_session.add_all([member1, member2])

        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_cascade_delete_tenant(self, db_session: AsyncSession):
        tenant = Tenant(name="Test Tenant", slug="test-cascade")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        member = TenantMember(tenant_id=tenant.id, user_id="user-cascade")
        db_session.add(member)
        await db_session.commit()

        await db_session.delete(tenant)
        await db_session.commit()

        result = await db_session.execute(
            select(TenantMember).where(TenantMember.tenant_id == tenant.id)
        )
        assert result.scalar_one_or_none() is None


class TestPlanModel:
    """Tests for Plan model."""

    @pytest.mark.asyncio
    async def test_create_free_plan(self, db_session: AsyncSession):
        # Plans are seeded in fixture, test querying instead
        from repositories.billing import PlanRepository
        plan_repo = PlanRepository(db_session)
        plan = await plan_repo.get_by_name(PlanName.FREE)
        assert plan is not None
        assert plan.name == PlanName.FREE
        assert plan.price_paise == 0
        assert plan.api_calls_limit == 1000
        assert plan.ai_tokens_limit == 100000
        assert plan.is_active is True

    @pytest.mark.asyncio
    async def test_create_pro_plan(self, db_session: AsyncSession):
        from repositories.billing import PlanRepository
        plan_repo = PlanRepository(db_session)
        plan = await plan_repo.get_by_name(PlanName.PRO)
        assert plan is not None
        assert plan.name == PlanName.PRO
        assert plan.price_paise == 99900
        assert plan.api_calls_limit == 100000
        assert plan.ai_tokens_limit == 10000000

    @pytest.mark.asyncio
    async def test_plan_name_unique(self, db_session: AsyncSession):
        # Try to create a duplicate FREE plan (already seeded)
        plan = Plan(
            name=PlanName.FREE,
            display_name="Free Duplicate",
            price_paise=0,
            api_calls_limit=1000,
            ai_tokens_limit=100000,
        )
        db_session.add(plan)

        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_plan_defaults(self, db_session: AsyncSession):
        from repositories.billing import PlanRepository
        plan_repo = PlanRepository(db_session)
        plan = await plan_repo.get_by_name(PlanName.FREE)
        assert plan is not None

        assert plan.currency == "INR"
        assert plan.billing_period == "monthly"
        assert plan.api_call_price_paise == 0
        assert plan.ai_input_token_price_paise == 0
        assert plan.ai_cached_input_token_price_paise == 0
        assert plan.ai_output_token_price_paise == 0
        assert plan.ai_reasoning_token_price_paise == 0
        assert plan.is_active is True
        assert plan.razorpay_plan_id is None


class TestSubscriptionModel:
    """Tests for Subscription model."""

    @pytest.mark.asyncio
    async def test_create_subscription(self, db_session: AsyncSession):
        # Create tenant and use seeded plan
        tenant = Tenant(name="Test Tenant", slug="test-sub-tenant")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        from repositories.billing import PlanRepository
        plan_repo = PlanRepository(db_session)
        plan = await plan_repo.get_by_name(PlanName.FREE)
        assert plan is not None

        now = datetime.now(UTC)
        from services.billing_period import get_billing_period_bounds
        period_start, period_end = get_billing_period_bounds(now)

        subscription = Subscription(
            tenant_id=tenant.id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=period_start,
            current_period_end=period_end,
        )
        db_session.add(subscription)
        await db_session.commit()
        await db_session.refresh(subscription)

        assert subscription.id is not None
        assert subscription.tenant_id == tenant.id
        assert subscription.plan_id == plan.id
        assert subscription.status == SubscriptionStatus.ACTIVE
        assert subscription.cancel_at_period_end is False
        assert subscription.canceled_at is None

    @pytest.mark.asyncio
    async def test_subscription_defaults(self, db_session: AsyncSession):
        tenant = Tenant(name="Test Tenant", slug="test-sub-defaults")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        from repositories.billing import PlanRepository
        plan_repo = PlanRepository(db_session)
        plan = await plan_repo.get_by_name(PlanName.FREE)
        assert plan is not None

        now = datetime.now(UTC)
        from services.billing_period import get_billing_period_bounds
        period_start, period_end = get_billing_period_bounds(now)

        subscription = Subscription(
            tenant_id=tenant.id,
            plan_id=plan.id,
            current_period_start=period_start,
            current_period_end=period_end,
        )
        db_session.add(subscription)
        await db_session.commit()
        await db_session.refresh(subscription)

        assert subscription.status == SubscriptionStatus.INCOMPLETE
        assert subscription.cancel_at_period_end is False

    @pytest.mark.asyncio
    async def test_unique_tenant_subscription(self, db_session: AsyncSession):
        tenant = Tenant(name="Test Tenant", slug="test-unique-sub")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        from repositories.billing import PlanRepository
        plan_repo = PlanRepository(db_session)
        plan1 = await plan_repo.get_by_name(PlanName.FREE)
        plan2 = await plan_repo.get_by_name(PlanName.PRO)
        assert plan1 is not None
        assert plan2 is not None

        now = datetime.now(UTC)
        from services.billing_period import get_billing_period_bounds
        period_start, period_end = get_billing_period_bounds(now)

        sub1 = Subscription(
            tenant_id=tenant.id,
            plan_id=plan1.id,
            current_period_start=period_start,
            current_period_end=period_end,
        )
        sub2 = Subscription(
            tenant_id=tenant.id,
            plan_id=plan2.id,
            current_period_start=period_start,
            current_period_end=period_end,
        )
        db_session.add_all([sub1, sub2])

        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_cascade_delete_tenant_subscription(self, db_session: AsyncSession):
        tenant = Tenant(name="Test Tenant", slug="test-sub-cascade")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        from repositories.billing import PlanRepository
        plan_repo = PlanRepository(db_session)
        plan = await plan_repo.get_by_name(PlanName.FREE)
        assert plan is not None
        await db_session.refresh(plan)

        now = datetime.now(UTC)
        from services.billing_period import get_billing_period_bounds
        period_start, period_end = get_billing_period_bounds(now)

        subscription = Subscription(
            tenant_id=tenant.id,
            plan_id=plan.id,
            current_period_start=period_start,
            current_period_end=period_end,
        )
        db_session.add(subscription)
        await db_session.commit()

        await db_session.delete(tenant)
        await db_session.commit()

        result = await db_session.execute(
            select(Subscription).where(Subscription.tenant_id == tenant.id)
        )
        assert result.scalar_one_or_none() is None


class TestBillingPeriodHelper:
    """Tests for billing period helper functions."""

    def test_get_billing_period_bounds(self):
        from services.billing_period import get_billing_period_bounds

        # Test with a specific date
        dt = datetime(2024, 6, 15, 12, 30, tzinfo=UTC)
        start, end = get_billing_period_bounds(dt)

        assert start == datetime(2024, 6, 1, tzinfo=UTC)
        assert end == datetime(2024, 7, 1, tzinfo=UTC)

    def test_get_billing_period_bounds_december(self):
        from services.billing_period import get_billing_period_bounds

        dt = datetime(2024, 12, 25, tzinfo=UTC)
        start, end = get_billing_period_bounds(dt)

        assert start == datetime(2024, 12, 1, tzinfo=UTC)
        assert end == datetime(2025, 1, 1, tzinfo=UTC)

    def test_is_within_billing_period(self):
        from services.billing_period import (
            is_within_billing_period,
        )

        period_start = datetime(2024, 6, 1, tzinfo=UTC)
        period_end = datetime(2024, 7, 1, tzinfo=UTC)

        # Inside period
        assert is_within_billing_period(
            datetime(2024, 6, 15, tzinfo=UTC), period_start, period_end
        )
        # Start boundary (inclusive)
        assert is_within_billing_period(period_start, period_start, period_end)
        # End boundary (exclusive)
        assert not is_within_billing_period(period_end, period_start, period_end)
        # Before period
        assert not is_within_billing_period(
            datetime(2024, 5, 31, tzinfo=UTC), period_start, period_end
        )
        # After period
        assert not is_within_billing_period(
            datetime(2024, 7, 2, tzinfo=UTC), period_start, period_end
        )

    def test_get_current_billing_period(self):
        from services.billing_period import get_current_billing_period

        start, end = get_current_billing_period()
        now = datetime.now(UTC)

        assert start <= now < end
        assert start.day == 1
        assert start.hour == 0
        assert start.minute == 0
        assert start.second == 0
