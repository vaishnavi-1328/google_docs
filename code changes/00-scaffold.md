# Stage 00 — Repo scaffold & guardrails baseline

## Summary

Stood up the monorepo skeleton for the Collab Docs app: a FastAPI backend (Python 3.11+), a Vite + React + TypeScript frontend, Postgres 16 via docker-compose, and Alembic migrations. Added the baseline guardrail hooks — UUIDv4 primary keys via `pgcrypto`, a single `Base` + mixins module, and a `db.py` with one clearly-marked extension point where Stage 1 will wire per-request `SET LOCAL app.tenant_id` for RLS. No business logic yet; the app only serves `/healthz` and the frontend verifies it can reach the backend.

## Files added / changed

- `PLAN.md` — approved multi-stage plan copied into the project root.
- `.gitignore`, `.env.example`, `Makefile`, `docker-compose.yml` — local-dev plumbing.
- `backend/requirements.txt` — FastAPI, SQLAlchemy 2, psycopg 3, Alembic, Argon2/passlib (ready for Stage 1), python-jose for JWT (Stage 1), pytest, ruff, mypy.
- `backend/app/__init__.py`
- `backend/app/settings.py` — Pydantic `BaseSettings`; reads `.env`.
- `backend/app/db.py` — SQLAlchemy engine + `get_session` dependency. Explicit comment marking where Stage 1 will add the `SET LOCAL app.tenant_id` hook.
- `backend/app/main.py` — FastAPI app, CORS, `/healthz`.
- `backend/app/models/__init__.py`, `backend/app/models/base.py` — `Base`, `UUIDPKMixin` (server default `gen_random_uuid()`), `TimestampMixin`.
- `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`
- `backend/alembic/versions/0001_init_extensions.py` — enables `pgcrypto` + `citext`.
- `frontend/package.json`, `frontend/tsconfig.json`, `frontend/vite.config.ts`, `frontend/index.html`
- `frontend/src/main.tsx`, `frontend/src/App.tsx` — minimal page that hits `/healthz`.
- `code changes/README.md` — stage index.

## Decisions

- **FastAPI + Postgres + SQLAlchemy 2 + Alembic** chosen over FastAPI+Tortoise or Django because SQLAlchemy 2 has first-class async, clean Alembic integration, and — critically — gives us direct access to raw SQL for `CREATE POLICY` RLS statements in migrations.
- **`gen_random_uuid()` (pgcrypto)** over app-side UUIDs so the database is the single source of ID generation (guardrail 5), and server defaults survive even if application code forgets to set the id.
- **One `db.py` seam** for the Stage 1 `SET LOCAL app.tenant_id` hook — makes it impossible to open a connection that bypasses tenant context without editing this one file.
- **Monorepo over split repos** so `code changes/*.md` and `PLAN.md` live next to the code that implements them, and reviewers see the full picture in one tree.

## Guardrails touched

| Guardrail | Status at end of stage |
|---|---|
| 1. Hashed credentials | Deferred to Stage 1 (dependencies already pinned in `requirements.txt`). |
| 2. Tenant data isolation | Base model mixins scaffolded. `TenantScopedMixin` to arrive in Stage 1. |
| 3. Server-derived tenant scoping | Dependency slot reserved in `db.py`; no route trusts client input yet because there are no routes besides `/healthz`. |
| 4. Postgres RLS | `pgcrypto` + `citext` enabled; RLS policies arrive in Stage 1 migrations. |
| 5. UUIDv4 public IDs | ✅ Enforced at the schema level via `UUIDPKMixin` (`gen_random_uuid()`). |

## How to verify

1. `cp .env.example .env`
2. `make db.up` — brings up Postgres on `localhost:5432`.
3. `make backend.install` — creates `backend/.venv` and installs deps.
4. `make db.migrate` — runs migration `0001`, enables `pgcrypto` and `citext`. Confirm with:
   ```
   docker compose exec db psql -U docs -d docs -c "SELECT extname FROM pg_extension WHERE extname IN ('pgcrypto','citext');"
   ```
   Expect both rows.
5. `make backend.dev` — FastAPI listens on `:8000`. `curl -s localhost:8000/healthz` returns `{"status":"ok"}`.
6. `make frontend.install && make frontend.dev` — Vite serves on `:5173`. Open the page; it should display **Backend health: ok**.

## Known gaps

- No auth, no sessions, no tenants — Stage 1.
- No documents, no editor — Stage 2.
- No realtime collab engine wired — Stage 3.
- No tests yet beyond directory scaffolding; first real pytest suite lands with Stage 1's RLS cross-tenant tests.
- `JWT_SECRET` in `.env.example` is a placeholder and must be replaced with a long random string before any non-local run.
