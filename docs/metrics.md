# CastTrace AI — Quality Metrics & Mathematical Specifications

**Document Version:** 1.0.0  
**Phase:** 1A (Architecture and Contracts)  
**Execution Target:** Deterministic Backend SQL Queries / SQLAlchemy 2.0 Aggregations  
**Guiding Axiom:** Physical items are the unit of manufacturing quality. Photographic evidence must never be counted as physical items in quality denominators.

---

## 1. Core Aggregation Rules & Design Standards

1. **Item-Level Aggregation for Multi-Image Items:** A single physical cast impeller (`inspection_items`) may have multiple photographs associated with it (e.g., suction eye view, hub bore view, rear shroud view).
   - **AI Flag Rule:** An item is classified as `AI_FLAGGED` if and only if **at least one** current, non-superseded image associated with the item has a latest successful model run predicting `DEFECTIVE`. The item is counted **exactly once** in the numerator.
   - **Human Confirmed Rule:** An item is classified as `HUMAN_CONFIRMED_DEFECTIVE` if human review confirmed one or more defects on the item. The item is counted **exactly once** in the numerator, regardless of how many individual defect features (e.g. 2 cracks and 1 blowhole) were flagged on that item.
2. **Superseded Evidence Filtering:** Any image with `is_superseded = TRUE` is strictly excluded from active operational metrics.
3. **Archived Record Exclusion:** Batches and products with `is_archived = TRUE` or status `ARCHIVED` are filtered out of active operational KPI dashboards (available only in historical retrospective filters).
4. **Zero-Division & Insufficient Data Handling:** Whenever a denominator evaluates to $0$, the system must **never** return `0.0%` (which misleadingly indicates zero defects). It must return an explicit payload:
   ```json
   {
     "status": "INSUFFICIENT_DATA",
     "value": null,
     "numerator": 0,
     "denominator": 0,
     "message": "No eligible physical items found for this evaluation scope."
   }
   ```
5. **No Sample Extrapolation Overclaims:** Sample coverage indicates what percentage of a batch was staged for visual inspection. It must **never** be presented as mathematical proof that uninspected parts are defect-free.

---

## 2. Metric Specifications

### 2.1 AI Flag Rate (Item-Level)

*Definition:* The proportion of inspected physical items flagged as potentially defective by the machine learning classifier.

$$\text{AI Flag Rate} = \frac{\text{Count of distinct physical items with } \ge 1 \text{ current image predicted } \text{"DEFECTIVE"}}{\text{Count of distinct physical items with } \ge 1 \text{ current image with a successful ML run}}$$

- **Numerator:**
  ```sql
  COUNT(DISTINCT ii.id) 
  FROM inspection_items ii
  JOIN images img ON img.inspection_item_id = ii.id AND img.is_superseded = FALSE
  JOIN model_runs mr ON mr.image_id = img.id
  WHERE mr.status = 'SUCCEEDED' 
    AND mr.predicted_label = 'DEFECTIVE'
    AND mr.id = (
        SELECT id FROM model_runs 
        WHERE image_id = img.id AND status = 'SUCCEEDED' 
        ORDER BY attempt_number DESC LIMIT 1
    )
    AND (:batch_id IS NULL OR img.batch_id = :batch_id)
  ```
- **Denominator:**
  ```sql
  COUNT(DISTINCT ii.id) 
  FROM inspection_items ii
  JOIN images img ON img.inspection_item_id = ii.id AND img.is_superseded = FALSE
  JOIN model_runs mr ON mr.image_id = img.id
  WHERE mr.status = 'SUCCEEDED'
    AND (:batch_id IS NULL OR img.batch_id = :batch_id)
  ```
- **Edge Cases & Filters:**
  - Items where ML inference failed or is pending are excluded from the denominator.
  - If denominator $= 0$, return `INSUFFICIENT_DATA`.

---

### 2.2 Confirmed Defect Rate (Item-Level)

*Definition:* The proportion of reviewed physical items confirmed to possess defects following human verification.

$$\text{Confirmed Defect Rate} = \frac{\text{Count of distinct physical items with } \ge 1 \text{ human-confirmed defect}}{\text{Count of distinct physical items with completed reviews}}$$

