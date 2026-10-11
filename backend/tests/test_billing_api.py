"""
Integration tests for billing API endpoints.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


class TestTenantAPI:
    """Tests for tenant API endpoints."""

    @pytest.mark.asyncio
    async def test_create_tenant(self, client: AsyncClient, db_session: AsyncSession):
        """Test creating a new tenant."""
        response = await client.post(
            "/api/v1/billing/tenants",
            json={"name": "Test Tenant", "slug": "test-tenant"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Tenant"
        assert data["slug"] == "test-tenant"
        assert "id" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_create_tenant_duplicate_slug(self, client: AsyncClient, db_session: AsyncSession):
        """Test creating tenant with duplicate slug fails."""
        await client.post(
            "/api/v1/billing/tenants",
            json={"name": "Test Tenant", "slug": "duplicate-slug"},
        )
        response = await client.post(
            "/api/v1/billing/tenants",
            json={"name": "Another Tenant", "slug": "duplicate-slug"},
        )
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_tenants(self, client: AsyncClient, db_session: AsyncSession):
        """Test listing tenants."""
        await client.post("/api/v1/billing/tenants", json={"name": "Tenant 1", "slug": "tenant-1"})
        await client.post("/api/v1/billing/tenants", json={"name": "Tenant 2", "slug": "tenant-2"})

        response = await client.get("/api/v1/billing/tenants")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2

    @pytest.mark.asyncio
    async def test_get_tenant(self, client: AsyncClient, db_session: AsyncSession):
        """Test getting a tenant by ID."""
        create_resp = await client.post(
            "/api/v1/billing/tenants", json={"name": "Get Tenant", "slug": "get-tenant"}
        )
        tenant_id = create_resp.json()["id"]

        response = await client.get(f"/api/v1/billing/tenants/{tenant_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == tenant_id
        assert data["name"] == "Get Tenant"

    @pytest.mark.asyncio
    async def test_get_tenant_by_slug(self, client: AsyncClient, db_session: AsyncSession):
        """Test getting a tenant by slug."""
        await client.post("/api/v1/billing/tenants", json={"name": "Slug Tenant", "slug": "slug-tenant"})

        response = await client.get("/api/v1/billing/tenants/slug/slug-tenant")
        assert response.status_code == 200
        data = response.json()
        assert data["slug"] == "slug-tenant"

    @pytest.mark.asyncio
    async def test_update_tenant(self, client: AsyncClient, db_session: AsyncSession):
        """Test updating a tenant."""
        create_resp = await client.post(
            "/api/v1/billing/tenants", json={"name": "Original", "slug": "update-tenant"}
        )
        tenant_id = create_resp.json()["id"]

        response = await client.patch(
            f"/api/v1/billing/tenants/{tenant_id}", json={"name": "Updated Name"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_delete_tenant(self, client: AsyncClient, db_session: AsyncSession):
        """Test deleting a tenant."""
        create_resp = await client.post(
            "/api/v1/billing/tenants", json={"name": "To Delete", "slug": "delete-tenant"}
        )
        tenant_id = create_resp.json()["id"]

        response = await client.delete(f"/api/v1/billing/tenants/{tenant_id}")
        assert response.status_code == 204

        get_resp = await client.get(f"/api/v1/billing/tenants/{tenant_id}")
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_nonexistent_tenant(self, client: AsyncClient):
        """Test getting a non-existent tenant returns 404."""
        response = await client.get("/api/v1/billing/tenants/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404


class TestTenantMemberAPI:
    """Tests for tenant member API endpoints."""

    @pytest.mark.asyncio
    async def test_add_tenant_member(self, client: AsyncClient, db_session: AsyncSession):
        """Test adding a member to a tenant."""
        tenant_resp = await client.post(
            "/api/v1/billing/tenants", json={"name": "Member Tenant", "slug": "member-tenant"}
        )
        tenant_id = tenant_resp.json()["id"]

        response = await client.post(
            f"/api/v1/billing/tenants/{tenant_id}/members",
            json={"user_id": "user-123", "role": "OWNER"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["tenant_id"] == tenant_id
        assert data["user_id"] == "user-123"
        assert data["role"] == "OWNER"

    @pytest.mark.asyncio
    async def test_add_duplicate_member(self, client: AsyncClient, db_session: AsyncSession):
        """Test adding duplicate member fails."""
        tenant_resp = await client.post(
            "/api/v1/billing/tenants", json={"name": "Dup Member Tenant", "slug": "dup-member-tenant"}
        )
        tenant_id = tenant_resp.json()["id"]

        await client.post(
            f"/api/v1/billing/tenants/{tenant_id}/members",
            json={"user_id": "user-dup", "role": "OWNER"},
        )
        response = await client.post(
            f"/api/v1/billing/tenants/{tenant_id}/members",
            json={"user_id": "user-dup", "role": "ADMIN"},
        )
        assert response.status_code == 409
        assert "already a member" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_tenant_members(self, client: AsyncClient, db_session: AsyncSession):
        """Test listing tenant members."""
        tenant_resp = await client.post(
            "/api/v1/billing/tenants", json={"name": "List Members", "slug": "list-members"}
        )
        tenant_id = tenant_resp.json()["id"]

        await client.post(f"/api/v1/billing/tenants/{tenant_id}/members", json={"user_id": "user-a", "role": "OWNER"})
        await client.post(f"/api/v1/billing/tenants/{tenant_id}/members", json={"user_id": "user-b", "role": "MEMBER"})

        response = await client.get(f"/api/v1/billing/tenants/{tenant_id}/members")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_update_tenant_member(self, client: AsyncClient, db_session: AsyncSession):
        """Test updating a tenant member role."""
        tenant_resp = await client.post(
            "/api/v1/billing/tenants", json={"name": "Update Member", "slug": "update-member"}
        )
        tenant_id = tenant_resp.json()["id"]

        member_resp = await client.post(
            f"/api/v1/billing/tenants/{tenant_id}/members",
            json={"user_id": "user-update", "role": "MEMBER"},
        )
        member_id = member_resp.json()["id"]

        response = await client.patch(
            f"/api/v1/billing/tenants/{tenant_id}/members/{member_id}",
            json={"role": "ADMIN"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "ADMIN"

    @pytest.mark.asyncio
    async def test_remove_tenant_member(self, client: AsyncClient, db_session: AsyncSession):
        """Test removing a tenant member."""
        tenant_resp = await client.post(
            "/api/v1/billing/tenants", json={"name": "Remove Member", "slug": "remove-member"}
        )
        tenant_id = tenant_resp.json()["id"]

        member_resp = await client.post(
            f"/api/v1/billing/tenants/{tenant_id}/members",
            json={"user_id": "user-remove", "role": "MEMBER"},
        )
        member_id = member_resp.json()["id"]

        response = await client.delete(f"/api/v1/billing/tenants/{tenant_id}/members/{member_id}")
        assert response.status_code == 204

        get_resp = await client.get(f"/api/v1/billing/tenants/{tenant_id}/members/{member_id}")
        assert get_resp.status_code == 404


class TestPlanAPI:
    """Tests for plan API endpoints."""

    @pytest.mark.asyncio
    async def test_list_plans(self, client: AsyncClient, db_session: AsyncSession):
        """Test listing plans."""
        response = await client.get("/api/v1/billing/plans")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_list_active_plans(self, client: AsyncClient, db_session: AsyncSession):
        """Test listing active plans."""
        response = await client.get("/api/v1/billing/plans/active")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        for plan in data:
            assert plan["is_active"] is True

    @pytest.mark.asyncio
    async def test_get_plan_by_name(self, client: AsyncClient, db_session: AsyncSession):
        """Test getting a plan by name."""
        response = await client.get("/api/v1/billing/plans/name/FREE")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "FREE"
        assert data["display_name"] == "Free"

    @pytest.mark.asyncio
    async def test_get_pro_plan_by_name(self, client: AsyncClient, db_session: AsyncSession):
        """Test getting PRO plan by name."""
        response = await client.get("/api/v1/billing/plans/name/PRO")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "PRO"
        assert data["price_paise"] == 99900

    @pytest.mark.asyncio
    async def test_get_nonexistent_plan(self, client: AsyncClient):
        """Test getting non-existent plan returns 404."""
        response = await client.get("/api/v1/billing/plans/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404


class TestSubscriptionAPI:
    """Tests for subscription API endpoints."""

    @pytest.mark.asyncio
    async def test_create_subscription(self, client: AsyncClient, db_session: AsyncSession):
        """Test creating a subscription."""
        tenant_resp = await client.post(
            "/api/v1/billing/tenants", json={"name": "Sub Tenant", "slug": "sub-tenant"}
        )
        tenant_id = tenant_resp.json()["id"]

        plan_resp = await client.get("/api/v1/billing/plans/name/FREE")
        plan_id = plan_resp.json()["id"]

        from datetime import UTC, datetime

        from services.billing_period import get_billing_period_bounds

        now = datetime.now(UTC)
        period_start, period_end = get_billing_period_bounds(now)

        response = await client.post(
            "/api/v1/billing/subscriptions",
            json={
                "tenant_id": tenant_id,
                "plan_id": plan_id,
                "status": "ACTIVE",
                "current_period_start": period_start.isoformat(),
                "current_period_end": period_end.isoformat(),
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["tenant_id"] == tenant_id
        assert data["plan_id"] == plan_id
        assert data["status"] == "ACTIVE"
        assert data["plan"] is not None
        assert data["tenant"] is not None

    @pytest.mark.asyncio
    async def test_create_duplicate_subscription(self, client: AsyncClient, db_session: AsyncSession):
        """Test creating duplicate subscription for same tenant fails."""
        tenant_resp = await client.post(
            "/api/v1/billing/tenants", json={"name": "Dup Sub Tenant", "slug": "dup-sub-tenant"}
        )
        tenant_id = tenant_resp.json()["id"]

        plan_resp = await client.get("/api/v1/billing/plans/name/FREE")
        plan_id = plan_resp.json()["id"]

        from datetime import UTC, datetime

        from services.billing_period import get_billing_period_bounds

        now = datetime.now(UTC)
        period_start, period_end = get_billing_period_bounds(now)

        await client.post(
            "/api/v1/billing/subscriptions",
            json={
                "tenant_id": tenant_id,
                "plan_id": plan_id,
                "current_period_start": period_start.isoformat(),
                "current_period_end": period_end.isoformat(),
            },
        )
        response = await client.post(
            "/api/v1/billing/subscriptions",
            json={
                "tenant_id": tenant_id,
                "plan_id": plan_id,
                "current_period_start": period_start.isoformat(),
                "current_period_end": period_end.isoformat(),
            },
        )
        assert response.status_code == 409
        assert "already has a subscription" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_tenant_subscription(self, client: AsyncClient, db_session: AsyncSession):
        """Test getting a tenant's subscription."""
        tenant_resp = await client.post(
            "/api/v1/billing/tenants", json={"name": "Get Sub Tenant", "slug": "get-sub-tenant"}
        )
        tenant_id = tenant_resp.json()["id"]

        plan_resp = await client.get("/api/v1/billing/plans/name/FREE")
        plan_id = plan_resp.json()["id"]

        from datetime import UTC, datetime

        from services.billing_period import get_billing_period_bounds

        now = datetime.now(UTC)
        period_start, period_end = get_billing_period_bounds(now)

        await client.post(
            "/api/v1/billing/subscriptions",
            json={
                "tenant_id": tenant_id,
                "plan_id": plan_id,
                "status": "ACTIVE",
                "current_period_start": period_start.isoformat(),
                "current_period_end": period_end.isoformat(),
            },
        )

        response = await client.get(f"/api/v1/billing/tenants/{tenant_id}/subscription")
        assert response.status_code == 200
        data = response.json()
        assert data["tenant_id"] == tenant_id
        assert data["plan"]["name"] == "FREE"

    @pytest.mark.asyncio
    async def test_list_subscriptions(self, client: AsyncClient, db_session: AsyncSession):
        """Test listing subscriptions."""
        response = await client.get("/api/v1/billing/subscriptions")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_update_subscription(self, client: AsyncClient, db_session: AsyncSession):
        """Test updating a subscription."""
        tenant_resp = await client.post(
            "/api/v1/billing/tenants", json={"name": "Update Sub Tenant", "slug": "update-sub-tenant"}
        )
        tenant_id = tenant_resp.json()["id"]

        plan_resp = await client.get("/api/v1/billing/plans/name/FREE")
        plan_id = plan_resp.json()["id"]

        from datetime import UTC, datetime

        from services.billing_period import get_billing_period_bounds

        now = datetime.now(UTC)
        period_start, period_end = get_billing_period_bounds(now)

        create_resp = await client.post(
            "/api/v1/billing/subscriptions",
            json={
                "tenant_id": tenant_id,
                "plan_id": plan_id,
                "current_period_start": period_start.isoformat(),
                "current_period_end": period_end.isoformat(),
            },
        )
        subscription_id = create_resp.json()["id"]

        pro_plan_resp = await client.get("/api/v1/billing/plans/name/PRO")
        pro_plan_id = pro_plan_resp.json()["id"]

        response = await client.patch(
            f"/api/v1/billing/subscriptions/{subscription_id}",
            json={"plan_id": pro_plan_id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["plan_id"] == pro_plan_id
        assert data["plan"]["name"] == "PRO"

    @pytest.mark.asyncio
    async def test_delete_subscription(self, client: AsyncClient, db_session: AsyncSession):
        """Test deleting a subscription."""
        tenant_resp = await client.post(
            "/api/v1/billing/tenants", json={"name": "Delete Sub Tenant", "slug": "delete-sub-tenant"}
        )
        tenant_id = tenant_resp.json()["id"]

        plan_resp = await client.get("/api/v1/billing/plans/name/FREE")
        plan_id = plan_resp.json()["id"]

        from datetime import UTC, datetime

        from services.billing_period import get_billing_period_bounds

        now = datetime.now(UTC)
        period_start, period_end = get_billing_period_bounds(now)

        create_resp = await client.post(
            "/api/v1/billing/subscriptions",
            json={
                "tenant_id": tenant_id,
                "plan_id": plan_id,
                "current_period_start": period_start.isoformat(),
                "current_period_end": period_end.isoformat(),
            },
        )
        subscription_id = create_resp.json()["id"]

        response = await client.delete(f"/api/v1/billing/subscriptions/{subscription_id}")
        assert response.status_code == 204

        get_resp = await client.get(f"/api/v1/billing/subscriptions/{subscription_id}")
        assert get_resp.status_code == 404
