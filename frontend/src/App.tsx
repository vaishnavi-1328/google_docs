import { useEffect, useState } from "react";
import { AuthPage } from "./AuthPage";
import { DocsList } from "./DocsList";
import { Editor } from "./editor/Editor";
import { api, type Me } from "./api";

type Route = { kind: "list" } | { kind: "doc"; id: string };

function parseHash(): Route {
  const m = location.hash.match(/^#\/doc\/([0-9a-f-]+)/i);
  if (m) return { kind: "doc", id: m[1] };
  return { kind: "list" };
}

export function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [route, setRoute] = useState<Route>(parseHash());

  useEffect(() => {
    api.me()
      .then(setMe)
      .catch(() => setMe(null))
      .finally(() => setLoading(false));
    const h = () => setRoute(parseHash());
    window.addEventListener("hashchange", h);
    return () => window.removeEventListener("hashchange", h);
  }, []);

  if (loading) return <div style={{ padding: 32 }}>Loading…</div>;
  if (!me) return <AuthPage onAuth={setMe} />;

  if (route.kind === "doc") {
    return (
      <Editor
        me={me}
        docId={route.id}
        onBack={() => {
          location.hash = "#/";
        }}
      />
    );
  }
  return (
    <DocsList
      me={me}
      onOpen={(id) => {
        location.hash = `#/doc/${id}`;
      }}
      onLogout={() => setMe(null)}
    />
  );
}
