import { useEffect, useRef, useState } from "react";
import type { Editor } from "@tiptap/react";

/** A single submenu entry. `onClick === null` renders as disabled (future stage). */
export type MenuItem = {
  label: string;
  shortcut?: string;
  onClick: (() => void) | null;
  divider?: boolean;
};

export type MenuDef = { label: string; items: MenuItem[] };

export function Toolbar({
  editor,
  docTitle,
  onRenameDoc,
  onBackToList,
  onNewDoc,
  onDownload,
  onShare,
  onVersionHistory,
  onInsertImage,
  onInsertDrawing,
  onInsertFlowchart,
  onInsertEquation,
  onOpenCalculator,
  onOpenFindReplace,
  zoom,
  onZoom,
}: {
  editor: Editor | null;
  docTitle: string;
  onRenameDoc: (t: string) => void;
  onBackToList: () => void;
  onNewDoc: () => void;
  onDownload: ((fmt: "pdf" | "md" | "txt" | "docx" | "epub") => void) | null;
  onShare: (() => void) | null;
  onVersionHistory: (() => void) | null;
  onInsertImage: (() => void) | null;
  onInsertDrawing: (() => void) | null;
  onInsertFlowchart: (() => void) | null;
  onInsertEquation: (() => void) | null;
  onOpenCalculator: (() => void) | null;
  onOpenFindReplace: (() => void) | null;
  zoom: number;
  onZoom: (next: number) => void;
}) {
  const [open, setOpen] = useState<string | null>(null);

  const menus: MenuDef[] = [
    {
      label: "File",
      items: [
        { label: "New", shortcut: "Ctrl+N", onClick: onNewDoc },
        { label: "Open", onClick: onBackToList },
        { label: "Make a copy", onClick: null, divider: true },
        { label: "Share…", onClick: onShare },
        {
          label: "Download",
          onClick: null,
          // Nested download options are rendered inline below via sub-toolbar for now.
        },
        {
          label: "  as PDF (.pdf)",
          onClick: onDownload ? () => onDownload("pdf") : null,
        },
        {
          label: "  as Markdown (.md)",
          onClick: onDownload ? () => onDownload("md") : null,
        },
        {
          label: "  as Plain text (.txt)",
          onClick: onDownload ? () => onDownload("txt") : null,
        },
        {
          label: "  as Word (.docx)",
          onClick: onDownload ? () => onDownload("docx") : null,
        },
        {
          label: "  as EPUB (.epub)",
          onClick: onDownload ? () => onDownload("epub") : null,
          divider: true,
        },
        { label: "Version history", onClick: onVersionHistory },
        { label: "Rename", onClick: () => {
            const t = prompt("Rename document", docTitle);
            if (t && t.trim()) onRenameDoc(t.trim());
          },
          divider: true,
        },
        { label: "Print", shortcut: "Ctrl+P", onClick: () => window.print() },
      ],
    },
    {
      label: "Edit",
      items: [
        { label: "Undo", shortcut: "Ctrl+Z", onClick: editor ? () => editor.chain().focus().undo().run() : null },
        { label: "Redo", shortcut: "Ctrl+Y", onClick: editor ? () => editor.chain().focus().redo().run() : null, divider: true },
        { label: "Cut", shortcut: "Ctrl+X", onClick: () => document.execCommand("cut") },
        { label: "Copy", shortcut: "Ctrl+C", onClick: () => document.execCommand("copy") },
        { label: "Paste", shortcut: "Ctrl+V", onClick: () => document.execCommand("paste"), divider: true },
        { label: "Select all", shortcut: "Ctrl+A", onClick: editor ? () => editor.chain().focus().selectAll().run() : null },
        { label: "Find and replace", shortcut: "Ctrl+H", onClick: onOpenFindReplace },
      ],
    },
    {
      label: "View",
      items: [
        { label: "Show ruler", onClick: null },
        { label: "Show outline", onClick: null },
        { label: "Full screen", onClick: () => document.documentElement.requestFullscreen?.(), divider: true },
        { label: "Zoom in", onClick: () => onZoom(Math.min(2, zoom + 0.1)) },
        { label: "Zoom out", onClick: () => onZoom(Math.max(0.5, zoom - 0.1)) },
        { label: `Reset zoom (${Math.round(zoom * 100)}%)`, onClick: () => onZoom(1) },
      ],
    },
    {
      label: "Insert",
      items: [
        { label: "Image", onClick: onInsertImage },
        { label: "Drawing", onClick: onInsertDrawing },
        { label: "Flowchart (Mermaid)", onClick: onInsertFlowchart, divider: true },
        { label: "Table", onClick: editor ? () => (editor.chain().focus() as unknown as { insertTable: (o: { rows: number; cols: number; withHeaderRow: boolean }) => { run: () => void } }).insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run() : null },
        { label: "Link", shortcut: "Ctrl+K", onClick: editor ? () => {
            const url = prompt("URL");
            if (url) (editor.chain().focus() as unknown as { setLink: (a: { href: string }) => { run: () => void } }).setLink({ href: url }).run();
          } : null },
        { label: "Equation (KaTeX)", onClick: onInsertEquation, divider: true },
        { label: "Horizontal line", onClick: editor ? () => editor.chain().focus().setHorizontalRule().run() : null },
      ],
    },
    {
      label: "Format",
      items: [
        { label: "Bold", shortcut: "Ctrl+B", onClick: editor ? () => editor.chain().focus().toggleBold().run() : null },
        { label: "Italic", shortcut: "Ctrl+I", onClick: editor ? () => editor.chain().focus().toggleItalic().run() : null },
        { label: "Underline", shortcut: "Ctrl+U", onClick: editor ? () => (editor.chain().focus() as unknown as { toggleUnderline: () => { run: () => void } }).toggleUnderline().run() : null },
        { label: "Strikethrough", onClick: editor ? () => editor.chain().focus().toggleStrike().run() : null, divider: true },
        { label: "Heading 1", onClick: editor ? () => editor.chain().focus().toggleHeading({ level: 1 }).run() : null },
        { label: "Heading 2", onClick: editor ? () => editor.chain().focus().toggleHeading({ level: 2 }).run() : null },
        { label: "Heading 3", onClick: editor ? () => editor.chain().focus().toggleHeading({ level: 3 }).run() : null, divider: true },
        { label: "Bullet list", onClick: editor ? () => editor.chain().focus().toggleBulletList().run() : null },
        { label: "Numbered list", onClick: editor ? () => editor.chain().focus().toggleOrderedList().run() : null },
        { label: "Blockquote", onClick: editor ? () => editor.chain().focus().toggleBlockquote().run() : null, divider: true },
        { label: "Clear formatting", onClick: editor ? () => editor.chain().focus().clearNodes().unsetAllMarks().run() : null },
      ],
    },
    {
      label: "Tools",
      items: [
        { label: "Word count", onClick: () => {
            const text = editor?.getText() ?? "";
            const words = text.trim().split(/\s+/).filter(Boolean).length;
            alert(`${words} words, ${text.length} characters`);
          } },
        { label: "Scientific calculator", onClick: onOpenCalculator },
        { label: "Spelling", onClick: null },
      ],
    },
    {
      label: "Extension",
      items: [{ label: "Add-ons (coming soon)", onClick: null }],
    },
    {
      label: "Help",
      items: [
        { label: "Keyboard shortcuts", onClick: () => alert(KEYS_HELP) },
        { label: "About Collab Docs", onClick: () => alert("Collab Docs — MVP") },
      ],
    },
  ];

  const containerRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(null);
    }
    document.addEventListener("click", onDocClick);
    return () => document.removeEventListener("click", onDocClick);
  }, []);

  return (
    <div ref={containerRef} className="menubar">
      <div className="menubar-title">
        <button onClick={onBackToList} title="Back to documents" style={{ marginRight: 8 }}>←</button>
        <input
          value={docTitle}
          onChange={(e) => onRenameDoc(e.target.value)}
          className="doc-title-input"
        />
      </div>
      <div className="menubar-menus">
        {menus.map((m) => (
          <div key={m.label} className="menu">
            <button
              className={`menu-trigger ${open === m.label ? "open" : ""}`}
              onClick={(e) => {
                e.stopPropagation();
                setOpen(open === m.label ? null : m.label);
              }}
            >
              {m.label}
            </button>
            {open === m.label && (
              <div className="menu-dropdown">
                {m.items.map((it, i) => (
                  <div key={i}>
                    <button
                      className="menu-item"
                      disabled={it.onClick === null}
                      onClick={() => {
                        it.onClick?.();
                        setOpen(null);
                      }}
                    >
                      <span>{it.label}</span>
                      {it.shortcut && <span className="shortcut">{it.shortcut}</span>}
                    </button>
                    {it.divider && <div className="divider" />}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
      <QuickFormatBar editor={editor} />
    </div>
  );
}

function QuickFormatBar({ editor }: { editor: Editor | null }) {
  if (!editor) return null;
  const btn = (label: string, active: boolean, onClick: () => void) => (
    <button className={`qbtn ${active ? "active" : ""}`} onClick={onClick}>
      {label}
    </button>
  );
  return (
    <div className="qbar">
      {btn("B", editor.isActive("bold"), () => editor.chain().focus().toggleBold().run())}
      {btn("I", editor.isActive("italic"), () => editor.chain().focus().toggleItalic().run())}
      {btn("S", editor.isActive("strike"), () => editor.chain().focus().toggleStrike().run())}
      <span className="sep" />
      {btn("H1", editor.isActive("heading", { level: 1 }), () => editor.chain().focus().toggleHeading({ level: 1 }).run())}
      {btn("H2", editor.isActive("heading", { level: 2 }), () => editor.chain().focus().toggleHeading({ level: 2 }).run())}
      <span className="sep" />
      {btn("• List", editor.isActive("bulletList"), () => editor.chain().focus().toggleBulletList().run())}
      {btn("1. List", editor.isActive("orderedList"), () => editor.chain().focus().toggleOrderedList().run())}
      {btn("“ Quote", editor.isActive("blockquote"), () => editor.chain().focus().toggleBlockquote().run())}
    </div>
  );
}

const KEYS_HELP = `Ctrl+B — Bold
Ctrl+I — Italic
Ctrl+Z / Ctrl+Y — Undo / Redo
Ctrl+A — Select all
Ctrl+K — Insert link
Ctrl+P — Print
`;
