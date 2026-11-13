import { useEffect, useState } from "react";
import { api, type AclResponse, type Role } from "../api";

export function ShareDialog({ docId, onClose }: { docId: string; onClose: () => void }) {
  const [acl, setAcl] = useState<AclResponse | null>(null);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("editor");
  const [linkRole, setLinkRole] = useState<Role>("viewer");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      setAcl(await api.acl(docId));
    } catch (e) {
      setErr((e as Error).message);
    }
  }
  useEffect(() => {
    refresh();
  }, [docId]);

  async function invite(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await api.invite(docId, { email, role });
      setEmail("");
      await refresh();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function createLink() {
    try {
      await api.createLink(docId, linkRole);
      await refresh();
    } catch (e) {
      setErr((e as Error).message);
    }
  }

  function linkUrl(linkId: string) {
    return `${location.origin}/#/doc/${docId}?link=${linkId}`;
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2>Share</h2>
          <button onClick={onClose}>Close</button>
        </div>
        {err && <div style={{ color: "crimson" }}>{err}</div>}

        <h3>People with access</h3>
        <ul style={{ listStyle: "none", padding: 0 }}>
          {acl?.entries.map((e) => (
            <li
              key={e.user_id}
              style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}
            >
              <span>
                {e.email} <em style={{ color: "#888" }}>({e.role})</em>
              </span>
              <button
                onClick={async () => {
                  await api.revokeInvite(docId, e.user_id);
                  refresh();
                }}
              >
                Remove
              </button>
            </li>
          ))}
          {acl && acl.entries.length === 0 && <li style={{ color: "#888" }}>No one besides the owner.</li>}
        </ul>

        <h3>Invite</h3>
        <form onSubmit={invite} style={{ display: "flex", gap: 8 }}>
          <input
            placeholder="email"
            value={email}
            onChange={(ev) => setEmail(ev.target.value)}
            required
            style={{ flex: 1 }}
          />
          <select value={role} onChange={(ev) => setRole(ev.target.value as Role)}>
            <option value="viewer">Viewer</option>
            <option value="commenter">Commenter</option>
            <option value="editor">Editor</option>
          </select>
          <button type="submit" disabled={busy}>Invite</button>
        </form>

        <h3>Link sharing</h3>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <select value={linkRole} onChange={(ev) => setLinkRole(ev.target.value as Role)}>
            <option value="viewer">Anyone with link — Viewer</option>
            <option value="commenter">Anyone with link — Commenter</option>
            <option value="editor">Anyone with link — Editor</option>
          </select>
          <button onClick={createLink}>Create link</button>
        </div>
        <ul style={{ listStyle: "none", padding: 0, marginTop: 8 }}>
          {acl?.links
            .filter((l) => !l.revoked_at)
            .map((l) => (
              <li
                key={l.id}
                style={{ display: "flex", gap: 8, alignItems: "center", padding: "4px 0" }}
              >
                <code style={{ flex: 1, fontSize: 12 }}>{linkUrl(l.id)}</code>
                <button
                  onClick={() => navigator.clipboard.writeText(linkUrl(l.id))}
                  title="Copy"
                >
                  Copy
                </button>
                <span style={{ color: "#888" }}>({l.role})</span>
                <button
                  onClick={async () => {
                    await api.revokeLink(docId, l.id);
                    refresh();
                  }}
                >
                  Revoke
                </button>
              </li>
            ))}
        </ul>
      </div>
    </div>
  );
}
