import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import PaymentStatus, pg_enum

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.friend import Friend


class Contribution(Base):
    __tablename__ = "contributions"
    __table_args__ = (
        # Also serves lookups by event_id alone (leading column).
        UniqueConstraint("event_id", "friend_id", name="uq_contributions_event_friend"),
        CheckConstraint("amount > 0", name="amount_positive"),
        Index("ix_contributions_friend_id", "friend_id"),
        Index("ix_contributions_event_id_payment_status", "event_id", "payment_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE")
    )
    friend_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("friends.id", ondelete="RESTRICT")
    )
    # Whole Indonesian Rupiah.
    amount: Mapped[int] = mapped_column(BigInteger)
    payment_status: Mapped[PaymentStatus] = mapped_column(
        pg_enum(PaymentStatus, "payment_status"),
        default=PaymentStatus.pending,
        server_default=PaymentStatus.pending.value,
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    event: Mapped["Event"] = relationship(back_populates="contributions")
    friend: Mapped["Friend"] = relationship(back_populates="contributions")
