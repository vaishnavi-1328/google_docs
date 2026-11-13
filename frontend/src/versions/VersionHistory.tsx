import { useEffect, useState } from "react";
import * as Y from "yjs";
import { api, type SnapshotMeta } from "../api";

/** Renders a snapshot into plain preview text by applying the Yjs update
 * into a throwaway Y.Doc and reading its default text fragment. For TipTap
 * docs the "prosemirror" XmlFragment is the content root; we just read its
 * string form for the preview. */
function previewFromUpdate(update: Uint8Array): string {
  try {
    const d = new Y.Doc();
    Y.applyUpdate(d, update);
    const frag = d.getXmlFragment("prosemirror");
    const s = frag.toString();
    // Strip tags so the preview reads like text, not markup.
    return s.replace(/<[^>]+>/g, "").slice(0, 800);
  } catch {
    return "(unreadable snapshot)";
  }
}

export function VersionHistory({
  docId,
  onClose,
  onAfterRestore,
}: {
  docId: string;
  onClose: () => void;
  onAfterRestore: () => void;
}) {
  const [snaps, setSnaps] = useState<SnapshotMeta[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [preview, setPreview] = useState<string>("");
  const [err, setErr] = useState<string | null>(null);

  async function refresh() {
    try {
      const list = await api.snapshotList(docId);
      setSnaps(list);
      if (!selected && list[0]) setSelected(list[0].id);
    } catch (e) {
      setErr((e as Error).message);
    }
  }
  useEffect(() => {
    refresh();
  }, [docId]);

  useEffect(() => {
    if (!selected) return;
    (async () => {
      try {
        const buf = await api.snapshotBlob(docId, selected);
        setPreview(previewFromUpdate(new Uint8Array(buf)));
      } catch (e) {
        setPreview("(error loading preview)");
      }
    })();
  }, [docId, selected]);

  async function takeNow() {
    const label = prompt("Label (optional)") || undefined;
    await api.snapshotCreate(docId, label);
    refresh();
  }

  async function restore() {
    if (!selected) return;
    if (!confirm("Restore this version? Current state will be overwritten on the next reconnect.")) return;
    await api.snapshotRestore(docId, selected);
    onAfterRestore();
    onClose();
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" style={{ width: 800 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2>Version history</h2>
          <div>
            <button onClick={takeNow}>Snapshot now</button>{" "}
            <button onClick={onClose}>Close</button>
          </div>
        </div>
        {err && <div style={{ color: "crimson" }}>{err}</div>}
        <div style={{ display: "flex", gap: 12 }}>
          <ul
            style={{
              listStyle: "none",
              padding: 0,
              margin: 0,
              width: 240,
              maxHeight: "60vh",
              overflow: "auto",
              borderRight: "1px solid #eee",
            }}
          >
            {snaps?.length === 0 && <li style={{ color: "#888", padding: 8 }}>No snapshots yet.</li>}
            {snaps?.map((s) => (
              <li key={s.id}>
                <button
                  onClick={() => setSelected(s.id)}
                  style={{
                    display: "block",
                    width: "100%",
                    textAlign: "left",
                    padding: 8,
                    background: selected === s.id ? "#e8f0fe" : "none",
                    border: 0,
                    cursor: "pointer",
                  }}
                >
                  <div style={{ fontWeight: 600 }}>
                    {s.label || "Autosave"}
                  </div>
                  <div style={{ fontSize: 12, color: "#888" }}>
                    {new Date(s.created_at).toLocaleString()}
                  </div>
                </button>
              </li>
            ))}
          </ul>
          <div style={{ flex: 1, maxHeight: "60vh", overflow: "auto" }}>
            <pre
              style={{
                whiteSpace: "pre-wrap",
                fontFamily: "Georgia, serif",
                fontSize: 14,
                lineHeight: 1.5,
                background: "#fafafa",
                padding: 16,
                borderRadius: 4,
                minHeight: 200,
              }}
            >
              {preview || "(empty)"}
            </pre>
            <div style={{ marginTop: 8 }}>
              <button onClick={restore} disabled={!selected}>Restore this version</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
