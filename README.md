# CastTrace AI — Product Quality Inspection & Defect Tracking System

**Buildathon 2.0 | Problem Statement 1**

CastTrace AI is an enterprise-grade AI-assisted product quality inspection, defect tracking, and release governance platform tailored for manufactured cast pump impellers (CF8M Stainless Steel).

The platform links physical shop-floor inspection with deep learning defect inference, human-in-the-loop review, defect recurrence lineage (**Recurrence Radar**), Corrective and Preventive Actions (CAPA) with strict Four-Eyes verification, independent reinspection, authorized batch release gates with immutable decision snapshots, and comprehensive audit logging.

> **Governance Principle:** AI predictions assist human inspectors and triage evidence, but **never** independently release, hold, or scrap a production batch. Official batch release and containment decisions require explicit, authorized human Quality Manager action.

---

## 1. Primary Application Workflows

CastTrace AI governs the end-to-end quality lifecycle through six tightly coordinated workflows:

```
[Shop Floor Inspection]
       │  (Inspector creates draft, registers physical items, uploads photos)
       ▼
[Photographic Evidence & SHA-256 Hashing]
       │  (Magic bytes, size check, hash calculated, path confinement enforced)
       ▼
[Detached ML Inference Worker]
       │  (ResNet-18 pipeline, quality gate, unfamiliar-input guard, 3-tier routing)
       ▼
[Human Review & Disagreement Tracking]
       │  (Inspector reviews item; AI prediction snapshot frozen; defects logged)
       ▼
[CAPA & Four-Eyes Reinspection]
       │  (Remediation assigned; implementer ≠ verifier; reinspection resolves defect)
       ▼
[Batch Release Gates & Immutable Decision Snapshot]
       │  (Quality Manager evaluates 8 automated gates; signs release with snapshot)
       ▼
[Operational Dashboards & Audit Trail]
```

* **Workflow A — Authentication & Role-Based Access Control (RBAC):** Three operational personas (`INSPECTOR`, `SUPERVISOR`, `QUALITY_MANAGER`) enforced through server-side JWT authentication with least-privilege scoping.
* **Workflow B — Batch & Product Management:** Traceability from SKU/alloy specification to batch serialization, declared quantities, and operational containment holds (`ON_HOLD`).
* **Workflow C — Inspection & Multi-Photo Evidence:** Sampling-plan-driven inspections (`AQL_LEVEL_II`), physical item registration, and multi-photo uploads without item-count inflation. Every image is cryptographically anchored via SHA-256 hashing.
* **Workflow D — Detached ResNet-18 Defect Inference:** Background worker claims queued jobs with atomic leases, applies image quality checks, detects out-of-distribution/unfamiliar castings, and applies calibrated routing (`LIKELY_OK`, `NEEDS_REVIEW`, `LIKELY_DEFECTIVE`).
* **Workflow E — Controlled Defects, CAPA & Four-Eyes Reinspection:** Categorized defect logging, root-cause remediation tracking, strict separation of duties (implementer cannot approve own verification), and mandatory reinspection.
* **Workflow F — Release Governance & Immutable Snapshots:** 8-rule automated release gate engine preventing release of uninspected, unreviewed, or defect-tainted batches. Release creates an immutable audit snapshot.

---

## 2. Technical Architecture & Process Separation

CastTrace AI strictly decouples the web API layer from the machine learning inference workload:

* **API Backend (FastAPI):** Light-weight, async HTTP service on port `8001`. Serves REST endpoints, validates schemas via Pydantic v2, enforces RBAC, writes audit trails, and enqueues inference jobs in SQLite. **The API process never loads PyTorch weights into memory.**
* **Inference Worker (`worker.py`):** Detached background daemon. Polls SQLite for queued jobs, acquires 45-second atomic leases, verifies file hash integrity, executes ResNet-18 forward pass on GPU/CPU, and commits results.
* **Frontend SPA (React + Vite + Tailwind CSS):** Modern single-page application on port `5173`. Proxies API traffic via Vite development server, maintains JWT authentication state, and provides real-time quality triage views.
* **Database (SQLite with WAL mode):** Zero-configuration local relational database. Configured with Write-Ahead Logging (`PRAGMA journal_mode=WAL`) and `busy_timeout=5000` for concurrent read/write transactions. Fully compatible with PostgreSQL.

