"""Four eyes on alerts (phase 10, docs/api/phase-10-contract.md §5.1).

* ``notify.message``: the last editor (``updated_by``), and the emergency override: ``single_reviewer`` with its
  ``emergency_reason``, then the second person who acknowledged it afterwards (``reviewed_by``, ``reviewed_at``).
* ``platform.setting`` ``alerts.four_eyes`` (default true).

Downgrade: the columns and the setting are dropped.

Revision ID: 0028_notify_four_eyes
Revises: 0027_orgs_certificate_revocation
Create Date: 2026-10-21
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0028_notify_four_eyes"
down_revision: str | None = "0027_orgs_certificate_revocation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    run_script(
        """
        ALTER TABLE notify.message
            ADD COLUMN updated_by        text,
            ADD COLUMN updated_by_name   text,
            ADD COLUMN single_reviewer   boolean NOT NULL DEFAULT false,
            ADD COLUMN emergency_reason  text,
            ADD COLUMN reviewed_by       text,
            ADD COLUMN reviewed_by_name  text,
            ADD COLUMN reviewed_at       timestamptz,
            ADD CONSTRAINT ck_message_single_reviewer CHECK (NOT single_reviewer OR emergency_reason IS NOT NULL);
        CREATE INDEX ix_message_review_needed ON notify.message (published_at)
            WHERE single_reviewer AND reviewed_at IS NULL;
        INSERT INTO platform.setting (key, value) VALUES ('alerts.four_eyes', 'true') ON CONFLICT (key) DO NOTHING;
        """
    )


def downgrade() -> None:
    run_script(
        """
        DELETE FROM platform.setting WHERE key = 'alerts.four_eyes';
        DROP INDEX notify.ix_message_review_needed;
        ALTER TABLE notify.message DROP CONSTRAINT ck_message_single_reviewer,
            DROP COLUMN updated_by, DROP COLUMN updated_by_name, DROP COLUMN single_reviewer,
            DROP COLUMN emergency_reason, DROP COLUMN reviewed_by, DROP COLUMN reviewed_by_name,
            DROP COLUMN reviewed_at;
        """
    )
