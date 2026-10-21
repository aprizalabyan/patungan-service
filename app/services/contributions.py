import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.errors import ApiError, not_found
from app.models import Contribution, Event, Friend, PaymentStatus
from app.schemas.contribution import ContributionCreate, ContributionUpdate


def list_contributions(
    db: Session,
    event_id: uuid.UUID,
    *,
    payment_status: PaymentStatus | None,
    page: int,
    page_size: int,
) -> tuple[list[Contribution], int]:
    stmt = select(Contribution).where(Contribution.event_id == event_id)
    if payment_status is not None:
        stmt = stmt.where(Contribution.payment_status == payment_status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.join(Contribution.friend)
        .options(joinedload(Contribution.friend))
        .order_by(Friend.name, Contribution.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(items), total


def list_public_participants(db: Session, event_id: uuid.UUID) -> list[Contribution]:
    """At most one row per friend per event, so this is bounded by the friend list."""
    return list(
        db.scalars(
            select(Contribution)
            .join(Contribution.friend)
            .options(joinedload(Contribution.friend))
            .where(Contribution.event_id == event_id)
            .order_by(Friend.name, Contribution.id)
        ).all()
    )


def get_contribution(
    db: Session, contribution_id: uuid.UUID, *, user_id: uuid.UUID
) -> Contribution:
    contribution = db.scalar(
        select(Contribution)
        .join(Contribution.event)
        .options(joinedload(Contribution.friend))
        .where(Contribution.id == contribution_id, Event.created_by == user_id)
    )
    if contribution is None:
        raise not_found("Contribution")
    return contribution


def create_contribution(
    db: Session, event: Event, data: ContributionCreate
) -> Contribution:
    friend = db.get(Friend, data.friend_id)
    if friend is None:
        raise not_found("Friend")
    duplicate = ApiError(
        409,
        "duplicate_contribution",
        "This friend already has a contribution in this event",
    )
    exists = db.scalar(
        select(Contribution.id).where(
            Contribution.event_id == event.id, Contribution.friend_id == friend.id
        )
    )
    if exists:
        raise duplicate

    contribution = Contribution(
        event_id=event.id,
        friend_id=friend.id,
        amount=data.amount,
        notes=data.notes,
        payment_status=PaymentStatus.pending,
    )
    db.add(contribution)
    try:
        db.commit()  # unique constraint is the real guard against races
    except IntegrityError:
        db.rollback()
        raise duplicate
    contribution.friend = friend
    return contribution


def update_contribution(
    db: Session, contribution_id: uuid.UUID, data: ContributionUpdate, *, user_id: uuid.UUID
) -> Contribution:
    contribution = get_contribution(db, contribution_id, user_id=user_id)
    changes = data.model_dump(exclude_unset=True)

    new_status = changes.pop("payment_status", None)
    if new_status is not None and new_status != contribution.payment_status:
        contribution.payment_status = new_status
        contribution.paid_at = (
            datetime.now(timezone.utc) if new_status == PaymentStatus.paid else None
        )
    # Remaining fields (amount, notes) never touch payment_status / paid_at.
    for field, value in changes.items():
        setattr(contribution, field, value)

    db.commit()
    return contribution


def delete_contribution(
    db: Session, contribution_id: uuid.UUID, *, user_id: uuid.UUID
) -> None:
    contribution = get_contribution(db, contribution_id, user_id=user_id)
    db.delete(contribution)
    db.commit()
