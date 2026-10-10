"""
Repeatable seed script for Free and Pro plans.

This script is idempotent - it can be run multiple times safely.
It uses ON CONFLICT DO UPDATE to upsert plan records.
"""

import asyncio
import logging
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import async_session_factory
from models.billing import Plan, PlanName


async def seed_plans(session: AsyncSession) -> None:
    """Seed or update Free and Pro plans."""

    # Free plan - 1000 API calls, 100k AI tokens per calendar month
    free_plan = Plan(
        id=uuid.uuid4(),
        name=PlanName.FREE,
        display_name="Free",
        description="Perfect for getting started with AI API metering",
        price_paise=0,
        currency="INR",
        billing_period="monthly",
        api_calls_limit=1000,
        ai_tokens_limit=100000,
        api_call_price_paise=0,
        ai_input_token_price_paise=0,
        ai_cached_input_token_price_paise=0,
        ai_output_token_price_paise=0,
        ai_reasoning_token_price_paise=0,
        is_active=True,
        razorpay_plan_id=None,
    )

    # Pro plan - 100k API calls, 10M AI tokens per calendar month, Rs 999/month
    pro_plan = Plan(
        id=uuid.uuid4(),
        name=PlanName.PRO,
        display_name="Pro",
        description="For growing teams and production applications",
        price_paise=99900,  # Rs 999.00 in paise
        currency="INR",
        billing_period="monthly",
        api_calls_limit=100000,
        ai_tokens_limit=10000000,
        api_call_price_paise=10,  # Rs 0.10 per API call overage
        ai_input_token_price_paise=5,  # Rs 0.05 per 1k input tokens
        ai_cached_input_token_price_paise=1,  # Rs 0.01 per 1k cached input tokens
        ai_output_token_price_paise=15,  # Rs 0.15 per 1k output tokens
        ai_reasoning_token_price_paise=15,  # Same as output tokens
        is_active=True,
        razorpay_plan_id=None,  # Set after creating plan in Razorpay dashboard
    )

    # Upsert Free plan
    await session.execute(
        text("""
            INSERT INTO plans (id, name, display_name, description, price_paise, currency,
                             billing_period, api_calls_limit, ai_tokens_limit,
                             api_call_price_paise, ai_input_token_price_paise,
                             ai_cached_input_token_price_paise, ai_output_token_price_paise,
                             ai_reasoning_token_price_paise, is_active, razorpay_plan_id,
                             created_at, updated_at)
            VALUES (:id, :name, :display_name, :description, :price_paise, :currency,
                    :billing_period, :api_calls_limit, :ai_tokens_limit,
                    :api_call_price_paise, :ai_input_token_price_paise,
                    :ai_cached_input_token_price_paise, :ai_output_token_price_paise,
                    :ai_reasoning_token_price_paise, :is_active, :razorpay_plan_id,
                    NOW(), NOW())
            ON CONFLICT (name) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                description = EXCLUDED.description,
                price_paise = EXCLUDED.price_paise,
                currency = EXCLUDED.currency,
                billing_period = EXCLUDED.billing_period,
                api_calls_limit = EXCLUDED.api_calls_limit,
                ai_tokens_limit = EXCLUDED.ai_tokens_limit,
                api_call_price_paise = EXCLUDED.api_call_price_paise,
                ai_input_token_price_paise = EXCLUDED.ai_input_token_price_paise,
                ai_cached_input_token_price_paise = EXCLUDED.ai_cached_input_token_price_paise,
                ai_output_token_price_paise = EXCLUDED.ai_output_token_price_paise,
                ai_reasoning_token_price_paise = EXCLUDED.ai_reasoning_token_price_paise,
                is_active = EXCLUDED.is_active,
                razorpay_plan_id = EXCLUDED.razorpay_plan_id,
                updated_at = NOW()
        """),
        {
            "id": free_plan.id,
            "name": free_plan.name.value,
            "display_name": free_plan.display_name,
            "description": free_plan.description,
            "price_paise": free_plan.price_paise,
            "currency": free_plan.currency,
            "billing_period": free_plan.billing_period,
            "api_calls_limit": free_plan.api_calls_limit,
            "ai_tokens_limit": free_plan.ai_tokens_limit,
            "api_call_price_paise": free_plan.api_call_price_paise,
            "ai_input_token_price_paise": free_plan.ai_input_token_price_paise,
            "ai_cached_input_token_price_paise": free_plan.ai_cached_input_token_price_paise,
            "ai_output_token_price_paise": free_plan.ai_output_token_price_paise,
            "ai_reasoning_token_price_paise": free_plan.ai_reasoning_token_price_paise,
            "is_active": free_plan.is_active,
            "razorpay_plan_id": free_plan.razorpay_plan_id,
        }
    )

    # Upsert Pro plan
    await session.execute(
        text("""
            INSERT INTO plans (id, name, display_name, description, price_paise, currency,
                             billing_period, api_calls_limit, ai_tokens_limit,
                             api_call_price_paise, ai_input_token_price_paise,
                             ai_cached_input_token_price_paise, ai_output_token_price_paise,
                             ai_reasoning_token_price_paise, is_active, razorpay_plan_id,
                             created_at, updated_at)
            VALUES (:id, :name, :display_name, :description, :price_paise, :currency,
                    :billing_period, :api_calls_limit, :ai_tokens_limit,
                    :api_call_price_paise, :ai_input_token_price_paise,
                    :ai_cached_input_token_price_paise, :ai_output_token_price_paise,
                    :ai_reasoning_token_price_paise, :is_active, :razorpay_plan_id,
                    NOW(), NOW())
            ON CONFLICT (name) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                description = EXCLUDED.description,
                price_paise = EXCLUDED.price_paise,
                currency = EXCLUDED.currency,
                billing_period = EXCLUDED.billing_period,
                api_calls_limit = EXCLUDED.api_calls_limit,
                ai_tokens_limit = EXCLUDED.ai_tokens_limit,
                api_call_price_paise = EXCLUDED.api_call_price_paise,
                ai_input_token_price_paise = EXCLUDED.ai_input_token_price_paise,
                ai_cached_input_token_price_paise = EXCLUDED.ai_cached_input_token_price_paise,
                ai_output_token_price_paise = EXCLUDED.ai_output_token_price_paise,
                ai_reasoning_token_price_paise = EXCLUDED.ai_reasoning_token_price_paise,
                is_active = EXCLUDED.is_active,
                razorpay_plan_id = EXCLUDED.razorpay_plan_id,
                updated_at = NOW()
        """),
        {
            "id": pro_plan.id,
            "name": pro_plan.name.value,
            "display_name": pro_plan.display_name,
            "description": pro_plan.description,
            "price_paise": pro_plan.price_paise,
            "currency": pro_plan.currency,
            "billing_period": pro_plan.billing_period,
            "api_calls_limit": pro_plan.api_calls_limit,
            "ai_tokens_limit": pro_plan.ai_tokens_limit,
            "api_call_price_paise": pro_plan.api_call_price_paise,
            "ai_input_token_price_paise": pro_plan.ai_input_token_price_paise,
            "ai_cached_input_token_price_paise": pro_plan.ai_cached_input_token_price_paise,
            "ai_output_token_price_paise": pro_plan.ai_output_token_price_paise,
            "ai_reasoning_token_price_paise": pro_plan.ai_reasoning_token_price_paise,
            "is_active": pro_plan.is_active,
            "razorpay_plan_id": pro_plan.razorpay_plan_id,
        }
    )

    await session.commit()
    logging.info("Plans seeded successfully!")


async def main() -> None:
    async with async_session_factory() as session:
        await seed_plans(session)


if __name__ == "__main__":
    asyncio.run(main())