- **Numerator:**
  ```sql
  COUNT(DISTINCT ii.id)
  FROM inspection_items ii
  JOIN reviews r ON r.inspection_item_id = ii.id
  WHERE r.decision = 'CONFIRMED_DEFECTIVE'
    AND (:batch_id IS NULL OR ii.inspection_id IN (SELECT id FROM inspections WHERE batch_id = :batch_id))
  ```
- **Denominator:**
  ```sql
  COUNT(DISTINCT ii.id)
  FROM inspection_items ii
  JOIN reviews r ON r.inspection_item_id = ii.id
  WHERE r.decision IN ('CONFIRMED_GOOD', 'CONFIRMED_DEFECTIVE')
    AND (:batch_id IS NULL OR ii.inspection_id IN (SELECT id FROM inspections WHERE batch_id = :batch_id))
  ```
- **Edge Cases & Filters:**
  - Items with `DISPUTED` or `REQUEST_ADDITIONAL_EVIDENCE` review status are excluded until adjudicated.
  - Multiple defects on a single item (e.g. 1 crack and 1 porosity pocket) increment the numerator by **one**.

---

### 2.3 Inspection / Sample Coverage

*Definition:* The fraction of declared production batch quantity physically staged and evaluated under the inspection protocol.

$$\text{Inspection Coverage} = \frac{\text{Total distinct physical items evaluated in batch}}{\text{Declared batch production quantity}}$$

- **Numerator:**
  ```sql
  COALESCE(SUM(item_count), 0) FROM (
      -- Distinct items inspected via ITEM or SURFACE scope
      SELECT COUNT(DISTINCT ii.id) AS item_count
      FROM inspection_items ii
      JOIN inspections insp ON insp.id = ii.inspection_id
      WHERE insp.batch_id = :batch_id AND insp.status != 'CANCELLED'
      UNION ALL
      -- Batch sample photographs accounting for represented items
      SELECT COALESCE(SUM(img.represented_item_count), 0) AS item_count
      FROM images img
      WHERE img.batch_id = :batch_id 
        AND img.image_scope = 'BATCH_SAMPLE' 
        AND img.is_superseded = FALSE
  )
  ```
- **Denominator:**
  ```sql
  SELECT declared_quantity FROM batches WHERE id = :batch_id
  ```
- **Edge Cases & Clarifications:**
  - For 100% inspection plans, coverage approaches $1.0$ ($100\%$).
  - For statistical sampling (AQL Level II), coverage may be $8\%\text{--}15\%$. **UI Disclaimer:** "Sample coverage indicates inspected portion of lot; it does not constitute 100% verification of uninspected parts."

---

### 2.4 AI-Human Disagreement Rate

*Definition:* The rate at which human reviewers overturn the suggestion produced by the ML classifier.

$$\text{Disagreement Rate} = \frac{\text{Count of distinct items where human review contradicted latest ML prediction}}{\text{Count of distinct items with both a completed ML prediction and completed human review}}$$

- **Numerator:**
  ```sql
  COUNT(DISTINCT ii.id)
  FROM inspection_items ii
  JOIN reviews r ON r.inspection_item_id = ii.id
  JOIN images img ON img.inspection_item_id = ii.id AND img.is_superseded = FALSE
  JOIN model_runs mr ON mr.image_id = img.id
  WHERE mr.status = 'SUCCEEDED'
    AND r.decision IN ('CONFIRMED_GOOD', 'CONFIRMED_DEFECTIVE')
    AND (
      (r.decision = 'CONFIRMED_GOOD' AND mr.predicted_label = 'DEFECTIVE') OR
      (r.decision = 'CONFIRMED_DEFECTIVE' AND mr.predicted_label = 'GOOD')
    )
    AND (:batch_id IS NULL OR img.batch_id = :batch_id)
  ```
- **Denominator:**
  ```sql
  COUNT(DISTINCT ii.id)
  FROM inspection_items ii
  JOIN reviews r ON r.inspection_item_id = ii.id
  JOIN images img ON img.inspection_item_id = ii.id AND img.is_superseded = FALSE
  JOIN model_runs mr ON mr.image_id = img.id
  WHERE mr.status = 'SUCCEEDED'
    AND r.decision IN ('CONFIRMED_GOOD', 'CONFIRMED_DEFECTIVE')
    AND (:batch_id IS NULL OR img.batch_id = :batch_id)
  ```
