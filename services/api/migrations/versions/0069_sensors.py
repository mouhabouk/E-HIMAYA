"""Sensors (L5b, docs/phase-l/design-l5.md §3.0 and §3.1) [SIM until a real source is named]: rain gauges, water
levels and temperatures of the Office, the weather institute or the agriculture ministry, read on the local network.

* ``sensor.device``: one sensor, its gouvernorat and place, its "watch" and "alarm" thresholds, the time after which
  it is "silent", and its signing key (encrypted; shown once when created or rotated, never logged).
* ``sensor.reading``: one signed reading the gateway beside MediaMTX relayed. (sensor, at) is unique, so a replayed
  reading is refused.

A threshold crossed becomes a suggestion in the alert centre (``weather.alert_suggestion``, metric ``sensor_*``): an
agent reviews it, and nothing reaches a citizen outside the existing two-person path.

Revision ID: 0069_sensors
Revises: 0068_import_profile
Create Date: 2026-10-28
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0069_sensors"
down_revision: str | None = "0068_import_profile"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OWN = "ehimaya.sees_all() OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat())"

UPGRADE = f"""
CREATE SCHEMA IF NOT EXISTS sensor;

CREATE TABLE sensor.device (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code              text NOT NULL UNIQUE CHECK (code ~ '^[A-Za-z0-9][A-Za-z0-9_-]{{1,39}}$'),
    name              text NOT NULL CHECK (char_length(name) BETWEEN 2 AND 120),
    kind              text NOT NULL CHECK (kind IN ('rain_1h', 'water_level', 'temperature')),
    gouvernorat_code  smallint NOT NULL REFERENCES geo.gouvernorat(code),
    lat               double precision NOT NULL CHECK (lat BETWEEN 30 AND 38),
    lon               double precision NOT NULL CHECK (lon BETWEEN 7 AND 12),
    provider          text NOT NULL CHECK (char_length(provider) BETWEEN 2 AND 80),
    watch_threshold   double precision NOT NULL,
    alarm_threshold   double precision NOT NULL,
    silent_after_min  smallint NOT NULL DEFAULT 30 CHECK (silent_after_min BETWEEN 5 AND 1440),
    enabled           boolean NOT NULL DEFAULT true,
    simulated         boolean NOT NULL DEFAULT true,
    key_enc           bytea NOT NULL,
    key_version       smallint NOT NULL DEFAULT 1,
    last_value        double precision,
    last_at           timestamptz,
    level             text NOT NULL DEFAULT 'normal' CHECK (level IN ('normal', 'watch', 'alarm')),
    level_since       timestamptz,
    created_by        text NOT NULL,
    created_by_name   text,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_sensor_thresholds CHECK (alarm_threshold >= watch_threshold)
);
CREATE INDEX ix_sensor_gouvernorat ON sensor.device (gouvernorat_code);

CREATE TABLE sensor.reading (
    id           bigserial PRIMARY KEY,
    sensor_id    uuid NOT NULL REFERENCES sensor.device(id) ON DELETE CASCADE,
    at           timestamptz NOT NULL,
    value        double precision NOT NULL,
    received_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_sensor_reading UNIQUE (sensor_id, at)
);
CREATE INDEX ix_sensor_reading_at ON sensor.reading (sensor_id, at DESC);

ALTER TABLE sensor.device ENABLE ROW LEVEL SECURITY;
CREATE POLICY device_read ON sensor.device FOR SELECT USING ({_OWN});
CREATE POLICY device_insert ON sensor.device FOR INSERT WITH CHECK ({_OWN});
CREATE POLICY device_update ON sensor.device FOR UPDATE USING ({_OWN}) WITH CHECK ({_OWN});

ALTER TABLE sensor.reading ENABLE ROW LEVEL SECURITY;
CREATE POLICY reading_read ON sensor.reading FOR SELECT
    USING (EXISTS (SELECT 1 FROM sensor.device d WHERE d.id = sensor_id));
-- Only the gateway's path (system scope) writes readings; no staff route does.
CREATE POLICY reading_insert ON sensor.reading FOR INSERT WITH CHECK (ehimaya.scope() = 'system');

ALTER TABLE weather.alert_suggestion DROP CONSTRAINT ck_suggestion_metric;
ALTER TABLE weather.alert_suggestion ADD CONSTRAINT ck_suggestion_metric CHECK (metric IN (
    'fire_danger', 'wind_gust', 'rain_24h', 'rain_1h', 'sensor_rain_1h', 'sensor_water_level', 'sensor_temperature'
));
"""  # noqa: S608 (constants only, no input)

DOWNGRADE = """
DELETE FROM weather.alert_suggestion WHERE metric LIKE 'sensor\\_%';
ALTER TABLE weather.alert_suggestion DROP CONSTRAINT ck_suggestion_metric;
ALTER TABLE weather.alert_suggestion ADD CONSTRAINT ck_suggestion_metric
    CHECK (metric IN ('fire_danger', 'wind_gust', 'rain_24h', 'rain_1h'));
DROP SCHEMA sensor CASCADE;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
