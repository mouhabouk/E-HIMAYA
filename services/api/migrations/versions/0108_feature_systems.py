"""The administrator acts on a whole system of the menu (Yamen, 2026-11-13: the menu of 20 systems in 4 blocks).

A rule may now name a system (``system.<key>``, the key pattern is unchanged) and, besides «grant» and «hide», be a
«suspend»: the system is closed for a while for everyone, a role (in every gouvernorat or one) or an account, and the
administrator's ``message`` (ar, fr, en) shows in its place. Only a system can be suspended.

Revision ID: 0108_feature_systems
Revises: 0107_par
Create Date: 2026-11-13
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0108_feature_systems"
down_revision: str | None = "0107_par"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = """
ALTER TABLE access.feature_rule ADD COLUMN message jsonb;
ALTER TABLE access.feature_rule DROP CONSTRAINT feature_rule_effect_check;
ALTER TABLE access.feature_rule ADD CONSTRAINT feature_rule_effect_check
    CHECK (effect IN ('grant', 'hide', 'suspend'));
ALTER TABLE access.feature_rule ADD CONSTRAINT ck_feature_rule_suspend
    CHECK (effect <> 'suspend' OR (feature_key LIKE 'system.%' AND message IS NOT NULL));
ALTER TABLE access.feature_rule ADD CONSTRAINT ck_feature_rule_message
    CHECK (message IS NULL OR jsonb_typeof(message) = 'object');
ALTER TABLE access.feature_rule DROP CONSTRAINT ck_feature_rule_everyone;
ALTER TABLE access.feature_rule ADD CONSTRAINT ck_feature_rule_everyone
    CHECK (target_kind <> 'everyone' OR (target = '*' AND effect IN ('hide', 'suspend')));
"""

DOWNGRADE = """
DELETE FROM access.feature_rule WHERE effect = 'suspend';
ALTER TABLE access.feature_rule DROP CONSTRAINT ck_feature_rule_everyone;
ALTER TABLE access.feature_rule ADD CONSTRAINT ck_feature_rule_everyone
    CHECK (target_kind <> 'everyone' OR (target = '*' AND effect = 'hide'));
ALTER TABLE access.feature_rule DROP CONSTRAINT ck_feature_rule_message;
ALTER TABLE access.feature_rule DROP CONSTRAINT ck_feature_rule_suspend;
ALTER TABLE access.feature_rule DROP CONSTRAINT feature_rule_effect_check;
ALTER TABLE access.feature_rule ADD CONSTRAINT feature_rule_effect_check CHECK (effect IN ('grant', 'hide'));
ALTER TABLE access.feature_rule DROP COLUMN message;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
