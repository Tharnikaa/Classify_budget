"""Unit tests for Phase 1 SQLAlchemy 2.0 ORM models, relationships, and seeding."""

from __future__ import annotations

from collections.abc import Generator
from datetime import date
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.db import Base, build_engine
from app.core.security import hash_password, verify_password
from app.models import (
    ClaimEventModel,
    ClaimLineItemModel,
    DepartmentModel,
    ExpenseCategoryModel,
    ExpenseClaimModel,
    IdempotencyRecordModel,
    MonthlyQuotaLedgerModel,
    PolicyTierModel,
    ReceiptScanModel,
    TierCategoryCapModel,
    UserModel,
)
from scripts.seed_db import seed_database


@pytest.fixture
def test_db_session(tmp_path: Path) -> Generator[Session, None, None]:
    """Provide an isolated, clean SQLite WAL session for model testing."""
    db_file = tmp_path / "test_models.db"
    engine = build_engine(f"sqlite:///{db_file.as_posix()}")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_department_and_user_relationships(test_db_session: Session) -> None:
    """Verify department and policy tier foreign keys and user relationships."""
    dept = DepartmentModel(
        id="dept-test-1",
        code="TEST_ENG",
        name="Test Engineering",
        monthly_budget_paise=25000000,
    )
    tier = PolicyTierModel(
        code="JUNIOR",
        display_name="Junior Tier",
        monthly_cap_paise=1500000,
    )
    test_db_session.add_all([dept, tier])
    test_db_session.flush()

    user = UserModel(
        id="user-test-1",
        persona_key="test_dev",
        full_name="Test Developer",
        email="dev@example.com",
        password_hash=hash_password("DevPass@123"),
        role="EMPLOYEE",
        spend_tier="JUNIOR",
        department_id="dept-test-1",
    )
    test_db_session.add(user)
    test_db_session.commit()

    # Query back and verify back-populates
    queried_user = test_db_session.get(UserModel, "user-test-1")
    assert queried_user is not None
    assert queried_user.department.name == "Test Engineering"
    assert queried_user.tier.display_name == "Junior Tier"
    assert len(dept.users) == 1
    assert dept.users[0].id == "user-test-1"


def test_composite_primary_keys_integrity(test_db_session: Session) -> None:
    """Ensure composite PK on tier_category_caps and monthly_quota_ledgers enforces uniqueness."""
    # 1. Tier Category Caps composite PK (tier_code, category_code)
    tier = PolicyTierModel(code="SENIOR", display_name="Senior", monthly_cap_paise=4000000)
    cat = ExpenseCategoryModel(code="MEALS", name="Meals", description="Dining", is_active=True)
    test_db_session.add_all([tier, cat])
    test_db_session.flush()

    cap1 = TierCategoryCapModel(tier_code="SENIOR", category_code="MEALS", cap_paise=120000)
    test_db_session.add(cap1)
    test_db_session.commit()

    # Duplicate composite PK must raise IntegrityError
    with pytest.raises(IntegrityError):
        test_db_session.execute(
            text(
                "INSERT INTO tier_category_caps (tier_code, category_code, cap_paise, updated_at) "
                "VALUES ('SENIOR', 'MEALS', 200000, CURRENT_TIMESTAMP)"
            )
        )
    test_db_session.rollback()

    # 2. Monthly Quota Ledgers composite PK (user_id, year_month)
    dept = DepartmentModel(id="dept-q", code="DEPT_Q", name="Dept Q", monthly_budget_paise=1000000)
    test_db_session.add(dept)
    test_db_session.flush()

    user = UserModel(
        id="user-q-1",
        persona_key="user_q",
        full_name="Quota User",
        email="quota@example.com",
        password_hash="fakehash",
        role="EMPLOYEE",
        spend_tier="SENIOR",
        department_id="dept-q",
    )
    test_db_session.add(user)
    test_db_session.flush()

    ledger1 = MonthlyQuotaLedgerModel(
        user_id="user-q-1",
        year_month="2026-11",
        disbursed_paise=50000,
        reserved_paise=20000,
    )
    test_db_session.add(ledger1)
    test_db_session.commit()

    with pytest.raises(IntegrityError):
        test_db_session.execute(
            text(
                "INSERT INTO monthly_quota_ledgers (user_id, year_month, disbursed_paise, reserved_paise, updated_at) "
                "VALUES ('user-q-1', '2026-11', 100000, 40000, CURRENT_TIMESTAMP)"
            )
        )
    test_db_session.rollback()


