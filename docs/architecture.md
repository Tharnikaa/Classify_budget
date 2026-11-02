# ExpenseIt — System Architecture (`docs/architecture.md`)

## 1. System Context & Component Boundaries

```mermaid
flowchart TB
    subgraph Mobile["React Native / Expo Client (mobile/)"]
        Cam["Camera & Image Normalizer (HEIC->JPEG <=2048px)"]
        Tabs["Expo Router 4-Tab Shell + Role Dashboards"]
        TokenStore["Secure JWT Store (expo-secure-store)"]
        ApiClient["Typed API Client (openapi-typescript)"]
    end

    subgraph Backend["FastAPI Backend (backend/)"]
        Auth["JWT Auth + RBAC + SoD Guards (app/core)"]
        OCR["OCR Adapter behind OCRServiceProtocol (app/ocr)"]
        Policy["Policy, Blacklist & IST Quota Engine (app/services)"]
        Workflow["10-State Approval & Idempotent Dispatch"]
        Storage["Authenticated Receipt StorageService"]
        Notif["Transactional NotificationService"]
    end

    subgraph External["Data & External Services"]
        DB["SQLite WAL (Local) / Cloud PostgreSQL (Staging)"]
        Gemini["Google Gemini Flash Multimodal API"]
    end

    Cam --> ApiClient
    Tabs --> ApiClient
    TokenStore --> ApiClient
    ApiClient -->|"HTTPS / LAN Bearer JWT + Idempotency-Key"| Auth
    Auth --> OCR
    Auth --> Policy
    Auth --> Workflow
    OCR -->|"Structured Output Schema + Active Categories"| Gemini
    OCR --> Storage
    Policy --> DB
    Workflow --> DB
    Workflow --> Notif
```

---

## 2. Anti-Tampering Receipt Scan & Claim Submission Flow

```mermaid
sequenceDiagram
    participant Emp as Employee (Expo App)
    participant API as FastAPI Backend
    participant OCR as OCRServiceProtocol
    participant DB as Database + Storage

    Emp->>API: POST /api/v1/ocr/scan (normalized JPEG)
    API->>DB: Save authenticated image + SHA-256 / pHash
    API->>DB: Load active dynamic categories
    API->>OCR: extract_receipt(image_bytes, mime_type, active_categories)
    OCR-->>API: ExtractedReceipt (paise, item_tags, field_confidence)
    API->>DB: Persist immutable receipt_scans row (receipt_id)
    API-->>Emp: Return receipt_id + OCR payload

    Emp->>API: POST /api/v1/claims/precheck (user-reviewed fields)
    API-->>Emp: Return eligible_amount_paise, blacklist deductions & cap warnings

    Emp->>API: POST /api/v1/claims (receipt_id + Idempotency-Key + submitted fields)
    API->>DB: Compute ocr_diff (raw OCR vs submitted) + save policy_snapshot
    API->>DB: Atomic soft-hold reserved_paise on (user_id, invoice_YYYY_MM)
    API-->>Emp: 201 Created (PENDING_APPROVAL)
```

---

## 3. Database Portability: SQLite WAL (Local) vs. Cloud PostgreSQL (Staging)

1. **Zero-Install Local Development (`sqlite:///./expenseit_dev.db`)**:
   - SQLAlchemy connection hook automatically executes:
     - `PRAGMA journal_mode=WAL;`
     - `PRAGMA busy_timeout=5000;`
     - `PRAGMA foreign_keys=ON;`
   - Quota reservation wraps checks and updates inside `BEGIN IMMEDIATE` transactions to serialize concurrent local writes.
2. **Cloud PostgreSQL Staging (`postgresql+psycopg://...`)**:
   - Uses `SELECT ... FOR UPDATE` (`query.with_for_update()`) on the `(user_id, year_month)` quota ledger row to prevent Time-of-Check-to-Time-of-Use (TOCTOU) cap races across concurrent API workers.
   - All money columns use `BIGINT` (`*_paise`), avoiding dialect float precision differences.

