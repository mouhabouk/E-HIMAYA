"""Incidents across gouvernorats (phase 9, docs/api/phase-9-contract.md §5).

* ``ops.incident.gouvernorat_code`` now means the **lead** gouvernorat: it is fixed at creation and changed only by an
  audited transfer (the phase 3 majority recompute is gone). New columns: who set the lead and when, the command level
  (``regional`` | ``central``), its reason and whether it was set by hand.
* ``ops.incident_gouvernorat`` — the lead and the participating gouvernorats of an incident. A trigger keeps the lead
  row in sync with ``incident.gouvernorat_code`` (the previous lead stays as participating), so no code path can leave
  the two apart; a partial unique index allows one lead row per incident.
* ``ops.resource_request`` — a room asks the gouvernorat owning a resource (or a kind of resource) to engage it on an
  incident; the owning region (or central command at central level) approves or refuses. ``ops.assignment.request_id``
  links the assignments an approval created.

Backfill (§9.4): a lead row from ``gouvernorat_code``; participating rows from the distinct gouvernorats of member
reports other than the lead; the command level computed by the §5.3 rule (severity at or above the critical band,
a participating gouvernorat, the lead at crisis or disaster level, or no lead at all → ``central``).

Revision ID: 0021_ops_multi_gouvernorat
Revises: 0020_reports_jurisdiction
Create Date: 2026-10-20
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0021_ops_multi_gouvernorat"
down_revision: str | None = "0020_reports_jurisdiction"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE = r"""
ALTER TABLE ops.incident
    ADD COLUMN lead_set_by text,
    ADD COLUMN lead_set_at timestamptz,
    ADD COLUMN command_level text NOT NULL DEFAULT 'regional',
    ADD COLUMN command_level_reason text,
    ADD COLUMN command_level_manual boolean NOT NULL DEFAULT false,
    ADD CONSTRAINT ck_incident_command_level CHECK (command_level IN ('regional', 'central'));

CREATE TABLE ops.incident_gouvernorat (
    incident_id       uuid NOT NULL REFERENCES ops.incident(id) ON DELETE CASCADE,
    gouvernorat_code  smallint NOT NULL REFERENCES geo.gouvernorat(code),
    role              text NOT NULL,
    added_at          timestamptz NOT NULL DEFAULT now(),
    added_by          text,
    reason            text,
    CONSTRAINT pk_incident_gouvernorat PRIMARY KEY (incident_id, gouvernorat_code),
    CONSTRAINT ck_incident_gouvernorat_role CHECK (role IN ('lead', 'participating'))
);
CREATE UNIQUE INDEX ux_incident_gouvernorat_lead ON ops.incident_gouvernorat (incident_id) WHERE role = 'lead';
CREATE INDEX ix_incident_gouvernorat_code ON ops.incident_gouvernorat (gouvernorat_code, incident_id);

-- The lead row follows incident.gouvernorat_code; the previous lead keeps participating.
CREATE FUNCTION ops.sync_incident_lead() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND NEW.gouvernorat_code IS NOT DISTINCT FROM OLD.gouvernorat_code THEN
        RETURN NEW;
    END IF;
    UPDATE ops.incident_gouvernorat SET role = 'participating'
     WHERE incident_id = NEW.id AND role = 'lead' AND gouvernorat_code IS DISTINCT FROM NEW.gouvernorat_code;
    IF NEW.gouvernorat_code IS NOT NULL THEN
        INSERT INTO ops.incident_gouvernorat (incident_id, gouvernorat_code, role, added_by, reason)
        VALUES (NEW.id, NEW.gouvernorat_code, 'lead', coalesce(NEW.lead_set_by, 'system'), 'lead')
        ON CONFLICT (incident_id, gouvernorat_code) DO UPDATE SET role = 'lead';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER trg_incident_lead AFTER INSERT OR UPDATE OF gouvernorat_code ON ops.incident
    FOR EACH ROW EXECUTE FUNCTION ops.sync_incident_lead();

