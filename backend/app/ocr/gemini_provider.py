"""Phase 2 Gemini Flash Multimodal OCR implementation target (Owned by System 2).

Phase 0 provides this clean adapter skeleton so System 2 can implement Gemini structured
extraction in `feature/phase-2-ocr-pipeline` while Phase 0/5 uses `MockOCRProvider` when
`GEMINI_API_KEY` is unset.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.core.errors import ApiError
from app.ocr.protocol import ActiveCategoryItem, OCRServiceProtocol
from app.schemas.api import ExtractedReceipt


class GeminiOCRProvider(OCRServiceProtocol):
    """Gemini Flash Multimodal receipt extractor (System 2 Phase 2 deliverable)."""

    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash") -> None:
        self.api_key = api_key
        self.model_name = model_name

    async def extract_receipt(
        self,
        image_bytes: bytes,
        mime_type: str,
        active_categories: Sequence[ActiveCategoryItem],
    ) -> ExtractedReceipt:
        raise ApiError(
            status_code=501,
            code="OCR_GEMINI_NOT_IMPLEMENTED",
            message=(
                "GeminiOCRProvider is the Phase 2 implementation target in "
                "backend/app/ocr/gemini_provider.py. Use MockOCRProvider in Phase 0."
            ),
        )

