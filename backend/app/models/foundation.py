"""SQLAlchemy 2.0 ORM models for ExpenseIt (Phase 1 Mobile-First Foundation).

Financial Invariants:
- All monetary values are integer BigInteger *_paise in INR.
- Dynamic categories and multi-tier limits.
- Immutable receipt scan provenance.
- 10-state claim lifecycle with audit events and IST monthly quota tracking.
- Idempotency records for dropped mobile connections and double-taps.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class DepartmentModel(Base):
    """Department organizational entity with monthly budget caps."""

    __tablename__ = "departments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    monthly_budget_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Relationships
    users: Mapped[list[UserModel]] = relationship("UserModel", back_populates="department")
    claims: Mapped[list[ExpenseClaimModel]] = relationship("ExpenseClaimModel", back_populates="department")


class PolicyTierModel(Base):
    """Spend tier definitions (JUNIOR, SENIOR, MANAGER, NONE) and monthly overall caps."""

    __tablename__ = "policy_tiers"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    monthly_cap_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    # Relationships
    users: Mapped[list[UserModel]] = relationship("UserModel", back_populates="tier")
    category_caps: Mapped[list[TierCategoryCapModel]] = relationship(
        "TierCategoryCapModel", back_populates="tier", cascade="all, delete-orphan"
    )


class ExpenseCategoryModel(Base):
    """Dynamic business expense categories (MEALS, TRAVEL, LODGING, etc.)."""

    __tablename__ = "expense_categories"

    code: Mapped[str] = mapped_column(String(48), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Relationships
    tier_caps: Mapped[list[TierCategoryCapModel]] = relationship(
        "TierCategoryCapModel", back_populates="category", cascade="all, delete-orphan"
    )
    claims: Mapped[list[ExpenseClaimModel]] = relationship("ExpenseClaimModel", back_populates="category")


class TierCategoryCapModel(Base):
    """Matrix mapping (spend_tier, category_code) -> per-claim cap in INR paise."""

    __tablename__ = "tier_category_caps"

    tier_code: Mapped[str] = mapped_column(
        String(32), ForeignKey("policy_tiers.code", ondelete="CASCADE"), primary_key=True
    )
    category_code: Mapped[str] = mapped_column(
        String(48), ForeignKey("expense_categories.code", ondelete="CASCADE"), primary_key=True
    )
    cap_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    # Relationships
    tier: Mapped[PolicyTierModel] = relationship("PolicyTierModel", back_populates="category_caps")
    category: Mapped[ExpenseCategoryModel] = relationship("ExpenseCategoryModel", back_populates="tier_caps")


class UserModel(Base):
    """User account entity with RBAC role, spend tier, and department assignment."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    persona_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(160), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    spend_tier: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("policy_tiers.code"),
        nullable=False,
    )
    department_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("departments.id"),
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Relationships
    department: Mapped[DepartmentModel] = relationship("DepartmentModel", back_populates="users")
    tier: Mapped[PolicyTierModel] = relationship("PolicyTierModel", back_populates="users")
    claims: Mapped[list[ExpenseClaimModel]] = relationship(
        "ExpenseClaimModel",
        back_populates="claimant",
        foreign_keys="ExpenseClaimModel.claimant_id",
    )
    claim_events: Mapped[list[ClaimEventModel]] = relationship(
        "ClaimEventModel",
        back_populates="actor",
    )
    quota_ledgers: Mapped[list[MonthlyQuotaLedgerModel]] = relationship(
        "MonthlyQuotaLedgerModel",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class ReceiptScanModel(Base):
    """Immutable raw OCR extraction provenance and image metadata for mobile efficiency."""

    __tablename__ = "receipt_scans"

    receipt_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    image_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    image_phash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    raw_extraction_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    image_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Relationships
    claim: Mapped[ExpenseClaimModel | None] = relationship(
        "ExpenseClaimModel", back_populates="receipt", uselist=False
    )


class ExpenseClaimModel(Base):
    """Core expense claim entity adhering strictly to integer INR paise invariants."""

    __tablename__ = "expense_claims"

    __table_args__ = (
        Index("ix_expense_claims_claimant_status", "claimant_id", "status"),
        Index("ix_expense_claims_dept_status", "department_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    receipt_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("receipt_scans.receipt_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    claimant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    department_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    vendor_name: Mapped[str] = mapped_column(String(120), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    category_code: Mapped[str] = mapped_column(
        String(48),
        ForeignKey("expense_categories.code", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    total_amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tax_amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    blacklisted_deduction_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    eligible_amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    approved_amount_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_over_cap: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    over_cap_reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True, default="DRAFT")
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    return_comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    payment_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ocr_diff: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    policy_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    # Relationships
    receipt: Mapped[ReceiptScanModel | None] = relationship("ReceiptScanModel", back_populates="claim")
    claimant: Mapped[UserModel] = relationship(
        "UserModel",
        back_populates="claims",
        foreign_keys=[claimant_id],
    )
    department: Mapped[DepartmentModel] = relationship("DepartmentModel", back_populates="claims")
    category: Mapped[ExpenseCategoryModel] = relationship("ExpenseCategoryModel", back_populates="claims")
    line_items: Mapped[list[ClaimLineItemModel]] = relationship(
        "ClaimLineItemModel",
        back_populates="claim",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    events: Mapped[list[ClaimEventModel]] = relationship(
        "ClaimEventModel",
        back_populates="claim",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ClaimEventModel.created_at",
    )


class ClaimLineItemModel(Base):
    """Detailed line item on an expense claim with blacklist classification tags."""

    __tablename__ = "claim_line_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    claim_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("expense_claims.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    unit_price_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    item_tag: Mapped[str] = mapped_column(String(48), nullable=False, default="other")
    is_excluded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    claim: Mapped[ExpenseClaimModel] = relationship("ExpenseClaimModel", back_populates="line_items")


class ClaimEventModel(Base):
    """Append-only audit trail recording every state transition, actor, and comment."""

    __tablename__ = "claim_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    claim_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("expense_claims.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    actor_role: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(48), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Relationships
    claim: Mapped[ExpenseClaimModel] = relationship("ExpenseClaimModel", back_populates="events")
    actor: Mapped[UserModel] = relationship("UserModel", back_populates="claim_events")


class MonthlyQuotaLedgerModel(Base):
    """IST calendar month quota tracker (user_id, YYYY-MM) powering live mobile quota widgets."""

    __tablename__ = "monthly_quota_ledgers"

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    year_month: Mapped[str] = mapped_column(String(7), primary_key=True)  # Format: "YYYY-MM"
    disbursed_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    reserved_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    # Relationships
    user: Mapped[UserModel] = relationship("UserModel", back_populates="quota_ledgers")


class IdempotencyRecordModel(Base):
    """Atomic idempotency registry protecting mobile submit and dispatch against network drops."""

    __tablename__ = "idempotency_records"

    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", "action", name="uq_idempotency_user_key_action"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(48), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Relationships
    user: Mapped[UserModel] = relationship("UserModel")
