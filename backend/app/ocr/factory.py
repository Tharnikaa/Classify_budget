"""OCR Provider Factory supporting Gemini, OpenAI, Claude, Ollama, and Mock fixtures."""

from __future__ import annotations

import os
from typing import Any

from app.ocr.anthropic_provider import AnthropicOCRProvider
from app.ocr.gemini_provider import GeminiOCRProvider
from app.ocr.mock_provider import MockOCRProvider
from app.ocr.openai_provider import OpenAIOCRProvider
from app.ocr.protocol import OCRServiceProtocol


def get_ocr_provider(
    provider_name: str | None = None,
    allow_mock_fallback: bool = True,
    **kwargs: Any,
) -> OCRServiceProtocol:
    """Instantiate and return the configured Vision AI OCR provider.

    Resolution Priority:
    1. Explicit `provider_name` argument if supplied.
    2. Environment variable `OCR_PROVIDER` (gemini | openai | anthropic | ollama | mock).
    3. Auto-detection based on presence of API keys (GEMINI_API_KEY -> OPENAI_API_KEY -> ANTHROPIC_API_KEY).
    4. Fallback to `MockOCRProvider` if no keys are found and `allow_mock_fallback=True`.
    """
    prov = (provider_name or os.getenv("OCR_PROVIDER", "")).strip().lower()

    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    base_url = os.getenv("OCR_BASE_URL", "http://localhost:11434/v1").strip()

    # Auto-detect if provider name is not explicitly forced
    if not prov:
        if gemini_key:
            prov = "gemini"
        elif openai_key:
            prov = "openai"
        elif anthropic_key:
            prov = "anthropic"
        elif os.getenv("OCR_BASE_URL"):
            prov = "ollama"
        else:
            prov = "mock"

    if prov == "gemini":
        model = kwargs.get("model_name") or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        key = kwargs.get("api_key") or gemini_key
        return GeminiOCRProvider(api_key=key, model_name=model)

    if prov in ("openai", "gpt"):
        model = kwargs.get("model_name") or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        key = kwargs.get("api_key") or openai_key
        url = kwargs.get("base_url") or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        return OpenAIOCRProvider(api_key=key, model_name=model, base_url=url)

    if prov in ("anthropic", "claude"):
        model = kwargs.get("model_name") or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        key = kwargs.get("api_key") or anthropic_key
        return AnthropicOCRProvider(api_key=key, model_name=model)

    if prov in ("ollama", "local", "openai_compatible"):
        model = kwargs.get("model_name") or os.getenv("OCR_MODEL", "qwen2-vl")
        key = kwargs.get("api_key") or os.getenv("OCR_API_KEY", "ollama")
        url = kwargs.get("base_url") or base_url
        return OpenAIOCRProvider(api_key=key, model_name=model, base_url=url)

    if allow_mock_fallback or prov == "mock":
        return MockOCRProvider()

    raise ValueError(f"Unknown OCR provider '{prov}' and fallback is disabled.")
