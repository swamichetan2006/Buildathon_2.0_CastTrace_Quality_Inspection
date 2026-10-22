from typing import List, Optional
from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.orm import Session

from backend.app.core.errors import AppException
from backend.app.core.idempotency import check_idempotency_key, record_idempotency_result
from backend.app.core.security import get_current_user, require_roles
from backend.app.database import get_db
from backend.app.models.entities import Product, User
from backend.app.schemas.products import ProductCreate, ProductResponse, ProductUpdate
from backend.app.services.audit import log_audit_event

router = APIRouter(prefix="/products", tags=["Products"])


@router.get(
    "",
    response_model=List[ProductResponse],
    summary="List Products",
    description="Lists casting products with optional archived filtering.",
)
def list_products(
    is_archived: Optional[bool] = Query(False, description="Filter by archived status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[ProductResponse]:
    query = db.query(Product)
    if is_archived is not None:
        query = query.filter(Product.is_archived == is_archived)
    products = query.order_by(Product.created_at.desc()).offset(offset).limit(limit).all()
    return [ProductResponse.model_validate(p) for p in products]


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Get Product Detail",
    description="Retrieves a specific product catalog item by UUID.",
)
def get_product(
    product_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProductResponse:
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="PRODUCT_NOT_FOUND",
            message=f"Product with ID '{product_id}' was not found.",
        )
    return ProductResponse.model_validate(product)


@router.post(
    "",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Product",
    description="Creates a new casting product model. Requires QUALITY_MANAGER role.",
)
def create_product(
    payload: ProductCreate,
    request: Request,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: User = Depends(require_roles(["QUALITY_MANAGER"])),
    db: Session = Depends(get_db),
) -> ProductResponse:
    cached = check_idempotency_key(
        db=db,
        key=idempotency_key,
        user=current_user,
        endpoint=str(request.url.path),
        payload_dict=payload.model_dump(),
    )
    if cached:
        return ProductResponse.model_validate(cached[1])

    existing_sku = db.query(Product).filter(Product.sku == payload.sku).first()
    if existing_sku:
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="SKU_ALREADY_EXISTS",
            message=f"A product with SKU '{payload.sku}' already exists.",
        )

    product = Product(
        sku=payload.sku,
        name=payload.name,
        material=payload.material,
        drawing_number=payload.drawing_number,
        nominal_weight_kg=payload.nominal_weight_kg,
        specifications=payload.specifications,
        is_archived=False,
    )
    db.add(product)
    db.flush()

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    log_audit_event(
        db=db,
        actor_id=current_user.id,
        action="PRODUCT_CREATED",
        entity_type="products",
        entity_id=product.id,
        new_state=payload.model_dump(),
        ip_address=client_ip,
        user_agent=user_agent,
    )
    db.commit()
    db.refresh(product)

    resp_data = ProductResponse.model_validate(product)
    record_idempotency_result(
        db=db,
        key=idempotency_key,
        user=current_user,
        response_code=status.HTTP_201_CREATED,
        response_body=resp_data.model_dump(mode="json"),
    )
    return resp_data


@router.patch(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Update Product",
    description="Updates product specifications or metadata. Requires QUALITY_MANAGER role.",
)
def update_product(
    product_id: str,
    payload: ProductUpdate,
    request: Request,
    current_user: User = Depends(require_roles(["QUALITY_MANAGER"])),
    db: Session = Depends(get_db),
) -> ProductResponse:
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="PRODUCT_NOT_FOUND",
            message=f"Product with ID '{product_id}' was not found.",
        )

    prev_state = {
        "name": product.name,
        "material": product.material,
        "drawing_number": product.drawing_number,
        "nominal_weight_kg": float(product.nominal_weight_kg) if product.nominal_weight_kg else None,
        "specifications": product.specifications,
    }

    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(product, field, val)

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    log_audit_event(
        db=db,
        actor_id=current_user.id,
        action="PRODUCT_UPDATED",
        entity_type="products",
        entity_id=product.id,
        previous_state=prev_state,
        new_state=update_data,
        ip_address=client_ip,
        user_agent=user_agent,
    )
    db.commit()
    db.refresh(product)
    return ProductResponse.model_validate(product)


@router.delete(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Soft-Archive Product",
    description="Soft-archives a product. Historical batches remain intact. Requires QUALITY_MANAGER role.",
)
def archive_product(
    product_id: str,
    request: Request,
    current_user: User = Depends(require_roles(["QUALITY_MANAGER"])),
    db: Session = Depends(get_db),
) -> ProductResponse:
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="PRODUCT_NOT_FOUND",
            message=f"Product with ID '{product_id}' was not found.",
        )

    product.is_archived = True
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    log_audit_event(
        db=db,
        actor_id=current_user.id,
        action="PRODUCT_ARCHIVED",
        entity_type="products",
        entity_id=product.id,
        new_state={"is_archived": True},
        ip_address=client_ip,
        user_agent=user_agent,
    )
    db.commit()
    db.refresh(product)
    return ProductResponse.model_validate(product)
