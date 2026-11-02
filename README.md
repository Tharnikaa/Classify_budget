# ExpenseIt — Automated Corporate Expense Classification & Policy System

Mobile-first corporate expense management with **Gemini Vision OCR**, dynamic **INR (`₹`)** category and monthly spend policy enforcement, blacklist auto-deduction, and Separation-of-Duties (SoD) multi-tier reimbursements.

- **Master Plan:** [plan.md](./plan.md)
- **Phase 0 Synchronization Blueprint:** [PHASE_0_PLAN.md](./PHASE_0_PLAN.md)
- **Agent Rules:** [AGENTS.md](./AGENTS.md)
- **Collaboration & LAN Setup:** [COLLABORATION.md](./COLLABORATION.md)
- **Architecture & State Machine:** [docs/architecture.md](./docs/architecture.md) · [docs/state-machine.md](./docs/state-machine.md)

---

## Quickstart (Phase 0 Baseline)

### 1. Backend (`Python 3.12` + `FastAPI`)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
.\scripts\dev.ps1
```

* API Docs (Swagger UI): `http://localhost:8000/docs`
* OpenAPI JSON: `http://localhost:8000/openapi.json`

### 2. Mobile Client (`Node 24` + `React Native / Expo`)

```powershell
cd mobile
npm install
Copy-Item .env.example .env
# Edit mobile/.env with your laptop LAN IP when testing on a physical phone via Expo Go
npx expo start
```

---

## Seeded Development Personas (`contracts/seed_personas.json`)

All seeded accounts share the development password **`ExpenseIt@123`** (or switch instantaneously via the `__DEV__` Role Switcher bar when `APP_ENV=development`):

| Persona | Email | Role | Spend Tier | Dept |
|---|---|---|---|---|
| **Aarav Mehta** | `aarav.junior@expenseit.in` | `EMPLOYEE` | `JUNIOR` (`₹15,000`/mo) | Engineering |
| **Diya Nair** | `diya.senior@expenseit.in` | `EMPLOYEE` | `SENIOR` (`₹40,000`/mo) | Engineering |
| **Rohan Iyer** | `rohan.enghead@expenseit.in` | `DEPT_HEAD` | `MANAGER` (`₹85,000`/mo) | Engineering |
| **Meera Kapoor** | `meera.saleshead@expenseit.in` | `DEPT_HEAD` | `MANAGER` (`₹85,000`/mo) | Sales |
| **Karthik Rao** | `karthik.fm1@expenseit.in` | `FINANCE_MANAGER` | `MANAGER` (`₹85,000`/mo) | Finance |
| **Neha Verma** | `neha.fm2@expenseit.in` | `FINANCE_MANAGER` | `MANAGER` (`₹85,000`/mo) | Finance |
| **Vikram Sethi** | `vikram.fh@expenseit.in` | `FINANCE_HEAD` | `NONE` *(Overseer)* | Executive |

---

## Running Verification Suites

```powershell
# Backend contract, RBAC/SoD, and stub endpoint tests
cd backend
.\.venv\Scripts\pytest -v

# Mobile TypeScript & OpenAPI type generation check
cd ..\mobile
npm run typecheck
```

