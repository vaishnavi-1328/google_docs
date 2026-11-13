"""attachments table with RLS

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-12
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE attachments (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id     UUID NOT NULL REFERENCES tenants(id)   ON DELETE CASCADE,
            document_id   UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            uploader_id   UUID NOT NULL REFERENCES users(id)     ON DELETE CASCADE,
            content_type  VARCHAR(128) NOT NULL,
            byte_length   INTEGER NOT NULL,
            storage_path  VARCHAR(512) NOT NULL,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_attachments_doc ON attachments(document_id);

        ALTER TABLE attachments ENABLE ROW LEVEL SECURITY;
        ALTER TABLE attachments FORCE  ROW LEVEL SECURITY;
        CREATE POLICY attachments_tenant_isolation ON attachments
          USING  (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
          WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP POLICY IF EXISTS attachments_tenant_isolation ON attachments;
        DROP TABLE IF EXISTS attachments;
        """
    )
