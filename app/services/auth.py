from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.security import create_access_token, verify_password
from app.models import User
from app.schemas.auth import TokenResponse


def login(db: Session, email: str, password: str) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == email.lower()))
    # verify_password does equivalent work when user is None (timing parity).
    if not verify_password(password, user.password_hash if user else None) or user is None:
        raise ApiError(
            401,
            "invalid_credentials",
            "Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token, expires_in = create_access_token(user.id)
    return TokenResponse(access_token=token, expires_in=expires_in)
