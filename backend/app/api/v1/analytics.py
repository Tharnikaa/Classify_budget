"""Enterprise analytics overview and immutable audit log routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import require_roles
from app.schemas.api import AnalyticsOverviewResponse, ClaimEvent, RoleEnum, UserProfile
from app.services.stub_store import StubStateStore, get_stub_store

router = APIRouter(prefix="/api/v1", tags=["Analytics"])


@router.get("/analytics/overview", response_model=AnalyticsOverviewResponse)
def get_analytics_overview(
    _actor: UserProfile = Depends(require_roles(RoleEnum.FINANCE_HEAD, RoleEnum.FINANCE_MANAGER)),
    store: StubStateStore = Depends(get_stub_store),
) -> AnalyticsOverviewResponse:
    return store.get_analytics_overview()


@router.get("/audit-logs", response_model=list[ClaimEvent])
def list_audit_logs(
    _actor: UserProfile = Depends(require_roles(RoleEnum.FINANCE_HEAD)),
    store: StubStateStore = Depends(get_stub_store),
) -> list[ClaimEvent]:
    return store.list_audit_logs()
