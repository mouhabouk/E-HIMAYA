"""Alerts to délégations (phase M, docs/phase-m/design-m.md §5).

An alert may now target some délégations: their ids are kept in ``notify.message.delegation_ids`` and the union of
their Map Tunisia boundaries becomes the area's polygon, so every rule that reads ``area_polygon`` (recipients, scope,
coverage, committee) works unchanged. An island délégation (Kerkennah, Djerba) makes the union several parts: the
column becomes a MultiPolygon; a drawn polygon is stored as a MultiPolygon of one part.

Revision ID: 0080_alert_delegations
Revises: 0079_admin_reference
Create Date: 2026-10-30
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0080_alert_delegations"
down_revision: str | None = "0079_admin_reference"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = """
ALTER TABLE notify.message ALTER COLUMN area_polygon TYPE geometry(MultiPolygon, 4326) USING ST_Multi(area_polygon);
ALTER TABLE notify.message ADD COLUMN delegation_ids integer[] NOT NULL DEFAULT '{}';
"""

# Back to one polygon: an area of several parts keeps its largest one.
DOWNGRADE = """
ALTER TABLE notify.message DROP COLUMN delegation_ids;
UPDATE notify.message m SET area_polygon = ST_Multi(
    (SELECT d.geom FROM ST_Dump(m.area_polygon) d ORDER BY ST_Area(d.geom) DESC LIMIT 1)
) WHERE ST_NumGeometries(area_polygon) > 1;
ALTER TABLE notify.message ALTER COLUMN area_polygon TYPE geometry(Polygon, 4326)
    USING ST_GeometryN(area_polygon, 1);
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
