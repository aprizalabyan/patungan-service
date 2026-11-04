# API Conventions

Base path: `/api/v1`. Also `GET /health` → `{"status":"ok"}` and OpenAPI/Swagger at `/docs`. JSON only.
The frontend is an external consumer: changing anything on this page can break it.

## Endpoints

| Method & path | Auth | Success | Notes |
|---|---|---|---|
| `POST /auth/login` | no | 200 `TokenResponse` | |
| `GET /auth/me` | yes | 200 `UserRead` | |
| `GET /friends` | yes | 200 `Page[FriendRead]` | `search` (≤100 chars), `page`, `page_size` |
| `POST /friends` | yes | 201 `FriendRead` | |
| `GET/PATCH/DELETE /friends/{friend_id}` | yes | 200 / 200 / 204 | delete → 409 `friend_in_use` if referenced |
| `GET /events` | yes | 200 `Page[EventRead]` | `status` filter; newest first |
| `POST /events` | yes | 201 `EventRead` | |
| `GET/PATCH/DELETE /events/{event_id}` | yes | 200 / 200 / 204 | delete cascades contributions |
| `GET /events/{event_id}/summary` | yes | 200 `EventSummary` | |
| `GET /events/{event_id}/contributions` | yes | 200 `Page[ContributionRead]` | `payment_status` filter; ordered by friend name |
| `POST /events/{event_id}/contributions` | yes | 201 `ContributionRead` | 404 unknown event/friend, 409 duplicate |
| `PATCH/DELETE /contributions/{contribution_id}` | yes | 200 / 204 | |
| `GET /public/events` | no | 200 `Page[PublicEventRead]` | public only; `status` filter |
| `GET /public/events/{event_id}` | no | 200 `PublicEventDetail` | 404 if private/unknown |
| `GET /public/events/{event_id}/summary` | no | 200 `EventSummary` | 404 if private/unknown |

`/public/...` only supports GET (other methods → 405).

## Conventions

* **IDs** are UUID strings. A malformed UUID in a path is `422`, an unknown one is `404`.
* **Dates/times**: `event_date` is `YYYY-MM-DD`; timestamps are ISO-8601 with offset (UTC).
* **Money**: JSON integers in Rupiah.
* **Mutations**: POST → `201` with the created resource; PATCH → `200` with the full updated resource;
  DELETE → `204` with an empty body.
* **PATCH** is partial: send only changed fields. Explicit `null` clears nullable fields and is rejected (`422`)
  for non-nullable ones (`name`, `title`, `status`, `is_public`, `amount`, `payment_status`).
* **Pagination** (all list endpoints): query `page` (≥1, default 1), `page_size` (1–100, default 20). Response:
  `{"items": [...], "total": <int>, "page": <int>, "page_size": <int>}`. Out-of-range values → `422` (never clamped).
* **Enums** are lowercase strings: event `status` `active|completed`; `payment_status` `pending|paid`.

## Error envelope

Every error (including 404/405/422/401) has this shape:

```json
{"error": {"code": "duplicate_contribution", "message": "…human readable…", "details": null}}
```

| Status | `code` | When |
|---|---|---|
| 401 | `not_authenticated` | missing/invalid/expired token (header `WWW-Authenticate: Bearer`) |
| 401 | `invalid_credentials` | wrong email or password (same response for unknown email) |
| 404 | `not_found` | unknown resource, someone else's resource, or a non-public event on public routes; unknown route |
| 405 | `method_not_allowed` | |
| 409 | `duplicate_contribution` | friend already in the event |
| 409 | `friend_in_use` | deleting a friend with contributions (`details: {"contributions": n}` when known) |
| 422 | `validation_error` | `details`: `[{"field": "query.page_size" \| "name" \| …, "message": "…"}]` |
| other | `http_error` | fallback for unclassified framework errors |

Frontends should branch on `code`, not `message`. Add new codes in snake_case and document them here.
Unhandled exceptions fall through to the framework's default 500 (not wrapped in the envelope).

## Key schemas (`app/schemas/`)

* `LoginRequest {email, password}` → `TokenResponse {access_token, token_type:"bearer", expires_in (seconds)}`.
* `UserRead {id, name, email, created_at}` — never includes `password_hash`.
* `FriendCreate {name 1–120, nickname 1–60?, phone?}`; phone: 3–30 chars, `^\+?[0-9][0-9 \-()]*$`.
  `FriendRead {id, name, nickname, phone, created_at}`.
* `EventCreate {title 1–200, description ≤5000?, event_date?, target_amount 0…1e12?, status="active", is_public=true}`;
  `EventUpdate` = same fields, all optional. `EventRead` adds `id, created_by, created_at, updated_at`.
* `ContributionCreate {friend_id, amount 1…1e12, notes ≤500?}` (no status on create).
  `ContributionUpdate {amount?, payment_status?, notes?}`.
  `ContributionRead {id, event_id, friend_id, friend {id,name,nickname}, amount, payment_status, paid_at, notes, created_at, updated_at}`.
* `EventSummary {event_id, total_participants, paid_count, pending_count, total_collected, total_pending, target_amount, progress_percent}`
  — `progress_percent` is an int, may exceed 100, `null` if target is null/0 (see BUSINESS_RULES).
* Public: `PublicEventRead {id, title, description, event_date, target_amount, status}`;
  `PublicEventDetail` = that + `participants: [{name, payment_status}]`. **Allow-lists** — see AUTHENTICATION.md/BUSINESS_RULES.md.

String inputs are trimmed; extra unknown JSON fields are ignored.

## Adding or changing an endpoint — checklist

1. Request/response schemas in `app/schemas/` (explicit `response_model`; never return raw ORM objects on public routes).
2. Logic in a service function; raise `ApiError` with a stable `code`.
3. Thin handler in the right router; auth is inherited from the router (don't add unauthenticated routes by accident).
4. Correct status code (`201`/`204`), pagination via `PaginationParams`, bounded inputs.
5. Tests for success, validation (422), 404, auth (401), and ownership/visibility.
6. Update this file and `README.md`; note breaking changes to the frontend.
