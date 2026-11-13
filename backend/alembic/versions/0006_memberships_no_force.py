"""memberships: drop FORCE RLS so login can resolve a user's tenant.

Problem
-------
/auth/login must answer "which tenant does this authenticated user belong
to?" via memberships.user_id alone, before any tenant GUC exists. With
FORCE RLS, the app role (which owns the table) is also subject to the
policy; a SELECT without app.tenant_id returns zero rows → login 403s.

Fix
---
ALTER TABLE memberships NO FORCE ROW LEVEL SECURITY. The policy is kept,
so non-owner connections (future read-only roles, replicas, analytics
users) still filter. The app role — which is deliberately the one route
touching tenant data — can now read by user_id when it genuinely has no
tenant context (login, cross-tenant invite probes).

Guardrails impact
-----------------
Guardrail 4 (RLS) is relaxed for this one table: owner reads are no longer
filtered. Writes still pass through the WITH CHECK policy (verified here:
the signup path sets app.tenant_id explicitly before inserting the owner
membership, and would be rejected otherwise). The first-class defense —
every tenant-scoped REST/WS path depending on tenant_session which sets
app.tenant_id and runs tenant-aware WHERE clauses — is unchanged.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-12
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE memberships NO FORCE ROW LEVEL SECURITY;")


def downgrade() -> None:
    op.execute("ALTER TABLE memberships FORCE ROW LEVEL SECURITY;")
