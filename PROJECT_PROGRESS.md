# ExpenseIt — Multi-Collaborator Project Progress Tracker

> **Single Source of Truth for Project Status & Synchronization**  
> **Last Updated:** 2026-11-04  
> **Current Milestone:** Milestone 0 (Phase 0 Foundation Landed on `develop`)  
> **Active Target:** Milestone 1 / Milestone 2 (Phase 1, Phase 2, Phase 5a in parallel)

---

## 1. Executive Status Dashboard

| Item | Details |
|---|---|
| **Overall Health** | 🟢 **Healthy / On Track** |
| **Current Integration Branch** | `develop` (Synced with `origin/develop`) |
| **Latest Shared Commit** | `f891a50` — *Phase 0 foundation, OpenAPI 3.1 contract stubs, and Expo mobile shell* |
| **System 1 Focus (`@Tharnikaa`)** | Phase 1: Database Models & Alembic Migrations (`backend/app/models/**`, `backend/migrations/**`) |
| **System 2 Focus (`Jai`)** | Phase 2: Vision AI Receipt OCR (`backend/app/ocr/**`) & Phase 5a: Mobile Capture & Review UI (`mobile/**`) |
| **Active Blockers** | **None** — Phase 0 stateful stubs and frozen contracts unblock 100% parallel work. |

---

## 2. Collaborator Ownership & Responsibility Matrix

| Scope / Component | Owner | System Role | Primary Branches | Permitted Paths |
|---|---|---|---|---|
| **Repository Governance & CI** | System 1 | `@Tharnikaa` | `main`, `develop` | `.github/**`, `AGENTS.md`, `COLLABORATION.md` |
| **API Contracts & JSON Schemas** | **Dual** | Both (Joint Sign-Off) | Feature PRs to `develop` | `contracts/**` |
| **Database & Migrations** | System 1 | `@Tharnikaa` | `feature/phase-1-policy-db` | `backend/app/models/**`, `backend/migrations/**` *(Sole migration owner)* |
| **Vision AI / Receipt OCR** | System 2 | `Jai` | `feature/phase-2-ocr-pipeline` | `backend/app/ocr/**` *(Adheres to `protocol.py`)* |
| **Policy & Quota Engine** | System 1 | `@Tharnikaa` | `feature/phase-3-verification-engine` | `backend/app/services/policy/**` |
| **Workflow State Machine & Payouts** | System 1 | `@Tharnikaa` | `feature/phase-4-claims-workflow` | `backend/app/services/workflow/**` |
| **Mobile Capture, Review & Employee UI** | System 2 | `Jai` | `feature/phase-5a-mobile-capture` | `mobile/src/app/**`, `mobile/src/components/**` |
| **Mobile Approver & FM Admin UI** | System 2 | `Jai` | `feature/phase-5b-role-dashboards` | `mobile/src/app/**`, `mobile/src/components/**` |
| **PostgreSQL Staging & E2E Testing** | **Dual** | Both (Joint Sign-Off) | `develop` | Root test suite, Docker/Neon staging |

---

## 3. Phase-by-Phase Roadmap & Delivery Tracker

### Phase 0: Foundation, Contracts & Synchronization
- **Lead:** System 1 (`@Tharnikaa`) | **Status:** ✅ **Completed** (Merged to `main` & `develop`)
- [x] Repository governance: `AGENTS.md`, `COLLABORATION.md`, `CODEOWNERS`, PR templates.
- [x] Contracts & Schemas: `contracts/openapi.yaml` (34 endpoints), JSON schemas, `seed_personas.json`, `seed_policies.json`.
- [x] Backend Foundation: SQLite WAL mode, Bearer JWT auth, RBAC + SoD dependencies, dev role switcher, full-surface stateful stubs.
- [x] Mobile Foundation: Expo Router 4-tab shell, WCAG AA Teal Theme tokens, `<DevRoleSwitcher />`, `<NotificationDrawer />`, TypeScript client.
- [x] CI Pipeline: GitHub Actions verifying pytest suite and Expo TypeScript types.

