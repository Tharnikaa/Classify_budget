# ExpenseIt — Claim State Machine & Accounting Rules (`docs/state-machine.md`)

## 1. Ten-State Lifecycle Transition Matrix

Every transition enforces **`actor.id != claim.claimant_id`** (except claimant-initiated `submit`, `amend`, and `withdraw` actions).

| From State | Action | To State | Permitted Actor(s) | Quota Ledger Effect | Emitted Notification |
|---|---|---|---|---|---|
| *(Scan)* | Save Draft / Scan | `DRAFT` | Claimant (`EMPLOYEE`, `DEPT_HEAD`, `FINANCE_MANAGER`) | None | None |
| `DRAFT` | Submit Claim | `PENDING_APPROVAL` | Claimant (`claimant_id == actor.id`) | `reserved_paise += eligible_amount_paise` | `CLAIM_SUBMITTED` (to DH or FH) |
| `DRAFT` | Discard | `WITHDRAWN` | Claimant | None | None |
| `PENDING_APPROVAL` | Approve | `APPROVED_BY_DEPT` | Own Dept `DEPT_HEAD` (for `EMPLOYEE`) **or** `FINANCE_HEAD` (for `DEPT_HEAD` / `FINANCE_MANAGER` claim) | Keep `reserved_paise` | `DEPT_APPROVED` |
| `PENDING_APPROVAL` | Request Info | `RETURNED_FOR_CORRECTION` | Assigned Approver (`DH` or `FH`) | Keep `reserved_paise` | `CLAIM_RETURNED` |
| `RETURNED_FOR_CORRECTION` | Resubmit | `PENDING_APPROVAL` | Claimant | Adjust `reserved_paise` delta | `CLAIM_SUBMITTED` |
| `PENDING_APPROVAL` / `RETURNED_FOR_CORRECTION` | Withdraw | `WITHDRAWN` | Claimant | `reserved_paise -= held_paise` | None |
| `PENDING_APPROVAL` | Reject | `REJECTED` | Assigned Approver (`DH` or `FH`) | `reserved_paise -= held_paise` | `CLAIM_REJECTED` |
| `APPROVED_BY_DEPT` | Verify (Within Caps) | `VERIFIED_FOR_DISPATCH` | `FINANCE_MANAGER` (`actor.id != claimant_id`) | Set `approved_amount_paise = eligible_amount_paise` | None |
| `APPROVED_BY_DEPT` | Verify (Over Cap / Stale) | `ESCALATED_TO_FH` | `FINANCE_MANAGER` (`actor.id != claimant_id`) | Keep `reserved_paise` | `CLAIM_ESCALATED` (to FH + Claimant) |
| `ESCALATED_TO_FH` | Override Full / Clamp Cap | `VERIFIED_FOR_DISPATCH` | `FINANCE_HEAD` | Adjust `reserved_paise` to `approved_amount_paise` | `OVERRIDE_APPLIED` (to FM + Claimant) |
| `ESCALATED_TO_FH` | Reject Exception | `REJECTED` | `FINANCE_HEAD` | `reserved_paise -= held_paise` | `CLAIM_REJECTED` |
| `VERIFIED_FOR_DISPATCH` | Dispatch Funds (`Idempotency-Key`) | `DISPATCHED` | `FINANCE_MANAGER` (`actor.id != claimant_id`) | `reserved_paise -= approved_paise`; `disbursed_paise += approved_paise` | `FUNDS_DISPATCHED` |
| `VERIFIED_FOR_DISPATCH` | Payout Error | `DISPATCH_FAILED` | `FINANCE_MANAGER` / Payout Gateway | Keep `reserved_paise` | None |
| `DISPATCH_FAILED` | Retry Dispatch (`Idempotency-Key`) | `DISPATCHED` | `FINANCE_MANAGER` (`actor.id != claimant_id`) | Move `reserved_paise` -> `disbursed_paise` | `FUNDS_DISPATCHED` |

---

## 2. Deterministic INR Paise Accounting Formulas

### 2.1 Blacklisted Line Item Deduction
Blacklisted `item_tag` set (seeded default, configurable in policy rules):
`{"alcohol", "tobacco", "gift_card", "personal"}`

- Sum raw blacklisted line items:
  `raw_blacklisted_paise = sum(item.amount_paise for item in line_items if item.item_tag in BLACKLISTED_TAGS)`
- Tax proration (when `tax_amount_paise > 0` and pre-tax `line_subtotal_paise > 0` and `line_subtotal_paise + tax_amount_paise == total_amount_paise` within `<= 100` paise rounding tolerance):
  `prorated_tax_paise = round(tax_amount_paise * raw_blacklisted_paise / line_subtotal_paise)`
  `blacklisted_deduction_paise = min(total_amount_paise, raw_blacklisted_paise + prorated_tax_paise)`
- Otherwise (tax-inclusive line items or summary receipt):
  `blacklisted_deduction_paise = min(total_amount_paise, raw_blacklisted_paise)`
- Eligible amount:
  `eligible_amount_paise = max(0, total_amount_paise - blacklisted_deduction_paise)`

### 2.2 Monthly IST Quota Window & Staleness
- **Ledger Bucket:** `(user_id, invoice_date[:7])` interpreted in `Asia/Kolkata` (`UTC+05:30`).
- **Staleness Check:** If `(today_ist - invoice_date).days > 60`, claim carries warning `STALE_RECEIPT` and routes through `ESCALATED_TO_FH` before dispatch.
- **Cap Checks (evaluated against `policy_snapshot` captured on submission):**
  - `CATEGORY_CAP_EXCEEDED`: `eligible_amount_paise > tier_category_cap_paise`
  - `MONTHLY_CAP_EXCEEDED`: `(disbursed_paise + reserved_paise_including_this_claim) > tier_monthly_cap_paise`

