"""Core schema: geography, identity, reports, operations, audit.

Revision ID: 0001_core_schema
Revises:
Create Date: 2026-10-19
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0001_core_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE = r"""
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS geo;
CREATE SCHEMA IF NOT EXISTS identity;
CREATE SCHEMA IF NOT EXISTS reports;
CREATE SCHEMA IF NOT EXISTS ops;
CREATE SCHEMA IF NOT EXISTS audit;

-- ===================== geo: Tunisian administrative reference =====================
CREATE TABLE geo.gouvernorat (
    code        smallint PRIMARY KEY CHECK (code BETWEEN 11 AND 83),
    iso_code    text NOT NULL UNIQUE,
    name_ar     text NOT NULL,
    name_fr     text NOT NULL,
    boundary    geometry(MultiPolygon, 4326)
);
CREATE INDEX ix_gouvernorat_boundary ON geo.gouvernorat USING gist (boundary);

CREATE TABLE geo.delegation (
    id                integer PRIMARY KEY,           -- gouvernorat_code * 100 + sequence
    code              text NOT NULL UNIQUE,          -- e.g. TN-61-12
    gouvernorat_code  smallint NOT NULL REFERENCES geo.gouvernorat(code),
    name_ar           text NOT NULL,
    name_fr           text NOT NULL,
    boundary          geometry(MultiPolygon, 4326),
    CONSTRAINT uq_delegation_gouvernorat_name UNIQUE (gouvernorat_code, name_fr)
);
CREATE INDEX ix_delegation_gouvernorat ON geo.delegation (gouvernorat_code);
CREATE INDEX ix_delegation_boundary ON geo.delegation USING gist (boundary);

-- ===================== identity =====================
CREATE TYPE identity.account_kind AS ENUM ('citizen', 'organization', 'anonymous');
CREATE TYPE identity.account_status AS ENUM ('active', 'suspended', 'banned');

CREATE TABLE identity.account (
    user_id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),   -- the unified USERID
    kind                identity.account_kind NOT NULL,
    keycloak_sub        text UNIQUE,                                   -- NULL for anonymous accounts
    anon_pseudonym      bytea UNIQUE,                                  -- HMAC(device install id); anonymous only
    status              identity.account_status NOT NULL DEFAULT 'active',
    false_report_count  integer NOT NULL DEFAULT 0 CHECK (false_report_count >= 0),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_account_identity_shape CHECK (
        (kind = 'anonymous' AND keycloak_sub IS NULL AND anon_pseudonym IS NOT NULL)
        OR (kind <> 'anonymous' AND keycloak_sub IS NOT NULL AND anon_pseudonym IS NULL)
    )
);

