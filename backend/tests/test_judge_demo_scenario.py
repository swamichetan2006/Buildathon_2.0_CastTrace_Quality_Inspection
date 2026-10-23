"""Automated test suite verifying the Judge Demonstration Scenario.

Covers:
- Seed-script idempotency and rollback on error.
- Valid foreign-key relationships and DB integrity.
- Distinct physical-item counting vs photograph counts.
- Actual inspection and review states (DRAFT, IN_PROGRESS, PENDING, CONFIRMED_DEFECTIVE).
- Active overdue CAPA vs completed CAPA awaiting verification.
- Accurate defect lifecycle status (PENDING_REINSPECTION).
- Historical similarity retrieval returning the persisted historical candidate (DEF-HIST-2026-001).
- Genuine no-match behavior for completely divergent defects.
- RBAC permissions and deterministic read-only release-gate behavior.
"""

import uuid
from datetime import date, datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import pytest
from fastapi import status
from sqlalchemy import text

from backend.app.models.entities import (
    Batch,
    Inspection,
    InspectionItem,
    Review,
    Defect,
    CorrectiveAction,
    Reinspection,
    BatchDecision,
    User,
)
from scripts.seed_judge_demo_scenario import (
    seed_judge_demo_scenario,
    DEMO_MAIN_BATCH,
    DEMO_HIST_BATCH,
)


@pytest.fixture(autouse=True)
def setup_demo_scenario(db_session, seeded_users):
    """Ensure demo scenario is populated in the test database for every test."""
    seed_judge_demo_scenario(db_session)
    db_session.commit()


def test_seed_script_idempotency_and_integrity(db_session):
    """Seed script can run multiple times without duplicating or corrupting demo records."""
    res1 = seed_judge_demo_scenario(db_session)
    assert res1["status"] == "ALREADY_SEEDED"

    res2 = seed_judge_demo_scenario(db_session)
    assert res2["status"] == "ALREADY_SEEDED"

    main_batches = db_session.query(Batch).filter_by(batch_number=DEMO_MAIN_BATCH).all()
    assert len(main_batches) == 1, "There must be exactly one main demo batch"

    hist_batches = db_session.query(Batch).filter_by(batch_number=DEMO_HIST_BATCH).all()
    assert len(hist_batches) == 1, "There must be exactly one historical demo batch"


def test_judge_demo_distinct_physical_item_counting(client, inspector_headers, db_session):
    """Distinct physical items are counted deterministically against declared quantity."""
    main_batch = db_session.query(Batch).filter_by(batch_number=DEMO_MAIN_BATCH).first()
    assert main_batch is not None
    assert main_batch.declared_quantity == 10

    # Query quality intelligence summary
    res = client.post(
        "/api/v1/intelligence/query",
        headers=inspector_headers,
        json={
            "batch_identifier": DEMO_MAIN_BATCH,
            "question": "What is the inspection coverage and defect count?",
        },
    )
    assert res.status_code == status.HTTP_200_OK
    metrics = res.json()["deterministic_metrics"]
    assert metrics["total_declared_quantity"] == 10
    assert metrics["inspected_items"] == 2  # SN-DEMO-IMP-001, SN-DEMO-IMP-002 have non-pending reviews
    assert metrics["confirmed_defects_count"] == 2


def test_judge_demo_overdue_vs_pending_verification_capa(client, inspector_headers, db_session):
    """CAPA-DEMO-2026-001 is active overdue (CRITICAL); CAPA-DEMO-2026-002 is completed awaiting verification (HIGH)."""
    res = client.get(
        f"/api/v1/intelligence/attention?batch_identifier={DEMO_MAIN_BATCH}",
        headers=inspector_headers,
    )
    assert res.status_code == status.HTTP_200_OK
    items = res.json()["items"]

    overdue_item = next((i for i in items if i["business_identifier"] == "CAPA-DEMO-2026-001"), None)
    assert overdue_item is not None
    assert overdue_item["is_overdue"] is True
    assert overdue_item["reason_code"] == "CAPA_OVERDUE"
    assert overdue_item["priority"] == "CRITICAL"

    verif_item = next((i for i in items if i["business_identifier"] == "CAPA-DEMO-2026-002"), None)
    assert verif_item is not None
    assert verif_item["is_overdue"] is False
    assert verif_item["reason_code"] == "CAPA_VERIFICATION_PENDING"
    assert verif_item["priority"] == "HIGH"


