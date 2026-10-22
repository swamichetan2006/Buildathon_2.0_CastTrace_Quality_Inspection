# CastTrace AI — End-to-End Demonstration Script & Evaluation Protocol

**Document Version:** 1.0.0  
**Phase:** 1A (Architecture and Contracts)  
**Execution Target:** Automated Python Demo Driver (`scripts/run_demo_e2e.py`) & Interactive Frontend Showcase  
**Product Focus:** Cast Stainless Steel Impeller Manufacturing (CF8M / 316SS)

---

## 1. Demonstration Overview & Setup

This document provides a step-by-step, reproducible demonstration script for **CastTrace AI**. It covers:
1. **The Complete 15-Step Quality Assurance Lifecycle (Normal Workflow)**.
2. **Nine Robustness & Security Exception Workflows**.
3. **The Recurrence Radar Innovation Evaluation Protocol** comparing distinct item-normalized recurrence against a naive raw-photo baseline.

### Pre-requisites & Seed Roles
The demonstration assumes three pre-seeded accounts:
- `inspector_chen` (Role: `INSPECTOR`, password: `Password123!`)
- `supervisor_torres` (Role: `SUPERVISOR`, password: `Password123!`)
- `qm_reynolds` (Role: `QUALITY_MANAGER`, password: `Password123!`)

---

## 2. Normal Workflow Demonstration (Steps 1–15)

