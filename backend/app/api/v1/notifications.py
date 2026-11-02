"""In-app notifications drawer and Expo push token registration routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_user
from app.schemas.api import NotificationItem, PushTokenRequest, UserProfile
from app.services.stub_store import StubStateStore, get_stub_store

router = APIRouter(prefix="/api/v1", tags=["Notifications"])


@router.get("/notifications", response_model=list[NotificationItem])
def list_notifications(
    unread_only: bool = Query(default=False),
    current_user: UserProfile = Depends(get_current_user),
    store: StubStateStore = Depends(get_stub_store),
) -> list[NotificationItem]:
    return store.notifications.list_for_user(current_user.id, unread_only=unread_only)


@router.post("/notifications/{notification_id}/read", response_model=NotificationItem)
def mark_notification_read(
    notification_id: str,
    current_user: UserProfile = Depends(get_current_user),
    store: StubStateStore = Depends(get_stub_store),
) -> NotificationItem:
    return store.notifications.mark_read(current_user.id, notification_id)


@router.post("/devices/push-token")
def register_push_token(
    payload: PushTokenRequest,
    current_user: UserProfile = Depends(get_current_user),
    store: StubStateStore = Depends(get_stub_store),
) -> dict[str, str]:
    store.notifications.register_push_token(
        current_user.id, payload.expo_push_token, payload.platform
    )
    return {"status": "registered"}

