from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.billing import (
    AIRequestStatus,
    Plan,
    PlanName,
    SubscriptionStatus,
    UsageEvent,
)
from repositories.billing import PlanRepository, SubscriptionRepository, TenantRepository
from services.billing_period import get_billing_period_bounds


@dataclass
class QuotaCheckResult:
    allowed: bool
    api_calls_used: int
    api_calls_limit: int
    ai_tokens_used: int
    ai_tokens_limit: int
    api_calls_remaining: int
    ai_tokens_remaining: int
    ai_tokens_reserved: int = 0  # outstanding reservations counted as used AI tokens
    error_message: str | None = None


class QuotaExceededError(Exception):
    """Raised when quota is exceeded."""

    def __init__(self, result: QuotaCheckResult):
        self.result = result
        super().__init__(result.error_message or "Quota exceeded")


class QuotaService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.tenant_repo = TenantRepository(session)
        self.subscription_repo = SubscriptionRepository(session)
        self.plan_repo = PlanRepository(session)

    # -- helpers ---------------------------------------------------------------

    async def get_effective_plan(self, tenant_id: UUID):
        """Return the :class:`Plan` to use for a tenant.

        Resolved policy:
        - If the subscription has an active plan, use it.
        - Otherwise fall back to the FREE plan (explicit).

        Returns ``None`` if no plan exists at all so callers can handle the no-plan case.
        """
        subscription = await self.subscription_repo.get_by_tenant_with_plan(tenant_id)
        if subscription and subscription.status == SubscriptionStatus.ACTIVE and subscription.plan:
            return subscription.plan

        free_plan = await self.plan_repo.get_by_name(PlanName.FREE)
        if free_plan is None:
            return None
        return free_plan

    async def _get_reserved_ai_tokens(
        self, tenant_id: UUID, period_start: datetime, period_end: datetime
    ) -> int:
        """Sum of ``AIRequest.reserved_tokens`` for PENDING requests in this period."""
        result = await self.session.execute(
            select(func.coalesce(func.sum(AIRequest.reserved_tokens), 0)).where(
                AIRequest.tenant_id == tenant_id,
                AIRequest.status == AIRequestStatus.PENDING,
                AIRequest.created_at >= period_start,
                AIRequest.created_at < period_end,
            )
        )
        return result.scalar() or 0

    async def _get_api_calls_used(
        self, tenant_id: UUID, period_start: datetime, period_end: datetime
    ) -> int:
        """Get total API calls used in the current billing period."""
        result = await self.session.execute(
            select(func.coalesce(func.sum(UsageEvent.api_calls), 0)).where(
                UsageEvent.tenant_id == tenant_id,
                UsageEvent.timestamp >= period_start,
                UsageEvent.timestamp < period_end,
            )
        )
        return result.scalar() or 0

    async def _get_ai_tokens_used(
        self, tenant_id: UUID, period_start: datetime, period_end: datetime
    ) -> int:
        """Get total AI tokens used in the current billing period."""
        result = await self.session.execute(
            select(
                func.coalesce(func.sum(UsageEvent.ai_input_tokens), 0)
                + func.coalesce(func.sum(UsageEvent.ai_cached_input_tokens), 0)
                + func.coalesce(func.sum(UsageEvent.ai_output_tokens), 0)
                + func.coalesce(func.sum(UsageEvent.ai_reasoning_tokens), 0)
            ).where(
                UsageEvent.tenant_id == tenant_id,
                UsageEvent.timestamp >= period_start,
                UsageEvent.timestamp < period_end,
            )
        )
        return result.scalar() or 0

    async def _build_check_params(
        self,
        tenant_id: UUID,
        period_start: datetime,
        period_end: datetime,
        *,
        plan: Plan | None = None,
    ):
        """Convenience wrapper around budget math returning (used, limit, remaining, reserved)."""
        api_calls_limit = plan.api_calls_limit if plan else 1000
        ai_tokens_limit = plan.ai_tokens_limit if plan else 100000

        api_calls_used = await self._get_api_calls_used(tenant_id, period_start, period_end)
        ai_tokens_used = await self._get_ai_tokens_used(tenant_id, period_start, period_end)
        reserved = await self._get_reserved_ai_tokens(tenant_id, period_start, period_end)

        api_calls_remaining = max(0, api_calls_limit - api_calls_used)
        ai_tokens_remaining = max(0, ai_tokens_limit - (ai_tokens_used + reserved))

        return api_calls_used, ai_tokens_used, api_calls_remaining, ai_tokens_remaining, reserved

    # -- public API ------------------------------------------------------------

    async def check_quota(
        self,
        tenant_id: UUID,
        api_calls: int = 0,
        ai_input_tokens: int = 0,
        ai_cached_input_tokens: int = 0,
        ai_output_tokens: int = 0,
        ai_reasoning_tokens: int = 0,
    ) -> QuotaCheckResult:
        """Check if the tenant has enough quota for the requested usage."""
        # Get tenant with subscription and plan
        tenant = await self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            return QuotaCheckResult(
                allowed=False,
                api_calls_used=0,
                api_calls_limit=0,
                ai_tokens_used=0,
                ai_tokens_limit=0,
                api_calls_remaining=0,
                ai_tokens_remaining=0,
                error_message="Tenant not found",
            )

        # Resolve effective plan; fall back to FREE plan when missing.
        plan = await self.get_effective_plan(tenant_id)
        if plan is None:
            return QuotaCheckResult(
                allowed=False,
                api_calls_used=0,
                api_calls_limit=0,
                ai_tokens_used=0,
                ai_tokens_limit=0,
                api_calls_remaining=0,
                ai_tokens_remaining=0,
                error_message="No plan configured",
            )

        period_start, period_end = get_billing_period_bounds()

        api_calls_used, ai_tokens_used, api_calls_remaining, ai_tokens_remaining, reserved = (
            self._build_check_params(tenant_id, period_start, period_end, plan=plan)
        )

        api_calls_limit = plan.api_calls_limit
        ai_tokens_limit = plan.ai_tokens_limit

        requested_ai_tokens = (
            ai_input_tokens + ai_cached_input_tokens + ai_output_tokens + ai_reasoning_tokens
        )

        # Check if request would exceed limits
        if api_calls_used + api_calls > api_calls_limit:
            return QuotaCheckResult(
                allowed=False,
                api_calls_used=api_calls_used,
                api_calls_limit=api_calls_limit,
                ai_tokens_used=ai_tokens_used,
                ai_tokens_limit=ai_tokens_limit,
                api_calls_remaining=api_calls_remaining,
                ai_tokens_remaining=ai_tokens_remaining,
                ai_tokens_reserved=reserved,
                error_message=(
                    f"API calls quota exceeded. Used: {api_calls_used}, Limit: {api_calls_limit}, "
                    f"Requested: {api_calls}"
                ),
            )

        if ai_tokens_used + requested_ai_tokens + reserved > ai_tokens_limit:
            return QuotaCheckResult(
                allowed=False,
                api_calls_used=api_calls_used,
                api_calls_limit=api_calls_limit,
                ai_tokens_used=ai_tokens_used,
                ai_tokens_limit=ai_tokens_limit,
                api_calls_remaining=api_calls_remaining,
                ai_tokens_remaining=ai_tokens_remaining,
                ai_tokens_reserved=reserved,
                error_message=(
                    f"AI tokens quota exceeded. Used: {ai_tokens_used + reserved}, "
                    f"Limit: {ai_tokens_limit}, Requested: {requested_ai_tokens}"
                ),
            )

        return QuotaCheckResult(
            allowed=True,
            api_calls_used=api_calls_used,
            api_calls_limit=api_calls_limit,
            ai_tokens_used=ai_tokens_used,
            ai_tokens_limit=ai_tokens_limit,
            api_calls_remaining=api_calls_remaining - api_calls,
            ai_tokens_remaining=ai_tokens_remaining - requested_ai_tokens,
            ai_tokens_reserved=reserved,
        )

    async def consume_quota(
        self,
        tenant_id: UUID,
        api_calls: int = 0,
        ai_input_tokens: int = 0,
        ai_cached_input_tokens: int = 0,
        ai_output_tokens: int = 0,
        ai_reasoning_tokens: int = 0,
    ) -> QuotaCheckResult:
        """Atomically check and consume quota within a transaction.

        Uses ``SELECT ... FOR UPDATE`` on the subscription row to prevent race
        conditions when multiple concurrent requests try to consume the last
        quota unit. Outstanding pending AI reservations are counted as already-
        used AI tokens so two concurrent reservations cannot both pass the
        boundary check.

        Raises ``QuotaExceededError`` if quota would be exceeded.
        """
        from models.billing import Subscription  # local import keeps module footprint small

        # Get tenant with subscription and plan
        tenant = await self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise QuotaExceededError(
                QuotaCheckResult(
                    allowed=False,
                    api_calls_used=0,
                    api_calls_limit=0,
                    ai_tokens_used=0,
                    ai_tokens_limit=0,
                    api_calls_remaining=0,
                    ai_tokens_remaining=0,
                    error_message="Tenant not found",
                )
            )

        # Lock the subscription row for this tenant to prevent concurrent modifications
        result = await self.session.execute(
            select(Subscription).where(Subscription.tenant_id == tenant_id).with_for_update()
        )
        subscription = result.scalar_one_or_none()

        # Determine the plan to use
        if subscription and subscription.plan:
            plan = subscription.plan
        else:
            free_plan = await self.plan_repo.get_by_name(PlanName.FREE)
            if not free_plan:
                raise QuotaExceededError(
                    QuotaCheckResult(
                        allowed=False,
                        api_calls_used=0,
                        api_calls_limit=0,
                        ai_tokens_used=0,
                        ai_tokens_limit=0,
                        api_calls_remaining=0,
                        ai_tokens_remaining=0,
                        error_message="No plan configured",
                    )
                )
            plan = free_plan

        # Check if subscription is active
        if subscription and subscription.status != SubscriptionStatus.ACTIVE:
            # For non-active subscriptions, use FREE plan limits
            free_plan = await self.plan_repo.get_by_name(PlanName.FREE)
            if free_plan:
                plan = free_plan

        # Get current billing period bounds
        period_start, period_end = get_billing_period_bounds()

        # Calculate current usage in this billing period including reservations
        api_calls_used = await self._get_api_calls_used(tenant_id, period_start, period_end)
        ai_tokens_used = await self._get_ai_tokens_used(tenant_id, period_start, period_end)
        reserved = await self._get_reserved_ai_tokens(tenant_id, period_start, period_end)

        requested_ai_tokens = (
            ai_input_tokens + ai_cached_input_tokens + ai_output_tokens + ai_reasoning_tokens
        )

        api_calls_limit = plan.api_calls_limit
        ai_tokens_limit = plan.ai_tokens_limit

        # Effective AI usage includes reservations so two concurrent requests
        # cannot both see the available quota and neither fail correctly.
        effective_ai_tokens_used = ai_tokens_used + reserved
        api_calls_remaining = max(0, api_calls_limit - api_calls_used)
        ai_tokens_remaining = max(0, ai_tokens_limit - effective_ai_tokens_used)

        # Check if request would exceed limits
        if api_calls_used + api_calls > api_calls_limit:
            raise QuotaExceededError(
                QuotaCheckResult(
                    allowed=False,
                    api_calls_used=api_calls_used,
                    api_calls_limit=api_calls_limit,
                    ai_tokens_used=ai_tokens_used,
                    ai_tokens_limit=ai_tokens_limit,
                    api_calls_remaining=api_calls_remaining,
                    ai_tokens_remaining=ai_tokens_remaining,
                    ai_tokens_reserved=reserved,
                    error_message=(
                        f"API calls quota exceeded. Used: {api_calls_used}, Limit: {api_calls_limit}, "
                        f"Requested: {api_calls}"
                    ),
                )
            )

        if effective_ai_tokens_used + requested_ai_tokens > ai_tokens_limit:
            raise QuotaExceededError(
                QuotaCheckResult(
                    allowed=False,
                    api_calls_used=api_calls_used,
                    api_calls_limit=api_calls_limit,
                    ai_tokens_used=ai_tokens_used,
                    ai_tokens_limit=ai_tokens_limit,
                    api_calls_remaining=api_calls_remaining,
                    ai_tokens_remaining=ai_tokens_remaining,
                    ai_tokens_reserved=reserved,
                    error_message=(
                        f"AI tokens quota exceeded. Used: {effective_ai_tokens_used}, "
                        f"Limit: {ai_tokens_limit}, Requested: {requested_ai_tokens}"
                    ),
                )
            )

        return QuotaCheckResult(
            allowed=True,
            api_calls_used=api_calls_used,
            api_calls_limit=api_calls_limit,
            ai_tokens_used=ai_tokens_used,
            ai_tokens_limit=ai_tokens_limit,
            api_calls_remaining=api_calls_remaining - api_calls,
            ai_tokens_remaining=ai_tokens_remaining - requested_ai_tokens,
            ai_tokens_reserved=reserved,
        )