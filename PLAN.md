# Plan: Lightweight Collaborative Docs (Google Docs–inspired SaaS)

## Context

`task.md` asks for a Google Docs–style collaborative editor as a SaaS: rich text editing, Google Docs–style toolbar (File / Edit / View / Insert / Format / Tools / Extension / Help with submenus), real-time collaboration over websockets, offline persistence via IndexedDB + localStorage so docs survive a server restart and reappear when the user comes back online, multi-format export (PDF / Markdown / Text / EPUB / DOCX), drawings, flowcharts, formulas, scientific calculations, and link-/role-based sharing (read / read+write / comment; everyone-with-link vs. restricted).

`guardrails.md` adds hard constraints:
1. Passwords/account info hashed, never exposed.
2. Strict per-tenant data isolation.
3. Every query / API route / background job filters by `tenant_id` (or `user_id`), never trusting client-supplied tenant IDs — always verified against the authenticated session.
4. Postgres **row-level security (RLS)** as a mandatory second defense layer.
5. Public-facing IDs must be UUIDv4 / ULID (no sequential IDs).

Full Google Docs parity is a multi-month build; per user direction we ship an **MVP first, then layer features in stages**. Each stage ends with a markdown changelog in `code changes/` capturing what changed, which files were touched, decisions made, and how to verify.

## Decisions (locked in with user)

- **Scope strategy:** MVP first, then layered feature stages.
- **Backend:** Python **FastAPI** + **Postgres** with **RLS** policies, websockets via FastAPI, Argon2 password hashing, UUIDv4 for all public IDs.
- **Collab engine:** **Yjs (CRDT) via `y-websocket`**. Chosen over hand-rolled OT because Yjs handles rich text, offline sync, awareness/cursors, and drawings cleanly; the task's "OT" requirement is interpreted as "a real-time convergent-edits engine," which CRDT satisfies better. This decision is documented explicitly in Stage 2's changelog.
- **Frontend:** Vite + React + TypeScript, **TipTap** editor (ProseMirror-based, integrates with Yjs via `y-prosemirror`). TipTap gives us the toolbar surface area (formatting, headings, lists, tables, images) for free.
- **Offline:** `y-indexeddb` provider so edits persist locally and sync on reconnect; also mirrors satisfy task.md's "available when I start the server and look online" requirement.
- **Doc depth:** Per-stage changelog in `code changes/`.

## Stage Plan

Each stage is independently demoable. Each ends with `code changes/NN-<slug>.md`.

### Stage 0 — Repo scaffold & guardrails baseline
- Monorepo: `backend/` (FastAPI), `frontend/` (Vite+React+TS), `code changes/`, `docs/`.
- `docker-compose.yml` with Postgres 16.
- `.env.example`, `.gitignore`, Makefile targets (`make dev`, `make test`, `make db.migrate`).
- Backend: FastAPI app skeleton, `/healthz`, Alembic configured, settings via Pydantic `BaseSettings`.
- Frontend: Vite app boots, talks to `/healthz`.
- Guardrail hooks established: UUIDv4 helper, request-scoped `current_user` dependency, SQLAlchemy base model with `tenant_id` column + `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`.
- **Changelog:** `code changes/00-scaffold.md`.

### Stage 1 — Auth + tenant isolation + RLS (guardrails stage)
- Tables: `users` (Argon2 password hash, email citext unique), `tenants`, `memberships` (user↔tenant with role).
- JWT session cookies (httpOnly, SameSite=Lax, Secure in prod).
- `current_user` + `current_tenant` FastAPI dependencies; **tenant_id is derived from the session, never from request body/query**.
- **RLS policies** on every tenant-scoped table: `USING (tenant_id = current_setting('app.tenant_id')::uuid)`. Connection middleware runs `SET LOCAL app.tenant_id = :tid` per request.
- Tests: cross-tenant read/write attempts must 404/403; RLS denies even if app layer forgets to filter.
- **Changelog:** `code changes/01-auth-and-rls.md` (documents guardrails 1–5 end-to-end).

