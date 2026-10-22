# CastTrace AI — REST API Contracts & Endpoint Specifications

**Document Version:** 1.0.0  
**Phase:** 1A (Architecture and Contracts)  
**API Prefix:** `/api/v1`  
**OpenAPI Specification:** 3.1.0 Compatible  
**Authentication Scheme:** Bearer JWT in `Authorization` header

---

## 1. Global API Standards

### 1.1 Error Envelope Specification

All non-2xx responses adhere strictly to the standardized error envelope format:

```json
{
  "error": {
    "code": "INVALID_STATE_TRANSITION",
    "message": "Cannot release batch with open or unresolved defects.",
    "details": {
      "batch_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "open_defect_count": 2
    },
    "request_id": "req-c89b21f3-e4d6-4e5a-8b1e-0d12e65a782b"
  }
}
```

#### Standard Error Codes & HTTP Status Mappings

| HTTP Code | Error Code Enum | Description / Common Cause |
| :--- | :--- | :--- |
| `400` | `BAD_REQUEST` | Malformed JSON, illegal query parameters, or missing required headers. |
| `401` | `UNAUTHENTICATED` | Missing, expired, or cryptographically invalid Bearer JWT. |
| `403` | `FORBIDDEN` | Authenticated user role lacks permission for the requested action. |
| `404` | `NOT_FOUND` | Target resource does not exist or has been soft-archived. |
| `409` | `CONFLICT` | Illegal state transition, concurrent modification, or duplicate unique key. |
| `413` | `PAYLOAD_TOO_LARGE`| Uploaded file exceeds the mandatory $10\text{ MB}$ size limit. |
| `415` | `UNSUPPORTED_MEDIA`| Uploaded image content fails magic-byte validation (only JPEG/PNG allowed). |
| `422` | `UNPROCESSABLE_ENTITY`| Pydantic validation failure or semantic domain constraint breach. |

---

### 1.2 Idempotency-Key Header Handling

Mutating endpoints that create mission-critical resources (`POST /inspections`, `POST /images/upload`, `POST /reviews`, `POST /defects`, `POST /batch-decisions`) support the HTTP header:

```http
Idempotency-Key: <UUIDv4 or client-generated unique string>
```

- **Cache Lifetime:** 24 hours in `idempotency_keys` table.
- **In-Flight Requests:** If a concurrent request arrives with the same `Idempotency-Key` while status is `IN_PROGRESS`, the backend returns HTTP `409 Conflict` with code `REQUEST_IN_PROGRESS`.
- **Completed Requests:** If the request succeeded previously, the backend returns the cached HTTP response code and payload with header `X-Cache-Lookup: HIT`, preventing duplicate records.

---

### 1.3 Photographic Evidence Upload Standards

- **Allowed Media Types:** `image/jpeg` (`.jpg`, `.jpeg`), `image/png` (`.png`).
- **Maximum File Size:** $10\text{ MB}$ ($10{,}485{,}760$ bytes).
- **Validation Pipeline:**
  1. Stream size verification (disconnect with `413 Payload Too Large` if stream exceeds 10 MB).
  2. Magic byte inspection:
     - JPEG: Starts with `FF D8 FF`
     - PNG: Starts with `89 50 4E 47 0D 0A 1A 0A`
  3. Header MIME-type vs. byte-content reconciliation.
- **Storage Strategy:** Files are saved to a non-public local directory using a generated UUID name (`storage/evidence/<uuid>.<ext>`). The database stores only the relative path and SHA-256 content checksum.

---

## 2. API Endpoint Groups

### 2.1 Authentication (`/auth`)

#### `POST /auth/login`
- **Purpose:** Authenticate user and issue access JWT.
- **Role:** Public.
- **Request Body:**
  ```json
  {
    "username": "inspector_chen",
    "password": "CorrectHorseBatteryStaple123!"
  }
  ```
