from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDPKMixin

# Roles, in increasing privilege. Store as strings for DB/API readability.
ROLE_VIEWER = "viewer"
ROLE_COMMENTER = "commenter"
ROLE_EDITOR = "editor"
ROLE_OWNER = "owner"
ROLE_RANK = {ROLE_VIEWER: 1, ROLE_COMMENTER: 2, ROLE_EDITOR: 3, ROLE_OWNER: 4}


class DocumentACL(Base, UUIDPKMixin, TimestampMixin):
    """Per-user grant on a document."""

    __tablename__ = "document_acls"
    __table_args__ = (UniqueConstraint("document_id", "user_id", name="uq_doc_user"),)

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)


class ShareLink(Base, UUIDPKMixin, TimestampMixin):
    """Link-based access. The link's UUIDv4 `id` IS the token."""

    __tablename__ = "share_links"

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)
