"""The field agents and the mission flow of the staff app after Yamen's review (docs/phase-f/design-f.md).

* ``ops.field_agent``: the agents the room chief adds, with a one-time activation code (its fingerprint only), the
  charter they accepted and their consents. A professional number is unique in its gouvernorat.
* ``ops.staff_device``: the agent who activated it, what the phone said about itself (model, device reference, SIM
  number), the IMEI the room chief may type from the box, and the fingerprint of the current refresh token.
* ``ops.shift``: the agents on the shift with the leader (they read its missions).
* ``ops.assignment``: the point the room picked on the map, the nature the team confirmed, the steps skipped and why,
  the end without intervention and why, and whether the team opened the mission from the field.
* ``ops.crew_event``: the new writes of the phone (skip, no intervention, nature, toll, the intervention report and a
  mission opened from the field); ``ops.field_report``: two new kinds, the toll and the intervention report.

Revision ID: 0087_field_agents
Revises: 0086_mission_record
Create Date: 2026-10-30
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0087_field_agents"
down_revision: str | None = "0086_mission_record"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = (
    "'ack', 'status', 'first_report', 'casualties', 'transport', 'alert', 'attachment', 'detailed_report', "
    "'milestone', 'record'"
)
NEW_KINDS = "'skip', 'no_intervention', 'nature', 'toll', 'report', 'open'"

UPGRADE = f"""
CREATE TABLE ops.field_agent (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    gouvernorat_code    smallint NOT NULL REFERENCES geo.gouvernorat(code),
    matricule           text NOT NULL CHECK (matricule ~ '^[0-9A-Za-z]{{3,20}}$'),
    name                text NOT NULL CHECK (length(name) BETWEEN 2 AND 120),
    function            text NOT NULL CHECK (function IN ('leader', 'agent', 'driver')),
    shift_label         text CHECK (length(shift_label) <= 60),
    phone_enc           bytea,
    status              text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'disabled', 'deleted')),
    code_hash           text,
    code_expires_at     timestamptz,
    code_attempts       smallint NOT NULL DEFAULT 0,
    charter_version     text,
    charter_accepted_at timestamptz,
    consents            jsonb NOT NULL DEFAULT '{{}}'::jsonb CHECK (jsonb_typeof(consents) = 'object'),
    created_by          text NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    activated_at        timestamptz,
    disabled_at         timestamptz,
    disabled_by         text,
    disabled_reason     text CHECK (length(disabled_reason) <= 300)
);
CREATE UNIQUE INDEX ux_field_agent_matricule ON ops.field_agent (gouvernorat_code, matricule)
    WHERE status <> 'deleted';
CREATE UNIQUE INDEX ux_field_agent_code ON ops.field_agent (code_hash) WHERE code_hash IS NOT NULL;
CREATE INDEX ix_field_agent_gouvernorat ON ops.field_agent (gouvernorat_code, status);
-- As the phones: the agent themself, the managers of the gouvernorat, the national accounts. The phone's activation and
-- token renewal (no account yet) run with the system scope after the code or the refresh token was checked.
ALTER TABLE ops.field_agent ENABLE ROW LEVEL SECURITY;
CREATE POLICY field_agent_select ON ops.field_agent FOR SELECT USING (
    ehimaya.sees_all() OR 'field:' || id::text = ehimaya.subject()
    OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat()));
CREATE POLICY field_agent_insert ON ops.field_agent FOR INSERT WITH CHECK (ehimaya.scope() <> 'none');
CREATE POLICY field_agent_update ON ops.field_agent FOR UPDATE USING (
    ehimaya.sees_all() OR 'field:' || id::text = ehimaya.subject()
    OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat())) WITH CHECK (ehimaya.scope() <> 'none');

