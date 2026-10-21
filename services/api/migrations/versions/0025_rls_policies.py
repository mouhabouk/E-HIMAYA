"""Row-level security (phase 9, docs/api/phase-9-contract.md §9.2): the database's own copy of the scope rules.

The API checks the scope first (``core/access.py``); these policies are the second layer, so a missing ``WHERE`` in a
query can no longer leak another gouvernorat's rows. Every transaction sets ``ehimaya.scope``, ``ehimaya.gouvernorat``
and ``ehimaya.subject`` (``core/db.py``); an unset scope (``none``) reads nothing.

* ``ehimaya.can_see(lead, incident, report, candidates)`` — scope ``system``/``national``, or scope ``gouvernorat``
  and: the lead is the caller's gouvernorat, the caller's gouvernorat participates in the incident, is a candidate of a
  report whose location is not trusted yet, or an unexpired break-glass grant of ``ehimaya.subject`` covers it.
* Policies are a **superset** of the API rule (it decides what is shown; the database only refuses other
  gouvernorats): referral target, claiming room, critical candidates, members of an institution for its reports, a
  volunteer for the incidents they are called to.
* ``UPDATE``/``DELETE`` reach visible rows only, and PostgreSQL also wants the updated row to stay visible. The few
  steps that cross scopes on purpose, after the API's own check (grouping across a border, AI scoring, refusing a
  referral, a citizen's export), run with the ``system`` scope for that step only (``core.db.as_system``).
* ``INSERT`` needs a scope (any but ``none``); ``audit.log`` takes inserts from every scope, through
  ``audit.append`` (owner rights) so the hash chain is always computed over the whole log.
* ``ENABLE`` only, never ``FORCE``: the owner role (migrations, maintenance) is not subject to the policies; the
  runtime role is ``NOBYPASSRLS``.

Downgrade (the rollback of the rollout, §9.3): policies dropped, row-level security disabled, helpers removed.

Revision ID: 0025_rls_policies
Revises: 0024_i18n_english
Create Date: 2026-10-21
"""

# ruff: noqa: S608 (policies are built from the constant SQL fragments below; no value comes from outside)

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0025_rls_policies"
down_revision: str | None = "0024_i18n_english"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


