"""Phase 2 OCR & Vision AI package (Owned by System 2).

Conforms strictly to `OCRServiceProtocol` and provides pluggable backends for:
- Google Gemini Flash / Pro (`GeminiOCRProvider`)
- OpenAI GPT-4o / GPT-4o-mini & OpenAI-compatible endpoints (`OpenAIOCRProvider`)
- Anthropic Claude 3.5 Sonnet / Haiku (`AnthropicOCRProvider`)
- Deterministic mock scanner for offline & local testing (`MockOCRProvider`)
"""

from __future__ import annotations

from app.ocr.anthropic_provider import AnthropicOCRProvider
from app.ocr.factory import get_ocr_provider
from app.ocr.gemini_provider import GeminiOCRProvider
from app.ocr.mock_provider import MockOCRProvider
from app.ocr.openai_provider import OpenAIOCRProvider
from app.ocr.protocol import ActiveCategoryItem, OCRServiceProtocol

__all__ = [
    "ActiveCategoryItem",
    "AnthropicOCRProvider",
    "GeminiOCRProvider",
    "MockOCRProvider",
    "OCRServiceProtocol",
    "OpenAIOCRProvider",
    "get_ocr_provider",
]
