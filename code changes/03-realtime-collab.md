# Stage 03 — Realtime collaboration over websockets

## Summary

Implemented the `/ws/docs/{doc_id}` websocket in FastAPI that speaks the y-websocket wire protocol. Multiple browsers editing the same document now converge in real time, show each other's cursors and names (awareness), and the server persists the merged Yjs state to Postgres whenever the room empties — so a later reader (or a crashed browser) picks up from the latest server-side state. Authentication reuses the Stage 1 session cookie; authorization re-checks tenant membership *and* that the target document actually belongs to that tenant.

## Files added / changed

- `backend/requirements.txt` — adds `y-py` (Python Yjs bindings) and `websockets`.
- `backend/app/ws/__init__.py`, `backend/app/ws/docs.py` — minimal y-websocket server:
  - varuint encoding/decoding utilities for sync-message framing;
  - `_Room` holds one in-memory `YDoc` + the set of connected sockets per doc;
  - handshake: on connect the server sends `sync-step1` so clients can reply with what they're missing;
  - sync updates are applied to the room's YDoc *and* broadcast to all other sockets;
  - awareness messages are opaque and relayed as-is;
  - on last-disconnect, `_persist_and_maybe_evict` writes the merged state back to `documents.ydoc_state` under the correct tenant GUC, then drops the room.
- `backend/app/main.py` — mounts the websocket router.
- `frontend/src/editor/Editor.tsx` — attaches a `y-websocket` provider to the same Yjs doc that `y-indexeddb` already drives, wires `CollaborationCursor` for remote carets, and shows a live connection state ("Saved to cloud · live" / "Connecting…" / "Offline · changes saved locally").
- `frontend/src/editor/editor.css` — styles for the remote-caret pill.

## Decisions

- **Hand-rolled y-websocket server instead of a Node sidecar.** `y-py` gives us a Python `YDoc` that can `apply_update` / `encode_state_as_update`, so we can live entirely inside FastAPI. The alternative (a separate `y-websocket` Node process) would double the deployment surface and force the auth cookie across two origins. The wire protocol we implement is small (two message kinds, three sync subtypes); varuint framing is ~20 lines.
- **Auth at connect time, not per message.** The session cookie is checked in `_authorize` before `accept()`. If the cookie is missing/invalid or the user isn't a member of the tenant that owns the doc, we close with policy-violation (`1008`) without accepting — browsers won't retry blindly.
- **RLS still enforced through the websocket path.** `_authorize` and `_persist_and_maybe_evict` both open a session with `SET LOCAL app.tenant_id` before reading/writing `documents`. The websocket is not a bypass.
- **Server is a relay plus a snapshotter.** We don't re-derive content on the server; we apply received updates into the room's YDoc so the state we persist is the merged result, but we rebroadcast the client's original update payload unchanged. This keeps the server dumb and the convergence guarantees firmly on Yjs's math.
- **Persist on last disconnect, not on every update.** Writing to Postgres on every keystroke is wasteful — per-user autosave is already in IndexedDB. Snapshotting on empty-room + Stage 6's timed background snapshots covers the "server restart and come back" requirement without hammering the DB.
- **Awareness messages are opaque.** They contain cursor positions and the user label; we never introspect them. If we later want to redact other-tenant names (we can't, because peers in a room share a tenant), this is still the right boundary.
- **Room name in the URL path (`/ws/docs/{id}`), room keyed by doc UUID in the server map.** Means we never trust a client-supplied room name — only the path, and the path is verified against the tenant before opening.

## Guardrails traceability

| Guardrail | Enforcement at end of this stage |
|---|---|
| 1. Hashed credentials | Unchanged. |
| 2. Tenant data isolation | A client cannot open a websocket to a doc that isn't in their tenant; the `documents.get` lookup runs under `SET LOCAL app.tenant_id` so RLS enforces it even if the dependency logic regressed. |
| 3. Server-derived tenant scoping | `tenant_id` comes from the signed session cookie only; the path contains only a `doc_id`, never a tenant id. |
| 4. Postgres RLS | Both the authz lookup and the `UPDATE documents SET ydoc_state = …` write use tenant-scoped sessions. |
| 5. UUIDv4 public IDs | `doc_id` is parsed as `UUID` by FastAPI — malformed ids return 422 before auth runs. |

## How to verify

1. `make backend.install` (picks up `y-py`, `websockets`).
2. `make backend.dev`, `cd frontend && npm install && npm run dev`.
3. Open two browser profiles (or one normal + one incognito), sign up as two different users **in the same tenant** — the simplest way for now is to have the second user also sign up with a distinct email but the same `tenant_name`; a membership-invite flow lands in Stage 4. For a purely single-user check, open the same doc in two tabs of the same profile.
4. In tab A, click **+ New document**, start typing. In tab B, open the same doc URL (`#/doc/<id>`). Text appears in both tabs as you type; moving the caret in A shows a labeled caret in B.
5. Status line toggles between **Saved to cloud · live** and **Offline · changes saved locally** when you stop/start the backend. Reload while offline — the doc still opens from IndexedDB.
6. `pytest -q` — the Stage 1/2 RLS tests still pass; Stage 3 does not add new backend tests (a Playwright convergence test lands with Stage 10 hardening).
7. Verify server-side persistence: close both tabs (room empties → server writes state), then open the doc again fresh in a cleared browser — content is still there, served from `documents.ydoc_state`.

## Known gaps

- **Single process only.** The in-memory `_rooms` map doesn't survive a restart or scale across workers. Horizontally scaling needs a Redis pub/sub for cross-worker broadcast; that's a Stage-10 concern once we actually need it. State itself is durable in Postgres — a restart loses in-flight cursor/awareness but no content.
- **No doc-level ACLs yet.** Membership-in-tenant is required but any member can open any doc in the tenant. Stage 4 adds per-doc viewer/commenter/editor roles and link sharing.
- **No rate limits on the socket.** Stage 10 adds per-connection message-rate and total-doc-size caps.
- **No origin check on the WS upgrade.** Stage 10 adds an explicit allowlist against `settings.allowed_origins_list`.
- **Playwright convergence test** deferred to Stage 10 (needs the full UI to be stable).
