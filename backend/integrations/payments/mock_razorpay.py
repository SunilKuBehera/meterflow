"""Mock Razorpay adapter for automated tests.

Strictly for test usage — returns deterministic responses regardless of
configuration.  Real production code must use ``RazorpayAdapter`` (which
requires ``RAZORPAY_KEY_ID``, ``RAZORPAY_KEY_SECRET``, and
``RAZORPAY_WEBHOOK_SECRET`` in the environment).

The mock adapter is accessible via ``RazorpayAdapter.mock()`` when the
real SDK is not installed, or when tests need to avoid external API calls.
"""

from __future__ import annotations

from typing import Any


class MockRazorpayAdapter:
    """Mock Razorpay adapter for automated tests.

    All methods return hard-coded deterministic values.  No network calls
    are made, and no environment variables are required.
    """

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Checkout / subscription
    # ------------------------------------------------------------------

    def initiate_subscription(
        self,
        *,
        plan_name: str,
        amount: int,
        customer_email: str,
        customer_contact: str,
        total_count: int | None = None,
        first_payment_at: str | None = None,
    ) -> dict[str, Any]:
        """Return a deterministic mock subscription response."""
        return {
            "id": "sub_test_mock_12345",
            "status": "pending",
            "amount": amount,
            "error": None,
        }

    # ------------------------------------------------------------------
    # Webhook verification
    # ------------------------------------------------------------------

    def verify_webhook_signature(
        self, payload: bytes, signature: str
    ) -> bool:
        """Always return ``True`` — test webhooks verify successfully."""
        return True

    # ------------------------------------------------------------------
    # Checkout session
    # ------------------------------------------------------------------

    def create_checkout_session(
        self,
        *,
        subscription_id: str,
        total_amount: int,
        currency: str = "INR",
        callback_url: str,
    ) -> dict[str, Any]:
        """Return a deterministic mock checkout response."""
        return {
            "id": "order_test_mock_67890",
            "checkout_url": "https://rzp.io/l/test_mock",
            "amount": total_amount,
            "currency": currency,
            "error": None,
        }

    # ------------------------------------------------------------------
    # Plan / pricing helpers (mock)
    # ------------------------------------------------------------------

    @staticmethod
    def mock_plan_response(plan_name: str = "pro_monthly") -> dict[str, Any]:
        """Return a mock plan config matching the backend plan definitions."""

        plans: dict[str, dict[str, object]] = {
            "free_monthly": {
                "id": "plan_free",
                "name": "Free",
                "amount": 0,
                "interval": "monthly",
                "currency": "INR",
            },
            "pro_monthly": {
                "id": "plan_pro",
                "name": "Pro",
                "amount": 99900,  # ₹999.00 per month
                "interval": "monthly",
                "currency": "INR",
            },
            "pro_yearly": {
                "id": "plan_pro_yearly",
                "name": "Pro",
                "amount": 999000,  # ₹9,990.00 per year
                "interval": "yearly",
                "currency": "INR",
            },
        }

        return plans.get(
            plan_name,
            {
                "id": f"plan_mock_{plan_name}",
                "name": plan_name,
                "amount": 0,
                "interval": "monthly",
                "currency": "INR",
            },
        )


# ----------------------------------------------------------------------
# Convenience shim so ``integrations.payments`` always has a callable.
# ------------------------------------------------------------------

_RAZORPAY_MOCK = MockRazorpayAdapter()


def mock() -> MockRazorpayAdapter:
    """Return the module-level mock adapter instance."""
    return _RAZORPAY_MOCK
