# Architecture

A conventional layered FastAPI service. No repository layer (not needed at this size) and no async DB access:
handlers are plain `def`, so FastAPI runs them in a threadpool with a synchronous SQLAlchemy session.

```
HTTP ──► app/main.py ──► api/v1/<router> ──► services/<module> ──► models (SQLAlchemy) ──► PostgreSQL
              │               │                    │
        CORS + error     auth/deps/pagination   business rules,
        handlers         request/response       queries, transactions
                         schemas (schemas/)
```

## Layers and responsibilities

| Layer | Path | Does | Must not |
|---|---|---|---|
| App wiring | `app/main.py` | create `FastAPI`, CORS, register error handlers, mount `/api/v1`, `/health` | contain logic |
| Routers | `app/api/v1/*.py` | declare paths, auth dependency, request/response schemas, status codes; call one service function; build `Page(...)` | query the DB, hold rules |
| Dependencies | `app/api/deps.py` | `DbSession`, `CurrentUser` / `get_current_user`, `PaginationParams` | – |
| Services | `app/services/*.py` | queries, business rules, ownership scoping, transactions (`commit`/`rollback`), raise `ApiError` | import FastAPI request objects |
| Schemas | `app/schemas/*.py` | Pydantic validation and output shape (incl. public allow-lists) | touch the DB |
| Models | `app/models/*.py` | table definitions, constraints, relationships | contain business logic |
| Core | `app/core/*.py` | settings, hashing/JWT, `ApiError` + handlers | – |
| DB | `app/db/*.py` | `Base` (naming convention), engine, `SessionLocal`, `get_db` | – |

Service ↔ router contract: services return ORM objects (or `EventSummary`), routers let FastAPI serialize via
`response_model` (`from_attributes`). Pagination services return `(items, total)`.

## Routers (all mounted under `/api/v1`)

| Module | Prefix | Protection |
|---|---|---|
| `auth.py` | `/auth` | `login` open; `me` requires token |
| `friends.py` | `/friends` | router-level `Depends(get_current_user)` |
| `events.py` | `/events` (includes `/{id}/summary`) | router-level auth |
| `contributions.py` | none: `/events/{id}/contributions`, `/contributions/{id}` | router-level auth |
| `public.py` | `/public/events` | **no auth**, read-only (GET only) |

Handlers that need the user's id declare `user: CurrentUser` (FastAPI caches the dependency, so no second lookup).

## Services

* `auth.login` — verify credentials, issue token.
* `friends` — list (search `ILIKE` over name/nickname/phone with wildcard escaping, order by name), CRUD, guarded delete.
* `events` — list/CRUD scoped by `created_by`; `list_public_events`, `get_public_event` (visibility gate);
  `get_summary` (single aggregate query, integer math).
* `contributions` — list with status filter, create (duplicate handling), update (status transition logic),
  delete, `list_public_participants`; ownership enforced by joining to `Event.created_by`.

## Request lifecycle

1. CORS middleware (allowed origins from settings).
2. Router dependency resolves Bearer token → `User` (401 `not_authenticated` otherwise).
3. Pydantic validates body/query/path (422 `validation_error` envelope).
4. Service runs in one session; mutations end with `commit()`.
5. `response_model` filters the output. Errors are rendered by `register_error_handlers`.

## Configuration

`app/core/config.py` → `Settings` (pydantic-settings, reads env then `.env`): `DATABASE_URL`, `TEST_DATABASE_URL`,
`CORS_ORIGINS` (comma-separated → list), `SECRET_KEY` (≥ 32 chars, required), `JWT_ALGORITHM` (default HS256),
`ACCESS_TOKEN_EXPIRE_MINUTES` (default 60). `get_settings()` is cached. The engine is created at import time of
`app/db/session.py`, so settings must be correct before app modules are imported (tests rely on this ordering —
see `app/tests/conftest.py`).

## Database access

* `engine = create_engine(DATABASE_URL, pool_pre_ping=True)`; `SessionLocal(expire_on_commit=False)`.
* `get_db()` yields one `Session` per request and closes it.
* Schema is managed only by Alembic (`alembic/env.py` loads `Base.metadata`, reads `DATABASE_URL` from settings,
  `compare_type=True`, accepts an injected connection via `config.attributes["connection"]` for tests).
  The app never creates tables.

## Error handling

`ApiError(status, code, message, details, headers)` is raised by services/deps; handlers in `core/errors.py` also
normalise Starlette `HTTPException` and `RequestValidationError` into the same envelope. See `API_CONVENTIONS.md`.

## Where to put new code

* New endpoint: schema in `schemas/`, rule/query in `services/`, thin handler in the matching router, auth dependency
  on the router, tests, docs.
* New table/column: model → autogenerate + review migration → schema/service → tests → `DATABASE_SCHEMA.md`.
* Cross-cutting concern (logging, rate limiting): `core/` or middleware in `main.py`.