| Step # | User Action & API Invocation | Persona Role | Underlying Database Changes | Expected UI Output & Response Payload |
| :---: | :--- | :--- | :--- | :--- |
| **1** | **Create Product Model**<br>`POST /api/v1/products`<br>`{"sku": "PUMP-IMP-CF8M-210", "name": "Closed Vane Impeller 210mm", "material": "CF8M Stainless Steel", "drawing_number": "DWG-IMP-210-REV4"}` | `QUALITY_MANAGER` | New row in `products`.<br>Audit event: `PRODUCT_CREATED`. | Status `201 Created`. Product appears in catalog with active status. |
| **2** | **Create Production Batch**<br>`POST /api/v1/batches`<br>`{"batch_number": "LOT-202610-098", "product_id": "<prod_id>", "manufacture_date": "2026-10-21", "heat_number": "HEAT-8841-A", "declared_quantity": 50}` | `SUPERVISOR` | New row in `batches` with status `IN_PRODUCTION`.<br>Audit: `BATCH_INITIALIZED`. | Status `201 Created`. Batch dashboard displays lot number and declared count of 50. |
| **3** | **Create Inspection & Register Physical Item**<br>`POST /api/v1/inspections`<br>`POST /api/v1/inspections/{id}/items`<br>`{"items": [{"item_identifier": "IMP-098-ITEM-01", "cavity_number": 2}]}` | `INSPECTOR` | Row in `inspections` (`status = DRAFT`).<br>Row in `inspection_items` (`status = PENDING`). | Status `201 Created`. Inspection sheet shows item registered with zero evidence photos. |
| **4** | **Upload Unseen Held-out Evaluation Image**<br>`POST /api/v1/images/upload`<br>Multipart form data: `file=@held_out_defective_04.jpg`, `inspection_item_id=<item_id>`, `image_scope=ITEM` | `INSPECTOR` | Validates magic bytes, writes file to `storage/evidence/<uuid>.jpg`, inserts row in `images`, queues job in `model_runs`. | Status `201 Created`. Evidence viewer previews uploaded photo with SHA-256 integrity badge. |
| **5** | **Execute ML Inference Classifier**<br>Background worker processes queued item or direct call: `POST /api/v1/images/{id}/infer` | System / Worker | ML pipeline executes tensor normalization & PyTorch forward pass. Updates `model_runs` (`status = SUCCEEDED`, `predicted_label = DEFECTIVE`, `score = 0.9421`). | Status `202 Accepted` $\rightarrow$ `200 OK`. UI badges item with amber **AI Suggestion: DEFECTIVE (94.2% confidence)**. |
| **6** | **Display Machine Prediction**<br>`GET /api/v1/inspections/{id}` | `INSPECTOR` | Unchanged (Read query). | UI shows dual-pane inspector review card: original high-res image alongside model score and confidence interval. |
| **7** | **Human Review Verification**<br>`POST /api/v1/reviews`<br>`{"inspection_item_id": "<item_id>", "model_run_id": "<mr_id>", "decision": "CONFIRMED_DEFECTIVE", "notes": "Confirmed thermal shrinkage tear on suction shroud"}` | `INSPECTOR` | Row created in `reviews`. `model_disagreement = FALSE`. `inspection_items.status = CONFIRMED_DEFECTIVE`. | Status `201 Created`. Inspector concurrence badge turns red; review card unlocks Defect Logging section. |
| **8** | **Create Confirmed Defect**<br>`POST /api/v1/defects`<br>`{"inspection_item_id": "<item_id>", "review_id": "<rev_id>", "category": "SHRINKAGE_POROSITY", "severity": "MAJOR", "surface_location": "SHROUD", "description": "4mm porous shrinkage zone near outer rim"}` | `INSPECTOR` | Row created in `defects` with business ID `DEF-20261021-0001` and status `OPEN`. | Status `201 Created`. Defect card generated with severity badge and link to original evidence photo. |
| **9** | **Assign Corrective Action (CAPA)**<br>`POST /api/v1/corrective-actions`<br>`{"defect_id": "<def_id>", "title": "Precision grind and polish shroud porosity", "action_type": "REWORK", "assigned_to": "<supervisor_id>", "due_date": "2026-10-23"}` | `SUPERVISOR` | Row created in `corrective_actions` (`status = OPEN`). Defect status transitions to `ACTION_ASSIGNED`. | Status `201 Created`. Action appears on Supervisor's active task board with countdown to due date. |
| **10** | **Complete Corrective Action**<br>`POST /api/v1/corrective-actions/{id}/complete`<br>`{"completion_notes": "Blended porous area with ceramic burr. Remaining wall thickness 4.2mm (spec > 3.8mm)."}` | `SUPERVISOR` | Action status $\rightarrow$ `COMPLETED`, `completed_at` set. Defect status $\rightarrow$ `PENDING_REINSPECTION`. | Status `200 OK`. Action shows completed checkmark; defect status notifies inspector for follow-up verification. |
| **11** | **Upload Follow-up Verification Evidence**<br>`POST /api/v1/images/upload`<br>Multipart form data: `file=@reinspection_repaired_01.jpg`, `inspection_item_id=<item_id>`, `image_scope=SURFACE` | `INSPECTOR` | New row in `images` tagged with surface location `SHROUD`. | Status `201 Created`. Side-by-side comparison modal displays pre-repair and post-repair images. |
| **12** | **Reinspect and Resolve Defect**<br>`POST /api/v1/reinspections`<br>`{"defect_id": "<def_id>", "corrective_action_id": "<capa_id>", "outcome": "DEFECT_RESOLVED", "notes": "Dye penetrant test confirms zero residual fissure."}` | `QUALITY_MANAGER` | Row created in `reinspections`. Defect status $\rightarrow$ `RESOLVED`. Audit: `DEFECT_RESOLVED`. | Status `201 Created`. Defect banner turns green: **RESOLVED (Verified by Quality Manager)**. |
| **13** | **Inspect Comprehensive Audit & History**<br>`GET /api/v1/audit-logs?entity_id=<batch_id>` | `QUALITY_MANAGER` | Unchanged (Read query). | UI timeline renders immutable chronicle: Batch creation $\rightarrow$ Image upload $\rightarrow$ ML inference $\rightarrow$ Human review $\rightarrow$ Defect $\rightarrow$ CAPA $\rightarrow$ Reinspection. |
| **14** | **Review Dashboard & Recurrence Radar**<br>`GET /api/v1/metrics/dashboard?batch_id=<batch_id>`<br>`GET /api/v1/metrics/recurrence-radar?product_id=<prod_id>` | All Roles | Executes deterministic SQL aggregation across distinct physical items. | Dashboard KPI cards update: Verified-Fix Rate = 100%, Open Actions = 0. Recurrence Radar plots cluster frequency. |
| **15** | **Grounded GenAI Batch Quality Summary**<br>`POST /api/v1/genai/query`<br>`{"prompt": "Summarize batch LOT-202610-098 quality status and state whether it is safe to release.", "target_batch_id": "<batch_id>"}` | `QUALITY_MANAGER` | LLM context builder retrieves batch, defect, CAPA, and reinspection records. Logs query in `genai_queries`. | Status `200 OK`. Grounded response provides complete factual summary with clickable source IDs (`[DEF-20261021-0001]`). Includes disclaimer that final release requires human QM sign-off. |
| **16** | **Release-Gate Evaluation & Official Batch Release**<br>`GET /api/v1/batches/{id}/release-gate`<br>`POST /api/v1/batches/{id}/decisions`<br>`{"decision": "RELEASE", "reason": "All 50 physical items clear; defect DEF-20261021-0001 verified resolved via follow-up reinspection."}` | `QUALITY_MANAGER` | Validates 6 release-gate domains. Updates `batches.status = RELEASED`. Creates immutable `batch_decisions` row with full JSON `snapshot`. Logs audit: `BATCH_RELEASED`. | Status `201 Created`. UI displays green **BATCH RELEASED** banner with immutable decision snapshot badge, timestamp, and signed QM authority. |

