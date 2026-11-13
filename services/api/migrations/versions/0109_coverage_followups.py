"""Follow-ups of the live coverage and the fleet (OS3-1 to OS3-4, Yamen 2026-11-13; docs/phase-os3/design-os3b.md).

* ``ops.reposition_order``: the order a room's repositioning sends to the crew holding the vehicle on the staff app
  (OS3-1): to a host unit as reinforcement, or back to its own unit. The crew says it saw the order, left and arrived;
  the room follows each step. A newer order, a breakdown, the workshop or the decommissioning closes an open one.
  Read by the rooms of the vehicle's gouvernorat and of the other end of the move, like ``ops.vehicle_event``.
* ``ops.vehicle_event`` gains the cost of a stay in the workshop (OS3-3): its kind (repair, periodic, accident),
  parts, labour and outside workshop in dinars (three decimals, millimes), the invoice or order number, and who
  entered the cost and when (at the exit, or later when the invoice arrives).

Revision ID: 0109_coverage_followups
Revises: 0108_feature_systems
Create Date: 2026-11-13
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0109_coverage_followups"
down_revision: str | None = "0108_feature_systems"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCOPE = (
    "ehimaya.sees_all() OR (ehimaya.regional() AND ehimaya.gouvernorat() IN (gouvernorat_code, host_gouvernorat_code))"
)

UPGRADE = f"""
CREATE TABLE ops.reposition_order (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_id           uuid NOT NULL REFERENCES ops.resource(id) ON DELETE CASCADE,
    vehicle_event_id      uuid REFERENCES ops.vehicle_event(id) ON DELETE SET NULL,
    kind                  text NOT NULL CHECK (kind IN ('reinforce', 'return')),
    from_unit_id          uuid NOT NULL REFERENCES ops.unit(id) ON DELETE CASCADE,
    to_unit_id            uuid NOT NULL REFERENCES ops.unit(id) ON DELETE CASCADE,
    gouvernorat_code      smallint NOT NULL REFERENCES geo.gouvernorat(code),
    host_gouvernorat_code smallint REFERENCES geo.gouvernorat(code),
    note                  text CHECK (char_length(note) <= 500),
    gain_population       integer CHECK (gain_population >= 0),
    shift_id              uuid REFERENCES ops.shift(id) ON DELETE SET NULL,
    leader_name           text CHECK (char_length(leader_name) <= 200),
    pushed                boolean NOT NULL DEFAULT false,
    created_by            text NOT NULL,
    created_by_name       text CHECK (char_length(created_by_name) <= 200),
    created_at            timestamptz NOT NULL DEFAULT now(),
    seen_at               timestamptz,
    seen_by_name          text CHECK (char_length(seen_by_name) <= 200),
    departed_at           timestamptz,
    arrived_at            timestamptz,
    closed_at             timestamptz,
    close_reason          text CHECK (close_reason IN ('replaced', 'state', 'maintenance', 'retired')),
    CONSTRAINT ck_reposition_units CHECK (from_unit_id <> to_unit_id),
    CONSTRAINT ck_reposition_closed CHECK ((closed_at IS NULL) = (close_reason IS NULL)),
    CONSTRAINT ck_reposition_steps CHECK (
        (departed_at IS NULL OR seen_at IS NOT NULL) AND (arrived_at IS NULL OR departed_at IS NOT NULL))
);
CREATE INDEX ix_reposition_order_resource ON ops.reposition_order (resource_id, created_at DESC);
CREATE INDEX ix_reposition_order_gouvernorat ON ops.reposition_order (gouvernorat_code, created_at DESC);
CREATE INDEX ix_reposition_order_open ON ops.reposition_order (resource_id)
    WHERE arrived_at IS NULL AND closed_at IS NULL;
ALTER TABLE ops.reposition_order ENABLE ROW LEVEL SECURITY;
CREATE POLICY reposition_order_select ON ops.reposition_order FOR SELECT USING ({_SCOPE});
CREATE POLICY reposition_order_insert ON ops.reposition_order FOR INSERT WITH CHECK ({_SCOPE});
CREATE POLICY reposition_order_update ON ops.reposition_order FOR UPDATE USING ({_SCOPE}) WITH CHECK ({_SCOPE});
CREATE POLICY reposition_order_delete ON ops.reposition_order FOR DELETE USING (ehimaya.scope() = 'system');

ALTER TABLE ops.vehicle_event
    ADD COLUMN maint_kind    text CHECK (maint_kind IN ('repair', 'periodic', 'accident')),
    ADD COLUMN cost_parts    numeric(12, 3) CHECK (cost_parts >= 0),
    ADD COLUMN cost_labour   numeric(12, 3) CHECK (cost_labour >= 0),
    ADD COLUMN cost_external numeric(12, 3) CHECK (cost_external >= 0),
    ADD COLUMN invoice_ref   text CHECK (char_length(invoice_ref) <= 60),
    ADD COLUMN cost_by_name  text CHECK (char_length(cost_by_name) <= 200),
    ADD COLUMN cost_at       timestamptz,
    ADD CONSTRAINT ck_vehicle_event_cost CHECK (
        kind = 'maintenance_end' OR (maint_kind IS NULL AND cost_parts IS NULL AND cost_labour IS NULL
                                     AND cost_external IS NULL AND invoice_ref IS NULL));

-- The change journal (migration 0097), like every table of its schema.
SELECT audit.journal_attach('ops.reposition_order'::regclass, false);
"""

DOWNGRADE = """
ALTER TABLE ops.vehicle_event
    DROP CONSTRAINT ck_vehicle_event_cost,
    DROP COLUMN maint_kind,
    DROP COLUMN cost_parts,
    DROP COLUMN cost_labour,
    DROP COLUMN cost_external,
    DROP COLUMN invoice_ref,
    DROP COLUMN cost_by_name,
    DROP COLUMN cost_at;
DROP TABLE ops.reposition_order;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
