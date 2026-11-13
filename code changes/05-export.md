# Stage 05 — Multi-format export (PDF / MD / TXT / DOCX / EPUB)

## Summary

Added `POST /docs/{id}/export?format=…` that turns the live TipTap HTML into a downloadable file in one of five formats plus HTML. The frontend's File → Download submenu now actually downloads. Access control reuses `authz.effective_role`: an unauthorized caller gets a 404 just like on the REST reads.

## Files added / changed

- `backend/requirements.txt` — adds `weasyprint`, `python-docx`, `ebooklib`, `html2text`, `beautifulsoup4`.
- `backend/app/exporters/__init__.py`, `backend/app/exporters/pipeline.py` — per-format converters from a shared HTML input. Each heavy library import is kept inside its own function so `make backend.dev` doesn't pay the WeasyPrint import cost unless someone actually exports a PDF.
- `backend/app/routes/export.py` — `POST /docs/{id}/export`, accepts `html` in the body, enforces viewer-at-minimum role, streams the file back with a `content-disposition` attachment header and a safe slugified filename.
- `backend/app/main.py` — mounts export router.
- `frontend/src/editor/Editor.tsx` — `download(fmt)` function; wires the toolbar `onDownload` prop so File → Download → *(format)* triggers a real download.

## Decisions

- **Export input is TipTap HTML, not Yjs state.** Rendering HTML from the serialized Yjs update would need a Python ProseMirror schema matching the one on the frontend — enormous surface area for the MVP. The browser already has the exact renderer; we let it serialize once (`editor.getHTML()`) and ship that to the server.
- **BeautifulSoup + python-docx walk** instead of pandoc. pandoc produces better output but adds a 300MB system dep. The current walker covers the MVP set (headings, paragraphs, bullet/numbered lists, blockquote, pre/code, hr) which is the subset `StarterKit` can produce today. Stage 8 extends this when we add KaTeX math nodes.
- **WeasyPrint for PDF** because it reads real CSS; the output is paginated and feels like Google Docs' "Download as PDF" rather than a raw screenshot. System libs (`pango`, `cairo`, `gdk-pixbuf`) must be installed; documented in the `How to verify` section.
- **EPUB from a single chapter** — "book" versus "one document" semantics line up with task.md's usage: an EPUB export is a reader-friendly single artifact, not a multi-chapter book.
- **Safe filename slugging.** `re.sub(r"[^A-Za-z0-9._-]+", "_", title)` to defeat response-splitting / content-disposition quoting bugs. Capped at 120 chars.
- **Access check reuses `effective_role`.** Viewer is enough to export — same as reading. If we later want to prohibit viewers from exporting (some orgs do), it's a one-line change to require `commenter` or `editor`.
- **HTML export** is included for free: makes it trivial to debug the pipeline (`format=html` returns the pre-conversion artifact).

## Guardrails traceability

| Guardrail | Enforcement at end of this stage |
|---|---|
| 1. Hashed credentials | Unchanged. |
| 2. Tenant data isolation | The export route depends on `tenant_session`; a cross-tenant export attempt 404s before the exporter runs. |
| 3. Server-derived tenant scoping | Tenant id from signed session; `?format=` is the only query param consulted, and it's an enum. |
| 4. Postgres RLS | The `db.get(Document, …)` call sits under the same tenant-scoped session, so RLS backs up the authz check. |
| 5. UUIDv4 public IDs | Route path is `UUID`-typed; invalid ids 422. |

## How to verify

1. Install system deps for WeasyPrint on macOS: `brew install cairo pango gdk-pixbuf libffi`. (On Ubuntu: `apt-get install libpango-1.0-0 libpangoft2-1.0-0`.)
2. `make backend.install && make backend.dev`.
3. Open any doc, type a heading + a few paragraphs + a bullet list + a blockquote, then File → Download → each of PDF, Markdown, Plain text, Word, EPUB. All five download; PDF renders paginated; DOCX opens in Word/Pages/LibreOffice; EPUB opens in Books/Calibre.
4. Negative test: in another tenant's session, `curl -s -b cookies.txt -X POST localhost:8000/docs/<other-tenants-doc>/export?format=md -H 'content-type: application/json' -d '{"html":"x"}'` → `404 not found`.

## Known gaps

- **Images / drawings / equations don't survive export yet** — Stage 7 and Stage 8 add those nodes; the exporter's walker already has fallbacks that recurse through unknown blocks, so they will export as plain text until we extend the dispatch table.
- **Tables are passed straight through for PDF/HTML** (they look fine) but **flattened for DOCX** (we render them as paragraphs). Stage 10 adds proper DOCX tables once the editor's tables extension is enabled.
- **No background export worker.** PDF of a huge doc would block one FastAPI worker. Stage 10 moves exports to an async queue once we have a reason to.
