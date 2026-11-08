"""The change journal ("mouchard"), Yamen 2026-11-08 (docs/phase-h/design-h5.md).

Every INSERT, UPDATE and DELETE on the application's tables is written by a database trigger to ``audit.change``:
when, who (the signed-in account the API set for the transaction, ``system`` for the worker loops, ``db:<role>``
for anything done directly in the database), from which request, which table and row, which columns changed, and
the values before and after.

What it never keeps:

* values of columns that may hold personal data, secrets or free text (names, phone numbers, e-mail addresses,
  encrypted fields, hashes, keys, tokens, notes, descriptions, positions...), and JSON objects or arrays of text
  outside the platform settings (a manager's card, a list of names): the column is listed under ``hidden`` as
  changed, without its value (rule: technical accounts never see personal data);
* any value of the schemas that are personal as a whole (identity, medical, personnel, safety, telephony, contact,
  access): their rows are traced (who, when, which columns), never their content;
* the high-volume streams (positions, telemetry, detections, sensor readings, outboxes, map features, boundaries),
  which are measurements rather than changes, and the audit schema itself.

``audit`` is append-only for the runtime role (core/db_roles.py): the API can neither change nor remove an entry.
The trigger function runs with the owner's rights, so it writes whatever the caller's row-level scope; reading is
for the national scope only (the API checks the role, and serves an institution's own changes to its admin).

Revision ID: 0097_change_journal
Revises: 0096_personnel
Create Date: 2026-11-08
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from migrations.sqlutil import run_script

revision: str = "0097_change_journal"
down_revision: str | None = "0096_personnel"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies of app/modules/audit/journal.py at this revision (a later migration attaches new tables itself).
EXCLUDED = (
    "audit.log",
    "audit.change",
    "events.outbox",
    "notify.outbox",
    "notify.dispatch",
    "ops.crew_position",
    "reports.stream_detection",
    "reports.stream_segment",
    "reports.stream_location",
    "reports.drone_telemetry",
    "reports.tracking_counter",
    "reports.camera_event",
    "reports.tower_event",
    "safety.location_point",
    "safety.location_history",
    "sensor.reading",
    "weather.observation",
    "weather.grid_point",
    "coastal.presence",
    "coastal.marine_hour",
    "coastal.beach_day",
    "knowledge.search_doc",
    "knowledge.index_state",
    "decision.procedure_chunk",
    "geo.layer_feature",
    "geo.gouvernorat",
    "geo.delegation",
    "geo.municipality",
    "geo.sector",
    "geo.district",
    "geo.city",
    "geo.economic_region",
    "geo.water_body",
    "identity.email_code",
    "medical.file_key",
    "medical.opinion_key",
    "evidence.leaf",
    "rewards.consumer_cursor",
    "ai.learning_sample",
    "snacr.intervention",
    "snacr.damage",
    "crisis.counter",
    "register.counter",
    "org.certificate_counter",
    "rewards.certificate_counter",
)
PERSONAL_SCHEMAS = ("identity", "medical", "personnel", "safety", "telephony", "contact", "access")

UPGRADE = r"""
CREATE TABLE audit.change (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    at              timestamptz NOT NULL DEFAULT clock_timestamp(),
    txid            bigint NOT NULL DEFAULT txid_current(),
    actor           text NOT NULL,
    actor_name      text,
    scope           text,
    actor_gouvernorat smallint,
    request_id      text,
    schema_name     text NOT NULL,
    table_name      text NOT NULL,
    op              char(1) NOT NULL CHECK (op IN ('I', 'U', 'D')),
    row_key         jsonb NOT NULL DEFAULT '{}',
    columns         text[] NOT NULL DEFAULT '{}',
    hidden          text[] NOT NULL DEFAULT '{}',
    old_values      jsonb,
    new_values      jsonb,
    org_id          uuid,
    gouvernorat_code smallint
);
CREATE INDEX ix_change_at ON audit.change (at DESC);
CREATE INDEX ix_change_table ON audit.change (schema_name, table_name, id DESC);
CREATE INDEX ix_change_actor ON audit.change (actor, id DESC);
CREATE INDEX ix_change_request ON audit.change (request_id) WHERE request_id IS NOT NULL;
CREATE INDEX ix_change_org ON audit.change (org_id, id DESC) WHERE org_id IS NOT NULL;
CREATE INDEX ix_change_row ON audit.change USING gin (row_key jsonb_path_ops);

