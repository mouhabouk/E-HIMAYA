"""Resources register, R3 (Yamen, 2026-10-28): the transfer of a member of staff from one gouvernorat to another,
more types (light vehicles, trucks, pick-ups, hydraulic spreaders), equipment carried by a vehicle, and more statuses
of a member of staff.

* ``inv.category``: new vehicle and equipment types. The catalogue stays the central room's: it can add others.
* ``inv.stock.vehicle_id``: equipment carried by one vehicle (a pump, a spreader on a rescue truck), in its unit.
* ``inv.agent.availability``: on duty, rest, leave, and now sick leave, training and mission.
* ``inv.transfer``: the transfer of a member of staff between gouvernorats, sent by the room of the gouvernorat they
  leave and accepted (with their new unit) or refused by the room of the gouvernorat they join. Both rooms see it.

Revision ID: 0067_inventory_r3
Revises: 0066_drill
Create Date: 2026-10-28
"""

import json
from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0067_inventory_r3"
down_revision: str | None = "0066_drill"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FOUR_WD = {
    "key": "four_wd",
    "unit": "",
    "type": "bool",
    "name": {"ar": "دفع رباعي", "fr": "4x4", "en": "Four-wheel drive"},
}
SEATS = {"key": "seats", "unit": "", "type": "number", "name": {"ar": "عدد الأشخاص", "fr": "Places", "en": "Seats"}}
PAYLOAD = {
    "key": "payload_t",
    "unit": "t",
    "type": "number",
    "name": {"ar": "الحمولة", "fr": "Charge utile", "en": "Payload"},
}
FORCE = {"key": "force_kn", "unit": "kN", "type": "number", "name": {"ar": "قوة الفتح", "fr": "Force", "en": "Force"}}

NEW = (
    ("light_vehicle", "vehicle", "vehicles", "سيارة خفيفة", "Véhicule léger", "Light vehicle", [SEATS, FOUR_WD]),
    ("pickup", "vehicle", "vehicles", "شاحنة خفيفة (بيك آب)", "Pick-up", "Pick-up", [SEATS, FOUR_WD]),
    ("truck", "vehicle", "vehicles", "شاحنة", "Camion", "Truck", [PAYLOAD, FOUR_WD]),
    ("motorcycle", "vehicle", "vehicles", "دراجة نارية", "Moto", "Motorcycle", []),
    (
        "hydraulic_spreader",
        "equipment",
        "equipment",
        "فك هيدروليكي",
        "Écarteur hydraulique",
        "Hydraulic spreader",
        [FORCE],
    ),
    ("hydraulic_ram", "equipment", "equipment", "دافع هيدروليكي", "Vérin hydraulique", "Hydraulic ram", [FORCE]),
    ("chainsaw", "equipment", "equipment", "منشار آلي", "Tronçonneuse", "Chainsaw", []),
)


def _q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


_ROWS = ",\n".join(
    f"({_q(k)}, {_q(kind)}, {_q(family)}, "
    f"{_q(json.dumps({'ar': ar, 'fr': fr, 'en': en}, ensure_ascii=False))}::jsonb, "
    f"{_q(json.dumps(specs, ensure_ascii=False))}::jsonb, 0, {100 + i})"
    for i, (k, kind, family, ar, fr, en, specs) in enumerate(NEW)
)
_KEYS = ", ".join(_q(k) for k, *_ in NEW)
_OWN_SIDE = "ehimaya.sees_all() OR (ehimaya.regional() AND ehimaya.gouvernorat() IN (from_gouvernorat, to_gouvernorat))"

