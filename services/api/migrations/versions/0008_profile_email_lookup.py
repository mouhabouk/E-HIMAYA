"""Exact, case-insensitive e-mail lookup of a citizen account for one-user notifications (FR-C-17).

Profile e-mails are stored in clear (they come from the identity provider and are used for delivery), so
an expression index on ``lower(email)`` is enough; no blind index is needed.

Revision ID: 0008_profile_email_lookup
Revises: 0007_operations
Create Date: 2026-10-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008_profile_email_lookup"
down_revision: str | None = "0007_operations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE INDEX ix_profile_email_lower ON identity.profile (lower(email)) WHERE email IS NOT NULL")


def downgrade() -> None:
    op.execute("DROP INDEX identity.ix_profile_email_lower")
