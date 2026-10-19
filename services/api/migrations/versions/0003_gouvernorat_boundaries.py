"""Load the 24 gouvernorat boundaries (geoBoundaries ADM1, ODbL) used to locate reports.

Revision ID: 0003_gouvernorat_boundaries
Revises: 0002_seed_tn_admin
Create Date: 2026-10-19
"""

import json
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision: str = "0003_gouvernorat_boundaries"
down_revision: str | None = "0002_seed_tn_admin"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEED_FILE = Path(__file__).resolve().parents[2] / "seed" / "geo" / "tn_gouvernorats.geojson"


def upgrade() -> None:
    features = json.loads(SEED_FILE.read_text(encoding="utf-8"))["features"]
    rows = [{"iso": f["properties"]["iso_code"], "geom": json.dumps(f["geometry"])} for f in features]
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE geo.gouvernorat SET boundary = "
            "ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326)), 3)) "
            "WHERE iso_code = :iso"
        ),
        rows,
    )
    loaded = bind.scalar(sa.text("SELECT count(*) FROM geo.gouvernorat WHERE boundary IS NOT NULL"))
    if loaded != 24:
        raise RuntimeError(f"expected 24 gouvernorat boundaries, found {loaded}")


def downgrade() -> None:
    op.execute("UPDATE geo.gouvernorat SET boundary = NULL")
