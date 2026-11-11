"""The fleet and its maintenance, live coverage and repositioning (OS3, Yamen 2026-11-11; docs/phase-os3/design-os3.md).

* ``ops.resource`` (the vehicle register of phase R1) gains the card the maintenance department keeps: plate number
  (رقم منجمي), odometer, acquisition date; the fault the room declared; the workshop, reason and expected end of a
  maintenance; the decommissioning decision (``out_reason = 'retired'``). The administrative number stays ``code``.
* ``stationed_unit_id``: a vehicle sent as reinforcement waits at another unit (its host) and is proposed from there;
  the host's gouvernorat reads it while it is there.
* ``ops.vehicle_event``: the log of the operational state set by the rooms, the maintenance and the decommissioning
  set by the maintenance department, and the repositioning decisions with the population they cover.
* ``access.feature_profile`` (Yamen 2026-11-11): a named set of dashboard pages, each read only or read and write,
  that the system administrator grants in one go to an account (the inspector general) or a role. Granting it writes
  the usual ``access.feature_rule`` rows, tied by ``profile_assignment_id`` so they are revoked together. Three
  read-only profiles are seeded: the fleet, the personnel, the inspections.

Revision ID: 0103_fleet
Revises: 0102_inspections
Create Date: 2026-11-11
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0103_fleet"
down_revision: str | None = "0102_inspections"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RESOURCE_VISIBLE = """
        EXISTS (SELECT 1 FROM ops.unit u WHERE u.id = unit_id)
        OR EXISTS (SELECT 1 FROM ops.assignment a WHERE a.resource_id = id)
        OR EXISTS (SELECT 1 FROM ops.resource_request q WHERE q.resource_id = id)"""
_HOSTED = "\n        OR EXISTS (SELECT 1 FROM ops.unit h WHERE h.id = stationed_unit_id)"
_SCOPED = "ehimaya.scope() <> 'none'"
_UNIT_VISIBLE = "ehimaya.sees_all() OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat())"


def _resource_policies(visible: str) -> str:
    return f"""
DROP POLICY resource_select ON ops.resource;
DROP POLICY resource_update ON ops.resource;
DROP POLICY resource_delete ON ops.resource;
CREATE POLICY resource_select ON ops.resource FOR SELECT USING ({visible});
CREATE POLICY resource_update ON ops.resource FOR UPDATE USING ({visible}) WITH CHECK ({_SCOPED});
CREATE POLICY resource_delete ON ops.resource FOR DELETE USING ({visible});
"""


_FLEET = r"""
ALTER TABLE ops.resource
    ADD COLUMN plate             text CHECK (char_length(plate) <= 20),
    ADD COLUMN odometer_km       integer CHECK (odometer_km BETWEEN 0 AND 5000000),
    ADD COLUMN acquired_on       date,
    ADD COLUMN stationed_unit_id uuid REFERENCES ops.unit(id),
    ADD COLUMN stationed_since   timestamptz,
    ADD COLUMN fault             text CHECK (char_length(fault) <= 500),
    ADD COLUMN workshop          text CHECK (char_length(workshop) <= 200),
    ADD COLUMN maint_reason      text CHECK (char_length(maint_reason) <= 500),
    ADD COLUMN maint_since       timestamptz,
    ADD COLUMN maint_until       date,
    ADD COLUMN retired_on        date,
    ADD COLUMN retire_decision   text CHECK (char_length(retire_decision) <= 80),
    ADD COLUMN retire_reason     text CHECK (char_length(retire_reason) <= 500),
    ADD CONSTRAINT ck_resource_stationed CHECK ((stationed_unit_id IS NULL) = (stationed_since IS NULL)),
    ADD CONSTRAINT ck_resource_retired CHECK ((out_reason = 'retired') = (retired_on IS NOT NULL));
ALTER TABLE ops.resource DROP CONSTRAINT resource_out_reason_check;
ALTER TABLE ops.resource ADD CONSTRAINT resource_out_reason_check
    CHECK (out_reason IN ('maintenance', 'broken', 'retired'));
CREATE UNIQUE INDEX ux_resource_plate ON ops.resource (plate) WHERE plate IS NOT NULL;
CREATE INDEX ix_resource_stationed ON ops.resource (stationed_unit_id) WHERE stationed_unit_id IS NOT NULL;

