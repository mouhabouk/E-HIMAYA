"""Map data layers loaded from files (phase B1, docs/phase-b/design.md §2).

* ``geo.layer`` — a named set of places ("Hospitals and emergency departments", "Shelters"…): names ar/fr/en, icon
  and colour, audience (``public``: shown in the app; ``staff``: dashboard only), source and licence, the columns
  never sent to the app (``staff_only``, ``manager`` by default), whether content editors may import into it, a
  metadata ``version`` (optimistic concurrency) and a ``data_version`` bumped at every change of its places (the
  ``ETag`` of the app's offline package).
* ``geo.layer_feature`` — one place: the file's own identifier (``ref``, unique in the layer), name, sub-type, phone,
  position (PostGIS point, spatial index), gouvernorat and délégation computed from the position, the other columns
  in ``props`` (address, hours, manager, beds…), ``hidden`` (taken off the map by hand).
* ``geo.layer_import`` — one uploaded file: preview counts and rejected rows, the parsed rows until it is applied,
  what applying it replaced (``undo``) so "undo the last import" restores the previous version, who and why.

Row-level security: a public, enabled layer and its visible places are read by everyone (the app reads them without
signing in); staff layers, hidden places and the imports by staff scopes only; writes need the national or system
scope (the API also checks the role: system administrator, or content editor on a layer open to them).

Revision ID: 0032_map_layers
Revises: 0031_phase_a_settings
Create Date: 2026-10-23
"""

# ruff: noqa: S608 (the policies are built from the constant SQL fragments below; no value comes from outside)

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0032_map_layers"
down_revision: str | None = "0031_phase_a_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STAFF = "ehimaya.scope() IN ('system', 'national', 'gouvernorat')"
_WRITE = "ehimaya.scope() IN ('system', 'national')"

UPGRADE = rf"""
CREATE TABLE geo.layer (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    key              text NOT NULL UNIQUE,
    name             jsonb NOT NULL,
    icon             text NOT NULL,
    colour           text NOT NULL,
    audience         text NOT NULL DEFAULT 'staff',
    source           text NOT NULL DEFAULT '',
    licence          text NOT NULL DEFAULT '',
    to_verify        boolean NOT NULL DEFAULT true,
    staff_only       text[] NOT NULL DEFAULT ARRAY['manager'],
    editors_allowed  boolean NOT NULL DEFAULT false,
    enabled          boolean NOT NULL DEFAULT true,
    version          integer NOT NULL DEFAULT 1,
    data_version     integer NOT NULL DEFAULT 0,
    created_by       text NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_by       text NOT NULL,
    updated_by_name  text,
    updated_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_layer_key CHECK (key ~ '^[a-z][a-z0-9_]{{1,39}}$'),
    CONSTRAINT ck_layer_colour CHECK (colour ~ '^#[0-9A-F]{{6}}$'),
    CONSTRAINT ck_layer_audience CHECK (audience IN ('public', 'staff')),
    CONSTRAINT ck_layer_versions CHECK (version >= 1 AND data_version >= 0)
);

CREATE TABLE geo.layer_import (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    layer_id         uuid NOT NULL REFERENCES geo.layer(id) ON DELETE CASCADE,
    file_name        text NOT NULL,
    sha256           text NOT NULL,
    format           text NOT NULL,
    mode             text NOT NULL,
    status           text NOT NULL DEFAULT 'preview',
    counts           jsonb NOT NULL,
    rejected         jsonb NOT NULL DEFAULT '[]'::jsonb,
    warnings         jsonb NOT NULL DEFAULT '[]'::jsonb,
    rows             jsonb,
    undo             jsonb,
    base_version     integer NOT NULL,
    result_version   integer,
    reason           text,
    created_by       text NOT NULL,
    created_by_name  text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    applied_at       timestamptz,
    undone_at        timestamptz,
    CONSTRAINT ck_layer_import_format CHECK (format IN ('csv', 'xlsx', 'json', 'geojson')),
    CONSTRAINT ck_layer_import_mode CHECK (mode IN ('merge', 'replace')),
    CONSTRAINT ck_layer_import_status CHECK (status IN ('preview', 'applied', 'undone', 'discarded'))
);
CREATE INDEX ix_layer_import_layer ON geo.layer_import (layer_id, created_at DESC);

CREATE TABLE geo.layer_feature (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    layer_id         uuid NOT NULL REFERENCES geo.layer(id) ON DELETE CASCADE,
    ref              text NOT NULL,
    name             text NOT NULL,
    kind             text,
    phone            text,
    location         geography(Point, 4326) NOT NULL,
    gouvernorat_code smallint REFERENCES geo.gouvernorat(code),
    delegation_id    integer REFERENCES geo.delegation(id),
    props            jsonb NOT NULL DEFAULT '{{}}'::jsonb,
    hidden           boolean NOT NULL DEFAULT false,
    import_id        uuid REFERENCES geo.layer_import(id) ON DELETE SET NULL,
    version          integer NOT NULL DEFAULT 1,
    updated_by       text,
    updated_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_layer_feature_ref UNIQUE (layer_id, ref),
    CONSTRAINT ck_layer_feature_name CHECK (length(name) BETWEEN 1 AND 200)
);
CREATE INDEX ix_layer_feature_location ON geo.layer_feature USING gist (location);
CREATE INDEX ix_layer_feature_layer_gouvernorat ON geo.layer_feature (layer_id, gouvernorat_code);

ALTER TABLE geo.layer ENABLE ROW LEVEL SECURITY;
CREATE POLICY layer_select ON geo.layer FOR SELECT USING ((audience = 'public' AND enabled) OR {_STAFF});
CREATE POLICY layer_insert ON geo.layer FOR INSERT WITH CHECK ({_WRITE});
CREATE POLICY layer_update ON geo.layer FOR UPDATE USING ({_WRITE}) WITH CHECK ({_WRITE});
CREATE POLICY layer_delete ON geo.layer FOR DELETE USING ({_WRITE});

-- The layer's own policy applies inside the EXISTS: a place is visible when its layer is.
ALTER TABLE geo.layer_feature ENABLE ROW LEVEL SECURITY;
CREATE POLICY layer_feature_select ON geo.layer_feature FOR SELECT USING (
    EXISTS (SELECT 1 FROM geo.layer l WHERE l.id = layer_id) AND (NOT hidden OR {_STAFF}));
CREATE POLICY layer_feature_insert ON geo.layer_feature FOR INSERT WITH CHECK ({_WRITE});
CREATE POLICY layer_feature_update ON geo.layer_feature FOR UPDATE USING ({_WRITE}) WITH CHECK ({_WRITE});
CREATE POLICY layer_feature_delete ON geo.layer_feature FOR DELETE USING ({_WRITE});

ALTER TABLE geo.layer_import ENABLE ROW LEVEL SECURITY;
CREATE POLICY layer_import_select ON geo.layer_import FOR SELECT USING ({_STAFF});
CREATE POLICY layer_import_insert ON geo.layer_import FOR INSERT WITH CHECK ({_WRITE});
CREATE POLICY layer_import_update ON geo.layer_import FOR UPDATE USING ({_WRITE}) WITH CHECK ({_WRITE});
CREATE POLICY layer_import_delete ON geo.layer_import FOR DELETE USING ({_WRITE});
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(
        """
        DROP TABLE geo.layer_feature;
        DROP TABLE geo.layer_import;
        DROP TABLE geo.layer;
        """
    )
