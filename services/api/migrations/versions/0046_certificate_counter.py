"""Certificate upgrade: renewal reminders and stamps at the counter of a regional administration (phase P3a,
docs/phase-p3/design-certificates.md §3).

* ``org.certificate.reminded_90_on`` / ``reminded_30_on``: the renewal e-mails already sent, one per threshold.
* ``org.certificate_stamp``: a paper certificate stamped by hand by an agent, with the place, the date, an optional
  photo of the stamped paper and the comparison with the institution at that moment.

Revision ID: 0046_certificate_counter
Revises: 0045_org_alerts_activities
Create Date: 2026-10-25
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0046_certificate_counter"
down_revision: str | None = "0045_org_alerts_activities"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = """
ALTER TABLE org.certificate ADD COLUMN reminded_90_on date;
ALTER TABLE org.certificate ADD COLUMN reminded_30_on date;

CREATE TABLE org.certificate_stamp (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    certificate_id      uuid NOT NULL REFERENCES org.certificate(id) ON DELETE CASCADE,
    place               text NOT NULL CHECK (char_length(place) BETWEEN 1 AND 200),
    gouvernorat_code    integer,
    stamped_on          date NOT NULL,
    note                text CHECK (char_length(note) <= 500),
    stamped_by          text NOT NULL,
    stamped_by_name     text,
    recorded_at         timestamptz NOT NULL DEFAULT now(),
    changes             jsonb NOT NULL DEFAULT '[]',
    photo_object_key    text,
    photo_sha256        text CHECK (photo_sha256 ~ '^[0-9a-f]{64}$'),
    photo_content_type  text CHECK (photo_content_type IN ('image/jpeg', 'image/png')),
    CHECK ((photo_object_key IS NULL) = (photo_sha256 IS NULL))
);
CREATE INDEX ix_certificate_stamp_certificate ON org.certificate_stamp (certificate_id, stamped_on DESC);
"""

DOWNGRADE = """
DROP TABLE org.certificate_stamp;
ALTER TABLE org.certificate DROP COLUMN reminded_30_on;
ALTER TABLE org.certificate DROP COLUMN reminded_90_on;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
