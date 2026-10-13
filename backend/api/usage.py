from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from repositories.billing import TenantRepository
from schemas.billing import UsageRecord
from services.usage import QuotaExceededError, UsageService

router = APIRouter(prefix="/usage", tags=["usage"])


@router.post("/", response_model=UsageRecord, status_code=status.HTTP_201_CREATED)
async def record_usage(
    usage_data: UsageRecord,
    db: AsyncSession = Depends(get_db),
):
    """Record usage metrics for a tenant with idempotency and quota enforcement."""
    tenant_repo = TenantRepository(db)
    tenant = await tenant_repo.get_by_id(usage_data.tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    usage_service = UsageService(db)
    try:
        usage_event = await usage_service.record_usage(
            tenant_id=usage_data.tenant_id,
            idempotency_key=usage_data.idempotency_key,
            api_calls=usage_data.api_calls,
            ai_input_tokens=usage_data.ai_input_tokens,
            ai_cached_input_tokens=usage_data.ai_cached_input_tokens,
            ai_output_tokens=usage_data.ai_output_tokens,
            ai_reasoning_tokens=usage_data.ai_reasoning_tokens,
        )
    except QuotaExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "QUOTA_EXCEEDED",
                "message": str(e),
                "api_calls_used": e.result.api_calls_used,
                "api_calls_limit": e.result.api_calls_limit,
                "ai_tokens_used": e.result.ai_tokens_used,
                "ai_tokens_limit": e.result.ai_tokens_limit,
                "api_calls_remaining": e.result.api_calls_remaining,
                "ai_tokens_remaining": e.result.ai_tokens_remaining,
            },
        ) from None
    return usage_event


@router.get("/{tenant_id}", response_model=list[UsageRecord])
async def get_usage(
    tenant_id: UUID,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """Get usage metrics for a tenant."""
    tenant_repo = TenantRepository(db)
    tenant = await tenant_repo.get_by_id(tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    usage_service = UsageService(db)
    usage_events = await usage_service.get_usage_by_tenant(
        tenant_id, limit=limit, offset=offset
    )
    return usage_events