---

## 3. Robustness & Security Exception Workflows

### 3.1 Exception E1: Uncertain / Poor-Quality Image
- **Scenario:** Inspector uploads an underexposed or blurred photo.
- **System Action:** ML inference returns low confidence (e.g. 0.51) or worker flags poor contrast. Inspector flags review as `REQUEST_ADDITIONAL_EVIDENCE`.
- **Expected Outcome:** Item status transitions to `ADDITIONAL_EVIDENCE_REQUESTED`. Previous image is superseded (`is_superseded = TRUE`) when replacement is provided, preserving original in audit records.

### 3.2 Exception E2: Failed ML Processing & Resilient Retry
- **Scenario:** Background worker encounters corrupted tensor bytes or timeout during inference.
- **System Action:** Worker catches exception, records stack trace in `model_runs.error_details`, and marks run `FAILED`. Inspection is NOT destroyed.
- **Inspector Action:** Inspector clicks "Retry Inference" (`POST /api/v1/model-runs/{id}/retry`).
- **Expected Outcome:** A new row is inserted into `model_runs` with `attempt_number = 2` and `parent_run_id` referencing the failed attempt. Failed run remains in history for telemetry.

### 3.3 Exception E3: Manual Review Without ML Run (Graceful Degraded Mode)
- **Scenario:** ML inference is temporarily disabled or offline.
- **System Action:** Inspector opens item review directly. `model_run_id` is passed as `null`.
- **Expected Outcome:** System permits human review to proceed unimpeded. Inspector confirms `CONFIRMED_GOOD` with note "Manual visual review performed during offline service window."

### 3.4 Exception E4: Unauthorized Attempt to Release Batch
- **Scenario:** `inspector_chen` calls `POST /api/v1/batches/{id}/decisions` attempting to release the batch.
- **Expected Outcome:** API terminates request immediately with HTTP `403 Forbidden` and error code `INSUFFICIENT_PERMISSIONS`. Incident is logged in `audit_log`.

### 3.5 Exception E5: Invalid State Transition (Premature Defect Closure)
- **Scenario:** Supervisor calls `POST /api/v1/defects/{id}/resolve` directly while defect is still `IN_PROGRESS` without completing a reinspection.
- **Expected Outcome:** Backend rejects request with HTTP `409 Conflict` and code `INVALID_STATE_TRANSITION`, citing requirement for an authorized reinspection record.

### 3.6 Exception E6: Unknown Batch in GenAI Query
- **Scenario:** User prompts GenAI: "What is the defect rate of batch LOT-UNKNOWN-999?"
- **Expected Outcome:** System searches database, finds zero records for the lot number, and responds: *"No batch matching LOT-UNKNOWN-999 was found in the factory records. No predictions or quality inferences can be made."* Model does NOT hallucinate batch statistics.

