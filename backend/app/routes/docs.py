"""Document CRUD routes.

All routes depend on `tenant_session`, which sets `app.tenant_id` for RLS.
A document from another tenant is invisible at the Postgres layer — a GET on
such an id returns 404 not 403, by design, to avoid leaking existence.
"""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..authz import effective_role, has_at_least
from ..deps import current_tenant_id, current_user, tenant_session
from ..models import ROLE_EDITOR, ROLE_VIEWER, Document, User

router = APIRouter(prefix="/docs", tags=["docs"])


class DocCreateIn(BaseModel):
    title: str = Field(default="Untitled document", max_length=300)


class DocUpdateIn(BaseModel):
    title: str | None = Field(default=None, max_length=300)


class DocOut(BaseModel):
    id: UUID
    title: str
    owner_id: UUID
    created_at: datetime
    updated_at: datetime


def _to_out(d: Document) -> DocOut:
    return DocOut(
        id=d.id,
        title=d.title,
        owner_id=d.owner_id,
        created_at=d.created_at,
        updated_at=d.updated_at,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_doc(
    body: DocCreateIn,
    db: Session = Depends(tenant_session),
    user: User = Depends(current_user),
    tenant_id: UUID = Depends(current_tenant_id),
) -> DocOut:
    doc = Document(tenant_id=tenant_id, owner_id=user.id, title=body.title)
    db.add(doc)
    db.flush()
    return _to_out(doc)


@router.get("")
def list_docs(db: Session = Depends(tenant_session)) -> list[DocOut]:
    rows = db.execute(select(Document).order_by(Document.updated_at.desc())).scalars().all()
    return [_to_out(d) for d in rows]


@router.get("/{doc_id}")
def get_doc(
    doc_id: UUID,
    db: Session = Depends(tenant_session),
    user: User = Depends(current_user),
) -> DocOut:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="not found")
    role = effective_role(db, user_id=user.id, document_id=doc_id)
    if not has_at_least(role, ROLE_VIEWER):
        raise HTTPException(status_code=404, detail="not found")
    return _to_out(doc)


@router.patch("/{doc_id}")
def update_doc(
    doc_id: UUID,
    body: DocUpdateIn,
    db: Session = Depends(tenant_session),
    user: User = Depends(current_user),
) -> DocOut:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="not found")
    role = effective_role(db, user_id=user.id, document_id=doc_id)
    if not has_at_least(role, ROLE_EDITOR):
        raise HTTPException(status_code=403, detail="editor required")
    if body.title is not None:
        doc.title = body.title
    db.flush()
    return _to_out(doc)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_doc(
    doc_id: UUID,
    db: Session = Depends(tenant_session),
    user: User = Depends(current_user),
) -> None:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="not found")
    if doc.owner_id != user.id:
        raise HTTPException(status_code=403, detail="owner required")
    db.delete(doc)
