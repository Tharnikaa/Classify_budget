"""OpenAI & OpenAI-Compatible (Ollama, vLLM, LiteLLM) Vision OCR Provider."""

from __future__ import annotations

import base64
from collections.abc import Sequence

import httpx

from app.core.errors import ApiError
from app.ocr.base import build_ocr_prompt, parse_and_validate_extraction
from app.ocr.protocol import ActiveCategoryItem, OCRServiceProtocol
from app.schemas.api import ExtractedReceipt


class OpenAIOCRProvider(OCRServiceProtocol):
    """OpenAI Vision & OpenAI-compatible (Ollama/vLLM) receipt extractor."""

    def __init__(
        self,
        api_key: str = "",
        model_name: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 30.0,
    ) -> None:
        self.api_key = api_key.strip()
        self.model_name = model_name.strip() or "gpt-4o-mini"
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def extract_receipt(
        self,
        image_bytes: bytes,
        mime_type: str,
        active_categories: Sequence[ActiveCategoryItem],
    ) -> ExtractedReceipt:
        # For non-local endpoints, api_key is required
        is_local = "localhost" in self.base_url or "127.0.0.1" in self.base_url
        if not is_local and not self.api_key:
            raise ApiError(
                status_code=500,
                code="OCR_OPENAI_KEY_MISSING",
                message="OPENAI_API_KEY is not configured.",
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

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{norm_mime};base64,{b64_img}"},
                        },
                    ],
                }
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            try:
                resp = await client.post(url, headers=headers, json=payload)
            except httpx.RequestError as exc:
                raise ApiError(
                    status_code=502,
                    code="OCR_OPENAI_NETWORK_ERROR",
                    message=f"OpenAI API network error: {exc}",
                ) from exc

        if resp.status_code != 200:
            error_detail = resp.text[:300]
            raise ApiError(
                status_code=502,
                code="OCR_OPENAI_API_ERROR",
                message=f"OpenAI API returned HTTP {resp.status_code}: {error_detail}",
            )

        try:
            data = resp.json()
            choices = data.get("choices") or []
            if not choices:
                raise ValueError("No choices returned by OpenAI Vision model.")
            content = choices[0].get("message", {}).get("content", "")
        except Exception as exc:
            raise ApiError(
                status_code=502,
                code="OCR_OPENAI_PARSE_ERROR",
                message=f"Failed to read OpenAI response: {exc}",
            ) from exc

        return parse_and_validate_extraction(
            raw_text=content,
            image_bytes=image_bytes,
            active_categories=active_categories,
        )
