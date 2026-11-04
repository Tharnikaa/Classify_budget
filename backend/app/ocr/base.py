"""Common utilities, hashing, prompt generation, and validation for Vision AI OCR."""

from __future__ import annotations

import hashlib
import io
import json
import re
from collections.abc import Sequence
from typing import Any

from PIL import Image

from app.ocr.protocol import ActiveCategoryItem
from app.schemas.api import (
    ExtractedLineItem,
    ExtractedReceipt,
    FieldConfidence,
    ItemTagEnum,
)

SYSTEM_OCR_PROMPT = """You are an expert corporate expense receipt extraction AI for the ExpenseIt system.
Your task is to analyze the receipt image and extract structured data accurately.

CURRENCY & MONETARY PRECISION:
- All monetary values must be represented as INTEGERS in minor units: INR paise (1 INR = 100 paise).
- CRITICAL: Always multiply the printed currency amount by 100 to get paise!
  * Example: ₹420.00 or 420/- -> 42000 paise (NEVER write 420).
  * Example: ₹21.50 -> 2150 paise.
  * Example: ₹441.00 -> 44100 paise.
  * Example: $15.00 -> 1500 cents (with detected_currency="USD").
- Ensure: total_amount_paise == subtotal_amount_paise + tax_amount_paise (or closest matching breakdown).

CATEGORIES:
Choose the single best matching category code for `suggested_category_code` strictly from this active list:
{active_categories_text}

FACTUAL LINE ITEMS & TAGGING:
Extract all identifiable line items. For each item, assign an `item_tag` from only these allowed tags:
- "meal" (food, non-alcoholic drinks, restaurant food)
- "alcohol" (beer, wine, spirits, cocktails, minibar alcohol)
- "tobacco" (cigarettes, cigars, vape)
- "gift_card" (prepaid cards, vouchers)
- "personal" (clothing, toiletries, personal electronics)
- "lodging" (hotel rooms, accommodation)
- "transport" (flights, taxi, train, fuel, parking, tolls)
- "office_supply" (stationery, printing, office materials)
- "software" (SaaS subscriptions, dev tools, cloud licenses)
- "telecom" (internet, phone bills, SIM charges)
- "tax_fee" (standalone service charges, GST/VAT lines if separated)
- "other" (any other business expense)

CONFIDENCE SCORES:
Provide field confidence scores between 0.0 (unreadable/guessed) and 1.0 (crystal clear):
- `vendor`: confidence in vendor name
- `date`: confidence in invoice date
- `total`: confidence in total amount
- `category`: confidence in assigned category

VALIDITY:
- If the image is blurry, corrupted, or not a receipt, set `is_valid_receipt: false`.
- If the vendor or date cannot be determined with certainty, set them to null.
- Date must be in ISO format: "YYYY-MM-DD" if present.

Return ONLY a valid JSON object matching this schema without any markdown formatting or commentary:
{
  "is_valid_receipt": true,
  "vendor_name": "Vendor Name or null",
  "vendor_tax_id": "GSTIN/Tax ID or null",
  "invoice_date": "YYYY-MM-DD or null",
  "detected_currency": "INR",
  "subtotal_amount_paise": 0,
  "tax_amount_paise": 0,
  "total_amount_paise": 0,
  "suggested_category_code": "CODE",
  "confidence_score": 0.95,
  "field_confidence": {
    "vendor": 0.95,
    "date": 0.95,
    "total": 0.95,
    "category": 0.95
  },
  "line_items": [
    {
      "description": "Item description",
      "quantity": 1.0,
      "unit_price_paise": 0,
      "amount_paise": 0,
      "item_tag": "meal"
    }
  ]
}
"""


def compute_sha256(data: bytes) -> str:
    """Compute SHA-256 hexadecimal checksum of image bytes."""
    return hashlib.sha256(data).hexdigest()


def compute_phash(image_bytes: bytes) -> str:
    """Compute a 64-bit difference hash (dHash) as a 16-character hex string.

    Uses PIL to resize the image to 9x8 grayscale, comparing adjacent pixels
    horizontally. Robust to scaling, aspect ratio, and minor compression artifacts.
    """
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            img = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
            pixels = list(img.getdata())

        difference: list[bool] = []
        for row in range(8):
            for col in range(8):
                pixel_left = pixels[row * 9 + col]
                pixel_right = pixels[row * 9 + col + 1]
                difference.append(pixel_left > pixel_right)

        decimal_value = 0
        for bit in difference:
            decimal_value = (decimal_value << 1) | int(bit)

        return f"{decimal_value:016x}"
    except Exception:
        # Fallback to standard hash if Pillow cannot open image bytes
        return hashlib.md5(image_bytes).hexdigest()[:16]  # noqa: S324


