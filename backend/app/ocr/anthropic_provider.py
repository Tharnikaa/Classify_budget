"""Anthropic Claude (Claude 3.5 Sonnet / Haiku) Vision OCR Provider."""

from __future__ import annotations

import base64
from collections.abc import Sequence

import httpx

from app.core.errors import ApiError
from app.ocr.base import build_ocr_prompt, parse_and_validate_extraction
from app.ocr.protocol import ActiveCategoryItem, OCRServiceProtocol
from app.schemas.api import ExtractedReceipt


class AnthropicOCRProvider(OCRServiceProtocol):
    """Anthropic Claude multimodal receipt extractor."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "claude-3-5-sonnet-20241022",
        timeout_seconds: float = 30.0,
    ) -> None:
        self.api_key = api_key.strip()
        self.model_name = model_name.strip() or "claude-3-5-sonnet-20241022"
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
                code="OCR_ANTHROPIC_KEY_MISSING",
                message="ANTHROPIC_API_KEY is not configured.",
            )

        prompt = build_ocr_prompt(active_categories)
        b64_img = base64.b64encode(image_bytes).decode("ascii")

        norm_mime = mime_type.lower()
        if "png" in norm_mime:
            norm_mime = "image/png"
        elif "webp" in norm_mime:
            norm_mime = "image/webp"
        else:
            norm_mime = "image/jpeg"

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        payload = {
            "model": self.model_name,
            "max_tokens": 4096,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": norm_mime,
                                "data": b64_img,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            "temperature": 0.1,
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            try:
                resp = await client.post(url, headers=headers, json=payload)
            except httpx.RequestError as exc:
                raise ApiError(
                    status_code=502,
                    code="OCR_ANTHROPIC_NETWORK_ERROR",
                    message=f"Anthropic API network error: {exc}",
                ) from exc

        if resp.status_code != 200:
            error_detail = resp.text[:300]
            raise ApiError(
                status_code=502,
                code="OCR_ANTHROPIC_API_ERROR",
                message=f"Anthropic API returned HTTP {resp.status_code}: {error_detail}",
            )

        try:
            data = resp.json()
            content_blocks = data.get("content") or []
            text_blocks = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
            combined_text = "\n".join(text_blocks)
        except Exception as exc:
            raise ApiError(
                status_code=502,
                code="OCR_ANTHROPIC_PARSE_ERROR",
                message=f"Failed to read Anthropic response: {exc}",
            ) from exc

        return parse_and_validate_extraction(
            raw_text=combined_text,
            image_bytes=image_bytes,
            active_categories=active_categories,
        )
