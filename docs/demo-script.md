# CastTrace AI — End-to-End Demonstration Script & Presenter Protocol

**Document Version:** 2.0.0
**Phase:** 7 (Product Readiness, Live Showcase & Operational Validation)
**Target Product:** Cast Stainless Steel Impeller Manufacturing (CF8M / 316SS)
**Demonstration Scope:** 7-Act Live Showcase, Robustness Exceptions & Presenter Checklist

---

## 1. Executive Summary & Value Proposition

CastTrace AI solves the fundamental compliance, quality-drift, and photographic-inflation challenges in industrial casting inspection:
1. **Human-Machine Separation:** Real ResNet-18 deep learning accelerates visual defect triage, but **never** independently releases or scraps a batch.
2. **Item-Level Non-Inflation:** Technicians can upload multiple diagnostic photos per impeller; evidence is attached to physical serialized items without inflating defect counts.
3. **Four-Eyes Governance:** Remediated defects require independent Quality Manager verification—an implementer can never approve their own corrective action.
4. **Immutable Decision Gate:** Batches can only be released when 8 deterministic quality gates evaluate to 0 blockers. Every release creates an immutable JSON decision snapshot.

---

## 2. Presenter Setup & Pre-Flight Checklist

Before beginning the live showcase, verify that the environment is fully operational:

* [ ] **Backend Service:** Running at `http://127.0.0.1:8001` (`.\scripts\dev.ps1 backend` or Uvicorn).
* [ ] **Worker Daemon:** Running at `127.0.0.1` (`.\scripts\dev.ps1 worker` or `worker.py --poll-interval 1.0`).
* [ ] **Frontend Application:** Running at `http://localhost:5173` (`.\scripts\dev.ps1 frontend` or Vite dev server).
* [ ] **ML Weights:** Verified present under `ml/artifacts/model_best.pt` with SHA-256 match.
* [ ] **Clean Probes:** Navigate to `http://localhost:5173/health` in browser; confirm `status: "healthy"`, `database: "connected"`, and `is_inference_ready: true`.
* [ ] **Demo Accounts Active:**
  * `supervisor_torres` (`SUPERVISOR` / `Password123!`) — Batch setup & containment
  * `inspector_chen` (`INSPECTOR` / `Password123!`) — Item registration, photo capture & review
  * `qm_reynolds` (`QUALITY_MANAGER` / `Password123!`) — Four-Eyes CAPA verification & release sign-off

---

## 3. Seven-Act Demonstration Protocol

```
Act 1: Production Setup (Supervisor)
   │
Act 2: Inspection & Evidence Capture (Inspector)
   │
Act 3: AI-Assisted Inference & Human Review (Inspector)
   │
Act 4: Defect Logging & Four-Eyes CAPA (Supervisor & QM)
   │
Act 5: Reinspection & Defect Resolution (Inspector)
   │
Act 6: Batch Release Governance (Quality Manager)
   │
Act 7: Auditability & Immutable Snapshot (Quality Manager)
```

---

### Act 1 — Production Setup

**Presenter Goal:** Show traceability from alloy/drawing catalog to production batch initialization.

* **Persona:** Log in as **Supervisor Torres** (`supervisor_torres`).
* **Action 1.1 — Select Product SKU:**
  * Navigate to `/products` in the top navigation.
  * Select or verify product `PUMP-IMP-CF8M-210` (Closed Vane Impeller 210mm, CF8M Stainless Steel, Drawing `DWG-IMP-210-REV4`).
* **Action 1.2 — Initialize Production Batch:**
  * Navigate to `/batches` and click **"+ New Batch"**.
  * Enter Batch Number: `LOT-202610-DEMO`
  * Product: `PUMP-IMP-CF8M-210`
  * Declared Quantity: `40`
  * Heat Number: `HEAT-CF8M-9941`
  * Click **"Create Batch"**.
* **Expected Observable Results:**
  * Batch appears in list with badge **Status: IN_PRODUCTION**.
  * Declared quantity displays `40 units`.
  * Audit log records `BATCH_INITIALIZED` event.

---

### Act 2 — Inspection & Evidence Capture

**Presenter Goal:** Demonstrate physical item registration, multi-photo evidence capture, and photographic non-inflation.

