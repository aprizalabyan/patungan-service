import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.models.enums import EventStatus, PaymentStatus
from app.schemas.common import MAX_AMOUNT, ORMModel, PatchModel

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]
TargetAmount = Annotated[int, Field(ge=0, le=MAX_AMOUNT)]


class EventCreate(BaseModel):
    title: Title
    description: Description | None = None
    event_date: date | None = None
    target_amount: TargetAmount | None = None
    status: EventStatus = EventStatus.active
    is_public: bool = True


class EventUpdate(PatchModel):
    non_nullable = frozenset({"title", "status", "is_public"})

    title: Title | None = None
    description: Description | None = None
    event_date: date | None = None
    target_amount: TargetAmount | None = None
    status: EventStatus | None = None
    is_public: bool | None = None


class EventRead(ORMModel):
    id: uuid.UUID
    title: str
    description: str | None
    event_date: date | None
    target_amount: int | None
    status: EventStatus
    is_public: bool
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class EventSummary(BaseModel):
    """Aggregates computed from contribution rows. All money is integer Rupiah.

    `progress_percent` = floor(total_collected * 100 / target_amount). It is NOT
    capped at 100 (over-collection shows e.g. 120) and is null when the target
    is missing or zero, since progress is undefined then.
    """

    event_id: uuid.UUID
    total_participants: int
    paid_count: int
    pending_count: int
    total_collected: int
    total_pending: int
    target_amount: int | None
    progress_percent: int | None


# --- Public (read-only, unauthenticated) --------------------------------------
# These schemas are an explicit allow-list. Do not add fields just because the
# ORM model has them.


class PublicEventRead(ORMModel):
    """Public event: no creator, no timestamps, no visibility flag."""

    id: uuid.UUID
    title: str
    description: str | None
    event_date: date | None
    target_amount: int | None
    status: EventStatus


class PublicParticipant(BaseModel):
    """Privacy: a participant's *display name* and paid/pending status are
    visible to anyone who has the event link. Amounts, phone numbers, notes,
    nicknames and payment timestamps are not exposed."""

    name: str
    payment_status: PaymentStatus


class PublicEventDetail(PublicEventRead):
    participants: list[PublicParticipant]
