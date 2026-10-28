"""The follow-up of a programme activity (phase L4, docs/phase-l/design-l4.md §6; Yamen, 2026-10-28): in progress,
done, not done, postponed or refused, set by hand or, for an activity with hours, by the clock (in progress at its
start, done at its end). ``status_manual`` keeps a status set by hand ahead of the clock.

Revision ID: 0063_schedule_statuses
Revises: 0062_schedule
Create Date: 2026-10-28
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0063_schedule_statuses"
down_revision: str | None = "0062_schedule"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = """
ALTER TABLE sched.item DROP CONSTRAINT item_status_check;
ALTER TABLE sched.item ADD CONSTRAINT item_status_check
    CHECK (status IN ('planned', 'in_progress', 'done', 'not_done', 'postponed', 'refused', 'cancelled'));
ALTER TABLE sched.item ADD COLUMN status_manual boolean NOT NULL DEFAULT false;
UPDATE sched.item SET status_manual = true WHERE status <> 'planned';
"""

DOWNGRADE = """
UPDATE sched.item SET status = 'planned' WHERE status = 'in_progress';
UPDATE sched.item SET status = 'cancelled' WHERE status IN ('not_done', 'refused');
ALTER TABLE sched.item DROP COLUMN status_manual;
ALTER TABLE sched.item DROP CONSTRAINT item_status_check;
ALTER TABLE sched.item ADD CONSTRAINT item_status_check
    CHECK (status IN ('planned', 'done', 'postponed', 'cancelled'));
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
