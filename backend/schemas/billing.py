from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from models.billing import PlanName, SubscriptionStatus, TenantRole


class TenantBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not v.replace("-", "").isalnum():
            raise ValueError("Slug must contain only lowercase letters, numbers, and hyphens")
        if v.startswith("-") or v.endswith("-"):
            raise ValueError("Slug cannot start or end with hyphen")
        return v.lower()


class TenantCreate(TenantBase):
    pass


class TenantUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)


class TenantResponse(TenantBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TenantMemberBase(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=255)
    role: TenantRole = TenantRole.MEMBER


class TenantMemberCreate(TenantMemberBase):
    pass


class TenantMemberUpdate(BaseModel):
    role: TenantRole | None = None


class TenantMemberResponse(TenantMemberBase):
    id: UUID
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PlanBase(BaseModel):
    name: PlanName
    display_name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    price_paise: int = Field(..., ge=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    billing_period: str = Field(default="monthly", pattern=r"^(monthly|yearly)$")
    api_calls_limit: int = Field(..., ge=0)
    ai_tokens_limit: int = Field(..., ge=0)
    api_call_price_paise: int = Field(default=0, ge=0)
    ai_input_token_price_paise: int = Field(default=0, ge=0)
    ai_cached_input_token_price_paise: int = Field(default=0, ge=0)
    ai_output_token_price_paise: int = Field(default=0, ge=0)
    ai_reasoning_token_price_paise: int = Field(default=0, ge=0)
    is_active: bool = True
    razorpay_plan_id: str | None = Field(None, max_length=100)


class PlanCreate(PlanBase):
    pass


class PlanUpdate(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    price_paise: int | None = Field(None, ge=0)
    currency: str | None = Field(None, min_length=3, max_length=3)
    billing_period: str | None = Field(None, pattern=r"^(monthly|yearly)$")
    api_calls_limit: int | None = Field(None, ge=0)
    ai_tokens_limit: int | None = Field(None, ge=0)
    api_call_price_paise: int | None = Field(None, ge=0)
    ai_input_token_price_paise: int | None = Field(None, ge=0)
    ai_cached_input_token_price_paise: int | None = Field(None, ge=0)
    ai_output_token_price_paise: int | None = Field(None, ge=0)
    ai_reasoning_token_price_paise: int | None = Field(None, ge=0)
    is_active: bool | None = None
    razorpay_plan_id: str | None = Field(None, max_length=100)


class PlanResponse(PlanBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SubscriptionBase(BaseModel):
    tenant_id: UUID
    plan_id: UUID
    status: SubscriptionStatus = SubscriptionStatus.INCOMPLETE
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool = False
    canceled_at: datetime | None = None
    razorpay_subscription_id: str | None = Field(None, max_length=100)
    razorpay_customer_id: str | None = Field(None, max_length=100)


class SubscriptionCreate(SubscriptionBase):
    pass


class SubscriptionUpdate(BaseModel):
    plan_id: UUID | None = None
    status: SubscriptionStatus | None = None
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool | None = None
    canceled_at: datetime | None = None
    razorpay_subscription_id: str | None = Field(None, max_length=100)
    razorpay_customer_id: str | None = Field(None, max_length=100)


class SubscriptionResponse(SubscriptionBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SubscriptionWithRelations(SubscriptionResponse):
    plan: PlanResponse | None = None
    tenant: TenantResponse | None = None

    class Config:
        from_attributes = True


class UsageRecord(BaseModel):
    id: UUID | None = None
    tenant_id: UUID
    idempotency_key: str = Field(..., max_length=255)
    api_calls: int = Field(default=0, ge=0)
    ai_input_tokens: int = Field(default=0, ge=0)
    ai_cached_input_tokens: int = Field(default=0, ge=0)
    ai_output_tokens: int = Field(default=0, ge=0)
    ai_reasoning_tokens: int = Field(default=0, ge=0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True
