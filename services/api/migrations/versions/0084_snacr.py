"""Risk analysis and coverage plan, SNACR (docs/phase-s/design-s.md).

* ``snacr.dataset``: one year of the archive of interventions (the Office's file, or [SIM] rows generated on the
  distributions of the real 2022 archive), with what the cleaning found.
* ``snacr.intervention``: one past intervention: nature, place and times only. The address, the free texts, the crew
  and the vehicles of the Office's export are never read.
* ``snacr.alias``: another way the archive writes a délégation, tied to its INS délégation; seeded with the names of
  the 2022 archive that neither the exact nor the loose comparison finds.
* ``snacr.special_risk``: the register of specific risks (probability and gravity, 1 to 5) by gouvernorat; seeded
  with [SIM] entries the committees replace.
* ``snacr.plan``: a national or regional plan, a frozen snapshot of the analysis, approved by its committee.

Revision ID: 0084_snacr
Revises: 0083_availability_slots
Create Date: 2026-10-30
"""

import re
from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0084_snacr"
down_revision: str | None = "0083_availability_slots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OWN = "ehimaya.sees_all() OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat())"
_STAFF = "ehimaya.scope() IN ('system', 'national', 'gouvernorat')"

# (gouvernorat, how the 2022 archive writes it, INS délégation).
ALIASES = [
    (11, "باب بحر", 1101),
    (12, "اريانة مدينة", 1201),
    (21, "دار شعبان", 2104),
    (21, "حمام الغزاز", 2109),
    (22, "بئرالمشارقة", 2201),
    (32, "وادمليز", 3208),
    (34, "بورويس", 3409),
    (34, "الروجية", 3408),
    (41, "الحاجب", 4107),
    (41, "العلاء", 4105),
    (42, "حاسي", 4206),
    (43, "بن عون", 4311),
    (43, "السبالة", 4302),
    (51, "سيدي عبد الحميد", 5115),
    (51, "زاوية سوسة", 5116),
    (51, "قصيبة سوسة", 5116),
    (51, "الثريات", 5116),
    (51, "الزاوية", 5116),
    (51, "شط مريم", 5101),
    (52, "المنستير المدينة", 5208),
    (53, "المهدية المدينة", 5309),
    (71, "المضيلة", 7106),
    (71, "بالخير", 7101),
    (81, "الحامة الغربية", 8102),
    (83, "السمار", 8306),
]

# [SIM] (gouvernorat, hazard, probability, gravity): a starting register the committees correct.
SPECIAL = [
    (32, "forest_fire", 5, 4),
    (31, "forest_fire", 4, 4),
    (23, "forest_fire", 4, 3),
    (33, "forest_fire", 3, 3),
    (34, "forest_fire", 3, 3),
    (42, "forest_fire", 4, 3),
    (21, "forest_fire", 3, 3),
    (22, "forest_fire", 3, 3),
    (21, "flood", 4, 4),
    (11, "flood", 3, 4),
    (13, "flood", 3, 3),
    (12, "flood", 3, 3),
    (61, "flood", 3, 4),
    (32, "flood", 4, 3),
    (41, "flood", 3, 3),
    (23, "flood", 3, 3),
    (82, "flood", 2, 3),
    (81, "industrial", 4, 5),
    (61, "industrial", 3, 4),
    (23, "industrial", 3, 4),
    (13, "industrial", 3, 3),
    (71, "industrial", 3, 3),
    (52, "coastal", 3, 3),
    (51, "coastal", 3, 3),
    (21, "coastal", 3, 3),
    (82, "coastal", 3, 3),
    (53, "coastal", 3, 3),
    (13, "hazmat_transport", 2, 4),
    (61, "hazmat_transport", 2, 4),
    (11, "earthquake", 1, 5),
    (41, "drought", 4, 2),
    (43, "drought", 4, 2),
    (83, "drought", 4, 2),
    (72, "storm", 3, 2),
    (73, "storm", 3, 2),
]


def _normalized(raw: str) -> str:
    """The form the import compares (``snacr.domain.normalize``), frozen here for the seeds."""
    s = re.sub("[\u064b-\u0652\u0640]", "", raw)
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ة", "ه"), ("ى", "ي"), ("ئ", "ي"), ("ؤ", "و")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