def build_ocr_prompt(active_categories: Sequence[ActiveCategoryItem]) -> str:
    """Build the dynamic prompt injecting runtime categories."""
    if active_categories:
        cats_text = "\n".join(
            f'- Code: "{c["code"]}" | Name: {c["name"]} ({c.get("description", "")})'
            for c in active_categories
        )
    else:
        cats_text = (
            '- Code: "MEALS" | Name: Meals & Refreshments\n'
            '- Code: "TRAVEL" | Name: Travel & Commute\n'
            '- Code: "LODGING" | Name: Lodging & Hotel\n'
            '- Code: "OFFICE_SUPPLIES" | Name: Office Supplies\n'
            '- Code: "SOFTWARE_TOOLS" | Name: Software Tools\n'
            '- Code: "INTERNET_PHONE" | Name: Internet & Phone\n'
            '- Code: "OTHER" | Name: Other Business Expenses'
        )
    return SYSTEM_OCR_PROMPT.replace("{active_categories_text}", cats_text)


def clean_json_text(text: str) -> str:
    """Strip markdown code fence blocks if returned by the LLM."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def parse_and_validate_extraction(
    raw_text: str,
    image_bytes: bytes,
    active_categories: Sequence[ActiveCategoryItem],
) -> ExtractedReceipt:
    """Parse JSON string from Vision AI model, enforce paise invariants, and validate."""
    cleaned = clean_json_text(raw_text)
    try:
        data: dict[str, Any] = json.loads(cleaned)
    except json.JSONDecodeError:
        # Attempt regex extraction if model enclosed JSON in narrative text
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
        else:
            raise ValueError(f"Failed to parse JSON from model response: {cleaned[:200]}") from None

    # Calculate image hashes
    sha = compute_sha256(image_bytes)
    phash = compute_phash(image_bytes)

    # Ensure field confidence structure
    fc = data.get("field_confidence") or {}
    field_confidence = FieldConfidence(
        vendor=float(fc.get("vendor", 0.8)),
        date=float(fc.get("date", 0.8)),
        total=float(fc.get("total", 0.8)),
        category=float(fc.get("category", 0.8)),
    )

    # Validate suggested category exists in active categories
    valid_codes = {c["code"] for c in active_categories}
    suggested_code = str(data.get("suggested_category_code", "OTHER")).upper()
    if valid_codes and suggested_code not in valid_codes:
        suggested_code = next(iter(valid_codes))

    # Parse and validate line items
    raw_items = data.get("line_items") or []
    line_items: list[ExtractedLineItem] = []
    computed_subtotal = 0

    for item in raw_items:
        desc = str(item.get("description", "Item")).strip() or "Item"
        qty = float(item.get("quantity", 1.0))
        amt_paise = int(item.get("amount_paise", 0))
        unit_paise = item.get("unit_price_paise")
        if unit_paise is not None:
            unit_paise = int(unit_paise)

        # Normalize tag to ItemTagEnum
        tag_val = str(item.get("item_tag", "other")).lower()
        try:
            tag = ItemTagEnum(tag_val)
        except ValueError:
            tag = ItemTagEnum.OTHER

        line_items.append(
            ExtractedLineItem(
                description=desc,
                quantity=qty,
                unit_price_paise=unit_paise,
                amount_paise=amt_paise,
                item_tag=tag,
            )
        )
        computed_subtotal += amt_paise

    total_paise = int(data.get("total_amount_paise", 0))
    tax_paise = int(data.get("tax_amount_paise", 0))
    subtotal_paise = data.get("subtotal_amount_paise")
    if subtotal_paise is not None:
        subtotal_paise = int(subtotal_paise)
    else:
        subtotal_paise = computed_subtotal if computed_subtotal > 0 else (total_paise - tax_paise)

    # Ensure total is at least subtotal + tax if total was 0
    if total_paise == 0 and (subtotal_paise + tax_paise) > 0:
        total_paise = subtotal_paise + tax_paise

    confidence_score = float(data.get("confidence_score", 0.85))
    confidence_score = max(0.0, min(1.0, confidence_score))

    return ExtractedReceipt(
        schema_version="1.0.0",
        receipt_id="",  # Will be assigned by storage service
        image_url=None,
        image_sha256=sha,
        image_phash=phash,
        is_valid_receipt=bool(data.get("is_valid_receipt", True)),
        vendor_name=data.get("vendor_name"),
        vendor_tax_id=data.get("vendor_tax_id"),
        invoice_date=data.get("invoice_date"),
        detected_currency=str(data.get("detected_currency", "INR")).upper(),
        subtotal_amount_paise=subtotal_paise,
        tax_amount_paise=tax_paise,
        total_amount_paise=total_paise,
        suggested_category_code=suggested_code,
        confidence_score=confidence_score,
        field_confidence=field_confidence,
        line_items=line_items,
    )
