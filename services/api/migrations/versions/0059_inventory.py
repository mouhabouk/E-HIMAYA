"""Resources register of every gouvernorat (phase R1, docs/phase-r/design-resources.md §2.1, §2.2, §2.5).

* ``inv.category``: the national catalogue. Vehicle and equipment types with their technical specifications (a fire
  engine's capacity in litres, a ladder's length) and the staff specialities with their levels (diving 1 to 3). The
  central room keeps it; a type is never deleted, only switched off.
* ``ops.resource`` (the vehicles assignable since phase 4) gains its catalogue type, specifications, internal number,
  year and the reason it is out of service (maintenance or broken).
* ``inv.stock``: equipment counted by quantity in a unit (5 pumps, 1 of them broken).
* ``inv.agent`` and ``inv.agent_skill``: the staff of a unit, their rank, availability and specialities with the
  expiry of their certificate. Names and phones are personal data: the API returns them to the operations rooms only.
* ``inv.revision``: every change with its reason; ``inv.unit_check``: when a unit's figures were last confirmed.

Row level security: a regional room sees and changes its own gouvernorat only, the central room every one.

Revision ID: 0059_inventory
Revises: 0058_layer_groups
Create Date: 2026-10-28
"""

import json
from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0059_inventory"
down_revision: str | None = "0058_layer_groups"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ALL = "ehimaya.sees_all()"
_OWN = "ehimaya.sees_all() OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat())"


def _spec(key: str, unit: str, ar: str, fr: str, en: str, kind: str = "number") -> dict[str, object]:
    return {"key": key, "unit": unit, "type": kind, "name": {"ar": ar, "fr": fr, "en": en}}


CAPACITY = _spec("capacity_l", "L", "السعة", "Capacité", "Capacity")
FLOW = _spec("flow_lpm", "L/min", "الصبيب", "Débit", "Flow")
FOUR_WD = _spec("four_wd", "", "دفع رباعي", "4x4", "Four-wheel drive", "bool")
LENGTH = _spec("length_m", "m", "الطول", "Longueur", "Length")
SEATS = _spec("seats", "", "عدد الأشخاص", "Places", "Seats")
POWER = _spec("power_kva", "kVA", "القدرة", "Puissance", "Power")

# key, kind, family, Arabic, French, English, specifications, levels
CATALOGUE: tuple[tuple[str, str, str | None, str, str, str, list[dict[str, object]], int], ...] = (
    (
        "fire_engine",
        "vehicle",
        "vehicles",
        "شاحنة إطفاء",
        "Camion d'incendie",
        "Fire engine",
        [CAPACITY, FLOW, FOUR_WD],
        0,
    ),
    ("water_tanker", "vehicle", "vehicles", "صهريج ماء", "Camion-citerne", "Water tanker", [CAPACITY, FOUR_WD], 0),
    ("aerial_ladder", "vehicle", "vehicles", "سلّم آلي", "Échelle aérienne", "Aerial ladder", [LENGTH], 0),
    ("ambulance", "vehicle", "vehicles", "سيارة إسعاف", "Ambulance", "Ambulance", [], 0),
    ("rescue_vehicle", "vehicle", "vehicles", "شاحنة إنقاذ", "Véhicule de secours", "Rescue vehicle", [FOUR_WD], 0),
    ("hazmat_vehicle", "vehicle", "vehicles", "شاحنة مواد خطرة", "Véhicule risques chimiques", "Hazmat vehicle", [], 0),
    ("command_vehicle", "vehicle", "vehicles", "سيارة قيادة", "Véhicule de commandement", "Command vehicle", [], 0),
    ("heavy_equipment", "vehicle", "vehicles", "آلية ثقيلة", "Engin lourd", "Heavy equipment", [], 0),
    (
        "large_extinguisher",
        "vehicle",
        "vehicles",
        "مطفأة كبيرة",
        "Grand extincteur",
        "Large extinguisher",
        [CAPACITY],
        0,
    ),
    ("boat", "vehicle", "boats", "زورق", "Embarcation", "Boat", [LENGTH, SEATS], 0),
    ("drone", "vehicle", "air", "طائرة مسيّرة", "Drone", "Drone", [], 0),
    ("pump", "equipment", "equipment", "مضخة", "Motopompe", "Pump", [FLOW], 0),
    ("generator", "equipment", "equipment", "مولد كهربائي", "Groupe électrogène", "Generator", [POWER], 0),
    ("lighting_tower", "equipment", "equipment", "برج إنارة", "Mât d'éclairage", "Lighting tower", [], 0),
    ("hydraulic_cutter", "equipment", "equipment", "مقص هيدروليكي", "Cisaille hydraulique", "Hydraulic cutter", [], 0),
    ("tent", "equipment", "equipment", "خيمة", "Tente", "Tent", [SEATS], 0),
    (
        "inflatable_boat",
        "equipment",
        "boats",
        "زورق مطاطي",
        "Bateau pneumatique",
        "Inflatable boat",
        [LENGTH, SEATS],
        0,
    ),
    ("diving_kit", "equipment", "ppe", "عدة غوص", "Équipement de plongée", "Diving kit", [], 0),
    ("breathing_apparatus", "equipment", "ppe", "جهاز تنفس", "Appareil respiratoire", "Breathing apparatus", [], 0),
    ("diving", "skill", None, "غوص", "Plongée", "Diving", [], 3),
    ("rope_rescue", "skill", None, "إنقاذ بالحبال", "Sauvetage sur cordes", "Rope rescue", [], 0),
    ("high_angle", "skill", None, "الإنقاذ في الأماكن المرتفعة", "Sauvetage en hauteur", "High-angle rescue", [], 0),
    ("hazmat", "skill", None, "المواد الخطرة (NRBC)", "Risques NRBC", "Hazmat (CBRN)", [], 2),
    ("advanced_first_aid", "skill", None, "الإسعاف المتقدم", "Secours avancés", "Advanced first aid", [], 0),
    ("usar", "skill", None, "الإنقاذ تحت الأنقاض", "Sauvetage-déblaiement", "Urban search and rescue", [], 2),
    ("swift_water", "skill", None, "الإنقاذ في المياه الجارية", "Sauvetage en eaux vives", "Swift-water rescue", [], 0),
    ("heavy_driver", "skill", None, "سائق وزن ثقيل", "Conducteur poids lourd", "Heavy vehicle driver", [], 0),
    ("drone_pilot", "skill", None, "مشغّل طائرة مسيّرة", "Télépilote de drone", "Drone pilot", [], 0),
    ("k9", "skill", None, "فريق الكلاب", "Équipe cynotechnique", "K9 team", [], 0),
)

