"""Receipt upload, OCR extraction, mock scan presets, and authenticated image serving."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Response, UploadFile

from app.core.security import get_current_user
from app.schemas.api import ExtractedReceipt, MockScanRequest, UserProfile
from app.services.stub_store import StubStateStore, get_stub_store

router = APIRouter(prefix="/api/v1", tags=["OCR"])


@router.post("/ocr/scan", response_model=ExtractedReceipt)
async def scan_receipt(
    file: UploadFile = File(...),
    _current_user: UserProfile = Depends(get_current_user),
    store: StubStateStore = Depends(get_stub_store),
) -> ExtractedReceipt:
    image_bytes = await file.read()
    return await store.scan_uploaded_receipt(image_bytes)


@router.post("/ocr/mock-scan", response_model=ExtractedReceipt)
def mock_scan_receipt(
    payload: MockScanRequest,
    _current_user: UserProfile = Depends(get_current_user),
    store: StubStateStore = Depends(get_stub_store),
) -> ExtractedReceipt:
    return store.create_mock_scan(payload.preset)


@router.get("/receipts/{receipt_id}/image")
def get_receipt_image(
    receipt_id: str,
    _current_user: UserProfile = Depends(get_current_user),
    store: StubStateStore = Depends(get_stub_store),
) -> Response:
    data, mime_type = store.storage.read_receipt(receipt_id)
    return Response(content=data, media_type=mime_type)

