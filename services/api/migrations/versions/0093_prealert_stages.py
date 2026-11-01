"""Fire detection in two kinds of devices and two stages (Yamen, 2026-11-01).

* ``reports.live_stream.monitored_by``: a camera of an institution is followed by its owner (``owner``: the staged
  pre-alert) or by the Civil Protection (``room``: a device the Civil Protection installed or has the right to follow;
  a fire it confirms goes to the room at once).
* ``org.member.safety_officer``: the head of the institution's safety team, told first.
* ``org.prealert.stage``: who is being asked now: ``officer`` (60 s), then ``owner`` (60 s), then the room is told
  automatically; ``room`` for a device the Civil Protection follows.

Revision ID: 0093_prealert_stages
Revises: 0092_feature_everyone
Create Date: 2026-11-01
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0093_prealert_stages"
down_revision: str | None = "0092_feature_everyone"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = """
ALTER TABLE reports.live_stream ADD COLUMN monitored_by text NOT NULL DEFAULT 'owner'
    CONSTRAINT ck_live_stream_monitored_by CHECK (monitored_by IN ('owner', 'room'));
ALTER TABLE org.member ADD COLUMN safety_officer boolean NOT NULL DEFAULT false;
ALTER TABLE org.prealert ADD COLUMN stage text NOT NULL DEFAULT 'owner'
    CONSTRAINT ck_prealert_stage CHECK (stage IN ('officer', 'owner', 'room'));
-- The officer's delay is 60 s (it was the owner's 90 s): a saved copy of the old default follows the new one.
UPDATE platform.setting SET value = jsonb_set(value, '{orgs.prealert_seconds}', '60')
    WHERE key = 'operations.thresholds' AND value->>'orgs.prealert_seconds' = '90';
"""

DOWNGRADE = """
ALTER TABLE org.prealert DROP COLUMN stage;
ALTER TABLE org.member DROP COLUMN safety_officer;
ALTER TABLE reports.live_stream DROP COLUMN monitored_by;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