For architectural specifications, see:
* [Entity Relationship Diagram](docs/erd.md)
* [Lifecycle State Machines](docs/state-machines.md)
* [Permissions & RBAC Matrix](docs/permissions.md)
* [API Contract & Schema](docs/api-contract.md)
* [Quality Metrics & Gates](docs/metrics.md)
* [Traceability & Lineage](docs/traceability.md)
* [ML Evaluation & Thresholds](docs/ml-evaluation.md)

---

## 3. Software Prerequisites

Ensure the following tools are installed on your host machine:

| Component | Minimum Version | Development Baseline | Check Command |
| :--- | :--- | :--- | :--- |
| **Operating System** | Windows 10/11, macOS, Linux | Windows 11 (x64) | `cmd /c ver` |
| **Python** | 3.10+ | Python 3.14.6 | `python --version` |
| **Node.js** | 18.0.0+ | Node.js 20.x | `node --version` |
| **npm** | 9.0.0+ | npm 10.x | `npm --version` |
| **Git** | 2.30+ | Git 2.45+ | `git --version` |

---

## 4. Local Environment Configuration

Copy the tracked configuration template to create your local `.env` file:

```powershell
Copy-Item .env.example .env
```

### Key Configuration Variables

| Variable | Default Value | Purpose |
| :--- | :--- | :--- |
| `APP_ENV` | `development` | Environment mode (`development`, `staging`, `production`). In `production`, strict security checks fail-safe on weak secrets. |
| `APP_DEBUG` | `true` | Detailed debug error reporting. Replaced with sanitized errors in production. |
| `HOST` | `127.0.0.1` | Local network binding interface. |
| `PORT` | `8001` | Backend HTTP API port. |
| `SECRET_KEY` | *(dev placeholder)* | HMAC-SHA256 signing secret for JWTs. Must be ≥32 characters and cryptographically random in production. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `480` | Session lifetime (480 min = 8 hours shift). |
| `DATABASE_URL` | `sqlite:///./casttrace.db` | Local SQLite database file location. |
| `STORAGE_DIR` | `./storage/evidence` | Dedicated evidence repository for uploaded inspection photos. |
| `MAX_UPLOAD_SIZE_BYTES` | `10485760` | 10 MB maximum upload limit per image file. |
| `ML_ARTIFACTS_DIR` | `ml/artifacts` | Directory containing trained weights and guard vectors. |
| `WORKER_POLL_INTERVAL` | `1.0` | Background worker queue polling interval (seconds). |
| `BACKEND_CORS_ORIGINS` | `["http://localhost:5173", ...]` | Explicit CORS allowed origins. Wildcards (`*`) are rejected. |

> **Security Rule:** Never commit `.env` to Git. The `.gitignore` file strictly excludes `.env`, `*.db`, `storage/`, and `backups/`.

---

## 5. Step-by-Step Setup Sequence

Follow this sequence to set up a clean clone of CastTrace AI on a new computer.

### Step 5.1: Create Python Virtual Environment & Install Dependencies

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
pip install -e .\ml
```

*Note: The `-e .\ml` command installs the local `casttrace_ml` package in editable mode.*

### Step 5.2: Apply SQLite Database Migrations

Apply the complete Alembic migration sequence (head revision `6eae03ca7c6e`):

```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

This constructs all 18 relational tables including indexes, unique constraints, foreign keys, and the `audit_log` ledger.

### Step 5.3: Seed Demo Operational Accounts

Run the idempotent seed script to populate test accounts:

```powershell
.\.venv\Scripts\python.exe backend\scripts\seed.py
```

#### Demo Credentials Reference

| Username | Role | Default Password | Description |
| :--- | :--- | :--- | :--- |
| `inspector_chen` | `INSPECTOR` | `Password123!` | Shop-floor inspection, photo evidence upload, initial review |
| `supervisor_torres`| `SUPERVISOR`| `Password123!` | Batch creation, containment holds, CAPA assignment |
| `qm_reynolds` | `QUALITY_MANAGER`| `Password123!` | Gate evaluation, official release, Four-Eyes CAPA verification |

*(Note: Change all credentials before deploying outside local development).*

### Step 5.4: Install Frontend Dependencies

```powershell
Push-Location frontend
npm install
Pop-Location
```

---

## 6. Running the Application

CastTrace AI consists of three concurrent processes during local development. You can launch them in separate terminals or use the unified PowerShell CLI.

### Option A: Using the `scripts/dev.ps1` Helper CLI

We provide a convenient PowerShell developer script that handles environment activation and commands:

