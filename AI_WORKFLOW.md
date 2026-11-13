# AI Workflow Note

## How I used Claude Code

This project was built entirely through Claude Code (the CLI), running in an interactive session against the codebase. I used it as a pair programmer that could read files, write code, run shell commands, and iterate on errors — all in one conversation.

---

## Workflow pattern

### 1. Requirements → staged plan

I gave Claude the `task.md` requirements and `guardrails.md` security constraints and asked it to plan in stages before writing any code. It produced an 11-stage plan (`PLAN.md`) covering scaffold → auth → editor → real-time → sharing → export → version history → media → formulas → menus → hardening.

Staging was deliberate: each stage produces something demoable and independently verifiable, so issues surface early rather than after the whole system is built.

### 2. Code generation with context

For each stage, Claude read the relevant existing files before generating new ones. This kept generated code consistent with the actual codebase rather than producing boilerplate that conflicts with existing patterns.

Example prompt pattern:
> "Read deps.py and models/__init__.py, then implement the sharing routes following the same session and RLS patterns used in docs.py."

### 3. Error-driven iteration

The most productive loop was: run the app → paste the browser error or backend traceback → Claude diagnoses and fixes. Errors were treated as specs: the stack trace told Claude exactly which file, line, and invariant was violated.

Key examples of this loop:
- **TipTap + y-prosemirror crash** (`Cannot read properties of undefined (reading 'doc')`) — required 6 iterations to fully diagnose. The root cause was `@tiptap/extension-collaboration-cursor` accessing `ySyncPluginKey` state during plugin `init` before the ProseMirror view was mounted. The fix was removing `CollaborationCursor` and creating the TipTap editor imperatively inside `useEffect` so it never ran during React's render phase.
- **SQLAlchemy autobegin conflict** (`A transaction is already begun on this Session`) — appeared in both the WebSocket auth handler and the sharing invite route. Claude identified the pattern (calling `s.begin()` after `s.execute()` triggers autobegin) and fixed both sites.
- **WeasyPrint Python 3.14 incompatibility** (`'super' object has no attribute 'transform'`) — Claude diagnosed the upstream incompatibility and switched to `fpdf2` (pure Python, no native deps).

### 4. Security as a constraint, not an afterthought

The guardrails were loaded at the start of every planning step. Claude checked each generated route against them: does this read `tenant_id` from the request body? Does this skip the membership check? Does this expose the password hash? This made security properties explicit and reviewable in the changelogs rather than implicit.

---

## What worked well

- **Diagnosis speed** — pasting a full stack trace got a correct root-cause explanation in one turn for most bugs.
- **Consistency across files** — because Claude read existing files before generating new ones, patterns (session handling, RLS setup, error response shapes) stayed consistent without manual coordination.
- **Changelogs as a byproduct** — asking Claude to document each stage in `code changes/` produced a reviewable audit trail of every decision and trade-off.

## What required the most iteration

- **TipTap + Yjs + React lifecycle** — this interaction has no single canonical solution in the documentation. It required reading the compiled bundle source of `@tiptap/extension-collaboration-cursor`, `y-prosemirror`, and `@tiptap/react` to understand exactly when each piece of state was accessed. Claude got there but it took more back-and-forth than purely backend work.
- **React StrictMode** — StrictMode's intentional double-invocation of effects exposed a real incompatibility with y-prosemirror. The fix (disabling StrictMode) is a workaround, not a solution. A proper fix would require an upstream change to y-prosemirror.

---

## Prompting principles that helped

1. **Give the error, not just the symptom** — "it crashes" is not as useful as the full stack trace with file + line numbers.
2. **Ask for diagnosis before fix** — "what is causing this and why?" before "fix it" produced better solutions.
3. **Stage the work** — asking for one feature at a time was more reliable than "build the whole sharing system."
4. **Read before write** — explicitly asking Claude to read a file before modifying it prevented conflicts with existing code.
