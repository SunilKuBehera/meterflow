from dataclasses import dataclass
from uuid import UUID

from models.billing import Plan, UsageEvent


@dataclass
class PriceBreakdown:
    """Breakdown of cost calculation for a usage event."""
    api_calls_cost_paise: int
    ai_input_tokens_cost_paise: int
    ai_cached_input_tokens_cost_paise: int
    ai_output_tokens_cost_paise: int
    ai_reasoning_tokens_cost_paise: int
    total_cost_paise: int

    @property
    def total_cost_rupees(self) -> float:
        """Convert total cost to rupees (float for display only)."""
        return self.total_cost_paise / 100.0


class PricingService:
    """Deterministic pricing service using integer minor units (paise).

    Pricing rules:
    - API calls: priced per API call using plan's api_call_price_paise
    - AI input tokens: priced per token using plan's ai_input_token_price_paise
    - AI cached input tokens: priced per token using plan's ai_cached_input_token_price_paise
    - AI output tokens: priced per token using plan's ai_output_token_price_paise
    - AI reasoning tokens: priced per token using plan's ai_output_token_price_paise (same rate as output)
    """

    @staticmethod
    def calculate_usage_cost(usage_event: UsageEvent, plan: Plan) -> PriceBreakdown:
        """Calculate the cost of a usage event based on plan pricing rates.

        All calculations use integer arithmetic in paise (minor units).
        No floating-point operations are performed.
        """
        api_calls_cost = usage_event.api_calls * plan.api_call_price_paise
        ai_input_tokens_cost = usage_event.ai_input_tokens * plan.ai_input_token_price_paise
        ai_cached_input_tokens_cost = (
            usage_event.ai_cached_input_tokens * plan.ai_cached_input_token_price_paise
        )
        ai_output_tokens_cost = usage_event.ai_output_tokens * plan.ai_output_token_price_paise
        ai_reasoning_tokens_cost = (
            usage_event.ai_reasoning_tokens * plan.ai_output_token_price_paise
        )

        total_cost = (
            api_calls_cost
            + ai_input_tokens_cost
            + ai_cached_input_tokens_cost
            + ai_output_tokens_cost
            + ai_reasoning_tokens_cost
        )

        return PriceBreakdown(
            api_calls_cost_paise=api_calls_cost,
            ai_input_tokens_cost_paise=ai_input_tokens_cost,
            ai_cached_input_tokens_cost_paise=ai_cached_input_tokens_cost,
            ai_output_tokens_cost_paise=ai_output_tokens_cost,
            ai_reasoning_tokens_cost_paise=ai_reasoning_tokens_cost,
            total_cost_paise=total_cost,
        )

    @staticmethod
    def calculate_usage_cost_from_counts(
        plan: Plan,
        api_calls: int = 0,
        ai_input_tokens: int = 0,
        ai_cached_input_tokens: int = 0,
        ai_output_tokens: int = 0,
        ai_reasoning_tokens: int = 0,
    ) -> PriceBreakdown:
        """Calculate cost directly from usage counts (without a UsageEvent object)."""
        api_calls_cost = api_calls * plan.api_call_price_paise
        ai_input_tokens_cost = ai_input_tokens * plan.ai_input_token_price_paise
        ai_cached_input_tokens_cost = (
            ai_cached_input_tokens * plan.ai_cached_input_token_price_paise
        )
        ai_output_tokens_cost = ai_output_tokens * plan.ai_output_token_price_paise
        ai_reasoning_tokens_cost = (
            ai_reasoning_tokens * plan.ai_output_token_price_paise
        )

        total_cost = (
            api_calls_cost
            + ai_input_tokens_cost
            + ai_cached_input_tokens_cost
            + ai_output_tokens_cost
            + ai_reasoning_tokens_cost
        )

        return PriceBreakdown(
            api_calls_cost_paise=api_calls_cost,
            ai_input_tokens_cost_paise=ai_input_tokens_cost,
            ai_cached_input_tokens_cost_paise=ai_cached_input_tokens_cost,
            ai_output_tokens_cost_paise=ai_output_tokens_cost,
            ai_reasoning_tokens_cost_paise=ai_reasoning_tokens_cost,
            total_cost_paise=total_cost,
        )

    @staticmethod
    def calculate_total_cost(events: list[UsageEvent], plan: Plan) -> int:
        """Calculate total cost for multiple usage events.

        Returns total cost in paise (integer minor units).
        """
        total = 0
        for event in events:
            total += PricingService.calculate_usage_cost(event, plan).total_cost_paise
        return total

    @staticmethod
    def calculate_total_cost_from_breakdowns(breakdowns: list[PriceBreakdown]) -> int:
        """Calculate total cost from multiple price breakdowns."""
        return sum(b.total_cost_paise for b in breakdowns)

    @staticmethod
    def format_paise_to_rupees(paise: int) -> str:
        """Format paise amount to rupees string for display."""
        rupees = paise / 100.0
        return f"₹{rupees:,.2f}"

    @staticmethod
    def validate_pricing(plan: Plan) -> None:
        """Validate that plan pricing rates are non-negative."""
        if plan.api_call_price_paise < 0:
            raise ValueError("api_call_price_paise cannot be negative")
        if plan.ai_input_token_price_paise < 0:
            raise ValueError("ai_input_token_price_paise cannot be negative")
        if plan.ai_cached_input_token_price_paise < 0:
            raise ValueError("ai_cached_input_token_price_paise cannot be negative")
        if plan.ai_output_token_price_paise < 0:
            raise ValueError("ai_output_token_price_paise cannot be negative")
        if plan.ai_reasoning_token_price_paise < 0:
            raise ValueError("ai_reasoning_token_price_paise cannot be negative")