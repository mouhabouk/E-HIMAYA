"""Weather layer and spread forecasts (phase 7, docs/api/phase-7-contract.md §1–§2, docs/weather-forecast.md).

* ``weather.grid_point`` — the points of the 0.25° grid laid over Tunisia (filled by the worker on first start), the
  fire weather moisture codes carried from day to day, and the fetch schedule of each point.
* ``weather.observation`` — hourly values per point (past 24 h and next 48 h): wind, temperature, humidity,
  precipitation, the fire weather indices of the day (Canadian FWI System from noon values) and the heavy-rain level.
* ``weather.rule`` — thresholds that turn a forecast into a suggested alert, national (gouvernorat NULL) or per
  gouvernorat; seeded with the national defaults of the contract.
* ``weather.alert_suggestion`` — suggested weather alerts shown to editors and committees; a human accepts (the
  phase 5 alert form opens prefilled, nothing is sent) or dismisses them.
* ``forecast.run`` — fire spread and flood advisory runs of an incident, with their inputs and assumptions.

Weather is not personal data: none of these tables is part of the /me export or erasure. The runtime role's grants
on the two new schemas are applied after the upgrade (migrations/env.py, app/core/db_roles.py).

Revision ID: 0012_weather
Revises: 0011_live_streams
Create Date: 2026-10-20
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0012_weather"
down_revision: str | None = "0011_live_streams"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE = r"""
CREATE SCHEMA weather;
CREATE SCHEMA forecast;

CREATE TABLE weather.grid_point (
    id                serial PRIMARY KEY,
    lat               double precision NOT NULL,
    lon               double precision NOT NULL,
    location          geography(Point, 4326) NOT NULL,
    gouvernorat_code  smallint REFERENCES geo.gouvernorat(code),
    -- Fire weather moisture codes after the noon of codes_date ({"ffmc", "dmc", "dc"}); NULL until spun up.
    codes             jsonb,
    codes_date        date,
    fetched_at        timestamptz,
    next_fetch_at     timestamptz NOT NULL DEFAULT now(),
    attempts          smallint NOT NULL DEFAULT 0,
    source            text,
    simulated         boolean NOT NULL DEFAULT false,
    CONSTRAINT uq_grid_point_position UNIQUE (lat, lon),
    CONSTRAINT ck_grid_point_lat CHECK (lat BETWEEN 29 AND 39),
    CONSTRAINT ck_grid_point_lon CHECK (lon BETWEEN 6 AND 13)
);
CREATE INDEX ix_grid_point_location ON weather.grid_point USING gist (location);
CREATE INDEX ix_grid_point_fetch ON weather.grid_point (next_fetch_at);
CREATE INDEX ix_grid_point_gouvernorat ON weather.grid_point (gouvernorat_code);

CREATE TABLE weather.observation (
    point_id               integer NOT NULL REFERENCES weather.grid_point(id) ON DELETE CASCADE,
    at                     timestamptz NOT NULL,
    temperature_c          real,
    relative_humidity_pct  real,
    wind_speed_kmh         real,
    wind_gust_kmh          real,
    wind_direction_deg     real,
    precipitation_mm       real,
    precipitation_24h_mm   real,
    weather_code           smallint,
    ffmc                   real,
    dmc                    real,
    dc                     real,
    isi                    real,
    bui                    real,
    fwi                    real,
    fire_danger            text,
    heavy_rain             text NOT NULL DEFAULT 'none',
    -- false: the hour was past when fetched (analysis); true: forecast.
    forecast               boolean NOT NULL DEFAULT true,
    PRIMARY KEY (point_id, at),
    CONSTRAINT ck_observation_fire_danger CHECK (fire_danger IS NULL OR fire_danger IN
        ('low', 'moderate', 'high', 'very_high', 'extreme')),
    CONSTRAINT ck_observation_heavy_rain CHECK (heavy_rain IN ('none', 'watch', 'warning')),
    CONSTRAINT ck_observation_humidity CHECK (relative_humidity_pct IS NULL OR relative_humidity_pct BETWEEN 0 AND 100)
);
CREATE INDEX ix_observation_at ON weather.observation (at);

