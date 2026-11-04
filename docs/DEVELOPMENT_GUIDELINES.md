# Development Guidelines

## Setup

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # fill in real values (never commit .env)
alembic upgrade head
python -m app.cli create-treasurer --name "Name" --email you@example.com
uvicorn app.main:app --reload
```

Two PostgreSQL databases are needed: development (`DATABASE_URL`) and tests (`TEST_DATABASE_URL`, name **must end in
`_test`**). Percent-encode special characters in URL passwords (`@` → `%40`).

**Database driver.** Use a `DATABASE_URL` scheme matching an installed driver: `postgresql+psycopg://` (Psycopg 3,
the project's intended driver) or `postgresql+pg8000://` (pure Python; what `.env.example` currently shows, handy when
psycopg's binary wheel is unavailable such as on Windows ARM). Only psycopg has been verified against the test suite
and migrations. `requirements.txt` is a full freeze containing both drivers.

## Testing

```bash
pytest                      # whole suite (config in pytest.ini, tests in app/tests/)
pytest app/tests/test_contributions.py -k paid
```

How the suite works (`app/tests/conftest.py`):

* Reads `TEST_DATABASE_URL`, **refuses to run** if it is missing or the database name doesn't end in `_test`, then
  sets `DATABASE_URL` to it **before** importing the app so the app's engine uses the test DB.
* Session start: `DROP SCHEMA public CASCADE; CREATE SCHEMA public`, then `alembic upgrade head` — so migrations are
  exercised on every run. After each test all tables are truncated.
* Fixtures: `client` (TestClient), `db` (session), `treasurer`, `auth` (Bearer headers), and factories
  `make_friend`, `make_event`, `make_contribution`.
* Never point `TEST_DATABASE_URL` at the dev database or anything valuable. Never weaken the `_test` guard.

Coverage by file: `test_models` (constraints, cascades, enums, indexes), `test_auth` (login, token failures, every
protected route, CORS, health), `test_friends`, `test_events`, `test_contributions` (duplicates, status transitions),
`test_summary` (money math), `test_public` (visibility, allow-list leakage, read-only).

When you change behaviour, add tests in the matching file; for new management routes also extend
`test_auth.PROTECTED`; for new public fields extend the leakage checks in `test_public.py`.

## Migrations

See `DATABASE_SCHEMA.md` ("Migrations: workflow"). In short: edit models → `alembic revision --autogenerate` →
**review** → `alembic upgrade head` → `alembic check` clean. Never edit applied revisions; never use `create_all()`.

## Code conventions

* Python typing everywhere; modern syntax (`str | None`, `list[...]`). SQLAlchemy 2.x style (`select()`,
  `db.scalars()`, `Mapped[...]`) — no legacy `Query`.
* Routers thin, services hold rules and `commit()`, schemas validate/shape, models only describe tables
  (see `ARCHITECTURE.md`).
* Raise `ApiError(status, "snake_case_code", "message", details?)` for domain errors; use `not_found("Thing")` for 404s.
* Handle races by relying on DB constraints too (pre-check for a friendly error, then catch `IntegrityError`,
  `rollback()`, raise the same domain error).
* Bound every input: string lengths, amounts (`MAX_AMOUNT`), `page_size` (max 100).
* Use integer arithmetic for money (`//`, never `/`).
* Queries that return lists need a deterministic `order_by` (include `id` as tie-breaker) so pagination is stable.
* Search input used in `LIKE` must be escaped (see `friends._escape_like`).
* Keep comments for the *why*; match the density and naming of surrounding code. No speculative abstractions.
* New dependency? Justify it, add it to `requirements.txt`.

## Recipes

**Add a field to a model:** model → autogenerate migration → review (nullability/defaults) → schemas → service →
tests → update `DATABASE_SCHEMA.md` and `API_CONVENTIONS.md`.

**Add an endpoint:** follow the checklist at the bottom of `API_CONVENTIONS.md`.

**Add a business rule:** implement in the service, cover with tests, record in `BUSINESS_RULES.md`.

## Safety checklist for agents

* Don't run destructive commands (`DROP`, `TRUNCATE`, `alembic downgrade base`) against any DB except a disposable
  `*_test` or scratch database.
* Don't commit `.env`, don't echo secrets.
* Don't change public response schemas without a privacy justification.
* Don't assume anything about the frontend beyond the API contract; flag breaking API changes in your summary.
* Don't claim tests passed unless you ran them; say what you couldn't run (e.g. no database available).
