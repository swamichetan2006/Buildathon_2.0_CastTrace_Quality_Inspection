import hashlib
import os
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, Header, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.core.errors import AppException
from backend.app.core.idempotency import check_idempotency_key, record_idempotency_result
from backend.app.core.security import get_current_user, require_roles
from backend.app.database import get_db
from backend.app.models.entities import Batch, Image, InspectionItem, User
from backend.app.schemas.images import ImageResponse, ImageSupersedeRequest
from backend.app.services.audit import log_audit_event

router = APIRouter(prefix="/images", tags=["Images & Evidence"])

# Magic bytes signatures
JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def detect_and_validate_image_type(content: bytes) -> str:
    """Validates magic bytes for JPEG and PNG formats."""
    if content.startswith(JPEG_MAGIC):
        return "image/jpeg", ".jpg"
    elif content.startswith(PNG_MAGIC):
        return "image/png", ".png"
    raise AppException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        code="UNSUPPORTED_MEDIA",
        message="Unsupported media type or corrupt image header. Only valid JPEG and PNG files are accepted.",
    )


@router.post(
    "/upload",
    response_model=ImageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Photographic Evidence",
    description="Uploads visual evidence with magic-byte validation, 10MB limit, SHA-256 hashing, and immutable storage.",
)
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    batch_id: str = Form(...),
    inspection_item_id: Optional[str] = Form(None),
    image_scope: str = Form("ITEM"),
    surface_location: Optional[str] = Form(None),
    represented_item_count: int = Form(1),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: User = Depends(require_roles(["INSPECTOR", "QUALITY_MANAGER"])),
    db: Session = Depends(get_db),
) -> ImageResponse:
    # Validate scope enum
    valid_scopes = ["ITEM", "SURFACE", "BATCH_SAMPLE"]
    if image_scope not in valid_scopes:
        raise AppException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="INVALID_IMAGE_SCOPE",
            message=f"image_scope must be one of: {valid_scopes}",
        )

    # Validate batch
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="BATCH_NOT_FOUND",
            message=f"Target batch with ID '{batch_id}' was not found.",
        )

    # Validate inspection item if provided
    if inspection_item_id:
        item = db.query(InspectionItem).filter(InspectionItem.id == inspection_item_id).first()
        if not item:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="ITEM_NOT_FOUND",
                message=f"Target inspection item with ID '{inspection_item_id}' was not found.",
            )
        if item.inspection.batch_id != batch_id:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="BATCH_ITEM_MISMATCH",
                message="The specified inspection item does not belong to the declared batch.",
            )
    elif image_scope != "BATCH_SAMPLE":
        raise AppException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="ITEM_REQUIRED_FOR_SCOPE",
            message="inspection_item_id is required when image_scope is 'ITEM' or 'SURFACE'.",
        )

    if represented_item_count < 1:
        raise AppException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="INVALID_ITEM_COUNT",
            message="represented_item_count must be at least 1.",
        )

    # Read and validate file content
    contents = await file.read()
    file_size = len(contents)

    if file_size > settings.MAX_UPLOAD_SIZE_BYTES:
        raise AppException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            code="PAYLOAD_TOO_LARGE",
            message=f"Uploaded file size ({file_size} bytes) exceeds maximum allowable limit of 10 MB ({settings.MAX_UPLOAD_SIZE_BYTES} bytes).",
        )

    if file_size == 0:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="EMPTY_FILE",
            message="Uploaded file is empty (0 bytes).",
        )

    mime_type, ext = detect_and_validate_image_type(contents)
    sha256_hash = hashlib.sha256(contents).hexdigest()

    # Generate secure UUID filename and ensure storage directory exists
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    image_uuid = str(uuid.uuid4())
    stored_filename = f"{image_uuid}{ext}"
    full_path = os.path.join(settings.STORAGE_DIR, stored_filename)

    # Path traversal protection: Guarantee full_path is confined strictly inside STORAGE_DIR
    abs_storage_dir = os.path.abspath(settings.STORAGE_DIR)
    abs_full_path = os.path.abspath(full_path)
    if os.path.commonpath([abs_full_path, abs_storage_dir]) != abs_storage_dir:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_DESTINATION_PATH",
            message="Resolved destination path escapes the configured evidence storage directory.",
        )

    with open(abs_full_path, "wb") as f:
        f.write(contents)

    image_record = Image(
        id=image_uuid,
        inspection_item_id=inspection_item_id,
        batch_id=batch_id,
        image_scope=image_scope,
        surface_location=surface_location,
        represented_item_count=represented_item_count,
        storage_path=full_path,
        original_filename=file.filename or f"upload{ext}",
        mime_type=mime_type,
        file_size_bytes=file_size,
        sha256_hash=sha256_hash,
        is_superseded=False,
        uploaded_by=current_user.id,
    )
    db.add(image_record)
    db.flush()

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    log_audit_event(
        db=db,
        actor_id=current_user.id,
        action="IMAGE_UPLOADED",
        entity_type="images",
        entity_id=image_record.id,
        new_state={
            "image_scope": image_scope,
            "file_size_bytes": file_size,
            "sha256_hash": sha256_hash,
            "original_filename": file.filename,
        },
        ip_address=client_ip,
        user_agent=user_agent,
    )
    db.commit()
    db.refresh(image_record)

    resp_data = ImageResponse.model_validate(image_record)
    record_idempotency_result(
        db=db,
        key=idempotency_key,
        user=current_user,
        response_code=status.HTTP_201_CREATED,
        response_body=resp_data.model_dump(mode="json"),
    )
    return resp_data


