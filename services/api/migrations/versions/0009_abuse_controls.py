"""Abuse controls: anonymous-budget verification flag on reports, verified media type and quarantine.

* ``reports.report.needs_verification`` / ``verification_reason`` — a report accepted beyond the global
  anonymous budget (or while the rate limiter ran degraded) is never rejected: it is flagged for a human
  check, its priority lowered, and the dashboard shows a badge + filter (A1/A2).
* ``reports.media.verified_type`` / ``rejection_reason`` and the ``quarantined`` status — the verification
  worker sniffs magic bytes; media is served with the verified type only. A declared type that does not
  match the bytes, or a disallowed type, is quarantined (kept for staff, never served inline) (A7).

Revision ID: 0009_abuse_controls
Revises: 0008_profile_email_lookup
Create Date: 2026-10-19
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0009_abuse_controls"
down_revision: str | None = "0008_profile_email_lookup"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE = r"""
ALTER TABLE reports.report
    ADD COLUMN needs_verification  boolean NOT NULL DEFAULT false,
    ADD COLUMN verification_reason text,
    ADD CONSTRAINT ck_report_verification_reason CHECK (
        verification_reason IS NULL OR verification_reason IN ('anonymous_budget', 'limiter_degraded'));
CREATE INDEX ix_report_needs_verification ON reports.report (received_at DESC) WHERE needs_verification;

ALTER TABLE reports.media
    ADD COLUMN verified_type    text,
    ADD COLUMN rejection_reason text,
    DROP CONSTRAINT ck_media_status,
    ADD CONSTRAINT ck_media_status CHECK (status IN ('uploading', 'verifying', 'stored', 'rejected', 'quarantined'));
"""


DOWNGRADE = r"""
UPDATE reports.media SET status = 'rejected' WHERE status = 'quarantined';
ALTER TABLE reports.media
    DROP CONSTRAINT ck_media_status,
    ADD CONSTRAINT ck_media_status CHECK (status IN ('uploading', 'verifying', 'stored', 'rejected')),
    DROP COLUMN rejection_reason,
    DROP COLUMN verified_type;

DROP INDEX reports.ix_report_needs_verification;
ALTER TABLE reports.report
    DROP CONSTRAINT ck_report_verification_reason,
    DROP COLUMN verification_reason,
    DROP COLUMN needs_verification;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
