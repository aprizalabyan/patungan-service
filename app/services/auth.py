import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.config import get_settings
from app.core.security import create_access_token, create_refresh_token, hash_refresh_token, verify_password
from app.models import RefreshToken, User
from app.schemas.auth import TokenResponse

logger = logging.getLogger(__name__)


def _new_refresh(db: Session, user_id: uuid.UUID, family_id: uuid.UUID, ip: str | None, user_agent: str | None) -> str:
    raw = create_refresh_token()
    settings = get_settings()
    db.add(RefreshToken(
        user_id=user_id, family_id=family_id, token_hash=hash_refresh_token(raw),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
        created_by_ip=ip,
        user_agent=user_agent,
    ))
    return raw


def login(db: Session, email: str, password: str, ip: str | None, user_agent: str | None) -> tuple[TokenResponse, str]:
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
    refresh = _new_refresh(db, user.id, uuid.uuid4(), ip, user_agent)
    db.commit()
    return TokenResponse(access_token=token, expires_in=expires_in), refresh


def refresh(db: Session, raw: str | None, ip: str | None, user_agent: str | None) -> tuple[TokenResponse, str]:
    unauthorized = ApiError(401, "invalid_refresh_token", "Refresh token is invalid")
    if not raw:
        raise unauthorized
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw)).with_for_update())
    if row is None:
        raise unauthorized
    now = datetime.now(timezone.utc)
    if row.revoked_at is not None:
        # A request blocked on the row lock may arrive just after its sibling rotated it.
        if row.replaced_by_token_id and (now - row.revoked_at).total_seconds() > 2:
            db.execute(update(RefreshToken).where(RefreshToken.family_id == row.family_id, RefreshToken.revoked_at.is_(None)).values(revoked_at=now))
            db.commit()
            logger.warning("Refresh token reuse detected for family %s", row.family_id)
        raise unauthorized
    if row.expires_at <= now:
        raise unauthorized
    user = db.get(User, row.user_id)
    if user is None:
        raise unauthorized
    new_raw = create_refresh_token()
    new_row = RefreshToken(
        user_id=row.user_id, family_id=row.family_id, token_hash=hash_refresh_token(new_raw),
        expires_at=now + timedelta(days=get_settings().refresh_token_expire_days),
        created_by_ip=ip,
        user_agent=user_agent,
    )
    db.add(new_row)
    row.revoked_at = now
    db.flush()
    row.replaced_by_token_id = new_row.id
    access, expires_in = create_access_token(user.id)
    db.commit()
    return TokenResponse(access_token=access, expires_in=expires_in), new_raw


def logout(db: Session, raw: str | None) -> None:
    if raw:
        row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw)).with_for_update())
        if row and row.revoked_at is None:
            row.revoked_at = datetime.now(timezone.utc)
            db.commit()


def logout_all(db: Session, user_id: uuid.UUID) -> None:
    db.execute(update(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)).values(revoked_at=datetime.now(timezone.utc)))
    db.commit()
