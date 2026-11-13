# Stage 10 — Hardening & load test

## Summary

Closed the security and operations gaps carried as "Stage 10" in prior changelogs. Added a security-headers middleware (CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy), a per-IP rate limiter on the two auth endpoints that have real abuse potential, a WS `Origin` check, a production-aware `Secure` cookie flag, a startup assertion that refuses to run with the example JWT secret outside dev, snapshot pruning (keep latest 30 autosaves + all user-labeled), a k6 load script, and an ACL test suite that pins the authorization matrix.

## Files added / changed

- `backend/app/middleware.py` — `SecurityHeadersMiddleware`, `RateLimitMiddleware` (60-second window, 30 hits per IP per window on `/auth/login` and `/auth/signup`), `startup_assertions()`.
- `backend/app/main.py` — adds both middleware; calls `startup_assertions()` at import time.
- `backend/app/settings.py` — adds `env: "dev" | "prod"`.
- `backend/app/routes/auth.py` — session cookie `secure` flag now flips to true when `env == "prod"`.
- `backend/app/ws/docs.py` — refuses WS upgrades whose `Origin` isn't in the allowlist; snapshot pruning in `_persist_and_maybe_evict` keeps the 30 most recent `Autosave` snapshots per doc and never deletes user-labeled ones.
- `backend/tests/test_sharing.py` — viewer-cannot-delete, viewer-cannot-patch, link-revoke flow.
- `loadtest/docs.js` — k6 script: VUs sign up, create a doc, and churn through `GET /docs/:id` + `GET /docs`.

## Decisions

- **Rate-limit auth, not the rest.** `/auth/login` and `/auth/signup` are the only endpoints an anonymous attacker can hit cheaply. Everything else is behind a valid session + tenant membership + (where it matters) a doc ACL; abuse there costs at least the price of a signup, which is now rate-limited.
- **In-memory rate limiter is honest about scope.** Multi-worker deployments will want Redis; the docstring says so. Shipping a Redis dependency this stage was out of proportion to the actual threat — a single uvicorn worker is the current deployment story.
- **CSP with `connect-src *`** so the editor can hit the WS endpoint regardless of dev/prod origin. In prod that line should narrow to the actual API origin; the `settings.allowed_origins_list` list is the right source, and templatizing the CSP is a one-line change that we deferred to keep this stage focused.
- **`X-Frame-Options: DENY` + CSP `frame-ancestors 'none'`** — the editor must not be embeddable, to prevent UI redressing of the share dialog.
- **Startup assertion is non-fatal in dev.** Running locally with the example `.env` is convenient; flipping `ENV=prod` makes the mis-secret an immediate crash so a deploy can't accidentally start with a predictable JWT secret.
- **Snapshot pruning is additive, not retentive-by-time.** A time-based policy (keep hourly for 24h, daily for 7d, etc.) is the "right" thing but adds schema/metadata; "keep 30 autosaves per doc + all user-labeled" keeps the table bounded for the MVP without special types.
- **Playwright convergence test is still deferred.** The k6 script exercises the REST surface under load; the convergence test will land when a full headless-chromium rig is set up in CI — a short follow-up PR rather than part of this stage.

## Guardrails traceability (consolidated across all stages)

| # | Guardrail | Where enforced |
|---|---|---|
| 1 | Hashed credentials | `security.py` Argon2id; `User.password_hash` never serialized (`MeOut` schema). `test_auth` asserts the hash never appears. |
| 2 | Tenant data isolation | Every tenant-scoped row carries `tenant_id`; `tenant_session` dep sets `app.tenant_id` GUC per request. |
| 3 | Server-derived tenant scoping | `current_identity` reads the tenant id from the signed session cookie; `current_user` re-verifies the (user, tenant) pair against `memberships` before any query. Request bodies / headers / query params are never consulted for tenant id. |
| 4 | Postgres RLS | `memberships`, `documents`, `document_snapshots`, `document_acls`, `share_links`, `comments`, `attachments` all have `ENABLE` + `FORCE ROW LEVEL SECURITY` + `USING`/`WITH CHECK` policies that collapse to NULL (deny) when the GUC is unset. |
| 5 | UUIDv4 public IDs | Every public id uses `gen_random_uuid()` via `UUIDPKMixin`. No sequential ids anywhere in the schema. |

## How to verify

1. Run the full test suite: `cd backend && . .venv/bin/activate && pytest -q`. Expected:
   - `test_rls.py` — three tests (RLS blocks SELECT, RLS blocks INSERT, no-GUC → zero rows).
   - `test_auth.py` — four tests (signup/me/logout flow, bad password generic 401, `/me` requires cookie, no `password_hash` in responses).
   - `test_docs_rls.py` — cross-tenant doc isolation.
   - `test_sharing.py` — viewer-can't-delete, viewer-can't-patch, share-link revoke.
2. Hit rate-limit: `for i in {1..40}; do curl -sw '%{http_code}\n' -o /dev/null -X POST localhost:8000/auth/login -H content-type:application/json -d '{"email":"a@b.c","password":"x"}'; done` — first ~30 return 401, remainder return 429.
3. Security headers: `curl -sI localhost:8000/healthz | grep -E 'X-Content-Type-Options|X-Frame-Options|Content-Security-Policy|Referrer-Policy'` — all four present.
4. WS origin check: `websocat --header 'Origin: https://evil.example' ws://localhost:8000/ws/docs/<any-id>` closes with 1008. A browser from `http://localhost:5173` connects fine.
5. Startup assertion: `ENV=prod make backend.dev` without setting `JWT_SECRET` raises immediately.
6. Load test (requires k6 installed): `k6 run --vus 50 --duration 30s loadtest/docs.js`. All checks should be green at ~50 VUs on a laptop; the rate limiter is scoped to auth so load-reading does not trigger 429s.
7. Snapshot pruning: in an editor tab, take ~35 snapshots quickly — only the 30 most recent autosaves remain; any user-labeled ones are preserved.

## Shipping notes

- Set `ENV=prod`, a real `JWT_SECRET`, and front the app with TLS before any non-local run. The `Secure` cookie flag depends on `ENV=prod`; nothing else changes.
- For a horizontal scale-out: move the rate limiter and `_rooms` map to Redis. The current code is deliberately single-worker; `code changes/03-realtime-collab.md` flagged this.
- `/auth/login` could grow a CAPTCHA/second-factor hook — out of scope for this plan; adding it is a drop-in between `current_identity` and `current_user`.
