from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from models.billing import PlanName
from repositories.billing import (
    PlanRepository,
    SubscriptionRepository,
    TenantMemberRepository,
    TenantRepository,
)
from schemas.billing import (
    PlanCreate,
    PlanResponse,
    PlanUpdate,
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionWithRelations,
    TenantCreate,
    TenantMemberCreate,
    TenantMemberResponse,
    TenantMemberUpdate,
    TenantResponse,
    TenantUpdate,
)

router = APIRouter(prefix="/billing", tags=["billing"])


# Tenant routes
@router.post("/tenants", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    tenant_data: TenantCreate,
    db: AsyncSession = Depends(get_db),
):
    tenant_repo = TenantRepository(db)

    if await tenant_repo.exists_by_slug(tenant_data.slug):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tenant with this slug already exists",
        )

    from models.billing import Tenant
    tenant = Tenant(name=tenant_data.name, slug=tenant_data.slug)
    return await tenant_repo.create(tenant)


@router.get("/tenants", response_model=list[TenantResponse])
async def list_tenants(
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    tenant_repo = TenantRepository(db)
    return await tenant_repo.get_all(limit=limit, offset=offset)


@router.get("/tenants/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    tenant_repo = TenantRepository(db)
    tenant = await tenant_repo.get_by_id(tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    return tenant


@router.get("/tenants/slug/{slug}", response_model=TenantResponse)
async def get_tenant_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    tenant_repo = TenantRepository(db)
    tenant = await tenant_repo.get_by_slug(slug)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    return tenant


@router.patch("/tenants/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: UUID,
    tenant_data: TenantUpdate,
    db: AsyncSession = Depends(get_db),
):
    tenant_repo = TenantRepository(db)
    tenant = await tenant_repo.get_by_id(tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    if tenant_data.name is not None:
        tenant.name = tenant_data.name

    return await tenant_repo.update(tenant)


@router.delete("/tenants/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    tenant_repo = TenantRepository(db)
    tenant = await tenant_repo.get_by_id(tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    await tenant_repo.delete(tenant)


# Tenant Member routes
@router.post(
    "/tenants/{tenant_id}/members",
    response_model=TenantMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_tenant_member(
    tenant_id: UUID,
    member_data: TenantMemberCreate,
    db: AsyncSession = Depends(get_db),
):
    tenant_repo = TenantRepository(db)
    member_repo = TenantMemberRepository(db)

    tenant = await tenant_repo.get_by_id(tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    existing = await member_repo.get_by_tenant_and_user(tenant_id, member_data.user_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this tenant",
        )

    from models.billing import TenantMember
    member = TenantMember(
        tenant_id=tenant_id,
        user_id=member_data.user_id,
        role=member_data.role,
    )
    return await member_repo.create(member)


@router.get("/tenants/{tenant_id}/members", response_model=list[TenantMemberResponse])
async def list_tenant_members(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    tenant_repo = TenantRepository(db)
    member_repo = TenantMemberRepository(db)

    tenant = await tenant_repo.get_by_id(tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    return await member_repo.get_by_tenant(tenant_id)


@router.get("/tenants/{tenant_id}/members/{member_id}", response_model=TenantMemberResponse)
async def get_tenant_member(
    tenant_id: UUID,
    member_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    member_repo = TenantMemberRepository(db)
    member = await member_repo.get_by_id(member_id)
    if not member or member.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )
    return member


@router.patch("/tenants/{tenant_id}/members/{member_id}", response_model=TenantMemberResponse)
async def update_tenant_member(
    tenant_id: UUID,
    member_id: UUID,
    member_data: TenantMemberUpdate,
    db: AsyncSession = Depends(get_db),
):
    member_repo = TenantMemberRepository(db)
    member = await member_repo.get_by_id(member_id)
    if not member or member.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )

    if member_data.role is not None:
        member.role = member_data.role

    return await member_repo.update(member)


@router.delete(
    "/tenants/{tenant_id}/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_tenant_member(
    tenant_id: UUID,
    member_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    member_repo = TenantMemberRepository(db)
    member = await member_repo.get_by_id(member_id)
    if not member or member.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )
    await member_repo.delete(member)


# Plan routes
@router.post("/plans", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
async def create_plan(
    plan_data: PlanCreate,
    db: AsyncSession = Depends(get_db),
):
    plan_repo = PlanRepository(db)

    existing = await plan_repo.get_by_name(plan_data.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Plan with this name already exists",
        )

    from models.billing import Plan
    plan = Plan(**plan_data.model_dump())
    return await plan_repo.create(plan)


@router.get("/plans", response_model=list[PlanResponse])
async def list_plans(
    active_only: bool = Query(default=False),
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    plan_repo = PlanRepository(db)
    return await plan_repo.get_all(active_only=active_only, limit=limit, offset=offset)


@router.get("/plans/active", response_model=list[PlanResponse])
async def list_active_plans(
    db: AsyncSession = Depends(get_db),
):
    plan_repo = PlanRepository(db)
    return await plan_repo.get_active_plans()


@router.get("/plans/{plan_id}", response_model=PlanResponse)
async def get_plan(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    plan_repo = PlanRepository(db)
    plan = await plan_repo.get_by_id(plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )
    return plan


@router.get("/plans/name/{name}", response_model=PlanResponse)
async def get_plan_by_name(
    name: PlanName,
    db: AsyncSession = Depends(get_db),
):
    plan_repo = PlanRepository(db)
    plan = await plan_repo.get_by_name(name)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )
    return plan


@router.patch("/plans/{plan_id}", response_model=PlanResponse)
async def update_plan(
    plan_id: UUID,
    plan_data: PlanUpdate,
    db: AsyncSession = Depends(get_db),
):
    plan_repo = PlanRepository(db)
    plan = await plan_repo.get_by_id(plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )

    update_data = plan_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(plan, field, value)

    return await plan_repo.update(plan)


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    plan_repo = PlanRepository(db)
    plan = await plan_repo.get_by_id(plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )
    await plan_repo.delete(plan)


# Subscription routes
@router.post(
    "/subscriptions",
    response_model=SubscriptionWithRelations,
    status_code=status.HTTP_201_CREATED,
)
async def create_subscription(
    subscription_data: SubscriptionCreate,
    db: AsyncSession = Depends(get_db),
):
    tenant_repo = TenantRepository(db)
    plan_repo = PlanRepository(db)
    sub_repo = SubscriptionRepository(db)

    tenant = await tenant_repo.get_by_id(subscription_data.tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    plan = await plan_repo.get_by_id(subscription_data.plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )

    existing = await sub_repo.get_by_tenant(subscription_data.tenant_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tenant already has a subscription",
        )

    from models.billing import Subscription
    subscription = Subscription(**subscription_data.model_dump())
    await sub_repo.create(subscription)

    return await sub_repo.get_by_tenant_with_plan(subscription_data.tenant_id)


@router.get("/subscriptions", response_model=list[SubscriptionWithRelations])
async def list_subscriptions(
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    sub_repo = SubscriptionRepository(db)
    return await sub_repo.get_all(limit=limit, offset=offset)


@router.get("/subscriptions/{subscription_id}", response_model=SubscriptionWithRelations)
async def get_subscription(
    subscription_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    sub_repo = SubscriptionRepository(db)
    subscription = await sub_repo.get_by_id(subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )

    return await sub_repo.get_by_tenant_with_plan(subscription.tenant_id)


@router.get("/tenants/{tenant_id}/subscription", response_model=SubscriptionWithRelations)
async def get_tenant_subscription(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    tenant_repo = TenantRepository(db)
    sub_repo = SubscriptionRepository(db)

    tenant = await tenant_repo.get_by_id(tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    subscription = await sub_repo.get_by_tenant_with_plan(tenant_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found for this tenant",
        )
    return subscription


@router.patch("/subscriptions/{subscription_id}", response_model=SubscriptionWithRelations)
async def update_subscription(
    subscription_id: UUID,
    subscription_data: SubscriptionUpdate,
    db: AsyncSession = Depends(get_db),
):
    sub_repo = SubscriptionRepository(db)
    subscription = await sub_repo.get_by_id(subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )

    update_data = subscription_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(subscription, field, value)

    updated = await sub_repo.update(subscription)
    return await sub_repo.get_by_tenant_with_plan(updated.tenant_id)


@router.delete("/subscriptions/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(
    subscription_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    sub_repo = SubscriptionRepository(db)
    subscription = await sub_repo.get_by_id(subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )
    await sub_repo.delete(subscription)
