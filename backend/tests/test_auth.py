"""Auth HTTP flow tests.

Verifies:
- signup → cookie → /me round-trip.
- /me never returns password_hash.
- login rejects a bad password with a generic 401.
- /me 401s with no cookie.
"""
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _mk_user():
    email = f"u-{uuid4()}@x.test"
    return {
        "email": email,
        "password": "correct horse battery staple",
        "display_name": "T U",
        "tenant_name": "T Co",
    }


def test_signup_me_logout_flow():
    client = TestClient(app)
    body = _mk_user()
    r = client.post("/auth/signup", json=body)
    assert r.status_code == 201, r.text
    data = r.json()
    assert "password_hash" not in data
    assert data["email"] == body["email"]

    r2 = client.get("/auth/me")
    assert r2.status_code == 200
    me = r2.json()
    assert me["id"] == data["id"]
    assert "password_hash" not in me

    r3 = client.post("/auth/logout")
    assert r3.status_code == 204

    r4 = client.get("/auth/me")
    assert r4.status_code == 401


def test_login_bad_password_is_generic_401():
    client = TestClient(app)
    body = _mk_user()
    client.post("/auth/signup", json=body)
    client.post("/auth/logout")
    r = client.post("/auth/login", json={"email": body["email"], "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid credentials"


def test_me_requires_cookie():
    client = TestClient(app)
    r = client.get("/auth/me")
    assert r.status_code == 401
