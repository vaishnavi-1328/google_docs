"""Image/file attachments for a document.

Dev storage is a local folder tree `uploads/<tenant_id>/<attachment_id>.<ext>`.
Path contains the tenant id, so a browser of tenant A never even forms a URL
that points at tenant B's files, and the serve route re-checks tenant+ACL.

Images are capped at 10 MB and whitelisted by MIME type.
"""
from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..authz import effective_role, has_at_least
from ..deps import current_tenant_id, current_user, tenant_session
from ..models import ROLE_EDITOR, ROLE_VIEWER, Attachment, User

router = APIRouter(prefix="/docs/{doc_id}", tags=["attachments"])

UPLOAD_ROOT = Path(os.environ.get("UPLOAD_ROOT", "uploads")).resolve()
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
MAX_BYTES = 10 * 1024 * 1024
ALLOWED_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp", "image/svg+xml"}
EXT = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/svg+xml": "svg",
}


class AttachmentOut(BaseModel):
    id: UUID
    url: str
    content_type: str
    byte_length: int


@router.post("/attachments", response_model=AttachmentOut, status_code=status.HTTP_201_CREATED)
async def upload(
    doc_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(tenant_session),
    user: User = Depends(current_user),
    tenant_id: UUID = Depends(current_tenant_id),
) -> AttachmentOut:
    role = effective_role(db, user_id=user.id, document_id=doc_id)
    if not has_at_least(role, ROLE_EDITOR):
        raise HTTPException(403, "editor required")
    ct = (file.content_type or "application/octet-stream").split(";")[0].strip().lower()
    if ct not in ALLOWED_TYPES:
        raise HTTPException(415, f"content type not allowed: {ct}")
    body = await file.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise HTTPException(413, "too large")

    att = Attachment(
        tenant_id=tenant_id,
        document_id=doc_id,
        uploader_id=user.id,
        content_type=ct,
        byte_length=len(body),
        storage_path="",  # set after we know the id
    )
    db.add(att)
    db.flush()
    tenant_dir = UPLOAD_ROOT / str(tenant_id)
    tenant_dir.mkdir(parents=True, exist_ok=True)
    disk_path = tenant_dir / f"{att.id}.{EXT[ct]}"
    disk_path.write_bytes(body)
    att.storage_path = str(disk_path)
    db.flush()
    return AttachmentOut(
        id=att.id,
        url=f"/docs/{doc_id}/attachments/{att.id}",
        content_type=ct,
        byte_length=att.byte_length,
    )


@router.get("/attachments/{att_id}")
def download(
    doc_id: UUID,
    att_id: UUID,
    db: Session = Depends(tenant_session),
    user: User = Depends(current_user),
) -> FileResponse:
    role = effective_role(db, user_id=user.id, document_id=doc_id)
    if not has_at_least(role, ROLE_VIEWER):
        raise HTTPException(404, "not found")
    att = db.get(Attachment, att_id)
    if att is None or att.document_id != doc_id:
        raise HTTPException(404, "not found")
    # Guardrail belt-and-braces: resolve under UPLOAD_ROOT and refuse paths that escape.
    p = Path(att.storage_path).resolve()
    if UPLOAD_ROOT not in p.parents and p != UPLOAD_ROOT:
        raise HTTPException(500, "bad storage path")
    return FileResponse(p, media_type=att.content_type)
