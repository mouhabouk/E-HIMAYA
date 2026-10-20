"""Break-glass grants and regional account administration (phase 9, docs/api/phase-9-contract.md §6).

* ``access.break_glass_grant`` — a time-boxed, justified, read-only extension of a staff member's scope to one report,
  one incident or one gouvernorat. Active at once; every grant is reviewed afterwards by a national security admin.
* ``access.account_admin_log`` — what the regional account administration proxy did in Keycloak (create, update,
  credentials reset), with the gouvernorat of the account. The audit log keeps the same entries (hash chain).

The runtime role's grants on the new schema come from the grants re-applied after every upgrade (migrations/env.py,
app/core/db_roles.py).

Revision ID: 0022_access_break_glass
Revises: 0021_ops_multi_gouvernorat
Create Date: 2026-10-20
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0022_access_break_glass"
down_revision: str | None = "0021_ops_multi_gouvernorat"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE = r"""
CREATE SCHEMA IF NOT EXISTS access;

CREATE TABLE access.break_glass_grant (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    subject           text NOT NULL,
    subject_name      text,
    target_kind       text NOT NULL,
    target_id         uuid,
    gouvernorat_code  smallint REFERENCES geo.gouvernorat(code),
    justification     text NOT NULL,
    granted_at        timestamptz NOT NULL DEFAULT now(),
    expires_at        timestamptz NOT NULL,
    -- Set by a revocation, or by the breakglass worker once the grant expired (its end is then announced).
    ended_at          timestamptz,
    revoked_at        timestamptz,
    revoked_by        text,
    reviewed_by       text,
    reviewed_at       timestamptz,
    review_outcome    text,
    review_note       text,
    -- When the breakglass worker announced the missing review (72 h after the end).
    overdue_notified_at timestamptz,
    CONSTRAINT ck_break_glass_grant_target_kind CHECK (target_kind IN ('report', 'incident', 'gouvernorat')),
    CONSTRAINT ck_break_glass_grant_target CHECK (
        (target_kind = 'gouvernorat' AND gouvernorat_code IS NOT NULL AND target_id IS NULL)
        OR (target_kind <> 'gouvernorat' AND target_id IS NOT NULL)),
    CONSTRAINT ck_break_glass_grant_justification CHECK (char_length(justification) BETWEEN 20 AND 1000),
    CONSTRAINT ck_break_glass_grant_expiry CHECK (expires_at > granted_at
                                                  AND expires_at <= granted_at + interval '240 minutes'),
    CONSTRAINT ck_break_glass_grant_review_outcome CHECK (review_outcome IS NULL
                                                          OR review_outcome IN ('justified', 'unjustified')),
    CONSTRAINT ck_break_glass_grant_reviewed CHECK ((review_outcome IS NULL) = (reviewed_at IS NULL))
);
CREATE INDEX ix_break_glass_grant_subject ON access.break_glass_grant (subject, expires_at DESC);
CREATE INDEX ix_break_glass_grant_granted ON access.break_glass_grant (granted_at DESC, id DESC);
CREATE INDEX ix_break_glass_grant_unreviewed ON access.break_glass_grant (expires_at) WHERE reviewed_at IS NULL;
CREATE INDEX ix_break_glass_grant_open ON access.break_glass_grant (expires_at) WHERE ended_at IS NULL;

CREATE TABLE access.account_admin_log (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    at                timestamptz NOT NULL DEFAULT now(),
    actor             text NOT NULL,
    actor_name        text,
    action            text NOT NULL,
    account_id        text NOT NULL,
    username          text,
    gouvernorat_code  smallint REFERENCES geo.gouvernorat(code),
    details           jsonb NOT NULL DEFAULT '{}',
    CONSTRAINT ck_account_admin_log_action CHECK (action IN ('account.create', 'account.update', 'account.reset'))
);
CREATE INDEX ix_account_admin_log_account ON access.account_admin_log (account_id, at DESC);
CREATE INDEX ix_account_admin_log_gouvernorat ON access.account_admin_log (gouvernorat_code, at DESC);
"""


DOWNGRADE = r"""
DROP TABLE access.account_admin_log;
DROP TABLE access.break_glass_grant;
DROP SCHEMA access;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