- **Response `200 OK`:**
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in_seconds": 28800,
    "user": {
      "id": "u-42a1b94d-7612-4ebf-8181-a83a04a3bb01",
      "username": "inspector_chen",
      "full_name": "David Chen",
      "role": "INSPECTOR"
    }
  }
  ```

#### `GET /auth/me`
- **Purpose:** Retrieve caller identity, role, and active permissions.
- **Role:** Authenticated (`INSPECTOR`, `SUPERVISOR`, `QUALITY_MANAGER`).
- **Response `200 OK`:** Returns user object.

---

### 2.2 Products (`/products`)

#### `GET /products`
- **Purpose:** List registered casting products.
- **Role:** All authenticated roles.
- **Query Params:** `is_archived=false`, `limit=50`, `offset=0`.
- **Response `200 OK`:** Array of product objects.

#### `POST /products`
- **Purpose:** Register new cast product model.
- **Role:** `QUALITY_MANAGER` only.
- **Request Body:**
  ```json
  {
    "sku": "PUMP-IMP-CF8M-316",
    "name": "Closed Vane Impeller 316SS",
    "material": "CF8M Stainless Steel",
    "drawing_number": "DWG-2026-IMP-044",
    "nominal_weight_kg": 4.850,
    "specifications": {
      "outer_diameter_mm": 210.0,
      "bore_diameter_mm": 32.0,
      "vane_count": 6
    }
  }
  ```
- **Response `201 Created`:** Created product record.

---

### 2.3 Production Batches (`/batches`)

#### `GET /batches`
- **Purpose:** List batches with filtering.
- **Role:** All authenticated roles.
- **Query Params:** `status`, `product_id`, `from_date`, `to_date`.
- **Response `200 OK`:** Array of batch summary objects.

#### `POST /batches`
- **Purpose:** Initialize a new manufacturing casting batch.
- **Role:** `SUPERVISOR`, `QUALITY_MANAGER`.
- **Request Body:**
  ```json
  {
    "batch_number": "LOT-202610-098",
    "product_id": "prod-18b3d6-44ab",
    "manufacture_date": "2026-10-21",
    "heat_number": "HEAT-8841-A",
    "declared_quantity": 120,
    "notes": "Ladle pour sequence #3; mold sand temp 24C"
  }
  ```
- **Response `201 Created`:** Batch details with `status: "IN_PRODUCTION"`.

#### `POST /batches/{id}/hold`
- **Purpose:** Operational containment hold — immediately suspends batch shipping/movement on the shop floor.
- **Role:** `INSPECTOR`, `SUPERVISOR`, `QUALITY_MANAGER`.
- **Request Body:**
  ```json
  {
    "reason": "Cluster of suspected surface porosity identified during shift staging."
  }
  ```
- **Response `200 OK`:** Updated batch object with `status: "ON_HOLD"`.


#### `POST /batches/{id}/decisions`
- **Purpose:** Authorize official engineering governance decision (`RELEASE`, `HOLD`, `REJECT_SCRAP`, `CONCESSION_DEVIATION`) for a batch.
- **Role:** `QUALITY_MANAGER` only (`INSPECTOR` and `SUPERVISOR` receive `403 Forbidden`).
- **Headers:** `Idempotency-Key` (Recommended).
- **Core Decisions:** `RELEASE`, `HOLD`.
- **Optional Extensions:** `REJECT_SCRAP`, `CONCESSION_DEVIATION`.
- **Request Body:**
  ```json
  {
    "decision": "RELEASE",
    "reason": "100% inspection completed. All 3 reported porosity defects resolved and verified through reinspection.",
    "is_concession": false,
    "concession_justification": null,
    "conditions": null
  }
  ```
- **Validation & Policy Rules:**
  - Standard `RELEASE` requires all confirmed defects to be resolved.
  - If open defects exist, standard release returns `422 Unprocessable Entity` (`OPEN_DEFECTS_REQUIRE_CONCESSION`) *unless* the Quality Manager explicitly sets `is_concession: true` and supplies documented `concession_justification`. An open defect does not automatically block release if the Quality Manager deliberately grants an authorized concession.
- **Response `201 Created`:** Batch decision entity and updated batch status (`RELEASED`).


---

### 2.4 Inspections & Items (`/inspections`)

#### `POST /inspections`
- **Purpose:** Create new inspection staging session.
- **Role:** `INSPECTOR`, `SUPERVISOR`, `QUALITY_MANAGER`.
- **Request Body:**
  ```json
  {
    "batch_id": "batch-9812-45e",
    "stage": "FINAL_VISUAL",
    "sampling_plan": "AQL_LEVEL_II"
  }
  ```
- **Response `201 Created`:** Inspection entity with generated `inspection_number` and `status: "DRAFT"`.

#### `POST /inspections/{id}/items`
- **Purpose:** Register physical items to an inspection.
- **Role:** `INSPECTOR`, `QUALITY_MANAGER`.
- **Request Body:**
  ```json
  {
    "items": [
      { "item_identifier": "IMP-098-01", "cavity_number": 1 },
      { "item_identifier": "IMP-098-02", "cavity_number": 2 }
    ]
  }
  ```
- **Response `201 Created`:** List of created `inspection_items`.

#### `POST /inspections/{id}/submit`
- **Purpose:** Transition inspection from `DRAFT` to `SUBMITTED`.
- **Role:** `INSPECTOR`, `QUALITY_MANAGER`.
- **Validation:** Fails with `422` if zero items or zero non-superseded images exist.
- **Response `200 OK`:** Inspection with `status: "SUBMITTED"`.

---

### 2.5 Evidence Images & Inference (`/images`, `/model-runs`)

#### `POST /images/upload`
- **Purpose:** Upload photographic evidence for an item or batch sample.
- **Role:** `INSPECTOR`, `QUALITY_MANAGER`.
- **Headers:** `Content-Type: multipart/form-data`, `Idempotency-Key`.
- **Form Fields:**
  - `file`: Binary image data (JPEG or PNG, $\le 10\text{ MB}$).
  - `batch_id`: UUID.
  - `inspection_item_id`: UUID (Optional if `image_scope == "BATCH_SAMPLE"`).
  - `image_scope`: `"ITEM" | "SURFACE" | "BATCH_SAMPLE"`.
  - `surface_location`: String (e.g. `"VANE_SUCTION_SIDE"`).
  - `represented_item_count`: Integer ($\ge 1$, default $1$).
- **Response `201 Created`:** Image metadata record. Enqueues background ML inference.

#### `GET /images/{id}/content`
- **Purpose:** Stream the raw image binary.
- **Role:** All authenticated roles.
- **Response `200 OK`:** Binary stream with appropriate `Content-Type` and `Cache-Control: private, max-age=86400`.

#### `POST /images/{id}/infer`
- **Purpose:** Synchronously or asynchronously trigger ML model inference on an image.
- **Role:** `INSPECTOR`, `QUALITY_MANAGER`.
- **Response `202 Accepted`:**
  ```json
  {
    "model_run_id": "mr-512a-41bf",
    "status": "QUEUED",
    "attempt_number": 1
  }
  ```

#### `POST /model-runs/{id}/retry`
- **Purpose:** Trigger retry of a failed model run.
- **Role:** `INSPECTOR`, `QUALITY_MANAGER`.
- **Response `201 Created`:** New `model_runs` record with incremented `attempt_number`.

---

### 2.6 Human Reviews & Dispute Resolution (`/reviews`)

#### `POST /reviews`
- **Purpose:** Record human verification on an inspected item.
- **Role:** `INSPECTOR`, `QUALITY_MANAGER`.
- **Request Body:**
  ```json
  {
    "inspection_item_id": "item-9912-45e",
    "model_run_id": "mr-512a-41bf",
    "decision": "CONFIRMED_DEFECTIVE",
    "notes": "Verified surface shrink crack along leading edge of Vane #3.",
    "defect": {
      "category": "CRACK",
      "severity": "MAJOR",
      "surface_location": "VANE_PRESSURE_SIDE",
      "description": "5mm linear thermal tear near shroud junction."
    }
  }
  ```
- **Response `201 Created`:** Returns review record and created defect record.

#### `POST /reviews/{id}/dispute`
- **Purpose:** Escalate review verdict to Quality Management due to uncertainty or disagreement.
- **Role:** `INSPECTOR`, `SUPERVISOR`.
- **Request Body:**
  ```json
  {
    "notes": "Surface roughness appears within Ra 3.2 spec; optical reflection flagged as crack."
  }
  ```
- **Response `200 OK`:** Review status updated to `DISPUTED`.

#### `POST /reviews/{id}/adjudicate`
- **Purpose:** Final adjudication of a disputed review.
- **Role:** `QUALITY_MANAGER` only.
- **Request Body:**
  ```json
  {
    "decision": "CONFIRMED_GOOD",
    "notes": "Surface inspected with optical comparator; profile conforms to drawing tolerances."
  }
  ```
- **Response `200 OK`:** Review updated to final resolved verdict.

---

### 2.7 Defects & Remediation CAPA (`/defects`, `/corrective-actions`)

#### `GET /defects`
- **Purpose:** Filter confirmed defects.
- **Query Params:** `status`, `severity`, `category`, `batch_id`.
- **Response `200 OK`:** Array of defect records.

#### `POST /corrective-actions`
- **Purpose:** Assign CAPA remediation task for an open defect.
- **Role:** `SUPERVISOR`, `QUALITY_MANAGER`.
- **Request Body:**
  ```json
  {
    "defect_id": "def-1082-84a",
    "title": "Blend and polish surface shrink mark",
    "action_type": "REWORK",
    "description": "Blend shallow defect using ceramic rotary burr within drawing tolerance; verify minimum wall thickness.",
    "assigned_to": "u-machinist-771",
    "due_date": "2026-10-23"
  }
  ```
- **Response `201 Created`:** Action details with `status: "OPEN"`.

#### `POST /corrective-actions/{id}/complete`
- **Purpose:** Mark remediation work completed.
- **Role:** Assignee (`SUPERVISOR` or assigned user), `QUALITY_MANAGER`.
- **Request Body:**
  ```json
  {
    "completion_notes": "Blended with 120-grit wheel. Wall thickness measured at 4.12mm (min spec 3.8mm). Ready for reinspection."
  }
  ```
- **Response `200 OK`:** Updates action to `COMPLETED` and defect status to `PENDING_REINSPECTION`.

---

### 2.8 Reinspection (`/reinspections`)

#### `POST /reinspections`
- **Purpose:** Conduct follow-up quality inspection after remediation.
- **Role:** `INSPECTOR`, `QUALITY_MANAGER`.
- **Request Body:**
  ```json
  {
    "defect_id": "def-1082-84a",
    "corrective_action_id": "capa-302-881",
    "outcome": "DEFECT_RESOLVED",
    "notes": "Visual and liquid penetrant test indicates zero residual indication.",
    "followup_inspection_id": "insp-901-22a"
  }
  ```
- **Response `201 Created`:**
  - If outcome is `DEFECT_RESOLVED`: Defect transitions to `RESOLVED`.
  - If outcome is `DEFECT_RECURRED_REOPENED`: Defect transitions to `REOPENED`.

---

### 2.9 Operational Metrics & Recurrence Radar (`/metrics`)

#### `GET /metrics/dashboard`
- **Purpose:** Retrieve real-time operational quality KPIs.
- **Role:** All authenticated roles.
- **Query Params:** `batch_id`, `product_id`, `start_date`, `end_date`.
- **Response `200 OK`:**
  ```json
  {
    "scope": { "batch_id": "batch-9812-45e", "product_id": null },
    "metrics": {
      "ai_flag_rate": { "status": "AVAILABLE", "value": 0.0833, "numerator": 10, "denominator": 120 },
      "confirmed_defect_rate": { "status": "AVAILABLE", "value": 0.0417, "numerator": 5, "denominator": 120 },
      "sample_coverage": { "status": "AVAILABLE", "value": 1.0000, "numerator": 120, "denominator": 120 },
      "ai_human_disagreement_rate": { "status": "AVAILABLE", "value": 0.0417, "numerator": 5, "denominator": 120 },
      "open_corrective_actions": { "status": "AVAILABLE", "value": 2 },
      "overdue_corrective_actions": { "status": "AVAILABLE", "value": 0 },
      "verified_fix_rate": { "status": "AVAILABLE", "value": 100.0, "numerator": 3, "denominator": 3 }
    }
  }
  ```

#### `GET /metrics/recurrence-radar`
- **Purpose:** Retrieve defect category recurrence trends normalized across physical item inspection volume.
- **Role:** All authenticated roles.
- **Query Params:** `product_id` (Required), `limit_batches=10`.
- **Response `200 OK`:**
  ```json
  {
    "product_id": "prod-18b3d6-44ab",
    "analysis_timestamp": "2026-10-21T10:25:00Z",
    "batches_evaluated": 5,
    "total_physical_items_inspected": 600,
    "recurrence_clusters": [
      {
        "category": "SHRINKAGE_POROSITY",
        "affected_batches": ["LOT-202610-095", "LOT-202610-098"],
        "distinct_items_affected": 14,
        "item_recurrence_rate": 0.0233,
        "trend_direction": "INCREASING",
        "primary_surface_locations": ["HUB_BORE", "VANE_ROOT"],
        "open_capa_count": 2
      }
    ]
  }
  ```

---

### 2.10 Evidence-Grounded GenAI Assistant (`/genai`)

#### `POST /genai/query`
- **Purpose:** Ask natural language questions grounded exclusively in stored database records.
- **Role:** All authenticated roles (Response pruned to caller scope).
- **Request Body:**
  ```json
  {
    "prompt": "What defects were confirmed in batch LOT-202610-098 and what is the status of their corrective actions?",
    "target_batch_id": "batch-9812-45e"
  }
  ```
- **Response `200 OK`:**
  ```json
  {
    "answer": "Batch LOT-202610-098 had 2 confirmed defects: one shrinkage crack on item IMP-098-01 (DEF-20261021-0001) and one porosity pocket on item IMP-098-04 (DEF-20261021-0002). Both defects have completed corrective actions and verified reinspections. The batch was officially released by Quality Management on 2026-10-21.",
    "is_fallback": false,
    "model_provider": "gemini",
    "retrieved_source_ids": [
      { "entity": "batches", "id": "batch-9812-45e", "reference": "LOT-202610-098" },
      { "entity": "defects", "id": "def-1082-84a", "reference": "DEF-20261021-0001" },
      { "entity": "defects", "id": "def-1082-84b", "reference": "DEF-20261021-0002" },
      { "entity": "batch_decisions", "id": "bd-991-01a", "reference": "RELEASE" }
    ],
    "disclaimer": "AI response grounded in database records. GenAI has no authority to alter quality or release status."
  }
  ```
- **Safeguard Behaviors:**
  - If queried about an unknown batch: Returns grounded explanation that no records exist; does not fabricate lot numbers.
  - If prompted with a false premise (e.g., "Why did AI release batch LOT-098?"): Refutes the premise, explaining that AI has no release authority and citing the actual human decision maker.
