/**
 * Minimal find & replace bar. Walks the ProseMirror doc, finds plaintext
 * matches of `query` inside text nodes, and either highlights them (visually
 * via native window.find for the current page) or replaces them via a single
 * transaction when the user clicks Replace / Replace all.
 *
 * This is deliberately not a `prosemirror-search` fork — the surface is small
 * and we can afford the simpler implementation.
 */
import { useState } from "react";
import type { Editor } from "@tiptap/react";

export function FindReplace({ editor, onClose }: { editor: Editor; onClose: () => void }) {
  const [q, setQ] = useState("");
  const [r, setR] = useState("");
  const [count, setCount] = useState<number | null>(null);

  function findAll(): { from: number; to: number }[] {
    const hits: { from: number; to: number }[] = [];
    if (!q) return hits;
    editor.state.doc.descendants((node, pos) => {
      if (node.isText && node.text) {
        let idx = 0;
        const t = node.text;
        while (true) {
          const i = t.indexOf(q, idx);
          if (i < 0) break;
          hits.push({ from: pos + i, to: pos + i + q.length });
          idx = i + q.length;
        }
      }
      return true;
    });
    return hits;
  }

  function doFindCount() {
    setCount(findAll().length);
  }

  function replaceOne() {
    const hits = findAll();
    if (hits.length === 0) {
      setCount(0);
      return;
    }
    const first = hits[0];
    editor.chain().focus().insertContentAt({ from: first.from, to: first.to }, r).run();
    setCount(findAll().length);
  }

  function replaceAll() {
    const hits = findAll();
    if (hits.length === 0) {
      setCount(0);
      return;
    }
    // Work back-to-front so earlier positions aren't invalidated by later edits.
    const tr = editor.state.tr;
    for (let i = hits.length - 1; i >= 0; i--) {
      const { from, to } = hits[i];
      tr.insertText(r, from, to);
    }
    editor.view.dispatch(tr);
    setCount(0);
  }

  return (
    <div
      style={{
        position: "fixed",
        top: 80,
        right: 20,
        background: "#fff",
        border: "1px solid #dadce0",
        borderRadius: 6,
        padding: 10,
        zIndex: 50,
        boxShadow: "0 2px 10px rgba(0,0,0,0.1)",
        width: 320,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <strong>Find and replace</strong>
        <button onClick={onClose}>Close</button>
      </div>
      <div style={{ display: "grid", gap: 6, marginTop: 8 }}>
        <input placeholder="Find" value={q} onChange={(e) => setQ(e.target.value)} />
        <input placeholder="Replace with" value={r} onChange={(e) => setR(e.target.value)} />
        <div style={{ display: "flex", gap: 6 }}>
          <button onClick={doFindCount}>Find</button>
          <button onClick={replaceOne}>Replace</button>
          <button onClick={replaceAll}>Replace all</button>
        </div>
        <div style={{ fontSize: 12, color: "#666" }}>
          {count === null ? "" : `${count} match${count === 1 ? "" : "es"}`}
        </div>
      </div>
    </div>
  );
}