### Stage 2 — Document model + single-user rich text editor
- Tables: `documents` (id UUIDv4, tenant_id, owner_id, title, created_at, updated_at, ydoc_state BYTEA), `document_snapshots` (periodic Yjs state snapshots for version history later).
- REST: `POST /docs`, `GET /docs`, `GET /docs/:id`, `PATCH /docs/:id`, `DELETE /docs/:id` — all RLS-protected.
- Frontend: TipTap editor mounted, Google-Docs-style **toolbar shell** with the 8 top-level menus (File / Edit / View / Insert / Format / Tools / Extension / Help). Only a subset of submenu items are wired this stage (Save, New, Open, basic Edit, basic Format). The remaining items render as disabled-but-visible so the UI feels complete and layers can light them up.
- Local persistence: `y-indexeddb` so docs survive reloads with no server.
- **Rationale doc** for Yjs-over-OT lives in this changelog.
- **Changelog:** `code changes/02-editor-and-docs.md`.

### Stage 3 — Real-time collaboration over websockets
- Websocket endpoint `/ws/docs/:id` in FastAPI; authenticates via session cookie, authorizes against `memberships` + doc ACL (next stage adds finer ACLs).
- Server relays Yjs sync messages and awareness (cursors, selections, user color/name).
- On disconnect, server persists latest `ydoc_state` to Postgres; on first connect, server seeds the client with the stored state.
- Multi-tab + multi-user convergence verified manually and with a Playwright test.
- **Changelog:** `code changes/03-realtime-collab.md`.

### Stage 4 — Sharing & ACLs
- Tables: `document_acls` (doc_id, principal_type ∈ {user, link}, principal_id, role ∈ {viewer, commenter, editor}), `share_links` (UUIDv4 token, doc_id, role, expires_at, revoked_at).
- Share dialog UI in File → Share: "Restricted" vs. "Anyone with the link"; per-user invites; role picker.
- Enforcement in both REST and WS layers; RLS policy extended so a user can read a doc if they are a member of the tenant **and** have an ACL grant (or the doc is link-shared and they present a valid token).
- Comments table added (empty UI shell) to support `commenter` role later.
- **Changelog:** `code changes/04-sharing-and-acls.md`.

### Stage 5 — Export: PDF / Markdown / Text / DOCX / EPUB
- Backend export worker: ProseMirror JSON → target format.
  - Markdown / Text: `prosemirror-markdown` on the frontend or a Python port server-side.
  - DOCX: `python-docx`.
  - PDF: WeasyPrint (HTML → PDF) from TipTap's HTML output.
  - EPUB: `ebooklib`.
- File → Download submenu wired to `GET /docs/:id/export?format=…`.
- Each export route is tenant+ACL filtered.
- **Changelog:** `code changes/05-export.md`.

### Stage 6 — Version history & File menu polish
- Snapshot Yjs state every N edits or T seconds (background job, tenant-scoped).
- File → Version history: timeline view, preview, restore.
- Wire remaining File menu items (New, Open from list, Save — Save is a no-op indicator since autosave is implicit, but kept for UX parity).
- **Changelog:** `code changes/06-version-history.md`.

### Stage 7 — Insert menu: images, drawings, flowcharts
- Images: upload to object storage (local disk in dev, S3-compatible interface), tenant-scoped paths, signed URLs.
- Drawings: embedded **tldraw** canvas stored as a Yjs subdoc so drawings are collaborative too.
- Flowcharts: Mermaid live-render block (`insert → flowchart` opens a code+preview pane).
- **Changelog:** `code changes/07-insert-media.md`.

### Stage 8 — Formulas & scientific calculations (Tools + Insert)
- Inline math: KaTeX rendering of `$…$` and `$$…$$` blocks.
- Tools → Scientific calculator: side panel powered by **mathjs** (expression eval, units, matrices, calculus basics). Pure client — no eval of untrusted strings on the server.
- Insert → Equation: KaTeX editor with live preview.
- **Changelog:** `code changes/08-formulas-and-calc.md`.

