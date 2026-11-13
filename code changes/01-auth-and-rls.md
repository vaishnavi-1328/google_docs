# Stage 01 — Auth, tenants, and Postgres RLS

## Summary

Added user accounts, tenants, and memberships; implemented signup / login / logout / me with Argon2id password hashing and JWT session cookies; wired `current_user` + `current_tenant_id` + `tenant_session` FastAPI dependencies; and enabled Postgres **row-level security** on `memberships` with `FORCE` + default-deny behavior when `app.tenant_id` is unset. This is the guardrails stage — every one of the five guardrails from `guardrails.md` is now enforced in code, at the database, or both. Cross-tenant and no-GUC read/write tests are included and must stay green.

## Files added / changed

- `backend/app/models/tenant.py`, `user.py`, `membership.py`, `__init__.py` — ORM models with UUID PK + timestamps + `UniqueConstraint(user_id, tenant_id)` on memberships.
- `backend/app/security.py` — `hash_password` / `verify_password` (Argon2id via passlib), `create_session_token` / `decode_session_token` (HS256 JWT).
- `backend/app/db.py` — kept the engine + `get_session`; added `_set_tenant_guc` helper. The actual tenant-scoped dependency now lives in `deps.py` to avoid a circular import and to keep the auth layer in one place.
- `backend/app/deps.py` — `current_identity`, `current_user`, `current_tenant_id`, `tenant_session`. Every tenant-scoped route must depend on `tenant_session`.
- `backend/app/routes/auth.py` — `POST /auth/signup`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`.
- `backend/app/main.py` — mounts the auth router.
- `backend/alembic/versions/0002_auth_and_rls.py` — creates `tenants`, `users`, `memberships`; enables `ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY` on `memberships`; creates the `memberships_tenant_isolation` policy using `current_setting('app.tenant_id', true)` with `NULLIF`+`::uuid` cast so missing/empty GUC collapses to NULL (deny-all).
- `backend/tests/conftest.py` — puts `backend/` on `sys.path`.
- `backend/tests/test_rls.py` — three tests: cross-tenant SELECT is blocked, cross-tenant INSERT is rejected by `WITH CHECK`, and no-GUC SELECT returns zero rows.
- `backend/tests/test_auth.py` — signup→me→logout flow, generic 401 for bad password, `/me` requires cookie, `password_hash` never appears in responses.

## Decisions

- **Argon2id over bcrypt.** passlib's argon2 backend uses sensible defaults; Stage 10 tunes memory/time parameters per deployment.
- **JWT in an httpOnly cookie** rather than `Authorization: Bearer`. Keeps browser-side JS from touching the token (XSS resistance) and makes the Yjs websocket authenticate for free in Stage 3. `SameSite=Lax` blocks naive CSRF for navigations; Stage 10 adds explicit CSRF tokens for state-changing requests.
- **Tenant id is a JWT claim, not a header/body parameter.** Every dependency path resolves the tenant from the signed claim and then re-verifies it against `memberships`. A forged/stolen JWT for a tenant the user doesn't belong to fails the membership check and 403s — even before any query runs.
- **RLS with `FORCE`.** Without `FORCE`, the table owner (the app role) bypasses RLS. With `FORCE`, even the owner is subject to the policy, which means a bug that forgets to filter by tenant still cannot leak data across tenants.
- **`NULLIF(current_setting('app.tenant_id', true), '')::uuid`** so an unset GUC becomes NULL → the equality fails → zero rows visible. This is the "default-deny" behavior verified by `test_rls_denies_without_guc`.
- **`SET LOCAL` inside a transaction** instead of `SET` so the GUC is bound to the request's transaction and is released cleanly when the connection goes back to the pool — no stale tenant context on a reused connection.
- **Uniform "invalid credentials" 401** on login to make email enumeration harder.
- `users` and `tenants` are **not** RLS-protected. `users` is global (a user's email must be unique platform-wide for login). `tenants` describe tenancy itself; access to them is only possible through `memberships`, which is RLS-protected.

## Guardrails traceability

| Guardrail | Enforcement |
|---|---|
| 1. Hashed credentials | `security.hash_password` uses Argon2id; `users.password_hash` is the only password-bearing column; `MeOut` schema excludes it; `test_auth` asserts it never appears in responses. |
| 2. Tenant data isolation | Every tenant-scoped route depends on `tenant_session`, which runs `SET LOCAL app.tenant_id = :tid` for RLS. |
| 3. Server-derived tenant scoping | `current_identity` reads the tenant id from the signed JWT only; `current_user` re-verifies the (user, tenant) pair against `memberships`. Request body/query/header tenant ids are never consulted. |
| 4. Postgres RLS | `memberships` has `ENABLE` + `FORCE` RLS and a policy on `(SELECT, INSERT, UPDATE, DELETE)`. Verified by `test_rls.py`. |
| 5. UUIDv4 public IDs | All three tables use `UUID PRIMARY KEY DEFAULT gen_random_uuid()`; no serial IDs exist. Auth responses return UUIDs. |

## How to verify

1. Bring up the stack: `make db.up && make backend.install && make db.migrate && make backend.dev`.
2. Create a user:
   ```bash
   curl -s -c cookies.txt -X POST localhost:8000/auth/signup \
     -H 'content-type: application/json' \
     -d '{"email":"a@x.test","password":"supersecret","display_name":"A","tenant_name":"Acme"}'
   ```
   Response shape: `{"id":"<uuid>","email":"a@x.test","display_name":"A","tenant_id":"<uuid>"}`. No `password_hash`.
3. `curl -s -b cookies.txt localhost:8000/auth/me` returns the same `MeOut`.
4. `curl -s -b cookies.txt -X POST localhost:8000/auth/logout` returns 204; a subsequent `/auth/me` 401s.
5. Run the tests: `cd backend && . .venv/bin/activate && pytest -q`.
   - `test_rls_blocks_cross_tenant_select` — confirms RLS hides other tenants' rows.
   - `test_rls_denies_insert_for_other_tenant` — confirms `WITH CHECK` blocks forged writes.
   - `test_rls_denies_without_guc` — confirms default-deny when no tenant context.
   - `test_auth` — proves the HTTP flow + no password leak.

## Known gaps

- Single active tenant per session. A user with multiple memberships always logs into their earliest-joined tenant; a tenant-switcher UI/endpoint lands when we need it.
- No email verification, password reset, or rate limiting on login — Stage 10.
- CSRF relies on `SameSite=Lax` for now; an explicit double-submit CSRF token arrives with Stage 10 alongside TLS-only cookie flags.
- `RLS` on `memberships` only; `documents` and `document_acls` get their own policies in Stages 2 and 4.
