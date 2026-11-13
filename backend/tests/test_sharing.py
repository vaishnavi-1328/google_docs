"""ACL + sharing tests."""
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _signup(c, tenant_name=None):
    body = {
        "email": f"u-{uuid4()}@x.test",
        "password": "correct horse battery staple",
        "display_name": "U",
        "tenant_name": tenant_name or f"T-{uuid4().hex[:6]}",
    }
    r = c.post("/auth/signup", json=body)
    assert r.status_code == 201, r.text
    return body["email"]


def test_viewer_cannot_delete():
    owner = TestClient(app)
    friend = TestClient(app)
    tn = f"T-{uuid4().hex[:6]}"
    _signup(owner, tenant_name=tn)
    friend_email = _signup(friend, tenant_name=tn)

    doc = owner.post("/docs", json={"title": "X"}).json()
    did = doc["id"]
    r = owner.post(f"/docs/{did}/invite", json={"email": friend_email, "role": "viewer"})
    assert r.status_code == 201, r.text

    # Friend can read.
    assert friend.get(f"/docs/{did}").status_code == 200
    # Friend cannot patch or delete.
    assert friend.patch(f"/docs/{did}", json={"title": "pwn"}).status_code == 403
    assert friend.delete(f"/docs/{did}").status_code == 403
    # Owner can delete.
    assert owner.delete(f"/docs/{did}").status_code == 204


def test_share_link_revoke():
    owner = TestClient(app)
    _signup(owner)
    doc = owner.post("/docs", json={"title": "Y"}).json()
    did = doc["id"]
    r = owner.post(f"/docs/{did}/share-link", json={"role": "viewer"})
    assert r.status_code == 201
    lid = r.json()["id"]
    r2 = owner.delete(f"/docs/{did}/share-link/{lid}")
    assert r2.status_code == 204
    acl = owner.get(f"/docs/{did}/acl").json()
    link = next(l for l in acl["links"] if l["id"] == lid)
    assert link["revoked_at"] is not None