### Stage 9 — Remaining menus: View / Edit / Format / Tools / Extension / Help
- Wire all remaining submenu items to real behavior where applicable (word count, find & replace, zoom, page setup, print → PDF export, keyboard shortcuts help).
- Extension menu: stub Marketplace shell (clearly labeled "coming soon") so the UI matches task.md's 8-menu requirement without pretending to ship a plugin system.
- **Changelog:** `code changes/09-menu-completion.md`.

### Stage 10 — Hardening: performance, load, polish
- Doc-list virtualization; Yjs GC + snapshot pruning; connection backoff; rate limits per tenant; basic observability (structured logs + request IDs).
- Security pass: cookie flags, CSRF for state-changing REST, CSP, WS origin check, Argon2 params tuned, dependency audit.
- Load test with `locust` or `k6`: N concurrent editors on one doc.
- **Changelog:** `code changes/10-hardening.md`.

## `code changes/` folder convention

Each file:
- `# Stage NN — <title>`
- **Summary** — 2–4 sentences.
- **Files added / changed** — bullet list with paths.
- **Decisions** — any trade-offs, with the "why."
- **Guardrails touched** — which of the 5 guardrails this stage reinforces (especially stages 1, 4, 5, 10).
- **How to verify** — exact commands + manual steps + screenshots where useful.
- **Known gaps** — what this stage intentionally leaves for later.

The folder also contains a running `README.md` index so future-readers can navigate stages in order.

## Critical files (first time each appears)

- `backend/app/main.py` — FastAPI entrypoint (stage 0)
- `backend/app/db.py` — SQLAlchemy engine + per-request `SET LOCAL app.tenant_id` (stage 1)
- `backend/app/models/*.py` — ORM models with tenant_id + UUIDv4 (stages 1–7)
- `backend/alembic/versions/*` — migrations including RLS `CREATE POLICY` statements (stage 1+)
- `backend/app/deps.py` — `current_user`, `current_tenant`, `require_doc_role` (stages 1, 4)
- `backend/app/ws/docs.py` — Yjs sync websocket (stage 3)
- `backend/app/exporters/*.py` — per-format exporters (stage 5)
- `frontend/src/editor/Editor.tsx` — TipTap + Yjs + y-indexeddb (stages 2–3)
- `frontend/src/editor/Toolbar.tsx` — 8-menu Google-Docs-style toolbar (stage 2, filled in across stages)
- `frontend/src/sharing/ShareDialog.tsx` — share UX (stage 4)
- `code changes/NN-*.md` — per-stage changelog.

## Verification (end-to-end, run after each stage)

- Backend: `pytest` (unit + RLS cross-tenant tests), `ruff`, `mypy`.
- Frontend: `vitest`, `tsc --noEmit`, `playwright test`.
- Manual smoke: two browser profiles editing the same doc show converging state and live cursors (stage 3+); kill backend, reload — doc still opens from IndexedDB (stage 2+); cross-tenant URL probe returns 404 (stage 1+).
- `docker compose up` must bring up a fully working stack from a clean clone at every stage.

## Guardrails traceability

| Guardrail | Enforced in stage | How |
|---|---|---|
| 1. Hashed credentials | 1 | Argon2id via `passlib`; passwords never logged; `/me` never returns hash. |
| 2. Tenant data isolation | 1, 4 | `tenant_id` on every row; dependency-injected `current_tenant`. |
| 3. Server-derived tenant scoping | 1 | `current_tenant` comes from JWT claims verified against `memberships`; request body `tenant_id` is ignored. |
| 4. Postgres RLS | 1, 4 | `ENABLE ROW LEVEL SECURITY` + policies per table; connection sets `app.tenant_id` per request. |
| 5. UUIDv4 public IDs | 0, 1 | Base model default `gen_random_uuid()`; no integer IDs exposed in URLs or payloads. |
