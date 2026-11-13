"""auth tables + RLS plumbing

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-12

Creates tenants, users, memberships. Enables RLS on memberships and sets the
default policy using `current_setting('app.tenant_id', true)`, which the
FastAPI tenant_session dependency sets per request via SET LOCAL.

Guardrail 4: RLS is the second defense layer — even if an app-level query
forgets to filter by tenant_id, Postgres will return zero rows unless
app.tenant_id matches the row's tenant_id.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE tenants (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name       TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE users (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email         CITEXT UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            display_name  VARCHAR(120) NOT NULL,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE memberships (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id    UUID NOT NULL REFERENCES users(id)   ON DELETE CASCADE,
            tenant_id  UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            role       VARCHAR(32) NOT NULL DEFAULT 'member',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_user_tenant UNIQUE (user_id, tenant_id)
        );

        CREATE INDEX ix_memberships_user_id   ON memberships(user_id);
        CREATE INDEX ix_memberships_tenant_id ON memberships(tenant_id);
        """
    )

    # RLS on memberships. A row is visible iff its tenant_id matches the
    # session GUC `app.tenant_id` set by the backend per request.
    # NULLIF + COALESCE ensures an unset GUC returns NULL, which never matches
    # any UUID — so missing context defaults to "deny all".
    op.execute(
        """
        ALTER TABLE memberships ENABLE ROW LEVEL SECURITY;
        ALTER TABLE memberships FORCE  ROW LEVEL SECURITY;

        CREATE POLICY memberships_tenant_isolation ON memberships
          USING  (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
          WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP POLICY IF EXISTS memberships_tenant_isolation ON memberships;
        DROP TABLE IF EXISTS memberships;
        DROP TABLE IF EXISTS users;
        DROP TABLE IF EXISTS tenants;
        """
    )
