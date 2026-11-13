# Stage 08 — Formulas & scientific calculator

## Summary

Finished the math pillar. The inline **Equation** block (KaTeX, double-click to edit) shipped in Stage 7 as a side-effect of the shared NodeView plumbing; this stage adds the **Tools → Scientific calculator** side panel. It's a modal powered by mathjs with a REPL-style history: arithmetic, functions, units (`3 inch to cm`), matrices, complex numbers, and back-references (`ans`, `ansN`). All evaluation is client-side — no server round-trips, so nothing untrusted is ever `eval`'d on the backend.

## Files added / changed

- `frontend/src/tools/Calculator.tsx` — modal REPL. History pushed with `{input, output}`; `ans` and `ans1 … ansN` injected into the mathjs scope. The mathjs instance has `import` / `createUnit` / `evaluate` / `parse` / `simplify` / `derivative` overridden with throwing stubs so a malicious expression from a copy-paste can't reach for the parser to extend the math space or redefine units at runtime.
- `frontend/src/editor/Editor.tsx` — Tools → Scientific calculator now opens the modal (`onOpenCalculator`).

## Decisions

- **Pure client math.** mathjs is non-trivial to lock down; running it server-side would mean giving a Node runtime access to arbitrary user input. Keeping evaluation in the browser means an abuse vector hits the user, not the tenant. The symmetric risk — an untrusted expression stealing data from the browser — is bounded because mathjs with `import`/`createUnit`/`evaluate`/`parse` disabled is a numeric calculator, not a scripting engine.
- **Modal REPL instead of a visible pad.** A Google-Docs-style sidebar would be nicer long-term, but the modal pattern already exists (Share, Version history) and keeps the Stage small. Promoting to a dockable side panel is a Stage 10 polish item.
- **KaTeX equation node ships in Stage 7.** Keeping that decision here so the Stage 7 → Stage 8 boundary is honest: Stage 7 built the equation editing surface, Stage 8 completes the "Tools" half of the math feature.

## Guardrails traceability

| Guardrail | Enforcement at end of this stage |
|---|---|
| 1. Hashed credentials | Unchanged. |
| 2. Tenant data isolation | Calculator is pure client; no new data paths. |
| 3. Server-derived tenant scoping | n/a |
| 4. Postgres RLS | n/a |
| 5. UUIDv4 public IDs | n/a |

## How to verify

1. `cd frontend && npm run dev` (no backend changes).
2. Open any doc → Tools → Scientific calculator.
3. Try: `2 + 2`, `sin(pi/6)`, `(1+2i) * (3-4i)`, `100 degC to degF`, `det([[1,2],[3,4]])`, then `ans * 2`, then `ans1 + ans2`.
4. Insert → Equation → `\int_0^\infty e^{-x^2} dx = \tfrac{\sqrt{\pi}}{2}` → double-click → edit → Save. Second tab: the edited equation appears via Yjs.

## Known gaps

- **Calculator history is in-memory only.** Closing the modal forgets history. Stage 10 adds a localStorage-backed history plus an "insert result at cursor" button.
- **No LaTeX-to-mathjs round trip.** You can type into the equation node and calculate separately, but there's no "evaluate this equation" button. A cross-wire is possible since both speak similar notation, but deferred.
