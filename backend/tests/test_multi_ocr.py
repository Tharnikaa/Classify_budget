"""Unit tests for Phase 2 Multi-Model Vision AI OCR Pipeline (System 2)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.ocr.anthropic_provider import AnthropicOCRProvider
from app.ocr.base import (
    build_ocr_prompt,
    clean_json_text,
    compute_phash,
    compute_sha256,
    parse_and_validate_extraction,
)
from app.ocr.factory import get_ocr_provider
from app.ocr.gemini_provider import GeminiOCRProvider
from app.ocr.mock_provider import MockOCRProvider
from app.ocr.openai_provider import OpenAIOCRProvider
from app.schemas.api import ExtractedReceipt, ItemTagEnum

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "receipts"
SAMPLE_CATS = [
    {"code": "MEALS", "name": "Meals & Refreshments", "description": "Client food"},
    {"code": "TRAVEL", "name": "Travel & Commute", "description": "Cabs & flights"},
    {"code": "LODGING", "name": "Lodging & Hotel", "description": "Hotels"},
]


def test_hashing_and_phash_computation() -> None:
    sample_img = FIXTURES_DIR / "clean_meal.png"
    assert sample_img.exists(), f"Missing fixture {sample_img}"
    data = sample_img.read_bytes()

    sha = compute_sha256(data)
    assert len(sha) == 64
    assert sha == "082ec4a4bfb9fddbe46a39b7a640135bc10032ff853f864783856404efdc07d8"

    phash = compute_phash(data)
    assert len(phash) == 16
    assert isinstance(phash, str)


def test_clean_json_text_markdown_stripping() -> None:
    raw = "```json\n{\"test\": 123}\n```"
    cleaned = clean_json_text(raw)
    assert cleaned == '{"test": 123}'


def test_build_ocr_prompt_injects_categories() -> None:
    prompt = build_ocr_prompt(SAMPLE_CATS)
    assert 'Code: "MEALS"' in prompt
    assert 'Code: "TRAVEL"' in prompt
    assert "INR paise" in prompt


def test_parse_and_validate_extraction_inr() -> None:
    fake_json = json.dumps({
        "is_valid_receipt": True,
        "vendor_name": "Starbucks Coffee",
        "vendor_tax_id": "29AABCS1234F1Z1",
        "invoice_date": "2026-11-04",
        "detected_currency": "INR",
        "subtotal_amount_paise": 35000,
        "tax_amount_paise": 1750,
        "total_amount_paise": 36750,
        "suggested_category_code": "MEALS",
        "confidence_score": 0.98,
        "field_confidence": {
            "vendor": 0.99,
            "date": 0.98,
            "total": 0.99,
            "category": 0.96,
        },
        "line_items": [
            {
                "description": "Vanilla Latte Grande",
                "quantity": 1.0,
                "unit_price_paise": 35000,
                "amount_paise": 35000,
                "item_tag": "meal",
            }
        ],
    })
    dummy_bytes = b"fake-png-bytes"
    receipt = parse_and_validate_extraction(fake_json, dummy_bytes, SAMPLE_CATS)

    assert isinstance(receipt, ExtractedReceipt)
    assert receipt.vendor_name == "Starbucks Coffee"
    assert receipt.total_amount_paise == 36750
    assert receipt.suggested_category_code == "MEALS"
    assert len(receipt.line_items) == 1
    assert receipt.line_items[0].item_tag == ItemTagEnum.MEAL


@pytest.mark.anyio
async def test_mock_provider_offline() -> None:
    sample_img = FIXTURES_DIR / "clean_meal.png"
    data = sample_img.read_bytes()
    prov = MockOCRProvider()
    res = await prov.extract_receipt(data, "image/png", SAMPLE_CATS)

    assert res.is_valid_receipt is True
    assert res.suggested_category_code == "MEALS"
    assert res.total_amount_paise == 44100
    assert res.image_sha256 == compute_sha256(data)


@pytest.mark.anyio
async def test_gemini_provider_mocked_network() -> None:
    prov = GeminiOCRProvider(api_key="test-gemini-key")
    fake_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps({
                                "is_valid_receipt": True,
                                "vendor_name": "Gemini Cafe",
                                "invoice_date": "2026-11-04",
                                "detected_currency": "INR",
                                "subtotal_amount_paise": 15000,
                                "tax_amount_paise": 750,
                                "total_amount_paise": 15750,
                                "suggested_category_code": "MEALS",
                                "confidence_score": 0.95,
                                "field_confidence": {"vendor": 0.95, "date": 0.9, "total": 0.95, "category": 0.95},
                                "line_items": [
                                    {
                                        "description": "Cold Brew",
                                        "quantity": 1.0,
                                        "amount_paise": 15000,
                                        "item_tag": "meal",
                                    }
                                ],
                            })
                        }
                    ]
                }
            }
        ]
    }

    mock_resp = httpx.Response(status_code=200, json=fake_response)
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        receipt = await prov.extract_receipt(b"fake-bytes", "image/png", SAMPLE_CATS)

    assert receipt.vendor_name == "Gemini Cafe"
    assert receipt.total_amount_paise == 15750
    assert receipt.detected_currency == "INR"


@pytest.mark.anyio
async def test_openai_provider_mocked_network() -> None:
    prov = OpenAIOCRProvider(api_key="test-openai-key")
    fake_response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "is_valid_receipt": True,
                        "vendor_name": "OpenAI Subs",
                        "invoice_date": "2026-11-01",
                        "detected_currency": "USD",
                        "subtotal_amount_paise": 2000,
                        "tax_amount_paise": 0,
                        "total_amount_paise": 2000,
                        "suggested_category_code": "SOFTWARE_TOOLS",
                        "confidence_score": 0.99,
                        "field_confidence": {"vendor": 0.99, "date": 0.99, "total": 0.99, "category": 0.99},
                        "line_items": [
                            {
                                "description": "ChatGPT Plus",
                                "quantity": 1.0,
                                "amount_paise": 2000,
                                "item_tag": "software",
                            }
                        ],
                    })
                }
            }
        ]
    }

    mock_resp = httpx.Response(status_code=200, json=fake_response)
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        receipt = await prov.extract_receipt(b"fake-bytes", "image/jpeg", SAMPLE_CATS)

    assert receipt.vendor_name == "OpenAI Subs"
    assert receipt.detected_currency == "USD"
    assert receipt.line_items[0].item_tag == ItemTagEnum.SOFTWARE


@pytest.mark.anyio
async def test_anthropic_provider_mocked_network() -> None:
    prov = AnthropicOCRProvider(api_key="test-anthropic-key")
    fake_response = {
        "content": [
            {
                "type": "text",
                "text": json.dumps({
                    "is_valid_receipt": True,
                    "vendor_name": "Claude Hotel",
                    "invoice_date": "2026-11-03",
                    "detected_currency": "INR",
                    "subtotal_amount_paise": 500000,
                    "tax_amount_paise": 60000,
                    "total_amount_paise": 560000,
                    "suggested_category_code": "LODGING",
                    "confidence_score": 0.96,
                    "field_confidence": {"vendor": 0.98, "date": 0.95, "total": 0.97, "category": 0.96},
                    "line_items": [
                        {
                            "description": "Room Stay 1 Night",
                            "quantity": 1.0,
                            "amount_paise": 500000,
                            "item_tag": "lodging",
                        }
                    ],
                }),
            }
        ]
    }

    mock_resp = httpx.Response(status_code=200, json=fake_response)
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        receipt = await prov.extract_receipt(b"fake-bytes", "image/png", SAMPLE_CATS)

    assert receipt.vendor_name == "Claude Hotel"
    assert receipt.total_amount_paise == 560000
    assert receipt.suggested_category_code == "LODGING"


def test_factory_switching() -> None:
    with patch.dict("os.environ", {"OCR_PROVIDER": "gemini", "GEMINI_API_KEY": "dummy"}):
        p = get_ocr_provider()
        assert isinstance(p, GeminiOCRProvider)

    with patch.dict("os.environ", {"OCR_PROVIDER": "openai", "OPENAI_API_KEY": "dummy"}):
        p = get_ocr_provider()
        assert isinstance(p, OpenAIOCRProvider)

    with patch.dict("os.environ", {"OCR_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "dummy"}):
        p = get_ocr_provider()
        assert isinstance(p, AnthropicOCRProvider)

    with patch.dict("os.environ", {"OCR_PROVIDER": "mock"}):
        p = get_ocr_provider()
        assert isinstance(p, MockOCRProvider)
