import { useState } from "react";
import { api, type Me } from "./api";

export function AuthPage({ onAuth }: { onAuth: (me: Me) => void }) {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [tenantName, setTenantName] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const me =
        mode === "login"
          ? await api.login({ email, password })
          : await api.signup({ email, password, display_name: displayName, tenant_name: tenantName });
      onAuth(me);
    } catch (e: unknown) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", maxWidth: 420, margin: "4rem auto" }}>
      <h1>Collab Docs</h1>
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <button onClick={() => setMode("login")} disabled={mode === "login"}>
          Log in
        </button>
        <button onClick={() => setMode("signup")} disabled={mode === "signup"}>
          Sign up
        </button>
      </div>
      <form onSubmit={submit} style={{ display: "grid", gap: 8 }}>
        <input placeholder="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <input
          placeholder="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        {mode === "signup" && (
          <>
            <input
              placeholder="your name"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              required
            />
            <input
              placeholder="workspace name"
              value={tenantName}
              onChange={(e) => setTenantName(e.target.value)}
              required
            />
          </>
        )}
        <button type="submit" disabled={busy}>
          {busy ? "…" : mode === "login" ? "Log in" : "Create account"}
        </button>
        {err && <div style={{ color: "crimson" }}>{err}</div>}
      </form>
    </main>
  );
}
