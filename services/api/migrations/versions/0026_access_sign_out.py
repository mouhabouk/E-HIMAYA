"""Account sign-out by an administrator (phase 10, docs/api/phase-10-contract.md §1.2).

``access.account_admin_log`` accepts the new action ``account.sign_out``.

Downgrade: the sign-out rows are removed from the proxy log (the audit log keeps them), then the old check returns.

Revision ID: 0026_access_sign_out
Revises: 0025_rls_policies
Create Date: 2026-10-21
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0026_access_sign_out"
down_revision: str | None = "0025_rls_policies"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE access.account_admin_log DROP CONSTRAINT ck_account_admin_log_action")
    op.execute(
        "ALTER TABLE access.account_admin_log ADD CONSTRAINT ck_account_admin_log_action "
        "CHECK (action IN ('account.create', 'account.update', 'account.reset', 'account.sign_out'))"
    )


def downgrade() -> None:
    op.execute("DELETE FROM access.account_admin_log WHERE action = 'account.sign_out'")
    op.execute("ALTER TABLE access.account_admin_log DROP CONSTRAINT ck_account_admin_log_action")
    op.execute(
        "ALTER TABLE access.account_admin_log ADD CONSTRAINT ck_account_admin_log_action "
        "CHECK (action IN ('account.create', 'account.update', 'account.reset'))"
    )
