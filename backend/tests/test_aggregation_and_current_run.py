import uuid
import datetime
import pytest

from backend.app.models.entities import (
    Product,
    Batch,
    Inspection,
    InspectionItem,
    Image,
    ModelRun,
    ModelVersion,
)
from backend.app.services.aggregation_service import (
    get_current_model_run_for_image,
    derive_item_level_routing,
)


@pytest.fixture
def test_setup(db_session, seeded_users):
    """Sets up product, batch, inspection, item, and model version for aggregation tests."""
    inspector = seeded_users["INSPECTOR"]

    prod = Product(
        sku=f"SKU-AGG-{uuid.uuid4().hex[:6]}",
        name="Valve Body Aggregation Test",
        material="Ductile Iron",
    )
    db_session.add(prod)
    db_session.flush()

    batch = Batch(
        batch_number=f"BATCH-AGG-{uuid.uuid4().hex[:6]}",
        product_id=prod.id,
        manufacture_date=datetime.date.today(),
        declared_quantity=10,
        created_by=inspector.id,
    )
    db_session.add(batch)
    db_session.flush()

    insp = Inspection(
        inspection_number=f"INSP-AGG-{uuid.uuid4().hex[:6]}",
        batch_id=batch.id,
        inspector_id=inspector.id,
        stage="FINAL_VISUAL",
        status="IN_PROGRESS",
    )
    db_session.add(insp)
    db_session.flush()

    item = InspectionItem(
        inspection_id=insp.id,
        item_identifier="ITEM-VALVE-01",
        cavity_number=1,
    )
    db_session.add(item)
    db_session.flush()

    ver = ModelVersion(
        version_name=f"v1.0.0-agg-{uuid.uuid4().hex[:4]}",
        model_architecture="ResNet-18",
        weights_path="ml/artifacts/model_best.pt",
        weights_sha256="ab2b592ab9a4cca3c97613d8e52d9f8abc2906dbef77cddd15c73d2da1c3c2da",
        unfamiliar_guard_sha256="c39905c247cd881175439833661610ce8d0dbff18811057fb289dfb24c464abc",
        training_dataset_info={"dataset": "casting_512x512"},
        metrics={"accuracy": 0.9898},
        is_active=True,
    )
    db_session.add(ver)
    db_session.commit()

    return {
        "batch": batch,
        "inspection": insp,
        "item": item,
        "version": ver,
    }


def create_image(db_session, batch_id, item_id, filename="img.jpg", is_superseded=False, scope="ITEM", uploaded_by=None):
    img = Image(
        id=str(uuid.uuid4()),
        batch_id=batch_id,
        inspection_item_id=item_id,
        image_scope=scope,
        storage_path=f"storage/evidence/{filename}",
        original_filename=filename,
        mime_type="image/jpeg",
        file_size_bytes=1024,
        sha256_hash=uuid.uuid4().hex + uuid.uuid4().hex,
        is_superseded=is_superseded,
        uploaded_by=uploaded_by or str(uuid.uuid4()),
    )
    db_session.add(img)
    db_session.flush()
    return img


def create_run(db_session, image_id, version_id, logical_id, attempt_number, status, outcome=None, score=None, parent_id=None):
    run = ModelRun(
        logical_run_id=logical_id,
        image_id=image_id,
        model_version_id=version_id,
        attempt_number=attempt_number,
        parent_run_id=parent_id,
        status=status,
        routing_outcome=outcome,
        score=score,
        score_type="UNRESTRICTED_LOGIT_SIGMOID_FRACTION" if score is not None else None,
    )
    db_session.add(run)
    db_session.flush()
    return run


