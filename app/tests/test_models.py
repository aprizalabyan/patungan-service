import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.db.session import engine
from app.models import Contribution, Event, EventStatus, Friend, PaymentStatus, User


def _user(db, email="a@example.com") -> User:
    u = User(name="A", email=email, password_hash="x")
    db.add(u)
    db.flush()
    return u


def _event(db, user, **kw) -> Event:
    e = Event(title="E", created_by=user.id, **kw)
    db.add(e)
    db.flush()
    return e


def test_defaults_and_timestamps(db):
    user = _user(db)
    event = _event(db, user)
    friend = Friend(name="F")
    db.add(friend)
    db.flush()
    c = Contribution(event_id=event.id, friend_id=friend.id, amount=1000)
    db.add(c)
    db.commit()
    db.refresh(c)
    db.refresh(event)
    assert event.status == EventStatus.active
    assert event.is_public is True
    assert c.payment_status == PaymentStatus.pending
    assert c.paid_at is None
    assert c.created_at.tzinfo is not None and event.updated_at.tzinfo is not None


def test_enum_types_are_named_in_postgres():
    with engine.connect() as conn:
        names = {r[0] for r in conn.execute(text("SELECT typname FROM pg_type WHERE typtype='e'"))}
    assert {"event_status", "payment_status"} <= names


def test_unique_email(db):
    _user(db, "dup@example.com")
    with pytest.raises(IntegrityError):
        _user(db, "dup@example.com")


def test_unique_event_friend_pair(db):
    user = _user(db)
    event = _event(db, user)
    friend = Friend(name="F")
    db.add(friend)
    db.flush()
    db.add(Contribution(event_id=event.id, friend_id=friend.id, amount=1))
    db.flush()
    db.add(Contribution(event_id=event.id, friend_id=friend.id, amount=2))
    with pytest.raises(IntegrityError):
        db.flush()


@pytest.mark.parametrize("amount", [0, -5])
def test_contribution_amount_must_be_positive(db, amount):
    user = _user(db)
    event = _event(db, user)
    friend = Friend(name="F")
    db.add(friend)
    db.flush()
    db.add(Contribution(event_id=event.id, friend_id=friend.id, amount=amount))
    with pytest.raises(IntegrityError):
        db.flush()


def test_target_amount_check(db):
    user = _user(db)
    _event(db, user, target_amount=0)  # zero allowed
    _event(db, user, target_amount=None)  # null allowed
    with pytest.raises(IntegrityError):
        _event(db, user, target_amount=-1)


def test_cannot_delete_friend_with_contributions(db):
    user = _user(db)
    event = _event(db, user)
    friend = Friend(name="F")
    db.add(friend)
    db.flush()
    db.add(Contribution(event_id=event.id, friend_id=friend.id, amount=1))
    db.flush()
    with pytest.raises(IntegrityError):
        db.execute(text("DELETE FROM friends WHERE id = :id"), {"id": friend.id})


def test_cannot_delete_user_with_events(db):
    user = _user(db)
    _event(db, user)
    with pytest.raises(IntegrityError):
        db.execute(text("DELETE FROM users WHERE id = :id"), {"id": user.id})


def test_deleting_event_cascades_contributions(db):
    user = _user(db)
    event = _event(db, user)
    friend = Friend(name="F")
    db.add(friend)
    db.flush()
    db.add(Contribution(event_id=event.id, friend_id=friend.id, amount=1))
    db.flush()
    db.execute(text("DELETE FROM events WHERE id = :id"), {"id": event.id})
    assert db.execute(text("SELECT count(*) FROM contributions")).scalar() == 0
    assert db.get(Friend, friend.id) is not None


def test_expected_indexes_exist():
    idx = {i["name"] for i in inspect(engine).get_indexes("contributions")}
    assert {"ix_contributions_friend_id", "ix_contributions_event_id_payment_status"} <= idx
