"""The decision window and its delegations (L4b, docs/phase-l/design-l4.md §3 and §5).

* ``decision_window.delegation``: the central room (any account) or the ops manager of a gouvernorat (its governor
  and its local committee) opens the window to one account, for a period, on selected events only; revoked rather
  than deleted. ``decision_window.delegation_event``: an axis or an incident of a delegation, added at the grant or later.
* ``decision_window.saved_search``: a search kept under a name by its owner.
* ``decision_window.synonym``: the dictionary of the quick search, kept by the central room: words (Arabic, French,
  English or dialect) that mean a category, an incident classification or another word.

Read and written through the system scope by the window service, after its own checks; the runtime role sees no row
of them otherwise.

Revision ID: 0065_decision_window
Revises: 0064_feature_rules
Create Date: 2026-10-28
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0065_decision_window"
down_revision: str | None = "0064_feature_rules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = """
CREATE SCHEMA IF NOT EXISTS decision_window;

CREATE TABLE decision_window.delegation (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    grantee          text NOT NULL CHECK (length(grantee) BETWEEN 1 AND 255),
    grantee_name     text,
    grantee_roles    text[] NOT NULL DEFAULT '{}',
    grantee_gouvernorat smallint REFERENCES geo.gouvernorat(code),
    reason           text NOT NULL CHECK (length(reason) BETWEEN 5 AND 500),
    starts_at        timestamptz NOT NULL,
    ends_at          timestamptz NOT NULL,
    granted_by       text NOT NULL,
    granted_by_name  text,
    granted_room     text NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    revoked_at       timestamptz,
    revoked_by_name  text,
    revoke_reason    text,
    CONSTRAINT ck_delegation_period CHECK (ends_at > starts_at)
);
CREATE INDEX ix_delegation_grantee ON decision_window.delegation (grantee) WHERE revoked_at IS NULL;

CREATE TABLE decision_window.delegation_event (
    delegation_id    uuid NOT NULL REFERENCES decision_window.delegation(id) ON DELETE CASCADE,
    kind             text NOT NULL CHECK (kind IN ('axis', 'incident')),
    target_id        uuid NOT NULL,
    label            text NOT NULL DEFAULT '',
    gouvernorat_code smallint REFERENCES geo.gouvernorat(code),
    added_by_name    text,
    added_at         timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (delegation_id, kind, target_id)
);

CREATE TABLE decision_window.saved_search (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner            text NOT NULL,
    name             text NOT NULL CHECK (length(name) BETWEEN 1 AND 120),
    kind             text NOT NULL CHECK (kind IN ('search', 'compare')),
    query            jsonb NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (owner, name)
);

CREATE TABLE decision_window.synonym (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    meaning          text NOT NULL CHECK (length(meaning) BETWEEN 1 AND 80),
    words            text[] NOT NULL CHECK (cardinality(words) BETWEEN 1 AND 50),
    updated_by_name  text,
    updated_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (meaning)
);

-- The dialect and everyday words the quick search understands from the start; the central room keeps the list.
INSERT INTO decision_window.synonym (meaning, words, updated_by_name) VALUES
    ('fire', ARRAY['حريقة', 'نار', 'شعلة', 'شعلت', 'حرايق', 'feu', 'incendies'], 'e-Himaya'),
    ('forest_fire', ARRAY['حريق غابة', 'حرائق الغابات', 'غابة', 'غابه', 'forêt', 'feu de forêt', 'wildfire'],
        'e-Himaya'),
    ('traffic_accident', ARRAY['كسيدة', 'اكسيدان', 'حادث مرور', 'حوادث المرور', 'accident', 'crash'], 'e-Himaya'),
    ('drowning', ARRAY['غرقة', 'غريق', 'غرقى', 'noyé', 'noyade'], 'e-Himaya'),
    ('flood', ARRAY['فيضانات', 'سيول', 'حملة', 'امطار', 'inondations', 'crue'], 'e-Himaya'),
    ('landslide', ARRAY['انزلاق', 'طيحة', 'éboulement'], 'e-Himaya'),
    ('chemical_leak', ARRAY['تسرب', 'غاز', 'fuite', 'gaz'], 'e-Himaya'),
    ('medical', ARRAY['مريض', 'إسعاف', 'malaise', 'ambulance'], 'e-Himaya');

ALTER TABLE decision_window.delegation ENABLE ROW LEVEL SECURITY;
CREATE POLICY delegation_system ON decision_window.delegation
    USING (ehimaya.scope() = 'system') WITH CHECK (ehimaya.scope() = 'system');
ALTER TABLE decision_window.delegation_event ENABLE ROW LEVEL SECURITY;
CREATE POLICY delegation_event_system ON decision_window.delegation_event
    USING (ehimaya.scope() = 'system') WITH CHECK (ehimaya.scope() = 'system');
ALTER TABLE decision_window.saved_search ENABLE ROW LEVEL SECURITY;
CREATE POLICY saved_search_system ON decision_window.saved_search
    USING (ehimaya.scope() = 'system') WITH CHECK (ehimaya.scope() = 'system');
ALTER TABLE decision_window.synonym ENABLE ROW LEVEL SECURITY;
CREATE POLICY synonym_system ON decision_window.synonym
    USING (ehimaya.scope() = 'system') WITH CHECK (ehimaya.scope() = 'system');
"""

DOWNGRADE = """
DROP SCHEMA decision_window CASCADE;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
