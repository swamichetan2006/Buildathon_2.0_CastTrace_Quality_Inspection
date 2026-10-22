from datetime import timedelta
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.core.errors import AppException
from backend.app.core.security import create_access_token, get_current_user, verify_password
from backend.app.database import get_db
from backend.app.models.entities import User
from backend.app.schemas.auth import LoginRequest, TokenResponse, UserResponse
from backend.app.services.audit import log_audit_event

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate User & Issue Token",
    description="Authenticates against hashed credentials and returns JWT bearer token.",
)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="INVALID_CREDENTIALS",
            message="Invalid username or password.",
        )

    if not user.is_active:
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="USER_INACTIVE",
            message="User account is deactivated. Contact Quality Management.",
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        data={"sub": user.id, "username": user.username, "role": user.role},
        expires_delta=access_token_expires,
    )

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    log_audit_event(
        db=db,
        actor_id=user.id,
        action="USER_LOGIN",
        entity_type="users",
        entity_id=user.id,
        ip_address=client_ip,
        user_agent=user_agent,
    )
    db.commit()

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_seconds=int(access_token_expires.total_seconds()),
        user=UserResponse.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Current User Profile",
    description="Returns authenticated caller identity and active role.",
)
def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)