CREATE TABLE ops.vehicle_event (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_id           uuid NOT NULL REFERENCES ops.resource(id) ON DELETE CASCADE,
    gouvernorat_code      smallint NOT NULL REFERENCES geo.gouvernorat(code),
    host_gouvernorat_code smallint REFERENCES geo.gouvernorat(code),
    kind                  text NOT NULL CHECK (kind IN ('state', 'maintenance_start', 'maintenance_end', 'retire',
                                                         'reinforce', 'reinforce_end')),
    from_state            text NOT NULL,
    to_state              text NOT NULL,
    details               jsonb NOT NULL DEFAULT '{}',
    created_by            text NOT NULL,
    created_by_name       text CHECK (char_length(created_by_name) <= 200),
    created_at            timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_vehicle_event_resource ON ops.vehicle_event (resource_id, created_at DESC);
CREATE INDEX ix_vehicle_event_gouvernorat ON ops.vehicle_event (gouvernorat_code, created_at DESC);

ALTER TABLE ops.vehicle_event ENABLE ROW LEVEL SECURITY;
CREATE POLICY vehicle_event_select ON ops.vehicle_event FOR SELECT USING (
    ehimaya.sees_all() OR (ehimaya.regional() AND ehimaya.gouvernorat() IN (gouvernorat_code, host_gouvernorat_code)));
CREATE POLICY vehicle_event_insert ON ops.vehicle_event FOR INSERT WITH CHECK (
    ehimaya.sees_all() OR (ehimaya.regional() AND ehimaya.gouvernorat() IN (gouvernorat_code, host_gouvernorat_code)));
CREATE POLICY vehicle_event_update ON ops.vehicle_event FOR UPDATE
    USING (ehimaya.scope() = 'system') WITH CHECK (ehimaya.scope() = 'system');
CREATE POLICY vehicle_event_delete ON ops.vehicle_event FOR DELETE USING (ehimaya.scope() = 'system');
"""


def _unit_policy(extra: str) -> str:
    return f"""
DROP POLICY unit_select ON ops.unit;
CREATE POLICY unit_select ON ops.unit FOR SELECT USING ({_UNIT_VISIBLE}{extra});
"""


_HOSTS = r"""
-- The room of the unit where a vehicle waits as reinforcement reads the vehicle's own unit (its name, where it comes
-- from). Owner rights: the resource policy refers back to the unit, which a policy cannot do on its own (recursion).
CREATE FUNCTION ehimaya.hosts_from(p_unit uuid) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
    SELECT ehimaya.regional() AND EXISTS (
        SELECT 1 FROM ops.resource r JOIN ops.unit h ON h.id = r.stationed_unit_id
        WHERE r.unit_id = p_unit AND h.gouvernorat_code = ehimaya.gouvernorat()) $$;
REVOKE ALL ON FUNCTION ehimaya.hosts_from(uuid) FROM PUBLIC;
"""

_PROFILES = r"""
CREATE TABLE access.feature_profile (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name            text NOT NULL UNIQUE CHECK (length(name) BETWEEN 3 AND 120),
    description     text CHECK (char_length(description) <= 500),
    items           jsonb NOT NULL DEFAULT '[]',
    builtin         boolean NOT NULL DEFAULT false,
    created_by      text NOT NULL,
    created_by_name text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_by_name text,
    updated_at      timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE access.feature_profile ENABLE ROW LEVEL SECURITY;
CREATE POLICY feature_profile_system ON access.feature_profile
    USING (ehimaya.scope() = 'system') WITH CHECK (ehimaya.scope() = 'system');

ALTER TABLE access.feature_rule
    ADD COLUMN profile_id            uuid REFERENCES access.feature_profile(id) ON DELETE SET NULL,
    ADD COLUMN profile_assignment_id uuid;
CREATE INDEX ix_feature_rule_assignment ON access.feature_rule (profile_assignment_id)
    WHERE profile_assignment_id IS NOT NULL;

INSERT INTO access.feature_profile (name, description, items, builtin, created_by, created_by_name) VALUES
    ('اطلاع على الوسائل', 'الأسطول والأعطاب والصيانة والأرشيف، دون تصرف',
     '[{"page": "fleet", "mode": "read"}]', true, 'system', 'e-Himaya'),
    ('اطلاع على الأفراد', 'قائمة الأعوان والغيابات والموجود العام، دون تصرف',
     '[{"page": "personnel", "mode": "read"}]', true, 'system', 'e-Himaya'),
    ('اطلاع على التفقديات', 'المهمات والمحاضر والحسابات، دون تصرف',
     '[{"page": "inspections", "mode": "read"}]', true, 'system', 'e-Himaya');

-- The change journal (migration 0097), like every table of its schema.
SELECT audit.journal_attach('ops.vehicle_event'::regclass, false);
SELECT audit.journal_attach('access.feature_profile'::regclass, true);
"""

UPGRADE = "".join(
    (
        _FLEET,
        _resource_policies(_RESOURCE_VISIBLE + _HOSTED),
        _HOSTS,
        _unit_policy(" OR ehimaya.hosts_from(id)"),
        _PROFILES,
    )
)

_UNDO = r"""
DROP FUNCTION ehimaya.hosts_from(uuid);
"""

_UNDO_FLEET = r"""
ALTER TABLE access.feature_rule DROP COLUMN profile_assignment_id, DROP COLUMN profile_id;
DROP TABLE access.feature_profile;
DROP TABLE ops.vehicle_event;
ALTER TABLE ops.resource DROP CONSTRAINT ck_resource_retired;
UPDATE ops.resource SET out_reason = 'broken' WHERE out_reason = 'retired';
ALTER TABLE ops.resource DROP CONSTRAINT resource_out_reason_check;
ALTER TABLE ops.resource ADD CONSTRAINT resource_out_reason_check CHECK (out_reason IN ('maintenance', 'broken'));
ALTER TABLE ops.resource
    DROP CONSTRAINT ck_resource_stationed,
    DROP COLUMN plate,
    DROP COLUMN odometer_km,
    DROP COLUMN acquired_on,
    DROP COLUMN stationed_unit_id,
    DROP COLUMN stationed_since,
    DROP COLUMN fault,
    DROP COLUMN workshop,
    DROP COLUMN maint_reason,
    DROP COLUMN maint_since,
    DROP COLUMN maint_until,
    DROP COLUMN retired_on,
    DROP COLUMN retire_decision,
    DROP COLUMN retire_reason;
"""

DOWNGRADE = "".join((_unit_policy(""), _UNDO, _resource_policies(_RESOURCE_VISIBLE), _UNDO_FLEET))


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
