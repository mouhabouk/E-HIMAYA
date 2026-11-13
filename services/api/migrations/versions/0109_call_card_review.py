"""Follow-ups of the guided call-taking cards (OS2-3, OS2-4; Yamen 2026-11-13; docs/phase-os2b/design-os2b.md).

* ``reports.report.entered_room``: the room that wrote a report down (``central`` or ``g:<code>``), and
  ``entry_started_at``, when its agent opened the intake form. With the phone's call (answered to ended) they give the
  statistics of card use and call time per room. Reports entered before this migration fall back on their claimed room.
* ``reports.call_card``: the review of a draft. ``submitted_at`` when the Office hands it to the doctor or the room
  manager, ``returned_*`` when one of them sends it back with a note, ``unchanged`` when the Office confirmed the
  [SIM] text as it is, ``notes`` the reviewer's note per question (``_card`` for the whole card).
* ``reports.call_card_reviewer``: who reviews each card (the Office's reviewer, the doctor), as names.

Revision ID: 0109_call_card_review
Revises: 0107_par
Create Date: 2026-11-13
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0109_call_card_review"
down_revision: str | None = "0107_par"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = r"""
ALTER TABLE reports.report
    ADD COLUMN entered_room text CHECK (entered_room ~ '^(central|g:[0-9]{1,3})$'),
    ADD COLUMN entry_started_at timestamptz;

ALTER TABLE reports.call_card
    ADD COLUMN submitted_at      timestamptz,
    ADD COLUMN submitted_by_name text,
    ADD COLUMN returned_at       timestamptz,
    ADD COLUMN returned_by_name  text,
    ADD COLUMN returned_reason   text CHECK (char_length(returned_reason) <= 500),
    ADD COLUMN unchanged         boolean NOT NULL DEFAULT false,
    ADD COLUMN notes             jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE reports.call_card_reviewer (
    category        text PRIMARY KEY CHECK (category IN ('sos', 'fire', 'flood', 'traffic_accident', 'drowning',
                                                         'landslide', 'chemical_leak', 'medical', 'other')),
    office          text CHECK (char_length(office) <= 200),
    doctor          text CHECK (char_length(doctor) <= 200),
    updated_by_name text,
    updated_at      timestamptz NOT NULL DEFAULT now()
);
SELECT audit.journal_attach('reports.call_card_reviewer'::regclass, false);
"""

DOWNGRADE = r"""
DROP TABLE reports.call_card_reviewer;
ALTER TABLE reports.call_card
    DROP COLUMN notes, DROP COLUMN unchanged, DROP COLUMN returned_reason, DROP COLUMN returned_by_name,
    DROP COLUMN returned_at, DROP COLUMN submitted_by_name, DROP COLUMN submitted_at;
ALTER TABLE reports.report DROP COLUMN entry_started_at, DROP COLUMN entered_room;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