ALTER TABLE audit.change ENABLE ROW LEVEL SECURITY;
CREATE POLICY change_select ON audit.change FOR SELECT USING (ehimaya.sees_all());
CREATE POLICY change_insert ON audit.change FOR INSERT WITH CHECK (false);

-- A column whose value is never kept: personal data, secrets, free text, positions, binary content.
CREATE FUNCTION audit.journal_hidden(p_column text) RETURNS boolean LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT p_column ~ ('(_enc|_hash|_key|_keys|_token|_secret|secret|password|pin|otp|phone|mobile|msisdn|email|'
        || 'name|cin|national|passport|address|birth|iban|geom|location|position|^lat|^lon|^lng|latitude|longitude|'
        || 'photo|image|picture|avatar|text|note|comment|description|body|message|content|reason|transcript|summary|'
        || 'embedding|vector|ip$|ip_|device|pseudonym|signature|pdf|blob|data$|payload|answer|title|subject|'
        || 'diagnos|medical|allerg|blood|plate|vin$|imei|iccid|uid$|card)')
$$;

-- A kept value, cut to 200 characters (large arrays and objects are not copied).
CREATE FUNCTION audit.journal_value(p jsonb) RETURNS jsonb LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT CASE
        WHEN p IS NULL OR jsonb_typeof(p) IN ('null', 'number', 'boolean') THEN p
        WHEN jsonb_typeof(p) = 'string' AND char_length(p #>> '{}') <= 200 THEN p
        WHEN jsonb_typeof(p) = 'string' THEN to_jsonb(left(p #>> '{}', 200) || '…')
        WHEN char_length(p::text) <= 200 THEN p
        ELSE to_jsonb('…'::text)
    END
$$;

CREATE FUNCTION audit.journal_row() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    o jsonb;
    n jsonb;
    src jsonb;
    k text;
    cols text[] := '{}';
    hid text[] := '{}';
    ov jsonb := '{}';
    nv jsonb := '{}';
    rk jsonb := '{}';
    keycols text[] := TG_ARGV[0]::text[];
    personal boolean := TG_ARGV[1]::boolean;
    who text := nullif(current_setting('ehimaya.actor', true), '');
    sc text := nullif(current_setting('ehimaya.scope', true), '');
    g text := nullif(current_setting('ehimaya.gouvernorat', true), '');
    org text;
    gv text;
BEGIN
    IF TG_OP <> 'INSERT' THEN o := to_jsonb(OLD); END IF;
    IF TG_OP <> 'DELETE' THEN n := to_jsonb(NEW); END IF;
    src := coalesce(n, o);
    FOR k IN SELECT jsonb_object_keys(src) LOOP
        IF TG_OP = 'UPDATE' AND (o -> k) IS NOT DISTINCT FROM (n -> k) THEN CONTINUE; END IF;
        IF TG_OP <> 'UPDATE' AND jsonb_typeof(src -> k) = 'null' THEN CONTINUE; END IF;
        cols := cols || k;
        -- Objects and arrays of text may hold anything (a manager's card, a list of names): kept only for the
        -- platform settings; arrays of numbers (gouvernorat codes...) are kept everywhere.
        IF personal OR audit.journal_hidden(k)
           OR (TG_TABLE_SCHEMA <> 'platform' AND (jsonb_typeof(src -> k) = 'object'
               OR (jsonb_typeof(src -> k) = 'array' AND jsonb_path_exists(src -> k, '$[*] ? (@.type() != "number")'))))
        THEN
            hid := hid || k;
            CONTINUE;
        END IF;
        IF o IS NOT NULL THEN ov := ov || jsonb_build_object(k, audit.journal_value(o -> k)); END IF;
        IF n IS NOT NULL THEN nv := nv || jsonb_build_object(k, audit.journal_value(n -> k)); END IF;
    END LOOP;
    IF TG_OP = 'UPDATE' AND cardinality(cols) = 0 THEN
        RETURN NULL;
    END IF;
    FOREACH k IN ARRAY keycols LOOP
        rk := rk || jsonb_build_object(k, src -> k);
    END LOOP;
    org := CASE WHEN TG_TABLE_SCHEMA = 'org' AND TG_TABLE_NAME = 'organization' THEN src ->> 'id'
                ELSE coalesce(src ->> 'org_id', src ->> 'organization_id') END;
    IF org !~ '^[0-9a-fA-F-]{36}$' THEN org := NULL; END IF;
    gv := src ->> 'gouvernorat_code';
    IF gv !~ '^[0-9]{1,2}$' THEN gv := NULL; END IF;
    INSERT INTO audit.change (actor, actor_name, scope, actor_gouvernorat, request_id, schema_name, table_name, op,
                              row_key, columns, hidden, old_values, new_values, org_id, gouvernorat_code)
    VALUES (coalesce(who, CASE WHEN sc = 'system' THEN 'system' ELSE 'db:' || session_user END),
            nullif(current_setting('ehimaya.actor_name', true), ''),
            sc,
            CASE WHEN g ~ '^[0-9]{1,2}$' THEN g::smallint END,
            nullif(current_setting('ehimaya.request_id', true), ''),
            TG_TABLE_SCHEMA, TG_TABLE_NAME, left(TG_OP, 1), rk, cols, hid,
            CASE WHEN TG_OP = 'INSERT' THEN NULL ELSE ov END,
            CASE WHEN TG_OP = 'DELETE' THEN NULL ELSE nv END,
            org::uuid, gv::smallint);
    RETURN NULL;
END
$$;
REVOKE ALL ON FUNCTION audit.journal_row() FROM PUBLIC;

-- Puts the trigger on one table (migrations call it for the tables they create; owner only).
CREATE FUNCTION audit.journal_attach(p_table regclass, p_personal boolean) RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    keycols text[];
BEGIN
    SELECT coalesce(array_agg(a.attname::text ORDER BY array_position(i.indkey::int2[], a.attnum)), '{}')
      INTO keycols
      FROM pg_index i JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY (i.indkey)
     WHERE i.indrelid = p_table AND i.indisprimary;
    EXECUTE format('DROP TRIGGER IF EXISTS zz_journal ON %s', p_table);
    EXECUTE format('CREATE TRIGGER zz_journal AFTER INSERT OR UPDATE OR DELETE ON %s FOR EACH ROW '
                   'EXECUTE FUNCTION audit.journal_row(%L, %L)', p_table, keycols::text, p_personal::text);
END
$$;
REVOKE ALL ON FUNCTION audit.journal_attach(regclass, boolean) FROM PUBLIC;
"""

DOWNGRADE = """
DO $$
DECLARE r record;
BEGIN
    FOR r IN SELECT tgrelid::regclass AS t FROM pg_trigger WHERE tgname = 'zz_journal' LOOP
        EXECUTE format('DROP TRIGGER zz_journal ON %s', r.t);
    END LOOP;
END
$$;
DROP FUNCTION audit.journal_attach(regclass, boolean);
DROP FUNCTION audit.journal_row();
DROP FUNCTION audit.journal_value(jsonb);
DROP FUNCTION audit.journal_hidden(text);
DROP TABLE audit.change;
"""


def upgrade() -> None:
    run_script(UPGRADE)
    bind = op.get_bind()
    tables = bind.execute(
        text(
            "SELECT n.nspname, c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "JOIN pg_roles r ON r.oid = n.nspowner "
            "WHERE c.relkind IN ('r', 'p') AND NOT c.relispartition AND r.rolname = current_user "
            "AND n.nspname NOT IN ('public', 'information_schema', 'tiger', 'topology') "
            "AND n.nspname NOT LIKE 'pg\\_%' ORDER BY 1, 2"
        )
    ).all()
    for schema, table in tables:
        name = f"{schema}.{table}"
        if name in EXCLUDED:
            continue
        bind.execute(
            text("SELECT audit.journal_attach(CAST(:t AS regclass), :p)"),
            {"t": f'"{schema}"."{table}"', "p": schema in PERSONAL_SCHEMAS},
        )


def downgrade() -> None:
    run_script(DOWNGRADE)
