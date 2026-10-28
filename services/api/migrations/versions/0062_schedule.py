"""Daily, weekly and monthly programmes of every gouvernorat (phase PL2, docs/phase-pl/design-plans.md §3).

* ``sched.setting``: how a gouvernorat approves its programmes (published directly, by the head of the room, or by the
  head of the room then the central room). Each gouvernorat chooses; without a row, the head of the room approves.
* ``sched.period``: one programme of a gouvernorat for a day, a week (from Monday) or a month (from the 1st), with its
  approval path (kept when it is sent, so a later change of the setting does not change a programme under way).
* ``sched.item``: an activity of the programme (duty, patrol, exercise, prevention visit, maintenance…), its day and
  hours, unit, place, person in charge, staff and resources, the plan it follows, and its follow-up (done, postponed
  or cancelled, with the reason).

Each gouvernorat reads and writes its own programmes; the central room all of them.

Revision ID: 0062_schedule
Revises: 0061_plan_hazards
Create Date: 2026-10-28
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0062_schedule"
down_revision: str | None = "0061_plan_hazards"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OWN = "ehimaya.sees_all() OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat())"
_APPROVALS = "'direct', 'head', 'head_and_centre'"

UPGRADE = f"""
CREATE SCHEMA IF NOT EXISTS sched;

CREATE TABLE sched.setting (
    gouvernorat_code smallint PRIMARY KEY REFERENCES geo.gouvernorat(code),
    approval         text NOT NULL CHECK (approval IN ({_APPROVALS})),
    updated_by       text,
    updated_by_name  text,
    updated_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE sched.period (
    id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    gouvernorat_code       smallint NOT NULL REFERENCES geo.gouvernorat(code),
    span                   text NOT NULL CHECK (span IN ('day', 'week', 'month')),
    starts_on              date NOT NULL,
    ends_on                date NOT NULL CHECK (ends_on >= starts_on),
    status                 text NOT NULL DEFAULT 'draft'
                           CHECK (status IN ('draft', 'submitted', 'awaiting_centre', 'approved', 'returned')),
    approval               text CHECK (approval IN ({_APPROVALS})),
    notes                  text NOT NULL DEFAULT '',
    return_reason          text,
    submitted_by_name      text,
    submitted_at           timestamptz,
    approved_by_name       text,
    approved_at            timestamptz,
    centre_approved_by_name text,
    centre_approved_at     timestamptz,
    version                integer NOT NULL DEFAULT 1,
    created_by             text,
    created_by_name        text,
    created_at             timestamptz NOT NULL DEFAULT now(),
    updated_by_name        text,
    updated_at             timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_period UNIQUE (gouvernorat_code, span, starts_on)
);
CREATE INDEX ix_period_dates ON sched.period (starts_on, ends_on);

CREATE TABLE sched.item (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    period_id        uuid NOT NULL REFERENCES sched.period(id) ON DELETE CASCADE,
    gouvernorat_code smallint NOT NULL REFERENCES geo.gouvernorat(code),
    series_id        uuid,
    activity         text NOT NULL,
    title            text NOT NULL,
    on_date          date NOT NULL,
    starts_at        time,
    ends_at          time,
    unit_id          uuid REFERENCES ops.unit(id),
    place            text NOT NULL DEFAULT '',
    responsible      text NOT NULL DEFAULT '',
    staff_count      integer CHECK (staff_count IS NULL OR staff_count BETWEEN 0 AND 10000),
    resources        jsonb NOT NULL DEFAULT '[]',
    plan_document_id uuid REFERENCES register.document(id),
    notes            text NOT NULL DEFAULT '',
    status           text NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'done', 'postponed', 'cancelled')),
    status_reason    text,
    status_by_name   text,
    status_at        timestamptz,
    created_by_name  text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_item_hours CHECK (ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at)
);
CREATE INDEX ix_item_period ON sched.item (period_id, on_date, starts_at);
CREATE INDEX ix_item_series ON sched.item (series_id) WHERE series_id IS NOT NULL;

ALTER TABLE sched.setting ENABLE ROW LEVEL SECURITY;
CREATE POLICY setting_select ON sched.setting FOR SELECT USING (true);
CREATE POLICY setting_write ON sched.setting FOR INSERT WITH CHECK ({_OWN});
CREATE POLICY setting_update ON sched.setting FOR UPDATE USING ({_OWN}) WITH CHECK ({_OWN});
ALTER TABLE sched.period ENABLE ROW LEVEL SECURITY;
CREATE POLICY period_all ON sched.period USING ({_OWN}) WITH CHECK ({_OWN});
ALTER TABLE sched.item ENABLE ROW LEVEL SECURITY;
CREATE POLICY item_all ON sched.item USING ({_OWN}) WITH CHECK ({_OWN});
"""

DOWNGRADE = """
DROP TABLE sched.item;
DROP TABLE sched.period;
DROP TABLE sched.setting;
DROP SCHEMA sched;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
