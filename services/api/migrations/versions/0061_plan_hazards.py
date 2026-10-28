"""Intervention plans by hazard, each with its colour (phase PL1, docs/phase-pl/design-plans.md §2).

* ``register.hazard``: the hazards a plan answers (floods, forest fires…), each with its names and the colour the
  national committee gave its plan (the blue plan of the floods). The central room keeps the list; a hazard is never
  deleted, only switched off.
* ``register.document.hazard_key``: the hazard of a plan of the register (only a plan has one). The plan in force
  for a hazard is the one in force on the day; a new version repeals the previous one, which stays readable.

Everyone on the staff reads the hazards; only the central room changes them.

Revision ID: 0061_plan_hazards
Revises: 0060_basemap
Create Date: 2026-10-28
"""

import json
from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0061_plan_hazards"
down_revision: str | None = "0060_basemap"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# key, colour, icon, Arabic, French, English. Only the blue of the floods is the committee's (Yamen, 2026-10-28);
# the other colours are proposals the central room confirms or changes on the plans page.
HAZARDS = (
    ("floods", "#1976D2", "water", "الفيضانات", "Inondations", "Floods"),
    ("forest_fires", "#D7141A", "localFireDepartment", "حرائق الغابات", "Feux de forêt", "Forest fires"),
    ("hazardous_materials", "#F5B400", "science", "المواد الخطرة", "Matières dangereuses", "Hazardous materials"),
    ("health", "#188038", "medicalServices", "الأوبئة والطوارئ الصحية", "Épidémies", "Epidemics"),
    ("earthquakes", "#7838A0", "landslide", "الزلازل", "Séismes", "Earthquakes"),
    ("storms", "#5B6478", "thunderstorm", "العواصف", "Tempêtes", "Storms"),
)

_ALL = "ehimaya.sees_all()"


def _rows() -> str:
    def q(v: str) -> str:
        return "'" + v.replace("'", "''") + "'"

    return ",\n".join(
        f"    ({q(k)}, {q(json.dumps({'ar': ar, 'fr': fr, 'en': en}, ensure_ascii=False))}::jsonb, {q(c)}, {q(i)}, {n})"
        for n, (k, c, i, ar, fr, en) in enumerate(HAZARDS)
    )


UPGRADE = f"""
CREATE TABLE register.hazard (
    key             text PRIMARY KEY CHECK (key ~ '^[a-z][a-z0-9_]{{1,39}}$'),
    name            jsonb NOT NULL,
    colour          text NOT NULL CHECK (colour ~ '^#[0-9A-F]{{6}}$'),
    icon            text NOT NULL,
    position        integer NOT NULL DEFAULT 0,
    active          boolean NOT NULL DEFAULT true,
    updated_by      text,
    updated_by_name text,
    updated_at      timestamptz NOT NULL DEFAULT now()
);
INSERT INTO register.hazard (key, name, colour, icon, position) VALUES
{_rows()};

ALTER TABLE register.document ADD COLUMN hazard_key text REFERENCES register.hazard(key) ON UPDATE CASCADE;
ALTER TABLE register.document ADD CONSTRAINT ck_document_hazard CHECK (hazard_key IS NULL OR kind = 'plan');
CREATE INDEX ix_document_hazard ON register.document (hazard_key) WHERE hazard_key IS NOT NULL;

ALTER TABLE register.hazard ENABLE ROW LEVEL SECURITY;
CREATE POLICY hazard_select ON register.hazard FOR SELECT USING (true);
CREATE POLICY hazard_insert ON register.hazard FOR INSERT WITH CHECK ({_ALL});
CREATE POLICY hazard_update ON register.hazard FOR UPDATE USING ({_ALL}) WITH CHECK ({_ALL});
"""  # noqa: S608 (constant SQL, the seed rows are quoted above)

DOWNGRADE = """
ALTER TABLE register.document DROP CONSTRAINT ck_document_hazard;
DROP INDEX register.ix_document_hazard;
ALTER TABLE register.document DROP COLUMN hazard_key;
DROP TABLE register.hazard;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
