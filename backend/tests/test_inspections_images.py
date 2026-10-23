import io
import uuid
from datetime import date
import pytest
from fastapi import status

JPEG_HEADER = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00" + b"\x00" * 50
PNG_HEADER = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00" + b"\x00" * 50


@pytest.fixture
def test_batch(client, qm_headers, supervisor_headers):
    sku = f"INSP-PROD-{uuid.uuid4().hex[:6]}"
    p_res = client.post(
        "/api/v1/products",
        headers=qm_headers,
        json={"sku": sku, "name": "Impeller", "material": "CF8M SS"},
    )
    prod_id = p_res.json()["id"]

    b_res = client.post(
        "/api/v1/batches",
        headers=supervisor_headers,
        json={
            "batch_number": f"BATCH-{uuid.uuid4().hex[:6]}",
            "product_id": prod_id,
            "manufacture_date": str(date.today()),
            "declared_quantity": 40,
        },
    )
    return b_res.json()


def test_inspection_lifecycle_and_validation(client, inspector_headers, supervisor_headers, qm_headers, test_batch, temp_storage):
    batch_id = test_batch["id"]

    # 1. Inspector creates draft inspection
    insp_res = client.post(
        "/api/v1/inspections",
        headers=inspector_headers,
        json={"batch_id": batch_id, "stage": "FINAL_VISUAL", "sampling_plan": "AQL_LEVEL_II"},
    )
    assert insp_res.status_code == status.HTTP_201_CREATED
    insp_data = insp_res.json()
    insp_id = insp_data["id"]
    assert insp_data["status"] == "DRAFT"

    # 2. Cannot submit without items
    sub_fail = client.post(f"/api/v1/inspections/{insp_id}/submit", headers=inspector_headers)
    assert sub_fail.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert sub_fail.json()["error"]["code"] == "NO_ITEMS_REGISTERED"

    # 3. Register physical items
    items_res = client.post(
        f"/api/v1/inspections/{insp_id}/items",
        headers=inspector_headers,
        json={"items": [
            {"item_identifier": "ITEM-A01", "cavity_number": 1},
            {"item_identifier": "ITEM-A02", "cavity_number": 2},
        ]},
    )
    assert items_res.status_code == status.HTTP_201_CREATED
    items = items_res.json()
    assert len(items) == 2
    item1_id = items[0]["id"]

    # 4. Cannot submit without images
    sub_fail2 = client.post(f"/api/v1/inspections/{insp_id}/submit", headers=inspector_headers)
    assert sub_fail2.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert sub_fail2.json()["error"]["code"] == "INSUFFICIENT_EVIDENCE"

    # 5. Upload valid JPEG evidence
    img_res1 = client.post(
        "/api/v1/images/upload",
        headers=inspector_headers,
        data={
            "batch_id": batch_id,
            "inspection_item_id": item1_id,
            "image_scope": "ITEM",
            "surface_location": "SUCTION_EYE",
            "represented_item_count": 1,
        },
        files={"file": ("impeller_front.jpg", io.BytesIO(JPEG_HEADER), "image/jpeg")},
    )
    assert img_res1.status_code == status.HTTP_201_CREATED
    img1 = img_res1.json()
    assert img1["mime_type"] == "image/jpeg"
    assert img1["is_superseded"] is False

    # 6. Upload second image for the same physical item (multi-image support)
    img_res2 = client.post(
        "/api/v1/images/upload",
        headers=inspector_headers,
        data={
            "batch_id": batch_id,
            "inspection_item_id": item1_id,
            "image_scope": "SURFACE",
            "surface_location": "VANE_TIP",
            "represented_item_count": 1,
        },
        files={"file": ("impeller_vane.png", io.BytesIO(PNG_HEADER), "image/png")},
    )
    assert img_res2.status_code == status.HTTP_201_CREATED
    img2 = img_res2.json()

    # 7. Submit inspection successfully
    sub_success = client.post(f"/api/v1/inspections/{insp_id}/submit", headers=inspector_headers)
    assert sub_success.status_code == status.HTTP_200_OK
    assert sub_success.json()["status"] == "SUBMITTED"

    # 8. Attempting to add items to submitted inspection fails
    add_fail = client.post(
        f"/api/v1/inspections/{insp_id}/items",
        headers=inspector_headers,
        json={"items": [{"item_identifier": "ITEM-A03"}]},
    )
    assert add_fail.status_code == status.HTTP_409_CONFLICT
    assert add_fail.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


