"""Pydantic schemas for AI generation."""

from uuid import UUID

from pydantic import BaseModel, Field


class AIGenerateRequest(BaseModel):
    """Request to trigger a deterministic AI generation."""

    tenant_id: UUID
    prompt: str = Field(..., min_length=1, max_length=8000)
    idempotency_key: str = Field(..., min_length=1, max_length=255)
    max_tokens: int | None = Field(None, ge=1, le=4096)
    temperature: float = Field(0.7, ge=0.0, le=2.0)


class AIGenerateResponse(BaseModel):
    """Response from an AI generation, including metering metadata."""

    content: str
    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    cached_prompt_tokens: int
    reasoning_tokens: int
    total_cost_paise: int
    usage_source: str
    request_id: UUID
    finish_reason: str
    replayed: bool = False
    quota_exceeded: bool = False
