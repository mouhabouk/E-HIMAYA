"""Saved places of the operations rooms (phase M, docs/phase-m/design-m.md §7).

A room marks a point on the map (a school, a fuel depot, a ford that floods, a cliff road) with a name, a kind
(important, critical, other) and a note, and finds it again in a list. The point's gouvernorat and délégation come
from the Map Tunisia boundaries; row level security keeps each room to its gouvernorat, the central room sees all.

Revision ID: 0081_saved_places
Revises: 0080_alert_delegations
Create Date: 2026-10-30
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0081_saved_places"
down_revision: str | None = "0080_alert_delegations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OWN = "ehimaya.sees_all() OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat())"

UPGRADE = f"""
CREATE TABLE ops.saved_place (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name              text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 120),
    kind              text NOT NULL CHECK (kind IN ('important', 'critical', 'other')),
    note              text CHECK (length(note) <= 2000),
    lat               double precision NOT NULL CHECK (lat BETWEEN -90 AND 90),
    lon               double precision NOT NULL CHECK (lon BETWEEN -180 AND 180),
    gouvernorat_code  smallint NOT NULL REFERENCES geo.gouvernorat(code),
    delegation_id     integer REFERENCES geo.delegation(id),
    created_by        text NOT NULL,
    created_by_name   text,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_by_name   text,
    updated_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_saved_place_gouvernorat ON ops.saved_place (gouvernorat_code, updated_at DESC);

ALTER TABLE ops.saved_place ENABLE ROW LEVEL SECURITY;
CREATE POLICY saved_place_read ON ops.saved_place FOR SELECT USING ({_OWN});
CREATE POLICY saved_place_insert ON ops.saved_place FOR INSERT WITH CHECK ({_OWN});
CREATE POLICY saved_place_update ON ops.saved_place FOR UPDATE USING ({_OWN}) WITH CHECK ({_OWN});
CREATE POLICY saved_place_delete ON ops.saved_place FOR DELETE USING ({_OWN});
"""

DOWNGRADE = "DROP TABLE ops.saved_place;"


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
