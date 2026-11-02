"""Pydantic v2 API schemas synchronized with contracts/openapi.yaml."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field


class RoleEnum(StrEnum):
    EMPLOYEE = "EMPLOYEE"
    DEPT_HEAD = "DEPT_HEAD"
    FINANCE_MANAGER = "FINANCE_MANAGER"
    FINANCE_HEAD = "FINANCE_HEAD"


class SpendTierEnum(StrEnum):
    JUNIOR = "JUNIOR"
    SENIOR = "SENIOR"
    MANAGER = "MANAGER"
    NONE = "NONE"


class ClaimStatusEnum(StrEnum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    RETURNED_FOR_CORRECTION = "RETURNED_FOR_CORRECTION"
    APPROVED_BY_DEPT = "APPROVED_BY_DEPT"
    ESCALATED_TO_FH = "ESCALATED_TO_FH"
    VERIFIED_FOR_DISPATCH = "VERIFIED_FOR_DISPATCH"
    DISPATCHED = "DISPATCHED"
    DISPATCH_FAILED = "DISPATCH_FAILED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"


class ItemTagEnum(StrEnum):
    MEAL = "meal"
    ALCOHOL = "alcohol"
    TOBACCO = "tobacco"
    GIFT_CARD = "gift_card"
    PERSONAL = "personal"
    LODGING = "lodging"
    TRANSPORT = "transport"
    OFFICE_SUPPLY = "office_supply"
    SOFTWARE = "software"
    TELECOM = "telecom"
    TAX_FEE = "tax_fee"
    OTHER = "other"


class NotificationTypeEnum(StrEnum):
    CLAIM_SUBMITTED = "CLAIM_SUBMITTED"
    DEPT_APPROVED = "DEPT_APPROVED"
    CLAIM_RETURNED = "CLAIM_RETURNED"
    CLAIM_REJECTED = "CLAIM_REJECTED"
    CLAIM_ESCALATED = "CLAIM_ESCALATED"
    OVERRIDE_APPLIED = "OVERRIDE_APPLIED"
    FUNDS_DISPATCHED = "FUNDS_DISPATCHED"
    POLICY_LIMIT_UPDATED = "POLICY_LIMIT_UPDATED"


class UserProfile(BaseModel):
    id: str
    persona_key: str
    full_name: str
    email: EmailStr
    role: RoleEnum
    spend_tier: SpendTierEnum
    department_id: str
    department_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class DevSwitchRoleRequest(BaseModel):
    persona_key: str


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile


class CategoryItem(BaseModel):
    code: str
    name: str
    description: str
    is_active: bool = True


class CreateCategoryRequest(BaseModel):
    code: str = Field(..., pattern=r"^[A-Z0-9_]+$")
    name: str = Field(..., min_length=2)
    description: str = Field(..., min_length=3)
    junior_cap_paise: int = Field(..., ge=0)
    senior_cap_paise: int = Field(..., ge=0)
    manager_cap_paise: int = Field(..., ge=0)


class SpendTierInfo(BaseModel):
    display_name: str
    monthly_cap_paise: int = Field(..., ge=0)


class TierCategoryCapMap(BaseModel):
    JUNIOR: int = Field(..., ge=0)
    SENIOR: int = Field(..., ge=0)
    MANAGER: int = Field(..., ge=0)


class PolicyLimitsResponse(BaseModel):
    base_currency: str = "INR"
    company_timezone: str = "Asia/Kolkata"
    blacklisted_item_tags: list[str]
    spend_tiers: dict[str, SpendTierInfo]
    tier_category_caps_paise: dict[str, TierCategoryCapMap]


class UpdatePolicyLimitsRequest(BaseModel):
    tier_monthly_caps_paise: dict[str, int] | None = None
    tier_category_caps_paise: dict[str, dict[str, int]] | None = None


class MonthlyQuotaSummary(BaseModel):
    user_id: str
    spend_tier: SpendTierEnum
    year_month: str
    currency: str = "INR"
    monthly_cap_paise: int = Field(..., ge=0)
    disbursed_paise: int = Field(..., ge=0)
    reserved_paise: int = Field(..., ge=0)
    remaining_paise: int = Field(..., ge=0)


class FieldConfidence(BaseModel):
    vendor: float = Field(..., ge=0.0, le=1.0)
    date: float = Field(..., ge=0.0, le=1.0)
    total: float = Field(..., ge=0.0, le=1.0)
    category: float = Field(..., ge=0.0, le=1.0)


class ExtractedLineItem(BaseModel):
    description: str
    quantity: float = Field(default=1.0, ge=0.0)
    unit_price_paise: int | None = Field(default=None, ge=0)
    amount_paise: int = Field(..., ge=0)
    item_tag: ItemTagEnum


class ExtractedReceipt(BaseModel):
    schema_version: str = "1.0.0"
    receipt_id: str
    image_url: str | None = None
    image_sha256: str
    image_phash: str | None = None
    is_valid_receipt: bool = True
    vendor_name: str | None = None
    vendor_tax_id: str | None = None
    invoice_date: str | None = None
    detected_currency: str = "INR"
    subtotal_amount_paise: int | None = Field(default=None, ge=0)
    tax_amount_paise: int = Field(default=0, ge=0)
    total_amount_paise: int = Field(..., ge=0)
    suggested_category_code: str
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    field_confidence: FieldConfidence
    line_items: list[ExtractedLineItem]


MockPresetName = Literal[
    "clean_meal",
    "hotel_with_alcohol",
    "over_cap_flight",
    "blurry_missing_date",
    "foreign_usd",
]


class MockScanRequest(BaseModel):
    preset: MockPresetName


class ClaimLineItemInput(BaseModel):
    description: str = Field(..., min_length=1)
    quantity: float = Field(default=1.0, ge=0.0)
    unit_price_paise: int | None = Field(default=None, ge=0)
    amount_paise: int = Field(..., ge=0)
    item_tag: ItemTagEnum


class ClaimLineItem(BaseModel):
    description: str
    quantity: float = Field(..., ge=0.0)
    unit_price_paise: int | None = None
    amount_paise: int = Field(..., ge=0)
    item_tag: str
    is_excluded: bool


class ClaimPrecheckRequest(BaseModel):
    receipt_id: str | None = None
    vendor_name: str = Field(..., min_length=1)
    invoice_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    category_code: str = Field(..., min_length=1)
    currency: str = "INR"
    total_amount_paise: int = Field(..., ge=0)
    tax_amount_paise: int = Field(default=0, ge=0)
    line_items: list[ClaimLineItemInput]


class ClaimPrecheckResponse(BaseModel):
    can_submit: bool
    blocking_errors: list[str]
    warnings: list[str]
    total_amount_paise: int
    blacklisted_deduction_paise: int
    eligible_amount_paise: int
    category_cap_paise: int
    remaining_monthly_paise: int
    will_escalate_to_fh: bool


class CreateClaimRequest(BaseModel):
    receipt_id: str | None = None
    vendor_name: str = Field(..., min_length=1)
    invoice_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    category_code: str = Field(..., min_length=1)
    description: str | None = None
    currency: str = "INR"
    total_amount_paise: int = Field(..., ge=0)
    tax_amount_paise: int = Field(default=0, ge=0)
    submit_immediately: bool = True
    line_items: list[ClaimLineItemInput]


class UpdateClaimRequest(BaseModel):
    vendor_name: str | None = None
    invoice_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    category_code: str | None = None
    description: str | None = None
    total_amount_paise: int | None = Field(default=None, ge=0)
    tax_amount_paise: int | None = Field(default=None, ge=0)
    resubmit: bool = False
    line_items: list[ClaimLineItemInput] | None = None


class OcrDiffEntry(BaseModel):
    ocr_value: Any
    submitted_value: Any


class PolicySnapshot(BaseModel):
    spend_tier: str
    category_code: str
    category_cap_paise: int
    monthly_cap_paise: int
    blacklisted_item_tags: list[str]
    captured_at: str


class ClaimEvent(BaseModel):
    id: str
    actor_id: str
    actor_name: str
    actor_role: str
    action: str
    from_status: str | None
    to_status: str
    comment: str | None = None
    created_at: str


class ExpenseClaim(BaseModel):
    schema_version: str = "1.0.0"
    id: str
    receipt_id: str | None = None
    receipt_url: str | None = None
    claimant_id: str
    claimant_name: str
    role: RoleEnum
    spend_tier: SpendTierEnum
    department_id: str
    department_name: str
    vendor_name: str
    invoice_date: str
    category_code: str
    description: str | None = None
    currency: str = "INR"
    total_amount_paise: int
    tax_amount_paise: int
    blacklisted_deduction_paise: int
    eligible_amount_paise: int
    approved_amount_paise: int | None = None
    is_over_cap: bool
    over_cap_reasons: list[str]
    status: ClaimStatusEnum
    rejection_reason: str | None = None
    return_comment: str | None = None
    payment_reference: str | None = None
    line_items: list[ClaimLineItem]
    ocr_diff: dict[str, OcrDiffEntry]
    policy_snapshot: PolicySnapshot
    events: list[ClaimEvent]
    submitted_at: str | None = None
    approved_at: str | None = None
    verified_at: str | None = None
    dispatched_at: str | None = None
    created_at: str
    updated_at: str


class WorkflowCommentRequest(BaseModel):
    comment: str | None = None


class WorkflowReasonRequest(BaseModel):
    reason: str = Field(..., min_length=3)


class FinanceHeadOverrideRequest(BaseModel):
    decision: Literal["APPROVE_FULL_ELIGIBLE", "CLAMP_TO_CAP", "REJECT"]
    custom_approved_paise: int | None = Field(default=None, ge=0)
    comment: str = Field(..., min_length=2)


class DispatchFundsRequest(BaseModel):
    payment_reference: str | None = None
    simulate_failure: bool = False


class NotificationItem(BaseModel):
    schema_version: str = "1.0.0"
    id: str
    user_id: str
    actor_id: str | None = None
    type: NotificationTypeEnum
    title: str
    message: str
    claim_id: str | None = None
    deep_link: str
    is_read: bool = False
    created_at: str


class PushTokenRequest(BaseModel):
    expo_push_token: str = Field(..., min_length=5)
    platform: Literal["android", "ios", "web"]


class AnalyticsOverviewResponse(BaseModel):
    currency: str = "INR"
    total_claims_count: int
    total_disbursed_paise: int
    total_pending_paise: int
    escalated_count: int
    spend_by_department: dict[str, int]
    spend_by_category: dict[str, int]

