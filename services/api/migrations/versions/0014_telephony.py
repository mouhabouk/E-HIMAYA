"""Telephony and SMS reports (phase 7, docs/api/phase-7-contract.md §4 and §5, docs/telephony.md).

* ``telephony.call`` — one call through the platform (scenario 1/2: 8000 queue, outbound calls placed by staff). The
  citizen's number is encrypted (``caller_number_enc``) with a blind index (``caller_hash``); the recording becomes
  ``reports.media`` kind ``call_recording`` (SHA-256 → S3), ingested by the worker (``recording_*`` columns).
* ``telephony.operator_endpoint`` — WebRTC endpoint pushed to Asterisk while an operator's SIP credentials are valid.
* ``telephony.conference`` — crisis rooms (ConfBridge) of an incident.
* ``telephony.sms_inbound`` — SMS received from the gateway (FR-A-048): deduplication only, no message text kept.
* ``reports.media.kind`` accepts ``call_recording``.

The runtime role's grants on the new schema come from the grants re-applied after every upgrade (migrations/env.py,
app/core/db_roles.py).

Revision ID: 0014_telephony
Revises: 0013_decision
Create Date: 2026-10-20
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0014_telephony"
down_revision: str | None = "0013_decision"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE = r"""
CREATE SCHEMA IF NOT EXISTS telephony;

ALTER TABLE reports.media DROP CONSTRAINT IF EXISTS media_kind_check;
ALTER TABLE reports.media ADD CONSTRAINT ck_media_kind
    CHECK (kind IN ('image', 'video', 'audio', 'recording', 'call_recording'));

CREATE TABLE telephony.call (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id          text NOT NULL UNIQUE,
    direction           text NOT NULL,
    source              text NOT NULL DEFAULT 'unknown',
    caller_number_enc   bytea,
    caller_hash         bytea,
    started_at          timestamptz NOT NULL DEFAULT now(),
    answered_at         timestamptz,
    ended_at            timestamptz,
    operator_user_id    text,
    operator_endpoint   text,
    queue               text,
    status              text NOT NULL DEFAULT 'ringing',
    end_reason          text,
    report_id           uuid REFERENCES reports.report(id) ON DELETE SET NULL,
    incident_id         uuid REFERENCES ops.incident(id) ON DELETE SET NULL,
    gouvernorat_code    smallint REFERENCES geo.gouvernorat(code),
    transferred_to      text,
    recording_media_id  uuid REFERENCES reports.media(id) ON DELETE SET NULL,
    -- Operational columns of the recording ingestion (not part of the public contract).
    recording_state     text NOT NULL DEFAULT 'none',
    recording_attempts  smallint NOT NULL DEFAULT 0,
    recording_next_at   timestamptz NOT NULL DEFAULT now(),
    recording_error     text,
    created_by          text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_call_direction CHECK (direction IN ('inbound', 'outbound')),
    CONSTRAINT ck_call_source CHECK (source IN ('trunk', 'webrtc', 'sim', 'operator', 'unknown')),
    CONSTRAINT ck_call_status CHECK (status IN ('ringing', 'answered', 'transferred', 'ended', 'missed', 'failed')),
    CONSTRAINT ck_call_end_reason CHECK (end_reason IS NULL OR end_reason IN
        ('completed', 'abandoned', 'no_answer', 'transferred', 'failed', 'untracked')),
    CONSTRAINT ck_call_recording_state CHECK (recording_state IN ('none', 'pending', 'done', 'missing', 'failed')),
    CONSTRAINT ck_call_channel_id CHECK (channel_id ~ '^[A-Za-z0-9_-][A-Za-z0-9._-]{0,63}$'),
    CONSTRAINT ck_call_caller_pair CHECK ((caller_number_enc IS NULL) = (caller_hash IS NULL)),
    CONSTRAINT ck_call_times CHECK (ended_at IS NULL OR ended_at >= started_at)
);
CREATE INDEX ix_call_started ON telephony.call (started_at DESC, id DESC);
CREATE INDEX ix_call_scope ON telephony.call (gouvernorat_code, started_at DESC);
CREATE INDEX ix_call_status ON telephony.call (status, started_at DESC);
CREATE INDEX ix_call_caller ON telephony.call (caller_hash) WHERE caller_hash IS NOT NULL;
CREATE INDEX ix_call_report ON telephony.call (report_id) WHERE report_id IS NOT NULL;
CREATE INDEX ix_call_incident ON telephony.call (incident_id) WHERE incident_id IS NOT NULL;
CREATE INDEX ix_call_recording_pending ON telephony.call (recording_next_at) WHERE recording_state = 'pending';
CREATE INDEX ix_call_ended ON telephony.call (ended_at) WHERE ended_at IS NOT NULL;

