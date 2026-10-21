# CastTrace AI — Role-Based Access Control (RBAC) & Permissions Matrix

**Document Version:** 1.0.0  
**Phase:** 1A (Architecture and Contracts)  
**Backend Enforcement:** FastAPI Dependencies (`SecurityScopes`, JWT claims), SQLAlchemy row-level filtering, and GenAI context pruning.

---

## 1. System Roles & Record Scopes

CastTrace AI implements a strict Role-Based Access Control (RBAC) model across three operational personas:

| Role Name | Identifier | Core Operational Focus | Record Access Scope |
| :--- | :--- | :--- | :--- |
| **Inspector** | `INSPECTOR` | Shop-floor imaging, visual quality verification, and defect logging. | **Operational Scope:** Read access to all products, batches, and model runs. Full write/update access to assigned inspections, items, images, and reviews. Read-only for batch decisions and audit logs. |
| **Production Supervisor** | `SUPERVISOR` | Production line oversight, batch creation, and CAPA remediation execution. | **Production Scope:** Read access to all products, batches, inspections, and defects. Write access to create batches, assign/update corrective actions in their shift, and initiate batch holds. Read-only for model weights, reviews, and audit logs. |
| **Quality Manager** | `QUALITY_MANAGER` | Final quality authority, dispute adjudication, release gatekeeper, and compliance audit. | **Enterprise Scope:** Unrestricted read access across all entities, logs, and historical archives. Exclusive authorization to release batches, scrap lots, resolve review disputes, and configure ML model deployment. |

---

## 2. Role-Permission Matrix

Legend:
- `ALLOW`: Permitted across scope.
- `OWN`: Permitted only for records created by, assigned to, or owned by the actor.
- `DENY`: Explicitly forbidden; blocked at API gateway with `403 Forbidden`.
- `COND`: Conditional on business state rules (e.g., cannot edit submitted inspections).

