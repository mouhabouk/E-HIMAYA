"""Satellite background of the maps (phase R, docs/phase-r/design-basemap.md).

* ``geo.basemap``: the paid imagery provider the administration may choose (one row per background, today
  ``satellite``): its tile address with ``{z}``, ``{x}``, ``{y}`` and ``{key}``, the licence key (encrypted, never
  returned), the attribution, the maximum zoom, whether it is on, and the last connection test. Without an enabled
  row, the maps use the open source (Sentinel-2 cloudless by EOX).

Everyone on the staff reads whether a paid provider is on (the key column is ciphertext); only the national system
administrator writes.

Revision ID: 0060_basemap
Revises: 0059_inventory
Create Date: 2026-10-28
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0060_basemap"
down_revision: str | None = "0059_inventory"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_WRITE = "ehimaya.scope() IN ('system', 'national')"

UPGRADE = f"""
CREATE TABLE geo.basemap (
    key            text PRIMARY KEY CHECK (key IN ('satellite')),
    provider       text NOT NULL CHECK (provider IN ('esri', 'maxar', 'mapbox', 'google', 'other')),
    url_template   text NOT NULL CHECK (url_template ~ '^https://'),
    api_key        bytea,
    key_header     text CHECK (key_header ~ '^[A-Za-z][A-Za-z0-9-]{{1,63}}$'),
    attribution    text NOT NULL,
    max_zoom       smallint NOT NULL DEFAULT 19 CHECK (max_zoom BETWEEN 1 AND 22),
    enabled        boolean NOT NULL DEFAULT false,
    last_test_ok   boolean,
    last_test_at   timestamptz,
    updated_by     text,
    updated_by_name text,
    updated_at     timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE geo.basemap ENABLE ROW LEVEL SECURITY;
CREATE POLICY basemap_select ON geo.basemap FOR SELECT USING (true);
CREATE POLICY basemap_insert ON geo.basemap FOR INSERT WITH CHECK ({_WRITE});
CREATE POLICY basemap_update ON geo.basemap FOR UPDATE USING ({_WRITE}) WITH CHECK ({_WRITE});
CREATE POLICY basemap_delete ON geo.basemap FOR DELETE USING ({_WRITE});
"""

DOWNGRADE = "DROP TABLE geo.basemap;"


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
