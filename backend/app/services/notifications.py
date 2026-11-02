"""NotificationService abstraction (in-app drawer polling + Expo Push token registry)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from app.core.errors import ApiError
from app.schemas.api import NotificationItem, NotificationTypeEnum


class NotificationServiceProtocol(Protocol):
    def notify(
        self,
        *,
        user_id: str,
        notif_type: NotificationTypeEnum,
        title: str,
        message: str,
        actor_id: str | None = None,
        claim_id: str | None = None,
    ) -> NotificationItem: ...

    def list_for_user(self, user_id: str, unread_only: bool = False) -> list[NotificationItem]: ...
    def mark_read(self, user_id: str, notification_id: str) -> NotificationItem: ...
    def register_push_token(self, user_id: str, token: str, platform: str) -> None: ...


class InMemoryNotificationService(NotificationServiceProtocol):
    def __init__(self) -> None:
        self._items: list[NotificationItem] = []
        self._push_tokens: dict[str, set[tuple[str, str]]] = {}

    def seed(self, item: NotificationItem) -> None:
        self._items.append(item)

    def notify(
        self,
        *,
        user_id: str,
        notif_type: NotificationTypeEnum,
        title: str,
        message: str,
        actor_id: str | None = None,
        claim_id: str | None = None,
    ) -> NotificationItem:
        deep_link = f"expenseit://claims/{claim_id}" if claim_id else "expenseit://notifications"
        item = NotificationItem(
            id=f"notif-{uuid4().hex[:12]}",
            user_id=user_id,
            actor_id=actor_id,
            type=notif_type,
            title=title,
            message=message,
            claim_id=claim_id,
            deep_link=deep_link,
            is_read=False,
            created_at=datetime.now(UTC).isoformat(),
        )
        self._items.insert(0, item)
        return item

    def list_for_user(self, user_id: str, unread_only: bool = False) -> list[NotificationItem]:
        results = [n for n in self._items if n.user_id == user_id]
        if unread_only:
            results = [n for n in results if not n.is_read]
        return results

    def mark_read(self, user_id: str, notification_id: str) -> NotificationItem:
        for idx, item in enumerate(self._items):
            if item.id == notification_id and item.user_id == user_id:
                updated = item.model_copy(update={"is_read": True})
                self._items[idx] = updated
                return updated
        raise ApiError(
            status_code=404,
            code="NOTIFICATION_NOT_FOUND",
            message=f"Notification '{notification_id}' not found for user.",
        )

    def register_push_token(self, user_id: str, token: str, platform: str) -> None:
        self._push_tokens.setdefault(user_id, set()).add((token, platform))