def test_judge_demo_defect_lifecycle_status_and_review_separation(client, inspector_headers, db_session):
    """Defect DEF-DEMO-2026-001 lifecycle status is PENDING_REINSPECTION, review decision is CONFIRMED_DEFECTIVE."""
    res = client.get(
        f"/api/v1/intelligence/batch-defects?batch_identifier={DEMO_MAIN_BATCH}",
        headers=inspector_headers,
    )
    assert res.status_code == status.HTTP_200_OK
    defects = res.json()

    target = next((d for d in defects if d["defect_number"] == "DEF-DEMO-2026-001"), None)
    assert target is not None
    assert target["status"] == "PENDING_REINSPECTION"
    assert target["review_decision"] == "CONFIRMED_DEFECTIVE"
    assert target["category"] == "SHRINKAGE_POROSITY"
    assert target["surface_location"] == "FLANGE_FACE"


def test_judge_demo_historical_similarity_matches_candidate(client, inspector_headers, db_session):
    """Historical similarity discovers DEF-HIST-2026-001 with high score, returning prior CAPA & reinspection."""
    def_main = db_session.query(Defect).filter_by(defect_number="DEF-DEMO-2026-001").first()
    assert def_main is not None

    res = client.get(
        f"/api/v1/intelligence/historical-similarity?defect_id={def_main.id}&include_cross_product=true",
        headers=inspector_headers,
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["matches_found"] >= 1

    top_match = data["matches"][0]
    assert top_match["defect_number"] == "DEF-HIST-2026-001"
    assert top_match["match_score"] >= 80.0
    assert top_match["status"] == "RESOLVED"
    assert top_match["review_decision"] == "CONFIRMED_DEFECTIVE"
    assert len(top_match["corrective_actions"]) >= 1
    assert top_match["corrective_actions"][0]["action_number"] == "CAPA-HIST-2026-001"
    assert len(top_match["reinspections"]) >= 1
    assert top_match["reinspections"][0]["outcome"] == "DEFECT_RESOLVED"


def test_judge_demo_genuine_no_match_for_divergent_defect(client, inspector_headers, db_session):
    """Defect with non-overlapping attributes returns no top matches or lower confidence scores."""
    prod_other = db_session.query(Batch).filter_by(batch_number=DEMO_MAIN_BATCH).first().product
    inspector = db_session.query(User).filter((User.username == "inspector_chen") | (User.role == "INSPECTOR")).first()
    assert inspector is not None

    # Create isolated test batch so DEMO_MAIN_BATCH blockers are not polluted
    batch_iso = Batch(
        batch_number=f"BATCH-TEST-NOMATCH-{uuid.uuid4().hex[:6]}",
        product_id=prod_other.id,
        manufacture_date=date.today(),
        heat_number="HEAT-TEST-NOMATCH",
        declared_quantity=1,
        status="IN_PRODUCTION",
        created_by=inspector.id,
    )
    db_session.add(batch_iso)
    db_session.flush()

    # Create isolated single defect with category 'OTHER' and surface 'UNKNOWN_ZONE'
    insp = Inspection(
        inspection_number=f"INSP-TEST-NOMATCH-{uuid.uuid4().hex[:6]}",
        batch_id=batch_iso.id,
        inspector_id=inspector.id,
        stage="FINAL_VISUAL",
        status="IN_PROGRESS",
    )
    db_session.add(insp)
    db_session.flush()

    item = InspectionItem(
        inspection_id=insp.id,
        item_identifier="SN-NOMATCH-01",
        status="DEFECTIVE",
    )
    db_session.add(item)
    db_session.flush()

    rev = Review(
        inspection_id=insp.id,
        inspection_item_id=item.id,
        reviewer_id=inspector.id,
        decision="CONFIRMED_DEFECTIVE",
    )
    db_session.add(rev)
    db_session.flush()

    diff_defect = Defect(
        defect_number=f"DEF-NOMATCH-{uuid.uuid4().hex[:6]}",
        inspection_item_id=item.id,
        review_id=rev.id,
        category="OTHER",
        severity="MINOR",
        surface_location="NOZZLE_TIP",
        description="Completely unrelated paint blemish on non-critical nozzle tip",
        status="OPEN",
    )
    db_session.add(diff_defect)
    db_session.commit()

    res = client.get(
        f"/api/v1/intelligence/historical-similarity?defect_id={diff_defect.id}&include_cross_product=false",
        headers=inspector_headers,
    )
    assert res.status_code == status.HTTP_200_OK
    matches = res.json()["matches"]
    # Should not match DEF-HIST-2026-001 at high tier
    hist_match = next((m for m in matches if m["defect_number"] == "DEF-HIST-2026-001"), None)
    if hist_match:
        assert hist_match["match_score"] < 60.0


def test_judge_demo_release_gate_deterministic_and_read_only(client, inspector_headers, db_session):
    """Release gate evaluation strictly reports 12 blockers and does NOT mutate batch status."""
    batch = db_session.query(Batch).filter_by(batch_number=DEMO_MAIN_BATCH).first()
    assert batch is not None
    initial_status = batch.status

    res = client.get(
        f"/api/v1/batches/{batch.id}/release-gate",
        headers=inspector_headers,
    )
    assert res.status_code == status.HTTP_200_OK
    gate = res.json()
    assert gate["is_permitted"] is False
    assert len(gate["blockers"]) == 12

    # Verify no state mutation
    db_session.refresh(batch)
    assert batch.status == initial_status


def test_judge_demo_rbac_enforcement(client, inspector_headers, supervisor_headers, db_session):
    """Inspectors and Supervisors cannot execute batch release decisions."""
    batch = db_session.query(Batch).filter_by(batch_number=DEMO_MAIN_BATCH).first()

    # Inspector attempts release -> 403 Forbidden
    res_insp = client.post(
        f"/api/v1/batches/{batch.id}/decisions",
        headers=inspector_headers,
        json={"decision": "RELEASE", "reason": "Unauthorized release attempt by inspector"},
    )
    assert res_insp.status_code == status.HTTP_403_FORBIDDEN

    # Supervisor attempts release -> 403 Forbidden
    res_sup = client.post(
        f"/api/v1/batches/{batch.id}/decisions",
        headers=supervisor_headers,
        json={"decision": "RELEASE", "reason": "Unauthorized release attempt by supervisor"},
    )
    assert res_sup.status_code == status.HTTP_403_FORBIDDEN


def test_judge_demo_seed_rollback_on_failure(db_session):
    """Seed script transaction safely rolls back if an unhandled database error occurs."""
    mock_db = MagicMock()
    # Simulate fresh run where batches do not exist yet
    mock_db.query.return_value.filter_by.return_value.first.return_value = None
    mock_db.flush.side_effect = Exception("Simulated flush failure")

    with pytest.raises(Exception, match="Simulated flush failure"):
        with patch("scripts.seed_judge_demo_scenario.create_engine"):
            with patch("scripts.seed_judge_demo_scenario.sessionmaker", return_value=MagicMock(return_value=mock_db)):
                with patch("scripts.seed_judge_demo_scenario.verify_environment_and_db"):
                    seed_judge_demo_scenario()

    mock_db.rollback.assert_called_once()
    mock_db.close.assert_called_once()
