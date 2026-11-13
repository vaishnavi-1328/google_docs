export const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";
export const WS_BASE = import.meta.env.VITE_WS_BASE ?? "ws://localhost:8000";

async function j<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  if (r.status === 204) return undefined as T;
  return r.json();
}

const h = { "content-type": "application/json" };
const opts: RequestInit = { credentials: "include" };

export type Me = { id: string; email: string; display_name: string; tenant_id: string };
export type Doc = {
  id: string;
  title: string;
  owner_id: string;
  created_at: string;
  updated_at: string;
};

export const api = {
  me: () => fetch(`${API_BASE}/auth/me`, opts).then(j<Me>),
  signup: (body: {
    email: string;
    password: string;
    display_name: string;
    tenant_name: string;
  }) =>
    fetch(`${API_BASE}/auth/signup`, { ...opts, method: "POST", headers: h, body: JSON.stringify(body) }).then(
      j<Me>,
    ),
  login: (body: { email: string; password: string }) =>
    fetch(`${API_BASE}/auth/login`, { ...opts, method: "POST", headers: h, body: JSON.stringify(body) }).then(
      j<Me>,
    ),
  logout: () => fetch(`${API_BASE}/auth/logout`, { ...opts, method: "POST" }).then(j<void>),

  docsList: () => fetch(`${API_BASE}/docs`, opts).then(j<Doc[]>),
  docsCreate: (title: string) =>
    fetch(`${API_BASE}/docs`, { ...opts, method: "POST", headers: h, body: JSON.stringify({ title }) }).then(
      j<Doc>,
    ),
  docsGet: (id: string) => fetch(`${API_BASE}/docs/${id}`, opts).then(j<Doc>),
  docsRename: (id: string, title: string) =>
    fetch(`${API_BASE}/docs/${id}`, {
      ...opts,
      method: "PATCH",
      headers: h,
      body: JSON.stringify({ title }),
    }).then(j<Doc>),
  docsDelete: (id: string) =>
    fetch(`${API_BASE}/docs/${id}`, { ...opts, method: "DELETE" }).then(j<void>),

  acl: (id: string) =>
    fetch(`${API_BASE}/docs/${id}/acl`, opts).then(j<AclResponse>),
  invite: (id: string, body: { email: string; role: Role }) =>
    fetch(`${API_BASE}/docs/${id}/invite`, {
      ...opts,
      method: "POST",
      headers: h,
      body: JSON.stringify(body),
    }).then(j<AclEntry>),
  revokeInvite: (id: string, userId: string) =>
    fetch(`${API_BASE}/docs/${id}/invite/${userId}`, { ...opts, method: "DELETE" }).then(j<void>),
  createLink: (id: string, role: Role) =>
    fetch(`${API_BASE}/docs/${id}/share-link`, {
      ...opts,
      method: "POST",
      headers: h,
      body: JSON.stringify({ role }),
    }).then(j<ShareLink>),
  revokeLink: (id: string, linkId: string) =>
    fetch(`${API_BASE}/docs/${id}/share-link/${linkId}`, { ...opts, method: "DELETE" }).then(
      j<void>,
    ),

  snapshotCreate: (id: string, label?: string) =>
    fetch(`${API_BASE}/docs/${id}/snapshots`, {
      ...opts,
      method: "POST",
      headers: h,
      body: JSON.stringify({ label: label ?? null }),
    }).then(j<SnapshotMeta>),
  snapshotList: (id: string) =>
    fetch(`${API_BASE}/docs/${id}/snapshots`, opts).then(j<SnapshotMeta[]>),
  snapshotBlob: (id: string, sid: string) =>
    fetch(`${API_BASE}/docs/${id}/snapshots/${sid}`, opts).then((r) => {
      if (!r.ok) throw new Error(`${r.status}`);
      return r.arrayBuffer();
    }),
  snapshotRestore: (id: string, sid: string) =>
    fetch(`${API_BASE}/docs/${id}/snapshots/${sid}:restore`, { ...opts, method: "POST" }).then(
      j<{ ok: string }>,
    ),
};

export type SnapshotMeta = { id: string; label: string | null; created_at: string };

export type Role = "viewer" | "commenter" | "editor";
export type AclEntry = { user_id: string; email: string; role: Role };
export type ShareLink = { id: string; role: Role; revoked_at: string | null };
export type AclResponse = {
  role_me: Role | "owner" | null;
  owner_id: string;
  entries: AclEntry[];
  links: ShareLink[];
};
