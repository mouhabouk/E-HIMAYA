"""Address warnings follow-ups OS8-1 to OS8-3 (Yamen, 2026-11-13; docs/phase-os8/design-os8.md §8 to §10).

* ``aw.reveal``: how the owner was told that a room read their name (``notified_via``: push or sms, none when the
  account has neither a device nor a phone), and the owner's objection («لا علم لي بأي بلاغ عندي») with its time and
  an optional note. The owner reads their own rows (policy of 0103); the objection is written by the API for them.
* ``aw.marker``: a field check asked from the review reminder (when and by whom); cleared by a confirm or an archive.
* ``aw.reminder_day``: one row per gouvernorat and day once the morning review reminder went to its room (08:00), so
  that several worker processes send it once.

Revision ID: 0108_aw_followups
Revises: 0107_par
Create Date: 2026-11-13
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0108_aw_followups"
down_revision: str | None = "0107_par"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OWN = "ehimaya.sees_all() OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat())"

UPGRADE = f"""
ALTER TABLE aw.reveal
    ADD COLUMN notified_via text CHECK (notified_via IN ('push', 'sms')),
    ADD COLUMN disputed_at  timestamptz,
    ADD COLUMN dispute_note text CHECK (char_length(dispute_note) <= 300);
CREATE INDEX ix_reveal_disputed ON aw.reveal (gouvernorat_code) WHERE disputed_at IS NOT NULL;

ALTER TABLE aw.marker
    ADD COLUMN check_requested_at      timestamptz,
    ADD COLUMN check_requested_by_name text CHECK (char_length(check_requested_by_name) <= 200);

CREATE TABLE aw.reminder_day (
    gouvernorat_code smallint NOT NULL REFERENCES geo.gouvernorat(code),
    day              date NOT NULL,
    late             integer NOT NULL,
    soon             integer NOT NULL,
    at               timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (gouvernorat_code, day)
);
ALTER TABLE aw.reminder_day ENABLE ROW LEVEL SECURITY;
CREATE POLICY reminder_day_own ON aw.reminder_day USING ({_OWN}) WITH CHECK ({_OWN});
"""

DOWNGRADE = """
DROP TABLE aw.reminder_day;
ALTER TABLE aw.marker DROP COLUMN check_requested_by_name, DROP COLUMN check_requested_at;
DROP INDEX aw.ix_reveal_disputed;
ALTER TABLE aw.reveal DROP COLUMN dispute_note, DROP COLUMN disputed_at, DROP COLUMN notified_via;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