HELPERS = r"""
CREATE SCHEMA IF NOT EXISTS ehimaya;

CREATE FUNCTION ehimaya.scope() RETURNS text LANGUAGE sql STABLE PARALLEL SAFE AS $$
    SELECT coalesce(nullif(current_setting('ehimaya.scope', true), ''), 'none') $$;

CREATE FUNCTION ehimaya.gouvernorat() RETURNS smallint LANGUAGE sql STABLE PARALLEL SAFE AS $$
    SELECT CASE WHEN current_setting('ehimaya.gouvernorat', true) ~ '^[0-9]{1,2}$'
                THEN CAST(current_setting('ehimaya.gouvernorat', true) AS smallint) END $$;

CREATE FUNCTION ehimaya.subject() RETURNS text LANGUAGE sql STABLE PARALLEL SAFE AS $$
    SELECT nullif(current_setting('ehimaya.subject', true), '') $$;

-- Worker loops, CLIs, internal hooks (system) and the central room (national) read every row.
CREATE FUNCTION ehimaya.sees_all() RETURNS boolean LANGUAGE sql STABLE PARALLEL SAFE AS $$
    SELECT ehimaya.scope() IN ('system', 'national') $$;

CREATE FUNCTION ehimaya.regional() RETURNS boolean LANGUAGE sql STABLE PARALLEL SAFE AS $$
    SELECT ehimaya.scope() = 'gouvernorat' AND ehimaya.gouvernorat() IS NOT NULL $$;

CREATE FUNCTION ehimaya.can_see(
    p_lead smallint, p_incident uuid, p_report uuid DEFAULT NULL, p_candidates smallint[] DEFAULT '{}'
) RETURNS boolean LANGUAGE sql STABLE AS $$
    SELECT ehimaya.sees_all() OR (ehimaya.regional() AND (
        p_lead = ehimaya.gouvernorat()
        OR ehimaya.gouvernorat() = ANY(p_candidates)
        OR (p_incident IS NOT NULL AND EXISTS (
            SELECT 1 FROM ops.incident_gouvernorat ig
            WHERE ig.incident_id = p_incident AND ig.gouvernorat_code = ehimaya.gouvernorat()))
        OR EXISTS (
            SELECT 1 FROM access.break_glass_grant g
            WHERE g.subject = ehimaya.subject() AND g.ended_at IS NULL AND g.expires_at > now()
              AND ((g.target_kind = 'report' AND g.target_id = p_report)
                OR (g.target_kind = 'incident' AND g.target_id = p_incident)
                OR (g.target_kind = 'gouvernorat' AND (
                    g.gouvernorat_code = p_lead
                    OR g.gouvernorat_code = ANY(p_candidates)
                    OR (p_incident IS NOT NULL AND EXISTS (
                        SELECT 1 FROM ops.incident_gouvernorat ig
                        WHERE ig.incident_id = p_incident AND ig.gouvernorat_code = g.gouvernorat_code))))))
    )) $$;

-- A volunteer (public scope) reads the incidents they are called out or assigned to. Owner rights: the assignment
-- and call-out policies refer back to the incident, which a policy cannot do on its own (recursion).
CREATE FUNCTION ehimaya.volunteer_on(p_incident uuid) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
    SELECT ehimaya.scope() = 'public' AND ehimaya.subject() IS NOT NULL AND (
        EXISTS (SELECT 1 FROM ops.assignment a
                WHERE a.incident_id = p_incident AND CAST(a.volunteer_id AS text) = ehimaya.subject())
        OR EXISTS (SELECT 1 FROM ops.callout c JOIN ops.callout_target t ON t.callout_id = c.id
                   WHERE c.incident_id = p_incident AND CAST(t.volunteer_id AS text) = ehimaya.subject())) $$;
REVOKE ALL ON FUNCTION ehimaya.volunteer_on(uuid) FROM PUBLIC;

-- The one way the runtime role writes the audit log: with the owner's rights, so the chain trigger reads the
-- previous entry whatever the caller may see, and the new entry comes back even when it is not visible to the caller.
CREATE FUNCTION audit.append(p_actor text, p_action text, p_target text, p_reason text, p_details jsonb)
RETURNS SETOF audit.log LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
    INSERT INTO audit.log (actor, action, target, reason, details)
    VALUES (p_actor, p_action, p_target, p_reason, coalesce(p_details, '{}'::jsonb))
    RETURNING * $$;
REVOKE ALL ON FUNCTION audit.append(text, text, text, text, jsonb) FROM PUBLIC;

-- Direct inserts (owner maintenance) keep the chain whole too.
ALTER FUNCTION audit.log_before_insert() SECURITY DEFINER;
ALTER FUNCTION audit.log_before_insert() SET search_path = pg_catalog, pg_temp;
"""

_REPORT = "EXISTS (SELECT 1 FROM reports.report r WHERE r.id = report_id)"
_INCIDENT = "EXISTS (SELECT 1 FROM ops.incident i WHERE i.id = incident_id)"

