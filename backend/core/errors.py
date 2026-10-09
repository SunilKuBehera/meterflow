from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from core.logging import get_logger

logger = get_logger(__name__)


class ErrorCode(str):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    INVALID_TOKEN = "INVALID_TOKEN"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    PAYMENT_REQUIRED = "PAYMENT_REQUIRED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    RATE_LIMITED = "RATE_LIMITED"


class ErrorDetail(BaseModel):
    code: str
    message: str
    field: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
    request_id: str | None = None


class AppException(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        field: str | None = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.field = field
        super().__init__(message)


class ValidationError(AppException):
    def __init__(self, message: str, field: str | None = None):
        super().__init__(
            code=ErrorCode.VALIDATION_ERROR,
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            field=field,
        )


class AuthenticationError(AppException):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            code=ErrorCode.AUTHENTICATION_REQUIRED,
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class InvalidTokenError(AppException):
    def __init__(self, message: str = "Invalid or malformed token"):
        super().__init__(
            code=ErrorCode.INVALID_TOKEN,
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class TokenExpiredError(AppException):
    def __init__(self, message: str = "Token has expired"):
        super().__init__(
            code=ErrorCode.TOKEN_EXPIRED,
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenError(AppException):
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(
            code=ErrorCode.FORBIDDEN,
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class NotFoundError(AppException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(
            code=ErrorCode.NOT_FOUND,
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ConflictError(AppException):
    def __init__(self, message: str = "Resource conflict"):
        super().__init__(
            code=ErrorCode.CONFLICT,
            message=message,
            status_code=status.HTTP_409_CONFLICT,
        )


class IdempotencyConflictError(AppException):
    def __init__(self, message: str = "Idempotency key already used with different request"):
        super().__init__(
            code=ErrorCode.IDEMPOTENCY_CONFLICT,
            message=message,
            status_code=status.HTTP_409_CONFLICT,
        )


class QuotaExceededError(AppException):
    def __init__(self, message: str = "Monthly quota exceeded"):
        super().__init__(
            code=ErrorCode.QUOTA_EXCEEDED,
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )


class PaymentRequiredError(AppException):
    def __init__(self, message: str = "Payment required to access this resource"):
        super().__init__(
            code=ErrorCode.PAYMENT_REQUIRED,
            message=message,
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
        )


class ProviderUnavailableError(AppException):
    def __init__(self, message: str = "AI provider unavailable"):
        super().__init__(
            code=ErrorCode.PROVIDER_UNAVAILABLE,
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class ProviderError(AppException):
    def __init__(self, message: str = "AI provider error"):
        super().__init__(
            code=ErrorCode.PROVIDER_ERROR,
            message=message,
            status_code=status.HTTP_502_BAD_GATEWAY,
        )


class RateLimitedError(AppException):
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(
            code=ErrorCode.RATE_LIMITED,
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )


def create_error_response(
    request: Request,
    code: str,
    message: str,
    status_code: int,
    field: str | None = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    error_detail = ErrorDetail(code=code, message=message, field=field)
    error_response = ErrorResponse(error=error_detail, request_id=request_id)
    return JSONResponse(
        status_code=status_code,
        content=error_response.model_dump(),
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        logger.warning(
            "Application error",
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            path=request.url.path,
            request_id=getattr(request.state, "request_id", None),
        )
        return create_error_response(request, exc.code, exc.message, exc.status_code, exc.field)

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled exception",
            path=request.url.path,
            request_id=getattr(request.state, "request_id", None),
            exc_info=exc,
        )
        return create_error_response(
            request,
            ErrorCode.INTERNAL_ERROR,
            "An unexpected error occurred",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
