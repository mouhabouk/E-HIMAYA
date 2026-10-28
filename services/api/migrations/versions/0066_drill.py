"""The digital dry run (L5a, docs/phase-l/design-l5.md §2): a written scenario of timed injects, played to the rooms of
the gouvernorats that approved it, answered with the resources of the real register (booked inside the dry run only),
then evaluated by an independent evaluator.

* ``drill.exercise``: the dry run, its gouvernorats, its plan and evaluator, its state and its limits.
* ``drill.participant``: the approval of each gouvernorat's room (approved, refused, withdrawn) with its reason.
* ``drill.inject``: a timed message of the scenario (minutes from the start), with the resources it needs and the
  expected answer.
* ``drill.response``: a room's answer to an inject, and the resources it booked for it (``drill.booking``).
* ``drill.evaluation``: the evaluator's mark on an inject.
* ``drill.stress_run``: the results of a load run against the isolated copy (report volume and attack payloads).

Nothing here is a report, an incident or an axis: a dry run never reaches the statistics, the window or a citizen.
Read and written through the system scope by the drill service after its own checks.

Revision ID: 0066_drill
Revises: 0065_decision_window
Create Date: 2026-10-28
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0066_drill"
down_revision: str | None = "0065_decision_window"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = """
CREATE SCHEMA IF NOT EXISTS drill;

