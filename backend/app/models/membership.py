from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDPKMixin


class Membership(Base, UUIDPKMixin, TimestampMixin):
    """Links a user to a tenant with a platform role.

    `tenant_id` lives here because a user can belong to multiple tenants.
    The user's active tenant for a given session is set via the JWT.
    """

    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "tenant_id", name="uq_user_tenant"),)

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="member")
