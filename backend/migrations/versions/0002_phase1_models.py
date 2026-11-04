"""Phase 1: Mobile-first data models, policy caps, claims, and audit events.

Revision ID: 0002_phase1_models
Revises: 0001_phase0_foundation
Create Date: 2026-11-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_phase1_models"
down_revision: str | None = "0001_phase0_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Tier Category Caps (Spend Tier x Category limit matrix)
    op.create_table(
        "tier_category_caps",
        sa.Column("tier_code", sa.String(length=32), nullable=False),
        sa.Column("category_code", sa.String(length=48), nullable=False),
        sa.Column("cap_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["category_code"], ["expense_categories.code"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tier_code"], ["policy_tiers.code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tier_code", "category_code"),
    )

    # 2. Receipt Scans (Immutable OCR provenance & mobile metadata)
    op.create_table(
        "receipt_scans",
        sa.Column("receipt_id", sa.String(length=64), nullable=False),
        sa.Column("image_sha256", sa.String(length=64), nullable=False),
        sa.Column("image_phash", sa.String(length=64), nullable=True),
        sa.Column("file_path", sa.String(length=512), nullable=True),
        sa.Column("raw_extraction_json", sa.JSON(), nullable=True),
        sa.Column("image_width", sa.Integer(), nullable=True),
        sa.Column("image_height", sa.Integer(), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("mime_type", sa.String(length=64), nullable=True),
        sa.Column("thumbnail_path", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("receipt_id"),
    )
    op.create_index("ix_receipt_scans_image_sha256", "receipt_scans", ["image_sha256"], unique=False)

    # 3. Expense Claims (Core claim entity with 10-state lifecycle & integer paise)
    op.create_table(
        "expense_claims",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("receipt_id", sa.String(length=64), nullable=True),
        sa.Column("claimant_id", sa.String(length=36), nullable=False),
        sa.Column("department_id", sa.String(length=36), nullable=False),
        sa.Column("vendor_name", sa.String(length=120), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("category_code", sa.String(length=48), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="INR"),
        sa.Column("total_amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("tax_amount_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("blacklisted_deduction_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("eligible_amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("approved_amount_paise", sa.BigInteger(), nullable=True),
        sa.Column("is_over_cap", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("over_cap_reasons", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="DRAFT"),
        sa.Column("rejection_reason", sa.String(length=500), nullable=True),
        sa.Column("return_comment", sa.String(length=500), nullable=True),
        sa.Column("payment_reference", sa.String(length=120), nullable=True),
        sa.Column("ocr_diff", sa.JSON(), nullable=True),
        sa.Column("policy_snapshot", sa.JSON(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["category_code"], ["expense_categories.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["claimant_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["receipt_id"], ["receipt_scans.receipt_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_expense_claims_receipt_id", "expense_claims", ["receipt_id"], unique=False)
    op.create_index("ix_expense_claims_claimant_id", "expense_claims", ["claimant_id"], unique=False)
    op.create_index("ix_expense_claims_department_id", "expense_claims", ["department_id"], unique=False)
    op.create_index("ix_expense_claims_category_code", "expense_claims", ["category_code"], unique=False)
    op.create_index("ix_expense_claims_invoice_date", "expense_claims", ["invoice_date"], unique=False)
    op.create_index("ix_expense_claims_status", "expense_claims", ["status"], unique=False)
    op.create_index("ix_expense_claims_claimant_status", "expense_claims", ["claimant_id", "status"], unique=False)
    op.create_index("ix_expense_claims_dept_status", "expense_claims", ["department_id", "status"], unique=False)

    # 4. Claim Line Items (Itemization and blacklist tagging)
    op.create_table(
        "claim_line_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("claim_id", sa.String(length=36), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("unit_price_paise", sa.BigInteger(), nullable=True),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("item_tag", sa.String(length=48), nullable=False, server_default="other"),
        sa.Column("is_excluded", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["claim_id"], ["expense_claims.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_claim_line_items_claim_id", "claim_line_items", ["claim_id"], unique=False)

    # 5. Claim Events (Append-only audit trail)
    op.create_table(
        "claim_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("claim_id", sa.String(length=36), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("actor_role", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=48), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("comment", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["claim_id"], ["expense_claims.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_claim_events_claim_id", "claim_events", ["claim_id"], unique=False)
    op.create_index("ix_claim_events_actor_id", "claim_events", ["actor_id"], unique=False)

    # 6. Monthly Quota Ledgers (Composite PK user_id + YYYY-MM)
    op.create_table(
        "monthly_quota_ledgers",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("year_month", sa.String(length=7), nullable=False),
        sa.Column("disbursed_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("reserved_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "year_month"),
    )

    # 7. Idempotency Records (Dropped connection & double-tap protection)
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=48), nullable=False),
        sa.Column("resource_id", sa.String(length=36), nullable=True),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "idempotency_key", "action", name="uq_idempotency_records_user_key_action"),
    )
    op.create_index("ix_idempotency_records_user_id", "idempotency_records", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_idempotency_records_user_id", table_name="idempotency_records")
    op.drop_table("idempotency_records")

    op.drop_table("monthly_quota_ledgers")

    op.drop_index("ix_claim_events_actor_id", table_name="claim_events")
    op.drop_index("ix_claim_events_claim_id", table_name="claim_events")
    op.drop_table("claim_events")

    op.drop_index("ix_claim_line_items_claim_id", table_name="claim_line_items")
    op.drop_table("claim_line_items")

    op.drop_index("ix_expense_claims_dept_status", table_name="expense_claims")
    op.drop_index("ix_expense_claims_claimant_status", table_name="expense_claims")
    op.drop_index("ix_expense_claims_status", table_name="expense_claims")
    op.drop_index("ix_expense_claims_invoice_date", table_name="expense_claims")
    op.drop_index("ix_expense_claims_category_code", table_name="expense_claims")
    op.drop_index("ix_expense_claims_department_id", table_name="expense_claims")
    op.drop_index("ix_expense_claims_claimant_id", table_name="expense_claims")
    op.drop_index("ix_expense_claims_receipt_id", table_name="expense_claims")
    op.drop_table("expense_claims")

    op.drop_index("ix_receipt_scans_image_sha256", table_name="receipt_scans")
    op.drop_table("receipt_scans")

    op.drop_table("tier_category_caps")

