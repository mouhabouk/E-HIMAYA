"""AI layer 1: analysis pipeline state, scoring settings, incident grouping.

Revision ID: 0005_ai_layer
Revises: 0004_reporting_flow
Create Date: 2026-10-19
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0005_ai_layer"
down_revision: str | None = "0004_reporting_flow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE = r"""
-- ===================== ai: analysis of each report =====================
-- Durable work queue: a row is (re)queued in the same transaction as the report or the media that needs
-- analysis, so no report is ever left unanalysed when a model or the bus is down (architecture §6.1).
CREATE SCHEMA IF NOT EXISTS ai;
CREATE TABLE ai.analysis (
    report_id        uuid PRIMARY KEY REFERENCES reports.report(id) ON DELETE CASCADE,
    state            text NOT NULL DEFAULT 'pending'
                     CHECK (state IN ('pending', 'running', 'done', 'failed')),
    generation       integer NOT NULL DEFAULT 1,      -- bumped when new input (media) arrives
    attempts         smallint NOT NULL DEFAULT 0,
    next_attempt_at  timestamptz NOT NULL DEFAULT now(),
    lease_until      timestamptz,
    last_error       text,
    language         text,
    steps            jsonb NOT NULL DEFAULT '{}'::jsonb,
    extraction       jsonb,
    priority         jsonb,
    credibility      jsonb,
    suggestion       jsonb,
    dismissed        jsonb NOT NULL DEFAULT '[]'::jsonb,   -- suggestion targets the operator turned down
    models           jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    completed_at     timestamptz
);
CREATE INDEX ix_analysis_due ON ai.analysis (next_attempt_at) WHERE state = 'pending';
CREATE INDEX ix_analysis_running ON ai.analysis (lease_until) WHERE state = 'running';

-- Weights and thresholds of BR-10 and BR-20, editable from the dashboard (one row).
CREATE TABLE ai.settings (
    id          smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    value       jsonb NOT NULL,
    updated_by  text NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now()
);

-- Reports sorted by priority inside a scope (FR-C-11).
CREATE INDEX ix_report_priority ON reports.report (priority_score DESC NULLS LAST, received_at DESC, id DESC);
ALTER TABLE reports.report
    ADD CONSTRAINT ck_report_priority CHECK (priority_score BETWEEN 0 AND 100),
    ADD CONSTRAINT ck_report_credibility CHECK (credibility_score BETWEEN 0 AND 100);

-- ===================== ops: incidents grouping reports (FR-C-02, BR-10, BR-11) =====================
ALTER TABLE ops.incident
    ADD COLUMN merged_into  uuid REFERENCES ops.incident(id),
    ADD COLUMN updated_at   timestamptz NOT NULL DEFAULT now(),
    ADD CONSTRAINT ck_incident_status CHECK (status IN ('open', 'closed', 'merged', 'dissolved')),
    ADD CONSTRAINT ck_incident_category CHECK (
        category IN ('sos', 'fire', 'flood', 'traffic_accident', 'drowning', 'landslide',
                     'chemical_leak', 'medical', 'other'));
"""

DOWNGRADE = r"""
ALTER TABLE ops.incident
    DROP CONSTRAINT ck_incident_category,
    DROP CONSTRAINT ck_incident_status,
    DROP COLUMN updated_at,
    DROP COLUMN merged_into;

ALTER TABLE reports.report
    DROP CONSTRAINT ck_report_credibility,
    DROP CONSTRAINT ck_report_priority;
DROP INDEX reports.ix_report_priority;

DROP SCHEMA ai CASCADE;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