### 3.7 Exception E7: Misleading Premise in GenAI Query
- **Scenario:** User asks: "Why did the AI system release batch LOT-202610-098 yesterday?"
- **Expected Outcome:** GenAI refutes the premise based on grounding rules: *"AI systems do not have authority to release manufacturing batches. Batch LOT-202610-098 was reviewed and officially released by Quality Manager E. Reynolds on 2026-10-21 following verified reinspection."* Cites `batch_decisions.id`.

### 3.8 Exception E8: Unauthorized Request for Restricted Records via GenAI
- **Scenario:** `inspector_chen` asks: "Show me executive financial scrap cost write-offs for this quarter."
- **Expected Outcome:** GenAI context retrieval prunes all non-inspector-scoped records. GenAI answers: *"You do not have access to financial scrap accounting records. Please contact your Quality Manager."*

### 3.9 Exception E9: Recurrent Defect on Reinspection (Defect Reopening)
- **Scenario:** After grinding rework, reinspection reveals residual crack indication.
- **Inspector Action:** Inspector submits reinspection with `outcome: "DEFECT_RECURRED_REOPENED"`.
- **Expected Outcome:** Defect state transitions from `PENDING_REINSPECTION` to `REOPENED`. System requires supervisor to assign a new CAPA remediation plan.

### 3.10 Exception E10: Release Blocked by Unresolved Gate Conditions
- **Scenario:** Quality Manager requests batch release while an item review is disputed, an inference run is still processing, or a defect is unresolved.
- **Expected Outcome:** Backend rejects request with HTTP `422 Unprocessable Entity` and returns a structured list of blockers (e.g. `UNRESOLVED_DEFECT`, `PENDING_HUMAN_REVIEW`). The batch remains in `PENDING` or `ON_HOLD` with zero false decision records created.

### 3.11 Exception E11: Stale State / Check-Then-Act Concurrency Collision
- **Scenario:** A Quality Manager checks the release gate and approves release, but a concurrent shop-floor event reopens a defect or places the batch on hold before the release transaction commits.
- **Expected Outcome:** In-transaction atomic verification detects the state collision and rejects the request with HTTP `409 Conflict`. No stale release decision or corrupted snapshot is persisted.

---

## 4. Innovation Evaluation Protocol: Recurrence Radar

### 4.1 Evaluation Hypothesis
Counting raw photographs overestimates defect recurrence rates when technicians take multiple diagnostic photos of severe defects, whereas counting distinct physical items normalizes recurrence trends against true manufacturing volume.

### 4.2 Benchmark Baseline Comparison

| Dimension | Baseline Approach (Naive Photo Count) | Recurrence Radar (Distinct Item Normalized) |
| :--- | :--- | :--- |
| **Numerator** | Total photos tagged with defect category $c$. | Distinct physical items (`inspection_items`) exhibiting category $c$. |
| **Denominator** | Total photos captured across batch. | Total distinct physical items inspected in batch. |
| **Susceptibility to Photographic Skew** | **High:** An item photographed 6 times from multiple angles skews the apparent defect frequency by 600%. | **Zero:** An item with 6 photos of a crack is counted exactly once. |
| **Trend Validity** | Fluctuates based on operator camera usage. | Reflects metallurgical and tooling recurrence. |

### 4.3 Measurable Evaluation Protocol
During Phase 8 testing, the demonstration evaluation script (`scripts/eval_recurrence_radar.py`) will execute:
1. Load a simulated multi-image test dataset of 5 batches (each batch = 100 physical items).
2. For items with severe shrink cracks, inject 3–5 surface photos per defective item.
3. Calculate both metrics across batches.
4. **Demonstration Output:** The script will print the empirical variance and demonstrate that Recurrence Radar accurately reflects the true 4.0% item defect rate, whereas the naive photo baseline reports a distorted 14.8% rate.
