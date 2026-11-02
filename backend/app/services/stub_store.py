"""Stateful Phase 0 Seeded Store backing all OpenAPI v1 endpoints.

Loads pinned personas (`contracts/seed_personas.json`) and INR paise policies
(`contracts/seed_policies.json`) so System 2 can develop the entire React Native / Expo
client against realistic, stateful responses from Day 1.
"""

from __future__ import annotations

import io
import json
from datetime import UTC, date, datetime
from functools import lru_cache
from threading import RLock
from uuid import uuid4
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw

from app.core.config import CONTRACTS_DIR, get_settings
from app.core.errors import ApiError
from app.ocr.mock_provider import MockOCRProvider
from app.schemas.api import (
    AnalyticsOverviewResponse,
    CategoryItem,
    ClaimEvent,
    ClaimLineItem,
    ClaimLineItemInput,
    ClaimPrecheckRequest,
    ClaimPrecheckResponse,
    ClaimStatusEnum,
    CreateCategoryRequest,
    CreateClaimRequest,
    DispatchFundsRequest,
    ExpenseClaim,
    ExtractedReceipt,
    FinanceHeadOverrideRequest,
    MockPresetName,
    MonthlyQuotaSummary,
    NotificationTypeEnum,
    OcrDiffEntry,
    PolicyLimitsResponse,
    PolicySnapshot,
    RoleEnum,
    SpendTierEnum,
    SpendTierInfo,
    TierCategoryCapMap,
    UpdateClaimRequest,
    UpdatePolicyLimitsRequest,
    UserProfile,
)
from app.services.notifications import InMemoryNotificationService
from app.services.storage import LocalDiskStorageService

IST = ZoneInfo("Asia/Kolkata")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _current_ist_year_month() -> str:
    return datetime.now(IST).strftime("%Y-%m")