def _upgrade() -> str:
    aliases = ",\n".join(f"({g}, '{raw}', '{_normalized(raw)}', {d}, 'system', 'e-Himaya')" for g, raw, d in ALIASES)
    special = ",\n".join(f"({g}, '{h}', {p}, {s}, true, 'system', 'e-Himaya')" for g, h, p, s in SPECIAL)
    return f"""
CREATE SCHEMA IF NOT EXISTS snacr;

CREATE TABLE snacr.dataset (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    year              smallint NOT NULL UNIQUE CHECK (year BETWEEN 2000 AND 2100),
    source            text NOT NULL CHECK (source IN ('office', 'simulated')),
    simulated         boolean NOT NULL,
    file_name         text,
    rows              integer NOT NULL CHECK (rows >= 0),
    quality           jsonb NOT NULL DEFAULT '{{}}'::jsonb,
    imported_by       text NOT NULL,
    imported_by_name  text,
    imported_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_dataset_simulated CHECK (simulated = (source = 'simulated'))
);

CREATE TABLE snacr.intervention (
    id                bigserial PRIMARY KEY,
    dataset_id        uuid NOT NULL REFERENCES snacr.dataset(id) ON DELETE CASCADE,
    year              smallint NOT NULL,
    family            text NOT NULL CHECK (family IN ('medical', 'road', 'fire', 'rescue')),
    nature            text NOT NULL,
    subtype           text,
    gouvernorat_code  smallint NOT NULL REFERENCES geo.gouvernorat(code),
    delegation_id     integer REFERENCES geo.delegation(id),
    delegation_raw    text NOT NULL,
    called_at         timestamptz NOT NULL,
    departed_at       timestamptz,
    arrived_at        timestamptz,
    ended_at          timestamptz,
    arrival_min       double precision,
    flags             text[] NOT NULL DEFAULT '{{}}'
);
CREATE INDEX ix_snacr_intervention_year ON snacr.intervention (year, gouvernorat_code, family);
CREATE INDEX ix_snacr_intervention_delegation ON snacr.intervention (delegation_id, year);
CREATE INDEX ix_snacr_intervention_dataset ON snacr.intervention (dataset_id);

CREATE TABLE snacr.alias (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    gouvernorat_code  smallint NOT NULL REFERENCES geo.gouvernorat(code),
    raw               text NOT NULL CHECK (char_length(raw) BETWEEN 1 AND 120),
    normalized        text NOT NULL,
    delegation_id     integer NOT NULL REFERENCES geo.delegation(id),
    created_by        text NOT NULL,
    created_by_name   text,
    created_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_snacr_alias UNIQUE (gouvernorat_code, normalized)
);

CREATE TABLE snacr.special_risk (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    gouvernorat_code  smallint NOT NULL REFERENCES geo.gouvernorat(code),
    hazard            text NOT NULL CHECK (hazard IN ('flood', 'forest_fire', 'industrial', 'hazmat_transport',
                                                      'coastal', 'earthquake', 'storm', 'drought', 'epidemic')),
    probability       smallint NOT NULL CHECK (probability BETWEEN 1 AND 5),
    gravity           smallint NOT NULL CHECK (gravity BETWEEN 1 AND 5),
    note              text CHECK (char_length(note) <= 500),
    simulated         boolean NOT NULL DEFAULT false,
    updated_by        text NOT NULL,
    updated_by_name   text,
    updated_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_snacr_special UNIQUE (gouvernorat_code, hazard)
);

CREATE TABLE snacr.plan (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    gouvernorat_code  smallint REFERENCES geo.gouvernorat(code),
    version           integer NOT NULL CHECK (version >= 1),
    years             smallint[] NOT NULL,
    status            text NOT NULL CHECK (status IN ('draft', 'approved', 'superseded')),
    simulated         boolean NOT NULL,
    content           jsonb NOT NULL,
    created_by        text NOT NULL,
    created_by_name   text,
    created_at        timestamptz NOT NULL DEFAULT now(),
    approved_by       text,
    approved_by_name  text,
    approved_at       timestamptz,
    CONSTRAINT ck_plan_approved CHECK ((status = 'draft') = (approved_at IS NULL))
);
CREATE UNIQUE INDEX uq_snacr_plan_version ON snacr.plan (coalesce(gouvernorat_code, 0), version);

INSERT INTO snacr.alias (gouvernorat_code, raw, normalized, delegation_id, created_by, created_by_name) VALUES
{aliases};
INSERT INTO snacr.special_risk (gouvernorat_code, hazard, probability, gravity, simulated, updated_by, updated_by_name)
VALUES
{special};

ALTER TABLE snacr.dataset ENABLE ROW LEVEL SECURITY;
CREATE POLICY dataset_read ON snacr.dataset FOR SELECT USING ({_STAFF});
CREATE POLICY dataset_write ON snacr.dataset FOR ALL USING (ehimaya.sees_all()) WITH CHECK (ehimaya.sees_all());

ALTER TABLE snacr.intervention ENABLE ROW LEVEL SECURITY;
CREATE POLICY intervention_read ON snacr.intervention FOR SELECT USING ({_OWN});
CREATE POLICY intervention_write ON snacr.intervention FOR ALL USING (ehimaya.sees_all())
    WITH CHECK (ehimaya.sees_all());

ALTER TABLE snacr.alias ENABLE ROW LEVEL SECURITY;
CREATE POLICY alias_read ON snacr.alias FOR SELECT USING ({_STAFF});
CREATE POLICY alias_write ON snacr.alias FOR ALL USING (ehimaya.sees_all()) WITH CHECK (ehimaya.sees_all());

ALTER TABLE snacr.special_risk ENABLE ROW LEVEL SECURITY;
CREATE POLICY special_read ON snacr.special_risk FOR SELECT USING ({_STAFF});
CREATE POLICY special_write ON snacr.special_risk FOR ALL USING ({_OWN}) WITH CHECK ({_OWN});

ALTER TABLE snacr.plan ENABLE ROW LEVEL SECURITY;
CREATE POLICY plan_read ON snacr.plan FOR SELECT USING (gouvernorat_code IS NULL AND {_STAFF} OR {_OWN});
CREATE POLICY plan_insert ON snacr.plan FOR INSERT WITH CHECK (
    ehimaya.sees_all() OR (gouvernorat_code IS NOT NULL AND ehimaya.regional()
                           AND gouvernorat_code = ehimaya.gouvernorat()));
CREATE POLICY plan_update ON snacr.plan FOR UPDATE USING (
    ehimaya.sees_all() OR (gouvernorat_code IS NOT NULL AND ehimaya.regional()
                           AND gouvernorat_code = ehimaya.gouvernorat()));
"""  # noqa: S608 (constants only, no input)


DOWNGRADE = "DROP SCHEMA snacr CASCADE;"


def upgrade() -> None:
    run_script(_upgrade())


def downgrade() -> None:
    run_script(DOWNGRADE)
