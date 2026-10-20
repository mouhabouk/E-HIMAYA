"""National memory and events library (phase 8, docs/api/phase-8-contract.md §2).

* ``knowledge.memory_entry`` — national memory (FR-C-22): after-action records of events with ar/fr Markdown
  sections, access level (national|gouvernorat|committee) and a review workflow (draft → in_review → published,
  archived); ``published_version`` names the snapshot readers see while a newer draft is being written.
* ``knowledge.memory_entry_version`` — full version history (one snapshot per saved change and transition).
* ``knowledge.search_doc`` — the events library (FR-C-23) as PostgreSQL rows, one per searchable item (memory
  entries, reports-library documents, incident timelines, report texts, transcripts, procedure passages). Texts that
  are encrypted at their source stay encrypted (``body_enc``) and are matched through blind-index ``tokens``; the
  others keep a normalised copy (``norm``) behind a 'simple' full-text vector and a pg_trgm index (Arabic). It is
  the full-text fallback when OpenSearch is down or disabled, holds the e5 vectors of the semantic part (pgvector),
  and is the authority for the scope check of every hit. ``os_dirty`` rows are pushed to OpenSearch by the worker.
* ``knowledge.index_state`` — the indexer's outbox cursor and sweep watermarks.

pg_trgm is a trusted extension: the database owner (migration role) may create it.
The runtime role's grants on the new schema are applied after the upgrade (migrations/env.py, app/core/db_roles.py).

Revision ID: 0016_knowledge
Revises: 0015_analytics
Create Date: 2026-10-20
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0016_knowledge"
down_revision: str | None = "0015_analytics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE = r"""
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE SCHEMA IF NOT EXISTS knowledge;

CREATE TABLE knowledge.memory_entry (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title              jsonb NOT NULL,
    event_type         text NOT NULL,
    started_at         timestamptz NOT NULL,
    ended_at           timestamptz,
    gouvernorats       smallint[] NOT NULL DEFAULT '{}',
    geometry           geometry(Geometry, 4326),
    incident_ids       uuid[] NOT NULL DEFAULT '{}',
    summary            jsonb NOT NULL,
    strengths          jsonb NOT NULL,
    weaknesses         jsonb NOT NULL,
    lessons            jsonb NOT NULL,
    recommendations    jsonb NOT NULL,
    sources            jsonb NOT NULL DEFAULT '[]'::jsonb,
    access             text NOT NULL DEFAULT 'national',
    status             text NOT NULL DEFAULT 'draft',
    author             text NOT NULL,
    author_name        text,
    updated_by         text NOT NULL,
    updated_by_name    text,
    reviewers          jsonb NOT NULL DEFAULT '[]'::jsonb,
    version            integer NOT NULL DEFAULT 1,
    published_version  integer,
    published_at       timestamptz,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_memory_entry_access CHECK (access IN ('national', 'gouvernorat', 'committee')),
    CONSTRAINT ck_memory_entry_status CHECK (status IN ('draft', 'in_review', 'published', 'archived')),
    CONSTRAINT ck_memory_entry_period CHECK (ended_at IS NULL OR ended_at >= started_at),
    CONSTRAINT ck_memory_entry_version CHECK (version >= 1 AND (published_version IS NULL OR published_version <= version)),
    CONSTRAINT ck_memory_entry_published CHECK (status <> 'published' OR published_version = version),
    CONSTRAINT ck_memory_entry_geometry CHECK (geometry IS NULL OR GeometryType(geometry) IN ('POLYGON', 'MULTIPOLYGON'))
);
CREATE INDEX ix_memory_entry_status ON knowledge.memory_entry (status, updated_at DESC, id DESC);
CREATE INDEX ix_memory_entry_gouvernorats ON knowledge.memory_entry USING gin (gouvernorats);
CREATE INDEX ix_memory_entry_incidents ON knowledge.memory_entry USING gin (incident_ids);

CREATE TABLE knowledge.memory_entry_version (
    entry_id         uuid NOT NULL REFERENCES knowledge.memory_entry(id) ON DELETE CASCADE,
    version          integer NOT NULL,
    snapshot         jsonb NOT NULL,
    status           text NOT NULL,
    change           text NOT NULL,
    note             text,
    created_by       text NOT NULL,
    created_by_name  text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (entry_id, version)
);

CREATE TABLE knowledge.search_doc (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kind             text NOT NULL,
    ref_id           text NOT NULL,
    title            text NOT NULL,
    body             text,
    body_enc         bytea,
    norm             text,
    tokens           bytea[] NOT NULL DEFAULT '{}',
    lang             text,
    date             timestamptz,
    gouvernorats     smallint[] NOT NULL DEFAULT '{}',
    access           text NOT NULL,
    categories       text[] NOT NULL DEFAULT '{}',
    incident_id      uuid,
    checksum         text NOT NULL,
    search           tsvector GENERATED ALWAYS AS (to_tsvector('simple'::regconfig, coalesce(norm, ''))) STORED,
    embedding        vector(768),
    embedding_model  text,
    deleted          boolean NOT NULL DEFAULT false,
    os_dirty         boolean NOT NULL DEFAULT true,
    updated_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_search_doc_kind_ref UNIQUE (kind, ref_id),
    CONSTRAINT ck_search_doc_kind CHECK (kind IN ('memory', 'report_doc', 'incident', 'report', 'transcript', 'procedure')),
    CONSTRAINT ck_search_doc_access CHECK (access IN ('all', 'gouvernorat', 'committee')),
    -- A text is either searchable in clear or encrypted with blind-index tokens, never both.
    CONSTRAINT ck_search_doc_body CHECK (body IS NULL OR body_enc IS NULL)
);
CREATE INDEX ix_search_doc_search ON knowledge.search_doc USING gin (search);
CREATE INDEX ix_search_doc_trgm ON knowledge.search_doc USING gin (norm gin_trgm_ops);
CREATE INDEX ix_search_doc_tokens ON knowledge.search_doc USING gin (tokens);
CREATE INDEX ix_search_doc_date ON knowledge.search_doc (date DESC);
CREATE INDEX ix_search_doc_gouvernorats ON knowledge.search_doc USING gin (gouvernorats);
CREATE INDEX ix_search_doc_embedding ON knowledge.search_doc USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ix_search_doc_dirty ON knowledge.search_doc (updated_at) WHERE os_dirty;
CREATE INDEX ix_search_doc_unembedded ON knowledge.search_doc (updated_at) WHERE embedding IS NULL AND NOT deleted;

CREATE TABLE knowledge.index_state (
    key         text PRIMARY KEY,
    value       jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at  timestamptz NOT NULL DEFAULT now()
);
"""


DOWNGRADE = r"""
DROP TABLE knowledge.index_state;
DROP TABLE knowledge.search_doc;
DROP TABLE knowledge.memory_entry_version;
DROP TABLE knowledge.memory_entry;
DROP SCHEMA knowledge;
DROP EXTENSION IF EXISTS pg_trgm;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