---

### Phase 1: Data Modeling & Policy DB
- **Lead:** System 1 (`@Tharnikaa`) | **Status:** ⏳ **Not Started / Ready to Start**
- **Branch:** `feature/phase-1-policy-db`
- [ ] SQLAlchemy 2.0 ORM models for Users, Spend Tiers, Categories, Claims, Line Items, Scans, Quota Ledgers, Audit Logs.
- [ ] Sole Alembic migration generation for complete schema.
- [ ] DB Seeding scripts from `contracts/seed_policies.json` and `contracts/seed_personas.json`.
- [ ] Integration tests verifying SQLite WAL mode and Neon PostgreSQL dialect compatibility.

---

### Phase 2: Receipt OCR & Vision AI
- **Lead:** System 2 (`Jai`) | **Status:** ✅ **Completed**
- **Branch:** `feature/phase-2-ocr-pipeline`
- [x] Implement Multi-Model Vision AI Engine (`GeminiOCRProvider`, `OpenAIOCRProvider`, `AnthropicOCRProvider`, `MockOCRProvider`) conforming to `OCRServiceProtocol`.
- [x] Dynamic category injection into Vision AI prompt with runtime active categories.
- [x] Perceptual hash (`pHash` dHash) + `SHA-256` receipt fingerprinting for duplicate detection.
- [x] Per-field confidence scoring (`vendor`, `date`, `total`, `category` in `[0.0, 1.0]`).
- [x] Factual line-item tagging (`meal`, `alcohol`, `tobacco`, `gift_card`, `personal`, `tax_fee`, etc.).
- [x] 100% passing unit tests in `backend/tests/test_multi_ocr.py` (mocked network, parsing, paise invariants).

---

### Phase 3: Policy, Blacklist & Quota Engine
- **Lead:** System 1 (`@Tharnikaa`) | **Status:** ⏸️ **Pending Phase 1**
- **Branch:** `feature/phase-3-verification-engine`
- [ ] Blacklist auto-deduction: $\text{eligible\_amount} = \text{total\_amount} - \text{blacklisted\_amount}$.
- [ ] `ocr_diff` tamper tracking comparing user edits to raw OCR scan.
- [ ] `Asia/Kolkata` (IST) calendar-month quota ledger calculation based on `invoice_date`.
- [ ] Soft quota reservation (`reserved_paise`) on claim submission; release on reject/withdrawal.
- [ ] Over-cap policy flag trigger and routing to `ESCALATED_TO_FH`.

---

### Phase 4: Claims Workflow & Disbursement Engine
- **Lead:** System 1 (`@Tharnikaa`) | **Status:** ⏸️ **Pending Phase 3**
- **Branch:** `feature/phase-4-claims-workflow`
- [ ] 10-state lifecycle state machine implementation (`docs/state-machine.md`).
- [ ] Strict Separation of Duties (SoD) enforcement: `actor_user_id != claimant_id`.
- [ ] Finance Head override engine (approve full, clamp to policy cap, or reject).
- [ ] Idempotent fund dispatching with `Idempotency-Key` header handling.
- [ ] In-app transactional notification dispatcher & push token triggers.

---

### Phase 5a: Mobile Capture, Review & Employee Experience
- **Lead:** System 2 (`Jai`) | **Status:** 🟡 **In Progress (Capture & Review UI Delivered)**
- **Branch:** `feature/phase-2-ocr-pipeline` / `feature/phase-5a-mobile-capture`
- [x] Camera (`launchCameraAsync`) and photo picker (`launchImageLibraryAsync`) in `mobile/src/app/(tabs)/snap.tsx`.
- [x] Image normalization via `normalizeReceiptImage` (JPEG, max dimension $\le 2048\text{px}$).
- [x] Confidence-highlighted review screen with visual warning pills for low-confidence fields ($< 0.8$).
- [x] Editable line-item, vendor, date, category, and total paise inputs before submission.
- [x] Real-time blacklist deduction preview and non-INR currency alerts.
- [ ] Employee Claim History screen with 10-state status badges and IST monthly quota progress bar.

