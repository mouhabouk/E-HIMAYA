"""Local self-learning from the reports (docs/learning.md).

``ai.learning_sample``: one anonymised, encrypted text per source (a closed or rejected report now; the commander's
decisions and orders later, AI5c) with its labels: weak ones read from the system (the citizen's category, the
language model's reading, the final status) or confirmed by a person (the operator, the commander). The split
(train / heldout) is fixed from a hash of ``group_key`` (or ``source_id``) so a sample never changes side.

``ai.learning_model``: each trained version of a task's model, as plain numbers (no pickle), with its figures on
the heldout samples. A version becomes ``current`` only when it beats the current one on the same heldout samples;
it stays in shadow: nothing it predicts changes a report until the committee decides otherwise (AI-01).

``ai.training_job``: the trainings the system administrator launches from the training centre, or the schedule
launches (setting ``learning.schedule``): queued, run by the worker (text models, new Derja words, the fire and smoke
image set), and their result. A training that needs a GPU (fire and smoke detector) waits for the trainer.

Revision ID: 0076_learning
Revises: 0075_anomalies
Create Date: 2026-10-29
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0076_learning"
down_revision: str | None = "0075_anomalies"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Operators of a gouvernorat confirm the reading of their reports; the AI administrator (national) reads and trains.
_STAFF = "ehimaya.sees_all() OR ehimaya.regional()"

UPGRADE = f"""
CREATE TABLE ai.learning_sample (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source        text NOT NULL CHECK (source ~ '^[a-z_]{{2,30}}$'),
    source_id     text NOT NULL CHECK (char_length(source_id) BETWEEN 1 AND 80),
    group_key     text CHECK (char_length(group_key) BETWEEN 1 AND 80),
    text_enc      bytea NOT NULL,
    label         jsonb NOT NULL DEFAULT '{{}}',
    label_origin  text NOT NULL CHECK (label_origin IN ('weak', 'operator', 'commander')),
    split         text NOT NULL CHECK (split IN ('train', 'heldout')),
    labelled_by   text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_learning_sample UNIQUE (source, source_id)
);
CREATE INDEX ix_learning_sample_source ON ai.learning_sample (source, updated_at DESC);

CREATE TABLE ai.learning_model (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task            text NOT NULL CHECK (task ~ '^[a-z_]{{2,40}}$'),
    version         integer NOT NULL CHECK (version > 0),
    algorithm       text NOT NULL,
    params          jsonb NOT NULL,
    metrics         jsonb NOT NULL,
    primary_metric  text NOT NULL,
    state           text NOT NULL CHECK (state IN ('current', 'retired', 'rejected')),
    train_samples   integer NOT NULL CHECK (train_samples >= 0),
    heldout_samples integer NOT NULL CHECK (heldout_samples >= 0),
    trained_by_name text NOT NULL,
    trained_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_learning_model UNIQUE (task, version)
);
CREATE UNIQUE INDEX uq_learning_model_current ON ai.learning_model (task) WHERE state = 'current';

CREATE TABLE ai.training_job (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task              text NOT NULL CHECK (task ~ '^[a-z_]{{2,40}}$'),
    trigger           text NOT NULL CHECK (trigger IN ('manual', 'schedule')),
    state             text NOT NULL DEFAULT 'queued'
                      CHECK (state IN ('queued', 'running', 'done', 'skipped', 'failed', 'waiting_trainer')),
    requested_by      text NOT NULL,
    requested_by_name text NOT NULL,
    requested_at      timestamptz NOT NULL DEFAULT now(),
    started_at        timestamptz,
    finished_at       timestamptz,
    result            jsonb NOT NULL DEFAULT '{{}}',
    error             text,
    model_id          uuid REFERENCES ai.learning_model(id) ON DELETE SET NULL
);
CREATE INDEX ix_training_job_task ON ai.training_job (task, requested_at DESC);
CREATE INDEX ix_training_job_queued ON ai.training_job (requested_at) WHERE state = 'queued';

ALTER TABLE ai.learning_sample ENABLE ROW LEVEL SECURITY;
CREATE POLICY learning_sample_all ON ai.learning_sample FOR ALL USING ({_STAFF}) WITH CHECK ({_STAFF});
ALTER TABLE ai.learning_model ENABLE ROW LEVEL SECURITY;
CREATE POLICY learning_model_select ON ai.learning_model FOR SELECT USING ({_STAFF});
CREATE POLICY learning_model_write ON ai.learning_model FOR ALL USING (ehimaya.sees_all()) WITH CHECK (ehimaya.sees_all());
ALTER TABLE ai.training_job ENABLE ROW LEVEL SECURITY;
CREATE POLICY training_job_all ON ai.training_job FOR ALL USING (ehimaya.sees_all()) WITH CHECK (ehimaya.sees_all());
"""

DOWNGRADE = """
DROP TABLE ai.training_job;
DROP TABLE ai.learning_model;
DROP TABLE ai.learning_sample;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
