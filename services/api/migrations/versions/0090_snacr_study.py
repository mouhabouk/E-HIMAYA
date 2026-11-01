"""SNACR studies (Yamen, 2026-11-01): the archive keeps the intervention number, the unit that went out and whether the
outing was a white one; a study freezes the six tables of the Office's format (SEC_GLOB, SAP, SR, LCI, SB, DIV) with
its settings, and the previous study of the same scope is archived when a new one is launched.

* ``snacr.intervention``: ``seq_num`` (NUM_SEQUENTIEL, the key of the damage tables), ``unit_raw`` (NOM_BRIGADE),
  ``intervened`` (INTERV_OUI_NON; false is a white outing, SB).
* ``snacr.study``: one study, national or of a gouvernorat, ``current`` until the next one of its scope archives it.

Revision ID: 0090_snacr_study
Revises: 0089_incident_delegation
Create Date: 2026-11-01
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0090_snacr_study"
down_revision: str | None = "0089_incident_delegation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OWN = "ehimaya.sees_all() OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat())"
_STAFF = "ehimaya.scope() IN ('system', 'national', 'gouvernorat')"

UPGRADE = f"""
ALTER TABLE snacr.intervention
    ADD COLUMN seq_num bigint,
    ADD COLUMN unit_raw text,
    ADD COLUMN intervened boolean;

CREATE TABLE snacr.study (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    number            integer NOT NULL CHECK (number >= 1),
    gouvernorat_code  smallint REFERENCES geo.gouvernorat(code),
    years             smallint[] NOT NULL CHECK (cardinality(years) BETWEEN 1 AND 10),
    split             boolean NOT NULL,
    travel_max        smallint NOT NULL CHECK (travel_max BETWEEN 5 AND 600),
    status            text NOT NULL CHECK (status IN ('current', 'archived')),
    simulated         boolean NOT NULL,
    tables            jsonb NOT NULL,
    quality           jsonb NOT NULL,
    created_by        text NOT NULL,
    created_by_name   text,
    created_at        timestamptz NOT NULL DEFAULT now(),
    archived_at       timestamptz,
    CONSTRAINT ck_study_archived CHECK ((status = 'current') = (archived_at IS NULL))
);
CREATE UNIQUE INDEX uq_snacr_study_number ON snacr.study (coalesce(gouvernorat_code, 0), number);
CREATE UNIQUE INDEX uq_snacr_study_current ON snacr.study (coalesce(gouvernorat_code, 0)) WHERE status = 'current';

ALTER TABLE snacr.study ENABLE ROW LEVEL SECURITY;
CREATE POLICY study_read ON snacr.study FOR SELECT USING (gouvernorat_code IS NULL AND {_STAFF} OR {_OWN});
CREATE POLICY study_insert ON snacr.study FOR INSERT WITH CHECK (
    ehimaya.sees_all() OR (gouvernorat_code IS NOT NULL AND ehimaya.regional()
                           AND gouvernorat_code = ehimaya.gouvernorat()));
CREATE POLICY study_update ON snacr.study FOR UPDATE USING (
    ehimaya.sees_all() OR (gouvernorat_code IS NOT NULL AND ehimaya.regional()
                           AND gouvernorat_code = ehimaya.gouvernorat()));
"""

DOWNGRADE = """
DROP TABLE snacr.study;
ALTER TABLE snacr.intervention DROP COLUMN seq_num, DROP COLUMN unit_raw, DROP COLUMN intervened;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
