"""Register of plans, decisions and instructions, central and regional (phase L3b, docs/phase-l/design-l3b.md).

* ``register.document``: one plan, decision, memo, circular, standing or temporary instruction, recommendation or
  minutes, central or of one gouvernorat, with its official reference, issuer, dates of issue, effect and end, topics,
  status (draft, in force, expired, repealed), access, the attached file (key and SHA-256) and the crisis axes it
  concerns. A signed recommendation or decision of an axis (L3) is recorded here automatically (``directive_id``).
  ``norm`` holds the folded words of the text and ``search`` its full-text vector.
* ``register.link``: one document repeals, amends or complements another.
* ``register.recommendation``: the key recommendations of a document with who acts, the deadline and the status.
* ``register.revision``: a snapshot of the document per saved change, with the reason.
* ``crisis.axis.plan_document_id``: the plan in force on an axis, a document of the register.

Row-level security: national staff see every document; a regional account sees the central documents and those of
its gouvernorat, and writes only those of its gouvernorat. The access level of a document (every staff member,
the rooms of its gouvernorat, the command, restricted) is the API's.

Revision ID: 0057_register
Revises: 0056_crisis_axes
Create Date: 2026-10-28
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0057_register"
down_revision: str | None = "0056_crisis_axes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_READ = "(ehimaya.sees_all() OR gouvernorat_code IS NULL OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat()))"
_WRITE = "(ehimaya.sees_all() OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat()))"
_DOC = "register.sees_document(document_id)"

UPGRADE = rf"""
CREATE SCHEMA IF NOT EXISTS register;

CREATE TABLE register.document (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    number           text NOT NULL UNIQUE,
    reference        text NOT NULL DEFAULT '' CHECK (length(reference) <= 300),
    kind             text NOT NULL CHECK (kind IN ('plan', 'decision', 'memo', 'circular', 'standing_instruction',
                                                   'temporary_instruction', 'recommendation', 'minutes', 'other')),
    level            text NOT NULL CHECK (level IN ('central', 'regional')),
    gouvernorat_code smallint REFERENCES geo.gouvernorat(code),
    issuer           text NOT NULL CHECK (length(issuer) BETWEEN 2 AND 200),
    signatory        text NOT NULL DEFAULT '',
    title            text NOT NULL CHECK (length(title) BETWEEN 3 AND 300),
    summary          text NOT NULL DEFAULT '',
    body             text NOT NULL DEFAULT '',
    topics           text[] NOT NULL DEFAULT '{{}}',
    issued_on        date NOT NULL,
    effective_from   date,
    effective_to     date,
    status           text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'in_force', 'expired', 'repealed')),
    repealed_by      uuid REFERENCES register.document(id) ON DELETE SET NULL,
    repeal_reason    text,
    access           text NOT NULL DEFAULT 'all' CHECK (access IN ('all', 'gouvernorat', 'command', 'restricted')),
    axis_ids         uuid[] NOT NULL DEFAULT '{{}}',
    source           text NOT NULL DEFAULT 'manual' CHECK (source IN ('manual', 'axis')),
    directive_id     uuid UNIQUE REFERENCES crisis.directive(id) ON DELETE SET NULL,
    signature        text,
    key_id           text,
    file_key         text,
    file_name        text,
    file_type        text,
    file_size        integer,
    file_sha256      text,
    norm             text NOT NULL DEFAULT '',
    search           tsvector GENERATED ALWAYS AS (to_tsvector('simple'::regconfig, norm)) STORED,
    created_by       text NOT NULL,
    created_by_name  text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_by       text NOT NULL,
    updated_by_name  text,
    updated_at       timestamptz NOT NULL DEFAULT now(),
    version          integer NOT NULL DEFAULT 1,
    CONSTRAINT ck_document_level CHECK (
        (level = 'central' AND gouvernorat_code IS NULL) OR (level = 'regional' AND gouvernorat_code IS NOT NULL)
    ),
    CONSTRAINT ck_document_dates CHECK (effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from),
    CONSTRAINT ck_document_temporary CHECK (kind <> 'temporary_instruction' OR effective_to IS NOT NULL)
);
CREATE INDEX ix_document_search ON register.document USING gin (search);
CREATE INDEX ix_document_norm ON register.document USING gin (norm gin_trgm_ops);
CREATE INDEX ix_document_filters ON register.document (status, level, gouvernorat_code, issued_on);
CREATE INDEX ix_document_topics ON register.document USING gin (topics);
CREATE INDEX ix_document_axes ON register.document USING gin (axis_ids);