* **Persona:** Log in as **Inspector Chen** (`inspector_chen`).
* **Action 2.1 — Create Inspection Session:**
  * Navigate to `/inspections` and click **"+ New Inspection"**.
  * Select Batch `LOT-202610-DEMO`.
  * Select Stage: `FINAL_VISUAL` | Sampling Plan: `AQL_LEVEL_II` (Normal Inspection).
  * Click **"Start Inspection"** (Session status: `DRAFT`).
* **Action 2.2 — Register Physical Impeller Items:**
  * In the **Physical Items** section, register 2 items:
    * `SN-IMP-001` (Cavity 1, Suction Eye)
    * `SN-IMP-002` (Cavity 2, Discharge Vane)
  * Click **"Register Items"**. Both items display badge **PENDING**.
* **Action 2.3 — Upload Multi-Angle Evidence (Non-Inflation):**
  * For item `SN-IMP-001`, upload front suction photo (`impeller_front.jpg`).
  * Upload a second diagnostic photo for the same item (`impeller_vane.jpg`).
  * For item `SN-IMP-002`, upload defect indication photo (`impeller_defect.jpg`).
* **Expected Observable Results:**
  * Every uploaded photo shows a green **SHA-256 Hash Verified** badge.
  * Item `SN-IMP-001` displays **2 Photos Attached**, but physical inspected item count remains strictly **1 item** (demonstrating distinct-item non-inflation).
  * Click **"Submit Inspection"**; status transitions to **SUBMITTED**.

---

### Act 3 — AI-Assisted Inference & Human Review

**Presenter Goal:** Showcase the detached ResNet-18 inference pipeline, calibrated routing, and human-in-the-loop review.

* **Persona:** Continue as **Inspector Chen** (`inspector_chen`).
* **Action 3.1 — Trigger Inference Pipeline:**
  * Click **"Run AI Defect Analysis"** for the inspection items.
  * Explain to audience: *The FastAPI backend enqueues the job in SQLite; the detached background worker picks up the job with an atomic lease, evaluates image quality and unfamiliarity, and runs ResNet-18.*
* **Action 3.2 — View AI Predictions:**
  * In $\approx 1$ second, results populate live:
    * Item 1 (`SN-IMP-001`): Model Score `0.00013` $\rightarrow$ Triage Badge **LIKELY_OK** (Green).
    * Item 2 (`SN-IMP-002`): Model Score `0.94210` $\rightarrow$ Triage Badge **LIKELY_DEFECTIVE** (Red).
* **Action 3.3 — Record Human Review Decisions:**
  * Open Review for Item 1: Click **"Confirm Good"** with note *"Visual surface clear of inclusions"*.
  * Open Review for Item 2: Click **"Confirm Defective"** with note *"Hot tear observed along trailing edge of blade 3"*.
* **Expected Observable Results:**
  * Item 1 status transitions to **CONFIRMED_GOOD**.
  * Item 2 status transitions to **CONFIRMED_DEFECTIVE** and automatically prompts defect logging.
  * Human decision card freezes an **Immutable AI Snapshot** capturing the prediction, confidence, model version, and timestamp at time of review.

---

### Act 4 — Defect Logging & Four-Eyes CAPA

**Presenter Goal:** Prove controlled defect registration, root-cause remediation, and strict Four-Eyes separation of duties.

* **Action 4.1 — Log Defect (Inspector Chen):**
  * From Item 2 review, log defect:
    * Category: `HOT_TEAR`
    * Severity: `CRITICAL`
    * Surface Location: `BLADE_TRAILING_EDGE`
    * Description: `2.5mm thermal shrinkage hot tear on suction side`
  * Defect `DEF-202610-001` is registered with status **OPEN**.
* **Action 4.2 — Assign CAPA Plan (Supervisor Torres):**
  * Switch user to **Supervisor Torres**.
  * Navigate to `/capa` and click **"Create CAPA"** for Defect `DEF-202610-001`:
    * Title: `Rework trailing edge tear via TIG weld build-up and stress relief`
    * Action Type: `REWORK`
    * Assigned Implementer: `supervisor_torres`
  * Click **"Create Action"** (CAPA status: `OPEN`, Defect: `ACTION_ASSIGNED`).
