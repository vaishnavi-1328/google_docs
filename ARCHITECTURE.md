# Architecture Note

## Overview

Collab Docs is a multi-tenant SaaS collaborative editor. The system has three runtime components: a Vite/React frontend, a FastAPI backend, and a PostgreSQL database. Real-time sync uses the standard y-websocket protocol over a WebSocket connection to the same backend process.

```
Browser
  │
  ├── HTTP (fetch, credentials: include)
  │     └── FastAPI  ──┐
  │                    ├── SQLAlchemy ──> PostgreSQL 16 (RLS)
  └── WebSocket        │
        └── y-websocket handler ──┘
              (Yjs sync protocol)
```

---

## Frontend

**Stack:** React 18, TypeScript, Vite, TipTap v3, Yjs

The frontend is a single-page app with hash-based routing (`#/doc/:id`). There are three top-level views: `AuthPage`, `DocsList`, and `Editor`.

### Editor

The editor is built on **TipTap** (a ProseMirror wrapper). TipTap was chosen because it ships production-ready extensions for tables, images, code blocks, and collaborative editing, avoiding the need to implement ProseMirror plugins from scratch.

Collaborative editing uses **Yjs** — a CRDT library that handles concurrent edits without conflicts or coordination. The key design constraint is that all three Yjs objects (`Y.Doc`, `IndexeddbPersistence`, `WebsocketProvider`) and the TipTap editor are created together inside a single `useEffect`, so they share one lifecycle. This avoids a race condition where React's cleanup could destroy the `Y.Doc` while the editor still held a reference to its `XmlFragment`.

**Offline persistence** is provided by `y-indexeddb`, which mirrors the document state to the browser's IndexedDB. When the backend is unreachable, edits accumulate locally and sync automatically on reconnect — the WebSocket provider handles this natively.

### State flow

```
User types
  → ProseMirror transaction
  → Yjs update (Collaboration extension)
  → WebsocketProvider broadcasts update to server
  → Server applies update to in-memory Y.Doc
  → Server broadcasts to other connected clients
  → Other clients apply update
  → ProseMirror re-renders

Page load
  → IndexeddbPersistence loads local state immediately (fast)
  → WebSocket connects, server sends sync-step1
  → Client replies with sync-step2 (what server is missing)
  → Server replies with sync-step2 (what client is missing)
  → Document converges to latest state
```

---

## Backend

**Stack:** Python 3.14, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16, pycrdt

### Request lifecycle

Every HTTP request goes through three middleware layers (outermost first):

1. **CORSMiddleware** — attaches `Access-Control-Allow-Origin` headers. Registered last in code so it runs first, ensuring CORS headers appear even on 429/500 responses from inner middleware.
2. **SecurityHeadersMiddleware** — adds `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`, `Referrer-Policy`.
3. **RateLimitMiddleware** — per-IP token bucket (120 req / 60 s) on `/auth/*` endpoints.

Then FastAPI dependency injection:

```
Request
  → current_identity()   — decodes the signed JWT cookie → (user_id, tenant_id)
  → current_user()       — verifies (user_id, tenant_id) is a live membership row
  → tenant_session()     — opens a DB session, runs SET app.tenant_id = :tid
  → route handler        — all queries now filtered by RLS
```

`tenant_id` is never read from the request body or query string. It comes exclusively from the signed JWT, which is verified against the `memberships` table on every request.

### Multi-tenancy and RLS

Every tenant-scoped table has:

```sql
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON documents
  USING (tenant_id = current_setting('app.tenant_id')::uuid);
```

The app sets `app.tenant_id` via `SELECT set_config('app.tenant_id', :t, true)` at the start of every transaction. `set_config` with `is_local=true` scopes the value to the transaction, so it cannot bleed across connection-pool reuses.

RLS is a **mandatory second defense layer** — not a primary filter. The app-layer `WHERE tenant_id = :tid` clauses are still present. RLS catches bugs in app-layer filtering (e.g. a developer forgets a WHERE clause) and is enforced by the database regardless of what the application does.

### WebSocket (real-time sync)

The WebSocket handler (`/ws/docs/{doc_id}`) implements the y-websocket wire protocol:

- **message type 0** (sync): sub-messages for step1 (state vector exchange), step2 (send missing updates), and update (broadcast a change)
- **message type 1** (awareness): user presence — cursor position, name, color — relayed opaque to all other clients

Each document has an in-memory `_Room` object holding the live `Y.Doc` and the set of connected WebSocket clients. When the last client disconnects, the merged Yjs state is persisted back to the `documents.ydoc_state` column in Postgres, and the room is evicted from memory. A periodic background task snapshots the state every 5 minutes to `document_snapshots` while anyone is connected.

Authentication on WebSocket upgrade uses the same session cookie — `Cookie(alias="session")` is extracted from the upgrade request headers by FastAPI before the connection is accepted.

### Export pipeline

The client sends TipTap's HTML output in the POST body. The server converts it to the requested format:

| Format | Library | Notes |
|---|---|---|
| PDF | fpdf2 | Pure Python; WeasyPrint was the original choice but has a Python 3.14 incompatibility with native pango bindings |
| Markdown | html2text | |
| Plain text | BeautifulSoup | |
| DOCX | python-docx | |
| EPUB | ebooklib | |

Sending HTML from the client avoids running a full ProseMirror schema in Python. The server still checks viewer access before exporting.

---

## Database schema

```
users          — platform-level (no tenant_id)
tenants        — workspace root
memberships    — user ↔ tenant, role
documents      — tenant_id, owner_id, title, ydoc_state (binary Yjs)
document_snapshots — tenant_id, document_id, ydoc_state, label
document_acls  — tenant_id, document_id, user_id, role
share_links    — tenant_id, document_id, role, revoked_at
attachments    — tenant_id, document_id, storage_path
```

All primary keys are `UUID DEFAULT gen_random_uuid()`. No integer IDs are exposed in any URL or API response.

---

## Security decisions

| Decision | Rationale |
|---|---|
| Argon2id for passwords | Resistant to GPU cracking; recommended by OWASP over bcrypt for new systems |
| httpOnly JWT cookie | Not accessible from JavaScript; immune to XSS token theft |
| `tenant_id` from JWT only | Prevents a user from impersonating another tenant by crafting a request body |
| RLS as second layer | Database enforces isolation even if app-layer filtering has a bug |
| UUIDv4 PKs everywhere | Prevents enumeration attacks (sequential IDs leak record counts and ordering) |
| Origin check on WebSocket | Refuses upgrades from origins not in `ALLOWED_ORIGINS`; prevents cross-site WebSocket hijacking |
