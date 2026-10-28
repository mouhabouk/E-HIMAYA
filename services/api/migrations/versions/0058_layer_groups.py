"""Map layers in groups (phase UI-3b, docs/phase-ui3/design-layer-groups.md).

* ``geo.layer_group``: a folder of the map's layer panel, with its names, icon, colour tone and order. The
  system administrator creates, renames, orders and deletes them (an empty group only).
* ``geo.layer.group_key``: the group a layer is in. A layer without one is shown in the group its key and icon
  suggest (``app.modules.layers.domain.default_group``), so new layers, programme layers and loaded OSM layers
  land in the right place without a step.

A group grants nothing: each layer keeps its audiences and scope, and the API lists only the groups in which the
caller sees a layer (so the minister's sensitive group stays unknown to everyone else).

Revision ID: 0058_layer_groups
Revises: 0057_register
Create Date: 2026-10-28
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0058_layer_groups"
down_revision: str | None = "0057_register"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_WRITE = "ehimaya.scope() IN ('system', 'national')"

# key, Arabic, French, English, icon (dashboard Icon.tsx), tone, sensitive
GROUPS = (
    (
        "civil_protection",
        "موارد الحماية المدنية",
        "Moyens de la protection civile",
        "Civil protection resources",
        "localFireDepartment",
        "red",
        False,
    ),
    ("health", "المؤسسات الصحية", "Établissements de santé", "Health facilities", "medicalServices", "pink", False),
    ("security", "الأمن", "Sécurité", "Security", "policy", "navy", False),
    ("administration", "الإدارة", "Administration", "Administration", "apartment", "slate", False),
    ("education", "التعليم", "Enseignement", "Education", "menuBook", "purple", False),
    ("transport", "النقل", "Transports", "Transport", "localShipping", "sky", False),
    ("economy", "المنشآت الاقتصادية", "Activités économiques", "Economic sites", "inventory2", "amber", False),
    ("water_forests", "الماء والغابات", "Eau et forêts", "Water and forests", "map", "teal", False),
    ("gathering", "أماكن التجمع", "Lieux de rassemblement", "Gathering places", "groups", "orange", False),
    ("seasons", "المواسم والسواحل", "Saisons et littoral", "Seasons and coast", "schedule", "teal", False),
    ("sensitive", "طبقات حساسة", "Couches sensibles", "Sensitive layers", "lockOpen", "red", True),
    ("other", "طبقات أخرى", "Autres couches", "Other layers", "layers", "slate", False),
)

# The layers loaded so far, by the stem of their key (``osm_hospitals`` → ``hospitals``); the same rules as
# ``default_group`` in the API.
STEMS = {
    "civil_protection": ("civil_protection", "fire_hydrants", "units"),
    "health": ("hospitals", "clinics", "pharmacies", "elderly_homes"),
    "security": ("police", "national_guard"),
    "administration": ("governorate_hq", "delegation_hq", "ministries"),
    "education": ("schools", "institutes", "faculties", "universities"),
    "transport": ("airports", "train_stations", "railways", "bus_stations", "bus_stops"),
    "economy": ("factories", "companies", "fuel_stations", "supermarkets", "hotels"),
    "water_forests": ("lakes", "rivers", "forests", "dams"),
    "gathering": ("worship", "sports"),
    "seasons": ("beaches",),
    "sensitive": ("barracks", "oil_gas"),
}


def _q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


_ROWS = ",\n".join(
    f"({_q(k)}, jsonb_build_object('ar', {_q(ar)}, 'fr', {_q(fr)}, 'en', {_q(en)}), {_q(icon)}, {_q(tone)}, {i + 1}, {str(s).lower()})"
    for i, (k, ar, fr, en, icon, tone, s) in enumerate(GROUPS)
)
_CASES = "\n".join(
    f"    WHEN regexp_replace(key, '^(osm_|sim_)', '') IN ({', '.join(_q(s) for s in stems)}) THEN {_q(group)}"
    for group, stems in STEMS.items()
)

UPGRADE = rf"""
CREATE TABLE geo.layer_group (
    key        text PRIMARY KEY CHECK (key ~ '^[a-z][a-z0-9_]{{1,39}}$'),
    name       jsonb NOT NULL,
    icon       text NOT NULL,
    tone       text NOT NULL,
    position   integer NOT NULL DEFAULT 0,
    sensitive  boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    updated_by text
);

INSERT INTO geo.layer_group (key, name, icon, tone, position, sensitive) VALUES
{_ROWS};

ALTER TABLE geo.layer ADD COLUMN group_key text REFERENCES geo.layer_group(key) ON UPDATE CASCADE;
CREATE INDEX ix_layer_group ON geo.layer (group_key);

UPDATE geo.layer SET group_key = CASE
    WHEN sensitive THEN 'sensitive'
    WHEN key LIKE 'prog\_%' THEN 'seasons'
{_CASES}
    ELSE NULL END;

ALTER TABLE geo.layer_group ENABLE ROW LEVEL SECURITY;
CREATE POLICY layer_group_select ON geo.layer_group FOR SELECT USING (true);
CREATE POLICY layer_group_insert ON geo.layer_group FOR INSERT WITH CHECK ({_WRITE});
CREATE POLICY layer_group_update ON geo.layer_group FOR UPDATE USING ({_WRITE}) WITH CHECK ({_WRITE});
CREATE POLICY layer_group_delete ON geo.layer_group FOR DELETE USING ({_WRITE});
"""  # noqa: S608 (constant SQL fragments, nothing is interpolated from input)

DOWNGRADE = """
ALTER TABLE geo.layer DROP COLUMN group_key;
DROP TABLE geo.layer_group;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
