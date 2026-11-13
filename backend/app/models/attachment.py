from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDPKMixin


class Attachment(Base, UUIDPKMixin, TimestampMixin):
    """A file uploaded for use in a document (image, etc)."""

    __tablename__ = "attachments"

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    uploader_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    byte_length: Mapped[int] = mapped_column(Integer, nullable=False)
    # Disk path is tenant-scoped: uploads/<tenant>/<attachment_uuid>.<ext>
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
