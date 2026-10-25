"""Twelve institution kinds with their own fields (phase P2, addition 12, docs/phase-p2/design-institutions-app.md §2).

* ``org.organization.kind``: 12 kinds instead of 6. ``educational`` becomes ``education``, ``hotel`` ``tourism``,
  ``government`` ``public_admin``; ``private`` has no match and becomes ``other`` with ``kind_review`` set, so the
  institutions auditor picks the right kind.
* ``kind_fields``: the answers to the fields of the kind (defined in ``app.modules.orgs.domain.KIND_FIELDS``, with
  the visibility of each field). The API validates them; the database only checks that they are a JSON object.

Downgrade maps the kinds back (kinds without an old equivalent become ``other``) and drops the two columns.

Revision ID: 0044_institution_kinds
Revises: 0043_medical_referrals
Create Date: 2026-10-25
"""

# ruff: noqa: S608 (the scripts are built from the constant kind lists below)
from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0044_institution_kinds"
down_revision: str | None = "0043_medical_referrals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_KINDS = (
    "'health', 'industrial', 'energy', 'tourism', 'education', 'social_care', 'public_admin', "
    "'culture_sport', 'commercial', 'transport', 'religious', 'other'"
)
OLD_KINDS = "'industrial', 'educational', 'hotel', 'government', 'private', 'other'"

UPGRADE = f"""
ALTER TABLE org.organization DROP CONSTRAINT organization_kind_check;
ALTER TABLE org.organization ADD COLUMN kind_review boolean NOT NULL DEFAULT false;
ALTER TABLE org.organization ADD COLUMN kind_fields jsonb NOT NULL DEFAULT '{{}}'
    CHECK (jsonb_typeof(kind_fields) = 'object');
UPDATE org.organization SET kind_review = true WHERE kind = 'private';
UPDATE org.organization SET kind = CASE kind
    WHEN 'educational' THEN 'education'
    WHEN 'hotel' THEN 'tourism'
    WHEN 'government' THEN 'public_admin'
    WHEN 'private' THEN 'other'
    ELSE kind END;
ALTER TABLE org.organization ADD CONSTRAINT organization_kind_check CHECK (kind IN ({NEW_KINDS}));
"""

DOWNGRADE = f"""
ALTER TABLE org.organization DROP CONSTRAINT organization_kind_check;
UPDATE org.organization SET kind = CASE
    WHEN kind = 'education' THEN 'educational'
    WHEN kind = 'tourism' THEN 'hotel'
    WHEN kind = 'public_admin' THEN 'government'
    WHEN kind = 'other' AND kind_review THEN 'private'
    WHEN kind = 'industrial' THEN 'industrial'
    ELSE 'other' END;
ALTER TABLE org.organization ADD CONSTRAINT organization_kind_check CHECK (kind IN ({OLD_KINDS}));
ALTER TABLE org.organization DROP COLUMN kind_fields;
ALTER TABLE org.organization DROP COLUMN kind_review;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