* **Action 4.3 — Complete Implementation (Supervisor Torres):**
  * Click **"Complete Implementation"**:
    * Completion Notes: `Blended crack indication, preheated to 150C, performed ER316L filler pass, post-weld solution annealed.`
  * CAPA transitions to **Implementation: COMPLETED**, **Verification: PENDING**.
* **Action 4.4 — Demonstrate Four-Eyes Enforcement:**
  * While still logged in as Supervisor Torres (the implementer), attempt to click **"Approve Verification"**.
  * **System Rejection:** UI disables button or API returns `HTTP 403 Forbidden` (`INSUFFICIENT_PERMISSIONS: Implementer cannot verify own CAPA`).
* **Action 4.5 — Independent QM Verification (Quality Manager Reynolds):**
  * Switch user to **Quality Manager Reynolds** (`qm_reynolds`).
  * Navigate to `/capa`, open the action, and click **"Approve Verification"**:
    * Verification Notes: `Metallurgical review approved. Wall thickness exceeds minimum 4.0mm spec.`
  * CAPA transitions to **VERIFIED**; Defect status transitions to **PENDING_REINSPECTION**.

---

### Act 5 — Reinspection & Defect Resolution

**Presenter Goal:** Demonstrate follow-up verification, defect closure, and recurrence lineage preservation.

* **Persona:** Log in as **Inspector Chen** (`inspector_chen`).
* **Action 5.1 — Upload Reinspection Evidence:**
  * Open Defect `DEF-202610-001` and navigate to **Reinspection**.
  * Upload post-repair dye penetrant test photo (`impeller_repaired_pt.jpg`).
* **Action 5.2 — Record Reinspection Outcome:**
  * Select Outcome: **DEFECT_RESOLVED**
  * Findings: `Color-contrast liquid penetrant inspection shows zero residual crack indications. Surface roughness Ra 1.6um achieved.`
  * Click **"Submit Reinspection"**.
* **Expected Observable Results:**
  * Defect status updates to **RESOLVED** (Green).
  * Inspection item `SN-IMP-002` clears to **CLEAR** status.
  * Audit event `DEFECT_RESOLVED` is logged with linkage to original inspection, CAPA, and reinspection records.

---

### Act 6 — Batch Governance & Release Gates

**Presenter Goal:** Demonstrate the automated 8-rule release gate engine, proving that releases are blocked when incomplete and permitted only when clean.

* **Persona:** Log in as **Quality Manager Reynolds** (`qm_reynolds`).
* **Action 6.1 — Demonstrate Blocked Release Scenario:**
  * Navigate to a batch with incomplete work (or place current batch on operational hold: click **"Hold Batch"**).
  * Navigate to the **Release Gate** panel.
  * **Observable Results:**
    * Release Gate displays amber/red banner: **RELEASE BLOCKED**.
    * Structured blocker list shows: `BATCH_ON_HOLD`.
    * Attempting to click **"Release Batch"** is rejected by backend (`HTTP 422 Unprocessable Entity`).
* **Action 6.2 — Lift Operational Hold:**
  * Click **"Remove Containment Hold"**; batch status returns to `IN_PRODUCTION`.
* **Action 6.3 — Evaluate Clean Release Gate:**
  * Refresh Release Gate panel.
  * All 8 automated quality gate rules evaluate to green checks:
    1. [x] `BATCH_NOT_HELD`: Batch is not under operational containment.
    2. [x] `SAMPLING_SATISFIED`: Mandatory sampling quantity inspected.
    3. [x] `ALL_ITEMS_INSPECTED`: Zero items pending visual inspection.
    4. [x] `NO_PROCESSING_RUNS`: Zero AI inference jobs currently queued or processing.
    5. [x] `ALL_ITEMS_REVIEWED`: All inspected items have human review recorded.
    6. [x] `NO_DISPUTED_REVIEWS`: Zero unresolved AI-human review disputes.
    7. [x] `ALL_DEFECTS_RESOLVED`: All registered defects resolved via reinspection.
    8. [x] `ALL_CAPAS_VERIFIED`: All remediation actions independently verified.
  * Blocker Count: **0 blockers**.
