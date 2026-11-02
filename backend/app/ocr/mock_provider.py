"""Deterministic Phase 0 Mock OCR Provider conforming to OCRServiceProtocol."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from uuid import uuid4

from app.ocr.protocol import ActiveCategoryItem, OCRServiceProtocol
from app.schemas.api import (
    ExtractedLineItem,
    ExtractedReceipt,
    FieldConfidence,
    ItemTagEnum,
    MockPresetName,
)


class MockOCRProvider(OCRServiceProtocol):
    """Produces realistic INR paise receipt extractions for UI and integration testing."""

    def build_preset(
        self,
        preset: MockPresetName,
        receipt_id: str | None = None,
        image_sha256: str | None = None,
    ) -> ExtractedReceipt:
        rid = receipt_id or f"rcpt-{uuid4().hex[:12]}"
        sha = image_sha256 or hashlib.sha256(f"expenseit-preset-{preset}".encode()).hexdigest()
        image_url = f"/api/v1/receipts/{rid}/image"

        if preset == "clean_meal":
            return ExtractedReceipt(
                receipt_id=rid,
                image_url=image_url,
                image_sha256=sha,
                image_phash="a1b2c3d4e5f60718",
                is_valid_receipt=True,
                vendor_name="Third Wave Coffee Roasters",
                vendor_tax_id="29AABCT1234F1ZP",
                invoice_date="2026-11-02",
                detected_currency="INR",
                subtotal_amount_paise=42000,
                tax_amount_paise=2100,
                total_amount_paise=44100,
                suggested_category_code="MEALS",
                confidence_score=0.97,
                field_confidence=FieldConfidence(vendor=0.99, date=0.98, total=0.99, category=0.94),
                line_items=[
                    ExtractedLineItem(
                        description="Cappuccino & Sourdough Toast",
                        quantity=1,
                        unit_price_paise=42000,
                        amount_paise=42000,
                        item_tag=ItemTagEnum.MEAL,
                    )
                ],
            )

        if preset == "hotel_with_alcohol":
            return ExtractedReceipt(
                receipt_id=rid,
                image_url=image_url,
                image_sha256=sha,
                image_phash="b2c3d4e5f6071829",
                is_valid_receipt=True,
                vendor_name="Taj MG Road Bengaluru",
                vendor_tax_id="29AAACT4321K1Z5",
                invoice_date="2026-11-01",
                detected_currency="INR",
                subtotal_amount_paise=600000,
                tax_amount_paise=72000,
                total_amount_paise=672000,
                suggested_category_code="LODGING",
                confidence_score=0.94,
                field_confidence=FieldConfidence(vendor=0.98, date=0.96, total=0.97, category=0.95),
                line_items=[
                    ExtractedLineItem(
                        description="Deluxe Business Room (1 Night)",
                        quantity=1,
                        unit_price_paise=480000,
                        amount_paise=480000,
                        item_tag=ItemTagEnum.LODGING,
                    ),
                    ExtractedLineItem(
                        description="Minibar Single Malt Whisky 60ml",
                        quantity=1,
                        unit_price_paise=120000,
                        amount_paise=120000,
                        item_tag=ItemTagEnum.ALCOHOL,
                    ),
                ],
            )

        if preset == "over_cap_flight":
            return ExtractedReceipt(
                receipt_id=rid,
                image_url=image_url,
                image_sha256=sha,
                image_phash="c3d4e5f60718293a",
                is_valid_receipt=True,
                vendor_name="IndiGo Airlines",
                vendor_tax_id="07AABCI9988M1Z2",
                invoice_date="2026-11-02",
                detected_currency="INR",
                subtotal_amount_paise=780000,
                tax_amount_paise=39000,
                total_amount_paise=819000,
                suggested_category_code="TRAVEL",
                confidence_score=0.96,
                field_confidence=FieldConfidence(vendor=0.99, date=0.97, total=0.98, category=0.98),
                line_items=[
                    ExtractedLineItem(
                        description="BLR -> DEL Return Economy Fare",
                        quantity=1,
                        unit_price_paise=780000,
                        amount_paise=780000,
                        item_tag=ItemTagEnum.TRANSPORT,
                    )
                ],
            )

        if preset == "blurry_missing_date":
            return ExtractedReceipt(
                receipt_id=rid,
                image_url=image_url,
                image_sha256=sha,
                image_phash="d4e5f60718293a4b",
                is_valid_receipt=True,
                vendor_name="Local Metered Auto Taxi",
                vendor_tax_id=None,
                invoice_date=None,
                detected_currency="INR",
                subtotal_amount_paise=38500,
                tax_amount_paise=0,
                total_amount_paise=38500,
                suggested_category_code="TRAVEL",
                confidence_score=0.58,
                field_confidence=FieldConfidence(vendor=0.62, date=0.18, total=0.79, category=0.84),
                line_items=[
                    ExtractedLineItem(
                        description="City Cab Transfer",
                        quantity=1,
                        unit_price_paise=38500,
                        amount_paise=38500,
                        item_tag=ItemTagEnum.TRANSPORT,
                    )
                ],
            )

        # foreign_usd
        return ExtractedReceipt(
            receipt_id=rid,
            image_url=image_url,
            image_sha256=sha,
            image_phash="e5f60718293a4b5c",
            is_valid_receipt=True,
            vendor_name="GitHub Inc.",
            vendor_tax_id=None,
            invoice_date="2026-11-01",
            detected_currency="USD",
            subtotal_amount_paise=2000,
            tax_amount_paise=0,
            total_amount_paise=2000,
            suggested_category_code="SOFTWARE_TOOLS",
            confidence_score=0.95,
            field_confidence=FieldConfidence(vendor=0.99, date=0.98, total=0.99, category=0.96),
            line_items=[
                ExtractedLineItem(
                    description="Copilot Pro Monthly Seat ($20.00 USD)",
                    quantity=1,
                    unit_price_paise=2000,
                    amount_paise=2000,
                    item_tag=ItemTagEnum.SOFTWARE,
                )
            ],
        )

    async def extract_receipt(
        self,
        image_bytes: bytes,
        mime_type: str,
        active_categories: Sequence[ActiveCategoryItem],
    ) -> ExtractedReceipt:
        sha = hashlib.sha256(image_bytes).hexdigest()
        available_codes = {c["code"] for c in active_categories}
        receipt = self.build_preset("clean_meal", image_sha256=sha)
        if receipt.suggested_category_code not in available_codes and active_categories:
            receipt.suggested_category_code = active_categories[0]["code"]
        return receipt
