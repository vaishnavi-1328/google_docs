"""POST /docs/{id}/export?format=pdf  body: {html: "<p>…</p>"} → file download.

The client sends the current TipTap HTML so the server doesn't need to run a
ProseMirror schema in Python. The server still checks that the caller has at
least viewer access to the doc under the current tenant.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..authz import effective_role, has_at_least
from ..deps import current_user, tenant_session
from ..exporters import export_document
from ..models import ROLE_VIEWER, Document, User

router = APIRouter(prefix="/docs/{doc_id}", tags=["export"])


class ExportIn(BaseModel):
    html: str = Field(default="")


@router.post("/export")
def export(
    doc_id: UUID,
    body: ExportIn,
    fmt: str = Query(default="pdf", alias="format"),
    db: Session = Depends(tenant_session),
    user: User = Depends(current_user),
) -> Response:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="not found")
    role = effective_role(db, user_id=user.id, document_id=doc_id)
    if not has_at_least(role, ROLE_VIEWER):
        raise HTTPException(status_code=404, detail="not found")
    try:
        data, mime, filename = export_document(fmt, doc.title, body.html)  # type: ignore[arg-type]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return Response(
        content=data,
        media_type=mime,
        headers={"content-disposition": f'attachment; filename="{filename}"'},
    )
