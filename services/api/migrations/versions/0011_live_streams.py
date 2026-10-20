"""Live streaming and computer vision (phase 6, docs/api/phase-6-contract.md §1).

* ``reports.live_stream`` — one publish session of a citizen (WHIP from the app, linked to a report) or a fixed
  source registered by staff (drone, camera) or the simulator. The publish token is stored only as a keyed hash
  (HMAC, ``app.core.crypto`` blind index). Operational columns: start deadline, location-event throttle, recording
  segment counter, vision watch state and the ring of the last analysed frames (3-of-5 confirmation).
* ``reports.stream_location`` — the position track sent by the app while streaming (retention follows the report).
* ``reports.stream_detection`` — fire / smoke / person detections of a stream frame or of an uploaded image.
* ``reports.stream_segment`` — queue of fMP4 recording segments announced by MediaMTX, ingested by the worker
  (SHA-256, S3, ``reports.media`` kind ``recording``); unique per file path, so a repeated hook is harmless.
* ``reports.media.stream_id`` (existing column) now references ``reports.live_stream``.

The runtime role's grants on the new tables come from ALTER DEFAULT PRIVILEGES and are re-applied after the upgrade
(migrations/env.py, app/core/db_roles.py).

Revision ID: 0011_live_streams
Revises: 0010_data_protection
Create Date: 2026-10-19
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0011_live_streams"
down_revision: str | None = "0010_data_protection"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE = r"""
CREATE TABLE reports.live_stream (
    id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id              uuid REFERENCES reports.report(id) ON DELETE CASCADE,
    user_id                uuid REFERENCES identity.account(user_id),
    source                 text NOT NULL,
    label                  text,
    path                   text NOT NULL UNIQUE,
    publish_token_hash     bytea,
    status                 text NOT NULL DEFAULT 'pending',
    created_at             timestamptz NOT NULL DEFAULT now(),
    started_at             timestamptz,
    ended_at               timestamptz,
    end_reason             text,
    gouvernorat_code       smallint REFERENCES geo.gouvernorat(code),
    last_location          geography(Point, 4326),
    last_location_at       timestamptz,
    max_fire_confidence    real,
    max_smoke_confidence   real,
    -- Operational columns (not part of the public contract).
    expires_at             timestamptz,
    created_by             text,
    location_event_at      timestamptz,
    segment_seq            integer NOT NULL DEFAULT 0,
    vision_state           text NOT NULL DEFAULT 'idle',
    vision_attempts        smallint NOT NULL DEFAULT 0,
    vision_next_attempt_at timestamptz NOT NULL DEFAULT now(),
    vision_frames          jsonb NOT NULL DEFAULT '[]'::jsonb,
    vision_alerts          jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT ck_live_stream_source CHECK (source IN ('app', 'drone', 'camera', 'sim')),
    CONSTRAINT ck_live_stream_status CHECK (status IN ('pending', 'live', 'ended', 'expired', 'rejected')),
    CONSTRAINT ck_live_stream_end_reason CHECK (end_reason IS NULL OR end_reason IN
        ('publisher_stopped', 'staff_stopped', 'max_duration', 'token_expired', 'error')),
    CONSTRAINT ck_live_stream_vision_state CHECK (vision_state IN ('idle', 'requested', 'watching', 'stopping', 'disabled')),
    CONSTRAINT ck_live_stream_path CHECK (path = 'live/' || id::text),
    CONSTRAINT ck_live_stream_label CHECK (char_length(label) <= 100),
    -- A citizen stream always belongs to a report and its reporter.
    CONSTRAINT ck_live_stream_app_report CHECK (source <> 'app' OR (report_id IS NOT NULL AND user_id IS NOT NULL)),
    CONSTRAINT ck_live_stream_confidence CHECK (
        (max_fire_confidence IS NULL OR max_fire_confidence BETWEEN 0 AND 1)
        AND (max_smoke_confidence IS NULL OR max_smoke_confidence BETWEEN 0 AND 1))
);
-- One pending or live stream per report (409 stream_already_active).
CREATE UNIQUE INDEX ux_live_stream_active_report ON reports.live_stream (report_id)
    WHERE status IN ('pending', 'live') AND report_id IS NOT NULL;
