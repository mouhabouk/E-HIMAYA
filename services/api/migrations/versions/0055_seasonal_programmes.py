"""Seasonal deployment programmes as dated, versioned map layers (phase L2, docs/phase-l/design-l2.md §2, item 12).

* ``programme.programme``: one programme (road rescue points, seasonal centres, beaches…), its validity dates, its
  life cycle (draft, approved, updated, ended, cancelled), its version and who approved it, and the map layer it owns
  once approved (a layer of phase L1a, so visibility, columns per audience, deletion and revisions come with it).
* ``programme.point``: one place of a programme, with a stable reference across versions; the position may be
  missing (the administrator places it on the map), and its accuracy stays visible. The supervisor's name and phone
  are personal data: the layer shows them to the operations rooms only.
* ``programme.revision``: the programme and its points after each change, with the reason; two revisions give the
  differences, and going back to one restores it.

Row-level security: the national staff writes programmes; a regional room updates the points of its own gouvernorat
(the daily follow-up); every staff account reads (the layer keeps its own visibility for the maps).

Revision ID: 0055_seasonal_programmes
Revises: 0054_coastal_safety
Create Date: 2026-10-28
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0055_seasonal_programmes"
down_revision: str | None = "0054_coastal_safety"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STAFF = "ehimaya.scope() IN ('system', 'national', 'gouvernorat')"
_WRITE = "ehimaya.scope() IN ('system', 'national')"

UPGRADE = rf"""
CREATE SCHEMA IF NOT EXISTS programme;

CREATE TABLE programme.programme (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code            text NOT NULL UNIQUE CHECK (code ~ '^[A-Z]+-[0-9]{{4}}(-[A-Z0-9]+)?$'),
    kind            text NOT NULL CHECK (kind IN ('road', 'seasonal', 'beach', 'other')),
    title           text NOT NULL,
    season          text NOT NULL DEFAULT '',
    valid_from      date NOT NULL,
    valid_to        date NOT NULL,
    status          text NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft', 'approved', 'updated', 'ended', 'cancelled')),
    version         integer NOT NULL DEFAULT 1,
    source_document text NOT NULL DEFAULT '',
    declared        jsonb NOT NULL DEFAULT '{{}}'::jsonb,
    approved_by     text,
    approved_by_name text,
    approved_at     timestamptz,
    cancel_reason   text,
    layer_id        uuid REFERENCES geo.layer(id) ON DELETE SET NULL,
    created_by      text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_by      text NOT NULL,
    updated_by_name text,
    updated_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_programme_dates CHECK (valid_to >= valid_from)
);
CREATE INDEX ix_programme_status ON programme.programme (status, valid_from, valid_to);

CREATE TABLE programme.point (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    programme_id        uuid NOT NULL REFERENCES programme.programme(id) ON DELETE CASCADE,
    ref                 text NOT NULL,
    gouvernorat_code    smallint REFERENCES geo.gouvernorat(code),
    place_name          text NOT NULL,
    sub_points          text,
    location            geography(POINT, 4326),
    geo_confidence      text NOT NULL DEFAULT 'unknown'
                        CHECK (geo_confidence IN ('confirmed', 'high', 'medium', 'approximate', 'review', 'unknown')),
    geo_note            text,
    staff_count         integer CHECK (staff_count >= 0),
    staff_composition   text,
    supervisors         integer CHECK (supervisors >= 0),
    lifeguards_planned  integer CHECK (lifeguards_planned >= 0),
    lifeguards_deployed integer CHECK (lifeguards_deployed >= 0),
    equipment           text,
    hours               text,
    opening_date        date,
    closing_date        date,
    status              text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed', 'postponed')),
    supervisor_name     text,
    supervisor_phone    text,
    notes               text,
    updated_by          text,
    updated_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_programme_point UNIQUE (programme_id, ref)
);
CREATE INDEX ix_programme_point_gouvernorat ON programme.point (programme_id, gouvernorat_code);
CREATE INDEX ix_programme_point_location ON programme.point USING gist (location);

CREATE TABLE programme.revision (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    programme_id    uuid NOT NULL REFERENCES programme.programme(id) ON DELETE CASCADE,
    number          integer NOT NULL,
    action          text NOT NULL,
    reason          text,
    snapshot        jsonb NOT NULL,
    created_by      text NOT NULL,
    created_by_name text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_programme_revision UNIQUE (programme_id, number)
);

ALTER TABLE programme.programme ENABLE ROW LEVEL SECURITY;
CREATE POLICY programme_select ON programme.programme FOR SELECT USING ({_STAFF});
CREATE POLICY programme_insert ON programme.programme FOR INSERT WITH CHECK ({_WRITE});
CREATE POLICY programme_update ON programme.programme FOR UPDATE USING ({_STAFF}) WITH CHECK ({_STAFF});
CREATE POLICY programme_delete ON programme.programme FOR DELETE USING ({_WRITE});

ALTER TABLE programme.point ENABLE ROW LEVEL SECURITY;
CREATE POLICY point_select ON programme.point FOR SELECT USING ({_STAFF});
CREATE POLICY point_insert ON programme.point FOR INSERT WITH CHECK ({_WRITE});
CREATE POLICY point_update ON programme.point FOR UPDATE
    USING (ehimaya.sees_all() OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat()))
    WITH CHECK (ehimaya.sees_all() OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat()));
CREATE POLICY point_delete ON programme.point FOR DELETE USING ({_WRITE});

ALTER TABLE programme.revision ENABLE ROW LEVEL SECURITY;
CREATE POLICY revision_select ON programme.revision FOR SELECT USING ({_STAFF});
CREATE POLICY revision_insert ON programme.revision FOR INSERT WITH CHECK ({_STAFF});
CREATE POLICY revision_delete ON programme.revision FOR DELETE USING ({_WRITE});
"""

DOWNGRADE = r"""
DROP SCHEMA programme CASCADE;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