| Functional Domain | Operation / Action | Inspector | Production Supervisor | Quality Manager | Enforcing Layer |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Products** | View Products & Specifications | ALLOW | ALLOW | ALLOW | API (`GET /products`) |
| | Create / Edit Product Catalog | DENY | DENY | ALLOW | API (`POST /products`, `PATCH /products/{id}`) |
| | Soft-Archive Product | DENY | DENY | ALLOW | API (`DELETE /products/{id}`) |
| **Batches** | View Batch Details & History | ALLOW | ALLOW | ALLOW | API (`GET /batches`) |
| | Create New Production Batch | DENY | ALLOW | ALLOW | API (`POST /batches`) |
| | Edit Batch Metadata (e.g., Heat #) | DENY | OWN / COND | ALLOW | API (`PATCH /batches/{id}`) |
| | Place Batch on Quality `HOLD` | ALLOW | ALLOW | ALLOW | API (`POST /batches/{id}/hold`) |
| | Authorize Batch `RELEASE` | **DENY** | **DENY** | **ALLOW** | API (`POST /batches/{id}/decisions`) |
| | Authorize Batch `SCRAP` | **DENY** | **DENY** | **ALLOW** | API (`POST /batches/{id}/decisions`) |
| **Inspections** | View Inspections | ALLOW | ALLOW | ALLOW | API (`GET /inspections`) |
| | Create Draft Inspection | ALLOW | ALLOW | ALLOW | API (`POST /inspections`) |
| | Add Items & Upload Images | ALLOW | DENY | ALLOW | API (`POST /inspections/{id}/items`) |
| | Submit Inspection for Review | ALLOW | DENY | ALLOW | API (`POST /inspections/{id}/submit`) |
| | Cancel Inspection | COND (Draft) | DENY | ALLOW | API (`POST /inspections/{id}/cancel`) |
| **Images & Evidence**| Upload Original Image | ALLOW | DENY | ALLOW | API (`POST /images/upload`) |
| | Mark Image as Superseded | ALLOW | DENY | ALLOW | API (`POST /images/{id}/supersede`) |
| | Hard Delete Evidence Image | **DENY** | **DENY** | **DENY** | **Database rule (Immutable)** |
| **Model Inference** | Trigger On-Demand Inference | ALLOW | DENY | ALLOW | API (`POST /images/{id}/infer`) |
| | Trigger Inference Retry | ALLOW | DENY | ALLOW | API (`POST /model-runs/{id}/retry`) |
| | Activate / Deploy Model Version | DENY | DENY | ALLOW | API (`POST /model-versions/{id}/activate`)|
| **Human Reviews** | Submit Initial Review (Good/Defect)| ALLOW | DENY | ALLOW | API (`POST /reviews`) |
| | Override ML Suggestion | ALLOW | DENY | ALLOW | API (`POST /reviews`) |
| | Raise Dispute / Flag Borderline | ALLOW | ALLOW | ALLOW | API (`POST /reviews/dispute`) |
| | Resolve Dispute / Final Adjudicate | **DENY** | **DENY** | **ALLOW** | API (`POST /reviews/{id}/adjudicate`) |
| **Defects** | Log Confirmed Defect | ALLOW | DENY | ALLOW | API (`POST /defects`) |
| | Update Defect Severity/Location | COND (Open) | DENY | ALLOW | API (`PATCH /defects/{id}`) |
| | Reopen Defect (Post-Reinspection)| ALLOW | DENY | ALLOW | API (`POST /defects/{id}/reopen`) |
| | Mark Defect `RESOLVED` | **DENY** | **DENY** | **ALLOW** | API (`POST /defects/{id}/resolve`) |
| **Corrective Actions**| Assign CAPA Remediation | DENY | ALLOW | ALLOW | API (`POST /corrective-actions`) |
| | Update Progress / Work Notes | DENY | OWN / ALLOW | ALLOW | API (`PATCH /corrective-actions/{id}`) |
| | Mark Remediation Completed | DENY | OWN / ALLOW | ALLOW | API (`POST /corrective-actions/{id}/complete`)|
| | Cancel Remediation Action | DENY | DENY | ALLOW | API (`POST /corrective-actions/{id}/cancel`)|
| **Reinspection** | Conduct Verification Inspection | ALLOW | DENY | ALLOW | API (`POST /reinspections`) |
| | Sign Off on Verified Defect Fix | ALLOW | DENY | ALLOW | API (`POST /reinspections/{id}/sign-off`)|
| **Dashboards** | View Operational Quality KPI | ALLOW | ALLOW | ALLOW | API (`GET /metrics/dashboard`) |
| | View Recurrence Radar | ALLOW | ALLOW | ALLOW | API (`GET /metrics/recurrence-radar`)|
| **Audit Logs** | View Audit Trail & System Events | DENY | DENY | ALLOW | API (`GET /audit-logs`) |
| **GenAI Assistant** | Natural Language Query Engine | ALLOW | ALLOW | ALLOW | API (`POST /genai/query`) |
| | GenAI Direct Database Mutation | **DENY** | **DENY** | **DENY** | **Engine architecture (Read-Only)** |

---

## 3. Grounded GenAI Permission Boundaries & Retrieval Filtering

The GenAI Assistant (`/api/v1/genai/query`) operates under strict permission boundaries:

1. **Read-Only Context Extraction:** GenAI execution pathways are architecturally isolated from database write transactions. It is impossible for a prompt injection or model hallucination to issue `INSERT`, `UPDATE`, or `DELETE` statements.
2. **Actor-Scoped Filtering:** When generating answers, the retrieval module filters the database context using the JWT claims of the calling user:
   - If an `INSPECTOR` queries the system: They receive summaries of inspections, images, and verified defects. Any confidential management audit trail or financial scrap valuations are excluded from the prompt context.
   - If a `SUPERVISOR` queries the system: They receive operational batch progress, open CAPA task statuses, and recurrence alerts.
   - If a `QUALITY_MANAGER` queries the system: Full access to root-cause histories, audit changes, and cross-batch release statuses is available.
3. **Traceable Grounding:** Every GenAI summary MUST explicitly return the primary keys of the database records that substantiate its claims in `retrieved_source_ids`.
4. **No Automated Authority:** Under no circumstances can GenAI authorize a batch release, close an open defect, or override a human reviewer's verdict.

---

## 4. Separation-of-Duties (SoD) Rules

### 4.1 Mandatory Rules (Strictly Enforced by Backend)
- **SoD-1 (Production vs. Quality Release):** A `SUPERVISOR` who creates a production batch CANNOT authorize that same batch for `RELEASE`. Only a `QUALITY_MANAGER` can execute release decisions.
- **SoD-2 (Remediation vs. Verification):** The user assigned to perform a physical corrective action (e.g., grinding or weld repair) CANNOT perform the subsequent verification `reinspection` on that same item. A qualified `INSPECTOR` or `QUALITY_MANAGER` must verify the fix.
- **SoD-3 (Audit Trail Immutability):** No user, regardless of role (including system administrators), is permitted to edit or delete rows in `audit_log` or `images`.

### 4.2 Optional / Configurable Rules (Tenant / Factory Config)
- **SoD-4 (Dual Review on Critical Defects):** When enabled, defects classified as `CRITICAL` require secondary concurrence from a `QUALITY_MANAGER` before a corrective action can be finalized.
- **SoD-5 (Inspector Self-Review Prohibition):** For high-precision aerospace/nuclear cast components, the technician who captures the images cannot be the sole reviewer who confirms the defect. (Disabled by default for standard industrial pump impeller staging).
