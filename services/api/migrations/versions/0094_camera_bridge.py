"""The camera bridge (Yamen, 2026-11-01): a thermal or fire-detecting camera sends its own alarm through a small
bridge on the institution's network, signed with a key of the camera.

* ``reports.live_stream.event_key_enc``: the camera's signing key, encrypted (shown once in the dashboard);
* ``reports.live_stream.bridge_seen_at``: the bridge's last heartbeat;
* ``reports.camera_event``: every alarm received, unique per (camera, at, label) against replays.

Revision ID: 0094_camera_bridge
Revises: 0093_prealert_stages
Create Date: 2026-11-01
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0094_camera_bridge"
down_revision: str | None = "0093_prealert_stages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = """
ALTER TABLE reports.live_stream ADD COLUMN event_key_enc bytea;
ALTER TABLE reports.live_stream ADD COLUMN bridge_seen_at timestamptz;
CREATE TABLE reports.camera_event (
    id bigserial PRIMARY KEY,
    stream_id uuid NOT NULL REFERENCES reports.live_stream(id) ON DELETE CASCADE,
    at timestamptz NOT NULL,
    label text NOT NULL CHECK (label IN ('fire', 'smoke')),
    confidence real NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    temperature_c real,
    vendor_event text,
    alerted boolean NOT NULL DEFAULT false,
    media_id uuid REFERENCES reports.media(id) ON DELETE SET NULL,
    received_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_camera_event UNIQUE (stream_id, at, label)
);
CREATE INDEX ix_camera_event_received ON reports.camera_event (received_at);
"""

DOWNGRADE = """
DROP TABLE reports.camera_event;
ALTER TABLE reports.live_stream DROP COLUMN bridge_seen_at;
ALTER TABLE reports.live_stream DROP COLUMN event_key_enc;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
