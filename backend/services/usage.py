from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from models.billing import UsageEvent
from repositories.usage import UsageRepository
from services.quota import QuotaExceededError, QuotaService  # noqa: F401


class UsageService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.usage_repo = UsageRepository(session)
        self.quota_service = QuotaService(session)

    async def record_usage(
        self,
        tenant_id: UUID,
        idempotency_key: str,
        api_calls: int = 0,
        ai_input_tokens: int = 0,
        ai_cached_input_tokens: int = 0,
        ai_output_tokens: int = 0,
        ai_reasoning_tokens: int = 0,
    ) -> UsageEvent:
        """Record usage with idempotency check and quota enforcement.

        If a usage event with the same tenant_id and idempotency_key already exists,
        return the existing event without creating a new one.

        Raises QuotaExceededError if the usage would exceed the tenant's quota.

        This method performs quota consumption and usage recording in a single transaction
        to ensure consistency under concurrent requests.
        """
        # Check for existing usage event with same idempotency key
        existing = await self.usage_repo.get_by_tenant_and_idempotency_key(
            tenant_id, idempotency_key
        )
        if existing:
            return existing

        # Consume quota and create usage event atomically
        # This will raise QuotaExceededError if quota would be exceeded
        await self.quota_service.consume_quota(
            tenant_id=tenant_id,
            api_calls=api_calls,
            ai_input_tokens=ai_input_tokens,
            ai_cached_input_tokens=ai_cached_input_tokens,
            ai_output_tokens=ai_output_tokens,
            ai_reasoning_tokens=ai_reasoning_tokens,
        )

        # Create new usage event (will be persisted when transaction commits)
        usage_event = UsageEvent(
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
            api_calls=api_calls,
            ai_input_tokens=ai_input_tokens,
            ai_cached_input_tokens=ai_cached_input_tokens,
            ai_output_tokens=ai_output_tokens,
            ai_reasoning_tokens=ai_reasoning_tokens,
        )
        return await self.usage_repo.create(usage_event)

    async def get_usage_by_tenant(
        self, tenant_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[UsageEvent]:
        """Get usage events for a tenant."""
        return await self.usage_repo.get_by_tenant(tenant_id, limit=limit, offset=offset)
