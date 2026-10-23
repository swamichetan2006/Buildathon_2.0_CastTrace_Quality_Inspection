from datetime import datetime, timedelta, timezone
from typing import Callable, List, Optional
import bcrypt
import jwt
from fastapi import Depends, Header, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.core.errors import AppException
from backend.app.database import get_db
from backend.app.models.entities import User

ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=False,
)


def hash_password(plain_password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": now})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="TOKEN_EXPIRED",
            message="Access token has expired. Please log in again.",
        )
    except jwt.PyJWTError:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="INVALID_TOKEN",
            message="Cryptographically invalid authentication token.",
        )


def get_user_by_token(token: str, db: Session) -> User:
    payload = decode_access_token(token)
    user_id: Optional[str] = payload.get("sub")
    if not user_id:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="INVALID_TOKEN",
            message="Token payload is missing subject identity.",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="USER_NOT_FOUND",
            message="User account associated with this token no longer exists.",
        )

    if not user.is_active:
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="USER_INACTIVE",
            message="User account has been deactivated.",
        )

    return user


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not token:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHENTICATED",
            message="Authentication credentials were not provided in request header.",
        )

    return get_user_by_token(token, db)


def require_roles(allowed_roles: List[str]) -> Callable:
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles and current_user.role != "ADMIN":
            raise AppException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="INSUFFICIENT_PERMISSIONS",
                message=f"Access denied. Required roles: {allowed_roles}. Your role: {current_user.role}",
                details={"allowed_roles": allowed_roles, "user_role": current_user.role},
            )
        return current_user

    return role_checker