def test_expense_claim_cascade_deletes(test_db_session: Session) -> None:
    """Verify that deleting an ExpenseClaim cascades delete to line items and audit events."""
    dept = DepartmentModel(id="dept-c", code="DEPT_C", name="Dept C", monthly_budget_paise=5000000)
    tier = PolicyTierModel(code="JUNIOR", display_name="Junior", monthly_cap_paise=1500000)
    cat = ExpenseCategoryModel(code="TRAVEL", name="Travel", description="Cabs", is_active=True)
    test_db_session.add_all([dept, tier, cat])
    test_db_session.flush()

    user = UserModel(
        id="user-c-1",
        persona_key="user_c",
        full_name="Cascade User",
        email="cascade@example.com",
        password_hash="fakehash",
        role="EMPLOYEE",
        spend_tier="JUNIOR",
        department_id="dept-c",
    )
    test_db_session.add(user)
    test_db_session.flush()

    scan = ReceiptScanModel(
        receipt_id="rcpt-c-1",
        image_sha256="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        image_phash="1234567890abcdef",
        file_path="/tmp/scan.png",
        raw_extraction_json={"test": True},
        image_width=400,
        image_height=600,
        file_size_bytes=8192,
        mime_type="image/png",
    )
    test_db_session.add(scan)
    test_db_session.flush()

    claim = ExpenseClaimModel(
        id="claim-c-1",
        receipt_id="rcpt-c-1",
        claimant_id="user-c-1",
        department_id="dept-c",
        vendor_name="Ola Cabs",
        invoice_date=date(2026, 11, 3),
        category_code="TRAVEL",
        description="Office commute",
        currency="INR",
        total_amount_paise=35000,
        tax_amount_paise=1500,
        blacklisted_deduction_paise=0,
        eligible_amount_paise=35000,
        is_over_cap=False,
        over_cap_reasons=[],
        status="PENDING_APPROVAL",
    )
    test_db_session.add(claim)
    test_db_session.flush()

    item = ClaimLineItemModel(
        id="item-c-1",
        claim_id="claim-c-1",
        description="Cab ride to office",
        quantity=1.0,
        unit_price_paise=35000,
        amount_paise=35000,
        item_tag="transport",
    )
    event = ClaimEventModel(
        id="event-c-1",
        claim_id="claim-c-1",
        actor_id="user-c-1",
        actor_role="EMPLOYEE",
        action="SUBMIT",
        to_status="PENDING_APPROVAL",
        comment="Submitted cab receipt",
    )
    test_db_session.add_all([item, event])
    test_db_session.commit()

    # Confirm created
    assert test_db_session.get(ClaimLineItemModel, "item-c-1") is not None
    assert test_db_session.get(ClaimEventModel, "event-c-1") is not None

    # Delete claim
    test_db_session.delete(claim)
    test_db_session.commit()

    # Line item and audit event must be cascade-deleted
    assert test_db_session.get(ClaimLineItemModel, "item-c-1") is None
    assert test_db_session.get(ClaimEventModel, "event-c-1") is None

    # The receipt scan must NOT be deleted (immutable scan retention)
    remaining_scan = test_db_session.get(ReceiptScanModel, "rcpt-c-1")
    assert remaining_scan is not None


