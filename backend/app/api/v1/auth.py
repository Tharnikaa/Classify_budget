"""Authentication and dev-only Role Switcher routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.core.errors import ApiError
from app.core.security import create_access_token, get_current_user
from app.schemas.api import (
    AuthTokenResponse,
    DevSwitchRoleRequest,
    LoginRequest,
    UserProfile,
)
from app.services.stub_store import StubStateStore, get_stub_store

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


@router.post("/login", response_model=AuthTokenResponse)
def login(
    payload: LoginRequest,
    settings: Settings = Depends(get_settings),
    store: StubStateStore = Depends(get_stub_store),
) -> AuthTokenResponse:
    user = store.authenticate(payload.email, payload.password)
    token = create_access_token(user, settings=settings)
    return AuthTokenResponse(access_token=token, user=user)


@router.get("/me", response_model=UserProfile)
def get_me(current_user: UserProfile = Depends(get_current_user)) -> UserProfile:
    return current_user


@router.get("/dev-personas", response_model=list[UserProfile])
def list_dev_personas(
    settings: Settings = Depends(get_settings),
    store: StubStateStore = Depends(get_stub_store),
) -> list[UserProfile]:
    if not settings.is_dev_role_switcher_enabled:
        raise ApiError(
            status_code=404,
            code="NOT_FOUND",
            message="Endpoint not found.",
        )
    return store.list_personas()


@router.post("/dev-switch-role", response_model=AuthTokenResponse)
def dev_switch_role(
    payload: DevSwitchRoleRequest,
    settings: Settings = Depends(get_settings),
    store: StubStateStore = Depends(get_stub_store),
) -> AuthTokenResponse:
    if not settings.is_dev_role_switcher_enabled:
        raise ApiError(
            status_code=404,
            code="NOT_FOUND",
            message="Endpoint not found.",
        )
    user = store.get_persona(payload.persona_key)
    token = create_access_token(user, settings=settings)
    return AuthTokenResponse(access_token=token, user=user)

