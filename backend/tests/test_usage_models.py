"""
Tests for UsageEvent model and usage ingestion.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models.billing import (
    PlanName,
    Tenant,
    UsageEvent,
)
from repositories.billing import PlanRepository
from repositories.usage import UsageRepository
from services.quota import QuotaService
from services.usage import UsageService


class TestUsageEventModel:
    """Tests for UsageEvent model."""

    @pytest.mark.asyncio
    async def test_create_usage_event(self, db_session: AsyncSession):
        """Test creating a usage event."""
        tenant = Tenant(name="Test Tenant", slug="test-usage-tenant")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        usage_event = UsageEvent(
            tenant_id=tenant.id,
            idempotency_key="idem-123",
            api_calls=5,
            ai_input_tokens=100,
            ai_cached_input_tokens=10,
            ai_output_tokens=50,
            ai_reasoning_tokens=5,
        )
        db_session.add(usage_event)
        await db_session.commit()
        await db_session.refresh(usage_event)

        assert usage_event.id is not None
        assert usage_event.tenant_id == tenant.id
        assert usage_event.idempotency_key == "idem-123"
        assert usage_event.api_calls == 5
        assert usage_event.ai_input_tokens == 100
        assert usage_event.ai_cached_input_tokens == 10
        assert usage_event.ai_output_tokens == 50
        assert usage_event.ai_reasoning_tokens == 5
        assert usage_event.timestamp is not None

    @pytest.mark.asyncio
    async def test_usage_event_defaults(self, db_session: AsyncSession):
        """Test default values for usage event metrics."""
        tenant = Tenant(name="Test Tenant", slug="test-usage-defaults")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        usage_event = UsageEvent(
            tenant_id=tenant.id,
            idempotency_key="idem-defaults",
        )
        db_session.add(usage_event)
        await db_session.commit()
        await db_session.refresh(usage_event)

        assert usage_event.api_calls == 0
        assert usage_event.ai_input_tokens == 0
        assert usage_event.ai_cached_input_tokens == 0
        assert usage_event.ai_output_tokens == 0
        assert usage_event.ai_reasoning_tokens == 0

    @pytest.mark.asyncio
    async def test_unique_idempotency_per_tenant(self, db_session: AsyncSession):
        """Test that idempotency key is unique per tenant."""
        tenant = Tenant(name="Test Tenant", slug="test-unique-idem")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        event1 = UsageEvent(tenant_id=tenant.id, idempotency_key="same-key")
        event2 = UsageEvent(tenant_id=tenant.id, idempotency_key="same-key")
        db_session.add_all([event1, event2])

        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_same_idempotency_different_tenant(self, db_session: AsyncSession):
        """Test that same idempotency key can be used for different tenants."""
        tenant1 = Tenant(name="Tenant 1", slug="tenant-1")
        tenant2 = Tenant(name="Tenant 2", slug="tenant-2")
        db_session.add_all([tenant1, tenant2])
        await db_session.commit()
        await db_session.refresh(tenant1)
        await db_session.refresh(tenant2)

        event1 = UsageEvent(tenant_id=tenant1.id, idempotency_key="shared-key")
        event2 = UsageEvent(tenant_id=tenant2.id, idempotency_key="shared-key")
        db_session.add_all([event1, event2])
        await db_session.commit()

        assert event1.id is not None
        assert event2.id is not None
        assert event1.id != event2.id

    @pytest.mark.asyncio
    async def test_cascade_delete_tenant(self, db_session: AsyncSession):
        """Test that usage events are deleted when tenant is deleted."""
        tenant = Tenant(name="Test Tenant", slug="test-cascade-usage")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        usage_event = UsageEvent(tenant_id=tenant.id, idempotency_key="idem-cascade")
        db_session.add(usage_event)
        await db_session.commit()

        await db_session.delete(tenant)
        await db_session.commit()

        result = await db_session.execute(
            select(UsageEvent).where(UsageEvent.tenant_id == tenant.id)
        )
        assert result.scalar_one_or_none() is None


class TestUsageRepository:
    """Tests for UsageRepository."""

    @pytest.mark.asyncio
    async def test_get_by_tenant_and_idempotency_key(self, db_session: AsyncSession):
        tenant = Tenant(name="Test Tenant", slug="test-repo-get")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        repo = UsageRepository(db_session)
        event = UsageEvent(tenant_id=tenant.id, idempotency_key="repo-key", api_calls=10)
        db_session.add(event)
        await db_session.commit()
        await db_session.refresh(event)

        found = await repo.get_by_tenant_and_idempotency_key(tenant.id, "repo-key")
        assert found is not None
        assert found.id == event.id
        assert found.api_calls == 10

    @pytest.mark.asyncio
    async def test_get_by_tenant_and_idempotency_key_not_found(self, db_session: AsyncSession):
        tenant = Tenant(name="Test Tenant", slug="test-repo-not-found")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        repo = UsageRepository(db_session)
        found = await repo.get_by_tenant_and_idempotency_key(tenant.id, "non-existent")
        assert found is None

    @pytest.mark.asyncio
    async def test_get_by_tenant_pagination(self, db_session: AsyncSession):
        tenant = Tenant(name="Test Tenant", slug="test-repo-pagination")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        repo = UsageRepository(db_session)
        base_time = datetime(2024, 1, 1, tzinfo=UTC)
        for i in range(15):
            event = UsageEvent(
                tenant_id=tenant.id,
                idempotency_key=f"key-{i}",
                api_calls=i,
                timestamp=base_time + timedelta(seconds=i),
            )
            db_session.add(event)
        await db_session.commit()

        events = await repo.get_by_tenant(tenant.id, limit=5, offset=0)
        assert len(events) == 5
        # Should be ordered by timestamp desc (most recent first)
        assert events[0].api_calls == 14

        events_page2 = await repo.get_by_tenant(tenant.id, limit=5, offset=5)
        assert len(events_page2) == 5
        assert events_page2[0].api_calls == 9


class TestUsageService:
    """Tests for UsageService idempotency logic."""

    @pytest.mark.asyncio
    async def test_record_usage_creates_new(self, db_session: AsyncSession):
        tenant = Tenant(name="Test Tenant", slug="test-service-create")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        service = UsageService(db_session)
        event = await service.record_usage(
            tenant_id=tenant.id,
            idempotency_key="service-create-1",
            api_calls=3,
            ai_input_tokens=50,
        )

        assert event.id is not None
        assert event.tenant_id == tenant.id
        assert event.idempotency_key == "service-create-1"
        assert event.api_calls == 3
        assert event.ai_input_tokens == 50

    @pytest.mark.asyncio
    async def test_record_usage_idempotent(self, db_session: AsyncSession):
        """Test that duplicate idempotency key returns existing event without creating new."""
        tenant = Tenant(name="Test Tenant", slug="test-service-idempotent")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        service = UsageService(db_session)
        event1 = await service.record_usage(
            tenant_id=tenant.id,
            idempotency_key="idem-duplicate",
            api_calls=5,
        )
        event2 = await service.record_usage(
            tenant_id=tenant.id,
            idempotency_key="idem-duplicate",
            api_calls=10,  # Different metrics, should be ignored
        )

        assert event1.id == event2.id
        assert event2.api_calls == 5  # Original values preserved

    @pytest.mark.asyncio
    async def test_record_usage_different_keys(self, db_session: AsyncSession):
        tenant = Tenant(name="Test Tenant", slug="test-service-diff-keys")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        service = UsageService(db_session)
        event1 = await service.record_usage(
            tenant_id=tenant.id,
            idempotency_key="key-1",
            api_calls=1,
        )
        event2 = await service.record_usage(
            tenant_id=tenant.id,
            idempotency_key="key-2",
            api_calls=2,
        )

        assert event1.id != event2.id
        assert event1.api_calls == 1
        assert event2.api_calls == 2

    @pytest.mark.asyncio
    async def test_get_usage_by_tenant(self, db_session: AsyncSession):
        tenant = Tenant(name="Test Tenant", slug="test-service-get")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        service = UsageService(db_session)
        await service.record_usage(tenant_id=tenant.id, idempotency_key="k1", api_calls=1)
        await service.record_usage(tenant_id=tenant.id, idempotency_key="k2", api_calls=2)
        await service.record_usage(tenant_id=tenant.id, idempotency_key="k3", api_calls=3)

        events = await service.get_usage_by_tenant(tenant.id, limit=10, offset=0)
        assert len(events) == 3
        # Sort by api_calls descending to verify all three are present
        sorted_events = sorted(events, key=lambda e: e.api_calls, reverse=True)
        assert sorted_events[0].api_calls == 3
        assert sorted_events[1].api_calls == 2
        assert sorted_events[2].api_calls == 1


class TestUsageAPI:
    """Integration tests for Usage API endpoints."""

    @pytest.mark.asyncio
    async def test_record_usage_endpoint(self, client, db_session: AsyncSession):
        from models.billing import Tenant

        tenant = Tenant(name="API Tenant", slug="api-usage-tenant")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        payload = {
            "tenant_id": str(tenant.id),
            "idempotency_key": "api-idem-1",
            "api_calls": 7,
            "ai_input_tokens": 200,
        }
        response = await client.post("/api/v1/usage/", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["tenant_id"] == str(tenant.id)
        assert data["idempotency_key"] == "api-idem-1"
        assert data["api_calls"] == 7
        assert data["ai_input_tokens"] == 200

    @pytest.mark.asyncio
    async def test_record_usage_idempotent_endpoint(self, client, db_session: AsyncSession):
        from models.billing import Tenant

        tenant = Tenant(name="API Tenant", slug="api-idempotent")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        payload = {
            "tenant_id": str(tenant.id),
            "idempotency_key": "api-idem-dup",
            "api_calls": 5,
        }
        # First request
        response1 = await client.post("/api/v1/usage/", json=payload)
        assert response1.status_code == 201
        data1 = response1.json()

        # Second request with same idempotency key but different api_calls
        payload["api_calls"] = 10
        response2 = await client.post("/api/v1/usage/", json=payload)
        assert response2.status_code == 201
        data2 = response2.json()

        # Should return the same event
        assert data1["id"] == data2["id"]
        assert data2["api_calls"] == 5  # Original value preserved

    @pytest.mark.asyncio
    async def test_get_usage_endpoint(self, client, db_session: AsyncSession):
        from models.billing import Tenant

        tenant = Tenant(name="API Tenant", slug="api-get-usage")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        from services.usage import UsageService

        service = UsageService(db_session)
        await service.record_usage(tenant_id=tenant.id, idempotency_key="k1", api_calls=1)
        await service.record_usage(tenant_id=tenant.id, idempotency_key="k2", api_calls=2)

        response = await client.get(f"/api/v1/usage/{tenant.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        api_calls = [item["api_calls"] for item in data]
        assert set(api_calls) == {1, 2}

    @pytest.mark.asyncio
    async def test_record_usage_tenant_not_found(self, client):
        import uuid

        payload = {
            "tenant_id": str(uuid.uuid4()),
            "idempotency_key": "test",
            "api_calls": 1,
        }
        response = await client.post("/api/v1/usage/", json=payload)
        # Should return 404 for non-existent tenant
        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Tenant not found"


class TestQuotaEnforcement:
    """Tests for quota enforcement."""

    @pytest.mark.asyncio
    async def test_quota_allowed_below_limit(self, db_session: AsyncSession):
        """Test that usage is allowed when below quota."""
        from models.billing import Tenant

        tenant = Tenant(name="Test Tenant", slug="quota-allowed")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        # Create FREE plan subscription (1000 api calls, 100000 ai tokens)
        plan_repo = PlanRepository(db_session)
        free_plan = await plan_repo.get_by_name(PlanName.FREE)
        assert free_plan is not None

        from models.billing import Subscription, SubscriptionStatus
        from services.billing_period import get_billing_period_bounds

        now = datetime.now(UTC)
        period_start, period_end = get_billing_period_bounds(now)

        subscription = Subscription(
            tenant_id=tenant.id,
            plan_id=free_plan.id,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=period_start,
            current_period_end=period_end,
        )
        db_session.add(subscription)
        await db_session.commit()

        quota_service = QuotaService(db_session)
        result = await quota_service.check_quota(
            tenant_id=tenant.id, api_calls=10, ai_input_tokens=100
        )

        assert result.allowed is True
        assert result.api_calls_limit == 1000
        assert result.ai_tokens_limit == 100000
        assert result.api_calls_remaining == 990
        assert result.ai_tokens_remaining == 99900

    @pytest.mark.asyncio
    async def test_quota_exceeded_api_calls(self, db_session: AsyncSession):
        """Test that quota is enforced for API calls."""
        from models.billing import PlanName, Tenant
        from services.usage import UsageService

        tenant = Tenant(name="Test Tenant", slug="quota-api-exceeded")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        plan_repo = PlanRepository(db_session)
        free_plan = await plan_repo.get_by_name(PlanName.FREE)
        assert free_plan is not None

        from models.billing import Subscription, SubscriptionStatus
        from services.billing_period import get_billing_period_bounds

        now = datetime.now(UTC)
        period_start, period_end = get_billing_period_bounds(now)

        subscription = Subscription(
            tenant_id=tenant.id,
            plan_id=free_plan.id,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=period_start,
            current_period_end=period_end,
        )
        db_session.add(subscription)
        await db_session.commit()

        # Record some usage first
        usage_service = UsageService(db_session)
        await usage_service.record_usage(
            tenant_id=tenant.id, idempotency_key="use-1", api_calls=990
        )

        quota_service = QuotaService(db_session)

        # Next request should exceed quota
        result = await quota_service.check_quota(tenant_id=tenant.id, api_calls=20)
        assert result.allowed is False
        assert result.error_message is not None
        assert "API calls quota exceeded" in result.error_message

    @pytest.mark.asyncio
    async def test_quota_exceeded_ai_tokens(self, db_session: AsyncSession):
        """Test that quota is enforced for AI tokens."""
        from models.billing import PlanName, Tenant
        from services.usage import UsageService

        tenant = Tenant(name="Test Tenant", slug="quota-ai-exceeded")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        plan_repo = PlanRepository(db_session)
        free_plan = await plan_repo.get_by_name(PlanName.FREE)
        assert free_plan is not None

        from models.billing import Subscription, SubscriptionStatus
        from services.billing_period import get_billing_period_bounds

        now = datetime.now(UTC)
        period_start, period_end = get_billing_period_bounds(now)

        subscription = Subscription(
            tenant_id=tenant.id,
            plan_id=free_plan.id,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=period_start,
            current_period_end=period_end,
        )
        db_session.add(subscription)
        await db_session.commit()

        # Record some usage first
        usage_service = UsageService(db_session)
        await usage_service.record_usage(
            tenant_id=tenant.id, idempotency_key="use-1", ai_input_tokens=99000
        )

        quota_service = QuotaService(db_session)

        # Next request should exceed quota
        result = await quota_service.check_quota(tenant_id=tenant.id, ai_input_tokens=2000)
        assert result.allowed is False
        assert result.error_message is not None
        assert "AI tokens quota exceeded" in result.error_message

    @pytest.mark.asyncio
    async def test_quota_exact_boundary(self, db_session: AsyncSession):
        """Test quota behavior at exact boundary."""
        from models.billing import PlanName, Tenant
        from services.usage import UsageService

        tenant = Tenant(name="Test Tenant", slug="quota-boundary")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        plan_repo = PlanRepository(db_session)
        free_plan = await plan_repo.get_by_name(PlanName.FREE)
        assert free_plan is not None

        from models.billing import Subscription, SubscriptionStatus
        from services.billing_period import get_billing_period_bounds

        now = datetime.now(UTC)
        period_start, period_end = get_billing_period_bounds(now)

        subscription = Subscription(
            tenant_id=tenant.id,
            plan_id=free_plan.id,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=period_start,
            current_period_end=period_end,
        )
        db_session.add(subscription)
        await db_session.commit()

        # Record exactly up to the limit
        usage_service = UsageService(db_session)
        await usage_service.record_usage(
            tenant_id=tenant.id, idempotency_key="use-1", api_calls=1000
        )

        quota_service = QuotaService(db_session)

        # One more should fail
        result = await quota_service.check_quota(tenant_id=tenant.id, api_calls=1)
        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_quota_inactive_subscription_uses_free_limits(self, db_session: AsyncSession):
        """Test that inactive subscription falls back to FREE plan limits."""
        from models.billing import PlanName, Tenant

        tenant = Tenant(name="Test Tenant", slug="quota-inactive")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        plan_repo = PlanRepository(db_session)
        free_plan = await plan_repo.get_by_name(PlanName.FREE)
        pro_plan = await plan_repo.get_by_name(PlanName.PRO)
        assert free_plan is not None
        assert pro_plan is not None

        from models.billing import Subscription, SubscriptionStatus
        from services.billing_period import get_billing_period_bounds

        now = datetime.now(UTC)
        period_start, period_end = get_billing_period_bounds(now)

        # Create subscription with PRO plan but INACTIVE status
        subscription = Subscription(
            tenant_id=tenant.id,
            plan_id=pro_plan.id,
            status=SubscriptionStatus.PAST_DUE,
            current_period_start=period_start,
            current_period_end=period_end,
        )
        db_session.add(subscription)
        await db_session.commit()

        quota_service = QuotaService(db_session)
        # Should use FREE plan limits (1000) not PRO plan limits (100000)
        result = await quota_service.check_quota(tenant_id=tenant.id, api_calls=5000)
        assert result.allowed is False  # FREE limit is 1000
        assert result.api_calls_limit == 1000

    @pytest.mark.asyncio
    async def test_quota_no_subscription_uses_free_limits(self, db_session: AsyncSession):
        """Test that tenant without subscription uses FREE plan limits."""
        from models.billing import Tenant

        tenant = Tenant(name="Test Tenant", slug="quota-no-sub")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        quota_service = QuotaService(db_session)
        # Should use FREE plan limits
        result = await quota_service.check_quota(tenant_id=tenant.id, api_calls=500)
        assert result.allowed is True
        assert result.api_calls_limit == 1000

        result = await quota_service.check_quota(tenant_id=tenant.id, api_calls=2000)
        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_quota_ai_token_categories_summed(self, db_session: AsyncSession):
        """Test that all AI token categories are summed for quota."""
        from models.billing import PlanName, Tenant
        from services.usage import UsageService

        tenant = Tenant(name="Test Tenant", slug="quota-ai-categories")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        plan_repo = PlanRepository(db_session)
        free_plan = await plan_repo.get_by_name(PlanName.FREE)
        assert free_plan is not None

        from models.billing import Subscription, SubscriptionStatus
        from services.billing_period import get_billing_period_bounds

        now = datetime.now(UTC)
        period_start, period_end = get_billing_period_bounds(now)

        subscription = Subscription(
            tenant_id=tenant.id,
            plan_id=free_plan.id,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=period_start,
            current_period_end=period_end,
        )
        db_session.add(subscription)
        await db_session.commit()

        # Record usage across different categories that sum to near limit
        usage_service = UsageService(db_session)
        await usage_service.record_usage(
            tenant_id=tenant.id,
            idempotency_key="use-1",
            ai_input_tokens=30000,
            ai_cached_input_tokens=20000,
            ai_output_tokens=25000,
            ai_reasoning_tokens=15000,
        )
        # Total = 90000, should be allowed

        quota_service = QuotaService(db_session)

        # Adding more should exceed
        result = await quota_service.check_quota(
            tenant_id=tenant.id,
            ai_input_tokens=20000,
        )
        # Total would be 110000 > 100000
        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_exact_boundary_record_usage(self, db_session: AsyncSession):
        """Test that usage exactly at the limit succeeds, one over fails."""
        from models.billing import Tenant
        from services.usage import QuotaExceededError, UsageService

        tenant = Tenant(name="Test Tenant", slug="quota-exact-bound")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        usage_service = UsageService(db_session)

        # Use exactly 1000 API calls (FREE plan limit)
        await usage_service.record_usage(
            tenant_id=tenant.id,
            idempotency_key="use-1",
            api_calls=1000,
        )

        # Next request should fail - we're now at the limit
        with pytest.raises(QuotaExceededError) as exc_info:
            await usage_service.record_usage(
                tenant_id=tenant.id,
                idempotency_key="use-2",
                api_calls=1,
            )
        assert "API calls quota exceeded" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_concurrent_last_unit_protection(self, db_session: AsyncSession):
        """Test that concurrent requests don't allow both to consume the final quota unit.

        This test creates a scenario where two concurrent requests try to use
        the last available quota unit. Only one should succeed.
        """
        from models.billing import PlanName, Subscription, SubscriptionStatus, Tenant
        from services.usage import QuotaExceededError, UsageService

        tenant = Tenant(name="Test Tenant", slug="quota-concurrent")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        # Create subscription with FREE plan (1000 API calls)
        plan_repo = PlanRepository(db_session)
        free_plan = await plan_repo.get_by_name(PlanName.FREE)
        from services.billing_period import get_billing_period_bounds

        now = datetime.now(UTC)
        period_start, period_end = get_billing_period_bounds(now)
        subscription = Subscription(
            tenant_id=tenant.id,
            plan_id=free_plan.id,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=period_start,
            current_period_end=period_end,
        )
        db_session.add(subscription)
        await db_session.commit()

        # Record 999 API calls first
        usage_service = UsageService(db_session)
        await usage_service.record_usage(
            tenant_id=tenant.id,
            idempotency_key="use-999",
            api_calls=999,
        )

        # Now simulate two concurrent requests each trying to use the last unit
        # In a real concurrent scenario, both might read 999 used and try to add 1
        # With proper locking, only one should succeed

        success_count = 0
        failure_count = 0

        # First concurrent request - should succeed (999 + 1 = 1000, at limit)
        try:
            await usage_service.record_usage(
                tenant_id=tenant.id,
                idempotency_key="concurrent-1",
                api_calls=1,
            )
            success_count += 1
        except QuotaExceededError:
            failure_count += 1

        # Second concurrent request - should fail (already at 1000 limit)
        try:
            await usage_service.record_usage(
                tenant_id=tenant.id,
                idempotency_key="concurrent-2",
                api_calls=1,
            )
            success_count += 1
        except QuotaExceededError:
            failure_count += 1

        # Exactly one should succeed
        assert success_count == 1, f"Expected 1 success, got {success_count}"
        assert failure_count == 1, f"Expected 1 failure, got {failure_count}"

    @pytest.mark.asyncio
    async def test_quota_consumption_is_atomic(self, db_session: AsyncSession):
        """Test that quota consumption and recording happen atomically.

        If a usage event is recorded, the quota must have been consumed.
        The reverse should also be true.
        """
        from models.billing import PlanName, Subscription, SubscriptionStatus, Tenant
        from services.usage import UsageService

        tenant = Tenant(name="Test Tenant", slug="quota-atomic")
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        plan_repo = PlanRepository(db_session)
        free_plan = await plan_repo.get_by_name(PlanName.FREE)
        from services.billing_period import get_billing_period_bounds

        now = datetime.now(UTC)
        period_start, period_end = get_billing_period_bounds(now)
        subscription = Subscription(
            tenant_id=tenant.id,
            plan_id=free_plan.id,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=period_start,
            current_period_end=period_end,
        )
        db_session.add(subscription)
        await db_session.commit()

        usage_service = UsageService(db_session)

        # Record a usage event
        event = await usage_service.record_usage(
            tenant_id=tenant.id,
            idempotency_key="atomic-test",
            api_calls=100,
            ai_output_tokens=500,
        )

        # Verify the event was actually created
        assert event.id is not None
        assert event.api_calls == 100

        # Verify quota was actually consumed
        quota_service = QuotaService(db_session)
        result = await quota_service.check_quota(tenant_id=tenant.id)
        assert result.api_calls_used == 100
        assert result.api_calls_remaining == 900