UPGRADE = rf"""
INSERT INTO inv.category (key, kind, family, name, specs, levels, position) VALUES
{_ROWS}
ON CONFLICT (key) DO NOTHING;

ALTER TABLE inv.stock ADD COLUMN vehicle_id uuid REFERENCES ops.resource(id) ON DELETE SET NULL;
ALTER TABLE inv.stock DROP CONSTRAINT uq_stock;
CREATE UNIQUE INDEX uq_stock ON inv.stock (unit_id, category_key, specs,
    coalesce(vehicle_id, '00000000-0000-0000-0000-000000000000'::uuid));
CREATE INDEX ix_stock_vehicle ON inv.stock (vehicle_id) WHERE vehicle_id IS NOT NULL;

ALTER TABLE inv.agent DROP CONSTRAINT agent_availability_check;
ALTER TABLE inv.agent ADD CONSTRAINT agent_availability_check
    CHECK (availability IN ('on_duty', 'rest', 'leave', 'sick', 'training', 'mission'));

ALTER TABLE inv.revision DROP CONSTRAINT revision_action_check;
ALTER TABLE inv.revision ADD CONSTRAINT revision_action_check
    CHECK (action IN ('create', 'update', 'delete', 'import', 'transfer_out', 'transfer_in'));

CREATE TABLE inv.transfer (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id          uuid NOT NULL REFERENCES inv.agent(id) ON DELETE CASCADE,
    from_gouvernorat  smallint NOT NULL REFERENCES geo.gouvernorat(code),
    from_unit_id      uuid NOT NULL REFERENCES ops.unit(id),
    to_gouvernorat    smallint NOT NULL REFERENCES geo.gouvernorat(code),
    to_unit_id        uuid REFERENCES ops.unit(id),
    effective_on      date,
    status            text NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending', 'accepted', 'refused', 'cancelled')),
    reason            text NOT NULL CHECK (char_length(reason) BETWEEN 5 AND 500),
    decision_reason   text CHECK (char_length(decision_reason) <= 500),
    requested_by      text NOT NULL,
    requested_by_name text,
    requested_at      timestamptz NOT NULL DEFAULT now(),
    decided_by_name   text,
    decided_at        timestamptz,
    CONSTRAINT ck_transfer_other CHECK (from_gouvernorat <> to_gouvernorat),
    CONSTRAINT ck_transfer_unit CHECK ((status = 'accepted') = (to_unit_id IS NOT NULL))
);
CREATE UNIQUE INDEX uq_transfer_pending ON inv.transfer (agent_id) WHERE status = 'pending';
CREATE INDEX ix_transfer_sides ON inv.transfer (to_gouvernorat, status, from_gouvernorat);

ALTER TABLE inv.transfer ENABLE ROW LEVEL SECURITY;
CREATE POLICY transfer_all ON inv.transfer USING ({_OWN_SIDE}) WITH CHECK ({_OWN_SIDE});
"""  # noqa: S608 (constant SQL fragments, nothing is interpolated from input)

DOWNGRADE = f"""
DROP TABLE inv.transfer;
DELETE FROM inv.revision WHERE action IN ('transfer_out', 'transfer_in');
ALTER TABLE inv.revision DROP CONSTRAINT revision_action_check;
ALTER TABLE inv.revision ADD CONSTRAINT revision_action_check
    CHECK (action IN ('create', 'update', 'delete', 'import'));
UPDATE inv.agent SET availability = 'leave' WHERE availability IN ('sick', 'training', 'mission');
ALTER TABLE inv.agent DROP CONSTRAINT agent_availability_check;
ALTER TABLE inv.agent ADD CONSTRAINT agent_availability_check CHECK (availability IN ('on_duty', 'rest', 'leave'));
DROP INDEX inv.ix_stock_vehicle;
DROP INDEX inv.uq_stock;
DELETE FROM inv.stock s WHERE s.vehicle_id IS NOT NULL AND EXISTS (
    SELECT 1 FROM inv.stock t WHERE t.id <> s.id AND t.unit_id = s.unit_id AND t.category_key = s.category_key
    AND t.specs = s.specs AND (t.vehicle_id IS NULL OR t.id < s.id));
ALTER TABLE inv.stock DROP COLUMN vehicle_id;
ALTER TABLE inv.stock ADD CONSTRAINT uq_stock UNIQUE (unit_id, category_key, specs);
UPDATE ops.resource SET category_key = NULL WHERE category_key IN ({_KEYS});
DELETE FROM inv.stock WHERE category_key IN ({_KEYS});
DELETE FROM inv.category WHERE key IN ({_KEYS});
"""  # noqa: S608


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
