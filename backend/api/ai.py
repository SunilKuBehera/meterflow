"""AI generation HTTP routes.

The route handlers are intentionally thin: they translate HTTP into a call to
:class:`services.ai.AIGenerationService` and let the application-wide
exception handlers translate domain errors into structured HTTP responses.

No provider call, quota arithmetic, pricing, or ledger write happens here —
all of that lives in the service layer.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from integrations.ai.factory import describe_provider
from schemas.ai import AIGenerateRequest, AIGenerateResponse
from services.ai import AIGenerationService

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/generate", response_model=AIGenerateResponse, status_code=status.HTTP_201_CREATED)
async def generate(
    request: AIGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Run one metered AI generation for the requested tenant.

    Idempotency: send the same ``idempotency_key`` with the same body to
    replay the original result without a second provider call or a second
    usage-ledger entry. The same key with a different body returns ``409``.
    """
    service = AIGenerationService(db)
    result = await service.generate(
        tenant_id=request.tenant_id,
        idempotency_key=request.idempotency_key,
        prompt=request.prompt,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
    )

    return AIGenerateResponse(
        content=result.content,
        model=result.model,
        provider=result.provider,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        cached_prompt_tokens=result.cached_prompt_tokens,
        reasoning_tokens=result.reasoning_tokens,
        total_cost_paise=result.total_cost_paise,
        usage_source=result.usage_source,
        request_id=result.request_id,
        finish_reason=result.finish_reason,
        replayed=result.replayed,
        quota_exceeded=result.quota_exceeded,
    )


@router.get("/status")
async def ai_status() -> dict:
    """Report the configured AI provider and whether it is usable.

    Never raises: an unavailable provider is reported as ``available: false``
    with a human-readable ``detail`` so the frontend can show a
    provider-down state instead of a generic error.
    """
    return describe_provider()
