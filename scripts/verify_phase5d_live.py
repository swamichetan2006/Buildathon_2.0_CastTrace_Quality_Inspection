"""Phase 5D Live Application & Integration Verification Script.

Tests the live running frontend (port 5173), backend (port 8001), and ML worker:
1. Frontend & Dev Proxy Serving (http://localhost:5173)
2. Workflow A: Authentication, RBAC, and Session Security
3. Workflow B: Product Catalog & Batch Management (Operational Hold)
4. Workflow C: Inspection Creation, Item Registration, Real Evidence Hashing
5. Workflow D: Real ML Inference Worker Execution (ResNet-18 forward pass on real dataset), Human Review & Snapshots
6. Workflow E: Controlled Defect Tracking, CAPA Lifecycle, Four-Eyes Verification, Reinspection
7. Workflow F: Release Gate Blocker Evaluation, Official QM Decision, Immutable Snapshots, 409 Conflict
"""

import os
import sys
import time
import uuid
import hashlib
from datetime import date, timedelta
import httpx

FRONTEND_URL = "http://localhost:5173"
BACKEND_URL = "http://127.0.0.1:8001"
API_V1 = f"{BACKEND_URL}/api/v1"
PROXY_API_V1 = f"{FRONTEND_URL}/api/v1"

# Locate real casting images dynamically from dataset
OK_DIR = os.path.join("data", "raw", "casting", "casting_512x512", "casting_512x512", "ok_front")
DEF_DIR = os.path.join("data", "raw", "casting", "casting_512x512", "casting_512x512", "def_front")

def get_sample_images():
    if os.path.exists(OK_DIR) and os.path.exists(DEF_DIR):
        ok_files = [f for f in os.listdir(OK_DIR) if f.lower().endswith(('.jpeg', '.jpg'))]
        def_files = [f for f in os.listdir(DEF_DIR) if f.lower().endswith(('.jpeg', '.jpg'))]
        if ok_files and def_files:
            return os.path.join(OK_DIR, ok_files[0]), os.path.join(DEF_DIR, def_files[0])
    return None, None

results = []

def record_result(section: str, test_name: str, passed: bool, details: str = ""):
    status_str = "PASS" if passed else "FAIL"
    results.append({"section": section, "test": test_name, "status": status_str, "details": details})
    print(f"[{status_str}] {section} -> {test_name}: {details}")
    if not passed:
        print(f"  FAILED ASSERTION: {test_name}")


def get_error_code(response: httpx.Response) -> str:
    try:
        body = response.json()
        if "error" in body and isinstance(body["error"], dict):
            return body["error"].get("code", "")
        return body.get("code", "")
    except Exception:
        return ""


