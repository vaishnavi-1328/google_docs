"""RLS isolation tests.

These tests assume a live Postgres from `make db.up` and that migrations have
been applied (`make db.migrate`). They work directly against the engine so
they verify the database-level policy, not just the app-level filter.
"""
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db import SessionLocal


@pytest.fixture
def two_tenants():
    """Seed two tenants + a membership in each, return their ids."""
    t_a = uuid4()
    t_b = uuid4()
    u_a = uuid4()
    u_b = uuid4()

    s = SessionLocal()
    try:
        s.begin()
        # tenants/users are not RLS-protected; plain inserts are fine.
        s.execute(text("INSERT INTO tenants(id, name) VALUES (:id, 'A')"), {"id": str(t_a)})
        s.execute(text("INSERT INTO tenants(id, name) VALUES (:id, 'B')"), {"id": str(t_b)})
        s.execute(
            text(
                "INSERT INTO users(id, email, password_hash, display_name)"
                " VALUES (:id, :e, 'x', 'A')"
            ),
            {"id": str(u_a), "e": f"a-{uuid4()}@x.test"},
        )
        s.execute(
            text(
                "INSERT INTO users(id, email, password_hash, display_name)"
                " VALUES (:id, :e, 'x', 'B')"
            ),
            {"id": str(u_b), "e": f"b-{uuid4()}@x.test"},
        )
        # Memberships are RLS-protected with FORCE: insert each row under the
        # matching tenant GUC so WITH CHECK passes.
        s.execute(text("SET LOCAL app.tenant_id = :t"), {"t": str(t_a)})
        s.execute(
            text("INSERT INTO memberships(user_id, tenant_id) VALUES (:u, :t)"),
            {"u": str(u_a), "t": str(t_a)},
        )
        s.commit()

        s.begin()
        s.execute(text("SET LOCAL app.tenant_id = :t"), {"t": str(t_b)})
        s.execute(
            text("INSERT INTO memberships(user_id, tenant_id) VALUES (:u, :t)"),
            {"u": str(u_b), "t": str(t_b)},
        )
        s.commit()

        yield {"t_a": t_a, "t_b": t_b, "u_a": u_a, "u_b": u_b}
    finally:
        s.close()
        # Cleanup. Memberships cascade from tenants; users are plain.
        c = SessionLocal()
        try:
            c.begin()
            c.execute(text("DELETE FROM tenants WHERE id IN (:a, :b)"), {"a": str(t_a), "b": str(t_b)})
            c.execute(text("DELETE FROM users   WHERE id IN (:a, :b)"), {"a": str(u_a), "b": str(u_b)})
            c.commit()
        finally:
            c.close()


def test_rls_blocks_cross_tenant_select(two_tenants):
    """With app.tenant_id = tenant A, memberships from tenant B must not appear."""
    t_a = two_tenants["t_a"]
    s = SessionLocal()
    try:
        s.begin()
        s.execute(text("SET LOCAL app.tenant_id = :t"), {"t": str(t_a)})
        rows = s.execute(text("SELECT tenant_id FROM memberships")).all()
        assert all(r[0] == t_a for r in rows), "RLS leaked rows from another tenant"
        assert len(rows) >= 1
    finally:
        s.rollback()
        s.close()


def test_rls_denies_insert_for_other_tenant(two_tenants):
    """WITH CHECK must reject inserting a row for a tenant that isn't the GUC."""
    from sqlalchemy.exc import DBAPIError

    t_a = two_tenants["t_a"]
    t_b = two_tenants["t_b"]
    u_a = two_tenants["u_a"]

    s = SessionLocal()
    try:
        s.begin()
        s.execute(text("SET LOCAL app.tenant_id = :t"), {"t": str(t_a)})
        with pytest.raises(DBAPIError):
            s.execute(
                text("INSERT INTO memberships(user_id, tenant_id) VALUES (:u, :t)"),
                {"u": str(u_a), "t": str(t_b)},
            )
            s.flush()
    finally:
        s.rollback()
        s.close()


def test_rls_denies_without_guc(two_tenants):
    """No GUC set → zero rows visible (default-deny)."""
    s = SessionLocal()
    try:
        s.begin()
        rows = s.execute(text("SELECT count(*) FROM memberships")).scalar_one()
        assert rows == 0
    finally:
        s.rollback()
        s.close()
