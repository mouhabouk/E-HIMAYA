"""Decision support (phase 7, docs/api/phase-7-contract.md §3).

* ``decision.procedure_chunk`` — the procedures library (docs/procedures/*.md, ar/fr) split into passages: the
  retrieval corpus of the incident assistant. Each passage keeps its procedure, language, the report categories and
  incident classifications it applies to, its public sources and a checksum (re-indexing only touches what changed).
  ``search`` is a full-text vector ('simple' configuration: Arabic and French words as written) used when no
  embedding is available; ``embedding`` is the multilingual-e5 vector of the AI service (filled by the worker).

Recommendations, routes and responder suggestions are computed on request from existing data and are not stored;
the assistant's questions and answers go to the incident timeline (``ops.timeline_event``, kind ``assistant``).
The runtime role's grants on the new schema are applied after the upgrade (migrations/env.py, app/core/db_roles.py).

Revision ID: 0013_decision
Revises: 0012_weather
Create Date: 2026-10-20
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0013_decision"
down_revision: str | None = "0012_weather"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE = r"""
CREATE SCHEMA IF NOT EXISTS decision;

CREATE TABLE decision.procedure_chunk (
    id               text PRIMARY KEY,
    procedure_id     text NOT NULL,
    lang             text NOT NULL,
    title            text NOT NULL,
    heading          text NOT NULL,
    body             text NOT NULL,
    position         smallint NOT NULL,
    categories       text[] NOT NULL DEFAULT '{}',
    classifications  text[] NOT NULL DEFAULT '{}',
    sources          jsonb NOT NULL DEFAULT '[]'::jsonb,
    path             text NOT NULL,
    checksum         text NOT NULL,
    search           tsvector GENERATED ALWAYS AS
                         (to_tsvector('simple'::regconfig, title || ' ' || heading || ' ' || body)) STORED,
    embedding        vector(768),
    embedding_model  text,
    indexed_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_procedure_chunk_lang CHECK (lang IN ('ar', 'fr')),
    CONSTRAINT ck_procedure_chunk_id CHECK (id = procedure_id || '.' || lang || '#' || position),
    CONSTRAINT ck_procedure_chunk_body CHECK (char_length(body) BETWEEN 1 AND 8000)
);
CREATE INDEX ix_procedure_chunk_search ON decision.procedure_chunk USING gin (search);
CREATE INDEX ix_procedure_chunk_lang ON decision.procedure_chunk (lang, procedure_id);
CREATE INDEX ix_procedure_chunk_unembedded ON decision.procedure_chunk (indexed_at) WHERE embedding IS NULL;
"""


DOWNGRADE = r"""
DROP TABLE decision.procedure_chunk;
DROP SCHEMA decision;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