- **Interpretation:**
  - High False Positive disagreement (AI says Defective, Human says Good) indicates over-sensitive optical thresholds or surface reflections.
  - High False Negative disagreement (AI says Good, Human says Defective) flags potential model blind spots.

---

### 2.5 Open Corrective Actions

*Definition:* The absolute count of CAPA remediation tasks currently requiring completion or investigation.

$$\text{Open Actions} = \sum [\text{status} \in \{\text{"OPEN"}, \text{"IN_PROGRESS"}\}]$$

- **Query:**
  ```sql
  SELECT COUNT(id) 
  FROM corrective_actions 
  WHERE status IN ('OPEN', 'IN_PROGRESS')
    AND (:assigned_to IS NULL OR assigned_to = :assigned_to)
  ```

---

### 2.6 Overdue Corrective Actions

*Definition:* The count of uncompleted corrective actions whose scheduled due date has elapsed.

$$\text{Overdue Actions} = \sum [\text{status} \in \{\text{"OPEN"}, \text{"IN_PROGRESS"}\} \land \text{due\_date} < \text{CURRENT\_DATE}]$$

- **Query:**
  ```sql
  SELECT COUNT(id) 
  FROM corrective_actions 
  WHERE status IN ('OPEN', 'IN_PROGRESS')
    AND due_date < CURRENT_DATE
    AND (:assigned_to IS NULL OR assigned_to = :assigned_to)
  ```

---

### 2.7 Recurrence Trend (Recurrence Radar Core)

*Definition:* The recurrence frequency of specific human-confirmed defect categories across batches for the same product, normalized by the physical inspection volume.

$$\text{Defect Category Recurrence Rate}(c, p, b) = \frac{\text{Distinct items exhibiting defect category } c \text{ on product } p \text{ in batch } b}{\text{Total distinct physical items inspected for product } p \text{ in batch } b}$$

- **Query Specification:**
  ```sql
  SELECT 
      b.batch_number,
      b.manufacture_date,
      d.category,
      COUNT(DISTINCT ii.id) AS defective_items_count,
      total_items.inspected_count,
      ROUND(CAST(COUNT(DISTINCT ii.id) AS FLOAT) / total_items.inspected_count * 100, 2) AS recurrence_percentage
  FROM defects d
  JOIN inspection_items ii ON ii.id = d.inspection_item_id
  JOIN inspections insp ON insp.id = ii.inspection_id
  JOIN batches b ON b.id = insp.batch_id
  JOIN (
      SELECT insp_sub.batch_id, COUNT(DISTINCT ii_sub.id) AS inspected_count
      FROM inspections insp_sub
      JOIN inspection_items ii_sub ON ii_sub.inspection_id = insp_sub.id
      WHERE insp_sub.status = 'COMPLETED'
      GROUP BY insp_sub.batch_id
  ) total_items ON total_items.batch_id = b.id
  WHERE b.product_id = :product_id
    AND total_items.inspected_count > 0
  GROUP BY b.batch_number, b.manufacture_date, d.category, total_items.inspected_count
  ORDER BY b.manufacture_date ASC;
  ```
- **Engineering Principle:** Recurrence Radar identifies recurring defect patterns over time. **Critical Rule:** The system flags correlation and recurrence patterns across shifts or tooling; it **never asserts a single root cause** without engineering metallographic investigation.

---

### 2.8 Verified-Fix Rate (Post-Remediation Reinspection)

*Definition:* The percentage of corrective actions where follow-up physical reinspection confirmed that the defect was successfully resolved.

$$\text{Verified-Fix Rate} = \frac{\text{Count of reinspections resulting in } \text{"DEFECT_RESOLVED"}}{\text{Total completed reinspections}} \times 100$$

