"""Dynamic Categories, Spend Tier Limits, and IST Monthly Quota routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_user, require_roles
from app.schemas.api import (
    CategoryItem,
    CreateCategoryRequest,
    MonthlyQuotaSummary,
    PolicyLimitsResponse,
    RoleEnum,
    UpdatePolicyLimitsRequest,
    UserProfile,
)
from app.services.stub_store import StubStateStore, get_stub_store

router = APIRouter(prefix="/api/v1", tags=["Policies"])


@router.get("/categories", response_model=list[CategoryItem])
def list_categories(
    _current_user: UserProfile = Depends(get_current_user),
    store: StubStateStore = Depends(get_stub_store),
) -> list[CategoryItem]:
    return store.list_categories(active_only=True)


@router.post("/categories", response_model=CategoryItem, status_code=201)
def create_category(
    payload: CreateCategoryRequest,
    actor: UserProfile = Depends(require_roles(RoleEnum.FINANCE_MANAGER)),
    store: StubStateStore = Depends(get_stub_store),
) -> CategoryItem:
    return store.create_category(actor, payload)


@router.get("/policies/limits", response_model=PolicyLimitsResponse)
def get_policy_limits(
    _current_user: UserProfile = Depends(get_current_user),
    store: StubStateStore = Depends(get_stub_store),
) -> PolicyLimitsResponse:
    return store.get_policy_limits()


@router.put("/policies/limits", response_model=PolicyLimitsResponse)
def update_policy_limits(
    payload: UpdatePolicyLimitsRequest,
    actor: UserProfile = Depends(require_roles(RoleEnum.FINANCE_MANAGER)),
    store: StubStateStore = Depends(get_stub_store),
) -> PolicyLimitsResponse:
    return store.update_policy_limits(actor, payload)


@router.get("/quotas/me", response_model=MonthlyQuotaSummary)
def get_my_quota(
    year_month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    current_user: UserProfile = Depends(get_current_user),
    store: StubStateStore = Depends(get_stub_store),
) -> MonthlyQuotaSummary:
    return store.get_monthly_quota(current_user, year_month=year_month)

