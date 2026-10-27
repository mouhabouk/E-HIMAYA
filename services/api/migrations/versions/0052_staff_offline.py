"""Staff app without network (phase P4d, docs/phase-p4/design-staff.md §9, F-STF-07 and F-APP-38).

* ``ops.staff_device.sms_key_enc``: the phone's own key that signs its ``EH2`` text messages (encrypted at rest).
* ``ops.crew_event.via`` and ``ops.crew_alert.via``: a write that came through the app or by SMS.
* ``ops.crew_position``: the vehicle's position during a mission (every 30 s en route, every 2 min on scene), kept
  30 days; ``ops.resource.location_at`` dates the position shown on the map.
* ``reports.report.team_en_route_at`` and ``team_on_scene_at``: the reporter is told the team is on its way, then
  there (F-APP-38); ``notify.device.team_notices`` lets the citizen turn those two pushes off.

Revision ID: 0052_staff_offline
Revises: 0051_prevention_on_site
Create Date: 2026-10-27
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0052_staff_offline"
down_revision: str | None = "0051_prevention_on_site"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = """
ALTER TABLE ops.staff_device ADD COLUMN sms_key_enc bytea;
ALTER TABLE ops.crew_event ADD COLUMN via text NOT NULL DEFAULT 'app' CHECK (via IN ('app', 'sms'));
ALTER TABLE ops.crew_alert ADD COLUMN via text NOT NULL DEFAULT 'app' CHECK (via IN ('app', 'sms'));
ALTER TABLE ops.resource ADD COLUMN location_at timestamptz;

CREATE TABLE ops.crew_position (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    assignment_id  uuid NOT NULL REFERENCES ops.assignment(id) ON DELETE CASCADE,
    incident_id    uuid NOT NULL REFERENCES ops.incident(id) ON DELETE CASCADE,
    resource_id    uuid REFERENCES ops.resource(id) ON DELETE CASCADE,
    at             timestamptz NOT NULL,
    location       geography(Point, 4326) NOT NULL,
    accuracy_m     real CHECK (accuracy_m >= 0),
    created_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (assignment_id, at)
);
CREATE INDEX ix_crew_position_assignment ON ops.crew_position (assignment_id, at DESC);
CREATE INDEX ix_crew_position_created ON ops.crew_position (created_at);

ALTER TABLE ops.crew_position ENABLE ROW LEVEL SECURITY;
CREATE POLICY crew_position_select ON ops.crew_position FOR SELECT USING (
    EXISTS (SELECT 1 FROM ops.incident i WHERE i.id = incident_id));
CREATE POLICY crew_position_insert ON ops.crew_position FOR INSERT WITH CHECK (ehimaya.scope() <> 'none');
CREATE POLICY crew_position_delete ON ops.crew_position FOR DELETE USING (ehimaya.sees_all());

ALTER TABLE reports.report
    ADD COLUMN team_en_route_at timestamptz,
    ADD COLUMN team_on_scene_at timestamptz;

ALTER TABLE notify.device ADD COLUMN team_notices boolean NOT NULL DEFAULT true;
"""

DOWNGRADE = """
ALTER TABLE notify.device DROP COLUMN team_notices;
ALTER TABLE reports.report DROP COLUMN team_en_route_at, DROP COLUMN team_on_scene_at;
DROP TABLE ops.crew_position;
ALTER TABLE ops.resource DROP COLUMN location_at;
ALTER TABLE ops.crew_alert DROP COLUMN via;
ALTER TABLE ops.crew_event DROP COLUMN via;
ALTER TABLE ops.staff_device DROP COLUMN sms_key_enc;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
