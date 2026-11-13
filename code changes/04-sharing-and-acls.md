# Stage 04 — Sharing & ACLs

## Summary

Added per-document access control: owners can invite users by email at viewer / commenter / editor roles, and can mint UUIDv4 share links at any of those roles that produce URLs anyone (inside the same tenant) can open. Enforcement is centralized in `authz.effective_role` and applied in three places: REST routes under `/docs/*`, the sharing routes themselves, and the realtime websocket (viewers can observe the Yjs stream but their update frames are dropped). A `comments` table was added as a shell so `commenter` is a real role with somewhere to land in Stage 9.

## Files added / changed

- `backend/app/models/acl.py` — `DocumentACL`, `ShareLink`, role constants + rank.
- `backend/app/models/comment.py` — shell table for Stage 9.
- `backend/app/models/__init__.py` — exports.
- `backend/alembic/versions/0004_sharing.py` — creates `document_acls`, `share_links`, `comments`; adds RLS + role `CHECK` constraints on both role columns.
- `backend/app/authz.py` — `effective_role(user, doc, link_token?)` returning `None` / `viewer` / `commenter` / `editor` / `owner`; `has_at_least`.
- `backend/app/routes/docs.py` — `GET`/`PATCH` require at least viewer/editor respectively; `DELETE` requires owner. Non-permitted reads 404 (don't leak existence).
- `backend/app/routes/sharing.py` — new router under `/docs/{doc_id}`:
  - `GET /acl` — grants + active share links
  - `POST /invite` / `DELETE /invite/{user_id}`
  - `POST /share-link` / `DELETE /share-link/{link_id}`
- `backend/app/ws/docs.py` — `_authorize` also returns effective role; viewers/commenters see updates but cannot write (their sync-update frames are dropped before `apply_update`).
- `backend/app/main.py` — mounts the sharing router.
- `frontend/src/api.ts` — typed clients for ACL endpoints + `Role` / `AclEntry` / `ShareLink` / `AclResponse`.
- `frontend/src/sharing/ShareDialog.tsx` — Google-Docs-style share modal: people list, invite form, link-sharing section with copy/revoke.
- `frontend/src/editor/Editor.tsx` — File → Share now opens the dialog.
- `frontend/src/editor/editor.css` — `.modal` + `.modal-backdrop`.

## Decisions

- **`effective_role` is the single source of truth.** Every path (REST, WS, sharing) asks the same helper for the same answer; no inline "if owner or has acl" expressions scattered through the codebase. Adding (for example) an organization-wide "default role" later is a one-function change.
- **Link tokens are the `share_links.id` UUIDv4.** No extra `token` column, no separate hashing — a UUIDv4 token has >122 bits of entropy, which is more than most bearer tokens. Guardrail 5 is satisfied by construction.
- **Links are tenant-scoped.** A link can grant access to a doc *within a tenant*; using a link does not put a user into a tenant they weren't in. To prevent surprise, the invite endpoint auto-adds the invitee to the tenant as a plain `member` if they weren't already — otherwise invites would silently 404.
- **Owners are implicit, not an ACL row.** `documents.owner_id` is the one way to be an owner. This avoids the "can an editor demote the owner?" bug class entirely.
- **Role granting: only owner can grant `editor`.** Editors can grant viewer/commenter and mint links; editor-level link minting is deliberately allowed because that's how collaborators share outside the tenant via the same tenant invite flow above.
- **Unauthorized reads → 404, not 403.** 403 leaks the fact the id exists; 404 does not. The WS close code is `1008 Policy Violation` — browsers won't retry blindly.
- **WS writes from viewers are silently dropped**, not disconnected. Dropping lets a viewer stay subscribed and keep seeing updates; disconnecting would be noisy and would make "briefly open a view-only doc" worse.
- **Comments table is a shell** with `anchor TEXT` to hold a serialized ProseMirror selection later. Including it now so Stage 9's comment sidebar doesn't require a migration + redeploy.

## Guardrails traceability

| Guardrail | Enforcement at end of this stage |
|---|---|
| 1. Hashed credentials | Unchanged. |
| 2. Tenant data isolation | Every new table carries `tenant_id` and has `FORCE` RLS. `document_acls` and `share_links` only ever grant access *inside* the same tenant — a link cannot cross tenants. |
| 3. Server-derived tenant scoping | `effective_role` opens its lookups on a `tenant_session` whose GUC was set from the signed JWT; the sharing routes never consult a body/header `tenant_id`. |
| 4. Postgres RLS | Three new RLS-protected tables with policies + role `CHECK` constraints. |
| 5. UUIDv4 public IDs | ACL rows, share-link tokens, comments — all `gen_random_uuid()`. |

## How to verify

1. `make db.migrate` (applies `0004_sharing`).
2. Two tenants A and B (sign up twice). Owner A creates a doc in tenant A and `POST /docs/{id}/share-link {role: "editor"}`. Confirm the link opens the doc for any user **in tenant A** but 403s for B's users — and `GET /docs/{id}` returns 404 for B.
3. In the UI: File → Share → invite another user **by email**. They appear under "People with access"; downgrading them to Viewer and reconnecting from their browser shows that their typing is ignored (status stays "Saved to cloud · live" but the server drops writes).
4. Downgrade yourself from owner to editor (there is no UI for this yet; set via psql `UPDATE document_acls …` after inserting a row): confirm you can no longer `DELETE` the doc (owner required).
5. Revoke a share link in the dialog, reload the page, confirm the link is now inert.
6. Backend tests still green: `pytest -q`. (Dedicated ACL tests arrive in Stage 10's hardening pass.)

## Known gaps

- **No role-upgrade UI** for existing ACL entries — only invite (which upserts) and remove.
- **No "pending invitation" state** if the invited email has no account. Stage 10 adds email-based pre-grants.
- **Link URLs carry `?link=…`** but the backend does not yet consult the token for anonymous users; today it only elevates an already-tenant-member user. True anonymous link access requires a cookie-less code path and is deferred to Stage 10 when we finalize security headers.
- **Commenter role has no sidebar/UI yet.** The DB and policies are in place; Stage 9 adds the inline comment thread UI.
