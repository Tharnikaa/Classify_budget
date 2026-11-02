# ExpenseIt — Collaboration & Workflow Guide (`COLLABORATION.md`)

## 1. Branching Strategy & Pull Request Flow

- **`main`**: Protected milestone and production branch. Updated only via PR from `develop` at verified milestones (`M0`, `M1`, `M2`, `M3`).
- **`develop`**: Protected central integration branch. Cut all feature branches from `develop` and open PRs back into `develop`.
- **Feature Branches**:
  - **System 1 (`@Tharnikaa`)**:
    - `feature/phase-1-policy-db`
    - `feature/phase-3-verification-engine`
    - `feature/phase-4-claims-workflow`
  - **System 2 (Collaborator)**:
    - `feature/phase-2-ocr-pipeline`
    - `feature/phase-5a-mobile-capture`
    - `feature/phase-5b-role-dashboards`

### Merge Rules
1. Pull latest `origin/develop` before starting a branch:
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/phase-2-ocr-pipeline
   ```
2. Ensure GitHub Actions CI (`ci.yml`) is green before merging.
3. Any PR touching `contracts/**` **must** be reviewed and approved by **both** collaborators and include updated `mobile/src/api/generated.ts` types.

---

## 2. Running FastAPI + Expo Together on Local Wi-Fi (Physical Phone Testing)

Because React Native / Expo Go runs on a physical Android or iOS phone, `localhost:8000` on the phone refers to the phone itself, **not** your laptop.

1. **Start Backend Bound to All Interfaces (`0.0.0.0:8000`)**:
   - **Windows PowerShell**:
     ```powershell
     cd backend
     .\scripts\dev.ps1
     ```
   - **macOS / Linux**:
     ```bash
     cd backend
     ./scripts/dev.sh
     ```
   The startup script prints your laptop's LAN IPv4 address (e.g., `http://192.168.1.42:8000/api/v1`).

2. **Point Expo Mobile App to Your Laptop's LAN IP**:
   Copy `mobile/.env.example` to `mobile/.env` and set:
   ```ini
   EXPO_PUBLIC_API_URL=http://<YOUR_LAPTOP_LAN_IP>:8000/api/v1
   EXPO_PUBLIC_ENABLE_ROLE_SWITCHER=true
   ```
   *(If running in an Android Emulator on the same laptop, use `http://10.0.2.2:8000/api/v1`; for iOS Simulator or Expo Web on the same laptop, `http://localhost:8000/api/v1` works directly.)*

3. **Start Expo**:
   ```bash
   cd mobile
   npm install
   npx expo start
   ```

---

## 3. Contract Change Protocol (`/contracts`)

1. Edit `contracts/openapi.yaml` and/or `contracts/schemas/*.schema.json` in a dedicated branch `chore/contract-<topic>`, bumping `schema_version` if breaking.
2. Regenerate mobile TypeScript definitions:
   ```bash
   cd mobile
   npm run codegen
   ```
3. Run backend contract conformance tests:
   ```bash
   cd backend
   pytest tests/test_contracts.py
   ```
4. Open a PR for dual sign-off before merging to `develop`.

---

## 4. Database Migration Protocol

- **System 1** is the sole owner of `backend/migrations/**` to prevent Alembic multi-head conflicts.
- If **System 2** needs an additional column or table for Phase 2 OCR, open a GitHub Issue listing the field name, type, and nullability so System 1 includes it in the next migration on `develop`.

---

## 5. Integration Milestones

| Milestone | Scope | Exit Check |
|---|---|---|
| **M0 (Phase 0)** | Contracts v1.0.0, Stateful FastAPI Stubs, Seeded Personas, Expo Router Shell, CI | All `pytest` + `tsc` checks green on `main` and `develop` |
| **M1 (OCR + Capture)** | Phase 1 DB + Phase 2 Gemini OCR + Phase 5a Camera & Review UI | Real receipt photo -> Gemini extraction -> confidence-highlighted mobile review |
| **M2 (Policy + Workflow)** | Phase 3 Quota/Blacklist Engine + Phase 4 Approval/Dispatch + Phase 5b Role Screens | Full Employee -> DH -> FM / FH Override -> Dispatch lifecycle working end-to-end |
| **M3 (Staging & Demo)** | Cloud PostgreSQL (`DATABASE_URL`), concurrency tests, production Role Switcher lock | 5-persona live mobile walkthrough against shared cloud staging DB |

