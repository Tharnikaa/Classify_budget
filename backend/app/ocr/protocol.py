"""Frozen OCR adapter contract between System 1 (Backend) and System 2 (Phase 2 Vision AI).

System 2 implements `GeminiOCRProvider` inside `backend/app/ocr/gemini_provider.py`
conforming to `OCRServiceProtocol` without needing to modify `main.py` or DB migrations.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, TypedDict

from app.schemas.api import ExtractedReceipt


class ActiveCategoryItem(TypedDict):
    code: str
    name: str
    description: str


class OCRServiceProtocol(Protocol):
    async def extract_receipt(
        self,
        image_bytes: bytes,
        mime_type: str,
        active_categories: Sequence[ActiveCategoryItem],
    ) -> ExtractedReceipt:
        """Extract structured factual receipt data in INR paise from uploaded image bytes."""
        ...

