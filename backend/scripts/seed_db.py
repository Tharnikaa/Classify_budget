"""Deterministic Database Seeder for ExpenseIt (Phase 1 Mobile-First Foundation).

Seeds:
1. Dynamic policy tiers, expense categories, and spend-tier caps from contracts/seed_policies.json.
2. Department structures and pinned personas from contracts/seed_personas.json (hashed passwords).
3. Three baseline mobile workflow claims:
   - Clean coffee (Aarav Mehta / Junior / PENDING_APPROVAL)
   - Multi-item hotel with alcohol deduction (Diya Nair / Senior / APPROVED_BY_DEPT)
   - Over-cap flight escalation (Diya Nair / Senior / ESCALATED_TO_FH)
4. IST monthly quota ledgers for live mobile dashboard cards.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.db import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models import (
    ClaimEventModel,
    ClaimLineItemModel,
    DepartmentModel,
    ExpenseCategoryModel,
    ExpenseClaimModel,
    MonthlyQuotaLedgerModel,
    PolicyTierModel,
    ReceiptScanModel,
    TierCategoryCapModel,
    UserModel,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_DIR = REPO_ROOT / "contracts"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "receipts"


def _read_json(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _file_meta(filename: str) -> tuple[str, int, Path]:
    target = FIXTURES_DIR / filename
    if target.exists():
        data = target.read_bytes()
        return hashlib.sha256(data).hexdigest(), len(data), target
    fallback_hash = hashlib.sha256(filename.encode("utf-8")).hexdigest()
    return fallback_hash, 12000, target


def seed_policies(session: Session, policies_data: dict[str, Any]) -> None:
    """Seed policy tiers, dynamic categories, and per-claim category caps."""
    # 1. Policy Tiers
    for tier_code, tier_info in policies_data["spend_tiers"].items():
        tier = session.get(PolicyTierModel, tier_code)
        if not tier:
            tier = PolicyTierModel(code=tier_code)
            session.add(tier)
        tier.display_name = tier_info["display_name"]
        tier.monthly_cap_paise = tier_info["monthly_cap_paise"]

    session.flush()

    # 2. Expense Categories
    for cat_data in policies_data["categories"]:
        cat = session.get(ExpenseCategoryModel, cat_data["code"])
        if not cat:
            cat = ExpenseCategoryModel(code=cat_data["code"])
            session.add(cat)
        cat.name = cat_data["name"]
        cat.description = cat_data.get("description", "")
        cat.is_active = cat_data.get("is_active", True)

    session.flush()

    # 3. Tier Category Caps Matrix
    caps_matrix = policies_data.get("tier_category_caps_paise", {})
    for cat_code, tier_map in caps_matrix.items():
        for tier_code, cap_paise in tier_map.items():
            cap = session.get(TierCategoryCapModel, (tier_code, cat_code))
            if not cap:
                cap = TierCategoryCapModel(tier_code=tier_code, category_code=cat_code)
                session.add(cap)
            cap.cap_paise = cap_paise

    session.flush()


def seed_personas(session: Session, personas_data: dict[str, Any]) -> dict[str, UserModel]:
    """Seed departments and pinned personas with bcrypt/argon2 hashed passwords."""
    default_password = personas_data.get("dev_default_password", "ExpenseIt@123")
    hashed_pwd = hash_password(default_password)

    # 1. Departments
    for dept_data in personas_data["departments"]:
        dept = session.get(DepartmentModel, dept_data["id"])
        if not dept:
            dept = DepartmentModel(id=dept_data["id"])
            session.add(dept)
        dept.code = dept_data["code"]
        dept.name = dept_data["name"]
        dept.monthly_budget_paise = dept_data["monthly_budget_paise"]

    session.flush()

    # 2. Users
    users_by_persona: dict[str, UserModel] = {}
    for user_data in personas_data["users"]:
        user = session.get(UserModel, user_data["id"])
        if not user:
            user = UserModel(id=user_data["id"])
            session.add(user)
        user.persona_key = user_data["persona_key"]
        user.full_name = user_data["full_name"]
        user.email = user_data["email"]
        user.password_hash = hashed_pwd
        user.role = user_data["role"]
        user.spend_tier = user_data["spend_tier"]
        user.department_id = user_data["department_id"]
        user.is_active = True
        users_by_persona[user.persona_key] = user

    session.flush()
    return users_by_persona


def seed_baseline_claims(session: Session, users: dict[str, UserModel]) -> None:
    """Seed the 3 mobile-first baseline workflow claims: clean coffee, hotel with alcohol, over-cap flight."""
    manifest_path = FIXTURES_DIR / "manifest.json"
    manifest: dict[str, Any] = _read_json(manifest_path) if manifest_path.exists() else {}

    junior = users["junior_employee"]
    senior = users["senior_employee"]
    eng_dh = users["eng_dept_head"]
    fm1 = users["finance_manager_1"]

    # =========================================================================
    # Claim 1: Clean Coffee (Aarav Mehta / Junior Employee) -> PENDING_APPROVAL
    # =========================================================================
    coffee_sha, coffee_size, coffee_path = _file_meta("clean_meal.png")
    coffee_extract = manifest.get("clean_meal", {}).get("expected_extraction", {})

    r1 = session.get(ReceiptScanModel, "rcpt-seed-clean-coffee")
    if not r1:
        r1 = ReceiptScanModel(
            receipt_id="rcpt-seed-clean-coffee",
            image_sha256=coffee_sha,
            image_phash="a1b2c3d4e5f60718",
            file_path=str(coffee_path),
            raw_extraction_json=coffee_extract,
            image_width=520,
            image_height=680,
            file_size_bytes=coffee_size,
            mime_type="image/png",
            thumbnail_path=None,
            created_at=datetime(2026, 11, 2, 9, 15, tzinfo=UTC),
        )
        session.add(r1)
        session.flush()

    c1 = session.get(ExpenseClaimModel, "claim-seed-clean-coffee-01")
    if not c1:
        c1 = ExpenseClaimModel(
            id="claim-seed-clean-coffee-01",
            receipt_id=r1.receipt_id,
            claimant_id=junior.id,
            department_id=junior.department_id,
            vendor_name="Third Wave Coffee Roasters",
            invoice_date=date(2026, 11, 2),
            category_code="MEALS",
            description="Client sprint planning coffee",
            currency="INR",
            total_amount_paise=44100,
            tax_amount_paise=2100,
            blacklisted_deduction_paise=0,
            eligible_amount_paise=44100,
            approved_amount_paise=None,
            is_over_cap=False,
            over_cap_reasons=[],
            status="PENDING_APPROVAL",
            rejection_reason=None,
            return_comment=None,
            payment_reference=None,
            ocr_diff={},
            policy_snapshot={
                "spend_tier": "JUNIOR",
                "category_code": "MEALS",
                "category_cap_paise": 50000,
                "monthly_cap_paise": 1500000,
                "blacklisted_item_tags": ["alcohol", "tobacco", "gift_card", "personal"],
                "captured_at": "2026-11-02T09:30:00Z",
            },
            submitted_at=datetime(2026, 11, 2, 9, 30, tzinfo=UTC),
            approved_at=None,
            verified_at=None,
            dispatched_at=None,
            created_at=datetime(2026, 11, 2, 9, 30, tzinfo=UTC),
            updated_at=datetime(2026, 11, 2, 9, 30, tzinfo=UTC),
        )
        session.add(c1)
        session.flush()

        item1 = ClaimLineItemModel(
            id="item-seed-clean-coffee-01",
            claim_id=c1.id,
            description="Cappuccino & Sourdough Toast",
            quantity=1.0,
            unit_price_paise=42000,
            amount_paise=42000,
            item_tag="meal",
            is_excluded=False,
        )
        event1 = ClaimEventModel(
            id="event-seed-clean-coffee-01",
            claim_id=c1.id,
            actor_id=junior.id,
            actor_role=junior.role,
            action="SUBMIT",
            from_status="DRAFT",
            to_status="PENDING_APPROVAL",
            comment="Submitted coffee expense for client sprint planning",
            created_at=datetime(2026, 11, 2, 9, 30, tzinfo=UTC),
        )
        session.add_all([item1, event1])

    # =========================================================================
    # Claim 2: Multi-Item Hotel with Alcohol (Diya Nair / Senior) -> APPROVED_BY_DEPT
    # =========================================================================
    hotel_sha, hotel_size, hotel_path = _file_meta("hotel_with_alcohol.png")
    hotel_extract = manifest.get("hotel_with_alcohol", {}).get("expected_extraction", {})

    r2 = session.get(ReceiptScanModel, "rcpt-seed-hotel-alcohol")
    if not r2:
        r2 = ReceiptScanModel(
            receipt_id="rcpt-seed-hotel-alcohol",
            image_sha256=hotel_sha,
            image_phash="b2c3d4e5f6071829",
            file_path=str(hotel_path),
            raw_extraction_json=hotel_extract,
            image_width=520,
            image_height=680,
            file_size_bytes=hotel_size,
            mime_type="image/png",
            thumbnail_path=None,
            created_at=datetime(2026, 11, 1, 9, 45, tzinfo=UTC),
        )
        session.add(r2)
        session.flush()

    c2 = session.get(ExpenseClaimModel, "claim-seed-hotel-alcohol-02")
    if not c2:
        # Pre-tax 600000, tax 72000, total 672000.
        # Alcohol line = 120000. Prorated tax = round(72000 * 120000 / 600000) = 14400.
        # Blacklisted deduction = 134400 paise. Eligible = 537600 paise.
        c2 = ExpenseClaimModel(
            id="claim-seed-hotel-alcohol-02",
            receipt_id=r2.receipt_id,
            claimant_id=senior.id,
            department_id=senior.department_id,
            vendor_name="Taj MG Road Bengaluru",
            invoice_date=date(2026, 11, 1),
            category_code="LODGING",
            description="Client onsite visit stay",
            currency="INR",
            total_amount_paise=672000,
            tax_amount_paise=72000,
            blacklisted_deduction_paise=134400,
            eligible_amount_paise=537600,
            approved_amount_paise=None,
            is_over_cap=False,
            over_cap_reasons=[],
            status="APPROVED_BY_DEPT",
            rejection_reason=None,
            return_comment=None,
            payment_reference=None,
            ocr_diff={},
            policy_snapshot={
                "spend_tier": "SENIOR",
                "category_code": "LODGING",
                "category_cap_paise": 650000,
                "monthly_cap_paise": 4000000,
                "blacklisted_item_tags": ["alcohol", "tobacco", "gift_card", "personal"],
                "captured_at": "2026-11-01T10:00:00Z",
            },
            submitted_at=datetime(2026, 11, 1, 10, 0, tzinfo=UTC),
            approved_at=datetime(2026, 11, 1, 14, 0, tzinfo=UTC),
            verified_at=None,
            dispatched_at=None,
            created_at=datetime(2026, 11, 1, 10, 0, tzinfo=UTC),
            updated_at=datetime(2026, 11, 1, 14, 0, tzinfo=UTC),
        )
        session.add(c2)
        session.flush()

        item2_room = ClaimLineItemModel(
            id="item-seed-hotel-01",
            claim_id=c2.id,
            description="Deluxe Business Room (1 Night)",
            quantity=1.0,
            unit_price_paise=480000,
            amount_paise=480000,
            item_tag="lodging",
            is_excluded=False,
        )
        item2_alcohol = ClaimLineItemModel(
            id="item-seed-hotel-02",
            claim_id=c2.id,
            description="Minibar Single Malt Whisky 60ml",
            quantity=1.0,
            unit_price_paise=120000,
            amount_paise=120000,
            item_tag="alcohol",
            is_excluded=True,
        )
        event2_sub = ClaimEventModel(
            id="event-seed-hotel-01",
            claim_id=c2.id,
            actor_id=senior.id,
            actor_role=senior.role,
            action="SUBMIT",
            from_status="DRAFT",
            to_status="PENDING_APPROVAL",
            comment="Client onsite visit stay at Taj MG Road",
            created_at=datetime(2026, 11, 1, 10, 0, tzinfo=UTC),
        )
        event2_app = ClaimEventModel(
            id="event-seed-hotel-02",
            claim_id=c2.id,
            actor_id=eng_dh.id,
            actor_role=eng_dh.role,
            action="APPROVE",
            from_status="PENDING_APPROVAL",
            to_status="APPROVED_BY_DEPT",
            comment="Approved business lodging. Alcohol and prorated tax deducted per policy.",
            created_at=datetime(2026, 11, 1, 14, 0, tzinfo=UTC),
        )
        session.add_all([item2_room, item2_alcohol, event2_sub, event2_app])

    # =========================================================================
    # Claim 3: Over-Cap Flight (Diya Nair / Senior) -> ESCALATED_TO_FH
    # =========================================================================
    flight_sha, flight_size, flight_path = _file_meta("over_cap_flight.png")
    flight_extract = manifest.get("over_cap_flight", {}).get("expected_extraction", {})

    r3 = session.get(ReceiptScanModel, "rcpt-seed-overcap-flight")
    if not r3:
        r3 = ReceiptScanModel(
            receipt_id="rcpt-seed-overcap-flight",
            image_sha256=flight_sha,
            image_phash="c3d4e5f60718293a",
            file_path=str(flight_path),
            raw_extraction_json=flight_extract,
            image_width=520,
            image_height=680,
            file_size_bytes=flight_size,
            mime_type="image/png",
            thumbnail_path=None,
            created_at=datetime(2026, 11, 2, 7, 45, tzinfo=UTC),
        )
        session.add(r3)
        session.flush()

    c3 = session.get(ExpenseClaimModel, "claim-seed-overcap-flight-03")
    if not c3:
        # Senior Travel per-claim cap is ₹5,000 (500000 paise).
        # Flight eligible amount is ₹8,190 (819000 paise) -> Exceeds cap by ₹3,190 -> Escalated to FH.
        c3 = ExpenseClaimModel(
            id="claim-seed-overcap-flight-03",
            receipt_id=r3.receipt_id,
            claimant_id=senior.id,
            department_id=senior.department_id,
            vendor_name="IndiGo Airlines",
            invoice_date=date(2026, 11, 2),
            category_code="TRAVEL",
            description="Customer onsite flight BLR-DEL",
            currency="INR",
            total_amount_paise=819000,
            tax_amount_paise=39000,
            blacklisted_deduction_paise=0,
            eligible_amount_paise=819000,
            approved_amount_paise=None,
            is_over_cap=True,
            over_cap_reasons=["CATEGORY_CAP_EXCEEDED: Travel cap of ₹5,000 exceeded by ₹3,190"],
            status="ESCALATED_TO_FH",
            rejection_reason=None,
            return_comment=None,
            payment_reference=None,
            ocr_diff={},
            policy_snapshot={
                "spend_tier": "SENIOR",
                "category_code": "TRAVEL",
                "category_cap_paise": 500000,
                "monthly_cap_paise": 4000000,
                "blacklisted_item_tags": ["alcohol", "tobacco", "gift_card", "personal"],
                "captured_at": "2026-11-02T08:00:00Z",
            },
            submitted_at=datetime(2026, 11, 2, 8, 0, tzinfo=UTC),
            approved_at=datetime(2026, 11, 2, 11, 0, tzinfo=UTC),
            verified_at=datetime(2026, 11, 2, 11, 30, tzinfo=UTC),
            dispatched_at=None,
            created_at=datetime(2026, 11, 2, 8, 0, tzinfo=UTC),
            updated_at=datetime(2026, 11, 2, 11, 30, tzinfo=UTC),
        )
        session.add(c3)
        session.flush()

        item3_flight = ClaimLineItemModel(
            id="item-seed-flight-01",
            claim_id=c3.id,
            description="BLR -> DEL Return Economy Fare",
            quantity=1.0,
            unit_price_paise=780000,
            amount_paise=780000,
            item_tag="transport",
            is_excluded=False,
        )
        event3_sub = ClaimEventModel(
            id="event-seed-flight-01",
            claim_id=c3.id,
            actor_id=senior.id,
            actor_role=senior.role,
            action="SUBMIT",
            from_status="DRAFT",
            to_status="PENDING_APPROVAL",
            comment="Emergency travel for customer kickoff",
            created_at=datetime(2026, 11, 2, 8, 0, tzinfo=UTC),
        )
        event3_app = ClaimEventModel(
            id="event-seed-flight-02",
            claim_id=c3.id,
            actor_id=eng_dh.id,
            actor_role=eng_dh.role,
            action="APPROVE",
            from_status="PENDING_APPROVAL",
            to_status="APPROVED_BY_DEPT",
            comment="Onsite customer visit flight approved",
            created_at=datetime(2026, 11, 2, 11, 0, tzinfo=UTC),
        )
        event3_esc = ClaimEventModel(
            id="event-seed-flight-03",
            claim_id=c3.id,
            actor_id=fm1.id,
            actor_role=fm1.role,
            action="ESCALATE",
            from_status="APPROVED_BY_DEPT",
            to_status="ESCALATED_TO_FH",
            comment="Exceeds Senior ₹5,000 per-claim Travel cap; escalating to FH",
            created_at=datetime(2026, 11, 2, 11, 30, tzinfo=UTC),
        )
        session.add_all([item3_flight, event3_sub, event3_app, event3_esc])

    session.flush()

    # =========================================================================
    # Monthly Quota Ledgers (live mobile quota cards)
    # =========================================================================
    # Junior: 44,100 paise reserved (coffee)
    ledger_junior = session.get(MonthlyQuotaLedgerModel, (junior.id, "2026-11"))
    if not ledger_junior:
        ledger_junior = MonthlyQuotaLedgerModel(
            user_id=junior.id,
            year_month="2026-11",
            disbursed_paise=0,
            reserved_paise=44100,
        )
        session.add(ledger_junior)
    else:
        ledger_junior.reserved_paise = 44100

    # Senior: 537,600 (hotel) + 819,000 (flight) = 1,356,600 paise reserved
    ledger_senior = session.get(MonthlyQuotaLedgerModel, (senior.id, "2026-11"))
    if not ledger_senior:
        ledger_senior = MonthlyQuotaLedgerModel(
            user_id=senior.id,
            year_month="2026-11",
            disbursed_paise=0,
            reserved_paise=1356600,
        )
        session.add(ledger_senior)
    else:
        ledger_senior.reserved_paise = 1356600

    session.flush()


def seed_database(session: Session | None = None) -> None:
    """Master entry point for deterministic seeding."""
    personas_path = CONTRACTS_DIR / "seed_personas.json"
    policies_path = CONTRACTS_DIR / "seed_policies.json"

    if not personas_path.exists() or not policies_path.exists():
        raise FileNotFoundError("Missing contracts/seed_personas.json or contracts/seed_policies.json")

    personas_data = _read_json(personas_path)
    policies_data = _read_json(policies_path)

    def _execute(sess: Session) -> None:
        seed_policies(sess, policies_data)
        users = seed_personas(sess, personas_data)
        seed_baseline_claims(sess, users)
        sess.commit()

    if session is not None:
        _execute(session)
    else:
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            _execute(db)


def main() -> None:
    print("Beginning deterministic database seeding...")
    seed_database()
    print("Database seeding completed successfully.")


if __name__ == "__main__":
    main()

