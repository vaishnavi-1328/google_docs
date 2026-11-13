"""Sharing routes.

  POST /docs/{id}/invite   — invite a user by email at a role
  DELETE /docs/{id}/invite/{user_id}
  GET  /docs/{id}/acl      — list grants + active share link (if any)
  POST /docs/{id}/share-link      — create a share link (role)
  DELETE /docs/{id}/share-link/{link_id} — revoke a share link

All routes require the caller to be at least editor on the doc. Owner is the
only role allowed to invite editors; everything else is open to editors.
"""
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..authz import effective_role, has_at_least
from ..deps import current_tenant_id, current_user, tenant_session
from ..models import (
    ROLE_COMMENTER,
    ROLE_EDITOR,
    ROLE_OWNER,
    ROLE_VIEWER,
    Document,
    DocumentACL,
    Membership,
    ShareLink,
    User,
)

router = APIRouter(prefix="/docs/{doc_id}", tags=["sharing"])

VALID_ACL_ROLES = {ROLE_VIEWER, ROLE_COMMENTER, ROLE_EDITOR}


class InviteIn(BaseModel):
    email: EmailStr
    role: str


class AclEntryOut(BaseModel):
    user_id: UUID
    email: str
    role: str


class ShareLinkOut(BaseModel):
    id: UUID
    role: str
    revoked_at: datetime | None


class AclOut(BaseModel):
    role_me: str | None
    owner_id: UUID
    entries: list[AclEntryOut]
    links: list[ShareLinkOut]


class ShareLinkIn(BaseModel):
    role: str


def _require_editor(db: Session, user_id: UUID, doc_id: UUID) -> str:
    role = effective_role(db, user_id=user_id, document_id=doc_id)
    if not has_at_least(role, ROLE_EDITOR):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="editor required")
    return role or ""


@router.get("/acl", response_model=AclOut)
def get_acl(
    doc_id: UUID,
    db: Session = Depends(tenant_session),
    user: User = Depends(current_user),
) -> AclOut:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(404, "not found")
    role = effective_role(db, user_id=user.id, document_id=doc_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="no access")
    rows = (
        db.execute(
            select(DocumentACL, User).join(User, User.id == DocumentACL.user_id).where(
                DocumentACL.document_id == doc_id
            )
        )
        .all()
    )
    entries = [AclEntryOut(user_id=u.id, email=u.email, role=a.role) for a, u in rows]
    links = [
        ShareLinkOut(id=l.id, role=l.role, revoked_at=l.revoked_at)
        for l in db.execute(select(ShareLink).where(ShareLink.document_id == doc_id)).scalars()
    ]
    return AclOut(role_me=role, owner_id=doc.owner_id, entries=entries, links=links)


@router.post("/invite", response_model=AclEntryOut, status_code=status.HTTP_201_CREATED)
def invite(
    doc_id: UUID,
    body: InviteIn,
    db: Session = Depends(tenant_session),
    user: User = Depends(current_user),
    tenant_id: UUID = Depends(current_tenant_id),
) -> AclEntryOut:
    if body.role not in VALID_ACL_ROLES:
        raise HTTPException(400, "invalid role")
    caller_role = _require_editor(db, user.id, doc_id)
    if body.role == ROLE_EDITOR and caller_role != ROLE_OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="owner required to grant editor")

    # Look up the user globally — but only grant if they're already a member
    # of this tenant. We do NOT create cross-tenant memberships via invite.
    from ..db import SessionLocal  # local import avoids cycle

    s = SessionLocal()
    try:
        s.begin()
        target = s.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
        if target is None:
            s.rollback()
            raise HTTPException(404, "no such user")
        member = s.execute(
            select(Membership).where(
                Membership.user_id == target.id, Membership.tenant_id == tenant_id
            )
        ).scalar_one_or_none()
        if member is None:
            # Soft-create: add them to the tenant with the plain `member` role.
            from sqlalchemy import text as _text
            s.execute(_text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)})
            s.execute(
                _text(
                    "INSERT INTO memberships(user_id, tenant_id, role) VALUES (:u, :t, 'member')"
                ),
                {"u": str(target.id), "t": str(tenant_id)},
            )
        s.commit()
        target_id = target.id
        target_email = target.email
    except HTTPException:
        raise
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()

    existing = db.execute(
        select(DocumentACL).where(
            DocumentACL.document_id == doc_id, DocumentACL.user_id == target_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.role = body.role
        db.flush()
        acl = existing
    else:
        acl = DocumentACL(
            tenant_id=tenant_id, document_id=doc_id, user_id=target_id, role=body.role
        )
        db.add(acl)
        db.flush()
    return AclEntryOut(user_id=target_id, email=target_email, role=acl.role)


@router.delete("/invite/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invite(
    doc_id: UUID,
    user_id: UUID,
    db: Session = Depends(tenant_session),
    user: User = Depends(current_user),
) -> None:
    _require_editor(db, user.id, doc_id)
    existing = db.execute(
        select(DocumentACL).where(
            DocumentACL.document_id == doc_id, DocumentACL.user_id == user_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        db.delete(existing)


@router.post("/share-link", response_model=ShareLinkOut, status_code=status.HTTP_201_CREATED)
def create_share_link(
    doc_id: UUID,
    body: ShareLinkIn,
    db: Session = Depends(tenant_session),
    user: User = Depends(current_user),
    tenant_id: UUID = Depends(current_tenant_id),
) -> ShareLinkOut:
    if body.role not in VALID_ACL_ROLES:
        raise HTTPException(400, "invalid role")
    _require_editor(db, user.id, doc_id)
    link = ShareLink(tenant_id=tenant_id, document_id=doc_id, role=body.role)
    db.add(link)
    db.flush()
    return ShareLinkOut(id=link.id, role=link.role, revoked_at=None)


@router.delete("/share-link/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_share_link(
    doc_id: UUID,
    link_id: UUID,
    db: Session = Depends(tenant_session),
    user: User = Depends(current_user),
) -> None:
    _require_editor(db, user.id, doc_id)
    link = db.get(ShareLink, link_id)
    if link is None or link.document_id != doc_id:
        raise HTTPException(404, "not found")
    link.revoked_at = datetime.now(tz=UTC)
    db.flush()
