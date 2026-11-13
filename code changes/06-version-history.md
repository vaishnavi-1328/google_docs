# Stage 06 — Version history

## Summary

Added version history: periodic `Autosave` snapshots are taken by the realtime websocket every 5 minutes while a room is alive, and users can also take named snapshots on demand. A File → Version history dialog lists all snapshots, previews the content (by replaying the Yjs update into a throwaway `Y.Doc` client-side), and restores the selected version by overwriting `documents.ydoc_state` with the chosen snapshot.

## Files added / changed

- `backend/app/routes/versions.py` — new endpoints:
  - `POST   /docs/{id}/snapshots`           (editor+)
  - `GET    /docs/{id}/snapshots`           (viewer+)
  - `GET    /docs/{id}/snapshots/{sid}`     (viewer+, returns raw Yjs update bytes)
  - `POST   /docs/{id}/snapshots/{sid}:restore` (editor+)
- `backend/app/main.py` — mounts the versions router.
- `backend/app/ws/docs.py` — periodic autosave: `_periodic_snapshotter` fires every `SNAPSHOT_INTERVAL_SECONDS` (default 5 min) while the room has clients; writes a snapshot row with `label='Autosave'` + updates `ydoc_state`.
- `frontend/src/api.ts` — typed clients: `snapshotCreate`, `snapshotList`, `snapshotBlob`, `snapshotRestore`, `SnapshotMeta`.
- `frontend/src/versions/VersionHistory.tsx` — modal with a timeline list + a right-side preview that applies the fetched update into an off-screen `Y.Doc` and reads the ProseMirror XML fragment.
- `frontend/src/editor/Editor.tsx` — File → Version history now opens the dialog; after restore, the page reloads to pick up the overwritten state.

## Decisions

- **Snapshots store full Yjs state, not diffs.** Yjs updates are already compact and self-contained; storing the full-state blob keeps restore trivial (`doc.ydoc_state = snap.ydoc_state`) and makes `GET snapshot/{sid}` a single read.
- **Preview rendered on the client** by applying the fetched update bytes into a scratch `Y.Doc` and reading the fragment. This reuses the frontend's already-loaded Yjs code. A server-side HTML preview would need the TipTap schema in Python.
- **Autosave interval = 5 minutes** chosen so a busy hour-long editing session produces ~12 rows per doc — a manageable timeline — while a short visit might not snapshot at all. Stage 10 adds snapshot pruning (keep N most recent + significant ones).
- **Restore is cold, not hot.** Overwriting `ydoc_state` doesn't disturb the in-memory `_Room` — currently-connected clients keep editing the pre-restore state. The frontend therefore `location.reload()`s after restore, which disconnects, reconnects, and re-seeds from Postgres. A hot restore (evict room + rebroadcast new state to all peers) is noted as a known gap.
- **Editor role required to snapshot/restore**, viewer to list/preview. Lets a shared viewer scroll through history without granting write rights.

## Guardrails traceability

| Guardrail | Enforcement at end of this stage |
|---|---|
| 1. Hashed credentials | Unchanged. |
| 2. Tenant data isolation | `document_snapshots` already has `FORCE` RLS from Stage 2's `0003_documents` migration; the new routes use `tenant_session`. |
| 3. Server-derived tenant scoping | Tenant id from signed session; snapshot ids are UUIDv4 from the URL. |
| 4. Postgres RLS | Snapshot fetches are gated by both `authz.effective_role` and the tenant-scoped session. |
| 5. UUIDv4 public IDs | Snapshot ids are UUIDv4 (`gen_random_uuid()`). |

## How to verify

1. `make backend.dev` (picks up the new router + periodic task). No new migration — tables exist since Stage 2.
2. Open a doc, type a few lines, File → Version history → Snapshot now → name it "v1". A new entry appears in the timeline with the text preview.
3. Type more content, wait 5 minutes with the tab open — a new `Autosave` entry appears. (For testing, drop `SNAPSHOT_INTERVAL_SECONDS` to 10 and verify quickly.)
4. Click "v1" → Restore this version → page reloads → doc is back to the v1 state.
5. Viewer-only user: File → Version history shows the list and previews, but the "Restore this version" button errors with 403.

## Known gaps

- **Hot restore evicts no one.** Peers currently connected keep collaborating on the pre-restore state until the room naturally empties. For the MVP this is acceptable (restore is rare and admins can tell peers to refresh), but Stage 10 should either close all sockets on restore or atomically swap the in-memory YDoc.
- **No snapshot pruning.** A doc edited for weeks will accumulate many `Autosave` rows. Stage 10 adds a retention policy (keep 24h-hourly, 7d-daily, 30d-weekly, plus all user-labeled snapshots).
- **Preview quality is text-only.** It strips ProseMirror XML tags; a richer preview (rendered through TipTap read-only) is a future polish item.