CREATE TABLE ops.resource_request (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id          uuid NOT NULL REFERENCES ops.incident(id) ON DELETE CASCADE,
    from_room            text NOT NULL,
    to_gouvernorat_code  smallint NOT NULL REFERENCES geo.gouvernorat(code),
    resource_id          uuid REFERENCES ops.resource(id) ON DELETE SET NULL,
    resource_kind        text NOT NULL,
    quantity             smallint NOT NULL DEFAULT 1,
    reason               text NOT NULL,
    status               text NOT NULL DEFAULT 'pending',
    requested_by         text NOT NULL,
    requested_by_name    text,
    requested_at         timestamptz NOT NULL DEFAULT now(),
    decided_by           text,
    decided_by_name      text,
    decided_at           timestamptz,
    decision_note        text,
    CONSTRAINT ck_resource_request_room CHECK (from_room ~ '^(central|g:[0-9]{1,2})$'),
    CONSTRAINT ck_resource_request_quantity CHECK (quantity BETWEEN 1 AND 50),
    CONSTRAINT ck_resource_request_reason CHECK (char_length(reason) BETWEEN 5 AND 500),
    CONSTRAINT ck_resource_request_status CHECK (status IN ('pending', 'approved', 'refused', 'cancelled')),
    CONSTRAINT ck_resource_request_decided CHECK ((status = 'pending') = (decided_at IS NULL))
);
CREATE INDEX ix_resource_request_incoming ON ops.resource_request (to_gouvernorat_code, requested_at DESC, id DESC);
CREATE INDEX ix_resource_request_outgoing ON ops.resource_request (from_room, requested_at DESC, id DESC);
CREATE INDEX ix_resource_request_incident ON ops.resource_request (incident_id, requested_at);

ALTER TABLE ops.assignment ADD COLUMN request_id uuid REFERENCES ops.resource_request(id) ON DELETE SET NULL;
CREATE INDEX ix_assignment_request ON ops.assignment (request_id) WHERE request_id IS NOT NULL;

-- ===================== backfill (§9.4)
INSERT INTO ops.incident_gouvernorat (incident_id, gouvernorat_code, role, added_at, added_by, reason)
SELECT i.id, i.gouvernorat_code, 'lead', i.opened_at, 'system:migration', 'backfill'
FROM ops.incident i WHERE i.gouvernorat_code IS NOT NULL;

INSERT INTO ops.incident_gouvernorat (incident_id, gouvernorat_code, role, added_at, added_by, reason)
SELECT DISTINCT r.incident_id, r.gouvernorat_code, 'participating', i.opened_at, 'system:migration', 'report_linked'
FROM reports.report r JOIN ops.incident i ON i.id = r.incident_id
WHERE r.gouvernorat_code IS NOT NULL AND r.gouvernorat_code IS DISTINCT FROM i.gouvernorat_code;

UPDATE ops.incident i SET command_level = 'central', command_level_reason = 'backfill'
WHERE i.gouvernorat_code IS NULL
   OR i.severity >= coalesce(
        (SELECT CAST(s.value ->> 'critical' AS integer) FROM platform.setting s WHERE s.key = 'sla.bands'), 85)
   OR EXISTS (SELECT 1 FROM ops.incident_gouvernorat g WHERE g.incident_id = i.id AND g.role = 'participating')
   OR EXISTS (SELECT 1 FROM ops.level_state l
              WHERE l.gouvernorat_code = i.gouvernorat_code AND l.level IN ('crisis', 'disaster'));
"""


DOWNGRADE = r"""
DROP INDEX ops.ix_assignment_request;
ALTER TABLE ops.assignment DROP COLUMN request_id;
DROP TABLE ops.resource_request;
DROP TRIGGER trg_incident_lead ON ops.incident;
DROP FUNCTION ops.sync_incident_lead();
DROP TABLE ops.incident_gouvernorat;
ALTER TABLE ops.incident
    DROP CONSTRAINT ck_incident_command_level,
    DROP COLUMN command_level_manual,
    DROP COLUMN command_level_reason,
    DROP COLUMN command_level,
    DROP COLUMN lead_set_at,
    DROP COLUMN lead_set_by;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
