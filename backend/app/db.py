"""Database engine, sessions, and the tenant-scoped session dependency.

Guardrail 4: Every request that reads/writes tenant data must go through
`get_tenant_session`, which runs `SET LOCAL app.tenant_id = :tid` on the
connection so Postgres RLS policies can enforce isolation. If a route forgets
`current_user`/`current_tenant` and uses `get_session` instead, it will NOT
see any tenant rows — the RLS policy `USING (tenant_id = current_setting(...))`
evaluates against an empty GUC and denies by default.
"""
from collections.abc import Iterator
from uuid import UUID

from fastapi import Depends
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .settings import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_session() -> Iterator[Session]:
    """Un-scoped session. For auth/signup where no tenant context exists yet.

    Routes that touch tenant data must use `get_tenant_session` instead.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _set_tenant_guc(session: Session, tenant_id: UUID) -> None:
    # set_config(name, value, is_local=true) is the parameterizable equivalent
    # of SET LOCAL; Postgres rejects bind params for the bare SET LOCAL form.
    # The GUC is still scoped to the current transaction.
    session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


def get_tenant_session_factory(tenant_id: UUID) -> Iterator[Session]:
    session = SessionLocal()
    try:
        session.begin()
        _set_tenant_guc(session, tenant_id)
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_tenant_session(
    tenant_id: UUID = Depends(lambda: None),  # replaced at import time below
) -> Iterator[Session]:
    # The real dependency wiring happens in deps.py to avoid a circular import.
    raise RuntimeError("Use app.deps.tenant_session instead of calling directly")
