"""Doc-level authorization helpers.

A user may access a document if any of the following hold (in tenant scope):
  * they own it (`documents.owner_id == user.id`)
  * they have a `document_acls` row for it
  * a valid (not revoked) share link for the doc is presented AND they are
    logged in and a member of the tenant that owns the doc

This module returns the effective role (viewer < commenter < editor < owner),
or None. Callers compare against a required role via `has_at_least`.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ROLE_EDITOR, ROLE_OWNER, ROLE_RANK, Document, DocumentACL, ShareLink


def effective_role(
    db: Session, *, user_id: UUID, document_id: UUID, link_token: UUID | None = None
) -> str | None:
    doc = db.get(Document, document_id)
    if doc is None:
        return None  # RLS already said "not in tenant"; nothing to grant.
    if doc.owner_id == user_id:
        return ROLE_OWNER
    acl = db.execute(
        select(DocumentACL).where(
            DocumentACL.document_id == document_id, DocumentACL.user_id == user_id
        )
    ).scalar_one_or_none()
    best: str | None = acl.role if acl else None

    if link_token is not None:
        link = db.get(ShareLink, link_token)
        if link is not None and link.document_id == document_id and link.revoked_at is None:
            if best is None or ROLE_RANK[link.role] > ROLE_RANK[best]:
                best = link.role
    return best


def has_at_least(role: str | None, required: str) -> bool:
    if role is None:
        return False
    return ROLE_RANK[role] >= ROLE_RANK[required]


def can_edit(role: str | None) -> bool:
    return has_at_least(role, ROLE_EDITOR)