# The vehicle kinds of phase 4 and their catalogue type.
FROM_KIND = {
    "fire_engine": "fire_engine",
    "water_tanker": "water_tanker",
    "ambulance": "ambulance",
    "rescue_vehicle": "rescue_vehicle",
    "heavy_equipment": "heavy_equipment",
    "drone": "drone",
    "large_extinguisher": "large_extinguisher",
    "boat": "boat",
    "command_vehicle": "command_vehicle",
}


def _q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


_ROWS = ",\n".join(
    f"({_q(k)}, {_q(kind)}, {_q(family) if family else 'NULL'}, "
    f"{_q(json.dumps({'ar': ar, 'fr': fr, 'en': en}, ensure_ascii=False))}::jsonb, "
    f"{_q(json.dumps(specs, ensure_ascii=False))}::jsonb, {levels}, {i + 1})"
    for i, (k, kind, family, ar, fr, en, specs, levels) in enumerate(CATALOGUE)
)
_KINDS = "\n".join(f"    WHEN {_q(kind)} THEN {_q(key)}" for kind, key in FROM_KIND.items())

UPGRADE = rf"""
CREATE SCHEMA IF NOT EXISTS inv;

CREATE TABLE inv.category (
    key        text PRIMARY KEY CHECK (key ~ '^[a-z][a-z0-9_]{{1,39}}$'),
    kind       text NOT NULL CHECK (kind IN ('vehicle', 'equipment', 'skill')),
    family     text CHECK (family IN ('vehicles', 'equipment', 'boats', 'air', 'ppe')),
    name       jsonb NOT NULL,
    specs      jsonb NOT NULL DEFAULT '[]',
    levels     smallint NOT NULL DEFAULT 0 CHECK (levels BETWEEN 0 AND 5),
    position   integer NOT NULL DEFAULT 0,
    active     boolean NOT NULL DEFAULT true,
    updated_at timestamptz NOT NULL DEFAULT now(),
    updated_by text,
    CONSTRAINT ck_category_family CHECK ((kind = 'skill') = (family IS NULL))
);

INSERT INTO inv.category (key, kind, family, name, specs, levels, position) VALUES
{_ROWS};

ALTER TABLE ops.resource
    ADD COLUMN category_key text REFERENCES inv.category(key) ON UPDATE CASCADE,
    ADD COLUMN specs jsonb NOT NULL DEFAULT '{{}}',
    ADD COLUMN code text CHECK (char_length(code) <= 40),
    ADD COLUMN year smallint CHECK (year BETWEEN 1950 AND 2100),
    ADD COLUMN out_reason text CHECK (out_reason IN ('maintenance', 'broken')),
    ADD COLUMN updated_by text;
CREATE INDEX ix_resource_category ON ops.resource (category_key, status);
UPDATE ops.resource SET category_key = CASE kind
{_KINDS}
    ELSE NULL END;

CREATE TABLE inv.stock (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    unit_id          uuid NOT NULL REFERENCES ops.unit(id),
    gouvernorat_code smallint NOT NULL REFERENCES geo.gouvernorat(code),
    category_key     text NOT NULL REFERENCES inv.category(key) ON UPDATE CASCADE,
    specs            jsonb NOT NULL DEFAULT '{{}}',
    qty_ready        integer NOT NULL DEFAULT 0 CHECK (qty_ready BETWEEN 0 AND 100000),
    qty_broken       integer NOT NULL DEFAULT 0 CHECK (qty_broken BETWEEN 0 AND 100000),
    notes            text CHECK (char_length(notes) <= 500),
    version          integer NOT NULL DEFAULT 1,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    updated_by       text,
    CONSTRAINT uq_stock UNIQUE (unit_id, category_key, specs)
);
CREATE INDEX ix_stock_gouvernorat ON inv.stock (gouvernorat_code, category_key);

CREATE TABLE inv.agent (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    unit_id          uuid NOT NULL REFERENCES ops.unit(id),
    gouvernorat_code smallint NOT NULL REFERENCES geo.gouvernorat(code),
    matricule        text NOT NULL UNIQUE CHECK (char_length(matricule) BETWEEN 2 AND 30),
    full_name        text NOT NULL CHECK (char_length(full_name) BETWEEN 2 AND 120),
    rank             text CHECK (char_length(rank) <= 60),
    phone            text CHECK (char_length(phone) <= 30),
    availability     text NOT NULL DEFAULT 'on_duty' CHECK (availability IN ('on_duty', 'rest', 'leave')),
    notes            text CHECK (char_length(notes) <= 500),
    version          integer NOT NULL DEFAULT 1,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    updated_by       text
);
CREATE INDEX ix_agent_gouvernorat ON inv.agent (gouvernorat_code, unit_id);

CREATE TABLE inv.agent_skill (
    agent_id     uuid NOT NULL REFERENCES inv.agent(id) ON DELETE CASCADE,
    skill_key    text NOT NULL REFERENCES inv.category(key) ON UPDATE CASCADE,
    level        smallint NOT NULL DEFAULT 0 CHECK (level BETWEEN 0 AND 5),
    cert_expires date,
    PRIMARY KEY (agent_id, skill_key)
);
CREATE INDEX ix_agent_skill ON inv.agent_skill (skill_key, level);

CREATE TABLE inv.revision (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity           text NOT NULL CHECK (entity IN ('vehicle', 'stock', 'agent')),
    entity_id        uuid NOT NULL,
    gouvernorat_code smallint NOT NULL REFERENCES geo.gouvernorat(code),
    action           text NOT NULL CHECK (action IN ('create', 'update', 'delete', 'import')),
    snapshot         jsonb NOT NULL,
    reason           text,
    created_by       text NOT NULL,
    created_by_name  text,
    created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_revision_entity ON inv.revision (entity_id, created_at DESC);

CREATE TABLE inv.unit_check (
    unit_id          uuid PRIMARY KEY REFERENCES ops.unit(id),
    gouvernorat_code smallint NOT NULL REFERENCES geo.gouvernorat(code),
    verified_at      timestamptz NOT NULL DEFAULT now(),
    verified_by      text NOT NULL,
    verified_by_name text
);

ALTER TABLE inv.category ENABLE ROW LEVEL SECURITY;
CREATE POLICY category_select ON inv.category FOR SELECT USING (true);
CREATE POLICY category_insert ON inv.category FOR INSERT WITH CHECK ({_ALL});
CREATE POLICY category_update ON inv.category FOR UPDATE USING ({_ALL}) WITH CHECK ({_ALL});

ALTER TABLE inv.stock ENABLE ROW LEVEL SECURITY;
CREATE POLICY stock_all ON inv.stock USING ({_OWN}) WITH CHECK ({_OWN});
ALTER TABLE inv.agent ENABLE ROW LEVEL SECURITY;
CREATE POLICY agent_all ON inv.agent USING ({_OWN}) WITH CHECK ({_OWN});
ALTER TABLE inv.agent_skill ENABLE ROW LEVEL SECURITY;
CREATE POLICY agent_skill_all ON inv.agent_skill
    USING (EXISTS (SELECT 1 FROM inv.agent a WHERE a.id = agent_id))
    WITH CHECK (EXISTS (SELECT 1 FROM inv.agent a WHERE a.id = agent_id));
ALTER TABLE inv.revision ENABLE ROW LEVEL SECURITY;
CREATE POLICY revision_all ON inv.revision USING ({_OWN}) WITH CHECK ({_OWN});
ALTER TABLE inv.unit_check ENABLE ROW LEVEL SECURITY;
CREATE POLICY unit_check_all ON inv.unit_check USING ({_OWN}) WITH CHECK ({_OWN});
"""  # noqa: S608 (constant SQL fragments, nothing is interpolated from input)

DOWNGRADE = """
DROP INDEX ops.ix_resource_category;
ALTER TABLE ops.resource DROP COLUMN category_key, DROP COLUMN specs, DROP COLUMN code, DROP COLUMN year,
    DROP COLUMN out_reason, DROP COLUMN updated_by;
DROP SCHEMA inv CASCADE;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
