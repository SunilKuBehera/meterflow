from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from models.billing import UsageEvent
from repositories.usage import UsageRepository


class UsageService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.usage_repo = UsageRepository(session)

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
        """Record usage with idempotency check.

        If a usage event with the same tenant_id and idempotency_key already exists,
        return the existing event without creating a new one.
        """
        # Check for existing usage event with same idempotency key
        existing = await self.usage_repo.get_by_tenant_and_idempotency_key(
            tenant_id, idempotency_key
        )
        if existing:
            return existing

        # Create new usage event
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
