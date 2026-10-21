import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import not_found
from app.models import Contribution, Event, EventStatus, PaymentStatus
from app.schemas.event import EventCreate, EventSummary, EventUpdate


def list_events(
    db: Session,
    *,
    user_id: uuid.UUID,
    status: EventStatus | None,
    page: int,
    page_size: int,
) -> tuple[list[Event], int]:
    stmt = select(Event).where(Event.created_by == user_id)
    if status is not None:
        stmt = stmt.where(Event.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.order_by(Event.created_at.desc(), Event.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(items), total


def list_public_events(
    db: Session, *, status: EventStatus | None, page: int, page_size: int
) -> tuple[list[Event], int]:
    stmt = select(Event).where(Event.is_public.is_(True))
    if status is not None:
        stmt = stmt.where(Event.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.order_by(Event.created_at.desc(), Event.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(items), total


def get_event(db: Session, event_id: uuid.UUID, *, user_id: uuid.UUID | None = None) -> Event:
    """Management lookup. Single-treasurer MVP: events are scoped to their creator."""
    event = db.get(Event, event_id)
    if event is None or (user_id is not None and event.created_by != user_id):
        raise not_found("Event")
    return event


def get_public_event(db: Session, event_id: uuid.UUID) -> Event:
    """Visibility is enforced here, independent of any authentication.
    Private events are reported as 404 so their existence is not revealed."""
    event = db.scalar(select(Event).where(Event.id == event_id, Event.is_public.is_(True)))
    if event is None:
        raise not_found("Event")
    return event


def create_event(db: Session, data: EventCreate, *, user_id: uuid.UUID) -> Event:
    event = Event(**data.model_dump(), created_by=user_id)
    db.add(event)
    db.commit()
    return event


def update_event(
    db: Session, event_id: uuid.UUID, data: EventUpdate, *, user_id: uuid.UUID
) -> Event:
    event = get_event(db, event_id, user_id=user_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(event, field, value)
    db.commit()
    return event


def delete_event(db: Session, event_id: uuid.UUID, *, user_id: uuid.UUID) -> None:
    """Deletes the event; its contributions go with it via ON DELETE CASCADE."""
    event = get_event(db, event_id, user_id=user_id)
    db.delete(event)
    db.commit()


def get_summary(db: Session, event: Event) -> EventSummary:
    paid = Contribution.payment_status == PaymentStatus.paid
    pending = Contribution.payment_status == PaymentStatus.pending
    row = db.execute(
        select(
            func.count(Contribution.id),
            func.count(Contribution.id).filter(paid),
            func.count(Contribution.id).filter(pending),
            func.coalesce(func.sum(Contribution.amount).filter(paid), 0),
            func.coalesce(func.sum(Contribution.amount).filter(pending), 0),
        ).where(Contribution.event_id == event.id)
    ).one()
    total, paid_count, pending_count, collected, pending_amount = (int(v) for v in row)

    progress = None
    if event.target_amount:  # None or 0 -> undefined
        progress = collected * 100 // event.target_amount

    return EventSummary(
        event_id=event.id,
        total_participants=total,
        paid_count=paid_count,
        pending_count=pending_count,
        total_collected=collected,
        total_pending=pending_amount,
        target_amount=event.target_amount,
        progress_percent=progress,
    )
