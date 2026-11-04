"""Google Gemini Flash/Pro Multimodal Vision AI OCR Provider (System 2 Phase 2)."""

from __future__ import annotations

import base64
from collections.abc import Sequence

import httpx

from app.core.errors import ApiError
from app.ocr.base import build_ocr_prompt, parse_and_validate_extraction
from app.ocr.protocol import ActiveCategoryItem, OCRServiceProtocol
from app.schemas.api import ExtractedReceipt


class GeminiOCRProvider(OCRServiceProtocol):
    """Gemini Flash Multimodal receipt extractor with structured JSON output."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.5-flash",
        timeout_seconds: float = 30.0,
    ) -> None:
        self.api_key = api_key.strip()
        self.model_name = model_name.strip() or "gemini-2.5-flash"
        self.timeout_seconds = timeout_seconds

    async def extract_receipt(
        self,
        image_bytes: bytes,
        mime_type: str,
        active_categories: Sequence[ActiveCategoryItem],
    ) -> ExtractedReceipt:
        if not self.api_key:
            raise ApiError(
                status_code=500,
                code="OCR_GEMINI_KEY_MISSING",
                message="GEMINI_API_KEY is not configured.",
            )

        prompt = build_ocr_prompt(active_categories)
        b64_img = base64.b64encode(image_bytes).decode("ascii")

        # Normalize mime type for Gemini
        norm_mime = mime_type.lower()
        if "png" in norm_mime:
            norm_mime = "image/png"
        elif "webp" in norm_mime:
            norm_mime = "image/webp"
        elif "heic" in norm_mime or "heif" in norm_mime:
            norm_mime = "image/heic"
        else:
            norm_mime = "image/jpeg"

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": norm_mime,
                                "data": b64_img,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.1,
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            try:
                resp = await client.post(url, json=payload)
            except httpx.RequestError as exc:
                raise ApiError(
                    status_code=502,
                    code="OCR_GEMINI_NETWORK_ERROR",
                    message=f"Gemini API network error: {exc}",
                ) from exc

        if resp.status_code != 200:
            error_detail = resp.text[:300]
            raise ApiError(
                status_code=502,
                code="OCR_GEMINI_API_ERROR",
                message=f"Gemini API returned HTTP {resp.status_code}: {error_detail}",
            )

        try:
            data = resp.json()
            candidates = data.get("candidates") or []
            if not candidates:
                raise ValueError("No candidates returned by Gemini Vision model.")
            parts = candidates[0].get("content", {}).get("parts") or []
            if not parts:
                raise ValueError("Empty candidate content parts from Gemini.")
            text_response = parts[0].get("text", "")
        except Exception as exc:
            raise ApiError(
                status_code=502,
                code="OCR_GEMINI_PARSE_ERROR",
                message=f"Failed to read Gemini response: {exc}",
            ) from exc

        return parse_and_validate_extraction(
            raw_text=text_response,
            image_bytes=image_bytes,
            active_categories=active_categories,
        )
