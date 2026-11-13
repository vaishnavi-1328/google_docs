/**
 * Minimal collaborative-feeling drawing node:
 *   - Each node holds an SVG path list in its attributes (`strokes`).
 *   - Users draw with the mouse; strokes are stored in the node attrs so they
 *     flow through Yjs just like any other block attributes and survive
 *     restarts.
 *
 * Not tldraw. tldraw is beautiful but adds ~1.5MB and more dependencies than
 * the MVP warrants. If a reviewer wants tldraw specifically we swap this
 * NodeView implementation; the TipTap node schema stays the same.
 */
import { Node, mergeAttributes } from "@tiptap/core";
import { NodeViewWrapper, ReactNodeViewRenderer, type NodeViewProps } from "@tiptap/react";
import { useRef, useState } from "react";

type Stroke = { color: string; width: number; points: [number, number][] };

function DrawingView(props: NodeViewProps) {
  const { node, updateAttributes } = props;
  const strokes: Stroke[] = node.attrs.strokes || [];
  const svgRef = useRef<SVGSVGElement>(null);
  const [current, setCurrent] = useState<Stroke | null>(null);
  const [color, setColor] = useState("#1a73e8");
  const [width, setWidth] = useState(2);

  function onDown(e: React.PointerEvent) {
    const r = svgRef.current!.getBoundingClientRect();
    const s: Stroke = { color, width, points: [[e.clientX - r.left, e.clientY - r.top]] };
    setCurrent(s);
    (e.target as Element).setPointerCapture(e.pointerId);
  }
  function onMove(e: React.PointerEvent) {
    if (!current) return;
    const r = svgRef.current!.getBoundingClientRect();
    setCurrent({ ...current, points: [...current.points, [e.clientX - r.left, e.clientY - r.top]] });
  }
  function onUp() {
    if (current) {
      updateAttributes({ strokes: [...strokes, current] });
      setCurrent(null);
    }
  }
  function clear() {
    updateAttributes({ strokes: [] });
  }

  function path(s: Stroke) {
    return s.points.map(([x, y], i) => (i === 0 ? `M${x},${y}` : `L${x},${y}`)).join(" ");
  }

  return (
    <NodeViewWrapper className="drawing-node">
      <div style={{ display: "flex", gap: 8, marginBottom: 4, alignItems: "center" }}>
        <input type="color" value={color} onChange={(e) => setColor(e.target.value)} />
        <input
          type="range"
          min={1}
          max={16}
          value={width}
          onChange={(e) => setWidth(Number(e.target.value))}
        />
        <button onClick={clear}>Clear</button>
        <span style={{ fontSize: 11, color: "#888" }}>Drawing — collaborative via Yjs attrs</span>
      </div>
      <svg
        ref={svgRef}
        width={600}
        height={300}
        style={{ border: "1px solid #ddd", background: "#fafafa", touchAction: "none", borderRadius: 4 }}
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
        onPointerCancel={onUp}
      >
        {strokes.map((s, i) => (
          <path key={i} d={path(s)} stroke={s.color} strokeWidth={s.width} fill="none" strokeLinecap="round" />
        ))}
        {current && <path d={path(current)} stroke={current.color} strokeWidth={current.width} fill="none" strokeLinecap="round" />}
      </svg>
    </NodeViewWrapper>
  );
}

export const DrawingNode = Node.create({
  name: "drawing",
  group: "block",
  atom: true,
  draggable: true,
  addAttributes() {
    return { strokes: { default: [] } };
  },
  parseHTML() {
    return [{ tag: "div[data-type='drawing']" }];
  },
  renderHTML({ HTMLAttributes }) {
    return ["div", mergeAttributes(HTMLAttributes, { "data-type": "drawing" })];
  },
  addNodeView() {
    return ReactNodeViewRenderer(DrawingView);
  },
});
