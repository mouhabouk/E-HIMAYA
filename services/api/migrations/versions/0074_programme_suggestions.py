"""Suggested activities in the programmes (AI3, docs/phase-l/design-l5.md §4.3).

* ``sched.item.suggestion_key``: the suggestion an activity was accepted from (fire danger on a day, red beaches,
  heavy rain, the season, a rise). Such an activity carries the AI label until it is approved like any other.
* ``sched.suggestion_dismissal``: a suggestion the room set aside for one programme, with its reason; it is not
  offered again for that programme.

Revision ID: 0074_programme_suggestions
Revises: 0073_model_cards
Create Date: 2026-10-29
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0074_programme_suggestions"
down_revision: str | None = "0073_model_cards"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OWN = "ehimaya.sees_all() OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat())"

UPGRADE = f"""
ALTER TABLE sched.item ADD COLUMN suggestion_key text CHECK (char_length(suggestion_key) BETWEEN 3 AND 80);

CREATE TABLE sched.suggestion_dismissal (
    period_id        uuid NOT NULL REFERENCES sched.period(id) ON DELETE CASCADE,
    key              text NOT NULL CHECK (char_length(key) BETWEEN 3 AND 80),
    gouvernorat_code smallint NOT NULL REFERENCES geo.gouvernorat(code),
    reason           text NOT NULL DEFAULT '' CHECK (char_length(reason) <= 300),
    dismissed_by_name text,
    dismissed_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (period_id, key)
);

ALTER TABLE sched.suggestion_dismissal ENABLE ROW LEVEL SECURITY;
CREATE POLICY suggestion_dismissal_all ON sched.suggestion_dismissal USING ({_OWN}) WITH CHECK ({_OWN});
"""

DOWNGRADE = """
DROP TABLE sched.suggestion_dismissal;
ALTER TABLE sched.item DROP COLUMN suggestion_key;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
