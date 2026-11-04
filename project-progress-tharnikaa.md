# ExpenseIt — Personal Progress Tracker (`project-progress-tharnikaa.md`)

**Developer / System 1 Lead:** `@Tharnikaa`  
**Repository:** `https://github.com/Tharnikaa/Classify_budget.git`  
**Current Active Branch:** `feature/phase1_project`  
**Role & Owned Areas (`AGENTS.md`):** Backend Core, Database Models & SQLite/PostgreSQL Concurrency, Alembic Migrations (Sole Owner), Policy & Quota Engine, Approval / Dispatch Workflows, and Shared Contract Governance.

---

## 1. Scope & Ownership Breakdown

According to the master collaboration plan ([`plan.md`](file:///f:/Budget_classify/plan.md)) and agent governance rules ([`AGENTS.md`](file:///f:/Budget_classify/AGENTS.md)):

| Phase | Phase Name | Primary Owner | Status | Deliverables / Focus Areas |
|---|---|---|---|---|
| **Phase 0** | Foundation & Collaboration Enablers | **Tharnikaa** (Solo Setup) | **Completed** | Monorepo structure, OpenAPI 3.1 contracts, stateful FastAPI stubs, Expo mobile shell, CI/CD, tests. |
| **Phase 1** | Data Modeling & Policy DB | **Tharnikaa** | **Completed** | SQLAlchemy 2.0 models, Alembic migrations, PostgreSQL/SQLite compatibility, seed scripts. |
| **Phase 2** | Receipt OCR & Vision AI | Collaborator (System 2) | *Delegated* | Implements `backend/app/ocr/gemini_provider.py` behind `OCRServiceProtocol`. |
| **Phase 3** | Policy & Limits Verification Engine | **Tharnikaa** | *Planned* | Quota holds, blacklist deductions, anti-tampering `ocr_diff`, INR paise validation. |
| **Phase 4** | Claims Workflow & Disbursement Engine | **Tharnikaa** | *Planned* | 10-state lifecycle, Separation-of-Duties (SoD) routing, FH override, idempotent dispatch. |
| **Phase 5** | Mobile Client Experience | Collaborator (System 2) | *Delegated* | React Native / Expo screens, Camera capture, review UI, approval dashboards. |
| **Phase 6** | Cloud PostgreSQL Staging & E2E Hardening | **Joint** | *Planned* | Neon/Supabase staging deployment, concurrency verification, demo readiness. |

---

## 2. Phase-by-Phase Task Tracker

### Phase 0: Foundation & Synchronization (Completed)
- [x] Initialized Git repository with `main` and `develop` branching strategy.
- [x] Formulated shared governance documentation: [`AGENTS.md`](file:///f:/Budget_classify/AGENTS.md), [`COLLABORATION.md`](file:///f:/Budget_classify/COLLABORATION.md), and [`.github/CODEOWNERS`](file:///f:/Budget_classify/.github/CODEOWNERS).
- [x] Authored OpenAPI 3.1 contract specification ([`contracts/openapi.yaml`](file:///f:/Budget_classify/contracts/openapi.yaml)) and Draft 2020-12 JSON schemas ([`contracts/schemas/`](file:///f:/Budget_classify/contracts/schemas/)).
- [x] Seeded pinned personas ([`contracts/seed_personas.json`](file:///f:/Budget_classify/contracts/seed_personas.json)) and default INR paise limits ([`contracts/seed_policies.json`](file:///f:/Budget_classify/contracts/seed_policies.json)).
- [x] Created synthetic test receipt fixtures ([`tests/fixtures/receipts/`](file:///f:/Budget_classify/tests/fixtures/receipts/)).
- [x] Built FastAPI stateful stub backend with SQLite WAL mode, JWT auth, and SoD guards.
- [x] Built React Native / Expo client shell with WCAG 2.1 AA Teal tokens and `__DEV__` role switcher.
- [x] Configured GitHub Actions CI pipeline ([`.github/workflows/ci.yml`](file:///f:/Budget_classify/.github/workflows/ci.yml)).
- [x] Verified full backend test suite (9/9 passed) and frontend typecheck (`tsc --noEmit` clean).
- [x] Pushed baseline commit `f891a50` to `origin/main` and `origin/develop`.

---

### Phase 1: Data Modeling & Policy DB (Completed — `feature/phase1_project`)
- [x] **Database Schema Expansion:**
  - [x] `departments`: Department codes, display names, and monthly departmental budget caps.
  - [x] `policy_tiers`: Spend tier definitions (`JUNIOR`, `SENIOR`, `MANAGER`, `NONE`) and monthly INR caps.
  - [x] `expense_categories`: Dynamic category definitions (`MEALS`, `TRAVEL`, `LODGING`, etc.).
  - [x] `tier_category_caps`: Composite matrix mapping `(tier_code, category_code) -> cap_paise`.
  - [x] `users`: Employee profiles, role (`EMPLOYEE`, `DEPT_HEAD`, `FINANCE_MANAGER`, `FINANCE_HEAD`), spend tier, department FK, password hash.
  - [x] `receipt_scans`: Immutable store for raw OCR extractions (`receipt_id`, image SHA-256, pHash, raw JSON payload, width/height/size/mime for mobile).
  - [x] `expense_claims`: Claims table with 10-state status, claimant FK, INR paise fields (`total`, `tax`, `blacklisted_deduction`, `eligible`, `approved`), policy snapshot, and `ocr_diff`.
  - [x] `claim_line_items`: Line items with tags (`meal`, `alcohol`, `transport`, etc.) and exclusion flags.
  - [x] `claim_events`: Append-only audit log of status transitions, approver actions, and comments.
  - [x] `monthly_quota_ledgers`: `(user_id, year_month)` tracking `disbursed_paise` and `reserved_paise` powering mobile live quota cards.
  - [x] `idempotency_records`: Atomic uniqueness on `(user_id, idempotency_key, action)` to protect against dropped mobile connections and double-taps.
- [x] **Alembic Migration:**
  - [x] Generated clean, reversible migration script under `backend/migrations/versions/0002_phase1_models.py`.
  - [x] Verified upgrade and downgrade against SQLite WAL and PostgreSQL compatibility.
- [x] **Deterministic Seed Script:**
  - [x] Implemented `backend/scripts/seed_db.py` to populate DB from `contracts/seed_*.json` with hashed passwords.
  - [x] Seeded the 3 baseline mobile workflow claims (clean coffee, multi-item hotel with alcohol deduction, over-cap flight escalation).
- [x] **Unit & Model Tests:**
  - [x] Wrote SQLAlchemy ORM model tests and relationship integrity tests in `backend/tests/test_models.py`.
  - [x] Verified full backend suite: 16/16 tests passing (100%), and zero errors in `ruff check app tests scripts`.

---

### Phase 3: Policy & Limits Verification Engine (Upcoming)
- [ ] Implement factual blacklist item deduction logic with prorated tax handling.
- [ ] Implement IST calendar month (`Asia/Kolkata`) monthly quota reservation and commit ledger.
- [ ] Implement anti-tampering `ocr_diff` calculation against immutable `receipt_scans`.
- [ ] Implement duplicate detection engine (perceptual hash + composite fingerprint).
- [ ] Implement receipt staleness check (> 60 days flag).

---

### Phase 4: Claims Workflow & Disbursement Engine (Upcoming)
- [ ] Implement 10-state state machine transition router with strict SoD validation (`actor_id != claimant_id`).
- [ ] Implement Department Head approval queue and cross-department access restrictions (BOLA/IDOR protection).
- [ ] Implement Finance Head override endpoint for `ESCALATED_TO_FH` claims (full approval, clamping, or rejection).
- [ ] Implement Finance Manager fund dispatch endpoint with `Idempotency-Key` protection.
- [ ] Implement transactional notification dispatch on state transitions.

---

### Phase 6: Cloud PostgreSQL Staging & E2E Hardening (Joint)
- [ ] Connect backend to shared Cloud PostgreSQL instance (Neon / Supabase).
- [ ] Run high-concurrency race condition tests (`SELECT ... FOR UPDATE` quota locking).
- [ ] Validate end-to-end flow across all 5 user roles with mobile client.
- [ ] Verify security gating: confirm `POST /api/v1/auth/dev-switch-role` returns `404` when `APP_ENV=production`.

---

## 3. Milestones & Release Log

| Date | Branch / Tag | Milestone Summary |
|---|---|---|
| **2026-11-03** | `main`, `develop` | **Milestone 0 (Phase 0 Complete):** Initial release with synchronized contracts, stateful backend stubs, and Expo client skeleton. |
| **2026-11-04** | `feature/phase1_project` | **Milestone 1 (Phase 1 Complete):** Implemented mobile-first SQLAlchemy 2.0 ORM models, Alembic migration `0002_phase1_models`, deterministic database seeder with 3 baseline mobile workflow claims, and comprehensive test suite with 100% pass rate (16/16). |

