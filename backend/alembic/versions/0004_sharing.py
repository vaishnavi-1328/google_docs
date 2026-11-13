"""document_acls, share_links, comments (all RLS)

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-12
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE document_acls (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   UUID NOT NULL REFERENCES tenants(id)   ON DELETE CASCADE,
            document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            user_id     UUID NOT NULL REFERENCES users(id)     ON DELETE CASCADE,
            role        VARCHAR(16) NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_doc_user UNIQUE (document_id, user_id),
            CONSTRAINT ck_doc_acl_role CHECK (role IN ('viewer','commenter','editor','owner'))
        );
        CREATE INDEX ix_doc_acls_doc ON document_acls(document_id);

        CREATE TABLE share_links (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   UUID NOT NULL REFERENCES tenants(id)   ON DELETE CASCADE,
            document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            role        VARCHAR(16) NOT NULL,
            revoked_at  TIMESTAMPTZ,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_share_link_role CHECK (role IN ('viewer','commenter','editor'))
        );
        CREATE INDEX ix_share_links_doc ON share_links(document_id);

        CREATE TABLE comments (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   UUID NOT NULL REFERENCES tenants(id)   ON DELETE CASCADE,
            document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            author_id   UUID NOT NULL REFERENCES users(id)     ON DELETE CASCADE,
            body        TEXT NOT NULL,
            anchor      TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_comments_doc ON comments(document_id);
        """
    )
    for t in ("document_acls", "share_links", "comments"):
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
    for t in ("comments", "share_links", "document_acls"):
        op.execute(f"DROP POLICY IF EXISTS {t}_tenant_isolation ON {t}; DROP TABLE IF EXISTS {t};")
