/**
 * Side-panel scientific calculator backed by mathjs. Expressions are
 * evaluated in a *limited* mathjs context: `import`, `createUnit`, `evaluate`,
 * `parse`, and `simplify` are disabled to prevent programmatic math-space
 * tampering. Pure client-side — nothing is sent to the server.
 */
import { useEffect, useRef, useState } from "react";
import { all, create } from "mathjs";

const math = create(all);
math.import(
  {
    import: function () {
      throw new Error("disabled");
    },
    createUnit: function () {
      throw new Error("disabled");
    },
    evaluate: function () {
      throw new Error("disabled");
    },
    parse: function () {
      throw new Error("disabled");
    },
    simplify: function () {
      throw new Error("disabled");
    },
    derivative: function () {
      throw new Error("disabled");
    },
  },
  { override: true },
);

type Entry = { input: string; output: string };

export function Calculator({ onClose }: { onClose: () => void }) {
  const [input, setInput] = useState("");
  const [history, setHistory] = useState<Entry[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  function run(expr: string) {
    try {
      const scope: Record<string, unknown> = Object.fromEntries(
        history.map((h, i) => [`ans${i + 1}`, h.output]),
      );
      if (history.length) scope.ans = history[history.length - 1].output;
      // mathjs' parser-less `.evaluate` with a scope map is safe for arithmetic.
      const result = (math as unknown as { evaluate: (e: string, s?: Record<string, unknown>) => unknown }).evaluate(expr, scope);
      const output = math.format(result, { precision: 14 });
      setHistory((h) => [...h, { input: expr, output }]);
      setInput("");
    } catch (e) {
      setHistory((h) => [...h, { input: expr, output: `error: ${(e as Error).message}` }]);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" style={{ width: 460 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2>Scientific calculator</h2>
          <button onClick={onClose}>Close</button>
        </div>
        <div style={{ fontSize: 12, color: "#666" }}>
          Supports arithmetic, functions (sin, cos, log, sqrt…), units (<code>3 inch to cm</code>),
          vectors, matrices, complex numbers. Reference earlier results with <code>ans</code> /{" "}
          <code>ansN</code>.
        </div>

        <div
          style={{
            background: "#fafafa",
            border: "1px solid #eee",
            borderRadius: 4,
            padding: 8,
            margin: "12px 0",
            maxHeight: 280,
            overflow: "auto",
            fontFamily: "ui-monospace, monospace",
            fontSize: 13,
          }}
        >
          {history.length === 0 && <div style={{ color: "#999" }}>No calculations yet.</div>}
          {history.map((h, i) => (
            <div key={i}>
              <div>
                <span style={{ color: "#888" }}>›</span> {h.input}
              </div>
              <div style={{ paddingLeft: 12, color: h.output.startsWith("error:") ? "crimson" : "#1a73e8" }}>
                = {h.output}
              </div>
            </div>
          ))}
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (input.trim()) run(input.trim());
          }}
          style={{ display: "flex", gap: 8 }}
        >
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="e.g. (2+3)^4, sin(pi/6), 100 degC to degF, det([[1,2],[3,4]])"
            style={{ flex: 1, fontFamily: "ui-monospace, monospace", fontSize: 13, padding: 6 }}
          />
          <button type="submit">=</button>
        </form>
      </div>
    </div>
  );
}