CREATE TABLE weather.rule (
    id                serial PRIMARY KEY,
    gouvernorat_code  smallint REFERENCES geo.gouvernorat(code),
    metric            text NOT NULL,
    threshold         real NOT NULL,
    severity          text NOT NULL,
    enabled           boolean NOT NULL DEFAULT true,
    updated_by        text,
    updated_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_rule_metric CHECK (metric IN ('fire_danger', 'wind_gust', 'rain_24h', 'rain_1h')),
    CONSTRAINT ck_rule_severity CHECK (severity IN ('high', 'medium', 'low')),
    -- fire_danger: class rank 0 (low) to 4 (extreme); others: km/h or mm.
    CONSTRAINT ck_rule_threshold CHECK (threshold >= 0 AND (metric <> 'fire_danger' OR threshold <= 4))
);
CREATE UNIQUE INDEX ux_rule_scope_metric ON weather.rule (COALESCE(gouvernorat_code, 0), metric);
INSERT INTO weather.rule (gouvernorat_code, metric, threshold, severity, updated_by) VALUES
    (NULL, 'fire_danger', 3, 'medium', 'system'),
    (NULL, 'wind_gust', 70, 'medium', 'system'),
    (NULL, 'rain_24h', 50, 'medium', 'system'),
    (NULL, 'rain_1h', 20, 'high', 'system');

CREATE TABLE weather.alert_suggestion (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    metric            text NOT NULL,
    gouvernorat_codes smallint[] NOT NULL,
    category          text NOT NULL DEFAULT 'weather',
    hazard            text NOT NULL,
    severity          text NOT NULL,
    title             jsonb NOT NULL,
    body              jsonb NOT NULL,
    evidence          jsonb NOT NULL DEFAULT '{}'::jsonb,
    valid_from        timestamptz NOT NULL,
    valid_until       timestamptz NOT NULL,
    status            text NOT NULL DEFAULT 'pending',
    simulated         boolean NOT NULL DEFAULT false,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    decided_by        text,
    decided_at        timestamptz,
    dismiss_reason    text,
    CONSTRAINT ck_suggestion_metric CHECK (metric IN ('fire_danger', 'wind_gust', 'rain_24h', 'rain_1h')),
    CONSTRAINT ck_suggestion_category CHECK (category = 'weather'),
    CONSTRAINT ck_suggestion_severity CHECK (severity IN ('high', 'medium', 'low')),
    CONSTRAINT ck_suggestion_status CHECK (status IN ('pending', 'accepted', 'dismissed', 'expired')),
    CONSTRAINT ck_suggestion_codes CHECK (cardinality(gouvernorat_codes) BETWEEN 1 AND 24),
    CONSTRAINT ck_suggestion_window CHECK (valid_until > valid_from),
    CONSTRAINT ck_suggestion_reason CHECK (char_length(dismiss_reason) <= 500)
);
CREATE INDEX ix_suggestion_status ON weather.alert_suggestion (status, created_at DESC);
CREATE INDEX ix_suggestion_codes ON weather.alert_suggestion USING gin (gouvernorat_codes);

CREATE TABLE forecast.run (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id  uuid NOT NULL REFERENCES ops.incident(id) ON DELETE CASCADE,
    kind         text NOT NULL,
    model        text NOT NULL,
    inputs       jsonb NOT NULL,
    result       jsonb NOT NULL,
    assumptions  jsonb NOT NULL DEFAULT '[]'::jsonb,
    simulated    boolean NOT NULL DEFAULT false,
    created_by   text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_run_kind CHECK (kind IN ('fire', 'flood'))
);
CREATE INDEX ix_run_incident ON forecast.run (incident_id, created_at DESC);
"""


DOWNGRADE = r"""
DROP TABLE forecast.run;
DROP TABLE weather.alert_suggestion;
DROP TABLE weather.rule;
DROP TABLE weather.observation;
DROP TABLE weather.grid_point;
DROP SCHEMA forecast;
DROP SCHEMA weather;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
