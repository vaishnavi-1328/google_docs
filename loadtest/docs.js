// k6 load test: N virtual users sign up, create a doc, then rapidly list + GET.
// Usage: k6 run --vus 50 --duration 30s loadtest/docs.js
import http from "k6/http";
import { check, sleep } from "k6";

const BASE = __ENV.BASE || "http://localhost:8000";

export default function () {
  const email = `k6-${Math.random().toString(36).slice(2, 10)}@x.test`;
  const jar = http.cookieJar();
  const r = http.post(
    `${BASE}/auth/signup`,
    JSON.stringify({
      email,
      password: "correct horse battery staple",
      display_name: "k6",
      tenant_name: `k6-${Math.random().toString(36).slice(2, 8)}`,
    }),
    { headers: { "content-type": "application/json" }, jar },
  );
  check(r, { "signup ok": (res) => res.status === 201 });

  const c = http.post(
    `${BASE}/docs`,
    JSON.stringify({ title: "Load" }),
    { headers: { "content-type": "application/json" }, jar },
  );
  check(c, { "create ok": (res) => res.status === 201 });
  const id = c.json("id");

  for (let i = 0; i < 20; i++) {
    const g = http.get(`${BASE}/docs/${id}`, { jar });
    check(g, { "get ok": (res) => res.status === 200 });
    const l = http.get(`${BASE}/docs`, { jar });
    check(l, { "list ok": (res) => res.status === 200 });
    sleep(0.05);
  }
}
