# CastTrace AI — Product Quality Inspection & Defect Tracking System

**Buildathon 2.0 | Problem Statement 1**  
CastTrace AI is a quality assurance and defect tracking system for manufactured cast pump impellers. It connects staging inspections, PyTorch-based ML binary defect prediction, human verification, corrective action tracking (CAPA), follow-up reinspection, authorized batch release/containment, operational quality dashboards (including the **Recurrence Radar**), and evidence-grounded GenAI intelligence.

---

## Technical Stack

- **Backend:** FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, SQLite (development) / PostgreSQL (production compatible).
- **Frontend:** React, TypeScript, Vite, Tailwind CSS, TanStack Query.
- **Machine Learning:** PyTorch transfer learning binary classifier (evaluated in Phase 3).
- **Security & Integrity:** BCrypt password hashing, RBAC (Inspector, Supervisor, Quality Manager), Idempotency Keys, append-only Audit Logging.

---

## Repository Structure

```
├── .env.example            # Environment configuration template
├── .gitignore               # Ignores venv, node_modules, sqlite, uploads, weights
├── alembic.ini              # Alembic migration configuration
├── pytest.ini               # Pytest configuration with pythonpath
├── docs/                    # Approved Phase 1A architecture and technical contracts
│   ├── erd.md
│   ├── state-machines.md
│   ├── permissions.md
│   ├── metrics.md
│   ├── api-contract.md
│   ├── traceability.md
│   └── demo-script.md
├── backend/
│   ├── alembic/             # Database migration versions
│   ├── app/
│   │   ├── api/v1/          # REST API endpoints (health, etc.)
│   │   ├── models/          # 16 SQLAlchemy 2 models from docs/erd.md
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   ├── config.py        # Settings via pydantic-settings
│   │   ├── database.py      # Engine and SessionLocal
│   │   └── main.py          # FastAPI application entrypoint
│   ├── scripts/
│   │   └── seed.py          # Idempotent demo role seed script
│   ├── tests/               # Backend pytest test suite
│   └── requirements.txt     # Python backend dependencies
└── frontend/
    ├── src/                 # React TypeScript source code
    ├── tailwind.config.js   # Tailwind CSS configuration
    ├── postcss.config.js    # PostCSS configuration
    ├── vite.config.ts       # Vite configuration with backend proxy
    └── package.json         # Node frontend dependencies
```

---

## Local Setup Instructions (Windows PowerShell)

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.14)
- Node.js 18+ & npm 9+
- Git

### 2. Environment Configuration
Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```

### 3. Backend Setup
Create and activate the virtual environment, then install dependencies:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

### 4. Database Migration
Apply initial Alembic migrations to create all 16 tables:
```powershell
.\.venv\Scripts\alembic upgrade head
```

### 5. Seed Demo Roles
Populate the initial demo accounts (`inspector_chen`, `supervisor_torres`, `qm_reynolds`):
```powershell
.\.venv\Scripts\python backend\scripts\seed.py
```
*Note: The seed script is completely idempotent and safe to run multiple times without creating duplicates.*

### 6. Frontend Setup
Install npm packages in the `frontend` directory:
```powershell
cd frontend
npm install
cd ..
```

---

## Running the Application

### Start the FastAPI Backend
```powershell
.\.venv\Scripts\uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
- API Base: `http://127.0.0.1:8000`
- Interactive Swagger Docs: `http://127.0.0.1:8000/docs`
- Health Endpoint: `http://127.0.0.1:8000/health`

### Start the React Frontend
In a separate PowerShell terminal:
```powershell
cd frontend
npm run dev
```
- Frontend Dashboard: `http://127.0.0.1:5173`
- The Vite dev server proxies `/health` and `/api` requests directly to FastAPI on port 8000.

---

## Running Automated Tests

Run backend tests using pytest:
```powershell
.\.venv\Scripts\pytest -v backend\tests
```

Test frontend build:
```powershell
cd frontend
npm run build
cd ..
```

---

## Seed Accounts Reference

| Role | Username | Password | Purpose |
| :--- | :--- | :--- | :--- |
| **Inspector** | `inspector_chen` | `Password123!` | Imaging, visual reviews, defect logging |
| **Supervisor** | `supervisor_torres` | `Password123!` | Production batch staging, CAPA remediation |
| **Quality Manager** | `qm_reynolds` | `Password123!` | Final quality decisions, release/containment, dispute resolution |
