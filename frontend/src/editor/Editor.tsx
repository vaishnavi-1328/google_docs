import { useEffect, useMemo, useRef, useState } from "react";
import { Editor as TiptapEditor } from "@tiptap/core";
import { EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import { Collaboration } from "@tiptap/extension-collaboration";
import { Image } from "@tiptap/extension-image";
import { Table } from "@tiptap/extension-table";
import { TableRow } from "@tiptap/extension-table-row";
import { TableCell } from "@tiptap/extension-table-cell";
import { TableHeader } from "@tiptap/extension-table-header";
import { FindReplace } from "./FindReplace";
import { MermaidNode } from "./nodes/MermaidNode";
import { EquationNode } from "./nodes/EquationNode";
import { DrawingNode } from "./nodes/DrawingNode";
import * as Y from "yjs";
import { IndexeddbPersistence } from "y-indexeddb";
import { WebsocketProvider } from "y-websocket";
import { api, WS_BASE, type Doc, type Me } from "../api";
import { ShareDialog } from "../sharing/ShareDialog";
import { Calculator } from "../tools/Calculator";
import { VersionHistory } from "../versions/VersionHistory";
import { Toolbar } from "./Toolbar";
import "./editor.css";

const USER_COLORS = ["#1a73e8", "#e8710a", "#188038", "#d93025", "#9334e6", "#007b83"];

function colorFor(id: string): string {
  let h = 0;
  for (const ch of id) h = (h * 31 + ch.charCodeAt(0)) | 0;
  return USER_COLORS[Math.abs(h) % USER_COLORS.length];
}

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export function Editor({ me, docId, onBack }: { me: Me; docId: string; onBack: () => void }) {
  const [doc, setDoc] = useState<Doc | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [showShare, setShowShare] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showCalc, setShowCalc] = useState(false);
  const [showFind, setShowFind] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [wsStatus, setWsStatus] = useState<"connecting" | "connected" | "disconnected">("connecting");
  const [editorReady, setEditorReady] = useState(false);

  const editorRef = useRef<TiptapEditor | null>(null);

  // Room name is tenant-scoped so IndexedDB stores never bleed across workspaces.
  const roomName = useMemo(() => `t:${me.tenant_id}:d:${docId}`, [me.tenant_id, docId]);

  useEffect(() => {
    // Y.Doc, IndexedDB persistence, WebSocket provider, and TipTap editor are
    // all created in one effect so they share a single lifecycle — no window
    // where the Y.Doc is destroyed while the editor still holds an XmlFragment.
    const ydoc = new Y.Doc();

    let idb: IndexeddbPersistence | null = null;
    try {
      idb = new IndexeddbPersistence(roomName, ydoc);
    } catch {
      // IndexedDB can be unavailable in Incognito or locked browser contexts.
      // The editor still works online; server persistence is the source of truth.
    }

    const wsProvider = new WebsocketProvider(`${WS_BASE}/ws/docs`, docId, ydoc, { connect: true });
    wsProvider.on("status", ({ status }: { status: string }) => {
      setWsStatus(status === "connected" ? "connected" : status === "connecting" ? "connecting" : "disconnected");
    });
    wsProvider.awareness.setLocalStateField("user", {
      name: me.display_name || me.email,
      color: colorFor(me.id),
    });

    const instance = new TiptapEditor({
      extensions: [
        StarterKit.configure({ undoRedo: false }),
        Placeholder.configure({ placeholder: "Start typing…" }),
        Image,
        Table.configure({ resizable: true }),
        TableRow,
        TableHeader,
        TableCell,
        MermaidNode,
        EquationNode,
        DrawingNode,
        Collaboration.configure({ document: ydoc }),
      ],
      editorProps: { attributes: { class: "tiptap-editor" } },
    });

    editorRef.current = instance;
    setEditorReady(true);

    return () => {
      editorRef.current = null;
      setEditorReady(false);
      instance.destroy();
      wsProvider.destroy();
      idb?.destroy();
      ydoc.destroy();
    };
  }, [roomName, docId, me.display_name, me.email, me.id]);

  useEffect(() => {
    api.docsGet(docId)
      .then(setDoc)
      .catch((e) => setErr((e as Error).message));
  }, [docId]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && (e.key === "f" || e.key === "h")) {
        e.preventDefault();
        setShowFind(true);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  async function rename(title: string) {
    setDoc((d) => (d ? { ...d, title } : d));
    try {
      await api.docsRename(docId, title);
    } catch (e) {
      setErr((e as Error).message);
    }
  }

  async function download(fmt: "pdf" | "md" | "txt" | "docx" | "epub") {
    const editor = editorRef.current;
    if (!editor || !doc) return;
    try {
      const r = await fetch(`${API_BASE}/docs/${docId}/export?format=${fmt}`, {
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ html: editor.getHTML() }),
      });
      if (!r.ok) { setErr(`Export failed: ${r.status}`); return; }
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const m = /filename="([^"]+)"/.exec(r.headers.get("content-disposition") || "");
      a.download = m ? m[1] : `${doc.title}.${fmt}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setErr((e as Error).message);
    }
  }

  async function insertImage() {
    const editor = editorRef.current;
    if (!editor) return;
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/*";
    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file) return;
      const fd = new FormData();
      fd.append("file", file);
      try {
        const r = await fetch(`${API_BASE}/docs/${docId}/attachments`, {
          method: "POST",
          credentials: "include",
          body: fd,
        });
        if (!r.ok) { setErr(`Upload failed: ${r.status}`); return; }
        const data = await r.json();
        editor.chain().focus().setImage({ src: `${API_BASE}${data.url}` }).run();
      } catch (e) {
        setErr((e as Error).message);
      }
    };
    input.click();
  }

  function insertMermaid() {
    editorRef.current?.chain().focus().insertContent({ type: "mermaid", attrs: { src: "graph TD;\n  A-->B;" } }).run();
  }

  function insertDrawing() {
    editorRef.current?.chain().focus().insertContent({ type: "drawing", attrs: { strokes: [] } }).run();
  }

  function insertEquation() {
    editorRef.current?.chain().focus().insertContent({ type: "equation", attrs: { src: "E = mc^2" } }).run();
  }

  async function newDoc() {
    const d = await api.docsCreate("Untitled document");
    location.hash = `#/doc/${d.id}`;
  }

  if (err) return <div style={{ padding: 16, color: "crimson" }}>Error: {err}</div>;
  if (!doc || !editorReady) return <div style={{ padding: 16 }}>Loading…</div>;

  return (
    <div className="editor-shell">
      <Toolbar
        editor={editorRef.current}
        docTitle={doc.title}
        onRenameDoc={rename}
        onBackToList={onBack}
        onNewDoc={newDoc}
        onDownload={download}
        onShare={() => setShowShare(true)}
        onVersionHistory={() => setShowHistory(true)}
        onInsertImage={insertImage}
        onInsertDrawing={insertDrawing}
        onInsertFlowchart={insertMermaid}
        onInsertEquation={insertEquation}
        onOpenCalculator={() => setShowCalc(true)}
        onOpenFindReplace={() => setShowFind(true)}
        zoom={zoom}
        onZoom={setZoom}
      />
      <div className="editor-page" style={{ transform: `scale(${zoom})`, transformOrigin: "top center" }}>
        <EditorContent editor={editorRef.current} />
      </div>
      {showFind && editorRef.current && (
        <FindReplace editor={editorRef.current} onClose={() => setShowFind(false)} />
      )}
      {showShare && <ShareDialog docId={docId} onClose={() => setShowShare(false)} />}
      {showCalc && <Calculator onClose={() => setShowCalc(false)} />}
      {showHistory && (
        <VersionHistory
          docId={docId}
          onClose={() => setShowHistory(false)}
          onAfterRestore={() => location.reload()}
        />
      )}
      <div className="editor-status">
        {wsStatus === "connected"
          ? "Saved to cloud · live"
          : wsStatus === "connecting"
            ? "Connecting…"
            : "Offline · changes saved locally"}
        {" · "}
        {me.email}
      </div>
    </div>
  );
}