```powershell
# Open 3 terminals:
# Terminal 1:
.\scripts\dev.ps1 backend

# Terminal 2:
.\scripts\dev.ps1 worker

# Terminal 3:
.\scripts\dev.ps1 frontend

# In a 4th terminal, check service status:
.\scripts\dev.ps1 status
```

### Option B: Manual Process Startup

#### Terminal 1 — FastAPI Backend (Port 8001)
```powershell
.\.venv\Scripts\uvicorn.exe backend.app.main:app --host 127.0.0.1 --port 8001 --reload
```

#### Terminal 2 — Detached ML Inference Worker
```powershell
.\.venv\Scripts\python.exe backend\app\worker.py --poll-interval 1.0
```

#### Terminal 3 — Vite Frontend Dev Server (Port 5173)
```powershell
cd frontend
npm run dev
```

### Active Local Endpoints

* **Frontend SPA:** [http://localhost:5173](http://localhost:5173)
* **Backend API Base:** [http://127.0.0.1:8001](http://127.0.0.1:8001)
* **Interactive OpenAPI Docs (Swagger):** [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs)
* **System Health Probe:** [http://127.0.0.1:8001/health](http://127.0.0.1:8001/health)
* **Worker Operational Status:** [http://127.0.0.1:8001/api/v1/workers/status](http://127.0.0.1:8001/api/v1/workers/status) *(QM / Supervisor)*

---

## 7. Machine Learning Artifact Prerequisites & Reproducibility

The application integrates a ResNet-18 deep learning model trained on industrial cast impeller imagery. In compliance with security best practices and dataset licensing (CC BY-NC-ND 4.0), **large binary weights are excluded from Git**.

### Required ML Artifacts

The inference worker requires the following local files under `ml/artifacts/`:

| Artifact Path | Purpose | Mandatory? | Integrity Check |
| :--- | :--- | :--- | :--- |
| `ml/artifacts/model_metadata.json` | Architecture metadata, frozen thresholds, expected SHA-256 hashes | **Yes** (Tracked in Git) | JSON schema validation |
| `ml/artifacts/model_best.pt` | PyTorch ResNet-18 state dictionary weights | **Yes** for real inference | SHA-256 hash match against metadata |
| `ml/artifacts/unfamiliar_guard_reference.json` | Reference embedding centroid and distance threshold for OOD guard | **Yes** for real inference | SHA-256 hash match against metadata |

### Preflight Diagnostics & Safe Degraded Mode

The backend API and ML worker incorporate preflight artifact validation:

1. **API Server Independence:** The FastAPI server boots normally even if ML weights are absent. Non-ML features (inspections, batches, CAPAs, manual reviews, release gates) remain 100% operational.
2. **Worker Safe Failure:** If `model_best.pt` is missing when an image is processed, the worker logs an actionable error and records the run as `FAILED` with code `MODEL_ARTIFACTS_UNAVAILABLE`. **It never fabricates mock predictions.**
3. **Health Diagnostics:** Calling `GET /health` reports full artifact readiness:
   ```json
   {
     "status": "healthy",
     "database": "connected",
     "details": {
       "ml_artifacts": {
         "metadata_present": true,
         "weights_present": true,
         "weights_sha256_match": true,
         "guard_present": true,
         "guard_sha256_match": true,
         "is_inference_ready": true
       }
     }
   }
   ```

### Obtaining or Training Model Weights

To train or reproduce the weights locally from the raw impeller dataset:
```powershell
.\.venv\Scripts\python.exe ml/train.py --epochs 15 --batch-size 32
.\.venv\Scripts\python.exe scripts/register_model_version.py
```

---

## 8. Automated Testing & Verification Suite

CastTrace AI includes automated unit tests, security tests, and live end-to-end integration verification.

### 8.1 Backend Test Suite (Pytest)

Run all 82 automated backend tests across models, services, RBAC, release gates, and security hardening:

```powershell
.\.venv\Scripts\pytest.exe backend/tests -v
```

*(All tests execute against an isolated temporary database `casttrace_test.db` and clean up automatically).*

### 8.2 Clean-Clone Reproducibility Verification

To verify that the application configuration, Alembic migrations, database seeding, artifact diagnostics, and API connectivity can run completely from scratch:

```powershell
.\.venv\Scripts\python.exe scripts/verify_clean_setup.py
```

*This script spins up an isolated temporary SQLite database, runs all migrations, seeds test users, checks ML integrity, and performs live API probes (14/14 checks).*

### 8.3 Live Application Integration Verification (Phase 5D)

With backend, worker, and frontend running, execute the 32-step live integration verification suite:

```powershell
.\.venv\Scripts\python.exe scripts/verify_phase5d_live.py
```

### 8.4 Frontend Build and Linting

```powershell
cd frontend
npm run build   # Validates TypeScript compilation and bundles static assets
npm run lint    # Runs Oxlint across all TypeScript and React components
cd ..
```

---

## 9. SQLite Backup, Restoration & Migration Safety

CastTrace AI includes robust, non-destructive database backup and recovery utilities utilizing the official SQLite Online Backup API.

### 9.1 Creating a Database Backup

Run the backup utility to create a timestamped, WAL-consistent backup file:

```powershell
.\.venv\Scripts\python.exe scripts/backup_database.py
```

* Output location: `backups/casttrace_backup_YYYYMMDD_HHMMSS.db`
* Safety: Uses `source_conn.backup(dest_conn)` which safely locks pages without interrupting live readers.
* Verification: Automatically runs `PRAGMA integrity_check` and confirms all 15 core tables exist before reporting success.

### 9.2 Verifying a Backup File (Non-Destructive)

Check whether a backup file is structurally valid without modifying the active database:

```powershell
.\.venv\Scripts\python.exe scripts/restore_database.py --backup backups/<backup_file>.db --check-only
```

### 9.3 Restoring from a Backup

To restore a verified backup:

```powershell
# 1. Gracefully stop backend and worker processes (Ctrl+C in their terminals)
# 2. Execute restoration:
.\.venv\Scripts\python.exe scripts/restore_database.py --backup backups/<backup_file>.db
```

**Restoration Safeguards:**
1. Pre-flight verification of backup file integrity.
2. Creates an automatic pre-restore safety copy (`casttrace.db.pre_restore_YYYYMMDD_HHMMSS.bak`).
3. Performs atomic restoration using SQLite backup API.
4. Verifies restored database integrity and Alembic migration version (`6eae03ca7c6e`).

---

## 10. Development vs. Production Configuration

| Parameter | Development Mode (`APP_ENV=development`) | Production Mode (`APP_ENV=production`) |
| :--- | :--- | :--- |
| **`APP_DEBUG`** | `true` (Full exception stack traces in logs) | **`false`** (Sanitized error responses, no traceback leaks) |
| **`SECRET_KEY`** | Default dev key permitted with startup warning | **Enforced:** Must be random, ≥32 chars, cannot contain "dev" or "insecure" |
| **CORS Origins** | `localhost:5173`, `localhost:3000` | Explicit production FQDN (e.g. `https://quality.company.com`). Wildcards rejected. |
| **Static Serving** | Vite dev proxy with HMR | Static bundle built via `npm run build`, served by Nginx / Caddy |
| **Database Engine** | SQLite WAL mode (`casttrace.db`) | SQLite on persistent volume (or managed PostgreSQL) |
| **Worker Execution**| Terminal script | Systemd service or supervised container daemon |

### Generating a Production Secret Key

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## 11. Production Deployment Guidelines

When deploying CastTrace AI outside local development:

1. **Reverse Proxy (Nginx / Caddy / Cloudflare):**
   * Terminate TLS (HTTPS) externally.
   * Route `/api/` and `/health` to FastAPI on port `8001`.
   * Route `/` to static frontend files built via `npm run build` (`frontend/dist`).
   * Never expose the backend port `8001` or worker directly to the public Internet.
2. **Persistent Storage:**
   * Ensure `casttrace.db` and `storage/evidence/` reside on persistent, backed-up block storage volumes.
   * Restrict OS permissions on `storage/evidence/` to the application runtime user.
3. **Worker Supervision:**
   * Supervise `worker.py` using `systemd`, `supervisor`, or a container orchestrator with automatic restart policies.
   * Ensure only one active worker instance runs per SQLite database to prevent lock contention.

---

## 12. Known Setup Limitations

* **SQLite Concurrency:** SQLite WAL mode allows multiple concurrent readers and one writer. For high-throughput factory lines with >50 concurrent inspectors, migration to PostgreSQL is recommended.
* **Worker Process:** The inference worker must run continuously in the background for automated AI triage. If the worker is offline, inspections remain in `QUEUED` state until the worker is restarted.
* **Model Artifacts:** Real defect inference requires local provisioning of `ml/artifacts/model_best.pt` due to licensing boundaries.

---

## 13. License & Attribution

* CastTrace AI Core Platform: MIT License
* Impeller Casting Dataset: Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International (CC BY-NC-ND 4.0)
