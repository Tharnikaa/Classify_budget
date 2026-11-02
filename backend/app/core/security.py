"""JWT authentication, RBAC guards, and Separation-of-Duties (SoD) enforcement."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash

from app.core.config import Settings, get_settings
from app.core.errors import ApiError
from app.schemas.api import RoleEnum, UserProfile
from app.services.stub_store import StubStateStore, get_stub_store

password_hasher = PasswordHash.recommended()
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(plain_password: str) -> str:
    return password_hasher.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hasher.verify(plain_password, hashed_password)


def create_access_token(user: UserProfile, settings: Settings | None = None) -> str:
    cfg = settings or get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": user.id,
        "email": user.email,
        "role": user.role.value,
        "spend_tier": user.spend_tier.value,
        "department_id": user.department_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=cfg.JWT_EXPIRE_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, cfg.JWT_SECRET, algorithm=cfg.JWT_ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
    store: StubStateStore = Depends(get_stub_store),
) -> UserProfile:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiError(
            status_code=401,
            code="UNAUTHENTICATED",
            message="Missing or invalid Bearer authentication token.",
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError as exc:
        raise ApiError(status_code=401, code="TOKEN_EXPIRED", message="Token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise ApiError(status_code=401, code="INVALID_TOKEN", message="Invalid JWT token.") from exc

    user_id = payload.get("sub")
    if not isinstance(user_id, str):
        raise ApiError(status_code=401, code="INVALID_TOKEN", message="Malformed token subject.")

    user = store.get_user_by_id(user_id)
    if user is None:
        raise ApiError(status_code=401, code="USER_NOT_FOUND", message="User no longer exists.")
    return user


def require_roles(*allowed_roles: RoleEnum) -> Callable[[UserProfile], UserProfile]:
    allowed_set = set(allowed_roles)

    def _guard(current_user: UserProfile = Depends(get_current_user)) -> UserProfile:
        if current_user.role not in allowed_set:
            allowed_str = ", ".join(r.value for r in allowed_roles)
            raise ApiError(
                status_code=403,
                code="FORBIDDEN_ROLE",
                message=f"Role '{current_user.role.value}' is not authorized. Required: {allowed_str}.",
            )
        return current_user

    return _guard


def assert_not_self_claim(actor_id: str, claimant_id: str, action_label: str) -> None:
    """Separation-of-Duties invariant: nobody may approve, verify, override, or dispatch their own claim."""
    if actor_id == claimant_id:
        raise ApiError(
            status_code=403,
            code="SOD_SELF_ACTION_FORBIDDEN",
            message=f"Separation of Duties violation: user cannot {action_label} their own expense claim.",
        )