ALTER TABLE ops.staff_device
    ADD COLUMN agent_id uuid REFERENCES ops.field_agent(id),
    ADD COLUMN model text CHECK (length(model) <= 80),
    ADD COLUMN device_ref text CHECK (length(device_ref) <= 80),
    ADD COLUMN sim_number_enc bytea,
    ADD COLUMN imei_enc bytea,
    ADD COLUMN refresh_hash text,
    ADD COLUMN refresh_expires_at timestamptz;
CREATE UNIQUE INDEX ux_staff_device_refresh ON ops.staff_device (refresh_hash) WHERE refresh_hash IS NOT NULL;
CREATE INDEX ix_staff_device_agent ON ops.staff_device (agent_id) WHERE agent_id IS NOT NULL;

ALTER TABLE ops.shift ADD COLUMN crew_agent_ids uuid[] NOT NULL DEFAULT '{{}}';
CREATE INDEX ix_shift_crew_agents ON ops.shift USING gin (crew_agent_ids) WHERE ended_at IS NULL;

ALTER TABLE ops.assignment
    ADD COLUMN target_location geography(Point, 4326),
    ADD COLUMN target_note text CHECK (length(target_note) <= 500),
    ADD COLUMN crew_nature text CHECK (length(crew_nature) <= 40),
    ADD COLUMN skipped jsonb NOT NULL DEFAULT '{{}}'::jsonb CHECK (jsonb_typeof(skipped) = 'object'),
    ADD COLUMN no_intervention_reason text CHECK (length(no_intervention_reason) <= 40),
    ADD COLUMN field_initiated boolean NOT NULL DEFAULT false;

ALTER TABLE ops.crew_event DROP CONSTRAINT crew_event_kind_check;
ALTER TABLE ops.crew_event ADD CONSTRAINT crew_event_kind_check CHECK (kind IN ({KINDS}, {NEW_KINDS}));

ALTER TABLE ops.field_report DROP CONSTRAINT field_report_kind_check, DROP CONSTRAINT ck_field_report_shape;
ALTER TABLE ops.field_report
    ADD CONSTRAINT field_report_kind_check CHECK (kind IN ('first', 'update', 'detailed', 'toll', 'report')),
    ADD CONSTRAINT ck_field_report_shape CHECK (CASE kind
        WHEN 'detailed' THEN answers IS NOT NULL
        WHEN 'toll' THEN answers IS NOT NULL
        WHEN 'report' THEN note IS NOT NULL
        ELSE answers IS NULL AND severity IS NOT NULL END);
"""

DOWNGRADE = f"""
DELETE FROM ops.field_report WHERE kind IN ('toll', 'report');
ALTER TABLE ops.field_report DROP CONSTRAINT field_report_kind_check, DROP CONSTRAINT ck_field_report_shape;
ALTER TABLE ops.field_report
    ADD CONSTRAINT field_report_kind_check CHECK (kind IN ('first', 'update', 'detailed')),
    ADD CONSTRAINT ck_field_report_shape CHECK (
        (kind = 'detailed') = (answers IS NOT NULL) AND (kind = 'detailed' OR severity IS NOT NULL));

DELETE FROM ops.crew_event WHERE kind IN ({NEW_KINDS});
ALTER TABLE ops.crew_event DROP CONSTRAINT crew_event_kind_check;
ALTER TABLE ops.crew_event ADD CONSTRAINT crew_event_kind_check CHECK (kind IN ({KINDS}));

ALTER TABLE ops.assignment DROP COLUMN target_location, DROP COLUMN target_note, DROP COLUMN crew_nature,
    DROP COLUMN skipped, DROP COLUMN no_intervention_reason, DROP COLUMN field_initiated;
ALTER TABLE ops.shift DROP COLUMN crew_agent_ids;
ALTER TABLE ops.staff_device DROP COLUMN agent_id, DROP COLUMN model, DROP COLUMN device_ref,
    DROP COLUMN sim_number_enc, DROP COLUMN imei_enc, DROP COLUMN refresh_hash, DROP COLUMN refresh_expires_at;
DROP TABLE ops.field_agent;
"""  # noqa: S608 (constant SQL, nothing is interpolated from input)


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