@router.get(
    "/{image_id}",
    response_model=ImageResponse,
    summary="Get Image Metadata",
    description="Retrieves metadata for an uploaded evidence photograph.",
)
def get_image_metadata(
    image_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ImageResponse:
    image = db.query(Image).filter(Image.id == image_id).first()
    if not image:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="IMAGE_NOT_FOUND",
            message=f"Evidence image with ID '{image_id}' was not found.",
        )
    return ImageResponse.model_validate(image)


@router.get(
    "/{image_id}/content",
    summary="Download Evidence Image Binary",
    description="Streams private evidence photo binary. Protected: requires authentication.",
)
def get_image_content(
    image_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    image = db.query(Image).filter(Image.id == image_id).first()
    if not image:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="IMAGE_NOT_FOUND",
            message=f"Evidence image with ID '{image_id}' was not found.",
        )

    # Path traversal protection: Ensure storage_path resides within configured STORAGE_DIR
    abs_storage_dir = os.path.abspath(settings.STORAGE_DIR)
    abs_file_path = os.path.abspath(image.storage_path)
    if os.path.commonpath([abs_file_path, abs_storage_dir]) != abs_storage_dir:
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="ACCESS_DENIED",
            message="Evidence path security violation: Path escapes the authorized evidence storage repository.",
        )

    if not os.path.exists(abs_file_path):
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="FILE_MISSING",
            message="Evidence file not found in local storage repository.",
        )

    return FileResponse(
        path=abs_file_path,
        media_type=image.mime_type,
        filename=image.original_filename,
        headers={"Cache-Control": "private, max-age=86400"},
    )


@router.post(
    "/{image_id}/supersede",
    response_model=ImageResponse,
    summary="Mark Image as Superseded",
    description="Marks previous evidence as superseded by newer image, preserving chain of custody.",
)
def supersede_image(
    image_id: str,
    payload: ImageSupersedeRequest,
    request: Request,
    current_user: User = Depends(require_roles(["INSPECTOR", "QUALITY_MANAGER"])),
    db: Session = Depends(get_db),
) -> ImageResponse:
    image = db.query(Image).filter(Image.id == image_id).first()
    if not image:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="IMAGE_NOT_FOUND",
            message=f"Original evidence image with ID '{image_id}' was not found.",
        )

    # Validate replacement image exists
    replacement = db.query(Image).filter(Image.id == payload.superseded_by_id).first()
    if not replacement:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="REPLACEMENT_IMAGE_NOT_FOUND",
            message=f"Replacement image with ID '{payload.superseded_by_id}' does not exist.",
        )

    image.is_superseded = True
    image.superseded_by_id = payload.superseded_by_id
    image.supersede_reason = payload.supersede_reason

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    log_audit_event(
        db=db,
        actor_id=current_user.id,
        action="IMAGE_SUPERSEDED",
        entity_type="images",
        entity_id=image.id,
        new_state={"is_superseded": True, "superseded_by_id": payload.superseded_by_id, "reason": payload.supersede_reason},
        ip_address=client_ip,
        user_agent=user_agent,
    )
    db.commit()
    db.refresh(image)
    return ImageResponse.model_validate(image)
