import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Index,
    text,
    JSON,
)
from sqlalchemy.orm import relationship

from backend.app.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(128), nullable=False)
    role = Column(String(32), nullable=False)  # INSPECTOR, SUPERVISOR, QUALITY_MANAGER, ADMIN
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, onupdate=get_utc_now)

    # Relationships
    batches_created = relationship("Batch", back_populates="creator", foreign_keys="Batch.created_by")
    inspections = relationship("Inspection", back_populates="inspector", foreign_keys="Inspection.inspector_id")
    reviews = relationship("Review", back_populates="reviewer", foreign_keys="Review.reviewer_id")
    actions_assigned = relationship("CorrectiveAction", back_populates="assignee", foreign_keys="CorrectiveAction.assigned_to")
    actions_created = relationship("CorrectiveAction", back_populates="creator", foreign_keys="CorrectiveAction.assigned_by")
    batch_decisions = relationship("BatchDecision", back_populates="decider", foreign_keys="BatchDecision.decided_by")


class Product(Base):
    __tablename__ = "products"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    sku = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    material = Column(String(64), nullable=False)
    drawing_number = Column(String(64), nullable=True)
    nominal_weight_kg = Column(Numeric(8, 3), nullable=True)
    specifications = Column(JSON, nullable=True)
    is_archived = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, onupdate=get_utc_now)

    batches = relationship("Batch", back_populates="product")


class Batch(Base):
    __tablename__ = "batches"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    batch_number = Column(String(64), unique=True, nullable=False, index=True)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False, index=True)
    manufacture_date = Column(Date, nullable=False)
    heat_number = Column(String(64), nullable=True)
    declared_quantity = Column(Integer, nullable=False)
    status = Column(String(32), nullable=False, default="IN_PRODUCTION")
    notes = Column(Text, nullable=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, onupdate=get_utc_now)

    product = relationship("Product", back_populates="batches")
    creator = relationship("User", back_populates="batches_created", foreign_keys=[created_by])
    inspections = relationship("Inspection", back_populates="batch")
    images = relationship("Image", back_populates="batch")
    decisions = relationship("BatchDecision", back_populates="batch")


class Inspection(Base):
    __tablename__ = "inspections"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    inspection_number = Column(String(64), unique=True, nullable=False, index=True)
    batch_id = Column(String(36), ForeignKey("batches.id"), nullable=False, index=True)
    inspector_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    stage = Column(String(32), nullable=False, default="FINAL_VISUAL")
    status = Column(String(32), nullable=False, default="DRAFT")
    sampling_plan = Column(String(64), nullable=False, default="AQL_LEVEL_II")
    started_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, onupdate=get_utc_now)

    batch = relationship("Batch", back_populates="inspections")
    inspector = relationship("User", back_populates="inspections", foreign_keys=[inspector_id])
    items = relationship("InspectionItem", back_populates="inspection", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="inspection")


class InspectionItem(Base):
    __tablename__ = "inspection_items"
    __table_args__ = (
        UniqueConstraint("inspection_id", "item_identifier", name="uq_inspection_item_identifier"),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    inspection_id = Column(String(36), ForeignKey("inspections.id"), nullable=False, index=True)
    item_identifier = Column(String(64), nullable=False)
    cavity_number = Column(Integer, nullable=True)
    status = Column(String(32), nullable=False, default="PENDING")
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, onupdate=get_utc_now)

    inspection = relationship("Inspection", back_populates="items")
    images = relationship("Image", back_populates="inspection_item")
    reviews = relationship("Review", back_populates="inspection_item")
    defects = relationship("Defect", back_populates="inspection_item")


