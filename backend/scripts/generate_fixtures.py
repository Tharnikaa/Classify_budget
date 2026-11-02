"""Generate deterministic synthetic receipt PNGs & manifest.json in tests/fixtures/receipts/."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

from PIL import Image, ImageDraw

from app.ocr.mock_provider import MockOCRProvider
from app.schemas.api import MockPresetName

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "receipts"

PRESETS: list[tuple[MockPresetName, list[str]]] = [
    (
        "clean_meal",
        [
            "THIRD WAVE COFFEE ROASTERS",
            "GSTIN: 29AABCT1234F1ZP",
            "Date: 2026-11-02",
            "1x Cappuccino & Sourdough   INR 420.00",
            "CGST/SGST (5%)              INR  21.00",
            "TOTAL                       INR 441.00",
        ],
    ),
    (
        "hotel_with_alcohol",
        [
            "TAJ MG ROAD BENGALURU",
            "GSTIN: 29AAACT4321K1Z5",
            "Date: 2026-11-01",
            "Deluxe Business Room 1N   INR 4,800.00",
            "Minibar Whisky 60ml       INR 1,200.00",
            "GST (12%)                 INR   720.00",
            "TOTAL                     INR 6,720.00",
        ],
    ),
    (
        "over_cap_flight",
        [
            "INDIGO AIRLINES TAX INVOICE",
            "GSTIN: 07AABCI9988M1Z2",
            "Date: 2026-11-02",
            "BLR -> DEL Return Econ    INR 7,800.00",
            "Taxes & Airport Fees      INR   390.00",
            "TOTAL                     INR 8,190.00",
        ],
    ),
    (
        "blurry_missing_date",
        [
            "LOCAL METERED AUTO TAXI",
            "Date: [FADED THERMAL INK]",
            "City Cab Transfer         INR   385.00",
            "TOTAL                     INR   385.00",
        ],
    ),
    (
        "foreign_usd",
        [
            "GITHUB INC. - SAN FRANCISCO",
            "Date: 2026-11-01",
            "Copilot Pro Seat             USD 20.00",
            "TOTAL                        USD 20.00",
        ],
    ),
]


def render_receipt_png(lines: list[str]) -> bytes:
    img = Image.new("RGB", (520, 680), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([16, 16, 504, 664], outline=(15, 118, 110), width=3)
    draw.text((36, 36), "EXPENSEIT TEST FIXTURE (SYNTHETIC)", fill=(100, 116, 139))
    y = 90
    for idx, line in enumerate(lines):
        color = (15, 23, 42) if idx > 0 else (15, 118, 110)
        draw.text((36, y), line, fill=color)
        y += 42
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    provider = MockOCRProvider()
    manifest: dict[str, dict[str, object]] = {}

    for preset_name, text_lines in PRESETS:
        png_bytes = render_receipt_png(text_lines)
        filename = f"{preset_name}.png"
        (FIXTURES_DIR / filename).write_bytes(png_bytes)
        sha = hashlib.sha256(png_bytes).hexdigest()
        expected = provider.build_preset(
            preset=preset_name,
            receipt_id=f"fixture-{preset_name}",
            image_sha256=sha,
        )
        manifest[preset_name] = {
            "image_file": filename,
            "expected_extraction": expected.model_dump(),
        }

    (FIXTURES_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Generated {len(PRESETS)} synthetic receipt fixtures in {FIXTURES_DIR}")


if __name__ == "__main__":
    main()