- **Query:**
  ```sql
  SELECT 
      COUNT(CASE WHEN outcome = 'DEFECT_RESOLVED' THEN 1 END) AS resolved_count,
      COUNT(id) AS total_reinspected_count,
      CASE 
          WHEN COUNT(id) = 0 THEN NULL
          ELSE ROUND(CAST(COUNT(CASE WHEN outcome = 'DEFECT_RESOLVED' THEN 1 END) AS FLOAT) / COUNT(id) * 100, 2)
      END AS verified_fix_rate
  FROM reinspections;
  ```
- **Edge Cases:** If `total_reinspected_count == 0`, returns `INSUFFICIENT_DATA`.

---

## 3. Batch Decision Snapshot Metrics & Immutability Specifications

### 3.1 Distinct Physical Item Counting Axioms
In compliance with Problem Statement 1 and manufacturing quality standards:
1. **Unit of Measure:** Physical casting parts (`inspection_items`) are the sole unit of manufacturing quality. Photographic evidence images (`images`) are evidentiary attachments and must never be counted as physical parts.
2. **Anti-Inflation Rule:** An impeller with 3 photographs (e.g., suction eye, hub bore, and shroud rim) increments `total_items` by **one**, `inspected_items` by **one**, and `reviewed_items` by **one**.
3. **Join Deduplication:** All count aggregates use `COUNT(DISTINCT ...)` over the primary key of the respective entity to avoid inflation from many-to-many or multi-image joins.

### 3.2 Decision Snapshot Field Definitions
Every finalized batch decision records an immutable snapshot containing:

| Field Name | Type | Mathematical / SQL Definition | Business Interpretation |
| :--- | :---: | :--- | :--- |
| `total_items` | `int` | `COUNT(DISTINCT ii.id)` across all batch inspections | Total distinct physical impeller castings registered in the batch inspections. |
| `inspected_items` | `int` | `COUNT(DISTINCT ii.id)` with $\ge 1$ non-superseded image | Physical impellers with photographic evidence captured. |
| `reviewed_items` | `int` | `COUNT(DISTINCT ii.id)` with $\ge 1$ human review recorded | Physical impellers that have completed human review sign-off. |
| `pending_inspection_items` | `int` | `total_items - inspected_items` | Registered parts awaiting evidence photo capture. |
| `pending_review_items` | `int` | `total_items - reviewed_items` | Registered parts awaiting human inspector review. |
| `unresolved_defects` | `int` | `COUNT(DISTINCT d.id)` with status $\in \{\text{OPEN}, \text{ACTION\_ASSIGNED}, \text{IN\_PROGRESS}, \text{PENDING\_REINSPECTION}, \text{REOPENED}\}$ | Active defects preventing standard release. |
| `resolved_defects` | `int` | `COUNT(DISTINCT d.id)` with status $\text{RESOLVED}$ | Defects successfully remediated and verified through reinspection. |
| `defects_requiring_reinspection`| `int` | `COUNT(DISTINCT d.id)` with status $\text{PENDING\_REINSPECTION}$ | Defects with completed CAPA awaiting follow-up inspection. |
| `capa_requiring_verification` | `int` | `COUNT(DISTINCT ca.id)` with `verification_status = 'PENDING'` | Corrective actions completed by technician awaiting independent QM verification. |
| `capa_verified` | `int` | `COUNT(DISTINCT ca.id)` with `verification_status = 'VERIFIED'` | Corrective actions independently approved by Quality Manager. |
| `pending_or_failed_reinspections`| `int` | `COUNT(DISTINCT r.id)` with `outcome = 'DEFECT_RECURRED_REOPENED'` | Reinspections that failed to clear the non-conformance. |

### 3.3 Snapshot Immutability Guarantee
- **Point-in-Time Persistence:** The decision snapshot is serialized and stored as a static JSON document in `batch_decisions.snapshot` within the same database transaction that finalizes the decision.
- **Historical Freeze:** Subsequent additions of evidence, new inspections, defect logs on other lots, or product specification revisions **never** mutate historical decision snapshots.
- **Auditable Recalculation vs. Historical Record:** While the live `/release-gate` endpoint evaluates the dynamic database state in real-time, querying `/batches/{id}/decisions` always returns the frozen state as it existed at the exact second the Quality Manager authorized the decision.
