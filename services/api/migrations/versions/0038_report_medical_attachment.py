"""Medical file attached to a report by its author (phase B2, docs/phase-b/design-b2.md §5, addition 7b).

* ``reports.medical_attachment`` — one per report at most: the 7b fields (blood group, allergies, chronic conditions,
  regular medicines, other information…) as encrypted JSON, and when it was attached. The file itself lives on the
  phone; it reaches the server only when the user ticks "attach my medical file to this report".

Row-level security: whoever sees the report sees that a file is attached (the API shows its content only to the staff
allowed to read the reporter's identity, and audits each opening); the reporter (public scope) inserts it with the
report; only the system scope deletes (retention, 30 days after the report is closed, and erasure).

Revision ID: 0038_report_medical_attachment
Revises: 0037_personal_safety
Create Date: 2026-10-23
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0038_report_medical_attachment"
down_revision: str | None = "0037_personal_safety"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = r"""
CREATE TABLE reports.medical_attachment (
    report_id   uuid PRIMARY KEY REFERENCES reports.report(id) ON DELETE CASCADE,
    data_enc    bytea NOT NULL,
    attached_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE reports.medical_attachment ENABLE ROW LEVEL SECURITY;
CREATE POLICY medical_attachment_select ON reports.medical_attachment FOR SELECT
    USING (EXISTS (SELECT 1 FROM reports.report r WHERE r.id = report_id));
CREATE POLICY medical_attachment_insert ON reports.medical_attachment FOR INSERT
    WITH CHECK (ehimaya.scope() <> 'none' AND EXISTS (SELECT 1 FROM reports.report r WHERE r.id = report_id));
CREATE POLICY medical_attachment_delete ON reports.medical_attachment FOR DELETE
    USING (ehimaya.scope() = 'system');
-- Retention locks the rows it purges (SELECT ... FOR UPDATE SKIP LOCKED), which needs an UPDATE policy too.
CREATE POLICY medical_attachment_update ON reports.medical_attachment FOR UPDATE
    USING (ehimaya.scope() = 'system') WITH CHECK (ehimaya.scope() = 'system');
"""

DOWNGRADE = r"""
DROP TABLE reports.medical_attachment;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