def test_biginteger_paise_arithmetic_and_financial_precision(test_db_session: Session) -> None:
    """Verify that BigInteger paise handles large enterprise sums (> 2^31-1) without overflow."""
    dept = DepartmentModel(
        id="dept-large",
        code="CORP_EXEC",
        name="Corporate Executive",
        monthly_budget_paise=500_000_000_00,  # ₹5,000,000,000.00 (exceeds 32-bit signed int max 2,147,483,647)
    )
    test_db_session.add(dept)
    test_db_session.commit()

    queried_dept = test_db_session.get(DepartmentModel, "dept-large")
    assert queried_dept is not None
    assert queried_dept.monthly_budget_paise == 50_000_000_000

    # Test integer paise deduction logic
    total_amount_paise = 672000  # ₹6,720.00
    tax_amount_paise = 72000  # ₹720.00
    pre_tax_subtotal_paise = 600000  # ₹6,000.00
    blacklisted_raw_paise = 120000  # ₹1,200.00 (minibar alcohol)

    # Prorated tax calculation in pure integer arithmetic: round(72000 * 120000 / 600000)
    prorated_tax_paise = round(tax_amount_paise * blacklisted_raw_paise / pre_tax_subtotal_paise)
    assert prorated_tax_paise == 14400

    total_blacklisted_deduction = blacklisted_raw_paise + prorated_tax_paise
    assert total_blacklisted_deduction == 134400

    eligible_amount_paise = total_amount_paise - total_blacklisted_deduction
    assert eligible_amount_paise == 537600


def test_idempotency_records_uniqueness(test_db_session: Session) -> None:
    """Verify idempotency record prevents duplicate mobile submissions."""
    dept = DepartmentModel(id="dept-i", code="DEPT_I", name="Dept I", monthly_budget_paise=1000000)
    tier = PolicyTierModel(code="JUNIOR", display_name="Junior", monthly_cap_paise=1500000)
    user = UserModel(
        id="user-i-1",
        persona_key="user_i",
        full_name="Idempotency User",
        email="idempotent@example.com",
        password_hash="fakehash",
        role="EMPLOYEE",
        spend_tier="JUNIOR",
        department_id="dept-i",
    )
    test_db_session.add_all([dept, tier, user])
    test_db_session.flush()

    record1 = IdempotencyRecordModel(
        id="rec-1",
        user_id="user-i-1",
        idempotency_key="mobile-req-abc-123",
        action="CREATE_CLAIM",
        resource_id="claim-uuid-999",
        response_status=201,
        response_payload={"claim_id": "claim-uuid-999"},
    )
    test_db_session.add(record1)
    test_db_session.commit()

    # Replaying same key for same user and action must raise IntegrityError
    duplicate_record = IdempotencyRecordModel(
        id="rec-2",
        user_id="user-i-1",
        idempotency_key="mobile-req-abc-123",
        action="CREATE_CLAIM",
        resource_id="claim-uuid-999",
        response_status=201,
        response_payload={"claim_id": "claim-uuid-999"},
    )
    test_db_session.add(duplicate_record)
    with pytest.raises(IntegrityError):
        test_db_session.flush()
    test_db_session.rollback()


