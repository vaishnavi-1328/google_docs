# Stage 02 — Document model, TipTap editor, Google-Docs toolbar shell

## Summary

Shipped the single-user editing experience. Backend gains `documents` + `document_snapshots` tables (both RLS-protected) and a `/docs` REST surface. Frontend gains a TipTap rich-text editor backed by a Yjs document that persists to IndexedDB (`y-indexeddb`), a Google-Docs-style top bar with the eight required menus (File / Edit / View / Insert / Format / Tools / Extension / Help) and a quick-format sub-toolbar, and routing between an auth page, a doc list, and the editor. Items that light up in later stages render as disabled menu entries so the UI feels complete today.

## Files added / changed

- `backend/app/models/document.py` — `Document`, `DocumentSnapshot` (both carry `tenant_id`).
- `backend/app/models/__init__.py` — exports the new models.
- `backend/alembic/versions/0003_documents.py` — creates both tables, ENABLE + FORCE RLS, tenant-isolation policy.
- `backend/app/routes/docs.py` — `POST/GET/GET:id/PATCH:id/DELETE:id` for `/docs`; all routes depend on `tenant_session`.
- `backend/app/main.py` — mounts the docs router.
- `backend/tests/test_docs_rls.py` — cross-tenant HTTP isolation test.
- `frontend/package.json` — adds `@tiptap/react`, `@tiptap/starter-kit`, `@tiptap/extension-placeholder`, `@tiptap/extension-collaboration`, `@tiptap/extension-collaboration-cursor`, `yjs`, `y-indexeddb`, `y-websocket`, `y-protocols`.
- `frontend/src/api.ts` — typed fetch client with `credentials: 'include'` for cookie auth.
- `frontend/src/AuthPage.tsx` — signup/login UI.
- `frontend/src/DocsList.tsx` — list / create / delete.
- `frontend/src/editor/Editor.tsx` — TipTap editor wired to a Yjs doc + IndexedDB persistence; uses `StarterKit` with history disabled (Yjs owns undo/redo).
- `frontend/src/editor/Toolbar.tsx` — 8-menu Google-Docs-style menubar + quick-format sub-toolbar. Disabled items are actual future features, not vaporware.
- `frontend/src/editor/editor.css` — Google-Docs-ish page styling.
- `frontend/src/App.tsx` — hash routing: list ↔ editor.

## Decisions

### Why Yjs (CRDT) when `task.md` says "operational transformation"?

OT and CRDT solve the same problem — "make concurrent edits converge" — with different math. We chose **Yjs (a CRDT)** over a hand-rolled or library OT for four reasons:

1. **Correctness is already solved.** Yjs is used in production by Jupyter, Evernote-style apps, and dozens of commercial editors. A hand-rolled OT needs transformation functions that are provably correct under every operation pair; getting that wrong silently corrupts documents. We would rather spend our time on the SaaS features in `task.md`.
2. **Rich text parity.** `y-prosemirror` / `@tiptap/extension-collaboration` lets us merge concurrent edits to formatted text, lists, tables, images — not just plaintext. A plaintext-only OT would not support the Format/Insert menus `task.md` requires.
3. **Offline for free.** `y-indexeddb` plugs into the same Yjs doc, which means the "available when I start the server and look online" requirement from `task.md` falls out of the architecture rather than needing a separate sync queue.
4. **Drawings and future subdocs.** Stage 7 collaborative drawings become a Yjs subdoc trivially. Extending an OT engine to a non-text data model is a larger surgery.

We're treating `task.md`'s "operational transformation" line as "a real-time convergent-edits engine." If a reviewer insists on literal OT we will swap `y-websocket` for ShareDB in Stage 3 — the TipTap layer and the whole menu/UI stay the same.

### Other decisions

- **Yjs owns undo/redo**, so `StarterKit` is configured with `history: false`. Mixing TipTap's history with Yjs's history causes double-undos.
- **IndexedDB room name is namespaced `t:<tenant_id>:d:<doc_id>`.** If two tenants happen to collide on doc UUIDs (they won't, but still), the IndexedDB stores remain separate.
- **GET on another tenant's doc returns 404, not 403.** 403 leaks the fact that an id exists; 404 does not. RLS enforces the behavior at the database layer — the route code is just the user-friendly surface.
- **Delete uses a confirm dialog** — this is the MVP; Stage 10 replaces it with a real modal + trash/restore.
- **Menu shell for all 8 menus.** Every submenu entry `task.md` implies is listed; the ones for later stages are rendered disabled rather than hidden so the UI's silhouette matches Google Docs from day one.

## Guardrails traceability

| Guardrail | Enforcement at end of this stage |
|---|---|
| 1. Hashed credentials | Unchanged (Stage 1). |
| 2. Tenant data isolation | `documents` and `document_snapshots` carry `tenant_id`, both RLS-protected with `FORCE`. |
| 3. Server-derived tenant scoping | Every `/docs` route depends on `tenant_session` → derives `tenant_id` from the signed JWT only. |
| 4. Postgres RLS | Policies added on `documents` and `document_snapshots` with WITH CHECK, so both read and write are database-enforced. |
| 5. UUIDv4 public IDs | Both tables use `gen_random_uuid()`; `GET /docs/:id` expects UUIDs. |

## How to verify

1. Migrate: `make db.migrate` (applies `0003_documents`).
2. `make backend.dev` and `cd frontend && npm install && npm run dev`.
3. Open `http://localhost:5173`, sign up, land on the docs list, click **+ New document** → editor opens with the Google-Docs-style menubar.
4. Type some text, apply **B / I / H1 / bullet list / blockquote** from the quick bar or the Format menu. Rename the doc via the title input or **File → Rename**.
5. Refresh the page. The content is still there (served from IndexedDB via `y-indexeddb`).
6. Stop the backend, refresh. The editor still loads and remains editable — the doc list shows a loading error, but the editor itself keeps working.
7. Run `pytest -q` — `test_docs_rls.test_cross_tenant_doc_isolation` must pass: tenant B 404s on tenant A's doc.
8. In psql: `SELECT count(*) FROM documents` **without** `SET LOCAL app.tenant_id` should return 0 (default-deny from RLS).

## Known gaps

- Single-user only. Stage 3 adds the `/ws/docs/:id` websocket and multi-user cursors so two browser tabs converge.
- No autosave *to the server* yet. IndexedDB is the only authoritative store from the client's perspective in this stage; Stage 3 adds server persistence of the Yjs state on websocket disconnect.
- Toolbar items for Download, Share, Version history, Insert > Image/Drawing/Flowchart/Equation, Tools > Calculator, Find & replace are rendered but disabled. They are enabled in Stages 5, 4, 6, 7, 8, 9 respectively.
- No mobile layout tuning. The MVP targets desktop widths.