CREATE TABLE identity.profile (
    user_id           uuid PRIMARY KEY REFERENCES identity.account(user_id) ON DELETE CASCADE,
    first_name        text,
    last_name         text,
    cin_enc           bytea,           -- national ID card number, field-level encrypted
    cin_hash          bytea UNIQUE,    -- keyed hash for lookup without decrypting
    phone             text,
    phone_verified_at timestamptz,
    email             text,
    email_verified_at timestamptz,
    gouvernorat_code  smallint REFERENCES geo.gouvernorat(code),
    delegation_id     integer REFERENCES geo.delegation(id),
    address           text,
    medical_enc       bytea,           -- age, blood group, medical info, emergency contact (encrypted JSON)
    locale            text NOT NULL DEFAULT 'ar' CHECK (locale IN ('ar', 'fr', 'en')),
    updated_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE identity.consent (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id          uuid NOT NULL REFERENCES identity.account(user_id) ON DELETE CASCADE,
    charter_version  text NOT NULL,
    locale           text NOT NULL,
    accepted_at      timestamptz NOT NULL DEFAULT now(),
    platform         text           -- android | ios | web
);
CREATE INDEX ix_consent_user ON identity.consent (user_id);

-- ===================== ops (incidents) =====================
CREATE TYPE ops.op_level AS ENUM ('normal', 'crisis', 'disaster');

CREATE TABLE ops.incident (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    category          text NOT NULL,
    severity          smallint CHECK (severity BETWEEN 0 AND 100),
    centroid          geography(Point, 4326),
    area              geography(Polygon, 4326),
    gouvernorat_code  smallint REFERENCES geo.gouvernorat(code),
    delegation_id     integer REFERENCES geo.delegation(id),
    op_level          ops.op_level NOT NULL DEFAULT 'normal',
    status            text NOT NULL DEFAULT 'open',
    opened_at         timestamptz NOT NULL DEFAULT now(),
    closed_at         timestamptz
);
CREATE INDEX ix_incident_centroid ON ops.incident USING gist (centroid);
CREATE INDEX ix_incident_scope ON ops.incident (gouvernorat_code, status, opened_at DESC);

CREATE TABLE ops.timeline_event (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id  uuid NOT NULL REFERENCES ops.incident(id) ON DELETE CASCADE,
    at           timestamptz NOT NULL DEFAULT now(),
    actor        text,
    kind         text NOT NULL,
    payload      jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX ix_timeline_incident ON ops.timeline_event (incident_id, at);

-- ===================== reports =====================
CREATE TABLE reports.report (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tracking_code      text NOT NULL UNIQUE,
    client_uuid        uuid UNIQUE,                 -- idempotency key generated on the device
    user_id            uuid NOT NULL REFERENCES identity.account(user_id),
    incident_id        uuid REFERENCES ops.incident(id),
    category           text NOT NULL,
    text_original      text,
    lang_original      text,
    text_ar            text,
    location           geography(Point, 4326) NOT NULL,
    location_accuracy_m real,
    gouvernorat_code   smallint REFERENCES geo.gouvernorat(code),
    delegation_id      integer REFERENCES geo.delegation(id),
    priority_score     smallint CHECK (priority_score BETWEEN 0 AND 100),
    credibility_score  smallint CHECK (credibility_score BETWEEN 0 AND 100),
    status             text NOT NULL DEFAULT 'received',
    source             text NOT NULL DEFAULT 'app' CHECK (source IN ('app', 'portal', 'iot', 'call', 'sms')),
    embedding          vector(768),
    created_at         timestamptz NOT NULL,         -- device time (may be earlier when sent offline)
    received_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_report_location ON reports.report USING gist (location);
CREATE INDEX ix_report_scope ON reports.report (gouvernorat_code, status, received_at DESC);
CREATE INDEX ix_report_user ON reports.report (user_id, received_at DESC);
CREATE INDEX ix_report_incident ON reports.report (incident_id);

CREATE TABLE reports.media (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id    uuid REFERENCES reports.report(id) ON DELETE CASCADE,
    stream_id    uuid,
    kind         text NOT NULL CHECK (kind IN ('image', 'video', 'audio', 'recording')),
    object_key   text NOT NULL UNIQUE,
    sha256       char(64) NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    bytes        bigint,
    duration_s   real,
    transcript   text,
    analysis     jsonb,
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_media_report ON reports.media (report_id);

-- ===================== audit: append-only, hash-chained =====================
CREATE TABLE audit.log (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    seq        bigint NOT NULL UNIQUE,      -- chain order, assigned under lock by the trigger
    at         timestamptz NOT NULL DEFAULT now(),
    actor      text NOT NULL,               -- "<realm>:<subject>" or "system"
    action     text NOT NULL,
    target     text,
    reason     text,
    details    jsonb NOT NULL DEFAULT '{}'::jsonb,
    prev_hash  char(64),
    hash       char(64) NOT NULL
);
CREATE INDEX ix_audit_actor ON audit.log (actor, at DESC);
CREATE INDEX ix_audit_target ON audit.log (target, at DESC);

CREATE FUNCTION audit.entry_hash(p_seq bigint, p_prev text, p_at timestamptz, p_actor text, p_action text,
                                 p_target text, p_reason text, p_details jsonb)
RETURNS char(64) LANGUAGE sql IMMUTABLE AS $$
    SELECT encode(public.digest(convert_to(concat_ws('|',
        p_seq::text,
        coalesce(p_prev, ''),
        to_char(p_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
        p_actor, p_action, coalesce(p_target, ''), coalesce(p_reason, ''), p_details::text
    ), 'UTF8'), 'sha256'), 'hex')
$$;

CREATE FUNCTION audit.log_before_insert() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    last_seq  bigint;
    last_hash char(64);
BEGIN
    -- Serialize writers so the chain never forks.
    PERFORM pg_advisory_xact_lock(hashtext('audit.log'));
    SELECT seq, hash INTO last_seq, last_hash FROM audit.log ORDER BY seq DESC LIMIT 1;
    NEW.seq := coalesce(last_seq, 0) + 1;
    NEW.prev_hash := last_hash;
    NEW.at := date_trunc('microseconds', clock_timestamp());
    NEW.hash := audit.entry_hash(NEW.seq, NEW.prev_hash, NEW.at, NEW.actor, NEW.action,
                                 NEW.target, NEW.reason, NEW.details);
    RETURN NEW;
END $$;

CREATE TRIGGER trg_audit_log_chain BEFORE INSERT ON audit.log
    FOR EACH ROW EXECUTE FUNCTION audit.log_before_insert();

CREATE FUNCTION audit.log_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit.log is append-only' USING ERRCODE = 'insufficient_privilege';
END $$;

CREATE TRIGGER trg_audit_log_no_update BEFORE UPDATE OR DELETE ON audit.log
    FOR EACH ROW EXECUTE FUNCTION audit.log_immutable();
CREATE TRIGGER trg_audit_log_no_truncate BEFORE TRUNCATE ON audit.log
    FOR EACH STATEMENT EXECUTE FUNCTION audit.log_immutable();

-- Returns the seq of the first entry whose hash or link is wrong, or NULL when the chain is intact.
CREATE FUNCTION audit.verify_chain() RETURNS bigint LANGUAGE sql STABLE AS $$
    SELECT min(seq) FROM (
        SELECT seq, hash, prev_hash,
               lag(hash) OVER (ORDER BY seq) AS expected_prev,
               lag(seq)  OVER (ORDER BY seq) AS prev_seq,
               audit.entry_hash(seq, prev_hash, at, actor, action, target, reason, details) AS recomputed
        FROM audit.log
    ) c
    WHERE c.hash <> c.recomputed
       OR c.prev_hash IS DISTINCT FROM c.expected_prev
       OR (c.prev_seq IS NULL AND c.seq <> 1)
       OR (c.prev_seq IS NOT NULL AND c.seq <> c.prev_seq + 1)
$$;
"""

DOWNGRADE = r"""
DROP SCHEMA IF EXISTS audit CASCADE;
DROP SCHEMA IF EXISTS reports CASCADE;
DROP SCHEMA IF EXISTS ops CASCADE;
DROP SCHEMA IF EXISTS identity CASCADE;
DROP SCHEMA IF EXISTS geo CASCADE;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
