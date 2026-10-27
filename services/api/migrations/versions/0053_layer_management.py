"""Map layers managed by the system administrator (phase L1a, docs/phase-l/design-layers.md §3, item 10).

* ``geo.layer``: ``status`` (``draft`` → ``published`` ↔ ``paused``; existing layers stay published, a new one starts
  as a draft), ``audiences`` (who sees it: ``citizen``, ``room``, ``field``, ``command``, ``support``; from the old
  ``audience``), ``scope`` (gouvernorat codes whose staff see it; empty = national), ``default_on``, ``sensitive``
  (the minister alone, every read audited), ``fields`` (column → audiences that see it; from ``staff_only``),
  ``actions`` (call and directions buttons), and ``deleted_at`` / ``deleted_by`` / ``delete_reason`` (a deleted layer
  is kept 30 days, then purged by the retention job). ``audience`` and ``enabled`` stay, kept in step by the API:
  ``public`` when citizens see it, ``enabled`` when it is published and not deleted.
* ``geo.layer_feature``: ``shape`` (the line or area; ``location`` stays a point on its surface), ``name_status``
  (``official``, ``suggested``, ``accepted``, ``rejected``), the suggested name, its confidence and source, the
  source reference and link, the extract date, ``possible_duplicate``, and ``deleted_at`` / ``deleted_by`` /
  ``delete_reason`` (a deleted place can be restored from the layer page).
* ``geo.layer_revision``: a snapshot of a layer's settings at each change, to go back to it.
* ``geo.layer_import.format``: also ``kml``, ``shp`` and ``gpkg``.

Row-level security: the public reads only published, non-sensitive, non-deleted layers and their visible places; a
regional staff scope never reads a sensitive layer (the API also checks the role: the minister alone).

Revision ID: 0053_layer_management
Revises: 0052_staff_offline
Create Date: 2026-10-27
"""

# ruff: noqa: S608 (the policies are built from the constant SQL fragments below; no value comes from outside)

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0053_layer_management"
down_revision: str | None = "0052_staff_offline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STAFF = "ehimaya.scope() IN ('system', 'national', 'gouvernorat')"
_NATIONAL = "ehimaya.scope() IN ('system', 'national')"
_WRITE = "ehimaya.scope() IN ('system', 'national')"
_PUBLIC = "audience = 'public' AND enabled AND NOT sensitive AND deleted_at IS NULL"

