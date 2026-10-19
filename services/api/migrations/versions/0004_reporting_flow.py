"""Core reporting flow: statuses and history, tracking-code counter, media upload states, event outbox.

Revision ID: 0004_reporting_flow
Revises: 0003_gouvernorat_boundaries
Create Date: 2026-10-19
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0004_reporting_flow"
down_revision: str | None = "0003_gouvernorat_boundaries"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE = r"""
-- ===================== reports =====================
ALTER TABLE reports.report
    ADD COLUMN updated_at        timestamptz NOT NULL DEFAULT now(),
    ADD COLUMN first_response_at timestamptz,
    ADD CONSTRAINT ck_report_status CHECK (
        status IN ('received', 'in_progress', 'intervened', 'ongoing', 'closed', 'rejected')),
    ADD CONSTRAINT ck_report_category CHECK (
        category IN ('sos', 'fire', 'flood', 'traffic_accident', 'drowning', 'landslide',
                     'chemical_leak', 'medical', 'other')),
    ADD CONSTRAINT ck_report_lang CHECK (lang_original IS NULL OR lang_original IN ('ar', 'fr', 'en')),
    ADD CONSTRAINT ck_report_text_length CHECK (char_length(text_original) <= 4000),
    ADD CONSTRAINT ck_report_tracking_code CHECK (tracking_code ~ '^EH-[0-9]{2}-[0-9]{2}-[0-9]{7}$');

-- Staff lists are read newest first inside a scope; national users read without a scope.
CREATE INDEX ix_report_received ON reports.report (received_at DESC, id DESC);

-- One counter row per year; the row lock serialises numbering for that year only.
CREATE TABLE reports.tracking_counter (
    year  smallint PRIMARY KEY,
    last  bigint NOT NULL CHECK (last > 0)
);

CREATE TABLE reports.status_history (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    report_id  uuid NOT NULL REFERENCES reports.report(id) ON DELETE CASCADE,
    status     text NOT NULL,
    at         timestamptz NOT NULL DEFAULT now(),
    actor      text NOT NULL,             -- "<realm>:<subject>", "reporter" or "system"
    note       text CHECK (char_length(note) <= 1000)
);
CREATE INDEX ix_status_history_report ON reports.status_history (report_id, at);

-- ===================== media (tus uploads) =====================
ALTER TABLE reports.media
    ADD COLUMN upload_id     text UNIQUE,                 -- tus upload id (also the object name)
    ADD COLUMN content_type  text,
    ADD COLUMN status        text NOT NULL DEFAULT 'uploading',
    ADD COLUMN stored_at     timestamptz,
    ADD CONSTRAINT ck_media_status CHECK (status IN ('uploading', 'verifying', 'stored', 'rejected'));
CREATE INDEX ix_media_verifying ON reports.media (created_at) WHERE status = 'verifying';

-- ===================== events: transactional outbox =====================
-- Rows are written in the same transaction as the change they describe and relayed to NATS
-- afterwards, so a report is never lost or announced twice when the bus is down.
CREATE SCHEMA IF NOT EXISTS events;
CREATE TABLE events.outbox (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject       text NOT NULL,
    payload       jsonb NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now(),
    published_at  timestamptz,
    attempts      integer NOT NULL DEFAULT 0
);
CREATE INDEX ix_outbox_pending ON events.outbox (id) WHERE published_at IS NULL;
"""

DOWNGRADE = r"""
DROP SCHEMA events CASCADE;

DROP INDEX reports.ix_media_verifying;
ALTER TABLE reports.media
    DROP CONSTRAINT ck_media_status,
    DROP COLUMN stored_at,
    DROP COLUMN status,
    DROP COLUMN content_type,
    DROP COLUMN upload_id;

DROP TABLE reports.status_history;
DROP TABLE reports.tracking_counter;
DROP INDEX reports.ix_report_received;

ALTER TABLE reports.report
    DROP CONSTRAINT ck_report_tracking_code,
    DROP CONSTRAINT ck_report_text_length,
    DROP CONSTRAINT ck_report_lang,
    DROP CONSTRAINT ck_report_category,
    DROP CONSTRAINT ck_report_status,
    DROP COLUMN first_response_at,
    DROP COLUMN updated_at;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
