"""The inspector's alerts on a mission order (phase I3, Yamen 2026-11-12; docs/phase-i/design-i.md §6).

The system tells the inspector of a mission order a first time so many days before its date (15 by default), then
reminds them a day or two before (the inspector general's settings, ``insp.policy``). The mission keeps when each
went out, so that each is sent once.

Each place of a mission order keeps the inspector's «arrived» and «left» (Yamen 2026-11-12), as the agents' app does
for an intervention: the phone's time, whether it was recorded without network, when it reached the server and where
the phone was. A mission with several places has an arrival and a departure for each.

Revision ID: 0105_mission_alerts
Revises: 0104_fleet
Create Date: 2026-11-12
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0105_mission_alerts"
down_revision: str | None = "0104_fleet"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = """
ALTER TABLE insp.mission
    ADD COLUMN notice_sent_at   timestamptz,
    ADD COLUMN reminder_sent_at timestamptz;
ALTER TABLE insp.mission_site
    ADD COLUMN arrived_at          timestamptz,
    ADD COLUMN arrived_offline     boolean NOT NULL DEFAULT false,
    ADD COLUMN arrived_received_at timestamptz,
    ADD COLUMN arrived_location    geography(Point, 4326),
    ADD COLUMN left_at             timestamptz,
    ADD COLUMN left_offline        boolean NOT NULL DEFAULT false,
    ADD COLUMN left_received_at    timestamptz,
    ADD COLUMN left_location       geography(Point, 4326),
    ADD CONSTRAINT ck_mission_site_presence CHECK (left_at IS NULL OR (arrived_at IS NOT NULL AND left_at >= arrived_at));
CREATE INDEX ix_mission_alerts ON insp.mission (on_date) WHERE status = 'planned' AND reminder_sent_at IS NULL;
"""

DOWNGRADE = """
DROP INDEX insp.ix_mission_alerts;
ALTER TABLE insp.mission_site
    DROP CONSTRAINT ck_mission_site_presence,
    DROP COLUMN arrived_at, DROP COLUMN arrived_offline, DROP COLUMN arrived_received_at, DROP COLUMN arrived_location,
    DROP COLUMN left_at, DROP COLUMN left_offline, DROP COLUMN left_received_at, DROP COLUMN left_location;
ALTER TABLE insp.mission DROP COLUMN notice_sent_at, DROP COLUMN reminder_sent_at;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
