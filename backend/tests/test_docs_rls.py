"""Cross-tenant tests for the /docs HTTP layer.

Proves that a document created in tenant A is invisible to tenant B via the
REST API. If this ever starts failing, RLS or the tenant_session dependency
regressed.
"""
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _signup(c: TestClient):
    email = f"u-{uuid4()}@x.test"
    r = c.post(
        "/auth/signup",
        json={
            "email": email,
            "password": "supersecret!!",
            "display_name": "T",
            "tenant_name": f"T-{uuid4().hex[:6]}",
        },
    )
    assert r.status_code == 201, r.text
    return email


def test_cross_tenant_doc_isolation():
    a = TestClient(app)
    b = TestClient(app)
    _signup(a)
    _signup(b)

    # A creates a doc.
    r = a.post("/docs", json={"title": "A's secret"})
    assert r.status_code == 201
    doc_id = r.json()["id"]

    # B's list must not contain A's doc.
    rb_list = b.get("/docs").json()
    assert all(d["id"] != doc_id for d in rb_list)

    # B's direct GET must 404, not 200/403.
    rb_get = b.get(f"/docs/{doc_id}")
    assert rb_get.status_code == 404

    # A can still see it.
    ra_get = a.get(f"/docs/{doc_id}")
    assert ra_get.status_code == 200
    assert ra_get.json()["title"] == "A's secret"
