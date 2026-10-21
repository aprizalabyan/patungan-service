import enum

from sqlalchemy import Enum


class EventStatus(str, enum.Enum):
    active = "active"
    completed = "completed"


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"


def pg_enum(enum_cls: type[enum.Enum], name: str) -> Enum:
    """Named PostgreSQL enum that stores member *values* (lowercase), not names."""
    return Enum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e])
