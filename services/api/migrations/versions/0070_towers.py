"""Watch towers (L5b, docs/phase-l/design-l5.md §3.0 and §3.2) [SIM until the field trial]: a fixed camera of the
Office on a tower, its field of view drawn on the map, and the fire and smoke its edge computer confirms.

* ``reports.camera_tower``: the tower of a fixed "camera" source (``reports.live_stream``): its code, place, bearing,
  field of view and range, and the signing key of its edge computer (encrypted; shown once when created or rotated,
  never logged). The video itself still travels through MediaMTX, as in phase 9.
* ``reports.tower_event``: one fire or smoke the edge computer confirmed in 3 of 5 frames and signed, relayed by the
  gateway beside MediaMTX. (tower, at, label) is unique, so a replayed event is refused.

An event becomes a suggestion in the alert centre (``weather.alert_suggestion``, metric ``tower_fire`` or
``tower_smoke``) and a ``stream.alert`` on the live feed; never an automatic report, and nothing reaches a citizen
outside the existing two-person path.

Revision ID: 0070_towers
Revises: 0069_sensors
Create Date: 2026-10-28
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0070_towers"
down_revision: str | None = "0069_sensors"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OWN = "ehimaya.sees_all() OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat())"
_METRICS = (
    "'fire_danger', 'wind_gust', 'rain_24h', 'rain_1h', 'sensor_rain_1h', 'sensor_water_level', 'sensor_temperature'"
)

UPGRADE = f"""
CREATE TABLE reports.camera_tower (
    stream_id         uuid PRIMARY KEY REFERENCES reports.live_stream(id) ON DELETE CASCADE,
    code              text NOT NULL UNIQUE CHECK (code ~ '^[A-Za-z0-9][A-Za-z0-9_-]{{1,39}}$'),
    gouvernorat_code  smallint NOT NULL REFERENCES geo.gouvernorat(code),
    lat               double precision NOT NULL CHECK (lat BETWEEN 30 AND 38),
    lon               double precision NOT NULL CHECK (lon BETWEEN 7 AND 12),
    bearing_deg       smallint NOT NULL CHECK (bearing_deg BETWEEN 0 AND 359),
    fov_deg           smallint NOT NULL CHECK (fov_deg BETWEEN 5 AND 360),
    range_m           integer NOT NULL CHECK (range_m BETWEEN 100 AND 50000),
    simulated         boolean NOT NULL DEFAULT true,
    key_enc           bytea NOT NULL,
    key_version       smallint NOT NULL DEFAULT 1,
    last_event_at     timestamptz,
    created_by        text NOT NULL,
    created_by_name   text,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_camera_tower_gouvernorat ON reports.camera_tower (gouvernorat_code);

CREATE TABLE reports.tower_event (
    id             bigserial PRIMARY KEY,
    stream_id      uuid NOT NULL REFERENCES reports.camera_tower(stream_id) ON DELETE CASCADE,
    at             timestamptz NOT NULL,
    label          text NOT NULL CHECK (label IN ('fire', 'smoke')),
    confidence     real NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    hits           smallint NOT NULL,
    frames         smallint NOT NULL,
    model          text,
    media_id       uuid REFERENCES reports.media(id) ON DELETE SET NULL,
    suggestion_id  uuid REFERENCES weather.alert_suggestion(id) ON DELETE SET NULL,
    received_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_tower_event UNIQUE (stream_id, at, label),
    CONSTRAINT ck_tower_event_frames CHECK (hits BETWEEN 1 AND frames AND frames BETWEEN 1 AND 30)
);
CREATE INDEX ix_tower_event_at ON reports.tower_event (stream_id, at DESC);

ALTER TABLE reports.camera_tower ENABLE ROW LEVEL SECURITY;
CREATE POLICY camera_tower_read ON reports.camera_tower FOR SELECT USING ({_OWN});
CREATE POLICY camera_tower_insert ON reports.camera_tower FOR INSERT WITH CHECK ({_OWN});
CREATE POLICY camera_tower_update ON reports.camera_tower FOR UPDATE USING ({_OWN}) WITH CHECK ({_OWN});

ALTER TABLE reports.tower_event ENABLE ROW LEVEL SECURITY;
CREATE POLICY tower_event_read ON reports.tower_event FOR SELECT
    USING (EXISTS (SELECT 1 FROM reports.camera_tower t WHERE t.stream_id = tower_event.stream_id));
-- Only the gateway's path (system scope) writes events (and links their frame and suggestion); no staff route does.
CREATE POLICY tower_event_insert ON reports.tower_event FOR INSERT WITH CHECK (ehimaya.scope() = 'system');
CREATE POLICY tower_event_update ON reports.tower_event FOR UPDATE
    USING (ehimaya.scope() = 'system') WITH CHECK (ehimaya.scope() = 'system');

ALTER TABLE weather.alert_suggestion DROP CONSTRAINT ck_suggestion_metric;
ALTER TABLE weather.alert_suggestion ADD CONSTRAINT ck_suggestion_metric
    CHECK (metric IN ({_METRICS}, 'tower_fire', 'tower_smoke'));
"""  # noqa: S608 (constants only, no input)

DOWNGRADE = f"""
DELETE FROM weather.alert_suggestion WHERE metric IN ('tower_fire', 'tower_smoke');
ALTER TABLE weather.alert_suggestion DROP CONSTRAINT ck_suggestion_metric;
ALTER TABLE weather.alert_suggestion ADD CONSTRAINT ck_suggestion_metric CHECK (metric IN ({_METRICS}));
DROP TABLE reports.tower_event;
DROP TABLE reports.camera_tower;
"""  # noqa: S608 (constants only, no input)


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
