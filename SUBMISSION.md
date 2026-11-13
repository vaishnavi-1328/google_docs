# Submission Checklist

## Included files

| Item | Location |
|---|---|
| Source code — backend (FastAPI + Python) | `backend/` |
| Source code — frontend (React + TypeScript) | `frontend/` |
| Local setup and run instructions | `README.md` |
| Architecture note | `ARCHITECTURE.md` |
| AI workflow note | `AI_WORKFLOW.md` |
| This file | `SUBMISSION.md` |
| Per-stage changelogs (11 stages) | `code changes/` |
| Original requirements | `task.md` |
| Security guardrails spec | `guardrails.md` |
| Walkthrough video URL | `WALKTHROUGH_VIDEO.txt` |

## Video recording:
https://drive.google.com/file/d/1evoTgqOZSY0EWFsRIl6e0z1aTg1zKWvW/view?usp=drive_link

Quick start for the reviewer:
```bash
cp .env.example .env
# edit .env: set JWT_SECRET=any-long-string
make db.local && make db.migrate
make backend.install && make backend.dev   # terminal 1
make frontend.install && make frontend.dev # terminal 2
# open http://localhost:5173
```

---

## What is working

- **Authentication** — signup, login, logout with Argon2id-hashed passwords and httpOnly JWT cookies
- **Multi-tenant isolation** — every table is RLS-protected; tenants are fully isolated at the Postgres layer
- **Document CRUD** — create, list, rename, delete documents
- **Rich text editor** — TipTap/ProseMirror with full formatting toolbar (bold, italic, headings, lists, tables, code blocks, blockquotes)
- **Real-time collaboration** — Yjs CRDT over WebSockets; multiple users editing the same document converge correctly
- **Offline persistence** — IndexedDB via y-indexeddb; edits survive backend restarts and sync on reconnect
- **Insert: images** — upload to server, stored tenant-scoped, rendered inline
- **Insert: flowcharts** — Mermaid DSL with live preview
- **Insert: equations** — KaTeX LaTeX rendering
- **Insert: drawings** — freehand SVG canvas, strokes stored in Yjs attrs
- **Export** — PDF (fpdf2), Markdown, plain text, DOCX (python-docx), EPUB (ebooklib)
- **Sharing** — invite users by email with viewer/commenter/editor role; anyone-with-link share links; revoke access
- **Version history** — automatic snapshots every 5 minutes + manual labeled snapshots; one-click restore
- **Scientific calculator** — mathjs side panel with expression history
- **Find & replace** — full text search with case-sensitivity toggle and replace-all
- **Zoom** — editor zoom control in the View menu
- **Security headers** — CSP, X-Frame-Options, Referrer-Policy on all responses
- **Rate limiting** — per-IP token bucket on auth endpoints

## What is incomplete

- **Collaboration cursors** — `@tiptap/extension-collaboration-cursor` v3.0.0 crashes on initialization due to a known incompatibility between `y-prosemirror`'s plugin state access and the TipTap v3 plugin lifecycle. User presence (name + color) is set on the WebSocket awareness channel — only the cursor decoration rendering is missing.
- **Live product URL** — not deployed; local setup works fully. A production deployment would add HTTPS, a managed Postgres (e.g. Supabase/RDS), object storage for attachments (e.g. S3), and environment-specific secrets.
- **Comments** — the `comments` table and `commenter` role are defined in the schema; the UI thread/comment panel is not wired up.
- **Extension marketplace** — the Extensions menu renders a "coming soon" stub; no plugin system is implemented.
- **Email invites** — invite currently requires the invitee to already have an account. A production flow would send an email via SendGrid/Resend and create the account on first click.

## What I would build next with another 2–4 hours

1. **Fix collaboration cursors** — pin `@tiptap/extension-collaboration-cursor` to a version compatible with y-prosemirror's plugin initialization order, or implement cursor decorations directly via a custom ProseMirror plugin using the awareness state already flowing through the WebSocket.
2. **Deploy to production** — Dockerfile for the FastAPI backend, static build served from a CDN (Vercel/Cloudflare Pages for frontend, Railway/Fly.io for backend + managed Postgres). ~45 minutes end-to-end.
3. **Inline comments** — thread anchored to a text range using ProseMirror marks, stored in the `comments` table, visible in a right sidebar. The Yjs awareness channel can broadcast comment presence in real time.
4. **Email notifications** — notify invited users and collaborators via a background task (FastAPI BackgroundTasks + Resend).
