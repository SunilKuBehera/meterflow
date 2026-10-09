from typing import Any

from jose import jwt  # type: ignore[import-untyped]
from jose.exceptions import ExpiredSignatureError, JWTError  # type: ignore[import-untyped]

from core.config import get_settings
from core.errors import InvalidTokenError, TokenExpiredError


class SupabaseJWTVerifier:
    def __init__(self) -> None:
        settings = get_settings()
        self._secret = settings.SUPABASE_JWT_SECRET
        self._algorithm = "HS256"
        self._audience = "authenticated"
        self._issuer = f"{settings.SUPABASE_URL}/auth/v1"

    def verify(self, token: str) -> dict[str, Any]:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                audience=self._audience,
                issuer=self._issuer,
                options={"verify_aud": True, "verify_iss": True},
            )
            return payload  # type: ignore[no-any-return]
        except ExpiredSignatureError as exc:
            raise TokenExpiredError() from exc
        except JWTError as exc:
            raise InvalidTokenError(str(exc)) from exc

    def get_user_id(self, token: str) -> str:
        payload = self.verify(token)
        user_id = payload.get("sub")
        if not user_id:
            raise InvalidTokenError("Token missing subject claim")
        return user_id  # type: ignore[no-any-return]

    def get_claims(self, token: str) -> dict[str, Any]:
        return self.verify(token)


_jwt_verifier: SupabaseJWTVerifier | None = None


def get_jwt_verifier() -> SupabaseJWTVerifier:
    global _jwt_verifier
    if _jwt_verifier is None:
        _jwt_verifier = SupabaseJWTVerifier()
    return _jwt_verifier