CREATE TABLE drill.exercise (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title            text NOT NULL CHECK (length(title) BETWEEN 3 AND 160),
    objective        text NOT NULL CHECK (length(objective) BETWEEN 3 AND 2000),
    hazard_key       text CHECK (hazard_key IS NULL OR length(hazard_key) <= 40),
    plan_document_id uuid,
    gouvernorats     smallint[] NOT NULL CHECK (cardinality(gouvernorats) BETWEEN 1 AND 24),
    room             text NOT NULL,
    planned_start    timestamptz NOT NULL,
    duration_min     smallint NOT NULL CHECK (duration_min BETWEEN 10 AND 720),
    evaluator        text,
    evaluator_name   text,
    status           text NOT NULL DEFAULT 'draft'
                     CHECK (status IN ('draft', 'submitted', 'ready', 'running', 'stopped', 'ended', 'closed')),
    started_at       timestamptz,
    ended_at         timestamptz,
    stop_reason      text,
    stopped_by_name  text,
    resources_at_start jsonb NOT NULL DEFAULT '{}',
    conclusion       text CHECK (conclusion IS NULL OR length(conclusion) <= 4000),
    created_by       text NOT NULL,
    created_by_name  text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_exercise_status ON drill.exercise (status);

CREATE TABLE drill.participant (
    exercise_id      uuid NOT NULL REFERENCES drill.exercise(id) ON DELETE CASCADE,
    gouvernorat_code smallint NOT NULL REFERENCES geo.gouvernorat(code),
    decision         text NOT NULL DEFAULT 'pending'
                     CHECK (decision IN ('pending', 'approved', 'refused', 'withdrawn')),
    reason           text CHECK (reason IS NULL OR length(reason) <= 500),
    decided_by_name  text,
    decided_at       timestamptz,
    PRIMARY KEY (exercise_id, gouvernorat_code)
);

CREATE TABLE drill.inject (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    exercise_id      uuid NOT NULL REFERENCES drill.exercise(id) ON DELETE CASCADE,
    offset_min       smallint NOT NULL CHECK (offset_min BETWEEN 0 AND 720),
    gouvernorat_code smallint REFERENCES geo.gouvernorat(code),
    kind             text NOT NULL
                     CHECK (kind IN ('report', 'development', 'shortage', 'evacuation', 'decision', 'information')),
    title            text NOT NULL CHECK (length(title) BETWEEN 3 AND 200),
    body             text NOT NULL DEFAULT '' CHECK (length(body) <= 2000),
    needs            jsonb NOT NULL DEFAULT '{}',
    expected         text NOT NULL DEFAULT '' CHECK (length(expected) <= 2000),
    generated        boolean NOT NULL DEFAULT false,
    created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_inject_exercise ON drill.inject (exercise_id, offset_min);

CREATE TABLE drill.response (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    inject_id        uuid NOT NULL REFERENCES drill.inject(id) ON DELETE CASCADE,
    gouvernorat_code smallint NOT NULL REFERENCES geo.gouvernorat(code),
    action           text NOT NULL
                     CHECK (action IN ('acknowledged', 'dispatched', 'escalated', 'evacuation', 'decision', 'note')),
    text             text NOT NULL DEFAULT '' CHECK (length(text) <= 2000),
    responded_by     text NOT NULL,
    responded_by_name text,
    responded_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_response_inject ON drill.response (inject_id);

CREATE TABLE drill.booking (
    exercise_id      uuid NOT NULL REFERENCES drill.exercise(id) ON DELETE CASCADE,
    resource_id      uuid NOT NULL REFERENCES ops.resource(id) ON DELETE CASCADE,
    response_id      uuid NOT NULL REFERENCES drill.response(id) ON DELETE CASCADE,
    kind             text NOT NULL,
    gouvernorat_code smallint NOT NULL REFERENCES geo.gouvernorat(code),
    booked_at        timestamptz NOT NULL DEFAULT now(),
    released_at      timestamptz,
    PRIMARY KEY (exercise_id, resource_id, booked_at)
);
-- A resource serves one inject at a time inside a dry run; never touched outside it.
CREATE UNIQUE INDEX ux_booking_open ON drill.booking (exercise_id, resource_id) WHERE released_at IS NULL;

CREATE TABLE drill.evaluation (
    inject_id        uuid PRIMARY KEY REFERENCES drill.inject(id) ON DELETE CASCADE,
    plan_followed    text NOT NULL CHECK (plan_followed IN ('yes', 'partly', 'no', 'not_applicable')),
    score            smallint NOT NULL CHECK (score BETWEEN 0 AND 5),
    notes            text NOT NULL DEFAULT '' CHECK (length(notes) <= 2000),
    evaluated_by_name text,
    evaluated_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE drill.stress_run (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    exercise_id      uuid NOT NULL REFERENCES drill.exercise(id) ON DELETE CASCADE,
    environment      text NOT NULL CHECK (environment IN ('isolated')),
    results          jsonb NOT NULL,
    recorded_by_name text,
    recorded_at      timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE drill.exercise ENABLE ROW LEVEL SECURITY;
CREATE POLICY exercise_system ON drill.exercise
    USING (ehimaya.scope() = 'system') WITH CHECK (ehimaya.scope() = 'system');
ALTER TABLE drill.participant ENABLE ROW LEVEL SECURITY;
CREATE POLICY participant_system ON drill.participant
    USING (ehimaya.scope() = 'system') WITH CHECK (ehimaya.scope() = 'system');
ALTER TABLE drill.inject ENABLE ROW LEVEL SECURITY;
CREATE POLICY inject_system ON drill.inject
    USING (ehimaya.scope() = 'system') WITH CHECK (ehimaya.scope() = 'system');
ALTER TABLE drill.response ENABLE ROW LEVEL SECURITY;
CREATE POLICY response_system ON drill.response
    USING (ehimaya.scope() = 'system') WITH CHECK (ehimaya.scope() = 'system');
ALTER TABLE drill.booking ENABLE ROW LEVEL SECURITY;
CREATE POLICY booking_system ON drill.booking
    USING (ehimaya.scope() = 'system') WITH CHECK (ehimaya.scope() = 'system');
ALTER TABLE drill.evaluation ENABLE ROW LEVEL SECURITY;
CREATE POLICY evaluation_system ON drill.evaluation
    USING (ehimaya.scope() = 'system') WITH CHECK (ehimaya.scope() = 'system');
ALTER TABLE drill.stress_run ENABLE ROW LEVEL SECURITY;
CREATE POLICY stress_run_system ON drill.stress_run
    USING (ehimaya.scope() = 'system') WITH CHECK (ehimaya.scope() = 'system');
"""

DOWNGRADE = """
DROP SCHEMA drill CASCADE;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
