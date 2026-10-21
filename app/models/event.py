import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import EventStatus, pg_enum

if TYPE_CHECKING:
    from app.models.contribution import Contribution
    from app.models.user import User


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint(
            "target_amount IS NULL OR target_amount >= 0", name="target_amount_nonnegative"
        ),
        Index("ix_events_created_by", "created_by"),
        Index("ix_events_status", "status"),
        Index("ix_events_is_public_status", "is_public", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    event_date: Mapped[date | None] = mapped_column(Date)
    # Whole Indonesian Rupiah.
    target_amount: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[EventStatus] = mapped_column(
        pg_enum(EventStatus, "event_status"),
        default=EventStatus.active,
        server_default=EventStatus.active.value,
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    creator: Mapped["User"] = relationship(back_populates="events")
    contributions: Mapped[list["Contribution"]] = relationship(
        back_populates="event", cascade="all, delete-orphan", passive_deletes=True
    )