UPGRADE = rf"""
ALTER TABLE geo.layer
    ADD COLUMN status        text NOT NULL DEFAULT 'published',
    ADD COLUMN audiences     text[] NOT NULL DEFAULT ARRAY['room', 'field', 'command', 'support'],
    ADD COLUMN scope         smallint[] NOT NULL DEFAULT '{{}}',
    ADD COLUMN default_on    boolean NOT NULL DEFAULT true,
    ADD COLUMN sensitive     boolean NOT NULL DEFAULT false,
    ADD COLUMN fields        jsonb NOT NULL DEFAULT '{{}}'::jsonb,
    ADD COLUMN actions       jsonb NOT NULL DEFAULT '{{"call": true, "directions": true}}'::jsonb,
    ADD COLUMN deleted_at    timestamptz,
    ADD COLUMN deleted_by    text,
    ADD COLUMN delete_reason text,
    ADD CONSTRAINT ck_layer_status CHECK (status IN ('draft', 'published', 'paused')),
    ADD CONSTRAINT ck_layer_audiences CHECK (audiences <@ ARRAY['citizen', 'room', 'field', 'command', 'support']),
    ADD CONSTRAINT ck_layer_sensitive CHECK (NOT sensitive OR audience = 'staff');

UPDATE geo.layer SET
    status = CASE WHEN enabled THEN 'published' ELSE 'paused' END,
    audiences = CASE WHEN audience = 'public'
                     THEN ARRAY['citizen', 'room', 'field', 'command', 'support']
                     ELSE ARRAY['room', 'field', 'command', 'support'] END,
    fields = COALESCE((SELECT jsonb_object_agg(c, to_jsonb(ARRAY['room', 'field', 'command', 'support']))
                       FROM unnest(staff_only) AS c), '{{}}'::jsonb);

ALTER TABLE geo.layer_feature
    ADD COLUMN shape              geography(Geometry, 4326),
    ADD COLUMN name_status        text NOT NULL DEFAULT 'official',
    ADD COLUMN suggested_name     text,
    ADD COLUMN name_confidence    text,
    ADD COLUMN name_source        text,
    ADD COLUMN source_url         text,
    ADD COLUMN snapshot_at        date,
    ADD COLUMN possible_duplicate boolean NOT NULL DEFAULT false,
    ADD COLUMN deleted_at         timestamptz,
    ADD COLUMN deleted_by         text,
    ADD COLUMN delete_reason      text,
    ADD CONSTRAINT ck_layer_feature_name_status
        CHECK (name_status IN ('official', 'suggested', 'accepted', 'rejected')),
    ADD CONSTRAINT ck_layer_feature_confidence
        CHECK (name_confidence IS NULL OR name_confidence IN ('confirmed', 'high', 'medium', 'low', 'review'));
CREATE INDEX ix_layer_feature_shape ON geo.layer_feature USING gist (shape) WHERE shape IS NOT NULL;
CREATE INDEX ix_layer_feature_review ON geo.layer_feature (layer_id, name_confidence)
    WHERE name_status = 'suggested' AND deleted_at IS NULL;

CREATE TABLE geo.layer_revision (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    layer_id         uuid NOT NULL REFERENCES geo.layer(id) ON DELETE CASCADE,
    number           integer NOT NULL,
    action           text NOT NULL,
    snapshot         jsonb NOT NULL,
    reason           text,
    created_by       text NOT NULL,
    created_by_name  text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_layer_revision UNIQUE (layer_id, number)
);

ALTER TABLE geo.layer_import DROP CONSTRAINT ck_layer_import_format;
ALTER TABLE geo.layer_import ADD CONSTRAINT ck_layer_import_format
    CHECK (format IN ('csv', 'xlsx', 'json', 'geojson', 'kml', 'shp', 'gpkg'));

DROP POLICY layer_select ON geo.layer;
CREATE POLICY layer_select ON geo.layer FOR SELECT USING (
    ({_PUBLIC}) OR {_NATIONAL} OR (ehimaya.scope() = 'gouvernorat' AND NOT sensitive));

DROP POLICY layer_feature_select ON geo.layer_feature;
CREATE POLICY layer_feature_select ON geo.layer_feature FOR SELECT USING (
    EXISTS (SELECT 1 FROM geo.layer l WHERE l.id = layer_id) AND ((NOT hidden AND deleted_at IS NULL) OR {_STAFF}));

ALTER TABLE geo.layer_revision ENABLE ROW LEVEL SECURITY;
CREATE POLICY layer_revision_select ON geo.layer_revision FOR SELECT USING ({_NATIONAL});
CREATE POLICY layer_revision_insert ON geo.layer_revision FOR INSERT WITH CHECK ({_WRITE});
CREATE POLICY layer_revision_delete ON geo.layer_revision FOR DELETE USING ({_WRITE});
"""

DOWNGRADE = rf"""
DROP TABLE geo.layer_revision;
DELETE FROM geo.layer_import WHERE format IN ('kml', 'shp', 'gpkg');
ALTER TABLE geo.layer_import DROP CONSTRAINT ck_layer_import_format;
ALTER TABLE geo.layer_import ADD CONSTRAINT ck_layer_import_format CHECK (format IN ('csv', 'xlsx', 'json', 'geojson'));

DROP POLICY layer_feature_select ON geo.layer_feature;
CREATE POLICY layer_feature_select ON geo.layer_feature FOR SELECT USING (
    EXISTS (SELECT 1 FROM geo.layer l WHERE l.id = layer_id) AND (NOT hidden OR {_STAFF}));
DROP POLICY layer_select ON geo.layer;
CREATE POLICY layer_select ON geo.layer FOR SELECT USING ((audience = 'public' AND enabled) OR {_STAFF});

DELETE FROM geo.layer_feature WHERE deleted_at IS NOT NULL;
DELETE FROM geo.layer WHERE deleted_at IS NOT NULL;
ALTER TABLE geo.layer_feature
    DROP COLUMN shape, DROP COLUMN name_status, DROP COLUMN suggested_name, DROP COLUMN name_confidence,
    DROP COLUMN name_source, DROP COLUMN source_url, DROP COLUMN snapshot_at, DROP COLUMN possible_duplicate,
    DROP COLUMN deleted_at, DROP COLUMN deleted_by, DROP COLUMN delete_reason;
ALTER TABLE geo.layer
    DROP COLUMN status, DROP COLUMN audiences, DROP COLUMN scope, DROP COLUMN default_on, DROP COLUMN sensitive,
    DROP COLUMN fields, DROP COLUMN actions, DROP COLUMN deleted_at, DROP COLUMN deleted_by, DROP COLUMN delete_reason;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