def test_deterministic_current_run_selection(db_session, test_setup):
    """Stage 12: Current run is the highest attempt number of the latest logical request."""
    batch_id = test_setup["batch"].id
    item_id = test_setup["item"].id
    ver_id = test_setup["version"].id

    img = create_image(db_session, batch_id, item_id, "determinism_test.jpg")
    img_id = img.id

    # 1. No runs yet -> None
    assert get_current_model_run_for_image(db_session, img_id) is None

    # 2. Logical Run 1: Attempt 1 fails, Attempt 2 succeeds
    log1 = str(uuid.uuid4())
    r1_1 = create_run(db_session, img_id, ver_id, log1, 1, "FAILED", outcome=None)
    db_session.commit()
    curr = get_current_model_run_for_image(db_session, img_id)
    assert curr.id == r1_1.id
    assert curr.status == "FAILED"

    r1_2 = create_run(db_session, img_id, ver_id, log1, 2, "SUCCEEDED", outcome="LIKELY_OK", score=0.005, parent_id=r1_1.id)
    db_session.commit()
    curr = get_current_model_run_for_image(db_session, img_id)
    assert curr.id == r1_2.id
    assert curr.attempt_number == 2
    assert curr.routing_outcome == "LIKELY_OK"

    # 3. Later explicit Logical Run 2 created (e.g. rerun request): Attempt 1 is QUEUED
    log2 = str(uuid.uuid4())
    r2_1 = create_run(db_session, img_id, ver_id, log2, 1, "QUEUED")
    db_session.commit()

    # Current run MUST now be r2_1 (latest logical request, attempt 1), NOT r1_2!
    curr = get_current_model_run_for_image(db_session, img_id)
    assert curr.id == r2_1.id
    assert curr.logical_run_id == log2
    assert curr.status == "QUEUED"


def test_multi_image_aggregation_rules(db_session, test_setup):
    """Stage 13: Item-level aggregation precedence rules across multiple images."""
    batch_id = test_setup["batch"].id
    item_id = test_setup["item"].id
    ver_id = test_setup["version"].id

    # Case A: Item with no images -> NEEDS_REVIEW
    res_empty = derive_item_level_routing(db_session, item_id)
    assert res_empty["derived_routing_outcome"] == "NEEDS_REVIEW"
    assert res_empty["total_images"] == 0
    assert res_empty["additional_review_required"] is True

    # Case B: Two images, both LIKELY_OK -> derived outcome LIKELY_OK
    img1 = create_image(db_session, batch_id, item_id, "flange_top.jpg")
    img2 = create_image(db_session, batch_id, item_id, "flange_bottom.jpg")

    create_run(db_session, img1.id, ver_id, str(uuid.uuid4()), 1, "SUCCEEDED", outcome="LIKELY_OK", score=0.002)
    create_run(db_session, img2.id, ver_id, str(uuid.uuid4()), 1, "SUCCEEDED", outcome="LIKELY_OK", score=0.003)
    db_session.commit()

    res_ok = derive_item_level_routing(db_session, item_id)
    assert res_ok["derived_routing_outcome"] == "LIKELY_OK"
    assert res_ok["total_images"] == 2
    assert res_ok["has_defective_flag"] is False
    assert res_ok["additional_review_required"] is False

    # Case C: Third image added with NEEDS_REVIEW -> item becomes NEEDS_REVIEW
    img3 = create_image(db_session, batch_id, item_id, "bore_side.jpg")
    create_run(db_session, img3.id, ver_id, str(uuid.uuid4()), 1, "SUCCEEDED", outcome="NEEDS_REVIEW", score=0.25)
    db_session.commit()

    res_review = derive_item_level_routing(db_session, item_id)
    assert res_review["derived_routing_outcome"] == "NEEDS_REVIEW"
    assert res_review["has_defective_flag"] is False
    assert res_review["additional_review_required"] is True

    # Case D: Fourth image added with LIKELY_DEFECTIVE -> item becomes LIKELY_DEFECTIVE
    # And since img3 is NEEDS_REVIEW, additional_review_required remains True
    img4 = create_image(db_session, batch_id, item_id, "flange_crack.jpg")
    create_run(db_session, img4.id, ver_id, str(uuid.uuid4()), 1, "SUCCEEDED", outcome="LIKELY_DEFECTIVE", score=0.98)
    db_session.commit()

    res_def = derive_item_level_routing(db_session, item_id)
    assert res_def["derived_routing_outcome"] == "LIKELY_DEFECTIVE"
    assert res_def["has_defective_flag"] is True
    assert res_def["has_review_or_incomplete_flag"] is True
    assert res_def["additional_review_required"] is True

    # Case E: Superseded image is excluded from aggregation
    # If img4 is superseded by an updated conforming retake
    img4.is_superseded = True
    db_session.commit()

    res_after_supersede = derive_item_level_routing(db_session, item_id)
    # img4 is excluded, remaining active images are img1 (OK), img2 (OK), img3 (NEEDS_REVIEW)
    assert res_after_supersede["total_images"] == 3
    assert res_after_supersede["has_defective_flag"] is False
    assert res_after_supersede["derived_routing_outcome"] == "NEEDS_REVIEW"