# Who may see (and update or delete) a row of each protected table.
VISIBLE: dict[str, str] = {
    "reports.report": """
        ehimaya.can_see(gouvernorat_code, incident_id, id,
                        CASE WHEN geo_state IN ('pending', 'contradictory') THEN geo_candidates
                             ELSE '{}'::smallint[] END)
        OR (ehimaya.regional() AND (claimed_room = 'g:' || ehimaya.gouvernorat()
                                    OR referred_to = ehimaya.gouvernorat()))
        OR (ehimaya.scope() = 'public' AND CAST(user_id AS text) = ehimaya.subject())
        -- Members of an institution read the reports sent on its behalf (phase 8 organisations).
        OR (ehimaya.scope() = 'public' AND organization_id IS NOT NULL AND EXISTS (
            SELECT 1 FROM org.member m
            WHERE m.org_id = organization_id AND CAST(m.user_id AS text) = ehimaya.subject()))""",
    "reports.status_history": _REPORT,
    "reports.escalation": _REPORT,
    "reports.reporter_context": f"ehimaya.scope() IN ('system', 'national', 'gouvernorat') AND {_REPORT}",
    "reports.media": f"""
        (report_id IS NOT NULL AND {_REPORT})
        OR (stream_id IS NOT NULL AND EXISTS (SELECT 1 FROM reports.live_stream s WHERE s.id = stream_id))
        OR (report_id IS NULL AND stream_id IS NULL AND ehimaya.scope() IN ('system', 'national', 'gouvernorat'))""",
    "reports.live_stream": f"""
        ehimaya.sees_all()
        OR (ehimaya.regional() AND (gouvernorat_code = ehimaya.gouvernorat()
                                    OR (report_id IS NOT NULL AND {_REPORT})))
        OR (ehimaya.scope() = 'public' AND CAST(user_id AS text) = ehimaya.subject())""",
    "ops.incident": "ehimaya.can_see(gouvernorat_code, id) OR ehimaya.volunteer_on(id)",
    "ops.timeline_event": _INCIDENT,
    # A volunteer reads their own assignments and the call-outs sent to them.
    "ops.assignment": f"""
        {_INCIDENT}
        OR (ehimaya.scope() = 'public' AND CAST(volunteer_id AS text) = ehimaya.subject())""",
    "ops.callout": f"""
        {_INCIDENT}
        OR (ehimaya.scope() = 'public' AND EXISTS (
            SELECT 1 FROM ops.callout_target t
            WHERE t.callout_id = id AND CAST(t.volunteer_id AS text) = ehimaya.subject()))""",
    "ops.resource_request": f"""
        {_INCIDENT}
        OR (ehimaya.regional() AND (to_gouvernorat_code = ehimaya.gouvernorat()
                                    OR from_room = 'g:' || ehimaya.gouvernorat()))""",
    "ops.unit": "ehimaya.sees_all() OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat())",
    "ops.resource": """
        EXISTS (SELECT 1 FROM ops.unit u WHERE u.id = unit_id)
        OR EXISTS (SELECT 1 FROM ops.assignment a WHERE a.resource_id = id)
        OR EXISTS (SELECT 1 FROM ops.resource_request q WHERE q.resource_id = id)""",
    "telephony.call": """
        ehimaya.sees_all()
        OR (ehimaya.regional() AND (gouvernorat_code = ehimaya.gouvernorat()
                                    OR (gouvernorat_code IS NULL AND status = 'ringing')
                                    OR operator_user_id = ehimaya.subject()))""",
    "access.break_glass_grant": "ehimaya.sees_all() OR subject = ehimaya.subject()",
}

_SCOPED = "ehimaya.scope() <> 'none'"


def _name(table: str) -> str:
    return table.split(".")[1]


def policy_statements() -> list[str]:
    statements: list[str] = []
    for table, visible in VISIBLE.items():
        name = _name(table)
        statements += [
            f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
            f"CREATE POLICY {name}_select ON {table} FOR SELECT USING ({visible})",
            f"CREATE POLICY {name}_insert ON {table} FOR INSERT WITH CHECK ({_SCOPED})",
            f"CREATE POLICY {name}_update ON {table} FOR UPDATE USING ({visible}) WITH CHECK ({_SCOPED})",
            f"CREATE POLICY {name}_delete ON {table} FOR DELETE USING ({visible})",
        ]
    # Append-only: read by scope, inserted by anyone (the triggers refuse every change).
    statements += [
        "ALTER TABLE audit.log ENABLE ROW LEVEL SECURITY",
        "CREATE POLICY log_select ON audit.log FOR SELECT USING (ehimaya.sees_all() "
        "OR (ehimaya.regional() AND ehimaya.gouvernorat() = ANY(gouvernorats)))",
        "CREATE POLICY log_insert ON audit.log FOR INSERT WITH CHECK (true)",
    ]
    return statements


def downgrade_statements() -> list[str]:
    statements: list[str] = []
    for table in [*VISIBLE, "audit.log"]:
        name = _name(table)
        actions = ("select", "insert") if table == "audit.log" else ("select", "insert", "update", "delete")
        statements += [f"DROP POLICY {name}_{action} ON {table}" for action in actions]
        statements.append(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    return statements


DOWNGRADE_HELPERS = r"""
ALTER FUNCTION audit.log_before_insert() RESET search_path;
ALTER FUNCTION audit.log_before_insert() SECURITY INVOKER;
DROP FUNCTION audit.append(text, text, text, text, jsonb);
DROP FUNCTION ehimaya.volunteer_on(uuid);
DROP FUNCTION ehimaya.can_see(smallint, uuid, uuid, smallint[]);
DROP FUNCTION ehimaya.regional();
DROP FUNCTION ehimaya.sees_all();
DROP FUNCTION ehimaya.subject();
DROP FUNCTION ehimaya.gouvernorat();
DROP FUNCTION ehimaya.scope();
DROP SCHEMA ehimaya;
"""


def upgrade() -> None:
    run_script(HELPERS)
    run_script(";\n".join(policy_statements()) + ";")


def downgrade() -> None:
    run_script(";\n".join(downgrade_statements()) + ";")
    run_script(DOWNGRADE_HELPERS)
