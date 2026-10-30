"""Reports entered by an operations room (phase N, docs/phase-n/design-n.md §5).

A room agent writes down a report that came by telephone, radio or in person. It is a report like the others
(tracking code, AI baseline, grouping into interventions, claim and follow-up), with ``source = 'room'``, the channel
it came by, and who entered it. The room that entered it holds it from the start.

Revision ID: 0082_room_intake
Revises: 0081_saved_places
Create Date: 2026-10-30
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0082_room_intake"
down_revision: str | None = "0081_saved_places"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = """
ALTER TABLE reports.report DROP CONSTRAINT report_source_check;
ALTER TABLE reports.report ADD CONSTRAINT report_source_check
    CHECK (source IN ('app', 'portal', 'iot', 'call', 'sms', 'room'));
ALTER TABLE reports.report
    ADD COLUMN intake_channel text,
    ADD COLUMN entered_by text,
    ADD COLUMN entered_by_name text,
    ADD CONSTRAINT ck_report_intake CHECK (
        (source = 'room') = (intake_channel IS NOT NULL AND entered_by IS NOT NULL)
        AND (intake_channel IS NULL OR intake_channel IN ('phone', 'radio', 'in_person', 'other'))
    );
"""

DOWNGRADE = """
ALTER TABLE reports.report DROP CONSTRAINT ck_report_intake;
-- A report entered by a room stays, as a call.
UPDATE reports.report SET source = 'call' WHERE source = 'room';
ALTER TABLE reports.report DROP COLUMN intake_channel, DROP COLUMN entered_by, DROP COLUMN entered_by_name;
ALTER TABLE reports.report DROP CONSTRAINT report_source_check;
ALTER TABLE reports.report ADD CONSTRAINT report_source_check
    CHECK (source IN ('app', 'portal', 'iot', 'call', 'sms'));
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
