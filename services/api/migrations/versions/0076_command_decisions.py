"""The commander's assistant: memory of proposed decisions and of what the commander did with them (AI5a,
docs/phase-ai5/design-ai5.md §3).

``decision.command_decision``: one proposal shown to a commander on an incident, either from the rules of decision
support (``origin = 'rules'``) or from an order the commander typed or dictated (``origin = 'order'``), with a snapshot
of the situation it was made in (``features``: the figures the rules read, no names, phone numbers or citizens'
words). The commander adopts it, adopts it modified, or rejects it with a reason; the row then keeps who decided, when,
what was finally kept and why. Adopting never executes anything: it opens the existing flow (assignment order, alert
form, call, route), where the usual confirmation and role checks apply. ``outcome`` is filled when the incident is
closed (AI5c). These rows are what the assistant learns from: how often commanders adopt each kind of proposal in
similar situations.

Rows follow the incident's visibility (row-level security, like the incident timeline).

Revision ID: 0076_command_decisions
Revises: 0075_anomalies
Create Date: 2026-10-29
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0076_command_decisions"
down_revision: str | None = "0075_anomalies"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INCIDENT = "EXISTS (SELECT 1 FROM ops.incident i WHERE i.id = incident_id)"

UPGRADE = f"""
CREATE TABLE decision.command_decision (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id      uuid NOT NULL REFERENCES ops.incident(id) ON DELETE CASCADE,
    origin           text NOT NULL CHECK (origin IN ('rules', 'order')),
    kind             text NOT NULL CHECK (kind IN ('resources', 'volunteers', 'route', 'escalation', 'alert',
                                                   'responders', 'note')),
    -- What the proposal is about, stable across refreshes: "resources:fire_engine", "escalation:crisis", ...
    key              text NOT NULL CHECK (char_length(key) BETWEEN 3 AND 80),
    title            jsonb NOT NULL,
    rationale        jsonb NOT NULL,
    confidence       text NOT NULL CHECK (confidence IN ('low', 'medium', 'high')),
    proposal         jsonb NOT NULL,
    features         jsonb NOT NULL DEFAULT '{{}}'::jsonb,
    command_text     text CHECK (char_length(command_text) <= 1000),
    lang             text CHECK (lang IN ('ar', 'fr')),
    model            text,
    simulated        boolean NOT NULL DEFAULT false,
    status           text NOT NULL DEFAULT 'proposed'
                         CHECK (status IN ('proposed', 'adopted', 'modified', 'rejected', 'expired')),
    final            jsonb,
    reason_code      text CHECK (reason_code IN ('not_needed', 'already_done', 'wrong_resource', 'too_slow',
                                                 'unsafe', 'wrong_reading', 'other')),
    reason_text      text CHECK (char_length(reason_text) <= 500),
    created_by       text NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    decided_by       text,
    decided_by_name  text,
    decided_at       timestamptz,
    outcome          jsonb,
    CONSTRAINT ck_command_decision_decided CHECK (
        (status IN ('proposed', 'expired')) = (decided_at IS NULL)),
    CONSTRAINT ck_command_decision_reason CHECK (status <> 'rejected' OR reason_code IS NOT NULL),
    CONSTRAINT ck_command_decision_order CHECK (origin <> 'order' OR command_text IS NOT NULL)
);
CREATE INDEX ix_command_decision_incident ON decision.command_decision (incident_id, created_at DESC);
CREATE INDEX ix_command_decision_learning ON decision.command_decision (key, status) WHERE decided_at IS NOT NULL;
-- At most one open proposal per incident and subject.
CREATE UNIQUE INDEX uq_command_decision_open ON decision.command_decision (incident_id, key)
    WHERE status = 'proposed' AND origin = 'rules';

ALTER TABLE decision.command_decision ENABLE ROW LEVEL SECURITY;
CREATE POLICY command_decision_all ON decision.command_decision USING ({_INCIDENT}) WITH CHECK ({_INCIDENT});
"""

DOWNGRADE = """
DROP TABLE decision.command_decision;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