class Image(Base):
    __tablename__ = "images"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    inspection_item_id = Column(String(36), ForeignKey("inspection_items.id"), nullable=True, index=True)
    batch_id = Column(String(36), ForeignKey("batches.id"), nullable=False, index=True)
    image_scope = Column(String(32), nullable=False, default="ITEM")  # ITEM, SURFACE, BATCH_SAMPLE
    surface_location = Column(String(64), nullable=True)
    represented_item_count = Column(Integer, nullable=False, default=1)
    storage_path = Column(String(512), nullable=False)
    original_filename = Column(String(255), nullable=False)
    mime_type = Column(String(64), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    sha256_hash = Column(String(64), nullable=False, index=True)
    is_superseded = Column(Boolean, nullable=False, default=False)
    superseded_by_id = Column(String(36), ForeignKey("images.id"), nullable=True)
    supersede_reason = Column(Text, nullable=True)
    uploaded_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)

    inspection_item = relationship("InspectionItem", back_populates="images")
    batch = relationship("Batch", back_populates="images")
    uploader = relationship("User", foreign_keys=[uploaded_by])
    superseded_by = relationship("Image", remote_side=[id], foreign_keys=[superseded_by_id])
    model_runs = relationship("ModelRun", back_populates="image")


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    version_name = Column(String(64), unique=True, nullable=False)
    model_architecture = Column(String(64), nullable=False)
    weights_path = Column(String(512), nullable=False)
    weights_sha256 = Column(String(64), nullable=True)
    unfamiliar_guard_sha256 = Column(String(64), nullable=True)
    training_dataset_info = Column(JSON, nullable=False)
    metrics = Column(JSON, nullable=False)
    is_active = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)

    model_runs = relationship("ModelRun", back_populates="model_version")


class ModelRun(Base):
    __tablename__ = "model_runs"
    __table_args__ = (
        Index(
            "uq_active_model_run",
            "image_id",
            "model_version_id",
            unique=True,
            sqlite_where=text("status IN ('QUEUED', 'PROCESSING')"),
            postgresql_where=text("status IN ('QUEUED', 'PROCESSING')"),
        ),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    logical_run_id = Column(String(36), nullable=False, default=generate_uuid, index=True)
    image_id = Column(String(36), ForeignKey("images.id"), nullable=False, index=True)
    model_version_id = Column(String(36), ForeignKey("model_versions.id"), nullable=True)
    status = Column(String(32), nullable=False, default="QUEUED")  # QUEUED, PROCESSING, SUCCEEDED, FAILED, CANCELLED
    predicted_label = Column(String(32), nullable=True)  # Strictly binary: GOOD or DEFECTIVE
    score = Column(Numeric(6, 5), nullable=True)
    score_type = Column(String(64), nullable=False, default="PROBABILITY_DEFECTIVE")
    threshold_applied = Column(Numeric(6, 5), nullable=False, default=0.50000)
    routing_outcome = Column(String(32), nullable=True)  # LIKELY_OK, NEEDS_REVIEW, LIKELY_DEFECTIVE
    routing_reason = Column(Text, nullable=True)
    processing_latency_ms = Column(Integer, nullable=True)
    attempt_number = Column(Integer, nullable=False, default=1)
    parent_run_id = Column(String(36), ForeignKey("model_runs.id"), nullable=True)
    claimed_by_worker_id = Column(String(64), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    error_code = Column(String(64), nullable=True)
    is_retryable = Column(Boolean, nullable=True, default=True)
    error_details = Column(JSON, nullable=True)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)

    image = relationship("Image", back_populates="model_runs")
    model_version = relationship("ModelVersion", back_populates="model_runs")
    parent_run = relationship("ModelRun", remote_side=[id], foreign_keys=[parent_run_id])
    reviews = relationship("Review", back_populates="model_run")


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"

    worker_id = Column(String(64), primary_key=True)
    status = Column(String(32), nullable=False, default="STARTING")  # STARTING, READY, OFFLINE, BUSY
    started_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    last_heartbeat_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    model_version_id = Column(String(36), ForeignKey("model_versions.id"), nullable=True)
    model_ready = Column(Boolean, nullable=False, default=False)
    last_error_code = Column(String(64), nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, onupdate=get_utc_now)

    model_version = relationship("ModelVersion", foreign_keys=[model_version_id])


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("inspection_item_id", "reviewer_id", "created_at", name="uq_review_item_reviewer_time"),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    inspection_id = Column(String(36), ForeignKey("inspections.id"), nullable=False, index=True)
    inspection_item_id = Column(String(36), ForeignKey("inspection_items.id"), nullable=False, index=True)
    model_run_id = Column(String(36), ForeignKey("model_runs.id"), nullable=True)
    reviewer_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    decision = Column(String(32), nullable=False)  # CONFIRMED_GOOD, CONFIRMED_DEFECTIVE, DISPUTED, REQUEST_ADDITIONAL_EVIDENCE
    model_disagreement = Column(Boolean, nullable=False, default=False)
    notes = Column(Text, nullable=True)
    ai_snapshot = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)

    inspection = relationship("Inspection", back_populates="reviews")
    inspection_item = relationship("InspectionItem", back_populates="reviews")
    model_run = relationship("ModelRun", back_populates="reviews")
    reviewer = relationship("User", back_populates="reviews", foreign_keys=[reviewer_id])
    defects = relationship("Defect", back_populates="review")


