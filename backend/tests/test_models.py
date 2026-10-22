from datetime import date, datetime, timezone
from backend.app.models.entities import (
    AuditLog,
    Batch,
    BatchDecision,
    CorrectiveAction,
    Defect,
    GenAIQuery,
    IdempotencyKey,
    Image,
    Inspection,
    InspectionItem,
    ModelRun,
    ModelVersion,
    Product,
    Reinspection,
    Review,
    User,
)


def test_models_persistence(db_session):
    """Verify that all core entities from docs/erd.md can be instantiated and saved."""
    # 1. User
    user = User(
        username="persisted_inspector",
        email="persisted_inspector@example.com",
        full_name="Test Inspector",
        role="INSPECTOR",
        hashed_password="fakehashpassword123",
    )

    db_session.add(user)
    db_session.commit()
    assert user.id is not None

    # 2. Product
    product = Product(
        sku="TEST-SKU-001",
        name="Test Impeller 200mm",
        material="CF8M Stainless Steel",
        drawing_number="DWG-001",
        nominal_weight_kg=4.5,
    )
    db_session.add(product)
    db_session.commit()
    assert product.id is not None

    # 3. Batch
    batch = Batch(
        batch_number="TEST-BATCH-001",
        product_id=product.id,
        manufacture_date=date.today(),
        declared_quantity=100,
        status="IN_PRODUCTION",
        created_by=user.id,
    )
    db_session.add(batch)
    db_session.commit()
    assert batch.id is not None

    # 4. Inspection
    inspection = Inspection(
        inspection_number="INSP-TEST-001",
        batch_id=batch.id,
        inspector_id=user.id,
        stage="FINAL_VISUAL",
        status="DRAFT",
    )
    db_session.add(inspection)
    db_session.commit()
    assert inspection.id is not None

    # 5. Inspection Item
    item = InspectionItem(
        inspection_id=inspection.id,
        item_identifier="ITEM-001",
        cavity_number=1,
        status="PENDING",
    )
    db_session.add(item)
    db_session.commit()
    assert item.id is not None

    # 6. Image
    image = Image(
        inspection_item_id=item.id,
        batch_id=batch.id,
        image_scope="ITEM",
        storage_path="storage/evidence/test.jpg",
        original_filename="test.jpg",
        mime_type="image/jpeg",
        file_size_bytes=1024,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        uploaded_by=user.id,
    )
    db_session.add(image)
    db_session.commit()
    assert image.id is not None

    # 7. Model Version
    m_ver = ModelVersion(
        version_name="v1.0-resnet18",
        model_architecture="ResNet-18",
        weights_path="checkpoints/v1.pt",
        training_dataset_info={"samples": 1000},
        metrics={"accuracy": 0.96},
        is_active=True,
    )
    db_session.add(m_ver)
    db_session.commit()
    assert m_ver.id is not None

    # 8. Model Run
    m_run = ModelRun(
        image_id=image.id,
        model_version_id=m_ver.id,
        status="SUCCEEDED",
        predicted_label="DEFECTIVE",
        score=0.92,
        attempt_number=1,
    )
    db_session.add(m_run)
    db_session.commit()
    assert m_run.id is not None

    # 9. Review
    review = Review(
        inspection_id=inspection.id,
        inspection_item_id=item.id,
        model_run_id=m_run.id,
        reviewer_id=user.id,
        decision="CONFIRMED_DEFECTIVE",
        model_disagreement=False,
    )
    db_session.add(review)
    db_session.commit()
    assert review.id is not None

    # 10. Defect
    defect = Defect(
        defect_number="DEF-TEST-001",
        inspection_item_id=item.id,
        review_id=review.id,
        category="CRACK",
        severity="MAJOR",
        description="Linear tear on vane root",
    )
    db_session.add(defect)
    db_session.commit()
    assert defect.id is not None

    # 11. Corrective Action
    action = CorrectiveAction(
        action_number="CAPA-TEST-001",
        defect_id=defect.id,
        title="Grind and inspect",
        description="Rework defect",
        assigned_to=user.id,
        assigned_by=user.id,
        due_date=date.today(),
        status="OPEN",
    )
    db_session.add(action)
    db_session.commit()
    assert action.id is not None

    # 12. Reinspection
    reinspection = Reinspection(
        defect_id=defect.id,
        corrective_action_id=action.id,
        original_inspection_id=inspection.id,
        followup_inspection_id=inspection.id,
        outcome="DEFECT_RESOLVED",
        verified_by=user.id,
    )
    db_session.add(reinspection)
    db_session.commit()
    assert reinspection.id is not None

    # 13. Batch Decision
    decision = BatchDecision(
        batch_id=batch.id,
        decision="RELEASE",
        reason="Quality standards met after reinspection",
        decided_by=user.id,
    )
    db_session.add(decision)
    db_session.commit()
    assert decision.id is not None

    # 14. Audit Log
    audit = AuditLog(
        actor_id=user.id,
        action="BATCH_RELEASED",
        entity_type="batches",
        entity_id=batch.id,
    )
    db_session.add(audit)
    db_session.commit()
    assert audit.id is not None

    # 15. Idempotency Key
    idemp = IdempotencyKey(
        key="idemp-key-test-123",
        user_id=user.id,
        endpoint="/api/v1/inspections",
        request_hash="hash123",
        expires_at=datetime.now(timezone.utc),
    )
    db_session.add(idemp)
    db_session.commit()
    assert idemp.id is not None

    # 16. GenAI Query
    genai = GenAIQuery(
        user_id=user.id,
        query_text="Summarize batch",
        response_text="Batch is good",
        retrieved_source_ids=[{"id": batch.id}],
        model_provider="mock",
        model_name="mock-v1",
    )
    db_session.add(genai)
    db_session.commit()
    assert genai.id is not None
