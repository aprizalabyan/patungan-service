# Authentication & Authorization

## Model

* One authenticated role: the **treasurer** (a row in `users`). There is no role column and **no registration endpoint**.
* Everyone else is anonymous and may only use `/api/v1/public/...` read-only endpoints.

## Creating the treasurer

```bash
python -m app.cli create-treasurer --name "Bendahara" --email treasurer@example.com
```

Password: prompted twice (hidden), or taken from env `PATUNGAN_TREASURER_PASSWORD` for non-interactive use.
Validation: valid email (stored **lowercase**), non-empty name, password ≥ 8 chars, email must not already exist.
Never pass the password as a command-line argument.

## Password storage

Argon2 via `argon2-cffi` `PasswordHasher()` defaults (Argon2id); hashes start with `$argon2`. Implemented in
`app/core/security.py` (`hash_password`, `verify_password`). Plaintext passwords are never stored or logged.

## Login flow

`POST /api/v1/auth/login` `{email, password}`:

1. Look up the user by lowercased email.
2. Verify the password; if the user doesn't exist a dummy hash is verified so timing doesn't reveal valid emails.
3. Any failure → `401 invalid_credentials` (identical for unknown email / wrong password).
4. Success → `{"access_token": "<jwt>", "token_type": "bearer", "expires_in": <seconds>}`.

There is **no login rate limiting** — add it at the reverse proxy/WAF or as middleware before production.

## Token

* JWT, `HS256` by default (`JWT_ALGORITHM`), signed with `SECRET_KEY` (required, ≥ 32 chars).
* Claims: `sub` (user UUID), `iat`, `exp`. `exp` and `sub` are required on decode; the algorithm is pinned to the
  configured one.
* Lifetime: `ACCESS_TOKEN_EXPIRE_MINUTES` (default 60). No refresh tokens, no revocation list: to invalidate all
  tokens, rotate `SECRET_KEY`. Deleting the user also invalidates their token (the user is loaded on every request).
* Client sends `Authorization: Bearer <token>`. Tokens live in headers, not cookies, so there is no CSRF surface.

## Protecting routes

* `app/api/deps.py::get_current_user` extracts the Bearer token (`HTTPBearer(auto_error=False)` so the error uses our
  envelope), decodes it, loads the `User`, else `401 not_authenticated` with `WWW-Authenticate: Bearer`.
* `CurrentUser = Annotated[User, Depends(get_current_user)]` for handlers that need the user.
* **Router-level** `dependencies=[Depends(get_current_user)]` on `friends`, `events`, and `contributions` routers —
  a new route in those routers is protected by default. `GET /auth/me` depends on it directly.
* Open routes: `POST /auth/login`, `GET /health`, `/docs`, and everything under `/public`.
* `app/tests/test_auth.py::PROTECTED` lists every management route and asserts it returns 401 without a token — add
  new management routes there.

## Authorization (ownership)

Single-treasurer MVP, but data access is still scoped: events are fetched with `created_by == current user`
(`events.get_event`, `list_events`), and contributions are fetched via a join to `Event.created_by`
(`contributions.get_contribution`). Another user's resources return `404`, not `403`, to avoid leaking existence.
Friends are shared master data (not owned per user). If multiple treasurers are ever supported, revisit friends.

## Public access rules

Public routes never read the token. Visibility is enforced in `events.get_public_event` / `list_public_events`
(`is_public IS TRUE`), so private events return `404` even with a valid treasurer token. Response schemas
(`PublicEventRead`, `PublicEventDetail`, `PublicParticipant`) are explicit allow-lists:
event basics + participant `name` and `payment_status` only. See `BUSINESS_RULES.md` for the privacy trade-off.
When adding a public field, justify it against that list and extend `test_public.py` leakage checks.

## CORS

`CORSMiddleware` with `allow_origins = CORS_ORIGINS` (comma-separated env var, trailing slashes stripped),
`allow_credentials=False`, methods `GET, POST, PATCH, DELETE, OPTIONS`, headers `Authorization, Content-Type`.
Never use `*` together with credentials; add origins via env, not code. `PUT` is not allowed — add it deliberately
if a PUT endpoint is ever introduced.

## Secrets handling

`.env` is git-ignored; `.env.example` holds placeholders only. Never commit `SECRET_KEY`, database passwords,
tokens or hashes; never include them in logs, test output, docs or error messages.

## Refresh rotation and sessions

Login returns the existing access-token JSON shape and sets an HttpOnly refresh cookie. The opaque refresh token is generated from 256 bits of cryptographic randomness; only its SHA-256 hash is stored. Access tokens expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (default 15). Refresh sessions expire after `REFRESH_TOKEN_EXPIRE_DAYS` (default 7).

`POST /api/v1/auth/refresh` validates the refresh cookie and an `Origin` listed in `CORS_ORIGINS`, then atomically revokes the old token and creates its replacement in the same `family_id`. Each login creates a new family, allowing independent device sessions. Reuse of a rotated token revokes active tokens in that family and logs the family ID only. A parallel request blocked on the same database row within two seconds gets 401 without family revocation to avoid treating an ordinary simultaneous tab refresh as theft.

`POST /api/v1/auth/logout` revokes the current cookie session if available and otherwise succeeds. `POST /api/v1/auth/logout-all` requires a valid Bearer access token and revokes every session for that user. Both clear the browser cookie.

Cookie configuration: `REFRESH_TOKEN_COOKIE_NAME` defaults to `refresh_token`; `COOKIE_SECURE` defaults false for local HTTP and must be true in HTTPS production; `COOKIE_SAMESITE` accepts `lax`, `strict`, or `none` (`none` requires Secure in browsers); `COOKIE_DOMAIN` is optional. Cookie path is `/api/v1/auth`. Configure exact frontend origins in `CORS_ORIGINS`; credentialed CORS is enabled with no wildcard. The frontend must include credentials on refresh/logout requests. Cross-site production deployments need HTTPS and typically `SameSite=None; Secure`.
