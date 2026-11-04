# AGENTS.md

Instructions for AI coding agents (and humans) working in the **Patungan backend** repository.
This file is the entry point; the detailed knowledge lives in `docs/`.

Patungan is a REST API for a treasurer who collects money from friends to buy wedding gifts.
Stack: Python, FastAPI, SQLAlchemy 2.x (sync, typed ORM), PostgreSQL, Alembic, Pydantic v2, pytest.
The frontend is a **separate repository that is not available here**. Do not guess its code; the API contract
(OpenAPI at `/docs`, and `docs/API_CONVENTIONS.md`) is the only interface to it.

## Read before you change anything

Always read `docs/PROJECT_CONTEXT.md` first (short). Then read what matches your task:

| If you are… | Read |
|---|---|
| Changing money, payment status, summaries, visibility, deletion behaviour | `docs/BUSINESS_RULES.md` |
| Adding/moving code, deciding which layer something belongs in | `docs/ARCHITECTURE.md` |
| Touching models, constraints, indexes, enums or migrations | `docs/DATABASE_SCHEMA.md` |
| Adding/changing endpoints, request/response schemas, errors, pagination | `docs/API_CONVENTIONS.md` |
| Touching login, tokens, passwords, CORS, route protection, public endpoints | `docs/AUTHENTICATION.md` |
| Setting up, running, testing, or writing new code and tests | `docs/DEVELOPMENT_GUIDELINES.md` |

`README.md` has setup commands and curl examples. If a doc and the code disagree, **the code is the truth** —
fix the doc in the same change.

## Non-negotiable rules

1. **Schema changes go through Alembic only.** Never use `Base.metadata.create_all()` and never alter the schema at
   app startup. After editing models: `alembic revision --autogenerate -m "..."`, review the file by hand, then
   `alembic upgrade head`. Run `alembic check` — it must report no drift.
2. **Routes stay thin; business rules live in `app/services/`.** Services own transactions (`db.commit()`).
3. **Money is integer Rupiah** (`BigInteger` in DB, `int` in Python). Never use floats for money or progress.
4. **Public endpoints use explicit allow-list schemas** (`Public*` in `app/schemas/event.py`). Never return ORM
   objects or add fields there "because they exist". Never expose phone numbers, notes, amounts per person,
   creator info or password hashes publicly.
5. **Every management route must be authenticated** (router-level `Depends(get_current_user)`), and event/contribution
   lookups must stay scoped to the current user (`created_by`).
6. **Errors use the shared envelope** `{"error": {"code", "message", "details"}}` via `ApiError`. Don't raise bare
   `HTTPException` or return ad-hoc error bodies.
7. **Never run anything destructive against the development database.** Tests use `TEST_DATABASE_URL`, whose name
   must end in `_test`, and they drop/rebuild that database's `public` schema. Do not weaken that guard.
8. **No secrets in the repo.** `.env` is git-ignored; only `.env.example` (placeholders) is committed. Don't print or
   log real credentials, tokens or password hashes.
9. **Do not delete data casually.** Friends with contribution history must not become deletable; deleting an event
   cascades to its contributions — keep that behaviour documented if you touch it.
10. Don't add dependencies, abstraction layers (e.g. repositories), or new roles/columns without a concrete need.

## Before you finish

* Run the test suite (`pytest`) and fix failures; add or update tests for behaviour you changed
  (see `docs/DEVELOPMENT_GUIDELINES.md`).
* If you changed models: migration generated, reviewed, applied to a scratch DB, `alembic check` clean.
* If you changed endpoints/schemas/rules: update the matching file in `docs/` (and `README.md` if user-facing).
* Match surrounding code style: type hints, small functions, `from __future__`-free modern typing (`X | None`).
* Report honestly what you ran and what you could not run.

## Quick commands

```bash
pip install -r requirements.txt
alembic upgrade head                 # apply migrations
python -m app.cli create-treasurer --name "Name" --email you@example.com
uvicorn app.main:app --reload        # docs at /docs, health at /health
pytest                               # needs TEST_DATABASE_URL (…_test database)
```
