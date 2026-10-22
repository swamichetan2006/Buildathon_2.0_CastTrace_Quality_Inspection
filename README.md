# CastTrace AI — Product Quality Inspection & Defect Tracking System

**Buildathon 2.0 | Problem Statement 1**

CastTrace AI is a quality assurance and defect tracking system for manufactured cast pump impellers. It connects inspection workflows, machine-learning-based defect prediction, human verification, corrective and preventive action (CAPA) tracking, follow-up reinspection, authorized batch release or containment, operational quality dashboards, and evidence-grounded Generative AI intelligence.

The system includes **Recurrence Radar**, an innovation designed to help identify recurring quality problems using historical defect and corrective-action information.

Machine predictions remain separate from human decisions. Official batch release and containment decisions require authorized human action.

---

## 1. Technical Stack

### Backend

* FastAPI
* Python
* Pydantic v2
* SQLAlchemy 2.0
* Alembic database migrations
* SQLite for local development
* PostgreSQL-compatible database architecture

### Frontend

* React
* TypeScript
* Vite
* Tailwind CSS
* TanStack Query

### Machine Learning

* PyTorch
* ResNet-18 transfer-learning classifier
* Binary classification: `GOOD` and `DEFECTIVE`
* Three-tier image routing: `LIKELY_OK`, `NEEDS_REVIEW`, and `LIKELY_DEFECTIVE`
* Image-quality validation and unfamiliar-input detection

### Security and Integrity

* Role-based access control (RBAC)
* Password hashing
* Idempotency protection
* Audit logging
* Immutable original image evidence
* SHA-256 evidence integrity verification
* Database-backed inference jobs
* Worker heartbeats, retry handling, and stale-lease recovery

### User Roles

* Inspector
* Supervisor
* Quality Manager

---

## 2. Repository Structure

```text
Buildathon_2.0/
├── .env.example
├── .gitignore
├── alembic.ini
├── pytest.ini
├── README.md
│
├── docs/
│   ├── erd.md
│   ├── state-machines.md
│   ├── permissions.md
│   ├── metrics.md
│   ├── api-contract.md
│   ├── traceability.md
│   ├── demo-script.md
│   ├── ml-evaluation.md
│   ├── model-card.md
│   └── assets/
│       └── confusion_matrix.png
│
├── backend/
│   ├── alembic/
│   │   └── versions/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── main.py
│   │   └── worker.py
│   ├── scripts/
│   │   └── seed.py
│   ├── tests/
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── postcss.config.js
│
├── ml/
│   ├── casttrace_ml/
│   │   ├── __init__.py
│   │   ├── model.py
│   │   ├── preprocessing.py
│   │   ├── quality_gate.py
│   │   ├── routing.py
│   │   └── unfamiliar_input.py
│   ├── artifacts/
│   │   ├── model_metadata.json
│   │   └── test_evaluation_report.json
│   ├── README.md
│   ├── pyproject.toml
│   └── train.py
│
└── scripts/
    ├── audit_cross_resolution.py
    ├── audit_embedding_similarity.py
    ├── backup_database.py
    ├── create_split_manifest.py
    ├── evaluate_held_out_test.py
    ├── generate_phase3a_deliverables.py
    ├── recalculate_validation_routing.py
    ├── register_model_version.py
    └── verify_phase3b_migration.py
```

Generated files, local databases, raw datasets, environment secrets, and restricted model artifacts are excluded from Git according to `.gitignore`.

---

## 3. Prerequisites

Install the following software before setting up the project:

* Git
* Python 3.10 or later, subject to compatibility with the pinned dependencies
* Node.js 18 or later
* npm 9 or later

Python 3.14 was used in the development environment.

Verify your installations:

```powershell
git --version
python --version
node --version
npm --version
```

---

## 4. Clone the Repository

Open PowerShell and navigate to the directory where you want to store the project.

```powershell
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd Buildathon_2.0
```

Replace `<YOUR_GITHUB_REPOSITORY_URL>` with the actual GitHub repository URL.

If the repository directory has a different name, enter that directory instead.

---

## 5. Configure Environment Variables

Create your local environment file from the committed template:

```powershell
Copy-Item .env.example .env
```

