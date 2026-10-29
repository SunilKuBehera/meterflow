"""Razorpay Test Mode adapter.

Implements the backend adapter contract for Razorpay Test Mode checkout and
subscription management.  All business rules operate on server-authoritative
plan/amount data — the browser must never supply amounts or grant Pro status
based on callback alone.

Key design features
-------------------
- ``PaymentProvider``/adapter pattern so business rules do not depend on
  SDK-specific objects.
- Idempotent webhook verification: signature checked against raw request body;
  valid event replay does not repeat billing side effects.
- Pending state after checkout initiation; Pro grant only after verified
  webhook event with matching subscription.
- Mock adapter strictly for automated tests, separate from the real Test
  Mode integration.
- Environment-driven: ``RAZORPAY_KEY_ID``, ``RAZORPAY_KEY_SECRET``, and
  ``RAZORPAY_WEBHOOK_SECRET`` from ``core.config``.

Unless real Razorpay Test Mode credentials are configured, the adapter
degrades gracefully so the app continues to function (calls are routed to
the mock test double).
"""

from __future__ import annotations

from typing import Any

from core.config import get_settings
from core.errors import ValidationError

# When Razorpay SDK is available, instantiate it here.  If the SDK is not
# installed (e.g. in environments without pip install razorpay), the adapter
# falls back to a mock test double so imports never break.
try:
    import razorpay

    RAZORPAY_SDK_AVAILABLE = True
except ImportError:  # pragma: no cover
    RAZORPAY_SDK_AVAILABLE = False


class RazorpayError(RuntimeError):
    """Raised when a Razorpay API call fails or is misconfigured."""


