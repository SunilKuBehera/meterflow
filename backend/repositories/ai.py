"""Tenant-scoped repository for ``AIRequest`` persistence."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.billing import AIRequest, AIRequestStatus


class AIRequestRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, request: AIRequest) -> AIRequest:
        self.session.add(request)
        await self.session.flush()
        await self.session.refresh(request)
        return request

    async def get_by_id(self, request_id: UUID) -> AIRequest | None:
        result = await self.session.execute(
            select(AIRequest).where(AIRequest.id == request_id)
        )
        return result.scalar_one_or_none()

    async def get_by_tenant_and_idempotency_key(
        self, tenant_id: UUID, idempotency_key: str
    ) -> AIRequest | None:
        result = await self.session.execute(
            select(AIRequest).where(
                AIRequest.tenant_id == tenant_id,
                AIRequest.idempotency_key == idempotency_key,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self, tenant_id: UUID, limit: int = 100, offset: int = 0
    ) -> Sequence[AIRequest]:
        result = await self.session.execute(
            select(AIRequest)
            .where(AIRequest.tenant_id == tenant_id)
            .order_by(AIRequest.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    async def update(self, request: AIRequest) -> AIRequest:
        await self.session.flush()
        await self.session.refresh(request)
        return request