# Patungan Backend

REST API for managing contributions collected from friends to buy wedding gifts.
FastAPI · SQLAlchemy 2 · PostgreSQL (Psycopg 3) · Alembic · Pydantic v2.

One application role exists: the **treasurer**. The treasurer logs in and manages friends, events and
contributions. Everyone else uses read-only, unauthenticated `/api/v1/public/...` endpoints for events marked public.

## Local setup

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows   (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
cp .env.example .env              # then edit values
```

> `psycopg[binary]` has no wheel for Windows-on-ARM + very new Python versions. If `pip` fails, use an
> x64 / Python 3.12 interpreter, or run commands in a container (e.g. `python:3.12-slim`).

### PostgreSQL

Create two databases: one for development and one **only** for tests.

```sql
CREATE USER patungan WITH PASSWORD 'change-me';
CREATE DATABASE patungan_db   OWNER patungan;
CREATE DATABASE patungan_test OWNER patungan;
```

Or with Docker:

```bash
docker run -d --name patungan-db -p 127.0.0.1:5432:5432 \
  -e POSTGRES_USER=patungan -e POSTGRES_PASSWORD=change-me -e POSTGRES_DB=patungan_db postgres:17-alpine
docker exec patungan-db psql -U patungan -d patungan_db -c "CREATE DATABASE patungan_test"
```

### Environment (`.env`)

| Variable | Meaning |
|---|---|
| `DATABASE_URL` | `postgresql+psycopg://user:pass@host:5432/patungan_db` (percent-encode special chars, e.g. `@` → `%40`) |
| `TEST_DATABASE_URL` | Test database. Its name **must end in `_test`** or the test suite refuses to start |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins |
| `SECRET_KEY` | JWT signing key, ≥ 32 chars (`python -c "import secrets; print(secrets.token_urlsafe(48))"`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime, default 60 |

`.env` is git-ignored; never commit real credentials.

## Database migrations

The schema is managed **only** by Alembic. The app never creates or alters tables at startup.

```bash
# First time (the initial migration is already generated: alembic/versions/71bc1a343b7e_create_initial_schema.py)
alembic upgrade head
alembic current                   # should print 71bc1a343b7e (head)

# For the record, it was generated with:
alembic revision --autogenerate -m "create initial schema"

# Future schema changes: edit models in app/models, then
alembic revision --autogenerate -m "describe the change"
#   -> REVIEW the generated file in alembic/versions/ (autogenerate misses enum member changes,
#      renames, and data migrations), then:
alembic upgrade head
alembic downgrade -1              # roll back one revision
alembic check                     # fails if models and migrations have drifted
```

Alembic reads `DATABASE_URL` through the app settings and runs with `compare_type=True`.

## Create the treasurer account

There is no public registration endpoint. Create the account from the command line:

```bash
python -m app.cli create-treasurer --name "Bendahara" --email treasurer@example.com
# prompts for the password (hidden, min 8 chars).
# Non-interactive: set PATUNGAN_TREASURER_PASSWORD in the environment instead.
```

## Run

```bash
uvicorn app.main:app --reload
```

* Interactive docs: <http://localhost:8000/docs>
* Health check: `GET /health`

## Tests

```bash
pytest
```

The suite connects to `TEST_DATABASE_URL` only (guarded by the `_test` suffix check), **drops and rebuilds the
`public` schema of that database**, applies the real Alembic migrations, and truncates tables between tests.
Never point `TEST_DATABASE_URL` at a database you care about.

## Authentication

`POST /api/v1/auth/login` returns a short-lived signed JWT (HS256). Send it as `Authorization: Bearer <token>` — the
approach fits a separately hosted frontend (no cookies, so no CSRF surface; CORS is restricted to `CORS_ORIGINS`).
Passwords are hashed with Argon2id. Login failures return one uniform `401` regardless of whether the email exists.

## API examples

```bash
BASE=http://localhost:8000/api/v1

TOKEN=$(curl -s $BASE/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"treasurer@example.com","password":"..."}' | jq -r .access_token)
AUTH="Authorization: Bearer $TOKEN"

# Friend
curl -s $BASE/friends -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"name":"Budi Santoso","nickname":"Budi","phone":"+62 812-3456-7890"}'
curl -s "$BASE/friends?search=budi&page=1&page_size=20" -H "$AUTH"

# Event
curl -s $BASE/events -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"title":"Wedding gift for Rina","target_amount":2000000,"event_date":"2026-12-12","is_public":true}'

# Add a participant, then mark them paid
curl -s $BASE/events/$EVENT_ID/contributions -H "$AUTH" -H 'Content-Type: application/json' \
  -d "{\"friend_id\":\"$FRIEND_ID\",\"amount\":150000}"
curl -s -X PATCH $BASE/contributions/$CONTRIBUTION_ID -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"payment_status":"paid"}'

# Summary (treasurer) and public read-only views (no token)
curl -s $BASE/events/$EVENT_ID/summary -H "$AUTH"
curl -s $BASE/public/events
curl -s $BASE/public/events/$EVENT_ID
curl -s $BASE/public/events/$EVENT_ID/summary
```

## Endpoint overview

| Method & path | Auth | Notes |
|---|---|---|
| `POST /auth/login`, `GET /auth/me` | – / yes | |
| `GET/POST /friends`, `GET/PATCH/DELETE /friends/{id}` | yes | `search`, `page`, `page_size` (max 100) |
| `GET/POST /events`, `GET/PATCH/DELETE /events/{id}` | yes | `status` filter |
| `GET /events/{id}/summary` | yes | |
| `GET/POST /events/{id}/contributions` | yes | `payment_status` filter |
| `PATCH/DELETE /contributions/{id}` | yes | |
| `GET /public/events`, `/public/events/{id}`, `/public/events/{id}/summary` | no | only `is_public=true` events |

## Behaviour worth knowing

* **Errors** always look like `{"error": {"code": "...", "message": "...", "details": ...}}`
  (`validation_error` 422, `not_found` 404, `duplicate_contribution` / `friend_in_use` 409, `not_authenticated` /
  `invalid_credentials` 401).
* **Pagination**: `page` ≥ 1, `page_size` 1–100 (default 20). Lists return `{items, total, page, page_size}`.
* **Payment transitions**: new contributions are `pending`. `pending → paid` sets `paid_at` to now (UTC);
  `paid → pending` clears it; re-sending `paid` keeps the original timestamp; changing the amount never touches status.
* **Summary**: computed in SQL from contribution rows. `total_collected` counts **paid only**; `total_pending` is
  separate. `progress_percent = floor(total_collected × 100 / target_amount)` using integers; it is **not capped at
  100** (over-collection shows e.g. 150) and is `null` when the target is missing or `0`.
* **Deleting an event** permanently deletes all its contributions (`ON DELETE CASCADE`); friends are kept. The frontend
  must ask for explicit confirmation first.
* **Deleting a friend** with any contribution history returns `409 friend_in_use` (`ON DELETE RESTRICT`). Users who
  created events cannot be deleted either.
* **Amounts** are whole Rupiah integers (stored as `BIGINT`, accepted up to 1,000,000,000,000).

## Public endpoints and privacy

Public responses are explicit allow-lists (`app/schemas/event.py`), not ORM dumps:

* Event: `id, title, description, event_date, target_amount, status`. No creator, timestamps or visibility flag.
* Participants: **`name` and `payment_status` only**. Phone numbers, nicknames, notes, individual amounts and
  `paid_at` are never exposed.
* Summary: aggregate counts and totals only.

**Privacy implication:** anyone with an event ID can see which friends joined and who has/hasn't paid, by full name.
Event IDs are unguessable UUIDs but are not secrets once shared. If that is too revealing, set `is_public=false`
(private events return `404`, indistinguishable from nonexistent ones) or change `PublicParticipant` to show only
nicknames/initials.

## Known limitations

* Single treasurer; events are scoped to their creator. No roles, password reset, or token revocation/refresh.
* No login rate limiting — put the API behind a reverse proxy/WAF that provides it.
* No friend deactivation (`is_active`); referenced friends simply cannot be deleted.
* Public participant list is unpaginated (bounded by one row per friend per event).
* Completed events still allow contribution changes.