* **Action 6.4 — Execute Official Release Decision:**
  * Click **"Official Release Batch"**.
  * Enter Justification: `Lot LOT-202610-DEMO verified compliant with API 610 CF8M casting standards. Item 2 hot tear successfully remediated, independently verified, and reinspected.`
  * Click **"Confirm & Sign Release"**.
* **Expected Observable Results:**
  * Batch status immediately updates to **RELEASED** (Dark Green badge).
  * System captures full JSON **Decision Snapshot** frozen in `batch_decisions`.

---

### Act 7 — Auditability & Decision Snapshot

**Presenter Goal:** Prove that quality decisions cannot be altered post-release and that full lineage is preserved.

* **Persona:** Continue as **Quality Manager Reynolds** (`qm_reynolds`).
* **Action 7.1 — View Immutable Decision Snapshot:**
  * On Batch Details page, open the **Decision History** card.
  * Expand the latest decision record.
  * Review the persisted JSON snapshot:
    * Policy version: `1.0.0`
    * Inspected items: `2` | Reviewed items: `2`
    * Resolved defects: `1` | Verified CAPAs: `1`
    * Release timestamp & Authorized signatory: `qm_reynolds`
* **Action 7.2 — Prove Stale-State Conflict Protection:**
  * Try to re-submit a release for the already released batch.
  * Backend returns `HTTP 409 Conflict` (`BATCH_ALREADY_RELEASED`).
* **Action 7.3 — View Chronological Audit Trail:**
  * Navigate to `/audit` or view batch audit timeline.
  * Timeline displays the unbroken chain of custody:
    `BATCH_INITIALIZED` $\rightarrow$ `IMAGE_UPLOADED` $\rightarrow$ `INFERENCE_SUCCEEDED` $\rightarrow$ `REVIEW_CONFIRMED_DEFECTIVE` $\rightarrow$ `DEFECT_LOGGED` $\rightarrow$ `CAPA_ASSIGNED` $\rightarrow$ `CAPA_COMPLETED` $\rightarrow$ `CAPA_VERIFIED` $\rightarrow$ `DEFECT_RESOLVED` $\rightarrow$ `BATCH_RELEASED`.

---

## 4. Innovation Evaluation Protocol: Recurrence Radar

### 4.1 Problem: Photographic Inflation Skew
In traditional inspection databases, calculating defect frequency by dividing *defective photos* by *total photos* produces massive photographic skew. If an inspector takes 6 macro-focus photos of a single porous impeller blade, naive analytics treat this as 6 defects.

### 4.2 Solution: Distinct-Item Normalized Recurrence
CastTrace AI tracks `inspection_items` independently from `images`. The **Recurrence Radar** metric evaluates:

$$\text{Item Recurrence Rate}(c) = \frac{\text{Distinct Inspected Items with Category } c}{\text{Total Distinct Physical Items Inspected in Batch}}$$

| Dimension | Naive Raw-Photo Count | Recurrence Radar (Item-Normalized) |
| :--- | :--- | :--- |
| **Numerator** | Total photos tagged with defect | Distinct physical impellers with defect |
| **Denominator** | Total photos captured | Total distinct physical impellers |
| **Susceptibility to Camera Bias** | **High (+500% error)** | **Zero (Invariable to photo count)** |
| **Engineering Value** | Distorts metallurgical reporting | Accurately identifies foundry mold wear |

---

## 5. Presenter Troubleshooting & Recovery Guide

| Symptom | Root Cause | Immediate Presenter Action |
| :--- | :--- | :--- |
| **AI Suggestion stays "Processing"** | Worker daemon is paused or stopped | Open worker terminal and run `.\scripts\dev.ps1 worker`. Worker claims job within 1 second. |
| **Health endpoint reports `is_inference_ready: false`** | `model_best.pt` or guard file missing | Non-ML features remain fully operational. Worker safely reports `MODEL_ARTIFACTS_UNAVAILABLE`. |
| **Release button disabled** | Gate conditions not met | Check the blocker list on the Release Gate card. Every blocker specifies the exact missing requirement. |
| **HTTP 403 on CAPA Verification** | Logged in as same user who implemented CAPA | Four-Eyes rule functioning as designed. Switch user to `qm_reynolds` to approve verification. |
| **HTTP 409 on Batch Decision** | Batch was already decided or status changed | Refresh page; verify that decision snapshot was already recorded. |
