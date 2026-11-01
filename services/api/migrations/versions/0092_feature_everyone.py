"""The administrator's rules reach every surface (phase 5, Yamen 2026-11-01): a rule may now apply to everyone (a
window of the citizen app or of the portal closed for all its users, anonymous ones included), and the feature keys of
the field app, the citizen app and the portal join the catalogue (no change of shape: same key pattern).

Revision ID: 0092_feature_everyone
Revises: 0091_damage_refs
Create Date: 2026-11-01
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0092_feature_everyone"
down_revision: str | None = "0091_damage_refs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = """
ALTER TABLE access.feature_rule DROP CONSTRAINT feature_rule_target_kind_check;
ALTER TABLE access.feature_rule ADD CONSTRAINT feature_rule_target_kind_check
    CHECK (target_kind IN ('user', 'role', 'everyone'));
ALTER TABLE access.feature_rule ADD CONSTRAINT ck_feature_rule_everyone
    CHECK (target_kind <> 'everyone' OR (target = '*' AND effect = 'hide'));
"""

DOWNGRADE = """
DELETE FROM access.feature_rule WHERE target_kind = 'everyone';
ALTER TABLE access.feature_rule DROP CONSTRAINT ck_feature_rule_everyone;
ALTER TABLE access.feature_rule DROP CONSTRAINT feature_rule_target_kind_check;
ALTER TABLE access.feature_rule ADD CONSTRAINT feature_rule_target_kind_check
    CHECK (target_kind IN ('user', 'role'));
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
