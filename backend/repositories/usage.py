from uuid import UUID
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.billing import UsageEvent


class UsageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, usage_event: UsageEvent) -> UsageEvent:
        self.session.add(usage_event)
        await self.session.flush()
        await self.session.refresh(usage_event)
        return usage_event

    async def get_by_id(self, usage_event_id: UUID) -> UsageEvent | None:
        result = await self.session.execute(
            select(UsageEvent).where(UsageEvent.id == usage_event_id)
        )
        return result.scalar_one_or_none()

    async def get_by_tenant_and_idempotency_key(
        self, tenant_id: UUID, idempotency_key: str
    ) -> UsageEvent | None:
        result = await self.session.execute(
            select(UsageEvent).where(
                UsageEvent.tenant_id == tenant_id,
                UsageEvent.idempotency_key == idempotency_key,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_tenant(
        self, tenant_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[UsageEvent]:
        result = await self.session.execute(
            select(UsageEvent)
            .where(UsageEvent.tenant_id == tenant_id)
            .order_by(UsageEvent.timestamp.desc(), UsageEvent.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def update(self, usage_event: UsageEvent) -> UsageEvent:
        await self.session.flush()
        await self.session.refresh(usage_event)
        return usage_event

    async def delete(self, usage_event: UsageEvent) -> None:
        await self.session.delete(usage_event)
        await self.session.flush()
