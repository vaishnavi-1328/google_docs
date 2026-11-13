"""FastAPI dependencies for auth, current tenant, and tenant-scoped DB session.

Guardrail 3: `current_user` + `current_tenant` are derived from the signed
session cookie. Request body/query/header `tenant_id` values are ignored by
construction — these dependencies do not read them.
"""
from collections.abc import Iterator
from uuid import UUID

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import SessionLocal, _set_tenant_guc
from .models import Membership, User
from .security import decode_session_token

SESSION_COOKIE = "session"


def _open_unscoped_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def current_identity(
    session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> tuple[UUID, UUID]:
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="no session")
    try:
        return decode_session_token(session)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid session")


def current_user(
    identity: tuple[UUID, UUID] = Depends(current_identity),
    db: Session = Depends(_open_unscoped_session),
) -> User:
    user_id, tenant_id = identity
    # Verify the claimed (user, tenant) pair is a real membership. This is the
    # guardrail-3 enforcement point: even a validly-signed token cannot act as
    # a tenant the user isn't a member of. memberships has RLS (not FORCE), so
    # the app role can read it unfiltered — we WHERE by both user_id and
    # tenant_id explicitly.
    membership = db.execute(
        select(Membership).where(
            Membership.user_id == user_id, Membership.tenant_id == tenant_id
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not a member")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unknown user")
    return user


def current_tenant_id(
    identity: tuple[UUID, UUID] = Depends(current_identity),
) -> UUID:
    return identity[1]


def tenant_session(
    tenant_id: UUID = Depends(current_tenant_id),
    _: User = Depends(current_user),  # forces membership check before any query
) -> Iterator[Session]:
    """Tenant-scoped DB session with `app.tenant_id` set for RLS."""
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
