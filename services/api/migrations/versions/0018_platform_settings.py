"""National settings (phase 9, docs/api/phase-9-contract.md §2): ``platform.setting``.

One row per key (JSONB value, optimistic ``version``, who changed it and when), seeded with the defaults of
``app/modules/settings/domain.py``: SLA bands and claim delays, the start of SLA enforcement (this migration: no
retro-escalation of older reports), the anonymous report quota, the geographic trust threshold and the real-send
switch (stays false, not editable in phase 9).

The runtime role's grants on the new schema come from the grants re-applied after every upgrade (migrations/env.py,
app/core/db_roles.py).

Revision ID: 0018_platform_settings
Revises: 0017_rewards
Create Date: 2026-10-20
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0018_platform_settings"
down_revision: str | None = "0017_rewards"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE = r"""
CREATE SCHEMA IF NOT EXISTS platform;

CREATE TABLE platform.setting (
    key              text PRIMARY KEY,
    value            jsonb NOT NULL,
    version          integer NOT NULL DEFAULT 1,
    updated_by       text,
    updated_by_name  text,
    updated_at       timestamptz DEFAULT now()
);

INSERT INTO platform.setting (key, value) VALUES
    ('sla.bands', '{"critical": 85, "high": 70, "normal": 40}'),
    ('sla.claim_delay_s', '{"critical": 60, "high": 90, "normal": 120, "low": 180}'),
    ('sla.enforced_since', to_jsonb(now())),
    ('anonymous.report_quota', '5'),
    ('geo.max_trusted_accuracy_m', '1000'),
    ('notify.real_send_enabled', 'false');
"""

DOWNGRADE = r"""
DROP TABLE IF EXISTS platform.setting;
DROP SCHEMA IF EXISTS platform;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