Review `.env` and update the settings for your local environment as required.

**Important:** Never commit `.env` or other files containing passwords, API keys, or secrets. Commit `.env.example` with placeholder values instead.

---

## 6. Backend Setup

Run these commands from the project root:

```powershell
python -m venv .venv
```

Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the backend dependencies:

```powershell
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
```

Install the ML package and its declared dependencies:

```powershell
pip install -e .\ml
```

The editable installation makes the local `casttrace_ml` package available to the Python environment.

If PowerShell blocks virtual-environment activation, use the environment's executables directly, as shown in the commands throughout this README.

---

## 7. Initialize the Database

Apply all available Alembic migrations:

```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

This creates or updates the database schema using the repository's migration history.

The project includes migrations for the core application and the ML model-run and worker infrastructure.

### Seed Demo Accounts

Run the seed script:

```powershell
.\.venv\Scripts\python.exe backend\scripts\seed.py
```

The seed script is designed to be idempotent, so it can be run again without creating duplicate seed accounts.

The demo accounts and their credentials are listed in the **Seed Accounts Reference** section below. These credentials are for local development and demonstrations only. Change them before using the application in any shared or production environment.

---

## 8. Frontend Setup

From the project root, install the frontend dependencies:

```powershell
Push-Location frontend
npm install
Pop-Location
```

The frontend development server uses port `5173` and proxies API requests to the backend on port `8001`.

---

## 9. Run the Application

Open separate PowerShell terminals from the project root.

### Terminal 1 — Start the FastAPI Backend

Ensure the virtual environment is available, then run:

```powershell
.\.venv\Scripts\uvicorn.exe backend.app.main:app --host 127.0.0.1 --port 8001 --reload
```

Available endpoints:

| Resource                      | Address                                     |
| ----------------------------- | ------------------------------------------- |
| API base                      | http://127.0.0.1:8001                       |
| Interactive API documentation | http://127.0.0.1:8001/docs                  |
| Health check                  | http://127.0.0.1:8001/health                |
| Worker status                 | http://127.0.0.1:8001/api/v1/workers/status |

Worker status is restricted to authorized roles.

### Terminal 2 — Start the AI Inference Worker

Run:

```powershell
.\.venv\Scripts\python.exe backend\app\worker.py
```

The worker processes queued inference jobs independently from the FastAPI application.

Available options:

| Option                      | Purpose                                         |
| --------------------------- | ----------------------------------------------- |
| `--once`                    | Process currently eligible queued jobs and exit |
| `--poll-interval <seconds>` | Configure the polling interval                  |
| `--inject-failure`          | Inject a controlled development-only failure    |
| `--target-run-id <uuid>`    | Target a particular run for failure injection   |

The default polling interval is one second.

**ML artifact requirement:** The inference worker requires the trained model weights and unfamiliar-input reference described in the ML Artifact Availability section. These files are not included in the repository. The worker cannot perform real inference until the required artifacts are obtained or generated locally and their hashes match the model metadata.

### Terminal 3 — Start the React Frontend

Run:

```powershell
Push-Location frontend
npm run dev
```

Open the following address in your browser:

**http://127.0.0.1:5173**

Keep this terminal open while using the application. To return to the project root after stopping the frontend, run:

```powershell
Pop-Location
```

---

## 10. Machine Learning and Inference Architecture

### 10.1 Process Separation

The FastAPI process handles application APIs, authorization, and inference-job creation. The detached worker process owns model loading and model execution.

The API process does not instantiate the PyTorch inference model.

### 10.2 Inference Pipeline

The inference pipeline applies the following stages:

1. **Evidence integrity verification:** Recalculates the SHA-256 hash of the stored image and compares it with the recorded hash.
2. **Image-quality gate:** Rejects unusable or invalid images before model execution.
3. **Unfamiliar-input detection:** Compares image features with the saved reference distribution.
4. **Binary classification:** The ResNet-18 model produces a score for the `DEFECTIVE` class.
5. **Routing:** Uses the frozen score thresholds to direct the image to a triage outcome.

### 10.3 Routing Thresholds

The current inference implementation uses these thresholds:

| Condition                   | Routing outcome    |
| --------------------------- | ------------------ |
| Score ≤ `0.01`              | `LIKELY_OK`        |
| Score ≥ `0.50`              | `LIKELY_DEFECTIVE` |
| Score > `0.01` and < `0.50` | `NEEDS_REVIEW`     |

Failed quality checks and unfamiliar inputs are routed to human review instead of being treated as automatically acceptable.

The classifier's score represents its model output on a scale from zero to one; it should not be interpreted as a guarantee of calibrated real-world probability.

**Machine predictions do not automatically release or contain a production batch.** Authorized human decisions remain required.

### 10.4 Model Artifact Availability

The repository intentionally excludes the raw dataset, trained model weights, and private dataset-related artifacts.

Real inference requires the appropriate local artifacts, including:

```text
ml/artifacts/
├── model_best.pt
├── model_metadata.json
└── unfamiliar_guard_reference.json
```

The model metadata records the expected artifact hashes. The inference service verifies the required files before loading the model.

To make real inference operational on a fresh clone:

1. Obtain or generate the trained model weights and unfamiliar-input reference through an approved process.
2. Place them at the expected paths under `ml/artifacts/`.
3. Verify that the actual SHA-256 hashes match the values in `model_metadata.json`.
4. Register the model version using the project's model-registration script.
5. Start the inference worker and verify its readiness.

The raw casting dataset is not included in Git. The project's model metadata records its source and a CC BY-NC-ND 4.0 licence. The redistribution status of the trained weights has not been resolved; do not publish the dataset or model weights without confirming that redistribution is permitted.

**A successful code clone alone does not provide the excluded model files.** Until those artifacts are provisioned, real ML inference is not ready, even though the rest of the application source code is available.

---

## 11. Worker Reliability and Recovery

The inference worker includes safeguards designed to support reliable asynchronous execution.

### Atomic Job Claiming

Database-backed conditional updates prevent multiple workers from successfully claiming the same eligible inference job.

### Idempotency

Inference requests support idempotency protection to reduce duplicate work from repeated requests.

### Retry Policy

A logical inference request has a maximum of three attempts:

* Attempt 1: Initial execution
* Attempt 2: Retry after a five-second backoff
* Attempt 3: Final retry after a thirty-second backoff

No fourth attempt is permitted.

### Lease Recovery

A worker acquires a 45-second lease on a claimed job. An expired lease triggers recovery and rescheduling when the attempt budget allows it.

### Worker Heartbeat

Worker heartbeats are updated every ten seconds. A worker without a heartbeat for more than thirty seconds is reported as offline.

### Evidence Integrity

If the original image bytes no longer match the recorded SHA-256 hash, inference is stopped and the run fails with `EVIDENCE_INTEGRITY_MISMATCH`. This integrity failure is non-retryable.

---

## 12. Multi-Image Inspection Aggregation

Item-level routing is derived from the latest applicable inference results across active, non-superseded images.

* If any active image is `LIKELY_DEFECTIVE`, the item is derived as `LIKELY_DEFECTIVE`.
* If any applicable image needs review, has failed, or is still processing, the item is derived as `NEEDS_REVIEW`, unless a defective image already determines the outcome.
* An item is derived as `LIKELY_OK` only when all required active images are `LIKELY_OK`.
* Superseded images are excluded from the active aggregation.

This derived view does not replace the official human inspection decision or authorized batch release/containment process.

---

## 13. Controlled Failure Injection Demo

This demonstration exercises worker failure handling without deliberately corrupting model weights.

**Prerequisite:** The application database must be migrated and the inference worker must have the required model artifacts configured.

1. Create an eligible inference request using an authorized Inspector or Quality Manager account:

   ```text
   POST /api/v1/images/{id}/infer
   ```

2. Run the worker with controlled failure injection:

   ```powershell
   .\.venv\Scripts\python.exe backend\app\worker.py --once --inject-failure
   ```

3. Verify that the injected attempt is recorded as failed with the error code `DEMO_INJECTED_FAILURE`.

4. Verify that the retry is scheduled according to the retry policy.

5. Resume normal processing:

   ```powershell
   .\.venv\Scripts\python.exe backend\app\worker.py --once
   ```

6. Verify the final run state and confirm that the original attempt remains in
