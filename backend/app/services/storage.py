"""Authenticated Receipt Image StorageService (Local disk in dev; S3/GCS ready)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.core.errors import ApiError

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


@dataclass(frozen=True)
class StoredReceiptFile:
    receipt_id: str
    mime_type: str
    sha256: str
    size_bytes: int
    file_path: Path


def detect_image_mime(data: bytes) -> str:
    """Verify magic bytes rather than trusting client Content-Type headers."""
    if len(data) < 12:
        raise ApiError(status_code=400, code="INVALID_IMAGE", message="Uploaded file is too small.")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[4:8] == b"ftyp" and data[8:12] in {b"heic", b"heix", b"mif1", b"msf1"}:
        return "image/heic"
    raise ApiError(
        status_code=400,
        code="UNSUPPORTED_MEDIA_TYPE",
        message="Only PNG, JPEG, WEBP, and HEIC receipt images are accepted.",
    )


class StorageServiceProtocol(Protocol):
    def save_receipt(self, receipt_id: str, data: bytes) -> StoredReceiptFile: ...
    def read_receipt(self, receipt_id: str) -> tuple[bytes, str]: ...


class LocalDiskStorageService(StorageServiceProtocol):
    """Stores receipt images outside public static mounts; served via authenticated route."""

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._index: dict[str, StoredReceiptFile] = {}

    def save_receipt(self, receipt_id: str, data: bytes) -> StoredReceiptFile:
        if len(data) > MAX_UPLOAD_BYTES:
            raise ApiError(
                status_code=413,
                code="FILE_TOO_LARGE",
                message="Receipt image exceeds 10 MB maximum upload limit.",
            )
        mime_type = detect_image_mime(data)
        ext = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/webp": ".webp",
            "image/heic": ".heic",
        }[mime_type]
        sha = hashlib.sha256(data).hexdigest()
        dest = self.base_dir / f"{receipt_id}{ext}"
        dest.write_bytes(data)
        meta = StoredReceiptFile(
            receipt_id=receipt_id,
            mime_type=mime_type,
            sha256=sha,
            size_bytes=len(data),
            file_path=dest,
        )
        self._index[receipt_id] = meta
        return meta

    def read_receipt(self, receipt_id: str) -> tuple[bytes, str]:
        meta = self._index.get(receipt_id)
        if meta and meta.file_path.exists():
            return meta.file_path.read_bytes(), meta.mime_type
        raise ApiError(
            status_code=404,
            code="RECEIPT_IMAGE_NOT_FOUND",
            message=f"Receipt image '{receipt_id}' not found.",
        )

