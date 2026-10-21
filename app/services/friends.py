import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ApiError, not_found
from app.models import Contribution, Friend
from app.schemas.friend import FriendCreate, FriendUpdate


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_friends(
    db: Session, *, search: str | None, page: int, page_size: int
) -> tuple[list[Friend], int]:
    stmt = select(Friend)
    if search and search.strip():
        pattern = f"%{_escape_like(search.strip())}%"
        stmt = stmt.where(
            or_(
                Friend.name.ilike(pattern, escape="\\"),
                Friend.nickname.ilike(pattern, escape="\\"),
                Friend.phone.ilike(pattern, escape="\\"),
            )
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.order_by(Friend.name, Friend.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(items), total


def get_friend(db: Session, friend_id: uuid.UUID) -> Friend:
    friend = db.get(Friend, friend_id)
    if friend is None:
        raise not_found("Friend")
    return friend


def create_friend(db: Session, data: FriendCreate) -> Friend:
    friend = Friend(**data.model_dump())
    db.add(friend)
    db.commit()
    return friend


def update_friend(db: Session, friend_id: uuid.UUID, data: FriendUpdate) -> Friend:
    friend = get_friend(db, friend_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(friend, field, value)
    db.commit()
    return friend


def delete_friend(db: Session, friend_id: uuid.UUID) -> None:
    friend = get_friend(db, friend_id)
    in_use = db.scalar(
        select(func.count()).select_from(Contribution).where(Contribution.friend_id == friend_id)
    )
    if in_use:
        raise _friend_in_use(in_use)
    try:
        db.delete(friend)
        db.commit()
    except IntegrityError:  # contribution added concurrently; FK RESTRICT fired
        db.rollback()
        raise _friend_in_use(None)


def _friend_in_use(count: int | None) -> ApiError:
    return ApiError(
        409,
        "friend_in_use",
        "Friend has contribution history and cannot be deleted",
        {"contributions": count} if count else None,
    )
