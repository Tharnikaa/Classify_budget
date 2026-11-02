"""Multi-tier SoD claim workflow routes (approve, return, reject, verify, override, dispatch)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header

from app.core.security import require_roles
from app.schemas.api import (
    DispatchFundsRequest,
    ExpenseClaim,
    FinanceHeadOverrideRequest,
    RoleEnum,
    UserProfile,
    WorkflowCommentRequest,
    WorkflowReasonRequest,
)
from app.services.stub_store import StubStateStore, get_stub_store

router = APIRouter(prefix="/api/v1/claims", tags=["Workflow"])


@router.post("/{claim_id}/approve", response_model=ExpenseClaim)
def approve_claim(
    claim_id: str,
    payload: WorkflowCommentRequest | None = None,
    actor: UserProfile = Depends(require_roles(RoleEnum.DEPT_HEAD, RoleEnum.FINANCE_HEAD)),
    store: StubStateStore = Depends(get_stub_store),
) -> ExpenseClaim:
    return store.approve_claim(actor, claim_id, comment=payload.comment if payload else None)


@router.post("/{claim_id}/return", response_model=ExpenseClaim)
def return_claim(
    claim_id: str,
    payload: WorkflowReasonRequest,
    actor: UserProfile = Depends(require_roles(RoleEnum.DEPT_HEAD, RoleEnum.FINANCE_HEAD)),
    store: StubStateStore = Depends(get_stub_store),
) -> ExpenseClaim:
    return store.return_claim(actor, claim_id, reason=payload.reason)


@router.post("/{claim_id}/reject", response_model=ExpenseClaim)
def reject_claim(
    claim_id: str,
    payload: WorkflowReasonRequest,
    actor: UserProfile = Depends(require_roles(RoleEnum.DEPT_HEAD, RoleEnum.FINANCE_HEAD)),
    store: StubStateStore = Depends(get_stub_store),
) -> ExpenseClaim:
    return store.reject_claim(actor, claim_id, reason=payload.reason)


@router.post("/{claim_id}/verify", response_model=ExpenseClaim)
def verify_claim(
    claim_id: str,
    payload: WorkflowCommentRequest | None = None,
    actor: UserProfile = Depends(require_roles(RoleEnum.FINANCE_MANAGER)),
    store: StubStateStore = Depends(get_stub_store),
) -> ExpenseClaim:
    return store.verify_claim(actor, claim_id, comment=payload.comment if payload else None)


@router.post("/{claim_id}/override", response_model=ExpenseClaim)
def override_claim(
    claim_id: str,
    payload: FinanceHeadOverrideRequest,
    actor: UserProfile = Depends(require_roles(RoleEnum.FINANCE_HEAD)),
    store: StubStateStore = Depends(get_stub_store),
) -> ExpenseClaim:
    return store.override_claim(actor, claim_id, payload)


@router.post("/{claim_id}/dispatch", response_model=ExpenseClaim)
def dispatch_claim(
    claim_id: str,
    payload: DispatchFundsRequest | None = None,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    actor: UserProfile = Depends(require_roles(RoleEnum.FINANCE_MANAGER)),
    store: StubStateStore = Depends(get_stub_store),
) -> ExpenseClaim:
    return store.dispatch_claim(actor, claim_id, req=payload, idempotency_key=idempotency_key)

