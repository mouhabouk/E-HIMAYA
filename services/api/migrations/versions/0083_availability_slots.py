"""Availability calendar of volunteers and doctors (phase N, docs/phase-n/design-n.md §8).

A volunteer or a doctor tells, from the app, when they are available and when they are not: every day between two
dates, or on some weekdays only, between two hours (an end before the start runs past midnight). The call-up does
not suggest a volunteer whose calendar says unavailable now; the staff read the calendar on the person's page.
``identity.planned_state`` is the rule of ``app.modules.availability.domain.planned_state`` in SQL.

Revision ID: 0083_availability_slots
Revises: 0082_room_intake
Create Date: 2026-10-30
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0083_availability_slots"
down_revision: str | None = "0082_room_intake"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = """
CREATE TABLE identity.availability_slot (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     uuid NOT NULL REFERENCES identity.account(user_id) ON DELETE CASCADE,
    role        text NOT NULL CHECK (role IN ('volunteer', 'doctor')),
    kind        text NOT NULL CHECK (kind IN ('available', 'unavailable')),
    weekdays    smallint[] NOT NULL DEFAULT '{}' CHECK (weekdays <@ ARRAY[1, 2, 3, 4, 5, 6, 7]::smallint[]),
    starts_on   date NOT NULL,
    ends_on     date CHECK (ends_on IS NULL OR ends_on >= starts_on),
    from_time   time NOT NULL,
    to_time     time NOT NULL CHECK (to_time <> from_time),
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_availability_slot_user ON identity.availability_slot (user_id, role);

CREATE FUNCTION identity.planned_state(p_user uuid, p_role text, p_at timestamptz) RETURNS text
LANGUAGE sql STABLE AS $$
    WITH here AS (SELECT (p_at AT TIME ZONE 'Africa/Tunis') AS t),
    covering AS (
        SELECT s.kind
        FROM identity.availability_slot s, here
        WHERE s.user_id = p_user AND s.role = p_role
          AND here.t::date >= s.starts_on
          AND (s.ends_on IS NULL OR here.t::date <= s.ends_on)
          AND (cardinality(s.weekdays) = 0 OR extract(isodow FROM here.t)::smallint = ANY (s.weekdays))
          AND CASE WHEN s.from_time <= s.to_time
                   THEN here.t::time >= s.from_time AND here.t::time < s.to_time
                   ELSE here.t::time >= s.from_time OR here.t::time < s.to_time END
    )
    SELECT CASE
        WHEN EXISTS (SELECT 1 FROM covering WHERE kind = 'unavailable') THEN 'unavailable'
        WHEN EXISTS (SELECT 1 FROM covering WHERE kind = 'available') THEN 'available'
    END
$$;
"""

DOWNGRADE = """
DROP FUNCTION identity.planned_state(uuid, text, timestamptz);
DROP TABLE identity.availability_slot;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
