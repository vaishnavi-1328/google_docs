# Collab Docs

A Google Docs–inspired collaborative document editor built as a multi-tenant SaaS. Multiple users can edit the same document simultaneously with live cursor awareness, offline persistence, role-based sharing, version history, and multi-format export.

---

## Features

| Category | Details |
|---|---|
| **Editor** | Rich text via TipTap/ProseMirror — headings, lists, tables, images, code blocks, blockquotes |
| **Real-time collaboration** | Yjs CRDT over WebSockets — convergent edits, no conflicts |
| **Offline** | IndexedDB local persistence — edits survive network loss and sync on reconnect |
| **Insert** | Images (uploaded to server), Mermaid flowcharts, KaTeX equations, freehand drawings |
| **Export** | PDF, Markdown, plain text, DOCX, EPUB |
| **Sharing** | Invite users by email with viewer / commenter / editor roles; anyone-with-link share links |
| **Version history** | Automatic snapshots every 5 min + manual labeled snapshots; one-click restore |
| **Tools** | Scientific calculator (mathjs), find & replace, zoom |
| **Multi-tenant** | Each workspace is fully isolated — Postgres RLS enforces isolation even if app logic forgets |
| **Auth** | Argon2id passwords, httpOnly JWT session cookies |

---

## Architecture

```
frontend/          React + TypeScript + Vite
  src/
    editor/        TipTap editor, toolbar, custom nodes
    sharing/       Share dialog, ACL management
    versions/      Version history browser
    tools/         Scientific calculator
    api.ts         Typed fetch client

backend/           Python FastAPI + SQLAlchemy 2 + PostgreSQL 16
  app/
    routes/        auth, docs, sharing, export, versions, attachments
    ws/            Yjs y-websocket sync endpoint
    exporters/     PDF (fpdf2), MD, TXT, DOCX, EPUB
    models/        ORM models with UUIDv4 PKs
    deps.py        FastAPI dependency injection (auth, tenant session)
    authz.py       Document role resolution
    middleware.py  Rate limiting, security headers
  alembic/         6 migrations with RLS policies
  tests/           pytest — auth, RLS, sharing
```

**Collaboration engine:** Yjs CRDT (chosen over hand-rolled OT — handles rich text, offline sync, and drawings cleanly with the official y-websocket protocol). The server relays sync messages and persists the merged Yjs state to Postgres on disconnect.

---

## Security guardrails

1. **Hashed credentials** — Argon2id via passlib; password hash never returned by any API endpoint.
2. **UUIDv4 public IDs** — `gen_random_uuid()` default on every table; no sequential integers in URLs.
3. **Server-derived tenant scoping** — `tenant_id` is extracted from the signed JWT, never from request body or query params.
4. **Postgres RLS** — Every tenant-scoped table has `ENABLE ROW LEVEL SECURITY` + `USING (tenant_id = current_setting('app.tenant_id')::uuid)`. The app sets `app.tenant_id` via `SELECT set_config(...)` per request. RLS is a mandatory second layer — it catches bugs in app-layer filtering.
5. **Membership verification** — Every request (HTTP and WebSocket) verifies the user is an active member of the claimed tenant before any query runs.

---

## Running the project

### Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | 3.12+ | [python.org](https://python.org) or `brew install python` |
| Node | 18+ | [nodejs.org](https://nodejs.org) or `brew install node` |
| PostgreSQL | 16 | `brew install postgresql@16` or Docker |

---

### Step 1 — Clone and configure environment

```bash
git clone <repo-url>
cd ajaia_assesment

cp .env.example .env
```

Open `.env` and set a JWT secret (required — everything else has sensible defaults):

```bash
# .env
JWT_SECRET=replace-this-with-a-long-random-string-at-least-32-chars
POSTGRES_PASSWORD=docs
```

All other defaults (`localhost:5432`, `docs` user/db, `http://localhost:5173` CORS) work out of the box.

---

### Step 2 — Start PostgreSQL

**Option A — Homebrew (macOS, no Docker needed):**
```bash
make db.local
```
This starts PostgreSQL 16, creates the `docs` role and `docs` database, and prints a confirmation.

**Option B — Docker:**
```bash
make db.up
```

---

### Step 3 — Run database migrations

```bash
make db.migrate
```

This applies all 6 Alembic migrations including schema creation, RLS policies, and indexes.

---

### Step 4 — Install and start the backend

```bash
make backend.install   # one-time: creates .venv + pip install
make backend.dev       # starts FastAPI on http://localhost:8000
```

Verify it's up:
```bash
curl http://localhost:8000/healthz
# → {"status":"ok"}
```

---

### Step 5 — Install and start the frontend

Open a **second terminal**:

```bash
make frontend.install  # one-time: npm install
make frontend.dev      # starts Vite on http://localhost:5173
```

---

### Step 6 — Open the app

Go to **http://localhost:5173** in your browser.

1. Click **Sign up** — enter an email, password, your name, and a workspace name
2. You land on the document list — click **New document**
3. The editor opens — start typing

---

### Testing features

| Feature | How to test |
|---|---|
| **Rich text** | Use the toolbar or keyboard shortcuts (Cmd+B bold, Cmd+I italic, Cmd+Z undo) |
| **Real-time collaboration** | Open the same doc URL in a second browser window (sign up with a different email first, then invite them via File → Share) |
| **Offline editing** | Type some text, stop the backend (`Ctrl+C`), keep typing — status bar shows "Offline". Restart backend — changes sync automatically |
| **Export** | File → Download → pick PDF / Markdown / DOCX / EPUB / TXT |
| **Share link** | File → Share → "Anyone with link" → copy link → open in incognito |
| **Version history** | File → Version history — snapshots are created automatically every 5 min, or manually via "Save snapshot" |
| **Insert flowchart** | Insert → Flowchart — edit the Mermaid DSL, diagram re-renders live |
| **Insert equation** | Insert → Equation — type LaTeX, renders via KaTeX |
| **Insert drawing** | Insert → Drawing — freehand canvas |
| **Calculator** | Tools → Calculator — supports full mathjs expressions (`sin(pi/2)`, `sqrt(2)`, `12 kg * 9.8 m/s^2`) |
| **Find & replace** | Edit → Find & replace, or Cmd+F |

---

### Running tests

```bash
make test
# or
cd backend && .venv/bin/pytest -v
```

Tests cover: signup/login flow, password hash never exposed in API responses, cross-tenant reads blocked by RLS, document ACL enforcement.

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | built from POSTGRES_* vars | SQLAlchemy connection string |
| `POSTGRES_USER` | `docs` | DB user |
| `POSTGRES_PASSWORD` | `docs` | DB password |
| `POSTGRES_DB` | `docs` | DB name |
| `POSTGRES_HOST` | `localhost` | DB host |
| `POSTGRES_PORT` | `5432` | DB port |
| `JWT_SECRET` | — | **Required.** Secret for HS256 JWT signing |
| `JWT_ALG` | `HS256` | JWT algorithm |
| `SESSION_TTL` | `86400` | Session lifetime in seconds |
| `ALLOWED_ORIGINS` | `http://localhost:5173` | Comma-separated CORS origins |
| `UPLOAD_ROOT` | `uploads/` | Local path for attachment storage |
| `VITE_API_BASE` | `http://localhost:8000` | Frontend → backend HTTP base URL |
| `VITE_WS_BASE` | `ws://localhost:8000` | Frontend → backend WebSocket base URL |

---

## API reference

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/signup` | Create account + tenant |
| `POST` | `/auth/login` | Issue session cookie |
| `POST` | `/auth/logout` | Clear session cookie |
| `GET` | `/auth/me` | Current user + tenant |
| `GET` | `/docs` | List documents in tenant |
| `POST` | `/docs` | Create document |
| `GET` | `/docs/{id}` | Fetch document metadata |
| `PATCH` | `/docs/{id}` | Rename document |
| `DELETE` | `/docs/{id}` | Delete document |
| `POST` | `/docs/{id}/export?format=pdf\|md\|txt\|docx\|epub` | Export document |
| `POST` | `/docs/{id}/attachments` | Upload image attachment |
| `GET` | `/docs/{id}/attachments/{aid}` | Serve attachment |
| `GET` | `/docs/{id}/acl` | List ACL entries + share links |
| `POST` | `/docs/{id}/invite` | Invite user by email |
| `DELETE` | `/docs/{id}/invite/{uid}` | Revoke user access |
| `POST` | `/docs/{id}/share-link` | Create share link |
| `DELETE` | `/docs/{id}/share-link/{lid}` | Revoke share link |
| `GET` | `/docs/{id}/snapshots` | List version snapshots |
| `POST` | `/docs/{id}/snapshots` | Create labeled snapshot |
| `POST` | `/docs/{id}/snapshots/{sid}:restore` | Restore snapshot |
| `WS` | `/ws/docs/{id}` | Yjs real-time sync (y-websocket protocol) |

---

## Running tests

```bash
cd backend
make test
# or directly:
.venv/bin/pytest tests/ -v
```

Tests cover: signup/login flow, password hash never exposed, cross-tenant read/write blocked by RLS, document ACL enforcement, sharing invite flow.

---

## Development notes

### Database migrations

```bash
# Create a new migration
.venv/bin/alembic revision --autogenerate -m "description"

# Apply all pending migrations
make db.migrate

# Downgrade one step
.venv/bin/alembic downgrade -1
```

### Key design decisions

**Yjs over hand-rolled OT** — Yjs is a battle-tested CRDT library with native support for ProseMirror (via y-prosemirror), offline sync via IndexedDB, and awareness (cursor positions). Rolling OT for rich text is a multi-month project with well-known edge cases. Yjs satisfies the "convergent real-time edits" requirement with far less risk.

**fpdf2 for PDF export** — WeasyPrint requires native system libraries (pango, cairo, gobject) that are incompatible with Python 3.14 on macOS at time of writing. fpdf2 is pure Python, produces smaller output, and has zero native dependencies.

**CollaborationCursor removed** — `@tiptap/extension-collaboration-cursor` v3.0.0 accesses `ySyncPluginKey` state during plugin `init`, which runs before the ProseMirror view is mounted. This causes a crash in certain initialization orders. Awareness state (user presence) is still set on the y-websocket provider — cursor decorations are the only missing piece.

**StrictMode disabled** — `y-prosemirror`'s sync plugin reads `fragment.doc` synchronously during ProseMirror plugin construction. React 18 StrictMode double-invokes effects in development, which can destroy the Y.Doc between the two invocations. This is a known upstream issue; StrictMode is disabled until y-prosemirror adds a fix.

---

## Project structure walkthrough

```
code changes/   Per-stage changelogs (00-scaffold → 10-hardening)
guardrails.md   Security constraints that informed every design decision
task.md         Original requirements
```

Each `code changes/NN-*.md` file documents: what changed, files touched, decisions made, guardrails impacted, and how to verify the stage.