def _make_placeholder_png(label: str) -> bytes:
    img = Image.new("RGB", (480, 640), color=(240, 253, 250))
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, 460, 620], outline=(15, 118, 110), width=3)
    draw.text((40, 50), "EXPENSEIT SYNTHETIC RECEIPT", fill=(15, 23, 42))
    draw.text((40, 100), label, fill=(15, 118, 110))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class StubStateStore:
    """Thread-safe stateful store enforcing all Phase 0 domain, quota, and SoD rules."""

    def __init__(self) -> None:
        self._lock = RLock()
        settings = get_settings()
        self.storage = LocalDiskStorageService(settings.STORAGE_LOCAL_DIR)
        self.notifications = InMemoryNotificationService()
        self.mock_ocr = MockOCRProvider()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            personas_raw = json.loads((CONTRACTS_DIR / "seed_personas.json").read_text("utf-8"))
            policies_raw = json.loads((CONTRACTS_DIR / "seed_policies.json").read_text("utf-8"))

            self.dev_password: str = personas_raw["dev_default_password"]
            self.base_currency: str = policies_raw["base_currency"]
            self.company_timezone: str = policies_raw["company_timezone"]
            self.receipt_staleness_days: int = policies_raw["receipt_staleness_days"]
            self.blacklisted_tags: list[str] = list(policies_raw["blacklisted_item_tags"])

            self.users_by_id: dict[str, UserProfile] = {}
            self.users_by_email: dict[str, UserProfile] = {}
            self.users_by_persona: dict[str, UserProfile] = {}
            for u in personas_raw["users"]:
                profile = UserProfile(**u)
                self.users_by_id[profile.id] = profile
                self.users_by_email[profile.email.lower()] = profile
                self.users_by_persona[profile.persona_key] = profile

            self.spend_tiers: dict[str, SpendTierInfo] = {
                k: SpendTierInfo(**v) for k, v in policies_raw["spend_tiers"].items()
            }
            self.categories: dict[str, CategoryItem] = {
                c["code"]: CategoryItem(**c) for c in policies_raw["categories"]
            }
            self.tier_category_caps: dict[str, TierCategoryCapMap] = {
                code: TierCategoryCapMap(**caps)
                for code, caps in policies_raw["tier_category_caps_paise"].items()
            }

            self.receipt_scans: dict[str, ExtractedReceipt] = {}
            self.claims: dict[str, ExpenseClaim] = {}
            self.audit_events: list[ClaimEvent] = []
            self.idempotency_claims: dict[tuple[str, str], str] = {}
            self.idempotency_dispatches: dict[tuple[str, str], str] = {}
            self.notifications = InMemoryNotificationService()

            self._seed_sample_workflows()

    # -------------------- User & Policy Helpers --------------------

    def get_user_by_id(self, user_id: str) -> UserProfile | None:
        return self.users_by_id.get(user_id)

    def authenticate(self, email: str, password: str) -> UserProfile:
        user = self.users_by_email.get(email.lower().strip())
        if user is None or password != self.dev_password:
            raise ApiError(
                status_code=401,
                code="INVALID_CREDENTIALS",
                message="Invalid email or password.",
            )
        return user

    def get_persona(self, persona_key: str) -> UserProfile:
        user = self.users_by_persona.get(persona_key)
        if user is None:
            raise ApiError(
                status_code=404,
                code="PERSONA_NOT_FOUND",
                message=f"Seeded persona '{persona_key}' does not exist.",
            )
        return user

    def list_personas(self) -> list[UserProfile]:
        return list(self.users_by_id.values())

    def list_categories(self, active_only: bool = True) -> list[CategoryItem]:
        cats = list(self.categories.values())
        return [c for c in cats if c.is_active] if active_only else cats

    def create_category(self, actor: UserProfile, req: CreateCategoryRequest) -> CategoryItem:
        with self._lock:
            if req.code in self.categories:
                raise ApiError(
                    status_code=409,
                    code="CATEGORY_EXISTS",
                    message=f"Category '{req.code}' already exists.",
                )
            cat = CategoryItem(
                code=req.code, name=req.name, description=req.description, is_active=True
            )
            self.categories[req.code] = cat
            self.tier_category_caps[req.code] = TierCategoryCapMap(
                JUNIOR=req.junior_cap_paise,
                SENIOR=req.senior_cap_paise,
                MANAGER=req.manager_cap_paise,
            )
            self._record_audit(
                actor=actor,
                action="CATEGORY_CREATED",
                from_status=None,
                to_status=req.code,
                comment=f"Added category {req.name}",
            )
            return cat

    def get_policy_limits(self) -> PolicyLimitsResponse:
        return PolicyLimitsResponse(
            base_currency=self.base_currency,
            company_timezone=self.company_timezone,
            blacklisted_item_tags=list(self.blacklisted_tags),
            spend_tiers=dict(self.spend_tiers),
            tier_category_caps_paise=dict(self.tier_category_caps),
        )

    def update_policy_limits(
        self, actor: UserProfile, req: UpdatePolicyLimitsRequest
    ) -> PolicyLimitsResponse:
        with self._lock:
            if req.tier_monthly_caps_paise:
                for tier_code, cap in req.tier_monthly_caps_paise.items():
                    if tier_code not in self.spend_tiers:
                        raise ApiError(
                            status_code=400,
                            code="UNKNOWN_SPEND_TIER",
                            message=f"Unknown spend tier '{tier_code}'.",
                        )
                    if cap < 0:
                        raise ApiError(
                            status_code=400,
                            code="INVALID_LIMIT",
                            message="Monthly cap must be non-negative paise.",
                        )
                    info = self.spend_tiers[tier_code]
                    self.spend_tiers[tier_code] = info.model_copy(update={"monthly_cap_paise": cap})

            if req.tier_category_caps_paise:
                for cat_code, tier_updates in req.tier_category_caps_paise.items():
                    if cat_code not in self.tier_category_caps:
                        raise ApiError(
                            status_code=400,
                            code="UNKNOWN_CATEGORY",
                            message=f"Unknown category '{cat_code}'.",
                        )
                    current = self.tier_category_caps[cat_code].model_dump()
                    for t_key, val in tier_updates.items():
                        if t_key not in current or val < 0:
                            raise ApiError(
                                status_code=400,
                                code="INVALID_CATEGORY_CAP",
                                message=f"Invalid tier '{t_key}' or negative cap.",
                            )
                        current[t_key] = val
                    self.tier_category_caps[cat_code] = TierCategoryCapMap(**current)

            self._record_audit(
                actor=actor,
                action="POLICY_LIMITS_UPDATED",
                from_status="ACTIVE",
                to_status="ACTIVE",
                comment="Updated spend tier / category INR paise limits",
            )
            fh = self.users_by_persona.get("finance_head")
            if fh:
                self.notifications.notify(
                    user_id=fh.id,
                    actor_id=actor.id,
                    notif_type=NotificationTypeEnum.POLICY_LIMIT_UPDATED,
                    title="Spend Limits Updated",
                    message=f"{actor.full_name} updated corporate spend limits.",
                )
            return self.get_policy_limits()

    # -------------------- Quota & Policy Calculation --------------------

    def get_monthly_quota(
        self, user: UserProfile, year_month: str | None = None, exclude_claim_id: str | None = None
    ) -> MonthlyQuotaSummary:
        ym = year_month or _current_ist_year_month()
        monthly_cap = self.spend_tiers[user.spend_tier.value].monthly_cap_paise
        disbursed = 0
        reserved = 0
        reserved_statuses = {
            ClaimStatusEnum.PENDING_APPROVAL,
            ClaimStatusEnum.RETURNED_FOR_CORRECTION,
            ClaimStatusEnum.APPROVED_BY_DEPT,
            ClaimStatusEnum.ESCALATED_TO_FH,
            ClaimStatusEnum.VERIFIED_FOR_DISPATCH,
            ClaimStatusEnum.DISPATCH_FAILED,
        }
        for c in self.claims.values():
            if c.id == exclude_claim_id:
                continue
            if c.claimant_id != user.id or c.invoice_date[:7] != ym:
                continue
            if c.status == ClaimStatusEnum.DISPATCHED:
                disbursed += c.approved_amount_paise or c.eligible_amount_paise
            elif c.status in reserved_statuses:
                reserved += (
                    c.approved_amount_paise
                    if c.approved_amount_paise is not None
                    else c.eligible_amount_paise
                )
        remaining = max(0, monthly_cap - disbursed - reserved)
        return MonthlyQuotaSummary(
            user_id=user.id,
            spend_tier=user.spend_tier,
            year_month=ym,
            currency="INR",
            monthly_cap_paise=monthly_cap,
            disbursed_paise=disbursed,
            reserved_paise=reserved,
            remaining_paise=remaining,
        )

    def _compute_blacklist_deduction(
        self,
        total_amount_paise: int,
        tax_amount_paise: int,
        line_items: list[ClaimLineItemInput],
    ) -> tuple[int, list[ClaimLineItem]]:
        blacklisted_set = set(self.blacklisted_tags)
        raw_blacklisted = 0
        line_subtotal = 0
        normalized_items: list[ClaimLineItem] = []

        for item in line_items:
            excluded = item.item_tag.value in blacklisted_set
            if excluded:
                raw_blacklisted += item.amount_paise
            line_subtotal += item.amount_paise
            normalized_items.append(
                ClaimLineItem(
                    description=item.description,
                    quantity=item.quantity,
                    unit_price_paise=item.unit_price_paise,
                    amount_paise=item.amount_paise,
                    item_tag=item.item_tag.value,
                    is_excluded=excluded,
                )
            )

        if (
            raw_blacklisted > 0
            and tax_amount_paise > 0
            and line_subtotal > 0
            and abs((line_subtotal + tax_amount_paise) - total_amount_paise) <= 100
        ):
            prorated_tax = round(tax_amount_paise * raw_blacklisted / line_subtotal)
            deduction = min(total_amount_paise, raw_blacklisted + prorated_tax)
        else:
            deduction = min(total_amount_paise, raw_blacklisted)

        return deduction, normalized_items

    def _get_category_cap_for_tier(self, category_code: str, spend_tier: SpendTierEnum) -> int:
        if category_code not in self.tier_category_caps:
            raise ApiError(
                status_code=400,
                code="UNKNOWN_CATEGORY",
                message=f"Category '{category_code}' is not an active expense category.",
            )
        if spend_tier == SpendTierEnum.NONE:
            return 0
        caps = self.tier_category_caps[category_code].model_dump()
        return int(caps[spend_tier.value])

    def precheck_claim(
        self,
        user: UserProfile,
        req: ClaimPrecheckRequest,
        exclude_claim_id: str | None = None,
    ) -> ClaimPrecheckResponse:
        blocking_errors: list[str] = []
        warnings: list[str] = []

        if user.role == RoleEnum.FINANCE_HEAD or user.spend_tier == SpendTierEnum.NONE:
            blocking_errors.append("ROLE_CANNOT_RAISE_CLAIM")

        if req.currency.upper() != self.base_currency:
            blocking_errors.append("UNSUPPORTED_CURRENCY")

        if (
            req.category_code not in self.categories
            or not self.categories[req.category_code].is_active
        ):
            blocking_errors.append("UNKNOWN_CATEGORY")

        deduction, _ = self._compute_blacklist_deduction(
            req.total_amount_paise, req.tax_amount_paise, req.line_items
        )
        eligible = max(0, req.total_amount_paise - deduction)
        if deduction > 0:
            warnings.append("BLACKLIST_ITEMS_EXCLUDED")

        category_cap = (
            self._get_category_cap_for_tier(req.category_code, user.spend_tier)
            if req.category_code in self.tier_category_caps
            and user.spend_tier != SpendTierEnum.NONE
            else 0
        )
        quota = self.get_monthly_quota(
            user, year_month=req.invoice_date[:7], exclude_claim_id=exclude_claim_id
        )

        will_escalate = False
        if user.spend_tier != SpendTierEnum.NONE and eligible > category_cap:
            warnings.append("CATEGORY_CAP_EXCEEDED")
            will_escalate = True

        if user.spend_tier != SpendTierEnum.NONE and eligible > quota.remaining_paise:
            warnings.append("MONTHLY_CAP_EXCEEDED")
            will_escalate = True

        try:
            inv_date = date.fromisoformat(req.invoice_date)
            today_ist = datetime.now(IST).date()
            if (today_ist - inv_date).days > self.receipt_staleness_days:
                warnings.append("STALE_RECEIPT")
                will_escalate = True
        except ValueError:
            blocking_errors.append("INVALID_INVOICE_DATE")

        # Duplicate composite fingerprint check
        norm_vendor = req.vendor_name.strip().lower()
        for existing in self.claims.values():
            if existing.id == exclude_claim_id:
                continue
            if existing.status in {ClaimStatusEnum.REJECTED, ClaimStatusEnum.WITHDRAWN}:
                continue
            if (
                existing.vendor_name.strip().lower() == norm_vendor
                and existing.invoice_date == req.invoice_date
                and existing.total_amount_paise == req.total_amount_paise
            ):
                warnings.append("POTENTIAL_DUPLICATE")
                will_escalate = True
                break

        return ClaimPrecheckResponse(
            can_submit=len(blocking_errors) == 0,
            blocking_errors=blocking_errors,
            warnings=warnings,
            total_amount_paise=req.total_amount_paise,
            blacklisted_deduction_paise=deduction,
            eligible_amount_paise=eligible,
            category_cap_paise=category_cap,
            remaining_monthly_paise=quota.remaining_paise,
            will_escalate_to_fh=will_escalate,
        )

    # -------------------- OCR & Receipt Storage --------------------

    async def scan_uploaded_receipt(self, data: bytes) -> ExtractedReceipt:
        rid = f"rcpt-{uuid4().hex[:12]}"
        stored = self.storage.save_receipt(rid, data)
        active_cats = [
            {"code": c.code, "name": c.name, "description": c.description}
            for c in self.list_categories(active_only=True)
        ]
        extracted = await self.mock_ocr.extract_receipt(data, stored.mime_type, active_cats)
        final_receipt = extracted.model_copy(
            update={
                "receipt_id": rid,
                "image_sha256": stored.sha256,
                "image_url": f"/api/v1/receipts/{rid}/image",
            }
        )
        with self._lock:
            self.receipt_scans[rid] = final_receipt
        return final_receipt

    def create_mock_scan(self, preset: MockPresetName) -> ExtractedReceipt:
        rid = f"rcpt-{uuid4().hex[:12]}"
        img_bytes = _make_placeholder_png(f"Preset: {preset} ({rid})")
        stored = self.storage.save_receipt(rid, img_bytes)
        receipt = self.mock_ocr.build_preset(
            preset=preset, receipt_id=rid, image_sha256=stored.sha256
        )
        with self._lock:
            self.receipt_scans[rid] = receipt
        return receipt

    # -------------------- Claims CRUD & Workflow --------------------

    def _compute_ocr_diff(
        self, receipt_id: str | None, req: CreateClaimRequest
    ) -> dict[str, OcrDiffEntry]:
        if not receipt_id or receipt_id not in self.receipt_scans:
            return {}
        scan = self.receipt_scans[receipt_id]
        diff: dict[str, OcrDiffEntry] = {}
        if scan.vendor_name != req.vendor_name:
            diff["vendor_name"] = OcrDiffEntry(
                ocr_value=scan.vendor_name, submitted_value=req.vendor_name
            )
        if scan.invoice_date != req.invoice_date:
            diff["invoice_date"] = OcrDiffEntry(
                ocr_value=scan.invoice_date, submitted_value=req.invoice_date
            )
        if scan.total_amount_paise != req.total_amount_paise:
            diff["total_amount_paise"] = OcrDiffEntry(
                ocr_value=scan.total_amount_paise, submitted_value=req.total_amount_paise
            )
        if len(scan.line_items) != len(req.line_items):
            diff["line_items_count"] = OcrDiffEntry(
                ocr_value=len(scan.line_items), submitted_value=len(req.line_items)
            )
        return diff

    def create_claim(
        self,
        user: UserProfile,
        req: CreateClaimRequest,
        idempotency_key: str | None = None,
    ) -> ExpenseClaim:
        with self._lock:
            if user.role == RoleEnum.FINANCE_HEAD or user.spend_tier == SpendTierEnum.NONE:
                raise ApiError(
                    status_code=403,
                    code="FINANCE_HEAD_CANNOT_RAISE_CLAIM",
                    message="Finance Head is a global oversight role and cannot submit personal claims in MVP.",
                )

            if idempotency_key:
                existing_id = self.idempotency_claims.get((user.id, idempotency_key))
                if existing_id and existing_id in self.claims:
                    return self.claims[existing_id]

            precheck = self.precheck_claim(
                user,
                ClaimPrecheckRequest(
                    **req.model_dump(exclude={"description", "submit_immediately"})
                ),
            )
            if not precheck.can_submit:
                raise ApiError(
                    status_code=400,
                    code=precheck.blocking_errors[0],
                    message=f"Claim failed policy validation: {', '.join(precheck.blocking_errors)}",
                    details={"blocking_errors": precheck.blocking_errors},
                )

            deduction, normalized_items = self._compute_blacklist_deduction(
                req.total_amount_paise, req.tax_amount_paise, req.line_items
            )
            eligible = max(0, req.total_amount_paise - deduction)
            over_cap_reasons = [
                w
                for w in precheck.warnings
                if w
                in {
                    "CATEGORY_CAP_EXCEEDED",
                    "MONTHLY_CAP_EXCEEDED",
                    "STALE_RECEIPT",
                    "POTENTIAL_DUPLICATE",
                }
            ]
            now = _now_iso()
            claim_id = f"clm-{uuid4().hex[:12]}"
            initial_status = (
                ClaimStatusEnum.PENDING_APPROVAL
                if req.submit_immediately
                else ClaimStatusEnum.DRAFT
            )
            receipt_url = f"/api/v1/receipts/{req.receipt_id}/image" if req.receipt_id else None

            snapshot = PolicySnapshot(
                spend_tier=user.spend_tier.value,
                category_code=req.category_code,
                category_cap_paise=precheck.category_cap_paise,
                monthly_cap_paise=self.spend_tiers[user.spend_tier.value].monthly_cap_paise,
                blacklisted_item_tags=list(self.blacklisted_tags),
                captured_at=now,
            )

            ev = self._make_event(
                actor=user,
                action="CLAIM_SUBMITTED" if req.submit_immediately else "DRAFT_SAVED",
                from_status=None,
                to_status=initial_status.value,
                comment=req.description,
            )

            claim = ExpenseClaim(
                id=claim_id,
                receipt_id=req.receipt_id,
                receipt_url=receipt_url,
                claimant_id=user.id,
                claimant_name=user.full_name,
                role=user.role,
                spend_tier=user.spend_tier,
                department_id=user.department_id,
                department_name=user.department_name,
                vendor_name=req.vendor_name,
                invoice_date=req.invoice_date,
                category_code=req.category_code,
                description=req.description,
                currency="INR",
                total_amount_paise=req.total_amount_paise,
                tax_amount_paise=req.tax_amount_paise,
                blacklisted_deduction_paise=deduction,
                eligible_amount_paise=eligible,
                approved_amount_paise=None,
                is_over_cap=len(over_cap_reasons) > 0,
                over_cap_reasons=over_cap_reasons,
                status=initial_status,
                line_items=normalized_items,
                ocr_diff=self._compute_ocr_diff(req.receipt_id, req),
                policy_snapshot=snapshot,
                events=[ev],
                submitted_at=now if req.submit_immediately else None,
                created_at=now,
                updated_at=now,
            )
            self.claims[claim_id] = claim
            if idempotency_key:
                self.idempotency_claims[(user.id, idempotency_key)] = claim_id

            if req.submit_immediately:
                self._notify_initial_approver(claim, user)

            return claim

    def _notify_initial_approver(self, claim: ExpenseClaim, claimant: UserProfile) -> None:
        if claimant.role == RoleEnum.EMPLOYEE:
            approvers = [
                u
                for u in self.users_by_id.values()
                if u.role == RoleEnum.DEPT_HEAD and u.department_id == claimant.department_id
            ]
        else:
            approvers = [u for u in self.users_by_id.values() if u.role == RoleEnum.FINANCE_HEAD]
        for approver in approvers:
            self.notifications.notify(
                user_id=approver.id,
                actor_id=claimant.id,
                notif_type=NotificationTypeEnum.CLAIM_SUBMITTED,
                title="New Expense Claim Submitted",
                message=f"{claimant.full_name} submitted a claim for {claim.vendor_name}.",
                claim_id=claim.id,
            )

    def _assert_can_view_claim(self, user: UserProfile, claim: ExpenseClaim) -> None:
        if user.role in {RoleEnum.FINANCE_HEAD, RoleEnum.FINANCE_MANAGER}:
            return
        if claim.claimant_id == user.id:
            return
        if user.role == RoleEnum.DEPT_HEAD and claim.department_id == user.department_id:
            return
        raise ApiError(
            status_code=403,
            code="FORBIDDEN_CLAIM_ACCESS",
            message="You do not have permission to access this claim.",
        )

    def get_claim(self, user: UserProfile, claim_id: str) -> ExpenseClaim:
        claim = self.claims.get(claim_id)
        if claim is None:
            raise ApiError(status_code=404, code="CLAIM_NOT_FOUND", message="Claim not found.")
        self._assert_can_view_claim(user, claim)
        return claim

    def list_claims(
        self,
        user: UserProfile,
        status: ClaimStatusEnum | None = None,
        scope: str | None = None,
    ) -> list[ExpenseClaim]:
        results: list[ExpenseClaim] = []
        for c in self.claims.values():
            if scope == "mine":
                if c.claimant_id != user.id:
                    continue
            elif scope == "queue":
                if c.claimant_id == user.id:
                    continue
                if user.role == RoleEnum.EMPLOYEE:
                    continue
                if user.role == RoleEnum.DEPT_HEAD:
                    if not (
                        c.department_id == user.department_id
                        and c.role == RoleEnum.EMPLOYEE
                        and c.status == ClaimStatusEnum.PENDING_APPROVAL
                    ):
                        continue
                elif user.role == RoleEnum.FINANCE_MANAGER:
                    if c.status not in {
                        ClaimStatusEnum.APPROVED_BY_DEPT,
                        ClaimStatusEnum.VERIFIED_FOR_DISPATCH,
                        ClaimStatusEnum.DISPATCH_FAILED,
                    }:
                        continue
                elif user.role == RoleEnum.FINANCE_HEAD:
                    is_mgr_pending = (
                        c.role in {RoleEnum.DEPT_HEAD, RoleEnum.FINANCE_MANAGER}
                        and c.status == ClaimStatusEnum.PENDING_APPROVAL
                    )
                    if not (is_mgr_pending or c.status == ClaimStatusEnum.ESCALATED_TO_FH):
                        continue
            else:
                if user.role == RoleEnum.EMPLOYEE and c.claimant_id != user.id:
                    continue
                if (
                    user.role == RoleEnum.DEPT_HEAD
                    and c.department_id != user.department_id
                    and c.claimant_id != user.id
                ):
                    continue

            if status is not None and c.status != status:
                continue
            results.append(c)

        results.sort(key=lambda item: item.updated_at, reverse=True)
        return results

    def update_claim(
        self, user: UserProfile, claim_id: str, req: UpdateClaimRequest
    ) -> ExpenseClaim:
        with self._lock:
            claim = self.get_claim(user, claim_id)
            if claim.claimant_id != user.id:
                raise ApiError(
                    status_code=403,
                    code="ONLY_CLAIMANT_CAN_AMEND",
                    message="Only the claimant can edit a draft or returned claim.",
                )
            if claim.status not in {
                ClaimStatusEnum.DRAFT,
                ClaimStatusEnum.RETURNED_FOR_CORRECTION,
            }:
                raise ApiError(
                    status_code=409,
                    code="INVALID_CLAIM_STATE",
                    message=f"Cannot edit claim in status '{claim.status.value}'.",
                )

            vendor = req.vendor_name if req.vendor_name is not None else claim.vendor_name
            inv_date = req.invoice_date if req.invoice_date is not None else claim.invoice_date
            cat_code = req.category_code if req.category_code is not None else claim.category_code
            desc = req.description if req.description is not None else claim.description
            total_paise = (
                req.total_amount_paise
                if req.total_amount_paise is not None
                else claim.total_amount_paise
            )
            tax_paise = (
                req.tax_amount_paise if req.tax_amount_paise is not None else claim.tax_amount_paise
            )
            line_inputs = (
                req.line_items
                if req.line_items is not None
                else [
                    ClaimLineItemInput(
                        description=li.description,
                        quantity=li.quantity,
                        unit_price_paise=li.unit_price_paise,
                        amount_paise=li.amount_paise,
                        item_tag=li.item_tag,  # type: ignore[arg-type]
                    )
                    for li in claim.line_items
                ]
            )

            precheck = self.precheck_claim(
                user,
                ClaimPrecheckRequest(
                    receipt_id=claim.receipt_id,
                    vendor_name=vendor,
                    invoice_date=inv_date,
                    category_code=cat_code,
                    currency="INR",
                    total_amount_paise=total_paise,
                    tax_amount_paise=tax_paise,
                    line_items=line_inputs,
                ),
                exclude_claim_id=claim.id,
            )
            if not precheck.can_submit:
                raise ApiError(
                    status_code=400,
                    code=precheck.blocking_errors[0],
                    message="Updated claim failed policy validation.",
                )

            deduction, normalized_items = self._compute_blacklist_deduction(
                total_paise, tax_paise, line_inputs
            )
            eligible = max(0, total_paise - deduction)
            over_cap_reasons = [
                w
                for w in precheck.warnings
                if w
                in {
                    "CATEGORY_CAP_EXCEEDED",
                    "MONTHLY_CAP_EXCEEDED",
                    "STALE_RECEIPT",
                    "POTENTIAL_DUPLICATE",
                }
            ]
            new_status = ClaimStatusEnum.PENDING_APPROVAL if req.resubmit else claim.status
            now = _now_iso()
            ev = self._make_event(
                actor=user,
                action="CLAIM_RESUBMITTED" if req.resubmit else "CLAIM_AMENDED",
                from_status=claim.status.value,
                to_status=new_status.value,
                comment="Amended claim fields",
            )
            updated = claim.model_copy(
                update={
                    "vendor_name": vendor,
                    "invoice_date": inv_date,
                    "category_code": cat_code,
                    "description": desc,
                    "total_amount_paise": total_paise,
                    "tax_amount_paise": tax_paise,
                    "blacklisted_deduction_paise": deduction,
                    "eligible_amount_paise": eligible,
                    "is_over_cap": len(over_cap_reasons) > 0,
                    "over_cap_reasons": over_cap_reasons,
                    "line_items": normalized_items,
                    "status": new_status,
                    "submitted_at": now
                    if req.resubmit and not claim.submitted_at
                    else claim.submitted_at,
                    "updated_at": now,
                    "events": [*claim.events, ev],
                }
            )
            self.claims[claim_id] = updated
            if req.resubmit:
                self._notify_initial_approver(updated, user)
            return updated

    def withdraw_claim(self, user: UserProfile, claim_id: str) -> ExpenseClaim:
        with self._lock:
            claim = self.get_claim(user, claim_id)
            if claim.claimant_id != user.id:
                raise ApiError(
                    status_code=403,
                    code="ONLY_CLAIMANT_CAN_WITHDRAW",
                    message="Only the claimant can withdraw their claim.",
                )
            if claim.status not in {
                ClaimStatusEnum.DRAFT,
                ClaimStatusEnum.PENDING_APPROVAL,
                ClaimStatusEnum.RETURNED_FOR_CORRECTION,
            }:
                raise ApiError(
                    status_code=409,
                    code="INVALID_CLAIM_STATE",
                    message=f"Cannot withdraw claim in status '{claim.status.value}'.",
                )
            ev = self._make_event(
                actor=user,
                action="CLAIM_WITHDRAWN",
                from_status=claim.status.value,
                to_status=ClaimStatusEnum.WITHDRAWN.value,
                comment="Withdrawn by claimant",
            )
            updated = claim.model_copy(
                update={
                    "status": ClaimStatusEnum.WITHDRAWN,
                    "updated_at": _now_iso(),
                    "events": [*claim.events, ev],
                }
            )
            self.claims[claim_id] = updated
            return updated

    def _assert_step1_approver(self, actor: UserProfile, claim: ExpenseClaim) -> None:
        if actor.id == claim.claimant_id:
            raise ApiError(
                status_code=403,
                code="SOD_SELF_ACTION_FORBIDDEN",
                message="Separation of Duties violation: cannot review your own claim.",
            )
        if claim.role == RoleEnum.EMPLOYEE:
            if actor.role != RoleEnum.DEPT_HEAD or actor.department_id != claim.department_id:
                raise ApiError(
                    status_code=403,
                    code="FORBIDDEN_APPROVER",
                    message="Employee claims must be reviewed by their own Department Head.",
                )
        elif claim.role in {RoleEnum.DEPT_HEAD, RoleEnum.FINANCE_MANAGER}:
            if actor.role != RoleEnum.FINANCE_HEAD:
                raise ApiError(
                    status_code=403,
                    code="FORBIDDEN_APPROVER",
                    message="Department Head and Finance Manager claims must be approved by the Finance Head.",
                )

    def approve_claim(
        self, actor: UserProfile, claim_id: str, comment: str | None = None
    ) -> ExpenseClaim:
        with self._lock:
            claim = self.get_claim(actor, claim_id)
            if claim.status != ClaimStatusEnum.PENDING_APPROVAL:
                raise ApiError(
                    status_code=409,
                    code="INVALID_CLAIM_STATE",
                    message=f"Claim must be PENDING_APPROVAL (currently {claim.status.value}).",
                )
            self._assert_step1_approver(actor, claim)
            now = _now_iso()
            ev = self._make_event(
                actor=actor,
                action="CLAIM_APPROVED",
                from_status=claim.status.value,
                to_status=ClaimStatusEnum.APPROVED_BY_DEPT.value,
                comment=comment,
            )
            updated = claim.model_copy(
                update={
                    "status": ClaimStatusEnum.APPROVED_BY_DEPT,
                    "approved_at": now,
                    "updated_at": now,
                    "events": [*claim.events, ev],
                }
            )
            self.claims[claim_id] = updated
            self.notifications.notify(
                user_id=claim.claimant_id,
                actor_id=actor.id,
                notif_type=NotificationTypeEnum.DEPT_APPROVED,
                title="Claim Approved",
                message=f"{actor.full_name} approved your claim for {claim.vendor_name}.",
                claim_id=claim.id,
            )
            for fm in self.users_by_id.values():
                if fm.role == RoleEnum.FINANCE_MANAGER and fm.id != claim.claimant_id:
                    self.notifications.notify(
                        user_id=fm.id,
                        actor_id=actor.id,
                        notif_type=NotificationTypeEnum.DEPT_APPROVED,
                        title="Claim Ready for Finance Verification",
                        message=f"Claim {claim.id} ({claim.vendor_name}) awaits verification.",
                        claim_id=claim.id,
                    )
            return updated

    def return_claim(self, actor: UserProfile, claim_id: str, reason: str) -> ExpenseClaim:
        with self._lock:
            claim = self.get_claim(actor, claim_id)
            if claim.status != ClaimStatusEnum.PENDING_APPROVAL:
                raise ApiError(
                    status_code=409,
                    code="INVALID_CLAIM_STATE",
                    message=f"Claim must be PENDING_APPROVAL (currently {claim.status.value}).",
                )
            self._assert_step1_approver(actor, claim)
            now = _now_iso()
            ev = self._make_event(
                actor=actor,
                action="CLAIM_RETURNED",
                from_status=claim.status.value,
                to_status=ClaimStatusEnum.RETURNED_FOR_CORRECTION.value,
                comment=reason,
            )
            updated = claim.model_copy(
                update={
                    "status": ClaimStatusEnum.RETURNED_FOR_CORRECTION,
                    "return_comment": reason,
                    "updated_at": now,
                    "events": [*claim.events, ev],
                }
            )
            self.claims[claim_id] = updated
            self.notifications.notify(
                user_id=claim.claimant_id,
                actor_id=actor.id,
                notif_type=NotificationTypeEnum.CLAIM_RETURNED,
                title="Clarification Requested",
                message=f"{actor.full_name} returned your claim: {reason}",
                claim_id=claim.id,
            )
            return updated

    def reject_claim(self, actor: UserProfile, claim_id: str, reason: str) -> ExpenseClaim:
        with self._lock:
            claim = self.get_claim(actor, claim_id)
            if claim.status == ClaimStatusEnum.PENDING_APPROVAL:
                self._assert_step1_approver(actor, claim)
            elif claim.status == ClaimStatusEnum.ESCALATED_TO_FH:
                if actor.role != RoleEnum.FINANCE_HEAD or actor.id == claim.claimant_id:
                    raise ApiError(
                        status_code=403,
                        code="FORBIDDEN_APPROVER",
                        message="Only Finance Head can reject an escalated claim.",
                    )
            else:
                raise ApiError(
                    status_code=409,
                    code="INVALID_CLAIM_STATE",
                    message=f"Cannot reject claim in status '{claim.status.value}'.",
                )
            now = _now_iso()
            ev = self._make_event(
                actor=actor,
                action="CLAIM_REJECTED",
                from_status=claim.status.value,
                to_status=ClaimStatusEnum.REJECTED.value,
                comment=reason,
            )
            updated = claim.model_copy(
                update={
                    "status": ClaimStatusEnum.REJECTED,
                    "rejection_reason": reason,
                    "updated_at": now,
                    "events": [*claim.events, ev],
                }
            )
            self.claims[claim_id] = updated
            self.notifications.notify(
                user_id=claim.claimant_id,
                actor_id=actor.id,
                notif_type=NotificationTypeEnum.CLAIM_REJECTED,
                title="Claim Rejected",
                message=f"{actor.full_name} rejected your claim: {reason}",
                claim_id=claim.id,
            )
            return updated

    def verify_claim(
        self, actor: UserProfile, claim_id: str, comment: str | None = None
    ) -> ExpenseClaim:
        with self._lock:
            claim = self.get_claim(actor, claim_id)
            if actor.id == claim.claimant_id:
                raise ApiError(
                    status_code=403,
                    code="SOD_SELF_ACTION_FORBIDDEN",
                    message="Separation of Duties violation: Finance Manager cannot verify their own claim.",
                )
            if claim.status != ClaimStatusEnum.APPROVED_BY_DEPT:
                raise ApiError(
                    status_code=409,
                    code="INVALID_CLAIM_STATE",
                    message=f"Claim must be APPROVED_BY_DEPT (currently {claim.status.value}).",
                )

            now = _now_iso()
            # If claim was already approved by Finance Head (DH/FM claim) and is within caps, verify directly;
            # if over cap (and not yet overridden), escalate to Finance Head!
            if claim.is_over_cap:
                target_status = ClaimStatusEnum.ESCALATED_TO_FH
                approved_paise = None
                action = "ESCALATED_OVER_CAP"
            else:
                target_status = ClaimStatusEnum.VERIFIED_FOR_DISPATCH
                approved_paise = claim.eligible_amount_paise
                action = "CLAIM_VERIFIED"

            ev = self._make_event(
                actor=actor,
                action=action,
                from_status=claim.status.value,
                to_status=target_status.value,
                comment=comment,
            )
            updated = claim.model_copy(
                update={
                    "status": target_status,
                    "approved_amount_paise": approved_paise,
                    "verified_at": now
                    if target_status == ClaimStatusEnum.VERIFIED_FOR_DISPATCH
                    else None,
                    "updated_at": now,
                    "events": [*claim.events, ev],
                }
            )
            self.claims[claim_id] = updated

            if target_status == ClaimStatusEnum.ESCALATED_TO_FH:
                fh = self.users_by_persona.get("finance_head")
                if fh:
                    self.notifications.notify(
                        user_id=fh.id,
                        actor_id=actor.id,
                        notif_type=NotificationTypeEnum.CLAIM_ESCALATED,
                        title="Over-Cap Claim Escalated",
                        message=f"Claim {claim.id} ({claim.vendor_name}) requires Finance Head override.",
                        claim_id=claim.id,
                    )
                self.notifications.notify(
                    user_id=claim.claimant_id,
                    actor_id=actor.id,
                    notif_type=NotificationTypeEnum.CLAIM_ESCALATED,
                    title="Claim Escalated for Cap Exception",
                    message=f"Your claim for {claim.vendor_name} exceeds policy caps and was escalated to Finance Head.",
                    claim_id=claim.id,
                )
            return updated

    def override_claim(
        self, actor: UserProfile, claim_id: str, req: FinanceHeadOverrideRequest
    ) -> ExpenseClaim:
        with self._lock:
            claim = self.get_claim(actor, claim_id)
            if actor.id == claim.claimant_id:
                raise ApiError(
                    status_code=403,
                    code="SOD_SELF_ACTION_FORBIDDEN",
                    message="Separation of Duties violation: cannot override your own claim.",
                )
            if claim.status != ClaimStatusEnum.ESCALATED_TO_FH:
                raise ApiError(
                    status_code=409,
                    code="INVALID_CLAIM_STATE",
                    message=f"Claim must be ESCALATED_TO_FH (currently {claim.status.value}).",
                )

            if req.decision == "REJECT":
                return self.reject_claim(actor, claim_id, req.comment)

            claimant = self.users_by_id[claim.claimant_id]
            quota_without_this = self.get_monthly_quota(
                claimant, year_month=claim.invoice_date[:7], exclude_claim_id=claim.id
            )
            if req.decision == "APPROVE_FULL_ELIGIBLE":
                approved_paise = (
                    req.custom_approved_paise
                    if req.custom_approved_paise is not None
                    else claim.eligible_amount_paise
                )
            else:
                # CLAMP_TO_CAP
                cat_cap = claim.policy_snapshot.category_cap_paise
                approved_paise = min(
                    claim.eligible_amount_paise,
                    cat_cap,
                    quota_without_this.remaining_paise,
                )

            now = _now_iso()
            ev = self._make_event(
                actor=actor,
                action=f"FH_{req.decision}",
                from_status=claim.status.value,
                to_status=ClaimStatusEnum.VERIFIED_FOR_DISPATCH.value,
                comment=req.comment,
            )
            updated = claim.model_copy(
                update={
                    "status": ClaimStatusEnum.VERIFIED_FOR_DISPATCH,
                    "approved_amount_paise": approved_paise,
                    "verified_at": now,
                    "updated_at": now,
                    "events": [*claim.events, ev],
                }
            )
            self.claims[claim_id] = updated

            self.notifications.notify(
                user_id=claim.claimant_id,
                actor_id=actor.id,
                notif_type=NotificationTypeEnum.OVERRIDE_APPLIED,
                title="Finance Head Exception Resolved",
                message=f"Finance Head resolved your escalated claim ({req.decision}).",
                claim_id=claim.id,
            )
            for fm in self.users_by_id.values():
                if fm.role == RoleEnum.FINANCE_MANAGER and fm.id != claim.claimant_id:
                    self.notifications.notify(
                        user_id=fm.id,
                        actor_id=actor.id,
                        notif_type=NotificationTypeEnum.OVERRIDE_APPLIED,
                        title="Escalated Claim Ready for Dispatch",
                        message=f"Claim {claim.id} resolved by Finance Head and ready for payout.",
                        claim_id=claim.id,
                    )
            return updated

    def dispatch_claim(
        self,
        actor: UserProfile,
        claim_id: str,
        req: DispatchFundsRequest | None = None,
        idempotency_key: str | None = None,
    ) -> ExpenseClaim:
        with self._lock:
            claim = self.get_claim(actor, claim_id)
            if actor.id == claim.claimant_id:
                raise ApiError(
                    status_code=403,
                    code="SOD_SELF_ACTION_FORBIDDEN",
                    message="Separation of Duties violation: Finance Manager cannot dispatch funds to themselves.",
                )

            if idempotency_key:
                prev_claim_id = self.idempotency_dispatches.get((claim_id, idempotency_key))
                if prev_claim_id and claim.status == ClaimStatusEnum.DISPATCHED:
                    return claim

            if claim.status not in {
                ClaimStatusEnum.VERIFIED_FOR_DISPATCH,
                ClaimStatusEnum.DISPATCH_FAILED,
            }:
                raise ApiError(
                    status_code=409,
                    code="INVALID_CLAIM_STATE",
                    message=f"Claim must be VERIFIED_FOR_DISPATCH or DISPATCH_FAILED (currently {claim.status.value}).",
                )

            now = _now_iso()
            if req and req.simulate_failure:
                ev_fail = self._make_event(
                    actor=actor,
                    action="DISPATCH_FAILED",
                    from_status=claim.status.value,
                    to_status=ClaimStatusEnum.DISPATCH_FAILED.value,
                    comment="Simulated payout gateway timeout",
                )
                failed = claim.model_copy(
                    update={
                        "status": ClaimStatusEnum.DISPATCH_FAILED,
                        "updated_at": now,
                        "events": [*claim.events, ev_fail],
                    }
                )
                self.claims[claim_id] = failed
                return failed

            pay_ref = (
                req.payment_reference
                if req and req.payment_reference
                else f"UTR-INR-{uuid4().hex[:10].upper()}"
            )
            ev = self._make_event(
                actor=actor,
                action="FUNDS_DISPATCHED",
                from_status=claim.status.value,
                to_status=ClaimStatusEnum.DISPATCHED.value,
                comment=f"Payment Reference: {pay_ref}",
            )
            updated = claim.model_copy(
                update={
                    "status": ClaimStatusEnum.DISPATCHED,
                    "approved_amount_paise": claim.approved_amount_paise
                    or claim.eligible_amount_paise,
                    "payment_reference": pay_ref,
                    "dispatched_at": now,
                    "updated_at": now,
                    "events": [*claim.events, ev],
                }
            )
            self.claims[claim_id] = updated
            if idempotency_key:
                self.idempotency_dispatches[(claim_id, idempotency_key)] = claim_id

            self.notifications.notify(
                user_id=claim.claimant_id,
                actor_id=actor.id,
                notif_type=NotificationTypeEnum.FUNDS_DISPATCHED,
                title="Reimbursement Dispatched",
                message=f"Funds for {claim.vendor_name} dispatched ({pay_ref}).",
                claim_id=claim.id,
            )
            return updated

    # -------------------- Analytics & Audit --------------------

    def get_analytics_overview(self) -> AnalyticsOverviewResponse:
        disbursed = 0
        pending = 0
        escalated_count = 0
        by_dept: dict[str, int] = {}
        by_cat: dict[str, int] = {}

        for c in self.claims.values():
            amt = c.approved_amount_paise or c.eligible_amount_paise
            if c.status == ClaimStatusEnum.DISPATCHED:
                disbursed += amt
                by_dept[c.department_name] = by_dept.get(c.department_name, 0) + amt
                by_cat[c.category_code] = by_cat.get(c.category_code, 0) + amt
            elif c.status not in {
                ClaimStatusEnum.REJECTED,
                ClaimStatusEnum.WITHDRAWN,
                ClaimStatusEnum.DRAFT,
            }:
                pending += amt
            if c.status == ClaimStatusEnum.ESCALATED_TO_FH:
                escalated_count += 1

        return AnalyticsOverviewResponse(
            currency="INR",
            total_claims_count=len(self.claims),
            total_disbursed_paise=disbursed,
            total_pending_paise=pending,
            escalated_count=escalated_count,
            spend_by_department=by_dept,
            spend_by_category=by_cat,
        )

    def list_audit_logs(self) -> list[ClaimEvent]:
        return list(self.audit_events)

    def _make_event(
        self,
        *,
        actor: UserProfile,
        action: str,
        from_status: str | None,
        to_status: str,
        comment: str | None = None,
    ) -> ClaimEvent:
        ev = ClaimEvent(
            id=f"evt-{uuid4().hex[:12]}",
            actor_id=actor.id,
            actor_name=actor.full_name,
            actor_role=actor.role.value,
            action=action,
            from_status=from_status,
            to_status=to_status,
            comment=comment,
            created_at=_now_iso(),
        )
        self.audit_events.insert(0, ev)
        return ev

    def _record_audit(
        self,
        *,
        actor: UserProfile,
        action: str,
        from_status: str | None,
        to_status: str,
        comment: str | None = None,
    ) -> None:
        self._make_event(
            actor=actor,
            action=action,
            from_status=from_status,
            to_status=to_status,
            comment=comment,
        )

    # -------------------- Initial Seed Workflows --------------------

    def _seed_sample_workflows(self) -> None:
        ym = _current_ist_year_month()
        junior = self.users_by_persona["junior_employee"]
        senior = self.users_by_persona["senior_employee"]
        eng_dh = self.users_by_persona["eng_dept_head"]
        fm1 = self.users_by_persona["finance_manager_1"]

        # 1. Junior clean meal pending Dept Head approval
        r1 = self.create_mock_scan("clean_meal")
        self.create_claim(
            junior,
            CreateClaimRequest(
                receipt_id=r1.receipt_id,
                vendor_name="Third Wave Coffee Roasters",
                invoice_date=f"{ym}-01",
                category_code="MEALS",
                description="Client sprint planning coffee",
                currency="INR",
                total_amount_paise=44100,
                tax_amount_paise=2100,
                line_items=[
                    ClaimLineItemInput(
                        description="Cappuccino & Sourdough Toast",
                        quantity=1,
                        unit_price_paise=42000,
                        amount_paise=42000,
                        item_tag="meal",  # type: ignore[arg-type]
                    )
                ],
            ),
        )

        # 2. Senior hotel stay with alcohol item -> approved by DH, escalated to FH due to lodging/alcohol demo
        r2 = self.create_mock_scan("over_cap_flight")
        c2 = self.create_claim(
            senior,
            CreateClaimRequest(
                receipt_id=r2.receipt_id,
                vendor_name="IndiGo Airlines",
                invoice_date=f"{ym}-02",
                category_code="TRAVEL",
                description="Customer onsite flight BLR-DEL",
                currency="INR",
                total_amount_paise=819000,
                tax_amount_paise=39000,
                line_items=[
                    ClaimLineItemInput(
                        description="BLR -> DEL Return Economy Fare",
                        quantity=1,
                        unit_price_paise=780000,
                        amount_paise=780000,
                        item_tag="transport",  # type: ignore[arg-type]
                    )
                ],
            ),
        )
        self.approve_claim(eng_dh, c2.id, "Onsite customer visit approved")
        self.verify_claim(
            fm1, c2.id, "Exceeds Senior ₹5,000 per-claim Travel cap; escalating to FH"
        )

        # 3. Completed dispatched claim for Junior employee (shows disbursed_paise on dashboard)
        c3 = self.create_claim(
            junior,
            CreateClaimRequest(
                vendor_name="Uber India",
                invoice_date=f"{ym}-01",
                category_code="TRAVEL",
                description="Airport transfer",
                currency="INR",
                total_amount_paise=125000,
                tax_amount_paise=5000,
                line_items=[
                    ClaimLineItemInput(
                        description="Airport Cab",
                        quantity=1,
                        unit_price_paise=120000,
                        amount_paise=120000,
                        item_tag="transport",  # type: ignore[arg-type]
                    )
                ],
            ),
        )
        self.approve_claim(eng_dh, c3.id, "Approved airport cab")
        self.verify_claim(fm1, c3.id, "Within Junior Travel & Monthly cap")
        self.dispatch_claim(fm1, c3.id, DispatchFundsRequest(payment_reference="UTR-INR-SEED0001"))


@lru_cache(maxsize=1)
def get_stub_store() -> StubStateStore:
    return StubStateStore()
