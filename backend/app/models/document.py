from uuid import UUID

from sqlalchemy import ForeignKey, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDPKMixin


class Document(Base, UUIDPKMixin, TimestampMixin):
    """A collaborative document.

    `ydoc_state` holds the latest serialized Yjs update (binary). Stage 3
    writes it on each websocket disconnect; Stage 2 initializes it empty.
    """

    __tablename__ = "documents"

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False, default="Untitled document")
    ydoc_state: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)


class DocumentSnapshot(Base, UUIDPKMixin, TimestampMixin):
    """Periodic snapshots of a document's Yjs state. Populated in Stage 6."""

    __tablename__ = "document_snapshots"

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    ydoc_state: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    label: Mapped[str | None] = mapped_column(String(300), nullable=True)