CREATE TABLE telephony.operator_endpoint (
    endpoint          text PRIMARY KEY,
    user_subject      text NOT NULL UNIQUE,
    display_name      text,
    gouvernorat_code  smallint REFERENCES geo.gouvernorat(code),
    expires_at        timestamptz NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    removed_at        timestamptz,
    CONSTRAINT ck_operator_endpoint_name CHECK (endpoint ~ '^op-[0-9a-f]{12}$'),
    CONSTRAINT ck_operator_endpoint_display CHECK (char_length(display_name) <= 100)
);
CREATE INDEX ix_operator_endpoint_expiry ON telephony.operator_endpoint (expires_at) WHERE removed_at IS NULL;

CREATE TABLE telephony.conference (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    room              text NOT NULL UNIQUE,
    incident_id       uuid NOT NULL REFERENCES ops.incident(id) ON DELETE CASCADE,
    gouvernorat_code  smallint REFERENCES geo.gouvernorat(code),
    created_by        text NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now(),
    ended_at          timestamptz,
    ended_by          text,
    CONSTRAINT ck_conference_room CHECK (room ~ '^[0-9]{8}$')
);
CREATE INDEX ix_conference_incident ON telephony.conference (incident_id, created_at DESC);
-- One open room per incident (409 conference_active).
CREATE UNIQUE INDEX ux_conference_open ON telephony.conference (incident_id) WHERE ended_at IS NULL;

CREATE TABLE telephony.sms_inbound (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    message_hash    bytea NOT NULL UNIQUE,
    sender_hash     bytea,
    sender_number_enc bytea,
    client_prefix   text,
    category        text,
    report_id       uuid REFERENCES reports.report(id) ON DELETE SET NULL,
    outcome         text NOT NULL,
    reason          text,
    merged_at       timestamptz,
    received_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_sms_inbound_outcome CHECK (outcome IN ('created', 'duplicate', 'rejected')),
    CONSTRAINT ck_sms_inbound_prefix CHECK (client_prefix IS NULL OR client_prefix ~ '^[0-9a-f]{8}$')
);
CREATE INDEX ix_sms_inbound_prefix ON telephony.sms_inbound (client_prefix, received_at DESC)
    WHERE client_prefix IS NOT NULL AND report_id IS NOT NULL;
CREATE INDEX ix_sms_inbound_received ON telephony.sms_inbound (received_at);
CREATE INDEX ix_sms_inbound_report ON telephony.sms_inbound (report_id) WHERE report_id IS NOT NULL;
CREATE INDEX ix_sms_inbound_sender ON telephony.sms_inbound (sender_hash) WHERE sender_hash IS NOT NULL;
"""


DOWNGRADE = r"""
DROP TABLE telephony.sms_inbound;
DROP TABLE telephony.conference;
DROP TABLE telephony.operator_endpoint;
DROP TABLE telephony.call;
DROP SCHEMA telephony;
-- Call recordings belong to calls: they go with them (their objects stay in S3 until removed by hand).
DELETE FROM reports.media WHERE kind = 'call_recording';
ALTER TABLE reports.media DROP CONSTRAINT ck_media_kind;
ALTER TABLE reports.media ADD CONSTRAINT media_kind_check
    CHECK (kind IN ('image', 'video', 'audio', 'recording'));
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
