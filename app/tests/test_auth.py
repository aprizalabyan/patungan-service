import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.config import get_settings
from app.tests.conftest import TREASURER_EMAIL, TREASURER_PASSWORD

PROTECTED = [
    ("GET", "/api/v1/auth/me"),
    ("GET", "/api/v1/friends"),
    ("POST", "/api/v1/friends"),
    ("GET", f"/api/v1/friends/{uuid.uuid4()}"),
    ("GET", "/api/v1/events"),
    ("POST", "/api/v1/events"),
    ("GET", f"/api/v1/events/{uuid.uuid4()}"),
    ("PATCH", f"/api/v1/events/{uuid.uuid4()}"),
    ("DELETE", f"/api/v1/events/{uuid.uuid4()}"),
    ("GET", f"/api/v1/events/{uuid.uuid4()}/summary"),
    ("GET", f"/api/v1/events/{uuid.uuid4()}/contributions"),
    ("POST", f"/api/v1/events/{uuid.uuid4()}/contributions"),
    ("PATCH", f"/api/v1/contributions/{uuid.uuid4()}"),
    ("DELETE", f"/api/v1/contributions/{uuid.uuid4()}"),
]


def test_login_success_and_me(client, treasurer):
    res = client.post(
        "/api/v1/auth/login", json={"email": TREASURER_EMAIL.upper(), "password": TREASURER_PASSWORD}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["token_type"] == "bearer" and body["expires_in"] > 0
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == TREASURER_EMAIL
    assert "password_hash" not in me.json() and "password" not in me.json()


@pytest.mark.parametrize(
    "email,password",
    [(TREASURER_EMAIL, "wrong-password"), ("nobody@example.com", TREASURER_PASSWORD)],
)
def test_login_failure_is_uniform(client, treasurer, email, password):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "invalid_credentials"


def test_login_validation_error_format(client):
    res = client.post("/api/v1/auth/login", json={"email": "not-an-email"})
    assert res.status_code == 422
    err = res.json()["error"]
    assert err["code"] == "validation_error"
    assert {d["field"] for d in err["details"]} >= {"email", "password"}


def test_password_stored_hashed(db, treasurer):
    assert treasurer.password_hash.startswith("$argon2")
    assert TREASURER_PASSWORD not in treasurer.password_hash


@pytest.mark.parametrize("method,path", PROTECTED)
def test_protected_routes_require_token(client, method, path):
    res = client.request(method, path)
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "not_authenticated"
    assert res.headers["www-authenticate"] == "Bearer"


def test_invalid_and_expired_tokens_rejected(client, treasurer):
    s = get_settings()
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer junk"}).status_code == 401
    expired = jwt.encode(
        {"sub": str(treasurer.id), "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        s.secret_key,
        algorithm=s.jwt_algorithm,
    )
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    forged = jwt.encode(
        {"sub": str(treasurer.id), "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        "x" * 40,
        algorithm="HS256",
    )
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_token_for_deleted_user_rejected(client, db, auth, treasurer):
    db.delete(treasurer)
    db.commit()
    assert client.get("/api/v1/auth/me", headers=auth).status_code == 401


def test_no_registration_endpoint(client):
    assert client.post("/api/v1/auth/register", json={}).status_code in (404, 405)


def test_health_and_docs(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/docs").status_code == 200


def test_cors_allows_configured_origin_only(client):
    origin = get_settings().cors_origins[0]
    ok = client.options(
        "/api/v1/friends",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )
    assert ok.headers.get("access-control-allow-origin") == origin
    bad = client.options(
        "/api/v1/friends",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in bad.headers
