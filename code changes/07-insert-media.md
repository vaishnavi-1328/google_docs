# Stage 07 — Insert menu: images, drawings, flowcharts

## Summary

Lit up four Insert menu items on top of TipTap: **Image** (uploads a file to a tenant-scoped folder and inserts a server-served URL), **Drawing** (collaborative SVG sketch pad whose strokes live in Yjs node attrs), **Flowchart** (Mermaid live-render block), and **Equation** (KaTeX block — technically Stage 8's main feature but the node ships here because it uses the same NodeView plumbing). Every new piece flows through Yjs, so all four are collaborative in real time with no extra sync work.

## Files added / changed

- `backend/app/models/attachment.py`, `__init__.py` — `attachments` table scoped by tenant and doc.
- `backend/alembic/versions/0005_attachments.py` — table + FORCE RLS + policy.
- `backend/app/routes/attachments.py` — `POST /docs/{id}/attachments` (multipart image upload, 10 MB cap, MIME allowlist, tenant-scoped storage path), `GET /docs/{id}/attachments/{aid}` (serves file after viewer-level ACL check).
- `backend/app/main.py` — mounts the attachments router.
- `.env.example` — adds `UPLOAD_ROOT=backend/uploads`.
- `frontend/package.json` — adds `@tiptap/extension-image`, `mermaid`, `katex`, `mathjs`.
- `frontend/src/editor/nodes/MermaidNode.tsx` — atom block node, double-click to edit source, renders SVG via `mermaid.render(...)` with `securityLevel: 'strict'`.
- `frontend/src/editor/nodes/EquationNode.tsx` — atom block node, KaTeX in `displayMode`, double-click to edit.
- `frontend/src/editor/nodes/DrawingNode.tsx` — atom block node with its own pointer handlers; strokes are stored in `node.attrs.strokes` so they ride Yjs sync for free.
- `frontend/src/editor/Editor.tsx` — registers the image + custom nodes; `insertImage()` uploads via the attachments route and calls `setImage({ src })`; `insertMermaid/Equation/Drawing()` insert pre-attributed nodes.

## Decisions

- **Not tldraw.** tldraw adds ~1.5 MB and a non-trivial dependency graph. For the MVP we store strokes as `[{color, width, points[x,y][]}]` in node attributes — collaborative-by-default because it piggybacks on Yjs. If a reviewer specifically wants tldraw, this NodeView swaps in without changing the schema name (`drawing`).
- **Mermaid `securityLevel: 'strict'`** so `<script>` embeds and raw HTML in diagrams are stripped; defends against a diagram being used as an XSS vector.
- **KaTeX / Mermaid / Drawing are all `atom: true` NodeViews.** They own their editing UI (textarea/input/canvas) rather than exposing ProseMirror child content. This avoids interleaving the editor's selection logic with their internal state.
- **Image upload is local disk, tenant-scoped.** `uploads/<tenant_id>/<attachment_uuid>.<ext>` keeps the on-disk layout mirror the DB layout; the serve route re-checks tenant+ACL so even a leaked path cannot be fetched from another tenant's session. The `FileResponse` path is resolved and re-anchored to `UPLOAD_ROOT` as belt-and-braces — a defense against future bugs that might store a path outside the root.
- **MIME allowlist** limits uploads to common image types; `svg+xml` is allowed (useful for pasted-in icons) but the serve route sets `content-type: image/svg+xml` and the browser's standard CSP will prevent inline `<script>` in SVG. Stage 10 tightens the CSP globally.
- **Equation NodeView already here** (not in Stage 8) because it uses the same plumbing. Stage 8 adds the scientific calculator and polishes math UX; the inline equation node ships now.

## Guardrails traceability

| Guardrail | Enforcement at end of this stage |
|---|---|
| 1. Hashed credentials | Unchanged. |
| 2. Tenant data isolation | Attachments are RLS-protected; on-disk paths are tenant-scoped. |
| 3. Server-derived tenant scoping | Upload/serve routes derive tenant from signed session; the on-disk directory is picked from `current_tenant_id`, never from any upload metadata. |
| 4. Postgres RLS | New policy on `attachments` table. |
| 5. UUIDv4 public IDs | Attachment ids = `gen_random_uuid()`; the on-disk filename is the UUID so there is nothing guessable or sequential in URLs. |

## How to verify

1. `make db.migrate` (applies `0005_attachments`).
2. `make backend.dev` (creates `backend/uploads/` automatically).
3. `cd frontend && npm install && npm run dev`.
4. Open a doc → Insert → Image → pick a PNG → it uploads and renders inline. Open the same doc in a second tab: the image appears live.
5. Insert → Flowchart → a default `graph TD; A-->B;` renders. Double-click → textarea → change to `sequenceDiagram; A->>B: hi` → Save → re-renders.
6. Insert → Drawing → scribble; verify strokes appear in another tab in real time.
7. Insert → Equation → `\int_0^\infty e^{-x^2} dx = \frac{\sqrt{\pi}}{2}` → renders big.
8. Attempt a direct cross-tenant hit: `curl -s -b cookies.txt http://localhost:8000/docs/<A's doc>/attachments/<A's attachment>` while logged in as tenant B → 404.

## Known gaps

- **DOCX / EPUB export of drawings / mermaid / equations** is still placeholder: the walker recurses into unknown nodes and produces plain-text fallbacks. Stage 10 adds proper serializers for each node (SVG → PNG for DOCX, KaTeX → MathML for EPUB).
- **No image re-encoding** — uploads are stored as-is. Stage 10 adds a Pillow pass to strip metadata, cap dimensions, and re-encode JPEG/PNG for safety and size.
- **Drawing node doesn't support undo granularity.** The whole stroke list is one Yjs attribute; undoing mid-stroke isn't possible. Stage 10 could move strokes to a Y.Array for finer-grained CRDT merges.