CREATE INDEX ix_live_stream_status ON reports.live_stream (status, created_at DESC);
CREATE INDEX ix_live_stream_scope ON reports.live_stream (gouvernorat_code, created_at DESC);
CREATE INDEX ix_live_stream_user ON reports.live_stream (user_id) WHERE user_id IS NOT NULL;
CREATE INDEX ix_live_stream_vision ON reports.live_stream (vision_next_attempt_at)
    WHERE vision_state IN ('requested', 'stopping');
CREATE INDEX ix_live_stream_ended ON reports.live_stream (ended_at) WHERE report_id IS NULL;

CREATE TABLE reports.stream_location (
    id          bigserial PRIMARY KEY,
    stream_id   uuid NOT NULL REFERENCES reports.live_stream(id) ON DELETE CASCADE,
    at          timestamptz NOT NULL DEFAULT now(),
    location    geography(Point, 4326) NOT NULL,
    accuracy_m  real CHECK (accuracy_m IS NULL OR accuracy_m >= 0)
);
CREATE INDEX ix_stream_location_stream ON reports.stream_location (stream_id, at);

CREATE TABLE reports.stream_detection (
    id          bigserial PRIMARY KEY,
    stream_id   uuid REFERENCES reports.live_stream(id) ON DELETE CASCADE,
    media_id    uuid REFERENCES reports.media(id) ON DELETE CASCADE,
    at          timestamptz NOT NULL,
    label       text NOT NULL,
    confidence  real NOT NULL,
    boxes       jsonb NOT NULL DEFAULT '[]'::jsonb,
    model       text,
    -- Part of a confirmed fire/smoke (3 of the last 5 frames, or one uploaded image) at the alert threshold.
    confirmed   boolean NOT NULL DEFAULT false,
    CONSTRAINT ck_stream_detection_label CHECK (label IN ('fire', 'smoke', 'person')),
    CONSTRAINT ck_stream_detection_confidence CHECK (confidence BETWEEN 0 AND 1),
    CONSTRAINT ck_stream_detection_owner CHECK (stream_id IS NOT NULL OR media_id IS NOT NULL)
);
CREATE INDEX ix_stream_detection_stream ON reports.stream_detection (stream_id, at DESC) WHERE stream_id IS NOT NULL;
CREATE INDEX ix_stream_detection_media ON reports.stream_detection (media_id) WHERE media_id IS NOT NULL;

ALTER TABLE reports.media
    ADD CONSTRAINT fk_media_stream_id_live_stream FOREIGN KEY (stream_id)
        REFERENCES reports.live_stream(id) ON DELETE CASCADE;
CREATE INDEX ix_media_stream ON reports.media (stream_id, created_at) WHERE stream_id IS NOT NULL;
-- Uploaded images waiting for the vision detector (media.analysis->'vision').
CREATE INDEX ix_media_vision_pending ON reports.media (created_at)
    WHERE kind = 'image' AND status = 'stored' AND stream_id IS NULL;

CREATE TABLE reports.stream_segment (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    stream_id        uuid NOT NULL REFERENCES reports.live_stream(id) ON DELETE CASCADE,
    segment_path     text NOT NULL UNIQUE,
    seq              integer NOT NULL,
    duration_s       real,
    state            text NOT NULL DEFAULT 'pending',
    attempts         smallint NOT NULL DEFAULT 0,
    next_attempt_at  timestamptz NOT NULL DEFAULT now(),
    media_id         uuid REFERENCES reports.media(id) ON DELETE SET NULL,
    last_error       text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    done_at          timestamptz,
    CONSTRAINT ck_stream_segment_state CHECK (state IN ('pending', 'done', 'failed', 'missing')),
    CONSTRAINT uq_stream_segment_seq UNIQUE (stream_id, seq)
);
CREATE INDEX ix_stream_segment_pending ON reports.stream_segment (next_attempt_at) WHERE state = 'pending';
"""


DOWNGRADE = r"""
DROP TABLE reports.stream_segment;
DROP INDEX reports.ix_media_vision_pending;
DROP INDEX reports.ix_media_stream;
-- Recordings and vision frames belong to streams: they go with them (their objects stay in S3).
DELETE FROM reports.stream_detection;
DELETE FROM reports.media WHERE stream_id IS NOT NULL;
ALTER TABLE reports.media DROP CONSTRAINT fk_media_stream_id_live_stream;
DROP TABLE reports.stream_detection;
DROP TABLE reports.stream_location;
DROP TABLE reports.live_stream;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
