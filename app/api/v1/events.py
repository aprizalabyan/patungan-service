import uuid

from fastapi import APIRouter, Depends, Response

from app.api.deps import CurrentUser, DbSession, PaginationParams, get_current_user
from app.models import EventStatus
from app.schemas.common import Page
from app.schemas.event import EventCreate, EventRead, EventSummary, EventUpdate
from app.services import events as service

router = APIRouter(
    prefix="/events", tags=["events"], dependencies=[Depends(get_current_user)]
)


@router.get("", response_model=Page[EventRead])
def list_events(
    db: DbSession,
    user: CurrentUser,
    pagination: PaginationParams,
    status: EventStatus | None = None,
):
    items, total = service.list_events(
        db,
        user_id=user.id,
        status=status,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return Page(items=items, total=total, page=pagination.page, page_size=pagination.page_size)


@router.post("", response_model=EventRead, status_code=201)
def create_event(body: EventCreate, db: DbSession, user: CurrentUser):
    return service.create_event(db, body, user_id=user.id)


@router.get("/{event_id}", response_model=EventRead)
def get_event(event_id: uuid.UUID, db: DbSession, user: CurrentUser):
    return service.get_event(db, event_id, user_id=user.id)


@router.patch("/{event_id}", response_model=EventRead)
def update_event(event_id: uuid.UUID, body: EventUpdate, db: DbSession, user: CurrentUser):
    return service.update_event(db, event_id, body, user_id=user.id)


@router.delete("/{event_id}", status_code=204)
def delete_event(event_id: uuid.UUID, db: DbSession, user: CurrentUser):
    """Permanently deletes the event AND all of its contributions (cascade).
    The frontend must obtain explicit user confirmation before calling this."""
    service.delete_event(db, event_id, user_id=user.id)
    return Response(status_code=204)


@router.get("/{event_id}/summary", response_model=EventSummary)
def event_summary(event_id: uuid.UUID, db: DbSession, user: CurrentUser):
    event = service.get_event(db, event_id, user_id=user.id)
    return service.get_summary(db, event)
