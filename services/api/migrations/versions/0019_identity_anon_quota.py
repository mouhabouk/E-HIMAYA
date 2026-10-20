"""Anonymous report quota (phase 9, docs/api/phase-9-contract.md §3): a counter per anonymous installation.

``identity.account.anon_reports_accepted`` counts the anonymous non-SMS reports accepted for the account (incremented
in the report's own transaction, so a rolled-back insert never counts) and ``anon_quota_reached_at`` records when the
quota was reached. No backfill: every existing installation starts at 0 (owner rule: 5 accepted reports counted from
the release), so no device is blocked by reports made before the rule existed.

An SOS beyond the quota is accepted and flagged: ``reports.report.verification_reason`` gains ``anonymous_quota``.

Revision ID: 0019_identity_anon_quota
Revises: 0018_platform_settings
Create Date: 2026-10-20
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0019_identity_anon_quota"
down_revision: str | None = "0018_platform_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE = r"""
ALTER TABLE identity.account
    ADD COLUMN anon_reports_accepted integer NOT NULL DEFAULT 0,
    ADD COLUMN anon_quota_reached_at timestamptz,
    ADD CONSTRAINT ck_account_anon_reports_accepted CHECK (anon_reports_accepted >= 0);

ALTER TABLE reports.report
    DROP CONSTRAINT ck_report_verification_reason,
    ADD CONSTRAINT ck_report_verification_reason CHECK (
        verification_reason IS NULL
        OR verification_reason IN ('anonymous_budget', 'anonymous_quota', 'limiter_degraded'));
"""

DOWNGRADE = r"""
UPDATE reports.report SET verification_reason = 'anonymous_budget' WHERE verification_reason = 'anonymous_quota';
ALTER TABLE reports.report
    DROP CONSTRAINT ck_report_verification_reason,
    ADD CONSTRAINT ck_report_verification_reason CHECK (
        verification_reason IS NULL OR verification_reason IN ('anonymous_budget', 'limiter_degraded'));

ALTER TABLE identity.account
    DROP CONSTRAINT IF EXISTS ck_account_anon_reports_accepted,
    DROP COLUMN IF EXISTS anon_quota_reached_at,
    DROP COLUMN IF EXISTS anon_reports_accepted;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