def test_image_validation_magic_bytes_and_size(client, inspector_headers, test_batch, temp_storage):
    batch_id = test_batch["id"]

    # 1. Invalid content / text file pretending to be image fails
    fake_img = b"This is plain text and not a real photo."
    r_invalid = client.post(
        "/api/v1/images/upload",
        headers=inspector_headers,
        data={"batch_id": batch_id, "image_scope": "BATCH_SAMPLE", "represented_item_count": 5},
        files={"file": ("fake.jpg", io.BytesIO(fake_img), "image/jpeg")},
    )
    assert r_invalid.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    assert r_invalid.json()["error"]["code"] == "UNSUPPORTED_MEDIA"

    # 2. Oversized file (>10MB) fails
    oversized = b"\xff\xd8\xff" + b"X" * (10485760 + 10)
    r_oversized = client.post(
        "/api/v1/images/upload",
        headers=inspector_headers,
        data={"batch_id": batch_id, "image_scope": "BATCH_SAMPLE", "represented_item_count": 5},
        files={"file": ("huge.jpg", io.BytesIO(oversized), "image/jpeg")},
    )
    assert r_oversized.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    assert r_oversized.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_private_evidence_access_and_supersede(client, inspector_headers, qm_headers, test_batch, temp_storage):
    batch_id = test_batch["id"]

    # Upload original image
    r_up1 = client.post(
        "/api/v1/images/upload",
        headers=inspector_headers,
        data={"batch_id": batch_id, "image_scope": "BATCH_SAMPLE", "represented_item_count": 10},
        files={"file": ("original.jpg", io.BytesIO(JPEG_HEADER), "image/jpeg")},
    )
    assert r_up1.status_code == status.HTTP_201_CREATED
    img1_id = r_up1.json()["id"]

    # Unauthenticated access to /content fails
    r_unauth = client.get(f"/api/v1/images/{img1_id}/content")
    assert r_unauth.status_code == status.HTTP_401_UNAUTHORIZED

    # Authenticated access succeeds and streams binary
    r_auth = client.get(f"/api/v1/images/{img1_id}/content", headers=inspector_headers)
    assert r_auth.status_code == status.HTTP_200_OK
    assert r_auth.headers["content-type"] == "image/jpeg"
    assert r_auth.content == JPEG_HEADER

    # Upload replacement image
    r_up2 = client.post(
        "/api/v1/images/upload",
        headers=inspector_headers,
        data={"batch_id": batch_id, "image_scope": "BATCH_SAMPLE", "represented_item_count": 10},
        files={"file": ("replacement.jpg", io.BytesIO(JPEG_HEADER), "image/jpeg")},
    )
    img2_id = r_up2.json()["id"]

    # Supersede image 1 with image 2
    r_sup = client.post(
        f"/api/v1/images/{img1_id}/supersede",
        headers=inspector_headers,
        json={"superseded_by_id": img2_id, "supersede_reason": "Retaken with improved ring light"},
    )
    assert r_sup.status_code == status.HTTP_200_OK
    data = r_sup.json()
    assert data["is_superseded"] is True
    assert data["superseded_by_id"] == img2_id
    assert data["supersede_reason"] == "Retaken with improved ring light"


def test_inspection_item_image_association_and_refresh(client, inspector_headers, test_batch, temp_storage):
    """Regression test: verifies image association with physical item, inspection detail refresh, and photo counts."""
    batch_id = test_batch["id"]

    # 1. Create inspection session
    insp_res = client.post(
        "/api/v1/inspections",
        headers=inspector_headers,
        json={"batch_id": batch_id, "stage": "FINAL_VISUAL", "sampling_plan": "AQL_LEVEL_II"},
    )
    assert insp_res.status_code == status.HTTP_201_CREATED
    insp_id = insp_res.json()["id"]

    # 2. Register physical item
    items_res = client.post(
        f"/api/v1/inspections/{insp_id}/items",
        headers=inspector_headers,
        json={"items": [{"item_identifier": "ITEM-REGRESSION-001", "cavity_number": 1}]},
    )
    assert items_res.status_code == status.HTTP_201_CREATED
    item_id = items_res.json()[0]["id"]

    # 3. Verify get_inspection returns item with empty images list
    get_insp = client.get(f"/api/v1/inspections/{insp_id}", headers=inspector_headers)
    assert get_insp.status_code == status.HTTP_200_OK
    items = get_insp.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == item_id
    assert items[0]["images"] == []

    # 4. Upload photo associated with physical item
    img_res1 = client.post(
        "/api/v1/images/upload",
        headers=inspector_headers,
        data={
            "batch_id": batch_id,
            "inspection_item_id": item_id,
            "image_scope": "ITEM",
            "surface_location": "SUCTION_EYE",
            "represented_item_count": 1,
        },
        files={"file": ("front_eye.jpg", io.BytesIO(JPEG_HEADER), "image/jpeg")},
    )
    assert img_res1.status_code == status.HTTP_201_CREATED
    img1_data = img_res1.json()
    assert img1_data["inspection_item_id"] == item_id

    # 5. Verify get_inspection returns the uploaded image associated with the item
    get_insp2 = client.get(f"/api/v1/inspections/{insp_id}", headers=inspector_headers)
    assert get_insp2.status_code == status.HTTP_200_OK
    item_after_up = get_insp2.json()["items"][0]
    assert len(item_after_up["images"]) == 1
    assert item_after_up["images"][0]["id"] == img1_data["id"]
    assert item_after_up["images"][0]["original_filename"] == "front_eye.jpg"
    assert item_after_up["images"][0]["sha256_hash"] == img1_data["sha256_hash"]
    assert item_after_up["images"][0]["surface_location"] == "SUCTION_EYE"

    # 6. Upload second photo for same physical item (multi-angle verification)
    img_res2 = client.post(
        "/api/v1/images/upload",
        headers=inspector_headers,
        data={
            "batch_id": batch_id,
            "inspection_item_id": item_id,
            "image_scope": "SURFACE",
            "surface_location": "VANE_TIP",
            "represented_item_count": 1,
        },
        files={"file": ("vane_detail.png", io.BytesIO(PNG_HEADER), "image/png")},
    )
    assert img_res2.status_code == status.HTTP_201_CREATED

    # 7. Verify count increases to 2
    get_insp3 = client.get(f"/api/v1/inspections/{insp_id}", headers=inspector_headers)
    assert get_insp3.status_code == status.HTTP_200_OK
    item_multi = get_insp3.json()["items"][0]
    assert len(item_multi["images"]) == 2

    # 8. Upload with non-existent inspection_item_id returns 404
    bad_item_upload = client.post(
        "/api/v1/images/upload",
        headers=inspector_headers,
        data={
            "batch_id": batch_id,
            "inspection_item_id": "00000000-0000-0000-0000-000000000000",
            "image_scope": "ITEM",
        },
        files={"file": ("test.jpg", io.BytesIO(JPEG_HEADER), "image/jpeg")},
    )
    assert bad_item_upload.status_code == status.HTTP_404_NOT_FOUND
