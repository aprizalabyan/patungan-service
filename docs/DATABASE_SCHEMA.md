# Database Schema

PostgreSQL. Source of truth: `app/models/*.py` and migration `alembic/versions/71bc1a343b7e_create_initial_schema.py`
(the only revision so far). All primary keys are UUIDs (`default=uuid.uuid4` in Python **and**
`server_default gen_random_uuid()`); all timestamps are `TIMESTAMPTZ`.

## Entity relationships

```
users 1 ──< events 1 ──< contributions >── 1 friends
        created_by  (CASCADE)         (RESTRICT)
 (RESTRICT)
```

## Tables

### `users`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| name | VARCHAR(120) | required |
| email | VARCHAR(255) | required, unique (`uq_users_email`); stored lowercase by the CLI |
| password_hash | VARCHAR(255) | Argon2 hash |
| created_at | TIMESTAMPTZ | `now()` |

No role column: the treasurer is the only role.

### `friends`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| name | VARCHAR(120) | required, indexed (`ix_friends_name`) |
| nickname | VARCHAR(60) | nullable |
| phone | VARCHAR(30) | nullable, **not unique** |
| created_at | TIMESTAMPTZ | `now()` |

### `events`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| title | VARCHAR(200) | required |
| description | TEXT | nullable |
| event_date | DATE | nullable |
| target_amount | BIGINT | nullable; check `target_amount IS NULL OR target_amount >= 0` (`ck_events_target_amount_nonnegative`) |
| status | enum `event_status` | `active` (default) / `completed` |
| is_public | BOOLEAN | default `true` |
| created_by | UUID FK → users.id | `ON DELETE RESTRICT` |
| created_at | TIMESTAMPTZ | `now()` |
| updated_at | TIMESTAMPTZ | `now()`; ORM `onupdate=func.now()` |

Indexes: `ix_events_created_by (created_by)`, `ix_events_status (status)`, `ix_events_is_public_status (is_public, status)`.
No stored balance/total — derive from contributions.

### `contributions`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| event_id | UUID FK → events.id | `ON DELETE CASCADE` |
| friend_id | UUID FK → friends.id | `ON DELETE RESTRICT` |
| amount | BIGINT | required; check `amount > 0` (`ck_contributions_amount_positive`) |
| payment_status | enum `payment_status` | `pending` (default) / `paid` |
| paid_at | TIMESTAMPTZ | nullable; maintained by the service (see BUSINESS_RULES) |
| notes | VARCHAR(500) | nullable |
| created_at / updated_at | TIMESTAMPTZ | as above |

Constraints/indexes: `uq_contributions_event_friend (event_id, friend_id)` (also serves `event_id` lookups),
`ix_contributions_friend_id (friend_id)`, `ix_contributions_event_id_payment_status (event_id, payment_status)`.

## Enums

Named PostgreSQL enum types created by the migration: `event_status ('active','completed')` and
`payment_status ('pending','paid')`. Python enums are in `app/models/enums.py`; `pg_enum()` stores the lowercase
**values**. Adding a member requires a hand-written migration (`ALTER TYPE … ADD VALUE`): Alembic autogenerate does
not detect enum member changes, and the initial migration's `downgrade()` drops both types explicitly.

## ORM relationships

* `User.events` ↔ `Event.creator`
* `Event.contributions` ↔ `Contribution.event` — `cascade="all, delete-orphan", passive_deletes=True` (the DB cascade does the work)
* `Friend.contributions` ↔ `Contribution.friend` — no cascade, so friends with history can't be deleted

## Naming convention

`app/db/base.py` defines a metadata naming convention (`pk_…`, `fk_<table>_<col>_<ref>`, `uq_…`, `ck_<table>_<name>`,
`ix_…`) so constraint names are deterministic across migrations. Give new check constraints a short `name=`.

## Migrations: workflow

```bash
alembic revision --autogenerate -m "describe the change"   # then REVIEW and edit the file
alembic upgrade head
alembic current
alembic check                                              # must report no drift
alembic downgrade -1                                       # verify reversibility on a scratch DB
```

Review checklist: server defaults, nullability on existing data (backfill before `NOT NULL`), enum changes, index
names, a correct `downgrade()`. `alembic/env.py` reads `DATABASE_URL` from app settings; never put a URL in
`alembic.ini`. Never edit an already-applied revision — add a new one. Do not use `create_all()`.
