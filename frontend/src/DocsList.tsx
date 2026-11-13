import { useEffect, useState } from "react";
import { api, type Doc, type Me } from "./api";

export function DocsList({ me, onOpen, onLogout }: { me: Me; onOpen: (id: string) => void; onLogout: () => void }) {
  const [docs, setDocs] = useState<Doc[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function refresh() {
    try {
      setDocs(await api.docsList());
    } catch (e) {
      setErr((e as Error).message);
    }
  }
  useEffect(() => {
    refresh();
  }, []);

  async function createDoc() {
    const d = await api.docsCreate("Untitled document");
    onOpen(d.id);
  }

  async function del(id: string) {
    if (!confirm("Delete this document?")) return;
    await api.docsDelete(id);
    refresh();
  }

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", maxWidth: 900, margin: "2rem auto" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>Your documents</h1>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span style={{ color: "#555" }}>{me.email}</span>
          <button onClick={async () => { await api.logout(); onLogout(); }}>Log out</button>
        </div>
      </header>
      <button onClick={createDoc} style={{ margin: "1rem 0" }}>+ New document</button>
      {err && <div style={{ color: "crimson" }}>{err}</div>}
      {docs === null ? (
        <div>Loading…</div>
      ) : docs.length === 0 ? (
        <div>No documents yet.</div>
      ) : (
        <ul style={{ listStyle: "none", padding: 0 }}>
          {docs.map((d) => (
            <li
              key={d.id}
              style={{
                display: "flex",
                justifyContent: "space-between",
                padding: "0.5rem 0",
                borderBottom: "1px solid #eee",
              }}
            >
              <button
                onClick={() => onOpen(d.id)}
                style={{ background: "none", border: 0, cursor: "pointer", textAlign: "left", flex: 1 }}
              >
                <strong>{d.title}</strong>{" "}
                <span style={{ color: "#888", fontSize: 12 }}>
                  updated {new Date(d.updated_at).toLocaleString()}
                </span>
              </button>
              <button onClick={() => del(d.id)}>Delete</button>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
