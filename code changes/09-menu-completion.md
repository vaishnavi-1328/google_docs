# Stage 09 — View / Edit / Format / Tools / Help menu completion

## Summary

Filled the last of the menu holes. Edit → Find & Replace opens a floating bar with `Find`, `Replace`, and `Replace all` powered by a direct ProseMirror text walk. View → Zoom in/out/reset scales the page with a CSS transform. Format → Underline now toggles an actual underline mark. Insert → Link and Insert → Table now create real TipTap nodes (Link mark, resizable 3×3 table with a header row). Help → Keyboard shortcuts was already live; Extension → Add-ons remains a clearly labeled "coming soon" stub (deliberate — a real plugin system is out of scope, pretending to ship one would be worse than being honest about it).

## Files added / changed

- `frontend/package.json` — adds `@tiptap/extension-link`, `@tiptap/extension-underline`, and the four `@tiptap/extension-table*` packages.
- `frontend/src/editor/FindReplace.tsx` — floating find-and-replace bar; walks `editor.state.doc.descendants` for text matches; replaces back-to-front so earlier positions aren't invalidated.
- `frontend/src/editor/Editor.tsx` — registers Underline/Link/Table extensions; adds `showFind` + `zoom` state; global `Ctrl+F` / `Ctrl+H` handler; passes `onOpenFindReplace`, `zoom`, `onZoom` to the Toolbar; wraps the editor page in a `transform: scale(zoom)` container.
- `frontend/src/editor/Toolbar.tsx` — Edit → Find and replace now invokes `onOpenFindReplace`; View → Zoom in/out/reset use `onZoom`; Format → Underline wired to `toggleUnderline`; Insert → Table uses `insertTable({rows:3,cols:3,withHeaderRow:true})`; Insert → Link uses `setLink({href})`.

## Decisions

- **Find & Replace is a hand-rolled walk, not `prosemirror-search`.** Our needs are small (plaintext, whole-doc, no regex). The walk is ~40 lines and avoids another plugin that would add its own decoration layer and race with Yjs's existing selection decorations.
- **Zoom via CSS transform, not editor font-size.** Using `transform: scale(z)` keeps the layout stable (headers stay headers, images stay in-position) and matches the Google Docs behavior where "View → Zoom" visually scales the page.
- **Table defaults to 3×3 with header row.** Mirrors Google Docs' default. Table resizing uses the stock TipTap `resizable: true` which gives column-drag handles.
- **Extension menu stays a stub.** Shipping a fake marketplace felt dishonest; a real plugin runtime is a multi-week project in its own right and is correctly deferred.

## Guardrails traceability

| Guardrail | Enforcement at end of this stage |
|---|---|
| 1–5 | All unchanged. No new server surface. Link marks use the stock TipTap sanitizer; `openOnClick: true` with `autolink: true` is safe because the parser rejects `javascript:` URLs. |

## How to verify

1. `cd frontend && npm install && npm run dev`.
2. Edit → Find and replace (or Ctrl+F / Ctrl+H) → bar appears; type a word that exists in the doc, click Find — count shows; Replace / Replace all mutates text through a single Yjs-friendly transaction (co-editor tab sees the replaced content).
3. View → Zoom in → page scales up; Zoom out → down; Reset zoom shows current %.
4. Format → Underline → selected text underlined. Same via Ctrl+U (handled by the Underline extension itself).
5. Insert → Table → 3×3 appears with a header row; drag column borders to resize.
6. Insert → Link → paste a URL → selection becomes a link; clicking it opens in a new tab (TipTap's default `openOnClick`).
7. Help → Keyboard shortcuts → modal lists the bindings.

## Known gaps

- **No comment thread sidebar** for the `commenter` role. The DB table is there; the UI is still deferred.
- **Find is plaintext-only.** No regex, no case toggles. Easy to add; left out to keep this stage small.
- **Underline isn't serialized to Markdown** (markdown has no standard underline); PDF/HTML/DOCX/EPUB honor it.
