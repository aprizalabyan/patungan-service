import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.models.enums import PaymentStatus
from app.schemas.common import MAX_AMOUNT, ORMModel, PatchModel
from app.schemas.friend import FriendBrief

Amount = Annotated[int, Field(gt=0, le=MAX_AMOUNT)]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


class ContributionCreate(BaseModel):
    friend_id: uuid.UUID
    amount: Amount
    notes: Notes | None = None


class ContributionUpdate(PatchModel):
    non_nullable = frozenset({"amount", "payment_status"})

    amount: Amount | None = None
    payment_status: PaymentStatus | None = None
    notes: Notes | None = None


class ContributionRead(ORMModel):
    id: uuid.UUID
    event_id: uuid.UUID
    friend_id: uuid.UUID
    friend: FriendBrief
    amount: int
    payment_status: PaymentStatus
    paid_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
