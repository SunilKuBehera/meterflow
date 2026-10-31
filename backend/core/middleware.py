"""Security and observability middleware.

Provides request ID tracking, rate limiting, size limits, and secure error
handling for the MeterFlow API. All middleware is framework-level (applies to
every endpoint) so business logic remains clean.
"""

import time
import uuid
from collections import defaultdict
from typing import Any

from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import get_settings
from core.logging import get_logger, set_correlation_id

logger = get_logger(__name__)
settings = get_settings()

# In-memory rate limit store (per-IP, per-endpoint). In production this would
# be Redis or a dedicated rate limiter service.
_rate_limit_store: dict[str, dict[str, Any]] = defaultdict(dict)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Adds a unique request ID to every request and passes it to the logger."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        set_correlation_id(request_id)

        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{process_time:.3f}"

        # Log the request with correlation info
        logger.info(
            "Request completed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            process_time_ms=int(process_time * 1000),
            client_host=request.client.host if request.client else "unknown",
        )

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple per-IP rate limiter.

    Configuration (via core.config):
      - ``RATE_LIMIT_REQUESTS``: maximum requests per window (default: 100)
      - ``RATE_LIMIT_WINDOW_SECONDS``: window size in seconds (default: 60)

    Notes
    -----
    - This is a best-effort in‑memory store; it does not block the request but
      adds an ``X-Rate-Limit-Remaining`` header so the frontend can display
      throttling state.
    - The limiter is per‑client IP; authenticated tenants may eventually want
      to scope it to the user ID.
    """

    def __init__(self, app, *, rate_limit_requests: int | None = None, rate_limit_window_seconds: int | None = None) -> None:
        super().__init__(app)
        self.rate_limit_requests = rate_limit_requests or settings.RATE_LIMIT_REQUESTS
        self.rate_limit_window_seconds = rate_limit_window_seconds or settings.RATE_LIMIT_WINDOW_SECONDS

    async def dispatch(self, request: Request, call_next) -> Response:
        client_host = request.client.host if request.client else "unknown"
        now = time.time()
        window_key = f"{client_host}:{int(now // self.rate_limit_window_seconds)}"

        store = _rate_limit_store[window_key]
        count = store.get("count", 0) + 1
        store["count"] = count
        store["first"] = store.get("first", now)

        remaining = max(0, self.rate_limit_requests - count)
        reset_time = int(store["first"] + self.rate_limit_window_seconds)

        if count > self.rate_limit_requests:
            # 429 Too Many Requests
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "RATE_LIMITED",
                    "message": f"Rate limit exceeded: {self.rate_limit_requests} requests per {self.rate_limit_window_seconds}s",
                    "retry_after": reset_time,
                },
            )

        response = await call_next(request)
        response.headers["X-Rate-Limit-Limit"] = str(self.rate_limit_requests)
        response.headers["X-Rate-Limit-Remaining"] = str(remaining)
        response.headers["X-Rate-Limit-Reset"] = str(reset_time)

        return response


def add_middleware(app) -> None:
    """Register all security/middleware layers in the correct order."""
    # RequestIDMiddleware first (innermost, closest to the app)
    app.add_middleware(RequestIDMiddleware)

    # RateLimitMiddleware outermost (runs after RequestIDMiddleware)
    app.add_middleware(RateLimitMiddleware)


def validate_request_size(max_bytes: int | None = None) -> callable:
    """Decorator to enforce request body size limits.

    Used on POST/PUT endpoints that accept JSON bodies.  Raises
    ``413 Payload Too Large`` when the limit is exceeded.
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            # FastAPI passes the Request object as the first arg after self
            for arg in args:
                if hasattr(arg, "body"):
                    body = arg.body
                    if body and len(body) > (max_bytes or settings.MAX_REQUEST_BYTES):
                        raise HTTPException(
                            status_code=status.HTTP_413_PAYLOAD_TOO_LARGE,
                            detail={
                                "error": "PAYLOAD_TOO_LARGE",
                                "message": f"Request body exceeds {max_bytes or settings.MAX_REQUEST_BYTES} bytes",
                            },
                        )
                    # Decode and store for downstream parsing
                    try:
                        arg._body_preview = body.decode("utf-8")[:200]
                    except Exception:
                        pass
                    return await func(*args, **kwargs)
            # If no Request object found (e.g. dependency-injected), skip
            return await func(*args, **kwargs)

        return wrapper

    return decorator
