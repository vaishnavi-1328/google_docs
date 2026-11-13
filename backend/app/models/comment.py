"""Comments are introduced here as a shell so `commenter` role has a place to go.
A full comments UI/API is out of scope for the MVP; this table exists so the
commenter role is a real thing, not a label, and so Stage 9 can light up a
simple comment sidebar on top of it.
"""
from uuid import UUID

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDPKMixin


class Comment(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "comments"

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    anchor: Mapped[str | None] = mapped_column(Text, nullable=True)  # ProseMirror selection JSON