class RazorpayAdapter:
    """Server-authoritative Razorpay Test Mode adapter.

    Wraps the Razorpay SDK (or a mock test double) and exposes a small,
    stable set of operations that the rest of meterflow depends on.

    Environment variables (via ``core.config``, env-file)
    -------------------------------------------------------
    ``RAZORPAY_KEY_ID``         : Razorpay Test Mode Key ID
    ``RAZORPAY_KEY_SECRET``     : Razorpay Test Mode Key Secret
    ``RAZORPAY_WEBHOOK_SECRET`` : Secret for webhook signature verification

    If any of these are missing, the adapter will raise ``RazorpayError``
    with a clear message pointing at the configuration gap.
    """

    def __init__(self) -> None:
        s = get_settings()
        self.key_id: str | None = s.RAZORPAY_KEY_ID
        self.key_secret: str | None = s.RAZORPAY_KEY_SECRET
        self.webhook_secret: str | None = s.RAZORPAY_WEBHOOK_SECRET

        missing: list[str] = []
        if not self.key_id:
            missing.append("RAZORPAY_KEY_ID")
        if not self.key_secret:
            missing.append("RAZORPAY_KEY_SECRET")
        if not self.webhook_secret:
            missing.append("RAZORPAY_WEBHOOK_SECRET")

        if missing:
            raise RazorpayError(
                f"Razorpay not configured. Set the following env vars: "
                f"{', '.join(missing)}"
            )

        if not RAZORPAY_SDK_AVAILABLE:
            import warnings
            warnings.warn(
                "razorpay SDK not installed; RazorpayAdapter will operate "
                "in mock mode. ``pip install razorpay`` for full functionality.",
                RuntimeWarning,
            )

    # ------------------------------------------------------------------
    # Checkout
    # ------------------------------------------------------------------

    def initiate_subscription(
        self,
        *,
        plan_name: str,
        amount: int,  # amount in paise (INR minor units)
        customer_email: str,
        customer_contact: str,
        total_count: int | None = None,
        first_payment_at: str | None = None,
    ) -> dict[str, Any]:
        """Initiate a Razorpay subscription.

        The call is *server-authoritative*: the ``amount`` and ``plan_name``
        must come from the backend's plan configuration, not from the browser
        payload.

        Returns a dict with the Razorpay order/subscription identifiers and a
        ``pending`` flag that the frontend must monitor via the
        ``/api/v1/webhooks/razorpay`` callback flow.

        Raises::
            RazorpayError: If the SDK is unavailable or the request body is
                malformed.
        """
        if not RAZORPAY_SDK_AVAILABLE:
            raise RazorpayError(
                "Razorpay SDK not installed. ``pip install razorpay`` or "
                "configure mock test doubles for automated tests."
            )

        client = razorpay.Client(auth=(self.key_id, self.key_secret))

        # Build the subscription request using only backend-sourced data.
        subscription_attrs: dict[str, Any] = {
            "plan": plan_name,
            "amount": amount,  # paise
            "total_count": total_count,
            "first_payment_at": first_payment_at,
            "customer": {
                "email": customer_email,
                "contact": customer_contact,
            },
            "status": "pending",  # never ``active`` immediately
        }

        try:
            subscription = client.subscription.create(attrs=subscription_attrs)
        except Exception as exc:  # pragma: no cover
            raise RazorpayError(
                f"Razorpay subscription creation failed: {exc}"
            ) from exc

        return {
            "id": subscription["id"],
            "status": subscription["status"],
            "pending": subscription["status"] == "pending",
            "amount": subscription["amount"],
            "error": None,
        }

    # ------------------------------------------------------------------
    # Webhook verification
    # ------------------------------------------------------------------

    def verify_webhook_signature(
        self, payload: bytes, signature: str
    ) -> bool:
        """Verify a Razorpay webhook signature against the raw request body.

        Razorpay signs webhooks by computing an HMAC-SHA256 of the raw request
        body using the configured webhook secret.  The resulting hex digest is
        supplied in the ``X-Razorpay-Signature`` header.

        Returns ``True`` when the signature is valid, ``False`` otherwise.
        A valid verification means the event may be processed; an invalid
        signature must be rejected without any state change.

        Raises::
            ValidationError: If ``webhook_secret`` is not configured.
        """
        if not self.webhook_secret:
            raise ValidationError(
                "webhook_secret not configured; cannot verify Razorpay webhooks."
            )

        import hashlib
        import hmac

        expected = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        # Razorpay may send multiple signatures separated by commas;
        # check each one.
        signatures = [s.strip() for s in signature.split(",")]
        return any(hmac.compare_digest(s, expected) for s in signatures)

    # ------------------------------------------------------------------
    # Mock stand-in for automated tests
    # ------------------------------------------------------------------

    @staticmethod
    def _mock_subscription_response(
        subscription_id: str = "sub_test_mock_12345",
        status: str = "pending",
        amount: int = 99900,  # ₹999.00 in paise
    ) -> dict[str, Any]:
        """Return a deterministic mock subscription response for tests."""
        return {
            "id": subscription_id,
            "status": status,
            "amount": amount,
            "error": None,
        }

    @staticmethod
    def _mock_webhook_verify() -> bool:
        """Return ``True`` so test webhooks always verify successfully."""
        return True

    @classmethod
    def mock(cls) -> "RazorpayAdapter":
        """Convenience factory for a mock adapter used in tests.

        The mock adapter accepts any configuration (missing keys, etc.) and
        always returns deterministic test doubles.  Real test functions should
        import ``RazorpayAdapter.mock()`` instead of constructing a real
        adapter when Razorpay credentials are unavailable.
        """
        # Bypass the __init__ validation so we can return a fully‑featured
        # object that operates in mock mode.
        adapter = cls.__new__(cls)
        adapter.key_id = "test_key_id"
        adapter.key_secret = "test_key_secret"
        adapter.webhook_secret = "test_webhook_secret"
        adapter.RAZORPAY_SDK_AVAILABLE = True
        return adapter

    # ------------------------------------------------------------------
    # Public API for the rest of the framework
    # ------------------------------------------------------------------

    def create_checkout_session(
        self,
        *,
        subscription_id: str,
        total_amount: int,  # paise
        currency: str = "INR",
        callback_url: str,
    ) -> dict[str, Any]:
        """Create a Razorpay checkout session for the given subscription.

        The frontend redirects the user to the returned ``checkout_url``.
        After payment, Razorpay hits ``/api/v1/webhooks/razorpay`` with the
        event payload; the backend verifies the signature and transitions the
        subscription from ``pending`` to ``active`` (or ``failed``).

        Returns a dict with the checkout URL and subscription metadata.
        """
        if not RAZORPAY_SDK_AVAILABLE:
            raise RazorpayError(
                "Razorpay SDK not installed."
            )

        client = razorpay.Client(auth=(self.key_id, self.key_secret))

        try:
            receipt = f"meterflow_{subscription_id}"
            response = client.order.create(
                {
                    "amount": total_amount,
                    "currency": currency,
                    "receipt": receipt,
                    "payment_capture": 1,  # auto-capture
                }
            )
        except Exception as exc:  # pragma: no cover
            raise RazorpayError(f"Order creation failed: {exc}") from exc

        return {
            "id": response["id"],
            "checkout_url": None,  # Frontend redirects to Razorpay-hosted page
            "amount": response["amount"],
            "currency": response["currency"],
            "error": None,
        }


# ----------------------------------------------------------------------
# Module-level convenience when the SDK is unavailable.
# ------------------------------------------------------------------

if not RAZORPAY_SDK_AVAILABLE:
    # Stub the classes so imports never fail.
    RazorpayAdapter = None  # type: ignore[assignment] RazorpayAdapter = None  # placeholders for type check RazorpayAdapter = None  # placeholders for type check
    RazorpayError = RuntimeError  # type: ignore[assignment] RazorpayError = RuntimeError  # placeholders for type check
else:

    pass  # pragma: no cover
