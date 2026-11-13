import { Node, mergeAttributes } from "@tiptap/core";
import { NodeViewWrapper, ReactNodeViewRenderer, type NodeViewProps } from "@tiptap/react";
import { useState } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";

function EquationView(props: NodeViewProps) {
  const { node, updateAttributes } = props;
  const src: string = node.attrs.src || "E = mc^2";
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(src);
  let html = "";
  let err: string | null = null;
  try {
    html = katex.renderToString(src, { throwOnError: false, displayMode: true });
  } catch (e) {
    err = (e as Error).message;
  }
  return (
    <NodeViewWrapper className="equation-node">
      {editing ? (
        <div>
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            style={{ width: "100%", fontFamily: "monospace", fontSize: 13 }}
          />
          <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
            <button
              onClick={() => {
                updateAttributes({ src: draft });
                setEditing(false);
              }}
            >
              Save
            </button>
            <button onClick={() => { setDraft(src); setEditing(false); }}>Cancel</button>
          </div>
        </div>
      ) : (
        <div onDoubleClick={() => setEditing(true)} style={{ cursor: "pointer" }}>
          {err ? (
            <pre style={{ color: "crimson" }}>{err}</pre>
          ) : (
            <span dangerouslySetInnerHTML={{ __html: html }} />
          )}
          <div style={{ fontSize: 11, color: "#888" }}>Equation — double-click to edit</div>
        </div>
      )}
    </NodeViewWrapper>
  );
}

export const EquationNode = Node.create({
  name: "equation",
  group: "block",
  atom: true,
  draggable: true,
  addAttributes() {
    return { src: { default: "E = mc^2" } };
  },
  parseHTML() {
    return [{ tag: "div[data-type='equation']" }];
  },
  renderHTML({ HTMLAttributes }) {
    return ["div", mergeAttributes(HTMLAttributes, { "data-type": "equation" }), HTMLAttributes.src || ""];
  },
  addNodeView() {
    return ReactNodeViewRenderer(EquationView);
  },
});
