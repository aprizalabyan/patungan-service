import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.schemas.common import ORMModel, PatchModel

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Nickname = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
Phone = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=3, max_length=30, pattern=r"^\+?[0-9][0-9 \-()]*$"
    ),
]


class FriendCreate(BaseModel):
    name: Name
    nickname: Nickname | None = None
    phone: Phone | None = None


class FriendUpdate(PatchModel):
    non_nullable = frozenset({"name"})

    name: Name | None = None
    nickname: Nickname | None = None
    phone: Phone | None = None


class FriendRead(ORMModel):
    id: uuid.UUID
    name: str
    nickname: str | None
    phone: str | None
    created_at: datetime


class FriendBrief(ORMModel):
    """Friend as embedded in management contribution responses."""

    id: uuid.UUID
    name: str
    nickname: str | None