class Defect(Base):
    __tablename__ = "defects"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    defect_number = Column(String(64), unique=True, nullable=False, index=True)
    inspection_item_id = Column(String(36), ForeignKey("inspection_items.id"), nullable=False, index=True)
    review_id = Column(String(36), ForeignKey("reviews.id"), nullable=False, index=True)
    category = Column(String(64), nullable=False)  # BLOWHOLE, SHRINKAGE_POROSITY, PINHOLE, HOT_TEAR, COLD_SHUT, CRACK, SURFACE_ROUGHNESS, INCLUSION, OTHER
    severity = Column(String(32), nullable=False)  # CRITICAL, MAJOR, MINOR
    status = Column(String(32), nullable=False, default="OPEN")  # OPEN, ACTION_ASSIGNED, IN_PROGRESS, PENDING_REINSPECTION, RESOLVED, REOPENED
    surface_location = Column(String(64), nullable=True)
    description = Column(Text, nullable=False)
    evidence_image_id = Column(String(36), ForeignKey("images.id"), nullable=True)
    resolved_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_notes = Column(Text, nullable=True)
    prior_defect_id = Column(String(36), ForeignKey("defects.id"), nullable=True, index=True)
    prior_corrective_action_id = Column(
        String(36),
        ForeignKey("corrective_actions.id", use_alter=True, name="fk_defects_prior_corrective_action_id"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, onupdate=get_utc_now)

    inspection_item = relationship("InspectionItem", back_populates="defects")
    review = relationship("Review", back_populates="defects")
    evidence_image = relationship("Image", foreign_keys=[evidence_image_id])
    resolver = relationship("User", foreign_keys=[resolved_by])
    prior_defect = relationship("Defect", remote_side=[id], foreign_keys=[prior_defect_id])
    prior_corrective_action = relationship("CorrectiveAction", foreign_keys=[prior_corrective_action_id])
    corrective_actions = relationship("CorrectiveAction", back_populates="defect", foreign_keys="CorrectiveAction.defect_id")
    reinspections = relationship("Reinspection", back_populates="defect")


class CorrectiveAction(Base):
    __tablename__ = "corrective_actions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    action_number = Column(String(64), unique=True, nullable=False, index=True)
    defect_id = Column(String(36), ForeignKey("defects.id"), nullable=False, index=True)
    title = Column(String(128), nullable=False)
    action_type = Column(String(32), nullable=False, default="REWORK")
    description = Column(Text, nullable=False)
    assigned_to = Column(String(36), ForeignKey("users.id"), nullable=False)
    assigned_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    status = Column(String(32), nullable=False, default="OPEN")  # OPEN, IN_PROGRESS, COMPLETED, CANCELLED
    due_date = Column(Date, nullable=False)
    root_cause = Column(Text, nullable=True)
    preventive_action = Column(Text, nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    completion_notes = Column(Text, nullable=True)
    completion_evidence_image_id = Column(String(36), ForeignKey("images.id"), nullable=True)
    verified_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verification_notes = Column(Text, nullable=True)
    verification_status = Column(String(32), nullable=True, default="PENDING")  # PENDING, VERIFIED, REJECTED
    rejection_reason = Column(Text, nullable=True)
    verification_history = Column(JSON, nullable=True, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, onupdate=get_utc_now)

    defect = relationship("Defect", back_populates="corrective_actions", foreign_keys=[defect_id])
    assignee = relationship("User", back_populates="actions_assigned", foreign_keys=[assigned_to])
    creator = relationship("User", back_populates="actions_created", foreign_keys=[assigned_by])
    verifier = relationship("User", foreign_keys=[verified_by])
    completion_evidence = relationship("Image", foreign_keys=[completion_evidence_image_id])
    reinspections = relationship("Reinspection", back_populates="corrective_action")


class Reinspection(Base):
    __tablename__ = "reinspections"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    defect_id = Column(String(36), ForeignKey("defects.id"), nullable=False, index=True)
    corrective_action_id = Column(String(36), ForeignKey("corrective_actions.id"), nullable=False, index=True)
    original_inspection_id = Column(String(36), ForeignKey("inspections.id"), nullable=False)
    followup_inspection_id = Column(String(36), ForeignKey("inspections.id"), nullable=False)
    outcome = Column(String(32), nullable=False)  # DEFECT_RESOLVED, DEFECT_RECURRED_REOPENED
    notes = Column(Text, nullable=True)
    evidence_image_id = Column(String(36), ForeignKey("images.id"), nullable=True)
    verified_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)

    defect = relationship("Defect", back_populates="reinspections")
    corrective_action = relationship("CorrectiveAction", back_populates="reinspections")
    original_inspection = relationship("Inspection", foreign_keys=[original_inspection_id])
    followup_inspection = relationship("Inspection", foreign_keys=[followup_inspection_id])
    verifier = relationship("User", foreign_keys=[verified_by])
    evidence_image = relationship("Image", foreign_keys=[evidence_image_id])


class BatchDecision(Base):
    __tablename__ = "batch_decisions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    batch_id = Column(String(36), ForeignKey("batches.id"), nullable=False, index=True)
    decision = Column(String(32), nullable=False)  # RELEASE, HOLD (Core); REJECT_SCRAP, CONCESSION_DEVIATION (Optional Extensions)
    reason = Column(Text, nullable=False)
    decided_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    conditions = Column(Text, nullable=True)
    snapshot = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)

    batch = relationship("Batch", back_populates="decisions")
    decider = relationship("User", back_populates="batch_decisions", foreign_keys=[decided_by])


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    actor_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    action = Column(String(64), nullable=False)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(String(36), nullable=False, index=True)
    previous_state = Column(JSON, nullable=True)
    new_state = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, index=True)

    actor = relationship("User", foreign_keys=[actor_id])


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    key = Column(String(128), unique=True, nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    endpoint = Column(String(128), nullable=False)
    request_hash = Column(String(64), nullable=False)
    response_code = Column(Integer, nullable=True)
    response_body = Column(JSON, nullable=True)
    status = Column(String(32), nullable=False, default="IN_PROGRESS")  # IN_PROGRESS, COMPLETED, FAILED
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)

    user = relationship("User", foreign_keys=[user_id])


class GenAIQuery(Base):
    __tablename__ = "genai_queries"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    query_text = Column(Text, nullable=False)
    response_text = Column(Text, nullable=False)
    retrieved_source_ids = Column(JSON, nullable=False)
    model_provider = Column(String(64), nullable=False)
    model_name = Column(String(64), nullable=False)
    is_fallback = Column(Boolean, nullable=False, default=False)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)

    user = relationship("User", foreign_keys=[user_id])


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    token = Column(String(512), unique=True, nullable=False, index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)

