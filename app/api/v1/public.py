"""Unauthenticated, read-only endpoints. Only events with is_public=true are
reachable; everything else is a 404. Response shapes are explicit allow-lists
(see app/schemas/event.py)."""

import uuid

from fastapi import APIRouter

from app.api.deps import DbSession, PaginationParams
from app.models import EventStatus
from app.schemas.common import Page
from app.schemas.event import (
    EventSummary,
    PublicEventDetail,
    PublicEventRead,
    PublicParticipant,
)
from app.services import contributions as contribution_service
from app.services import events as service

router = APIRouter(prefix="/public/events", tags=["public"])


@router.get("", response_model=Page[PublicEventRead])
def list_public_events(
    db: DbSession, pagination: PaginationParams, status: EventStatus | None = None
):
    items, total = service.list_public_events(
        db, status=status, page=pagination.page, page_size=pagination.page_size
    )
    return Page(items=items, total=total, page=pagination.page, page_size=pagination.page_size)


@router.get("/{event_id}", response_model=PublicEventDetail)
def get_public_event(event_id: uuid.UUID, db: DbSession):
    event = service.get_public_event(db, event_id)
    participants = [
        PublicParticipant(name=c.friend.name, payment_status=c.payment_status)
        for c in contribution_service.list_public_participants(db, event.id)
    ]
    return PublicEventDetail(
        **PublicEventRead.model_validate(event).model_dump(), participants=participants
    )


@router.get("/{event_id}/summary", response_model=EventSummary)
def get_public_event_summary(event_id: uuid.UUID, db: DbSession):
    event = service.get_public_event(db, event_id)
    return service.get_summary(db, event)
