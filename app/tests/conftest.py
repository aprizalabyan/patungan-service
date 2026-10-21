import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, make_url, text

from alembic import command
from alembic.config import Config
from app.core.config import Settings

# --- Safety: tests only ever touch a database whose name ends with "_test". ----
_test_url = Settings().test_database_url  # type: ignore[call-arg]
if not _test_url:
    raise RuntimeError("TEST_DATABASE_URL is not set; refusing to run tests.")
_db_name = make_url(_test_url).database or ""
if not _db_name.endswith("_test"):
    raise RuntimeError(
        f"TEST_DATABASE_URL must point to a database ending in '_test' (got {_db_name!r})."
    )
# Must happen before app modules are imported so the app's engine uses the test DB.
os.environ["DATABASE_URL"] = _test_url

from fastapi.testclient import TestClient  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402

assert engine.url.database == _db_name

ROOT = Path(__file__).resolve().parents[2]
TREASURER_EMAIL = "treasurer@example.com"
TREASURER_PASSWORD = "correct-horse-battery"


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema():
    """Rebuild the test schema from the real Alembic migrations."""
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def _clean_tables(_migrated_schema):
    yield
    with engine.begin() as conn:
        conn.execute(
            text("TRUNCATE contributions, events, friends, users RESTART IDENTITY CASCADE")
        )


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def treasurer(db) -> User:
    user = User(
        name="Bendahara",
        email=TREASURER_EMAIL,
        password_hash=hash_password(TREASURER_PASSWORD),
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def auth(client, treasurer) -> dict[str, str]:
    res = client.post(
        "/api/v1/auth/login",
        json={"email": TREASURER_EMAIL, "password": TREASURER_PASSWORD},
    )
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


# --- Small API helpers ---------------------------------------------------------
@pytest.fixture
def make_friend(client, auth):
    def _make(name: str = "Budi", **extra) -> dict:
        res = client.post("/api/v1/friends", json={"name": name, **extra}, headers=auth)
        assert res.status_code == 201, res.text
        return res.json()

    return _make


@pytest.fixture
def make_event(client, auth):
    def _make(title: str = "Wedding gift", **extra) -> dict:
        res = client.post("/api/v1/events", json={"title": title, **extra}, headers=auth)
        assert res.status_code == 201, res.text
        return res.json()

    return _make


@pytest.fixture
def make_contribution(client, auth):
    def _make(event_id: str, friend_id: str, amount: int = 50_000, **extra) -> dict:
        res = client.post(
            f"/api/v1/events/{event_id}/contributions",
            json={"friend_id": friend_id, "amount": amount, **extra},
            headers=auth,
        )
        assert res.status_code == 201, res.text
        return res.json()

    return _make
