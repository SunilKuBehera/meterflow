"""
Tests for UsageEvent model and usage ingestion.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models.billing import (
    Tenant,
    UsageEvent,
)
from repositories.usage import UsageRepository
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
                timestamp=base_time + timedelta(seconds=i)
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
