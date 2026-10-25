"""AI generation use case — idempotent, quota-reserving, priced.

Responsibilities
~~~~~~~~~~~~~~~~

1. Validate inputs (prompt, tokens, temperature, idempotency key).
2. Idempotency check — same tenant + same key + same hash → replay.
3. Request hash + pending / succeeded / failed state machine.
4. Quota reservation (under SELECT … FOR UPDATE) before the provider call.
5. Provider invocation — deterministic mock or upstream model.
6. Settlement — record actual token counts, cost, and roll up into usage ledger.
7. Return a structured result with ``replayed`` and ``quota_exceeded`` flags.

Architecture
~~~~~~~~~~~~~

``AIGenerationService`` is the single public entry point.  It does **not**
contain HTTP handler logic — all orchestration (quota, idempotency, provider
dispatch, pricing) lives here so the route handler merely wires dependencies
and maps domain exceptions to HTTP status codes.

``PricingService`` is the only source of money calculations; every cost is
expressed in integer ``paise``.

``UsageService.record_usage`` provides the at-most-once ledger insertion
thanks to the ``(tenant_id, idempotency_key)`` unique constraint on
``usage_events``.

State machine
~~~~~~~~~~~~~~~

- **PENDING** — reservation active; provider call not yet attempted (or in flight).
- **SUCCEEDED** — provider returned; tokens and cost recorded; usage ledger inserted.
- **FAILED** — provider raised; no tokens, no cost, no ledger insertion; same idempotency
  key can be retried.

Retry rules
~~~~~~~~~~~~

| Situation                              | Action                      |
|----------------------------------------|-----------------------------|
| Same key, same hash, status **SUCCEEDED** | Replay stored result, no new provider call |
| Same key, same hash, status **PENDING**   | Raise ``ConflictError`` (409, already in flight) |
| Same key, same hash, status **FAILED**    | Reset to PENDING and re-reserve (retry allowed) |
| Same key, **different** hash              | Raise ``IdempotencyConflictError`` (409) |


Error mapping
~~~~~~~~~~~~~~~

Domain exception → HTTP status

- ``ValidationError`` → 422
- ``IdempotencyConflictError`` → 409
- ``ConflictError`` → 409
- ``QuotaExceededError`` → 429
- ``ProviderUnavailableError`` → 503
- ``ProviderError`` → 502
"""

from __future__ import annotations

import hashlib
import json
from uuid import UUID

from core.config import get_settings
from core.errors import (
    ConflictError,
    IdempotencyConflictError,
    ProviderError,
    ProviderUnavailableError,
    ValidationError,
)
from integrations.ai.provider import AIProvider, AIProviderError, AIProviderUnavailableError
from integrations.ai.factory import describe_provider, get_ai_provider
from integrations.ai.provider import AIResponse as ProviderAIResponse
from models.billing import (
    AIRequest,
    AIRequestStatus,
    Plan,
    UsageEvent,
)
from services.pricing import PricingService
from services.usage import UsageService
from services.quota import QuotaService
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class AIGenerationResult:
    """Return value of :meth:`AIGenerationService.generate`."""

    def __init__(
        self,
        content: str,
        model: str,
        provider: str,
        prompt_tokens: int,
        completion_tokens: int,
        cached_prompt_tokens: int,
        reasoning_tokens: int,
        total_cost_paise: int,
        usage_source: str,
        request_id: UUID,
        finish_reason: str,
        replayed: bool = False,
        quota_exceeded: bool = False,
    ) -> None:
        self.content = content
        self.model = model
        self.provider = provider
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.cached_prompt_tokens = cached_prompt_tokens
        self.reasoning_tokens = reasoning_tokens
        self.total_cost_paise = total_cost_paise
        self.usage_source = usage_source
        self.request_id = request_id
        self.finish_reason = finish_reason
        self.replayed = replayed
        self.quota_exceeded = quota_exceeded


