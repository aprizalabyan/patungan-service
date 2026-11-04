# Project Context

## What this is

**Patungan** ("chipping in together") helps one person — the **treasurer** — collect money from high-school friends
for wedding gifts. This repository is the **backend REST API only**.

* The treasurer logs in and manages friends (master data), events (a gift collection), and contributions
  (one friend's amount in one event, `pending` or `paid`).
* Other friends have **no accounts**. They can open publicly shared events through read-only endpoints.
* MVP scope: one application role (treasurer). No registration endpoint, no roles column.

## Tech stack (as implemented)

| Area | Choice |
|---|---|
| Language / framework | Python, FastAPI (`/docs` = Swagger UI) |
| ORM | SQLAlchemy 2.x, declarative typed models (`Mapped[...]`), **synchronous** sessions |
| Database | PostgreSQL (uses `gen_random_uuid()`, native enums) |
| Driver | Selected by the `DATABASE_URL` scheme. Intended: Psycopg 3 (`postgresql+psycopg://`). See note below |
| Migrations | Alembic (`alembic/`, one revision so far: `71bc1a343b7e_create_initial_schema`) |
| Validation / settings | Pydantic v2, pydantic-settings (`.env`) |
| Auth | Argon2 (`argon2-cffi`) password hashes, JWT (`PyJWT`, HS256) Bearer tokens |
| Tests | pytest + FastAPI `TestClient` (HTTPX), real PostgreSQL test database |

> **Driver note.** The code is driver-agnostic (it only passes `DATABASE_URL` to `create_engine`). The original
> design and `README.md` use Psycopg 3. `requirements.txt` is currently a full `pip freeze` that includes both
> `psycopg` (without `[binary]`, so it needs a system libpq) and `pg8000`, and `.env.example` currently shows a
> `postgresql+pg8000://` URL (a pure-Python driver that works where psycopg's binary wheel is unavailable, e.g. Windows
> on ARM). The test suite and migrations were verified with `postgresql+psycopg` only; behaviour with pg8000 has not
> been verified by the author of this documentation. Pick one driver for your environment and keep the URL consistent
> in `.env` and `TEST_DATABASE_URL`.

## Repository layout

```
app/
  main.py            FastAPI app, CORS, error handlers, /health, mounts /api/v1
  cli.py             `python -m app.cli create-treasurer`
  core/              config.py (settings), security.py (hash + JWT), errors.py (ApiError + handlers)
  db/                base.py (Base + naming convention), session.py (engine, SessionLocal, get_db)
  models/            user, friend, event, contribution, enums
  schemas/           Pydantic request/response models (common, auth, friend, event, contribution)
  services/          Business logic + transactions (auth, friends, events, contributions)
  api/deps.py        DbSession, CurrentUser, pagination dependency
  api/v1/            Routers: auth, friends, events, contributions, public
  tests/             pytest suite (conftest.py builds schema from migrations)
alembic/             env.py, script.py.mako, versions/
docs/                This documentation
AGENTS.md / CLAUDE.md  Agent entry points
```

## The frontend

The frontend lives in a **separate repository that is not accessible from here**, and nothing about its code,
framework or deployment is known to this documentation. What the backend does tell us:

* It is expected to be hosted separately: CORS is driven by `CORS_ORIGINS`; auth uses a Bearer token in the
  `Authorization` header (no cookies). `.env.example` lists `http://localhost:5173` and `http://localhost:3000` as
  *example* origins only — that is not evidence of the frontend's stack.
* The requirements state that the frontend is responsible for explicit user confirmation before calling
  `DELETE /api/v1/events/{id}` (which permanently deletes the event's contributions).
* The authoritative contract is the OpenAPI document at `/docs` and `docs/API_CONVENTIONS.md`. Treat any change to
  response shapes, field names, status codes or error codes as a **breaking change for an unseen consumer**.

## Current limitations (known, intentional for MVP)

* Single treasurer; events are scoped to their creator. No password reset, token refresh or revocation.
* No login rate limiting (expected at the reverse-proxy layer).
* No friend deactivation; friends referenced by contributions simply cannot be deleted.
* The public participant list is not paginated (bounded by one row per friend per event).
* Completed events still accept contribution changes.
* The `docs/` and `README.md` may mention `psycopg` while `.env.example` shows `pg8000` (see driver note).

## Glossary

* **Treasurer** — the only authenticated user (`users` row).
* **Friend** — a person who may contribute; master record, no login.
* **Event** — one collection (e.g. "Gift for Rina"), with optional target amount, `active`/`completed`, public flag.
* **Contribution** — a friend's pledged amount in an event; `pending` until marked `paid`.
* **Collected** — sum of amounts of `paid` contributions only.
