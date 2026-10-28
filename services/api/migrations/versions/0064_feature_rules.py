"""What the system administrator grants and hides (L4, docs/phase-l/design-l4.md §8).

``access.feature_rule``: a grant or a hiding of a catalogue feature (a page, a tab or a button) for one account or one
role, in every gouvernorat or in one, for a period or open-ended, with its reason; revoked rather than deleted. Read
and written through the system scope by the permissions service; the runtime role sees no row of it otherwise.

Revision ID: 0064_feature_rules
Revises: 0063_schedule_statuses
Create Date: 2026-10-28
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0064_feature_rules"
down_revision: str | None = "0063_schedule_statuses"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = """
CREATE TABLE access.feature_rule (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    feature_key      text NOT NULL CHECK (feature_key ~ '^[a-z_]+(\\.[a-z_]+)?$'),
    effect           text NOT NULL CHECK (effect IN ('grant', 'hide')),
    target_kind      text NOT NULL CHECK (target_kind IN ('user', 'role')),
    target           text NOT NULL CHECK (length(target) BETWEEN 1 AND 255),
    target_name      text,
    gouvernorat_code smallint REFERENCES geo.gouvernorat(code),
    reason           text NOT NULL CHECK (length(reason) BETWEEN 5 AND 500),
    starts_at        timestamptz,
    ends_at          timestamptz,
    created_by       text NOT NULL,
    created_by_name  text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    revoked_at       timestamptz,
    revoked_by_name  text,
    revoke_reason    text,
    CONSTRAINT ck_feature_rule_period CHECK (ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at),
    CONSTRAINT ck_feature_rule_user_scope CHECK (target_kind = 'role' OR gouvernorat_code IS NULL)
);
CREATE INDEX ix_feature_rule_active ON access.feature_rule (feature_key) WHERE revoked_at IS NULL;

ALTER TABLE access.feature_rule ENABLE ROW LEVEL SECURITY;
CREATE POLICY feature_rule_system ON access.feature_rule
    USING (ehimaya.scope() = 'system') WITH CHECK (ehimaya.scope() = 'system');
"""

DOWNGRADE = """
DROP TABLE access.feature_rule;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
