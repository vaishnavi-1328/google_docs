from sqlalchemy import String
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDPKMixin


class User(Base, UUIDPKMixin, TimestampMixin):
    """Platform-level user record.

    Guardrail 1: `password_hash` holds an Argon2id hash. The plaintext never
    reaches storage or logs. API responses must never serialize this column.
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(CITEXT(), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