def test_deterministic_seeder_execution(tmp_path: Path) -> None:
    """Execute seed_database and verify complete DB population and workflow integrity."""
    db_file = tmp_path / "seeded_test.db"
    test_engine = build_engine(f"sqlite:///{db_file.as_posix()}")
    Base.metadata.create_all(bind=test_engine)

    session_factory = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    with session_factory() as session:
        seed_database(session)

        # 1. Verify Organization and Policies
        assert session.scalar(select(text("COUNT(*)")).select_from(DepartmentModel)) == 4
        assert session.scalar(select(text("COUNT(*)")).select_from(PolicyTierModel)) == 4
        assert session.scalar(select(text("COUNT(*)")).select_from(ExpenseCategoryModel)) == 7
        assert session.scalar(select(text("COUNT(*)")).select_from(TierCategoryCapModel)) == 21
        assert session.scalar(select(text("COUNT(*)")).select_from(UserModel)) == 7

        # 2. Verify Pinned Personas and Passwords
        junior = session.scalar(select(UserModel).where(UserModel.persona_key == "junior_employee"))
        assert junior is not None
        assert junior.email == "aarav.junior@expenseit.in"
        assert junior.role == "EMPLOYEE"
        assert junior.spend_tier == "JUNIOR"
        assert verify_password("ExpenseIt@123", junior.password_hash)

        fh = session.scalar(select(UserModel).where(UserModel.persona_key == "finance_head"))
        assert fh is not None
        assert fh.role == "FINANCE_HEAD"
        assert fh.spend_tier == "NONE"

        # 3. Verify the 3 Baseline Mobile Claims
        claims = session.scalars(select(ExpenseClaimModel).order_by(ExpenseClaimModel.id)).all()
        assert len(claims) == 3

        # Claim 1: Clean Coffee
        coffee = session.get(ExpenseClaimModel, "claim-seed-clean-coffee-01")
        assert coffee is not None
        assert coffee.vendor_name == "Third Wave Coffee Roasters"
        assert coffee.status == "PENDING_APPROVAL"
        assert coffee.total_amount_paise == 44100
        assert coffee.eligible_amount_paise == 44100
        assert coffee.blacklisted_deduction_paise == 0
        assert len(coffee.line_items) == 1
        assert len(coffee.events) == 1
        assert coffee.events[0].action == "SUBMIT"

        # Claim 2: Hotel with Alcohol
        hotel = session.get(ExpenseClaimModel, "claim-seed-hotel-alcohol-02")
        assert hotel is not None
        assert hotel.vendor_name == "Taj MG Road Bengaluru"
        assert hotel.status == "APPROVED_BY_DEPT"
        assert hotel.total_amount_paise == 672000
        assert hotel.blacklisted_deduction_paise == 134400
        assert hotel.eligible_amount_paise == 537600
        assert len(hotel.line_items) == 2
        # Alcohol line is excluded
        alcohol_item = next(i for i in hotel.line_items if i.item_tag == "alcohol")
        assert alcohol_item.is_excluded is True
        assert len(hotel.events) == 2
        assert hotel.events[1].action == "APPROVE"

        # Claim 3: Over-cap Flight
        flight = session.get(ExpenseClaimModel, "claim-seed-overcap-flight-03")
        assert flight is not None
        assert flight.vendor_name == "IndiGo Airlines"
        assert flight.status == "ESCALATED_TO_FH"
        assert flight.is_over_cap is True
        assert flight.total_amount_paise == 819000
        assert len(flight.events) == 3
        assert flight.events[2].action == "ESCALATE"

        # 4. Verify Monthly Quota Ledgers
        ledger_junior = session.get(MonthlyQuotaLedgerModel, (junior.id, "2026-11"))
        assert ledger_junior is not None
        assert ledger_junior.reserved_paise == 44100
        assert ledger_junior.disbursed_paise == 0

        senior = session.scalar(select(UserModel).where(UserModel.persona_key == "senior_employee"))
        assert senior is not None
        ledger_senior = session.get(MonthlyQuotaLedgerModel, (senior.id, "2026-11"))
        assert ledger_senior is not None
        assert ledger_senior.reserved_paise == 1356600
        assert ledger_senior.disbursed_paise == 0

        # 5. Verify Seeder Idempotency (re-run on existing DB must succeed)
        seed_database(session)
        assert session.scalar(select(text("COUNT(*)")).select_from(ExpenseClaimModel)) == 3

    test_engine.dispose()


def test_alembic_migrations_upgrade_and_downgrade(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that Alembic migrations run cleanly to head and downgrade reversibly."""
    db_file = tmp_path / "alembic_verify.db"
    db_url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    get_settings.cache_clear()

    alembic_ini_path = Path(__file__).resolve().parents[1] / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    alembic_cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))

    try:
        # Upgrade all the way to head
        command.upgrade(alembic_cfg, "head")

        # Verify tables exist via raw engine
        check_engine = build_engine(db_url)
        with check_engine.connect() as conn:
            tables = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
            ).scalars().all()
            assert "departments" in tables
            assert "users" in tables
            assert "policy_tiers" in tables
            assert "expense_categories" in tables
            assert "tier_category_caps" in tables
            assert "receipt_scans" in tables
            assert "expense_claims" in tables
            assert "claim_line_items" in tables
            assert "claim_events" in tables
            assert "monthly_quota_ledgers" in tables
            assert "idempotency_records" in tables
        check_engine.dispose()

        # Downgrade back to Phase 0 foundation
        command.downgrade(alembic_cfg, "0001_phase0_foundation")

        check_engine = build_engine(db_url)
        with check_engine.connect() as conn:
            remaining_tables = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
            ).scalars().all()
            # Phase 1 tables should be cleanly dropped
            assert "expense_claims" not in remaining_tables
            assert "tier_category_caps" not in remaining_tables
            assert "claim_line_items" not in remaining_tables
            # Phase 0 foundation tables remain
            assert "departments" in remaining_tables
            assert "users" in remaining_tables
        check_engine.dispose()
    finally:
        get_settings.cache_clear()
