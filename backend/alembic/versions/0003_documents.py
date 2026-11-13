"""documents + document_snapshots with RLS

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-12
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE documents (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            owner_id    UUID NOT NULL REFERENCES users(id)   ON DELETE RESTRICT,
            title       VARCHAR(300) NOT NULL DEFAULT 'Untitled document',
            ydoc_state  BYTEA,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_documents_tenant_id ON documents(tenant_id);
        CREATE INDEX ix_documents_owner_id  ON documents(owner_id);

        CREATE TABLE document_snapshots (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id    UUID NOT NULL REFERENCES tenants(id)   ON DELETE CASCADE,
            document_id  UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            ydoc_state   BYTEA NOT NULL,
            label        VARCHAR(300),
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_doc_snaps_doc ON document_snapshots(document_id);
        """
    )
    for t in ("documents", "document_snapshots"):
        op.execute(
            f"""
            ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;
            ALTER TABLE {t} FORCE  ROW LEVEL SECURITY;
            CREATE POLICY {t}_tenant_isolation ON {t}
              USING  (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
            """
        )


def downgrade() -> None:
    op.execute(
        """
        DROP POLICY IF EXISTS document_snapshots_tenant_isolation ON document_snapshots;
        DROP POLICY IF EXISTS documents_tenant_isolation          ON documents;
        DROP TABLE IF EXISTS document_snapshots;
        DROP TABLE IF EXISTS documents;
        """
    )
