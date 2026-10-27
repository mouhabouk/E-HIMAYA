"""Prevention visits on the inspector's phone (phase P4c, docs/phase-p4/design-staff.md §8, F-STF-06).

* ``org.prevention_visit``: the inspector who took the visit on a phone (``inspector_subject``), the phone's id for the
  inspection sent from it (``inspection_client_id``, so a resent inspection is applied once) and its clock, and the two
  signatures (inspector, institution representative with name and role) kept in the object store.
* ``org.prevention_photo``: photos taken on site, attached to an item of the grid or to the visit.

Revision ID: 0051_prevention_on_site
Revises: 0050_staff_app_field
Create Date: 2026-10-27
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0051_prevention_on_site"
down_revision: str | None = "0050_staff_app_field"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = """
ALTER TABLE org.prevention_visit
    ADD COLUMN inspector_subject text,
    ADD COLUMN inspection_client_id uuid UNIQUE,
    ADD COLUMN inspected_device_at timestamptz,
    ADD COLUMN inspector_signature_key text,
    ADD COLUMN representative_name text CHECK (char_length(representative_name) <= 120),
    ADD COLUMN representative_role text CHECK (char_length(representative_role) <= 120),
    ADD COLUMN representative_signature_key text;
CREATE INDEX ix_prevention_visit_inspector ON org.prevention_visit (inspector_subject)
    WHERE status IN ('scheduled', 'inspected');

CREATE TABLE org.prevention_photo (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    visit_id            uuid NOT NULL REFERENCES org.prevention_visit(id) ON DELETE CASCADE,
    org_id              uuid NOT NULL REFERENCES org.organization(id) ON DELETE CASCADE,
    item_key            text CHECK (char_length(item_key) <= 60),
    object_key          text NOT NULL,
    sha256              text NOT NULL,
    bytes               integer NOT NULL CHECK (bytes > 0),
    content_type        text NOT NULL,
    client_id           uuid NOT NULL UNIQUE,
    created_by          text NOT NULL,
    created_by_name     text,
    device_at           timestamptz,
    created_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_prevention_photo_visit ON org.prevention_photo (visit_id, created_at);
"""

DOWNGRADE = """
DROP TABLE org.prevention_photo;
DROP INDEX org.ix_prevention_visit_inspector;
ALTER TABLE org.prevention_visit
    DROP COLUMN inspector_subject,
    DROP COLUMN inspection_client_id,
    DROP COLUMN inspected_device_at,
    DROP COLUMN inspector_signature_key,
    DROP COLUMN representative_name,
    DROP COLUMN representative_role,
    DROP COLUMN representative_signature_key;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
