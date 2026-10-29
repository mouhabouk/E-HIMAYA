"""Model cards and the drowning risk model kept in shadow (L5, docs/phase-l/design-l5.md §4.1 and §4.2).

* ``ai.model_decision``: what the committee decided about a model (AI-01): its thresholds approved, or that approval
  withdrawn, with the reference of the minutes. Append-only: the latest row of a model is its standing.
* ``coastal.risk_model``: one trained version of the drowning risk model (scikit-learn, on [SIM] data), stored as
  plain coefficients (no pickle), with the measures taken when it was trained.
* ``coastal.beach_day``: the shadow probability and level of that model beside the declared rules, for comparison
  day by day. Never shown to the public and never used to open an alert.

Revision ID: 0073_model_cards
Revises: 0072_plan_checklist
Create Date: 2026-10-29
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0073_model_cards"
down_revision: str | None = "0072_plan_checklist"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = """
CREATE TABLE ai.model_decision (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    model            text NOT NULL CHECK (char_length(model) BETWEEN 1 AND 40),
    decision         text NOT NULL CHECK (decision IN ('approved', 'withdrawn')),
    -- The thresholds and the version the decision is about, as the card showed them.
    thresholds       jsonb NOT NULL DEFAULT '{}',
    version          text NOT NULL CHECK (char_length(version) BETWEEN 1 AND 80),
    reference        text NOT NULL CHECK (char_length(reference) BETWEEN 3 AND 200),
    note             text NOT NULL DEFAULT '' CHECK (char_length(note) <= 500),
    decided_by_name  text NOT NULL,
    decided_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_model_decision_model ON ai.model_decision (model, decided_at DESC);

ALTER TABLE ai.model_decision ENABLE ROW LEVEL SECURITY;
CREATE POLICY model_decision_select ON ai.model_decision FOR SELECT USING (ehimaya.sees_all());
CREATE POLICY model_decision_insert ON ai.model_decision FOR INSERT WITH CHECK (ehimaya.sees_all());

CREATE TABLE coastal.risk_model (
    version          integer PRIMARY KEY CHECK (version > 0),
    algorithm        text NOT NULL,
    -- Feature names, coefficients, intercept and the probability cut-offs of the levels.
    params           jsonb NOT NULL,
    metrics          jsonb NOT NULL,
    simulated        boolean NOT NULL DEFAULT true,
    seed             integer NOT NULL,
    trained_by_name  text NOT NULL,
    trained_at       timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE coastal.risk_model ENABLE ROW LEVEL SECURITY;
CREATE POLICY risk_model_select ON coastal.risk_model FOR SELECT USING (true);
CREATE POLICY risk_model_insert ON coastal.risk_model FOR INSERT WITH CHECK (ehimaya.sees_all());

ALTER TABLE coastal.beach_day
    ADD COLUMN shadow_p       double precision CHECK (shadow_p BETWEEN 0 AND 1),
    ADD COLUMN shadow_level   text CHECK (shadow_level IN ('green', 'yellow', 'red')),
    ADD COLUMN shadow_version integer;
"""

DOWNGRADE = """
ALTER TABLE coastal.beach_day DROP COLUMN shadow_version, DROP COLUMN shadow_level, DROP COLUMN shadow_p;
DROP TABLE coastal.risk_model;
DROP TABLE ai.model_decision;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
