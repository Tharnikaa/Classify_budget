"""Phase 0 Contract, Security, RBAC/SoD, and Stateful Workflow Verification Suite."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from sqlalchemy import text

from app.core.config import CONTRACTS_DIR, Settings
from app.core.db import Base, build_engine
from app.main import create_app
from app.services.stub_store import get_stub_store

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = CONTRACTS_DIR / "schemas"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "receipts"


@pytest.fixture(autouse=True)
def reset_state() -> None:
    get_stub_store().reset()


@pytest.fixture()
def dev_client() -> TestClient:
    settings = Settings(APP_ENV="development")
    return TestClient(create_app(settings_override=settings))


@pytest.fixture()
def prod_client() -> TestClient:
    settings = Settings(APP_ENV="production", CORS_ORIGINS="https://app.expenseit.in")
    return TestClient(create_app(settings_override=settings))


def _auth_header(client: TestClient, persona_key: str) -> dict[str, str]:
    resp = client.post("/api/v1/auth/dev-switch-role", json={"persona_key": persona_key})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# -------------------- 1. Contract & Schema Validation --------------------


def test_all_json_schemas_are_valid_draft202012() -> None:
    schema_files = [
        "receipt_extracted.schema.json",
        "expense_claim.schema.json",
        "notification.schema.json",
        "seed_policies.schema.json",
    ]
    for name in schema_files:
        schema = json.loads((SCHEMAS_DIR / name).read_text("utf-8"))
        Draft202012Validator.check_schema(schema)


def test_seed_policies_and_receipt_fixtures_validate_against_schemas() -> None:
    policy_schema = json.loads((SCHEMAS_DIR / "seed_policies.schema.json").read_text("utf-8"))
    policy_data = json.loads((CONTRACTS_DIR / "seed_policies.json").read_text("utf-8"))
    Draft202012Validator(policy_schema).validate(policy_data)

    receipt_schema = json.loads((SCHEMAS_DIR / "receipt_extracted.schema.json").read_text("utf-8"))
    manifest = json.loads((FIXTURES_DIR / "manifest.json").read_text("utf-8"))
    assert len(manifest) >= 5
    for preset_name, entry in manifest.items():
        assert (FIXTURES_DIR / entry["image_file"]).exists(), f"Missing PNG for {preset_name}"
        Draft202012Validator(receipt_schema).validate(entry["expected_extraction"])


def test_openapi_yaml_matches_live_fastapi_routes(dev_client: TestClient) -> None:
    spec = yaml.safe_load((CONTRACTS_DIR / "openapi.yaml").read_text("utf-8"))
    assert spec["openapi"].startswith("3.1")

    live_openapi = dev_client.get("/openapi.json").json()
    spec_routes: set[tuple[str, str]] = set()
    for path, methods in spec["paths"].items():
        for method in methods:
            if method.lower() in {"get", "post", "put", "patch", "delete"}:
                spec_routes.add((path, method.lower()))

    live_routes: set[tuple[str, str]] = set()
    for path, methods in live_openapi["paths"].items():
        for method in methods:
            if method.lower() in {"get", "post", "put", "patch", "delete"}:
                live_routes.add((path, method.lower()))

    assert spec_routes == live_routes


def test_seeded_claims_and_notifications_validate_against_json_schemas(
    dev_client: TestClient,
) -> None:
    claim_schema = json.loads((SCHEMAS_DIR / "expense_claim.schema.json").read_text("utf-8"))
    notif_schema = json.loads((SCHEMAS_DIR / "notification.schema.json").read_text("utf-8"))

    fh_headers = _auth_header(dev_client, "finance_head")
    claims = dev_client.get("/api/v1/claims", headers=fh_headers).json()
    assert len(claims) >= 3
    for claim in claims:
        Draft202012Validator(claim_schema).validate(claim)

    dh_headers = _auth_header(dev_client, "eng_dept_head")
    notifs = dev_client.get("/api/v1/notifications", headers=dh_headers).json()
    assert len(notifs) >= 1
    for notif in notifs:
        Draft202012Validator(notif_schema).validate(notif)


# -------------------- 2. Security & SQLite WAL Checks --------------------


def test_role_switcher_strictly_returns_404_in_production(prod_client: TestClient) -> None:
    r1 = prod_client.get("/api/v1/auth/dev-personas")
    assert r1.status_code == 404

    r2 = prod_client.post("/api/v1/auth/dev-switch-role", json={"persona_key": "finance_manager_1"})
    assert r2.status_code == 404

    # Standard email/password login still works in production
    login_resp = prod_client.post(
        "/api/v1/auth/login",
        json={"email": "aarav.junior@expenseit.in", "password": "ExpenseIt@123"},
    )
    assert login_resp.status_code == 200
    assert login_resp.json()["user"]["role"] == "EMPLOYEE"


def test_sqlite_wal_and_foundation_tables(tmp_path: Path) -> None:
    db_file = tmp_path / "wal_check.db"
    test_engine = build_engine(f"sqlite:///{db_file.as_posix()}")
    Base.metadata.create_all(bind=test_engine)
    with test_engine.connect() as conn:
        mode = conn.execute(text("PRAGMA journal_mode;")).scalar_one()
        fk = conn.execute(text("PRAGMA foreign_keys;")).scalar_one()
        assert str(mode).lower() == "wal"
        assert int(fk) == 1
    test_engine.dispose()


# -------------------- 3. Separation of Duties & BOLA Checks --------------------


def test_sod_dept_head_cannot_self_approve_and_routes_to_finance_head(
    dev_client: TestClient,
) -> None:
    eng_dh = _auth_header(dev_client, "eng_dept_head")
    sales_dh = _auth_header(dev_client, "sales_dept_head")
    fh = _auth_header(dev_client, "finance_head")

    create_resp = dev_client.post(
        "/api/v1/claims",
        headers=eng_dh,
        json={
            "vendor_name": "Oberoi Business Lunch",
            "invoice_date": "2026-11-02",
            "category_code": "MEALS",
            "currency": "INR",
            "total_amount_paise": 180000,
            "tax_amount_paise": 9000,
            "line_items": [
                {
                    "description": "Team Architecture Lunch",
                    "quantity": 1,
                    "amount_paise": 171000,
                    "item_tag": "meal",
                }
            ],
        },
    )
    assert create_resp.status_code == 201
    claim_id = create_resp.json()["id"]

    # Self-approval MUST fail with 403 SOD_SELF_ACTION_FORBIDDEN
    self_approve = dev_client.post(f"/api/v1/claims/{claim_id}/approve", headers=eng_dh)
    assert self_approve.status_code == 403
    assert self_approve.json()["error"]["code"] == "SOD_SELF_ACTION_FORBIDDEN"

    # Cross-department Dept Head cannot view or approve Engineering DH's claim
    cross_dept = dev_client.get(f"/api/v1/claims/{claim_id}", headers=sales_dh)
    assert cross_dept.status_code == 403

    # Finance Head approves Dept Head's personal claim cleanly
    fh_approve = dev_client.post(
        f"/api/v1/claims/{claim_id}/approve",
        headers=fh,
        json={"comment": "Approved by Finance Head"},
    )
    assert fh_approve.status_code == 200
    assert fh_approve.json()["status"] == "APPROVED_BY_DEPT"


def test_sod_finance_manager_claim_requires_fh_and_peer_fm_dispatch(
    dev_client: TestClient,
) -> None:
    fm1 = _auth_header(dev_client, "finance_manager_1")
    fm2 = _auth_header(dev_client, "finance_manager_2")
    fh = _auth_header(dev_client, "finance_head")

    # Finance Head cannot raise personal claims in MVP
    fh_claim = dev_client.post(
        "/api/v1/claims",
        headers=fh,
        json={
            "vendor_name": "Airport Lounge",
            "invoice_date": "2026-11-02",
            "category_code": "MEALS",
            "currency": "INR",
            "total_amount_paise": 50000,
            "tax_amount_paise": 0,
            "line_items": [
                {"description": "Snack", "quantity": 1, "amount_paise": 50000, "item_tag": "meal"}
            ],
        },
    )
    assert fh_claim.status_code == 403

    # FM-1 submits personal claim
    fm1_claim = dev_client.post(
        "/api/v1/claims",
        headers={**fm1, "Idempotency-Key": "idem-fm1-001"},
        json={
            "vendor_name": "Notion Enterprise Tooling",
            "invoice_date": "2026-11-02",
            "category_code": "SOFTWARE_TOOLS",
            "currency": "INR",
            "total_amount_paise": 250000,
            "tax_amount_paise": 0,
            "line_items": [
                {
                    "description": "Finance Ops License",
                    "quantity": 1,
                    "amount_paise": 250000,
                    "item_tag": "software",
                }
            ],
        },
    )
    assert fm1_claim.status_code == 201
    cid = fm1_claim.json()["id"]

    # Idempotent retry returns identical claim ID
    fm1_retry = dev_client.post(
        "/api/v1/claims",
        headers={**fm1, "Idempotency-Key": "idem-fm1-001"},
        json={
            "vendor_name": "Notion Enterprise Tooling",
            "invoice_date": "2026-11-02",
            "category_code": "SOFTWARE_TOOLS",
            "currency": "INR",
            "total_amount_paise": 250000,
            "tax_amount_paise": 0,
            "line_items": [
                {
                    "description": "Finance Ops License",
                    "quantity": 1,
                    "amount_paise": 250000,
                    "item_tag": "software",
                }
            ],
        },
    )
    assert fm1_retry.json()["id"] == cid

    # FH approves FM-1's claim
    assert dev_client.post(f"/api/v1/claims/{cid}/approve", headers=fh).status_code == 200

    # FM-1 CANNOT verify or dispatch their own claim
    assert dev_client.post(f"/api/v1/claims/{cid}/verify", headers=fm1).status_code == 403

    # Peer FM-2 verifies and dispatches FM-1's claim
    assert dev_client.post(f"/api/v1/claims/{cid}/verify", headers=fm2).status_code == 200
    disp = dev_client.post(
        f"/api/v1/claims/{cid}/dispatch",
        headers={**fm2, "Idempotency-Key": "disp-fm1-001"},
        json={"payment_reference": "UTR-PEER-FM2"},
    )
    assert disp.status_code == 200
    assert disp.json()["status"] == "DISPATCHED"


# -------------------- 4. Blacklist, OCR Diff, Quota & FH Override --------------------


def test_blacklist_proration_ocr_diff_and_fh_clamp_workflow(dev_client: TestClient) -> None:
    senior = _auth_header(dev_client, "senior_employee")
    fm1 = _auth_header(dev_client, "finance_manager_1")
    fh = _auth_header(dev_client, "finance_head")

    # 1. Mock scan hotel receipt containing room (₹4,800) + minibar alcohol (₹1,200) + 12% GST (₹720) = ₹6,720
    scan = dev_client.post(
        "/api/v1/ocr/mock-scan",
        headers=senior,
        json={"preset": "hotel_with_alcohol"},
    ).json()

    # 2. Senior submits with slightly edited vendor name -> triggers ocr_diff & alcohol auto-deduction
    # Room ₹4,800 + prorated GST ₹576 = ₹5,376 (537600 paise); deduction = ₹1,200 + ₹144 = ₹1,344 (134400 paise)
    created = dev_client.post(
        "/api/v1/claims",
        headers=senior,
        json={
            "receipt_id": scan["receipt_id"],
            "vendor_name": "Taj MG Road Bengaluru (Edited)",
            "invoice_date": "2026-11-02",
            "category_code": "LODGING",
            "currency": "INR",
            "total_amount_paise": 672000,
            "tax_amount_paise": 72000,
            "line_items": scan["line_items"],
        },
    )
    assert created.status_code == 201
    claim = created.json()
    assert claim["blacklisted_deduction_paise"] == 134400
    assert claim["eligible_amount_paise"] == 537600
    assert "vendor_name" in claim["ocr_diff"]

    # 3. Verify quota reservation & release on withdraw
    q_before = dev_client.get("/api/v1/quotas/me?year_month=2026-11", headers=senior).json()
    assert q_before["reserved_paise"] >= 537600

    withdrawn = dev_client.post(f"/api/v1/claims/{claim['id']}/withdraw", headers=senior)
    assert withdrawn.status_code == 200
    q_after = dev_client.get("/api/v1/quotas/me?year_month=2026-11", headers=senior).json()
    assert q_after["reserved_paise"] == q_before["reserved_paise"] - 537600

    # 4. Resolve seeded escalated flight claim via Finance Head CLAMP_TO_CAP
    escalated_list = dev_client.get("/api/v1/claims?status=ESCALATED_TO_FH", headers=fh).json()
    assert len(escalated_list) >= 1
    esc_id = escalated_list[0]["id"]

    clamped = dev_client.post(
        f"/api/v1/claims/{esc_id}/override",
        headers=fh,
        json={"decision": "CLAMP_TO_CAP", "comment": "Clamped to Senior ₹5,000 Travel cap"},
    )
    assert clamped.status_code == 200
    assert clamped.json()["status"] == "VERIFIED_FOR_DISPATCH"
    assert clamped.json()["approved_amount_paise"] == 500000

    dispatched = dev_client.post(f"/api/v1/claims/{esc_id}/dispatch", headers=fm1)
    assert dispatched.status_code == 200
    assert dispatched.json()["status"] == "DISPATCHED"
