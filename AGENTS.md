# ExpenseIt — Shared Antigravity Agent Governance (`AGENTS.md`)

> **CRITICAL:** This repository is developed in parallel by **two developers running independent Antigravity instances**:
> - **System 1 (`@Tharnikaa`)**: Owns backend core, DB models, Alembic migrations, policy engine, and approval/dispatch workflows.
> - **System 2 (Collaborator)**: Owns `backend/app/ocr/**` (Phase 2 Vision AI) and `mobile/**` (Phase 5 React Native / Expo client).
>
> Both agents MUST follow every rule in this file without exception.

---

## 1. Locked Technology Stack

- **Backend (`backend/`)**: Python `3.12`, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, `PyJWT`, `pwdlib`
- **Database**:
  - Local dev: Zero-install **SQLite (`WAL` mode + `BEGIN IMMEDIATE` transaction lock)** (`sqlite:///./expenseit_dev.db`)
  - Shared staging / concurrency tests: **Cloud PostgreSQL** (Neon / Supabase) via `DATABASE_URL` with `SELECT ... FOR UPDATE`
- **Mobile Client (`mobile/`)**: **React Native + Expo** (`TypeScript`, `Expo Router`, typed WCAG 2.1 AA Teal tokens in `mobile/src/theme/tokens.ts`, `@tanstack/react-query`, `expo-image-picker`, `expo-image-manipulator`, `expo-secure-store`)
- **API & Domain Contracts (`contracts/`)**: OpenAPI 3.1 (`contracts/openapi.yaml`) + JSON Schemas (`contracts/schemas/*.schema.json`)

---

## 2. Strict File & Directory Ownership Rules

Never modify files outside your user's owned directories unless the user explicitly approves a cross-boundary change for a dedicated PR:

| Path | Owner | Agent Rule |
|---|---|---|
| `contracts/**` | **Dual Ownership** | **Single Source of Truth.** Never silently drift backend Pydantic schemas or mobile TypeScript interfaces away from `contracts/openapi.yaml`. Contract changes require a dedicated PR and re-running `npx openapi-typescript ../contracts/openapi.yaml -o src/api/generated.ts` inside `mobile/`. |
| `backend/migrations/**`, `backend/alembic.ini` | **System 1 ONLY** | **Never generate Alembic migrations on System 2** (prevents multi-head migration collisions). If Phase 2 OCR needs a new column, open an issue/request for System 1. |
| `backend/app/ocr/**` | **System 2** | Implement Gemini Vision extraction strictly behind `OCRServiceProtocol` in `backend/app/ocr/protocol.py`. Do not modify `backend/app/main.py` or policy/workflow routers. |
| `backend/app/{core,models,schemas,services,api}/**` | **System 1** | Owned by System 1 after Phase 0. |
| `mobile/**` | **System 2** | Owned by System 2 after the Phase 0 shell lands (includes Employee, Dept Head, Finance Manager limit-config & dispatch, and Finance Head screens). |

---

## 3. Non-Negotiable Domain & Financial Invariants

1. **Integer Paise Only (`INR`)**:
   - Base currency is `INR` (`₹`).
   - **Never** use floating-point numbers (`float` / JS fractional math) for monetary storage or comparisons. Every monetary value in DB columns, API payloads, and contracts MUST be an integer in minor units (`*_paise: int`, e.g., `₹500.00 == 50000`).
2. **Roles vs. Spend Tiers**:
   - RBAC `role` (`EMPLOYEE`, `DEPT_HEAD`, `FINANCE_MANAGER`, `FINANCE_HEAD`) controls permissions.
   - `spend_tier` (`JUNIOR`, `SENIOR`, `MANAGER`, `NONE`) controls per-category and monthly INR caps. Never hardcode `EMPLOYEE_JUNIOR` or `EMPLOYEE_SENIOR` as RBAC roles.
3. **Dynamic Categories & Factual OCR**:
   - Categories are dynamic DB/seed records (`GET /api/v1/categories`), passed into the OCR prompt at runtime.
   - Phase 2 OCR outputs **facts only** (`item_tag`: `meal`, `alcohol`, `tobacco`, `gift_card`, `personal`, etc., plus per-field `field_confidence` and nullable `vendor_name`/`invoice_date`). Never make policy decisions (`is_flagged_blacklisted`) inside the OCR module.
4. **Separation of Duties (SoD)**:
   - Enforce `actor_user_id != claim.claimant_id` on every approve, return, reject, verify, override, and dispatch transition.
   - `DEPT_HEAD` personal claims route to `FINANCE_HEAD -> FINANCE_MANAGER`.
   - `FINANCE_MANAGER` personal claims route to `FINANCE_HEAD -> peer FINANCE_MANAGER` (`actor != claimant`).
   - `FINANCE_HEAD` cannot raise personal claims (`403 Forbidden` in MVP).
5. **Immutable OCR Provenance & IST Quota Holds**:
   - Persist raw OCR scans (`receipt_id`) immutably; compute `ocr_diff` whenever user-submitted claim fields differ from raw OCR.
   - Monthly caps use calendar months (`YYYY-MM`) in **`Asia/Kolkata` (IST)** keyed on `invoice_date`, reserving `reserved_paise` on submission and releasing on rejection/withdrawal.
6. **Production Security Gating**:
   - `POST /api/v1/auth/dev-switch-role` MUST return `404` whenever `APP_ENV != "development"`.
   - `<DevRoleSwitcher />` in `mobile/` MUST only render when `__DEV__` is true.
   - Receipt images MUST be served only through authenticated endpoints (`/api/v1/receipts/{id}/image`), never public static folders.
   - Interactive UI elements MUST maintain WCAG 2.1 AA contrast (`#0F766E` + `#FFFFFF` in Light mode; `#14B8A6` + `#041E1D` in Dark mode) and `>= 48px` touch targets.