def main():
    print("=" * 80)
    print("CASTTRACE AI — PHASE 5D LIVE APPLICATION VERIFICATION")
    print(f"Backend Target:  {BACKEND_URL}")
    print(f"Frontend Target: {FRONTEND_URL}")
    print("=" * 80)

    client = httpx.Client(timeout=15.0)

    # -------------------------------------------------------------------------
    # 1. FRONTEND SERVER & PROXY INTEGRATION
    # -------------------------------------------------------------------------
    print("\n--- 1. Testing Frontend Dev Server & Reverse Proxy ---")
    try:
        r_fe = client.get(f"{FRONTEND_URL}/")
        passed = (r_fe.status_code == 200 and '<div id="root">' in r_fe.text and "CastTrace" in r_fe.text)
        record_result("Frontend Server", "Serve SPA HTML", passed, f"Status {r_fe.status_code}, contains #root and CastTrace title")
    except Exception as e:
        record_result("Frontend Server", "Serve SPA HTML", False, str(e))

    try:
        r_health_proxy = client.get(f"{FRONTEND_URL}/health")
        data = r_health_proxy.json()
        passed = (r_health_proxy.status_code == 200 and data.get("status") == "healthy" and data.get("database") == "connected")
        record_result("Frontend Server", "Proxy /health to Backend", passed, f"Proxied successfully: db={data.get('database')}, latency={data.get('latency_ms')}ms")
    except Exception as e:
        record_result("Frontend Server", "Proxy /health to Backend", False, str(e))

    try:
        r_auth_unauth = client.get(f"{PROXY_API_V1}/auth/me")
        passed = (r_auth_unauth.status_code == 401)
        record_result("Frontend Server", "Proxy 401 Unauthorized Handling", passed, f"Status {r_auth_unauth.status_code} as expected")
    except Exception as e:
        record_result("Frontend Server", "Proxy 401 Unauthorized Handling", False, str(e))

    # -------------------------------------------------------------------------
    # 2. WORKFLOW A: AUTHENTICATION AND ROLES
    # -------------------------------------------------------------------------
    print("\n--- 2. Testing Workflow A: Authentication & RBAC ---")
    tokens = {}
    users_to_login = [
        ("inspector_chen", "Password123!", "INSPECTOR"),
        ("supervisor_torres", "Password123!", "SUPERVISOR"),
        ("qm_reynolds", "Password123!", "QUALITY_MANAGER"),
    ]

    for username, password, expected_role in users_to_login:
        try:
            res = client.post(f"{API_V1}/auth/login", json={"username": username, "password": password})
            if res.status_code == 200:
                body = res.json()
                token = body["access_token"]
                role = body["user"]["role"]
                tokens[expected_role] = token
                passed = (role == expected_role and bool(token))
                record_result("Auth & Roles", f"Login {username} ({expected_role})", passed, f"Token received, role={role}")
            else:
                record_result("Auth & Roles", f"Login {username} ({expected_role})", False, f"Status {res.status_code}: {res.text}")
        except Exception as e:
            record_result("Auth & Roles", f"Login {username} ({expected_role})", False, str(e))

    # Test invalid login (HTTP 401)
    try:
        bad_res = client.post(f"{API_V1}/auth/login", json={"username": "inspector_chen", "password": "WrongPassword!"})
        err_code = get_error_code(bad_res)
        passed = (bad_res.status_code == 401 and err_code == "INVALID_CREDENTIALS")
        record_result("Auth & Roles", "Reject Invalid Credentials", passed, f"Status {bad_res.status_code}, code={err_code}")
    except Exception as e:
        record_result("Auth & Roles", "Reject Invalid Credentials", False, str(e))

    # Test session check /auth/me for QM
    qm_headers = {"Authorization": f"Bearer {tokens['QUALITY_MANAGER']}"}
    sup_headers = {"Authorization": f"Bearer {tokens['SUPERVISOR']}"}
    insp_headers = {"Authorization": f"Bearer {tokens['INSPECTOR']}"}

    try:
        me_res = client.get(f"{API_V1}/auth/me", headers=qm_headers)
        passed = (me_res.status_code == 200 and me_res.json()["role"] == "QUALITY_MANAGER")
        record_result("Auth & Roles", "Session Restoration /auth/me", passed, f"User {me_res.json()['username']} authenticated")
    except Exception as e:
        record_result("Auth & Roles", "Session Restoration /auth/me", False, str(e))

    # RBAC Enforcement: Inspector & Supervisor attempt Quality Manager-only endpoint
    try:
        dummy_id = str(uuid.uuid4())
        insp_dec_res = client.post(
            f"{API_V1}/batches/{dummy_id}/decisions",
            headers=insp_headers,
            json={"decision": "RELEASE", "reason": "Inspector unauthorized bypass attempt"},
        )
        passed = (insp_dec_res.status_code == 403)
        record_result("Auth & Roles", "Block Inspector from QM Decision", passed, f"Status {insp_dec_res.status_code} Forbidden")
    except Exception as e:
        record_result("Auth & Roles", "Block Inspector from QM Decision", False, str(e))

    try:
        sup_dec_res = client.post(
            f"{API_V1}/batches/{dummy_id}/decisions",
            headers=sup_headers,
            json={"decision": "RELEASE", "reason": "Supervisor unauthorized bypass attempt"},
        )
        passed = (sup_dec_res.status_code == 403)
        record_result("Auth & Roles", "Block Supervisor from QM Decision", passed, f"Status {sup_dec_res.status_code} Forbidden")
    except Exception as e:
        record_result("Auth & Roles", "Block Supervisor from QM Decision", False, str(e))

    # -------------------------------------------------------------------------
    # 3. WORKFLOW B: PRODUCT AND BATCH MANAGEMENT
    # -------------------------------------------------------------------------
    print("\n--- 3. Testing Workflow B: Product and Batch Management ---")
    product_id = None
    try:
        prod_list_res = client.get(f"{API_V1}/products", headers=sup_headers)
        products = prod_list_res.json()
        if products and len(products) > 0:
            product_id = products[0]["id"]
            record_result("Product & Batch", "List Products", True, f"Found existing product {products[0]['sku']}")
        else:
            sku_name = f"PUMP-IMP-5D-{uuid.uuid4().hex[:6]}"
            new_prod_res = client.post(
                f"{API_V1}/products",
                headers=qm_headers,
                json={
                    "sku": sku_name,
                    "name": "Cast Stainless Impeller 5D",
                    "material": "ASTM A743 CF8M",
                    "drawing_number": "DWG-5D-VAL-001",
                    "nominal_weight_kg": 18.5,
                },
            )
            passed = (new_prod_res.status_code == 201)
            product_id = new_prod_res.json()["id"]
            record_result("Product & Batch", "Create Product Catalog Entry", passed, f"Created {sku_name} (ID: {product_id})")
    except Exception as e:
        record_result("Product & Batch", "Product Operations", False, str(e))

    batch_id = None
    batch_num = f"LOT-5D-VAL-{uuid.uuid4().hex[:6]}"
    try:
        batch_res = client.post(
            f"{API_V1}/batches",
            headers=sup_headers,
            json={
                "batch_number": batch_num,
                "product_id": product_id,
                "manufacture_date": str(date.today()),
                "heat_number": "HEAT-CF8M-991",
                "declared_quantity": 2,
                "notes": "Phase 5D verification test lot",
            },
        )
        passed = (batch_res.status_code == 201)
        batch_id = batch_res.json()["id"]
        status_init = batch_res.json()["status"]
        record_result("Product & Batch", "Create Production Batch", passed, f"Created {batch_num} with status={status_init}")
    except Exception as e:
        record_result("Product & Batch", "Create Production Batch", False, str(e))

    try:
        hold_res = client.post(
            f"{API_V1}/batches/{batch_id}/hold",
            headers=sup_headers,
            json={"reason": "Operational containment hold for verification testing"},
        )
        passed = (hold_res.status_code == 200 and hold_res.json()["status"] == "ON_HOLD")
        record_result("Product & Batch", "Operational Containment Hold", passed, f"Status updated to ON_HOLD")
    except Exception as e:
        record_result("Product & Batch", "Operational Containment Hold", False, str(e))

    # -------------------------------------------------------------------------
    # 4. WORKFLOW C: INSPECTION AND EVIDENCE
    # -------------------------------------------------------------------------
    print("\n--- 4. Testing Workflow C: Inspection & Photographic Evidence ---")
    insp_id = None
    item1_id = None
    item2_id = None
    try:
        insp_create_res = client.post(
            f"{API_V1}/inspections",
            headers=insp_headers,
            json={
                "batch_id": batch_id,
                "stage": "FINAL_VISUAL",
                "sampling_plan": "100_PERCENT",
            },
        )
        passed = (insp_create_res.status_code == 201)
        insp_id = insp_create_res.json()["id"]
        insp_num = insp_create_res.json()["inspection_number"]
        record_result("Inspection & Evidence", "Create Inspection Session", passed, f"Session {insp_num} (ID: {insp_id})")
    except Exception as e:
        record_result("Inspection & Evidence", "Create Inspection Session", False, str(e))

    try:
        items_res = client.post(
            f"{API_V1}/inspections/{insp_id}/items",
            headers=insp_headers,
            json={
                "items": [
                    {"item_identifier": "SN-5D-IMP-001", "cavity_number": 1},
                    {"item_identifier": "SN-5D-IMP-002", "cavity_number": 2},
                ]
            },
        )
        passed = (items_res.status_code == 201 and len(items_res.json()) == 2)
        items_data = items_res.json()
        item1_id = items_data[0]["id"]
        item2_id = items_data[1]["id"]
        record_result("Inspection & Evidence", "Register 2 Physical Items", passed, f"Registered SN-5D-IMP-001 & SN-5D-IMP-002")
    except Exception as e:
        record_result("Inspection & Evidence", "Register 2 Physical Items", False, str(e))

    # Multi-image upload using real dataset photographs
    img1_id = None
    img1_hash = None
    img2_id = None
    img3_id = None
    try:
        ok_sample, def_sample = get_sample_images()
        if not ok_sample or not def_sample:
            raise FileNotFoundError("Could not find sample casting images in dataset directory.")
        with open(ok_sample, "rb") as f:
            photo1_bytes = f.read()
        with open(def_sample, "rb") as f:
            photo2_bytes = f.read()

        # Image 1 (Item 1, primary photo, conforming casting)
        r_img1 = client.post(
            f"{API_V1}/images/upload",
            headers=insp_headers,
            data={"batch_id": batch_id, "inspection_item_id": item1_id, "image_scope": "ITEM"},
            files={"file": ("cast_ok_0_1.jpeg", photo1_bytes, "image/jpeg")},
        )
        img1_data = r_img1.json()
        img1_id = img1_data["id"]
        img1_hash = img1_data["sha256_hash"]
        expected_hash1 = hashlib.sha256(photo1_bytes).hexdigest()

        # Image 2 (Item 1, secondary surface photo - checks multiple images per physical item)
        r_img1b = client.post(
            f"{API_V1}/images/upload",
            headers=insp_headers,
            data={"batch_id": batch_id, "inspection_item_id": item1_id, "image_scope": "SURFACE", "surface_location": "SHROUD"},
            files={"file": ("cast_ok_0_1_surface.jpeg", photo1_bytes, "image/jpeg")},
        )
        img2_id = r_img1b.json()["id"]

        # Image 3 (Item 2, defective casting photo)
        r_img2 = client.post(
            f"{API_V1}/images/upload",
            headers=insp_headers,
            data={"batch_id": batch_id, "inspection_item_id": item2_id, "image_scope": "ITEM"},
            files={"file": ("cast_def_0_100.jpeg", photo2_bytes, "image/jpeg")},
        )
        img3_id = r_img2.json()["id"]

        passed = (
            r_img1.status_code == 201
            and r_img1b.status_code == 201
            and r_img2.status_code == 201
            and img1_hash == expected_hash1
        )
        record_result("Inspection & Evidence", "Evidence Upload & SHA-256 Hashing", passed, f"Hash verified: {img1_hash[:16]}...")
    except Exception as e:
        record_result("Inspection & Evidence", "Evidence Upload & SHA-256 Hashing", False, str(e))

    # Verify physical item count integrity (3 photos across 2 physical items must not inflate item count)
    try:
        insp_detail = client.get(f"{API_V1}/inspections/{insp_id}", headers=insp_headers).json()
        item_count = len(insp_detail["items"])
        passed = (item_count == 2)
        record_result("Inspection & Evidence", "Item Count Integrity (Multi-Photo Non-Inflation)", passed, f"Physical item count remains strictly {item_count}")
    except Exception as e:
        record_result("Inspection & Evidence", "Item Count Integrity (Multi-Photo Non-Inflation)", False, str(e))

    # Submit inspection from DRAFT to SUBMITTED
    try:
        sub_res = client.post(f"{API_V1}/inspections/{insp_id}/submit", headers=insp_headers)
        passed = (sub_res.status_code == 200 and sub_res.json()["status"] == "SUBMITTED")
        record_result("Inspection & Evidence", "Submit Inspection Session", passed, f"Status: {sub_res.json()['status']}")
    except Exception as e:
        record_result("Inspection & Evidence", "Submit Inspection Session", False, str(e))

    # -------------------------------------------------------------------------
    # 5. WORKFLOW D: REAL AI INFERENCE AND HUMAN REVIEW
    # -------------------------------------------------------------------------
    print("\n--- 5. Testing Workflow D: Real ML Inference Worker & Review ---")
    run1_id = None
    try:
        infer_res = client.post(f"{API_V1}/images/{img1_id}/infer", headers=insp_headers)
        passed = (infer_res.status_code == 202 and infer_res.json()["status"] == "QUEUED")
        run1_id = infer_res.json()["model_run_id"]
        record_result("AI Inference & Review", "Enqueue ML Inference Job", passed, f"Job enqueued: {run1_id}")
    except Exception as e:
        record_result("AI Inference & Review", "Enqueue ML Inference Job", False, str(e))

    # Wait for active background worker (task-2512) to process genuine ResNet-18 forward pass
    worker_succeeded = False
    run1_result = None
    print("Waiting up to 15s for active ML inference worker to execute ResNet-18 pipeline...")
    for poll_idx in range(15):
        time.sleep(1.0)
        try:
            run_poll = client.get(f"{API_V1}/model-runs/{run1_id}", headers=insp_headers)
            if run_poll.status_code == 200:
                poll_data = run_poll.json()
                status_cur = poll_data.get("status")
                print(f"  Poll {poll_idx+1}: Status = {status_cur}")
                if status_cur == "SUCCEEDED":
                    worker_succeeded = True
                    run1_result = poll_data
                    break
                elif status_cur == "FAILED":
                    run1_result = poll_data
                    break
        except Exception as e:
            print(f"  Poll {poll_idx+1} error: {e}")

    passed = (worker_succeeded and run1_result is not None and run1_result.get("predicted_label") is not None)
    details = (
        f"Real ResNet-18 executed: status={run1_result.get('status')}, label={run1_result.get('predicted_label')}, "
        f"score={run1_result.get('score')}, latency={run1_result.get('processing_latency_ms')}ms, model_version={run1_result.get('model_version_name')}"
        if passed else f"Worker outcome: {run1_result}"
    )
    record_result("AI Inference & Review", "Real ML Worker Execution (ResNet-18)", passed, details)

    # Enqueue ML Inference on Image 3 (Item 2)
    try:
        infer_res2 = client.post(f"{API_V1}/images/{img3_id}/infer", headers=insp_headers)
        run2_id = infer_res2.json()["model_run_id"]
        for _ in range(10):
            time.sleep(1.0)
            p = client.get(f"{API_V1}/model-runs/{run2_id}", headers=insp_headers).json()
            if p.get("status") in ("SUCCEEDED", "FAILED"):
                break
    except Exception as e:
        print(f"Image 3 inference note: {e}")

    # Human Review: Item 1 -> CONFIRMED_GOOD
    try:
        rev1_res = client.post(
            f"{API_V1}/reviews",
            headers=insp_headers,
            json={
                "inspection_item_id": item1_id,
                "decision": "CONFIRMED_GOOD",
                "notes": "Surface profile matches CF8M specifications. AI prediction verified.",
            },
        )
        passed = (rev1_res.status_code == 201)
        rev1_data = rev1_res.json()
        snapshot = rev1_data.get("ai_snapshot", {})
        has_snapshot = (
            snapshot.get("predicted_label") is not None
            and "evidence_images" in snapshot
            and len(snapshot["evidence_images"]) >= 1
        )
        record_result("AI Inference & Review", "Review Item 1 (CONFIRMED_GOOD) & AI Snapshot", passed and has_snapshot,
                      f"Decision recorded with immutable AI snapshot containing label={snapshot.get('predicted_label')}, {len(snapshot.get('evidence_images', []))} image(s)")
    except Exception as e:
        record_result("AI Inference & Review", "Review Item 1 (CONFIRMED_GOOD)", False, str(e))

    # Human Review: Item 2 -> CONFIRMED_DEFECTIVE (creates defect)
    defect_id = None
    try:
        rev2_res = client.post(
            f"{API_V1}/reviews",
            headers=insp_headers,
            json={
                "inspection_item_id": item2_id,
                "decision": "CONFIRMED_DEFECTIVE",
                "notes": "Fillet radius hot tear observed near shroud interface.",
                "defect": {
                    "category": "HOT_TEAR",
                    "severity": "CRITICAL",
                    "surface_location": "SHROUD",
                    "description": "4.5mm hot tear crack located along shroud fillet.",
                },
            },
        )
        passed = (rev2_res.status_code == 201 and len(rev2_res.json().get("defects", [])) > 0)
        rev2_data = rev2_res.json()
        defect_id = rev2_data["defects"][0]["id"]
        record_result("AI Inference & Review", "Review Item 2 (CONFIRMED_DEFECTIVE)", passed, f"Defect logged: {defect_id} (HOT_TEAR/CRITICAL)")
    except Exception as e:
        record_result("AI Inference & Review", "Review Item 2 (CONFIRMED_DEFECTIVE)", False, str(e))

    # -------------------------------------------------------------------------
    # 6. WORKFLOW E: DEFECTS, CAPA, AND REINSPECTION
    # -------------------------------------------------------------------------
    print("\n--- 6. Testing Workflow E: Defects, CAPA & Four-Eyes Reinspection ---")
    # 6.1 Pre-CAPA Release Gate Check: Must be blocked by unresolved defect
    try:
        gate_res_pre = client.get(f"{API_V1}/batches/{batch_id}/release-gate", headers=qm_headers)
        passed = (gate_res_pre.status_code == 200 and gate_res_pre.json()["is_permitted"] is False)
        blocker_codes = [b["code"] for b in gate_res_pre.json().get("blockers", [])]
        record_result("Defects & CAPA", "Release Gate Blocks on Open Defect", passed, f"is_permitted=False, blockers={blocker_codes}")
    except Exception as e:
        record_result("Defects & CAPA", "Release Gate Blocks on Open Defect", False, str(e))

    # 6.2 Supervisor Creates CAPA
    capa_id = None
    sup_user_id = client.get(f"{API_V1}/auth/me", headers=sup_headers).json()["id"]
    try:
        capa_res = client.post(
            f"{API_V1}/corrective-actions",
            headers=sup_headers,
            json={
                "defect_id": defect_id,
                "title": "Weld Repair and Shroud Fillet Blend",
                "action_type": "REWORK",
                "description": "Excavate tear, TIG weld overlay with ER316L filler, grind to R5 contour.",
                "assigned_to": sup_user_id,
                "due_date": str(date.today() + timedelta(days=2)),
                "root_cause": "Thermal contraction strain in mold fillet zone.",
                "preventive_action": "Increase riser chilling on shroud section.",
            },
        )
        passed = (capa_res.status_code == 201)
        capa_id = capa_res.json()["id"]
        record_result("Defects & CAPA", "Create CAPA Remediation Plan", passed, f"CAPA {capa_id} created with status={capa_res.json()['status']}")
    except Exception as e:
        record_result("Defects & CAPA", "Create CAPA Remediation Plan", False, str(e))

    # 6.3 Start and Complete CAPA
    try:
        client.post(f"{API_V1}/corrective-actions/{capa_id}/start", headers=sup_headers)
        comp_res = client.post(
            f"{API_V1}/corrective-actions/{capa_id}/complete",
            headers=sup_headers,
            json={"completion_notes": "Cavity excavating and TIG weld build-up finished. Dye penetrant prepared."},
        )
        passed = (comp_res.status_code == 200 and comp_res.json()["status"] == "COMPLETED" and comp_res.json()["verification_status"] == "PENDING")
        record_result("Defects & CAPA", "Complete CAPA (Implementation COMPLETED, Verification PENDING)", passed,
                      f"status={comp_res.json()['status']}, verification_status={comp_res.json()['verification_status']}")
    except Exception as e:
        record_result("Defects & CAPA", "Complete CAPA", False, str(e))

    # 6.4 Four-Eyes Separation of Duties: Implementer cannot verify own work!
    try:
        self_verify_res = client.post(
            f"{API_V1}/corrective-actions/{capa_id}/verify",
            headers=sup_headers,
            json={"decision": "APPROVED", "notes": "Self verification attempt should be blocked"},
        )
        err_code = get_error_code(self_verify_res)
        passed = (self_verify_res.status_code in (403, 422) or err_code in ("FOUR_EYES_VIOLATION", "SELF_VERIFICATION_FORBIDDEN", "INSUFFICIENT_PERMISSIONS"))
        record_result("Defects & CAPA", "Four-Eyes Principle: Block Implementer Self-Verification", passed,
                      f"Status {self_verify_res.status_code}, error={err_code}")
    except Exception as e:
        record_result("Defects & CAPA", "Four-Eyes Principle: Block Implementer Self-Verification", False, str(e))

    # 6.5 Independent Verification by Quality Manager
    try:
        verify_res = client.post(
            f"{API_V1}/corrective-actions/{capa_id}/verify",
            headers=qm_headers,
            json={"decision": "APPROVED", "notes": "Independent verification: liquid penetrant exam indicates defect-free weld."},
        )
        passed = (verify_res.status_code == 200 and verify_res.json()["verification_status"] == "VERIFIED")
        record_result("Defects & CAPA", "Independent QM Verification Approval", passed,
                      f"verification_status={verify_res.json()['verification_status']}")
    except Exception as e:
        record_result("Defects & CAPA", "Independent QM Verification Approval", False, str(e))

    # 6.6 Reinspection Workflow: Inspector uploads post-remediation evidence & submits reinspection
    try:
        ok_sample, _ = get_sample_images()
        with open(ok_sample, "rb") as f:
            re_photo_bytes = f.read()

        r_reimg = client.post(
            f"{API_V1}/images/upload",
            headers=insp_headers,
            data={"batch_id": batch_id, "inspection_item_id": item2_id, "image_scope": "ITEM"},
            files={"file": ("reinspection_impeller_002.jpeg", re_photo_bytes, "image/jpeg")},
        )
        reimg_id = r_reimg.json()["id"]

        reinsp_res = client.post(
            f"{API_V1}/reinspections",
            headers=insp_headers,
            json={
                "defect_id": defect_id,
                "corrective_action_id": capa_id,
                "outcome": "DEFECT_RESOLVED",
                "notes": "Visual and penetrant reinspection confirms weld is defect-free. Item clear.",
                "evidence_image_id": reimg_id,
            },
        )
        passed = (reinsp_res.status_code == 201 and reinsp_res.json()["outcome"] == "DEFECT_RESOLVED")

        # Verify defect is now RESOLVED and item is CLEAR
        defect_detail = client.get(f"{API_V1}/defects/{defect_id}", headers=insp_headers).json()
        insp_check = client.get(f"{API_V1}/inspections/{insp_id}", headers=insp_headers).json()
        item2_status = next((it["status"] for it in insp_check["items"] if it["id"] == item2_id), None)

        passed = passed and (defect_detail["status"] == "RESOLVED") and (item2_status == "CLEAR")
        record_result("Defects & CAPA", "Reinspection & Defect Resolution", passed,
                      f"Outcome={reinsp_res.json()['outcome']}, Defect status={defect_detail['status']}, Item status={item2_status}")
    except Exception as e:
        record_result("Defects & CAPA", "Reinspection & Defect Resolution", False, str(e))

    # -------------------------------------------------------------------------
    # 7. WORKFLOW F: RELEASE GOVERNANCE
    # -------------------------------------------------------------------------
    print("\n--- 7. Testing Workflow F: Release Governance & Decisions ---")
    # 7.1 Evaluate Release Gates: All mandatory requirements satisfied
    gate_data = None
    try:
        gate_res_post = client.get(f"{API_V1}/batches/{batch_id}/release-gate", headers=qm_headers)
        passed = (gate_res_post.status_code == 200)
        gate_data = gate_res_post.json()
        passed = passed and (gate_data["is_permitted"] is True) and (len(gate_data["blockers"]) == 0)
        record_result("Release Governance", "Live Release Gate Evaluation (0 Blockers)", passed,
                      f"is_permitted={gate_data.get('is_permitted')}, blockers={len(gate_data.get('blockers', []))}, counts={gate_data.get('counts')}")
    except Exception as e:
        record_result("Release Governance", "Live Release Gate Evaluation (0 Blockers)", False, str(e))

    # 7.2 Quality Manager Executes Official Release Decision
    try:
        rel_res = client.post(
            f"{API_V1}/batches/{batch_id}/decisions",
            headers=qm_headers,
            json={
                "decision": "RELEASE",
                "reason": "100% inspection completed. One defect remediated, independently verified, and confirmed clear via reinspection.",
            },
        )
        passed = (rel_res.status_code == 201)
        dec_data = rel_res.json()
        snapshot = dec_data.get("snapshot", {})

        # Verify batch status updated to RELEASED
        batch_after = client.get(f"{API_V1}/batches/{batch_id}", headers=qm_headers).json()
        passed = passed and (batch_after["status"] == "RELEASED") and (snapshot.get("decision") == "RELEASE")
        record_result("Release Governance", "Official Quality Manager Release Decision", passed,
                      f"Batch status={batch_after['status']}, Decision={dec_data['decision']}, PolicyVersion={snapshot.get('policy_version')}")
    except Exception as e:
        record_result("Release Governance", "Official Quality Manager Release Decision", False, str(e))

    # 7.3 Decision Snapshot Immutability & Ledger Verification
    try:
        ledger_res = client.get(f"{API_V1}/batches/{batch_id}/decisions", headers=qm_headers)
        passed = (ledger_res.status_code == 200 and ledger_res.json()["total"] >= 1)
        history_item = ledger_res.json()["items"][0]
        snap = history_item["snapshot"]
        passed = passed and (snap["inspection_counts"]["total_items"] == 2) and (snap["quality_counts"]["resolved_defects"] == 1)
        record_result("Release Governance", "Historical Decision Ledger & Immutable Snapshot", passed,
                      f"Retrieved {ledger_res.json()['total']} decision(s), persisted snapshot total_items={snap['inspection_counts']['total_items']}")
    except Exception as e:
        record_result("Release Governance", "Historical Decision Ledger & Immutable Snapshot", False, str(e))

    # 7.4 Stale-State HTTP 409 Conflict Handling
    try:
        stale_res = client.post(
            f"{API_V1}/batches/{batch_id}/decisions",
            headers=qm_headers,
            json={
                "decision": "RELEASE",
                "reason": "Duplicate attempt to release already released batch",
            },
        )
        err_code = get_error_code(stale_res)
        passed = (stale_res.status_code == 409 and err_code == "BATCH_ALREADY_RELEASED")
        record_result("Release Governance", "Stale-State HTTP 409 Conflict Detection", passed,
                      f"Status {stale_res.status_code}, code={err_code}")
    except Exception as e:
        record_result("Release Governance", "Stale-State HTTP 409 Conflict Detection", False, str(e))

    # -------------------------------------------------------------------------
    # FINAL SUMMARY
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PHASE 5D VERIFICATION SUMMARY")
    print("=" * 80)
    passed_cnt = sum(1 for r in results if r["status"] == "PASS")
    total_cnt = len(results)
    print(f"Total Tests Executed: {total_cnt}")
    print(f"Passed:              {passed_cnt}")
    print(f"Failed:              {total_cnt - passed_cnt}")
    print("=" * 80)

    if passed_cnt == total_cnt:
        print("ALL END-TO-END APPLICATION AND INTEGRATION WORKFLOWS PASSED!")
        return 0
    else:
        print("SOME TESTS FAILED — SEE ABOVE FOR DETAILS")
        return 1

if __name__ == "__main__":
    sys.exit(main())
