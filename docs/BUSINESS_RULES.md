# Business Rules

Rules below are implemented in `app/services/` and enforced by DB constraints; tests in `app/tests/` pin them.

## Money

* Amounts are **whole Indonesian Rupiah integers**. DB: `BIGINT`. No decimals, no floats, ever.
* Client input bounds: `amount` 1 … 1,000,000,000,000; `target_amount` 0 … 1,000,000,000,000
  (`MAX_AMOUNT` in `app/schemas/common.py`).
* Event totals are **never stored**; they are computed from contribution rows on each request.

## Friends

* Master records: `name` (required), optional `nickname`, optional `phone`. No login.
* Phone is **not unique** (people may share numbers).
* A friend can join many events, but at most once per event.
* **Deletion**: allowed only if the friend has zero contributions. Otherwise `409 friend_in_use`
  (pre-check, plus FK `ON DELETE RESTRICT` as the backstop for races). Historical data is never silently dropped.
  There is no deactivation flag yet.

## Events

* Fields: title, optional description/date/target, `status` (`active` | `completed`, default `active`),
  `is_public` (default `true`), `created_by`.
* Management access is scoped to the creator: another user's event is reported as `404`.
* `status` is a plain field the treasurer can set either way; there is no enforced workflow, and completed events
  still accept contribution changes.
* **Deletion** permanently deletes the event **and all its contributions** (`ON DELETE CASCADE`). Friends are kept.
  The frontend must confirm explicitly with the user first; the API does not require a confirmation token.

## Contributions

* One per `(event, friend)`. Duplicate → `409 duplicate_contribution` (pre-check, plus unique-constraint catch for
  races). The same friend may join other events.
* Creating requires an existing event (owned by the user) and an existing friend (`404` otherwise).
* A new contribution is always `pending` with `paid_at = null`; create does not accept a status.
* `amount` must be > 0 (also a DB check). `notes` ≤ 500 chars.

### Payment status transitions (`update_contribution`)

| From → To | `payment_status` | `paid_at` |
|---|---|---|
| `pending` → `paid` | `paid` | set to current UTC time |
| `paid` → `pending` | `pending` | set to `null` |
| `paid` → `paid` (re-sent) | unchanged | **unchanged** (original timestamp kept) |
| amount or notes edited | **unchanged** | unchanged |

Changing the amount of a `paid` contribution changes the collected total but never silently flips its status.

## Summary (`GET /events/{id}/summary`, also public variant)

Computed by one SQL aggregate over the event's contributions:

* `total_participants` = count of contributions; `paid_count`, `pending_count` by status.
* `total_collected` = SUM(amount) where `paid` (0 if none). **Pending is never counted as collected.**
* `total_pending` = SUM(amount) where `pending` (0 if none).
* `target_amount` = event's target (nullable).
* `progress_percent` = `total_collected * 100 // target_amount` (integer floor), **only if target > 0**;
  `null` when target is `null` or `0`. **Not capped at 100** — over-collection reports e.g. `150`.
  With a positive target and nothing collected it is `0`.

## Visibility (public vs private)

* `is_public = true` events are readable without authentication through `/api/v1/public/events…`; everything else
  returns `404` there (indistinguishable from non-existent). Visibility is checked in the service
  (`get_public_event`), **independent of whether a token is sent** — a treasurer token does not unlock private events
  on public routes.
* Public data is an allow-list:
  * Event: `id, title, description, event_date, target_amount, status`.
  * Participants: **`name` and `payment_status` only**.
  * Summary: aggregates only.
* Never public: phone, nickname, notes, per-person amounts, `paid_at`, creator, timestamps, `is_public`, anything
  about users.
* **Privacy trade-off:** anyone holding an event link can see which friends (by full name) have paid. Making an event
  private hides it entirely.

## Pagination and validation

* Lists: `page ≥ 1`, `page_size` 1–100 (default 20). Out-of-range values are `422`, not clamped.
* Text input is whitespace-stripped; empty names/titles are rejected.
* PATCH: omitted fields are untouched; fields that cannot be null (`name`, `title`, `status`, `is_public`, `amount`,
  `payment_status`) reject an explicit `null`; nullable fields can be cleared with `null`.

## Transactions

Each service function that mutates data performs a single `commit()` at the end; on `IntegrityError` it rolls back
and raises a domain error. `get_db()` provides one session per request.

## Changing a rule

Update the service, add a migration if a constraint changes, update tests, and update this file.
