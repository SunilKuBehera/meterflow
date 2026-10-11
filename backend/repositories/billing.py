from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.billing import (
    Plan,
    PlanName,
    Subscription,
    SubscriptionStatus,
    Tenant,
    TenantMember,
)


class TenantRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, tenant: Tenant) -> Tenant:
        self.session.add(tenant)
        await self.session.flush()
        await self.session.refresh(tenant)
        return tenant

    async def get_by_id(self, tenant_id: UUID) -> Tenant | None:
        result = await self.session.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Tenant | None:
        result = await self.session.execute(
            select(Tenant).where(Tenant.slug == slug)
        )
        return result.scalar_one_or_none()

    async def get_all(self, limit: int = 100, offset: int = 0) -> Sequence[Tenant]:
        result = await self.session.execute(
            select(Tenant).order_by(Tenant.created_at.desc()).limit(limit).offset(offset)
        )
        return result.scalars().all()

    async def update(self, tenant: Tenant) -> Tenant:
        await self.session.flush()
        await self.session.refresh(tenant)
        return tenant

    async def delete(self, tenant: Tenant) -> None:
        await self.session.delete(tenant)
        await self.session.flush()

    async def exists_by_slug(self, slug: str, exclude_id: UUID | None = None) -> bool:
        query = select(func.count()).select_from(Tenant).where(Tenant.slug == slug)
        if exclude_id:
            query = query.where(Tenant.id != exclude_id)
        result = await self.session.execute(query)
        count = result.scalar()
        return (count or 0) > 0


class TenantMemberRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, member: TenantMember) -> TenantMember:
        self.session.add(member)
        await self.session.flush()
        await self.session.refresh(member)
        return member

    async def get_by_id(self, member_id: UUID) -> TenantMember | None:
        result = await self.session.execute(
            select(TenantMember).where(TenantMember.id == member_id)
        )
        return result.scalar_one_or_none()

    async def get_by_tenant_and_user(
        self, tenant_id: UUID, user_id: str
    ) -> TenantMember | None:
        result = await self.session.execute(
            select(TenantMember).where(
                TenantMember.tenant_id == tenant_id,
                TenantMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_tenant(self, tenant_id: UUID) -> Sequence[TenantMember]:
        result = await self.session.execute(
            select(TenantMember).where(TenantMember.tenant_id == tenant_id)
        )
        return result.scalars().all()

    async def get_by_user(self, user_id: str) -> Sequence[TenantMember]:
        result = await self.session.execute(
            select(TenantMember).where(TenantMember.user_id == user_id)
        )
        return result.scalars().all()

    async def update(self, member: TenantMember) -> TenantMember:
        await self.session.flush()
        await self.session.refresh(member)
        return member

    async def delete(self, member: TenantMember) -> None:
        await self.session.delete(member)
        await self.session.flush()


class PlanRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, plan: Plan) -> Plan:
        self.session.add(plan)
        await self.session.flush()
        await self.session.refresh(plan)
        return plan

    async def get_by_id(self, plan_id: UUID) -> Plan | None:
        result = await self.session.execute(
            select(Plan).where(Plan.id == plan_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: PlanName) -> Plan | None:
        result = await self.session.execute(
            select(Plan).where(Plan.name == name)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self, active_only: bool = False, limit: int = 100, offset: int = 0
    ) -> Sequence[Plan]:
        query = select(Plan).order_by(Plan.price_paise.asc())
        if active_only:
            query = query.where(Plan.is_active.is_(True))
        query = query.limit(limit).offset(offset)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_active_plans(self) -> Sequence[Plan]:
        result = await self.session.execute(
            select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.price_paise.asc())
        )
        return result.scalars().all()

    async def update(self, plan: Plan) -> Plan:
        await self.session.flush()
        await self.session.refresh(plan)
        return plan

    async def delete(self, plan: Plan) -> None:
        await self.session.delete(plan)
        await self.session.flush()


class SubscriptionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, subscription: Subscription) -> Subscription:
        self.session.add(subscription)
        await self.session.flush()
        await self.session.refresh(subscription)
        return subscription

    async def get_by_id(self, subscription_id: UUID) -> Subscription | None:
        result = await self.session.execute(
            select(Subscription).where(Subscription.id == subscription_id)
        )
        return result.scalar_one_or_none()

    async def get_by_tenant(self, tenant_id: UUID) -> Subscription | None:
        result = await self.session.execute(
            select(Subscription)
            .options(selectinload(Subscription.plan))
            .where(Subscription.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def get_by_tenant_with_plan(self, tenant_id: UUID) -> Subscription | None:
        result = await self.session.execute(
            select(Subscription)
            .options(selectinload(Subscription.plan), selectinload(Subscription.tenant))
            .where(Subscription.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def get_by_plan(self, plan_id: UUID) -> Sequence[Subscription]:
        result = await self.session.execute(
            select(Subscription).where(Subscription.plan_id == plan_id)
        )
        return result.scalars().all()

    async def get_by_status(self, status: SubscriptionStatus) -> Sequence[Subscription]:
        result = await self.session.execute(
            select(Subscription).where(Subscription.status == status)
        )
        return result.scalars().all()

    async def get_all(self, limit: int = 100, offset: int = 0) -> Sequence[Subscription]:
        result = await self.session.execute(
            select(Subscription)
            .options(selectinload(Subscription.plan), selectinload(Subscription.tenant))
            .order_by(Subscription.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    async def get_expiring_soon(self, days: int = 3) -> Sequence[Subscription]:
        cutoff = datetime.utcnow()
        result = await self.session.execute(
            select(Subscription)
            .options(selectinload(Subscription.plan), selectinload(Subscription.tenant))
            .where(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.current_period_end <= cutoff,
                Subscription.cancel_at_period_end.is_(False),
            )
        )
        return result.scalars().all()

    async def update(self, subscription: Subscription) -> Subscription:
        await self.session.flush()
        await self.session.refresh(subscription)
        return subscription

    async def delete(self, subscription: Subscription) -> None:
        await self.session.delete(subscription)
        await self.session.flush()
