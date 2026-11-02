"""Expense claims precheck, CRUD, and withdrawal endpoints."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Header, Query

from app.core.security import get_current_user
from app.schemas.api import (
    ClaimPrecheckRequest,
    ClaimPrecheckResponse,
    ClaimStatusEnum,
    CreateClaimRequest,
    ExpenseClaim,
    UpdateClaimRequest,
    UserProfile,
)
from app.services.stub_store import StubStateStore, get_stub_store

router = APIRouter(prefix="/api/v1/claims", tags=["Claims"])


@router.post("/precheck", response_model=ClaimPrecheckResponse)
def precheck_claim(
    payload: ClaimPrecheckRequest,
    current_user: UserProfile = Depends(get_current_user),
    store: StubStateStore = Depends(get_stub_store),
) -> ClaimPrecheckResponse:
    return store.precheck_claim(current_user, payload)


@router.get("", response_model=list[ExpenseClaim])
def list_claims(
    status: ClaimStatusEnum | None = Query(default=None),
    scope: Literal["mine", "queue", "all"] | None = Query(default=None),
    current_user: UserProfile = Depends(get_current_user),
    store: StubStateStore = Depends(get_stub_store),
) -> list[ExpenseClaim]:
    return store.list_claims(current_user, status=status, scope=scope)


@router.post("", response_model=ExpenseClaim, status_code=201)
def create_claim(
    payload: CreateClaimRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: UserProfile = Depends(get_current_user),
    store: StubStateStore = Depends(get_stub_store),
) -> ExpenseClaim:
    return store.create_claim(current_user, payload, idempotency_key=idempotency_key)


@router.get("/{claim_id}", response_model=ExpenseClaim)
def get_claim(
    claim_id: str,
    current_user: UserProfile = Depends(get_current_user),
    store: StubStateStore = Depends(get_stub_store),
) -> ExpenseClaim:
    return store.get_claim(current_user, claim_id)


@router.patch("/{claim_id}", response_model=ExpenseClaim)
def update_claim(
    claim_id: str,
    payload: UpdateClaimRequest,
    current_user: UserProfile = Depends(get_current_user),
    store: StubStateStore = Depends(get_stub_store),
) -> ExpenseClaim:
    return store.update_claim(current_user, claim_id, payload)


@router.post("/{claim_id}/withdraw", response_model=ExpenseClaim)
def withdraw_claim(
    claim_id: str,
    current_user: UserProfile = Depends(get_current_user),
    store: StubStateStore = Depends(get_stub_store),
) -> ExpenseClaim:
    return store.withdraw_claim(current_user, claim_id)

