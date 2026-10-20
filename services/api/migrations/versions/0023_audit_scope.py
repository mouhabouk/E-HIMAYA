"""Gouvernorats of audit entries (phase 9, docs/api/phase-9-contract.md §7.2).

``audit.record(..., gouvernorats=[...])`` stores the gouvernorats an action concerns as ``details.gouvernorats``,
inside the hash chain. ``audit.log.gouvernorats`` is a stored generated column derived from it by the immutable
function ``audit.scope_of`` (GIN-indexed) for the redacted regional view and row-level security.

The hash function, the chain trigger and the append-only triggers are untouched: the chain covers ``details``, which
does not change, so ``audit.verify_chain()`` keeps passing on every existing row. Existing rows carry no
``details.gouvernorats``: they are national-only entries (empty array).

Revision ID: 0023_audit_scope
Revises: 0022_access_break_glass
Create Date: 2026-10-20
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0023_audit_scope"
down_revision: str | None = "0022_access_break_glass"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE = r"""
CREATE FUNCTION audit.scope_of(p_details jsonb) RETURNS smallint[] LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT coalesce(array_agg(DISTINCT CAST(v AS smallint) ORDER BY CAST(v AS smallint)), '{}'::smallint[])
    FROM jsonb_array_elements_text(
        CASE WHEN jsonb_typeof(p_details -> 'gouvernorats') = 'array' THEN p_details -> 'gouvernorats'
             ELSE '[]'::jsonb END) AS v
    WHERE v ~ '^[0-9]{1,4}$'
$$;

-- A table rewrite, not a row update: the append-only triggers do not fire and the stored hashes are unchanged.
ALTER TABLE audit.log ADD COLUMN gouvernorats smallint[] GENERATED ALWAYS AS (audit.scope_of(details)) STORED;
CREATE INDEX ix_audit_gouvernorats ON audit.log USING gin (gouvernorats);
"""


DOWNGRADE = r"""
DROP INDEX audit.ix_audit_gouvernorats;
ALTER TABLE audit.log DROP COLUMN gouvernorats;
DROP FUNCTION audit.scope_of(jsonb);
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