CREATE TABLE register.counter (
    year integer PRIMARY KEY,
    last integer NOT NULL
);

-- The document policy, for the tables that hang off a document (owner's rights: no recursion into the policy).
CREATE FUNCTION register.sees_document(p_document uuid) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
    SELECT EXISTS (
        SELECT 1 FROM register.document d WHERE d.id = p_document AND (
            ehimaya.sees_all() OR d.gouvernorat_code IS NULL
            OR (ehimaya.regional() AND d.gouvernorat_code = ehimaya.gouvernorat())
        )
    ) $$;

CREATE TABLE register.link (
    from_id    uuid NOT NULL REFERENCES register.document(id) ON DELETE CASCADE,
    to_id      uuid NOT NULL REFERENCES register.document(id) ON DELETE CASCADE,
    relation   text NOT NULL CHECK (relation IN ('repeals', 'amends', 'complements')),
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (from_id, to_id),
    CONSTRAINT ck_link_self CHECK (from_id <> to_id)
);
CREATE INDEX ix_link_to ON register.link (to_id);

CREATE TABLE register.recommendation (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id   uuid NOT NULL REFERENCES register.document(id) ON DELETE CASCADE,
    number        integer NOT NULL,
    body          text NOT NULL CHECK (length(body) BETWEEN 3 AND 2000),
    responsible   text NOT NULL DEFAULT '',
    due_on        date,
    status        text NOT NULL DEFAULT 'proposed'
                  CHECK (status IN ('proposed', 'in_progress', 'done', 'dropped')),
    status_reason text,
    updated_by    text NOT NULL,
    updated_by_name text,
    updated_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_recommendation_number UNIQUE (document_id, number)
);

CREATE TABLE register.revision (
    document_id     uuid NOT NULL REFERENCES register.document(id) ON DELETE CASCADE,
    version         integer NOT NULL,
    snapshot        jsonb NOT NULL,
    change          text NOT NULL,
    reason          text,
    created_by      text NOT NULL,
    created_by_name text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (document_id, version)
);

ALTER TABLE crisis.axis ADD COLUMN plan_document_id uuid REFERENCES register.document(id) ON DELETE SET NULL;

ALTER TABLE register.document ENABLE ROW LEVEL SECURITY;
CREATE POLICY document_all ON register.document USING {_READ} WITH CHECK {_WRITE};
ALTER TABLE register.counter ENABLE ROW LEVEL SECURITY;
CREATE POLICY counter_all ON register.counter USING (true) WITH CHECK (true);
ALTER TABLE register.link ENABLE ROW LEVEL SECURITY;
CREATE POLICY link_all ON register.link USING (register.sees_document(from_id) AND register.sees_document(to_id))
    WITH CHECK (register.sees_document(from_id) AND register.sees_document(to_id));
ALTER TABLE register.recommendation ENABLE ROW LEVEL SECURITY;
CREATE POLICY recommendation_all ON register.recommendation USING ({_DOC}) WITH CHECK ({_DOC});
ALTER TABLE register.revision ENABLE ROW LEVEL SECURITY;
CREATE POLICY revision_all ON register.revision USING ({_DOC}) WITH CHECK ({_DOC});

ALTER TABLE knowledge.search_doc DROP CONSTRAINT ck_search_doc_kind;
ALTER TABLE knowledge.search_doc ADD CONSTRAINT ck_search_doc_kind
    CHECK (kind IN ('memory', 'report_doc', 'incident', 'report', 'transcript', 'procedure', 'register'));
"""  # noqa: S608 (constant SQL fragments, nothing is interpolated from input)

DOWNGRADE = r"""
DELETE FROM knowledge.search_doc WHERE kind = 'register';
ALTER TABLE knowledge.search_doc DROP CONSTRAINT ck_search_doc_kind;
ALTER TABLE knowledge.search_doc ADD CONSTRAINT ck_search_doc_kind
    CHECK (kind IN ('memory', 'report_doc', 'incident', 'report', 'transcript', 'procedure'));
ALTER TABLE crisis.axis DROP COLUMN plan_document_id;
DROP SCHEMA register CASCADE;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