---

### Phase 5b: Approver, Finance & Admin Dashboards
- **Lead:** System 2 (`Jai`) | **Status:** ⏸️ **Pending Phase 5a**
- **Branch:** `feature/phase-5b-role-dashboards`
- [ ] Department Head approval, return for correction, and rejection interface.
- [ ] Finance Manager Dynamic Category & Spend Tier Limit management screen.
- [ ] Finance Manager fund verification & idempotent payout dispatch screen.
- [ ] Finance Head Overseer dashboard (over-cap escalation resolution + spend analytics).
- [ ] Notification Drawer with deep linking (`expenseit://claims/{id}`).

---

### Phase 6: Cloud Postgres Staging & E2E Hardening
- **Lead:** Joint (`@Tharnikaa` & `Jai`) | **Status:** ⏸️ **Pending Phases 1–5**
- **Target:** Milestone 3
- [ ] Cloud PostgreSQL (Neon / Supabase) row-locking concurrency verification.
- [ ] Full end-to-end user journeys across all 7 seeded personas.
- [ ] Edge-case validation (foreign currency, blurry receipts, concurrent duplicate claims).
- [ ] Production readiness review and release tag `v1.0.0`.

---

## 4. Active Feature Branches & PR Registry

| Branch Name | Owner | Target Branch | Status | Notes / Associated Issues |
|---|---|---|---|---|
| `main` | Joint | — | 🟢 Up-to-date | Protected milestone branch |
| `develop` | Joint | `main` | 🟢 Up-to-date | Active integration branch (`f891a50`) |
| `feature/phase-2-ocr-pipeline` | System 2 (`Jai`) | `develop` | 🟡 Ready to cut | Next task for Jai |
| `feature/phase-5a-mobile-capture` | System 2 (`Jai`) | `develop` | ⚪ Queued | Mobile capture & review screen |
| `feature/phase-1-policy-db` | System 1 (`@Tharnikaa`) | `develop` | ⚪ Queued | DB models & Alembic migration |

---

## 5. Contract & Schema Version Log

| File | Current Version | Last Modified By | Description |
|---|---|---|---|
| `contracts/openapi.yaml` | `1.0.0` | System 1 | Complete OpenAPI 3.1 specification (34 endpoints) |
| `contracts/schemas/receipt_extracted.schema.json` | `1.0.0` | System 1 | Minor paise units, confidence scores, factual item tags |
| `contracts/schemas/expense_claim.schema.json` | `1.0.0` | System 1 | 10-state claim schema with SoD and quota snapshots |
| `contracts/schemas/notification.schema.json` | `1.0.0` | System 1 | 8 transactional notification event types |
| `contracts/schemas/seed_policies.schema.json` | `1.0.0` | System 1 | Policy cap matrix validation schema |
| `contracts/seed_personas.json` | `1.0.0` | System 1 | 7 deterministic persona UUIDs |
| `contracts/seed_policies.json` | `1.0.0` | System 1 | Default INR category and monthly paise caps |

---

## 6. Collaboration Log & Milestone Handoffs

* **2026-11-04 (Phase 0 Landed & Phase 2 Delivered):**
  * System 1 (`@Tharnikaa`) completed and committed Phase 0 (`f891a50`).
  * System 2 (`Jai`) implemented Phase 2 Multi-Model Vision AI Engine (`backend/app/ocr/**`) supporting Gemini, OpenAI, Claude, and Ollama with perceptual hashing.
  * System 2 implemented Phase 5a Mobile-First Capture (`snap.tsx`) with Camera + Gallery picker, confidence-highlighted review, inline edits, and real-time blacklist deduction previews.
  * 18/18 pytest tests pass, mobile TypeScript checks pass with zero errors.
