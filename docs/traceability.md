# CastTrace AI — Problem Statement Traceability Matrix

**Document Version:** 1.0.0  
**Phase:** 1A (Architecture and Contracts)  
**Scope:** Buildathon 2.0 — Problem Statement 1 (Product Quality Inspection & Defect Tracking System)

---

## 1. Traceability Overview

This matrix maps every requirement from Problem Statement 1 (PS-1), including mandatory core domains (A–H), Machine Learning lifecycle, Grounded GenAI, the Recurrence Radar innovation, and demonstration deliverables, directly to system architecture artifacts, database entities, endpoints, UI views, and verification test procedures.

---

## 2. PS-1 Mandatory Requirements Traceability

| Req ID | Requirement Area & Description | Target Phase | Database Entities | API Endpoints & UI Components | Verification & Test Evidence Method |
| :--- | :--- | :---: | :--- | :--- | :--- |
| **A-1** | Create, view, edit, and archive product records (SKU, material, tolerances). | Phase 2, 5 | `products` | `POST /products`<br>`GET /products`<br>`DELETE /products/{id}`<br>`ProductsPage.tsx` | Pytest CRUD tests; verify soft-archive flag preserves historical links; UI end-to-end form test. |
| **A-2** | Create, view, edit, and archive production batches (lot#, heat#, quantity). | Phase 2, 5 | `batches`, `products` | `POST /batches`<br>`GET /batches`<br>`BatchesPage.tsx` | Unit test lot quantity validation ($>0$); verify foreign key to products; batch listing query tests. |
| **B-1** | Link inspection staging sessions to specific batches and inspectors. | Phase 2, 5 | `inspections`, `batches`, `users` | `POST /inspections`<br>`GET /inspections/{id}`<br>`InspectionCreateModal.tsx` | Integration test verifying inspection-batch FK constraint and inspector user assignment. |
| **B-2** | Capture photographic evidence with explicit `image_scope` (ITEM, SURFACE, BATCH_SAMPLE). | Phase 2, 5 | `images`, `inspection_items` | `POST /images/upload`<br>`ImageEvidenceUploader.tsx` | API test uploading JPEG/PNG; assert scope enum validation; verify metadata stored accurately. |
| **B-3** | Preserve original evidence immutably; track superseded images with rationale. | Phase 2, 5 | `images` | `POST /images/{id}/supersede`<br>`EvidenceHistoryView.tsx` | Test asserting original image cannot be deleted or overwritten; verify `superseded_by_id` pointer. |
| **B-4** | Multi-image item aggregation: Multiple photos linked to one physical item. | Phase 2, 5 | `inspection_items`, `images` | `POST /inspections/{id}/items`<br>`ItemDetailCard.tsx` | Test uploading 3 photos for 1 item; assert item count is 1 in database and metric aggregates. |
| **B-5** | Batch sample image item accounting: Account for represented item count when known. | Phase 2, 5 | `images` | `represented_item_count` in `/images/upload` | Verify `represented_item_count` is stored and included in batch sample coverage calculations. |
| **C-1** | Separation of Machine Predictions and Human Decisions into distinct records. | Phase 1A, 2, 4 | `model_runs`, `reviews` | `POST /images/{id}/infer`<br>`POST /reviews`<br>`DualReviewPanel.tsx` | Database schema audit; verify independent tables, timestamps, and separate actor identities. |
| **C-2** | ML binary inference predicting strictly GOOD or DEFECTIVE. | Phase 3 | `model_runs`, `model_versions` | Background Worker<br>`POST /images/{id}/infer` | Model unit test verifying output is constrained to `GOOD` or `DEFECTIVE` with confidence score. |
| **C-3** | Human review workflow: Accept, override, or dispute ML suggestions. | Phase 4, 5 | `reviews`, `model_runs` | `POST /reviews`<br>`POST /reviews/dispute`<br>`ReviewWorkspace.tsx` | Test inspector overriding ML prediction; assert `model_disagreement = TRUE` and status recorded. |
| **C-4** | Degraded / manual review recovery when ML inference fails or is unavailable. | Phase 4, 5 | `reviews` | `POST /reviews` (nullable `model_run_id`) | Simulate failed ML run; verify human review can proceed and complete inspection without blocker. |
| **D-1** | Human-selected defect classification (category, severity, surface location, notes). | Phase 4, 5 | `defects`, `reviews` | `POST /defects`<br>`DefectLoggingModal.tsx` | Validation test rejecting automated category assignment; test mandatory severity/category fields. |
| **D-2** | Corrective Action (CAPA) tracking: Assign owner, due date, description, work status. | Phase 4, 5 | `corrective_actions`, `defects` | `POST /corrective-actions`<br>`CAPAManager.tsx` | Lifecycle test: Transition `OPEN` $\rightarrow$ `IN_PROGRESS` $\rightarrow$ `COMPLETED`; verify due date validation. |
| **D-3** | Follow-up verification inspection (Reinspection) after corrective action. | Phase 4, 5 | `reinspections`, `defects` | `POST /reinspections`<br>`ReinspectionModal.tsx` | Verification test linking follow-up inspection to defect and CAPA action. |
| **D-4** | Defect resolution or reopening based on reinspection outcome. | Phase 4, 5 | `defects`, `reinspections` | `POST /reinspections` | Test: Reinspection clear $\rightarrow$ `RESOLVED`; Reinspection defect found $\rightarrow$ `REOPENED`. |
| **E-1** | Decoupled Batch Release/Hold decisions separate from individual inspection outcomes. | Phase 2, 4, 5 | `batch_decisions`, `batches` | `POST /batches/{id}/decisions`<br>`POST /batches/{id}/hold` | Verify completing an inspection does NOT release batch; release requires explicit authorized call. |
| **E-2** | Quality containment hold: Immediate suspension of batch shipping. | Phase 2, 5 | `batches`, `batch_decisions` | `POST /batches/{id}/hold`<br>`BatchDetailHeader.tsx` | Test transitioning batch to `ON_HOLD`; assert batch status is visible across dashboards. |
| **E-3** | Documented release policy: Prevent standard release with open defects unless authorized QM concession is documented. | Phase 2, 4 | `batch_decisions`, `defects` | `POST /batches/{id}/decisions` | Test attempting release on batch with open defect returns 422 unless explicit QM concession justification is provided. |

| **F-1** | Operational quality dashboard with filters (batch, product, date). | Phase 6 | Deterministic SQL queries | `GET /metrics/dashboard`<br>`DashboardOverview.tsx` | Integration tests verifying SQL queries match mathematical definitions in `docs/metrics.md`. |
| **F-2** | Pending reviews, confirmed defects, open actions, and recent activity feeds. | Phase 5, 6 | `reviews`, `defects`, `corrective_actions` | `GET /defects?status=OPEN`<br>`ActivityFeed.tsx` | Test query pagination and status filtering under realistic mock database load. |
| **G-1** | Strict backend validation, schema enforcement, and role permissions. | Phase 1A, 2 | `users`, FastAPI RBAC | FastAPI Dependencies<br>`docs/permissions.md` | Security test suite verifying `403 Forbidden` when unauthorized role calls protected routes. |
| **G-2** | Idempotency protection against duplicate submissions on network retry. | Phase 2 | `idempotency_keys` | `IdempotencyMiddleware` | Test sending duplicate `POST` with identical `Idempotency-Key`; assert single DB write and HTTP `200`. |
| **H-1** | Append-only audit history of state changes, overrides, and administrative actions. | Phase 2 | `audit_log` | `GET /audit-logs`<br>`AuditTrailViewer.tsx` | Test that entity mutations generate audit rows; verify database rejects `UPDATE` on `audit_log`. |
| **H-2** | Resilient background processing: Preserves failed model runs and supports retry. | Phase 3 | `model_runs` | `POST /model-runs/{id}/retry`<br>`WorkerTask.py` | Simulate worker crash/timeout; verify run marked `FAILED`, new retry attempt increments counter. |

---

## 3. Specialized & Innovation Requirements Traceability

| Req ID | Requirement Area & Description | Target Phase | Implementation Architecture | API / UI Components | Verification & Test Evidence Method |
| :--- | :--- | :---: | :--- | :--- | :--- |
| **ML-1** | PyTorch Transfer Learning Binary Classifier (GOOD / DEFECTIVE). | Phase 3 | PyTorch, torchvision (ResNet-18 / MobileNetV3) | `ml/model.py`<br>`ml/train.py`<br>`ml/evaluate.py` | Model checkpoint evaluation script verifying accuracy, ROC-AUC, precision, and recall on test split. |
| **ML-2** | Dataset Verification: Validate casting dataset images, labels, and licence. | Phase 3 | Local casting dataset | `scripts/verify_dataset.py` | Script checks image integrity, class balance, zero label leakage, and logs dataset provenance. |
| **ML-3** | Robust image pre-processing and format normalization (10MB limit, magic bytes). | Phase 2, 3 | Pillow, OpenCV, python-magic | `core/image_processor.py` | Unit tests with corrupted files, oversized files (>10MB), non-image extensions; assert `415/413`. |
| **GA-1** | Provider-independent GenAI client with DB retrieval context. | Phase 7 | GenAI adapter interface + offline deterministic fallback | `POST /genai/query`<br>`GenAIAssistantModal.tsx` | Mock/live provider unit tests verifying grounded answers with explicit citations. |
| **GA-2** | GenAI Grounding & Source Citation: Must return source record IDs. | Phase 7 | Context builder linking primary keys | `retrieved_source_ids` in `/genai/query` | Automated test querying batch summary; assert response includes valid `batch_id` and `defect_id`. |
| **GA-3** | GenAI Permission Boundaries: Cannot access unauthorized records. | Phase 7 | RBAC context filtering in retrieval service | Backend retrieval layer | Security test: Inspector query cannot retrieve restricted executive audit or cost records. |
| **GA-4** | GenAI Guardrails: Never independently releases batches or closes defects. | Phase 7 | System prompt + API isolation (Read-only) | Architecture design | Attempt to prompt GenAI to release batch; verify refusal and lack of DB mutation routes. |
| **RAD-1**| **Innovation — Recurrence Radar:** Detects recurring confirmed defect patterns across batches. | Phase 6 | Time-series / batch SQL aggregation | `GET /metrics/recurrence-radar`<br>`RecurrenceRadarView.tsx` | Radar test script asserting recurrence rate normalizes against physical items, not photo counts. |
| **RAD-2**| Recurrence Radar Baseline Evaluation: Measured improvement over naive raw photo count. | Phase 6 | Comparative evaluation script | `scripts/eval_recurrence_radar.py` | Benchmark test demonstrating reduction in false skew compared to naive unweighted photo counts. |
| **DEMO** | Reproducible Final Demonstration Script (Normal & Exception Workflows). | Phase 8 | End-to-end automated script + manual UI guide | `docs/demo-script.md`<br>`scripts/run_demo_e2e.py` | Execution of end-to-end demonstration covering all 15 normal steps and 9 exception scenarios. |
