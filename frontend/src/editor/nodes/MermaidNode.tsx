import { Node, mergeAttributes } from "@tiptap/core";
import { NodeViewWrapper, ReactNodeViewRenderer, type NodeViewProps } from "@tiptap/react";
import { useEffect, useRef, useState } from "react";
import mermaid from "mermaid";

mermaid.initialize({ startOnLoad: false, theme: "default", securityLevel: "strict" });

function MermaidView(props: NodeViewProps) {
  const { node, updateAttributes } = props;
  const src: string = node.attrs.src || "graph TD;\n  A-->B;";
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(src);
  const [err, setErr] = useState<string | null>(null);
  const svgHost = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancel = false;
    (async () => {
      try {
        const { svg } = await mermaid.render(`m-${Math.random().toString(36).slice(2)}`, src);
        if (!cancel && svgHost.current) {
          svgHost.current.innerHTML = svg;
          setErr(null);
        }
      } catch (e: unknown) {
        setErr((e as Error).message);
      }
    })();
    return () => {
      cancel = true;
    };
  }, [src]);

  return (
    <NodeViewWrapper className="mermaid-node">
      {editing ? (
        <div>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={8}
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
          {err ? <pre style={{ color: "crimson" }}>{err}</pre> : <div ref={svgHost} />}
          <div style={{ fontSize: 11, color: "#888" }}>Mermaid — double-click to edit</div>
        </div>
      )}
    </NodeViewWrapper>
  );
}

export const MermaidNode = Node.create({
  name: "mermaid",
  group: "block",
  atom: true,
  draggable: true,
  addAttributes() {
    return { src: { default: "graph TD;\n  A-->B;" } };
  },
  parseHTML() {
    return [{ tag: "div[data-type='mermaid']" }];
  },
  renderHTML({ HTMLAttributes }) {
    return [
      "div",
      mergeAttributes(HTMLAttributes, { "data-type": "mermaid" }),
      ["code", {}, HTMLAttributes.src || ""],
    ];
  },
  addNodeView() {
    return ReactNodeViewRenderer(MermaidView);
  },
});
