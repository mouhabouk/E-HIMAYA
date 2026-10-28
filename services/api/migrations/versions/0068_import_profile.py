"""Resources register, R4b (Yamen, 2026-10-28): a file whose columns are not the template's. The user matches each
column of the file with a field of the register from a list, and keeps the match as a named profile for next time.

* ``inv.import_profile``: a gouvernorat's profiles, or the central room's (no gouvernorat), which every room may use.
  The mapping is ``{"vehicles" | "stock" | "agents": {"<file heading>": "<field>"}}``; the API checks the fields.

Revision ID: 0068_import_profile
Revises: 0067_inventory_r3
Create Date: 2026-10-28
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0068_import_profile"
down_revision: str | None = "0067_inventory_r3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OWN = "ehimaya.sees_all() OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat())"

UPGRADE = f"""
CREATE TABLE inv.import_profile (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name             text NOT NULL CHECK (char_length(name) BETWEEN 2 AND 80),
    gouvernorat_code smallint REFERENCES geo.gouvernorat(code),
    mapping          jsonb NOT NULL,
    created_by       text NOT NULL,
    created_by_name  text,
    created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_import_profile ON inv.import_profile (coalesce(gouvernorat_code, 0), lower(name));

ALTER TABLE inv.import_profile ENABLE ROW LEVEL SECURITY;
CREATE POLICY import_profile_read ON inv.import_profile FOR SELECT USING (gouvernorat_code IS NULL OR {_OWN});
CREATE POLICY import_profile_insert ON inv.import_profile FOR INSERT WITH CHECK ({_OWN});
CREATE POLICY import_profile_delete ON inv.import_profile FOR DELETE USING ({_OWN});
"""

DOWNGRADE = """
DROP TABLE inv.import_profile;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