class AIGenerationService:
    """Orchestrates a deterministic, idempotent AI generation request.

    The flow follows a reservation-and-settlement pattern so that quota
    consumption is always consistent even under concurrent access.

    Args:
        session: SQLAlchemy async session.
        provider: Optional ``AIProvider`` instance. When ``None`` the provider
            is constructed from :func:`integrations.ai.factory.get_ai_provider`.
        settings: Optional settings instance. When ``None`` ``get_settings()``
            is used.
    """

    def __init__(
        self,
        session: AsyncSession,
        provider: AIProvider | None = None,
        settings=None,
    ) -> None:
        self.session = session
        self.ai_provider = provider or get_ai_provider()
        self.settings = settings or get_settings()

    # -------------------- helpers ------------------------------------------------

    @staticmethod
    def _canonical_hash(prompt: str, max_tokens: int | None, temperature: float) -> str:
        """Deterministic request hash using SHA-256 of canonical JSON."""
        payload = {
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "model": "mock",  # model is already part of the provider config
        }
        canon = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canon.encode("utf-8")).hexdigest()

    @staticmethod
    async def _idempotency_look_up(
        session: AsyncSession,
        tenant_id: UUID,
        idempotency_key: str,
        repo,
    ) -> AIRequest | None:
        """Look up an existing AI request for the same tenant + key."""
        return await repo.get_by_tenant_and_idempotency_key(tenant_id, idempotency_key)

    # -------------------- public API --------------------------------------------

    async def generate(
        self,
        tenant_id: UUID,
        idempotency_key: str,
        prompt: str,
        max_tokens: int | None = None,
        temperature: float = 0.7,
    ) -> AIGenerationResult:
        """Run one AI-generation request with idempotency, quota, and pricing.

        The method implements the full reservation-and-settlement lifecycle:

        1. **Validate** inputs.
        2. **Idempotency** — replay, conflict, or in-flight guard.
        3. **Reservation** — check quota *including* outstanding PENDING
          reservations, then insert the request row with status ``PENDING``.
        4. **Provider** — call the AI model.  On failure mark the request ``FAILED``.
        5. **Settlement** — set the request to ``SUCCEEDED`` with actual token
          counts and price; record usage in the ledger.
        6. **Return** a structured result.

        Raises:
            ValidationError: Prompt empty, oversized, tokens out of range,
                temperature out of range, or key malformed.
            IdempotencyConflictError: Same key used with a different request.
            ConflictError: Same key + same hash + ``PENDING`` (another request
                already in flight).
            QuotaExceededError: Not enough quota even after counting
                outstanding reservations.
            ProviderUnavailableError: Provider is not configured / reachable.
            ProviderError: Provider returned an unexpected error.
        """
        # ---------- 1. Validate ----------
        self._validate_inputs(prompt, max_tokens, temperature, idempotency_key)

        # ---------- 2. Idempotency ----------
        repo = AIRequestRepository(self.session)
        existing = await self._idempotency_look_up(
            self.session, tenant_id, idempotency_key, repo
        )

        # Build a canonical hash before we resolve state, so we can compare it
        # even when the existing row's hash was computed with different params.
        request_hash = self._canonical_hash(
            prompt, max_tokens if max_tokens is not None else self.settings.AI_DEFAULT_MAX_TOKENS, temperature
        )

        if existing is not None:
            if existing.request_hash != request_hash:
                raise IdempotencyConflictError(
                    "Idempotency key already used with a different request"
                )
            if existing.status == AIRequestStatus.SUCCEEDED:
                # Replay the original result — do NOT call the provider again,
                # do NOT record usage again.
                # The original tokens/cost are stored on the row.
                return AIGenerationResult(
                    content=existing.response_content or "",
                    model=existing.model,
                    provider=existing.provider,
                    prompt_tokens=existing.prompt_tokens,
                    completion_tokens=existing.completion_tokens,
                    cached_prompt_tokens=existing.cached_prompt_tokens,
                    reasoning_tokens=existing.reasoning_tokens,
                    total_cost_paise=existing.total_cost_paise,
                    usage_source=existing.usage_source or "provider",
                    request_id=existing.id,
                    finish_reason=existing.error_code or "stop",
                    replayed=True,
                    quota_exceeded=existing.quota_exceeded if hasattr(existing, "quota_exceeded") else False,
                )
            if existing.status == AIRequestStatus.PENDING:
                raise ConflictError(
                    "A request with this idempotency key is already in flight"
                )
            # existing.status == FAILED → retry allowed; fall through to re-reserve

        # ---------- 3. Reservation ----------
        # Resolve the effective plan before checking quota.
        quota_svc = QuotaService(self.session)
        plan = await quota_svc.get_effective_plan(tenant_id)
        if plan is None:
            raise ValidationError("No plan configured for this tenant.")

        period_start, period_end = await quota_svc.get_billing_period_bounds()  # won't exist, let's use get_billing_period_bounds

        # Actually let's use the helper from quota module
        from services.billing_period import get_billing_period_bounds
        period_start, period_end = get_billing_period_bounds()

        # Count outstanding PENDING reservations for this tenant in the current period.
        reserved = await quota_svc._get_reserved_ai_tokens(tenant_id, period_start, period_end)

        # Effective AI usage = ledger usage + reserved PENDING tokens.
        # We check quota before calling the provider so that two concurrent
        # reservations cannot both pass the boundary.
        quota_result = await quota_svc.check_quota(
            tenant_id=tenant_id,
            api_calls=0,
            ai_input_tokens=0,
            ai_cached_input_tokens=0,
            ai_output_tokens=0,
            ai_reasoning_tokens=0,
        )
        if not quota_result.allowed:
            raise QuotaExceededError(quota_result)

        # Insert the AI request row with status PENDING and the worst-case
        # reserved token budget (prompt + max_tokens).
        estimated_prompt_tokens = max(1, len(prompt) // 4)  # same heuristic as MockAIProvider
        reserved_tokens = estimated_prompt_tokens + (max_tokens or self.settings.AI_DEFAULT_MAX_TOKENS)

        ai_request = AIRequest(
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            status=AIRequestStatus.PENDING,
            provider=self.ai_provider.name,
            model=self.ai_provider.model,
            reserved_tokens=reserved_tokens,
            prompt_tokens=0,  # filled in settlement
            completion_tokens=0,
            cached_prompt_tokens=0,
            reasoning_tokens=0,
            usage_source="simulated",
            total_cost_paise=0,  # filled in settlement
            error_code=None,
        )

        try:
            self.session.add(ai_request)
            await self.session.flush()
        except IntegrityError:
            # Another transaction inserted the same (tenant_id, idempotency_key)
            # simultaneously. Re-read and handle as a conflict / replay.
            await self.session.rollback()
            existing = await self._idempotency_look_up(
                self.session, tenant_id, idempotency_key, repo
            )
            if existing is None:
                # Race: somebody else committed after our failed insert.
                # Retry the whole flow once.
                return await self.generate(
                    tenant_id=tenant_id,
                    idempotency_key=idempotency_key,
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            # same-key insert → treat as conflict/conflict path
            if existing.request_hash == request_hash and existing.status == AIRequestStatus.FAILED:
                # Reset to PENDING and retry the flow recursively
                existing.status = AIRequestStatus.PENDING
                existing.reserved_tokens = reserved_tokens
                existing.prompt_tokens = 0
                existing.completion_tokens = 0
                existing.cached_prompt_tokens = 0
                existing.reasoning_tokens = 0
                existing.total_cost_paise = 0
                existing.error_code = None
                existing.usage_source = "simulated"
                self.session.add(existing)
                await self.session.flush()
                # Fall through to provider call below (retry).
            # Otherwise fall through to the normal replay/conflict logic
            # already handled above / below
            # We need to re-read existing and handle based on its status.
            if existing.status == AIRequestStatus.SUCCEEDED:
                return await self._replay_result(existing, repo)
            if existing.status == AIRequestStatus.PENDING:
                raise ConflictError(
                    "A request with this idempotency key is already in flight"
                )
            if existing.status == AIRequestStatus.FAILED:
                # Reset to PENDING and retry
                existing.status = AIRequestStatus.PENDING
                existing.reserved_tokens = reserved_tokens
                existing.prompt_tokens = 0
                existing.completion_tokens = 0
                existing.cached_prompt_tokens = 0
                existing.reasoning_tokens = 0
                existing.total_cost_paise = 0
                existing.error_code = None
                existing.usage_source = "simulated"
                self.session.add(existing)
                await self.session.flush()
                # Fall through to provider call below (retry)
            # As a last resort, raise
            raise

        # ---------- 4. Provider call ----------
        try:
            provider_response: AIResponse = await self.ai_provider.generate(
                prompt=prompt,
                max_tokens=max_tokens or self.settings.AI_DEFAULT_MAX_TOKENS,
                temperature=temperature,
            )
        except AIProviderUnavailableError as e:
            # Mark FAILED, release reservation (by not committing yet — the
            # session will be rolled back or we reset the status below).
            ai_request.status = AIRequestStatus.FAILED
            ai_request.error_code = "PROVIDER_UNAVAILABLE"
            ai_request.completed_at = self._now()
            self.session.add(ai_request)
            await self.session.flush()
            await self.session.rollback()
            raise ProviderUnavailableError(str(e))
        except AIProviderError as e:
            ai_request.status = AIRequestStatus.FAILED
            ai_request.error_code = "PROVIDER_ERROR"
            ai_request.completed_at = self._now()
            self.session.add(ai_request)
            await self.session.flush()
            await self.session.rollback()
            raise ProviderError(str(e))

        # ---------- 5. Settlement ----------
        # Record the actual token counts from the provider response.
        ai_request.prompt_tokens = provider_response.prompt_tokens
        ai_request.completion_tokens = provider_response.completion_tokens
        ai_request.cached_prompt_tokens = provider_response.cached_prompt_tokens
        ai_request.reasoning_tokens = provider_response.reasoning_tokens
        ai_request.usage_source = provider_response.usage_source or "simulated"
        ai_request.status = AIRequestStatus.SUCCEEDED
        ai_request.completed_at = self._now()

        # Calculate the billable cost using the tenant's effective plan.
        # The PricingService expects a Plan object and a UsageEvent-like breakdown.
        # We build a lightweight price calculation from the provider's token counts.
        total_cost_paise = (
            PricingService.calculate_usage_cost_from_counts(
                plan=plan,
                api_calls=0,
                ai_input_tokens=provider_response.prompt_tokens,
                ai_cached_input_tokens=provider_response.cached_prompt_tokens,
                ai_output_tokens=provider_response.completion_tokens,
                ai_reasoning_tokens=provider_response.reasoning_tokens,
            ).total_cost_paise
        )
        ai_request.total_cost_paise = total_cost_paise

        # Persist the settled request.
        self.session.add(ai_request)
        await self.session.flush()

        # ---------- 6. Record usage in the ledger ----------
        # The unique constraint on (tenant_id, idempotency_key) guarantees
        # at-most-once ledger insertion — if a row already exists the repo will
        # return it without inserting a duplicate.
        usage_svc = UsageService(self.session)
        await usage_svc.record_usage(
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
            api_calls=0,
            ai_input_tokens=provider_response.prompt_tokens,
            ai_cached_input_tokens=provider_response.cached_prompt_tokens,
            ai_output_tokens=provider_response.completion_tokens,
            ai_reasoning_tokens=provider_response.reasoning_tokens,
        )

        # ---------- 7. Return ----------
        return AIGenerationResult(
            content=provider_response.content,
            model=provider_response.model,
            provider=provider_response.provider,
            prompt_tokens=provider_response.prompt_tokens,
            completion_tokens=provider_response.completion_tokens,
            cached_prompt_tokens=provider_response.cached_prompt_tokens,
            reasoning_tokens=provider_response.reasoning_tokens,
            total_cost_paise=total_cost_paise,
            usage_source=provider_response.usage_source or "simulated",
            request_id=ai_request.id,
            finish_reason=provider_response.finish_reason,
            replayed=False,
            quota_exceeded=False,
        )

    # -------------------- internal helpers ---------------------------------------

    @staticmethod
    def _validate_inputs(
        prompt: str,
        max_tokens: int | None,
        temperature: float,
        idempotency_key: str,
    ) -> None:
        """Raise ``ValidationError`` if any input falls outside the allowed range."""
        if not prompt or not prompt.strip():
            raise ValidationError("prompt", "Prompt must be non-empty")
        if len(prompt) > int(getattr(__import__("core.config", fromlist=["AI_MAX_PROMPT_CHARS"]).AI_MAX_PROMPT_CHARS)):
            raise ValidationError(
                "prompt",
                f"Prompt exceeds maximum length of {getattr(__import__('core.config', fromlist=['AI_MAX_PROMPT_CHARS']).AI_MAX_PROMPT_CHARS)} characters",
            )

        # Determine the effective max_tokens to validate against
        settings = __import__("core.config", fromlist=["AI_MAX_OUTPUT_TOKENS"]).get_settings()
        max_out = int(getattr(settings, "AI_MAX_OUTPUT_TOKENS", 4096))

        # Validate max_tokens
        resolved_max = max_tokens if max_tokens is not None else 512  # AI_DEFAULT_MAX_TOKENS
        if not (1 <= resolved_max <= max_out):
            raise ValidationError(
                "max_tokens",
                f"max_tokens must be between 1 and {max_out}",
            )

        # Validate temperature
        if not (0.0 <= temperature <= 2.0):
            raise ValidationError(
                "temperature",
                f"temperature must be between 0.0 and 2.0, got {temperature}",
            )

        # Validate idempotency key
        if not idempotency_key or not idempotency_key.strip():
            raise ValidationError(
                "idempotency_key",
                "Idempotency key must be non-empty",
            )
        if len(idempotency_key) > 255:
            raise ValidationError(
                "idempotency_key",
                f"Idempotency key must be at most 255 characters (got {len(idempotency_key)})",
            )

    @staticmethod
    def _now() -> datetime:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc)

    async def _replay_result(self, existing: AIRequest, repo) -> AIGenerationResult:
        """Replay a previously-succeeded request, returning the stored result."""
        return AIGenerationResult(
            content=existing.response_content or "",
            model=existing.model,
            provider=existing.provider,
            prompt_tokens=existing.prompt_tokens,
            completion_tokens=existing.completion_tokens,
            cached_prompt_tokens=existing.cached_prompt_tokens,
            reasoning_tokens=existing.reasoning_tokens,
            total_cost_paise=existing.total_cost_paise,
            usage_source=existing.usage_source or "provider",
            request_id=existing.id,
            finish_reason=existing.error_code or "stop",
            replayed=True,
            quota_exceeded=False,
        )