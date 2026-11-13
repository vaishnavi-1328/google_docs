"""Version history: snapshots of a document's Yjs state.

  POST   /docs/{id}/snapshots          — take a named snapshot now
  GET    /docs/{id}/snapshots          — list (id, label, created_at)
  GET    /docs/{id}/snapshots/{sid}    — fetch raw Yjs update (binary) for preview
  POST   /docs/{id}/snapshots/{sid}:restore — overwrite ydoc_state with the snapshot

Snapshots are also taken implicitly by the WS layer whenever the room empties.
Stage 6 only adds the explicit endpoints + the listing/preview/restore UI.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..authz import effective_role, has_at_least
from ..deps import current_tenant_id, current_user, tenant_session
from ..models import ROLE_EDITOR, ROLE_VIEWER, Document, DocumentSnapshot, User

router = APIRouter(prefix="/docs/{doc_id}", tags=["versions"])


class SnapshotIn(BaseModel):
    label: str | None = Field(default=None, max_length=300)


class SnapshotMetaOut(BaseModel):
    id: UUID
    label: str | None
    created_at: datetime


@router.post("/snapshots", status_code=201)
def create_snapshot(
    doc_id: UUID,
    body: SnapshotIn,
    db: Session = Depends(tenant_session),
    user: User = Depends(current_user),
    tenant_id: UUID = Depends(current_tenant_id),
) -> SnapshotMetaOut:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(404, "not found")
    role = effective_role(db, user_id=user.id, document_id=doc_id)
    if not has_at_least(role, ROLE_EDITOR):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "editor required")
    snap = DocumentSnapshot(
        tenant_id=tenant_id,
        document_id=doc_id,
        ydoc_state=doc.ydoc_state or b"",
        label=body.label,
    )
    db.add(snap)
    db.flush()
    return SnapshotMetaOut(id=snap.id, label=snap.label, created_at=snap.created_at)


@router.get("/snapshots", response_model=list[SnapshotMetaOut])
def list_snapshots(
    doc_id: UUID,
    db: Session = Depends(tenant_session),
    user: User = Depends(current_user),
) -> list[SnapshotMetaOut]:
    role = effective_role(db, user_id=user.id, document_id=doc_id)
    if not has_at_least(role, ROLE_VIEWER):
        raise HTTPException(404, "not found")
    rows = (
        db.execute(
            select(DocumentSnapshot)
            .where(DocumentSnapshot.document_id == doc_id)
            .order_by(DocumentSnapshot.created_at.desc())
            .limit(200)
        )
        .scalars()
        .all()
    )
    return [SnapshotMetaOut(id=r.id, label=r.label, created_at=r.created_at) for r in rows]


@router.get("/snapshots/{snap_id}")
def get_snapshot_blob(
    doc_id: UUID,
    snap_id: UUID,
    db: Session = Depends(tenant_session),
    user: User = Depends(current_user),
) -> Response:
    role = effective_role(db, user_id=user.id, document_id=doc_id)
    if not has_at_least(role, ROLE_VIEWER):
        raise HTTPException(404, "not found")
    snap = db.get(DocumentSnapshot, snap_id)
    if snap is None or snap.document_id != doc_id:
        raise HTTPException(404, "not found")
    return Response(content=snap.ydoc_state, media_type="application/octet-stream")


@router.post("/snapshots/{snap_id}:restore")
def restore_snapshot(
    doc_id: UUID,
    snap_id: UUID,
    db: Session = Depends(tenant_session),
    user: User = Depends(current_user),
) -> dict[str, str]:
    role = effective_role(db, user_id=user.id, document_id=doc_id)
    if not has_at_least(role, ROLE_EDITOR):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "editor required")
    snap = db.get(DocumentSnapshot, snap_id)
    if snap is None or snap.document_id != doc_id:
        raise HTTPException(404, "not found")
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(404, "not found")
    doc.ydoc_state = snap.ydoc_state
    # NOTE: any clients currently connected will not automatically reset — they
    # continue collaborating on the live YDoc in memory. The restore applies on
    # the next room-cold-start. A hot restore requires evicting the room; we
    # document this in the Known gaps rather than adding a soft reload path.
    db.flush()
    return {"ok": "restored"}
