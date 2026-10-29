"""Drones as read-only sources (L5b, docs/phase-l/design-l5.md §3.0 and §3.3) [SIM until the type is known].

* ``reports.drone_telemetry``: where a drone was, read from its own stream through MediaMTX (KLV, MISB ST 0601) or a
  bridge on the local network: position, altitude, heading, the camera's direction and opening, and the battery and
  flight mode when the source carries them. (drone, at) is unique.
* ``reports.drone_zone``: the work areas and no-fly zones a room draws for its gouvernorat.
* ``reports.drone_alert``: leaving a work area, nearing or entering a no-fly zone, low battery. Shown to the room,
  acknowledged by an agent.

There is no table, column or route that sends anything to a drone: the pilot alone flies it (tests/test_drones.py
fails if a command path appears).

Revision ID: 0071_drones
Revises: 0070_towers
Create Date: 2026-10-28
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0071_drones"
down_revision: str | None = "0070_towers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OWN = "ehimaya.sees_all() OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat())"
_STREAM = "EXISTS (SELECT 1 FROM reports.live_stream s WHERE s.id = stream_id)"
_SYSTEM = "ehimaya.scope() = 'system'"

UPGRADE = f"""
CREATE TABLE reports.drone_zone (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    gouvernorat_code  smallint NOT NULL REFERENCES geo.gouvernorat(code),
    kind              text NOT NULL CHECK (kind IN ('work', 'no_fly')),
    name              text NOT NULL CHECK (char_length(name) BETWEEN 2 AND 100),
    area              geography(POLYGON, 4326) NOT NULL,
    margin_m          integer NOT NULL DEFAULT 500 CHECK (margin_m BETWEEN 0 AND 5000),
    active            boolean NOT NULL DEFAULT true,
    created_by        text NOT NULL,
    created_by_name   text,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_drone_zone_gouvernorat ON reports.drone_zone (gouvernorat_code) WHERE active;
CREATE INDEX ix_drone_zone_area ON reports.drone_zone USING gist (area);

CREATE TABLE reports.drone_telemetry (
    id               bigserial PRIMARY KEY,
    stream_id        uuid NOT NULL REFERENCES reports.live_stream(id) ON DELETE CASCADE,
    at               timestamptz NOT NULL,
    lat              double precision NOT NULL CHECK (lat BETWEEN -90 AND 90),
    lon              double precision NOT NULL CHECK (lon BETWEEN -180 AND 180),
    alt_m            real CHECK (alt_m BETWEEN -900 AND 19000),
    heading_deg      real CHECK (heading_deg >= 0 AND heading_deg < 360),
    sensor_az_deg    real CHECK (sensor_az_deg >= 0 AND sensor_az_deg < 360),
    sensor_hfov_deg  real CHECK (sensor_hfov_deg > 0 AND sensor_hfov_deg <= 180),
    battery_pct      real CHECK (battery_pct BETWEEN 0 AND 100),
    mode             text CHECK (char_length(mode) <= 32),
    received_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_drone_telemetry UNIQUE (stream_id, at)
);
CREATE INDEX ix_drone_telemetry_at ON reports.drone_telemetry (stream_id, at DESC);

CREATE TABLE reports.drone_alert (
    id               bigserial PRIMARY KEY,
    stream_id        uuid NOT NULL REFERENCES reports.live_stream(id) ON DELETE CASCADE,
    gouvernorat_code smallint REFERENCES geo.gouvernorat(code),
    at               timestamptz NOT NULL,
    kind             text NOT NULL CHECK (kind IN ('left_work_area', 'near_no_fly', 'in_no_fly', 'low_battery')),
    zone_id          uuid REFERENCES reports.drone_zone(id) ON DELETE SET NULL,
    detail           jsonb NOT NULL DEFAULT '{{}}',
    acknowledged_by  text,
    acknowledged_by_name text,
    acknowledged_at  timestamptz
);
CREATE INDEX ix_drone_alert_open ON reports.drone_alert (stream_id, kind, at DESC);

ALTER TABLE reports.drone_zone ENABLE ROW LEVEL SECURITY;
CREATE POLICY drone_zone_read ON reports.drone_zone FOR SELECT USING ({_OWN});
CREATE POLICY drone_zone_insert ON reports.drone_zone FOR INSERT WITH CHECK ({_OWN});
CREATE POLICY drone_zone_update ON reports.drone_zone FOR UPDATE USING ({_OWN}) WITH CHECK ({_OWN});

ALTER TABLE reports.drone_telemetry ENABLE ROW LEVEL SECURITY;
CREATE POLICY drone_telemetry_read ON reports.drone_telemetry FOR SELECT USING ({_STREAM});
-- Only the reader beside MediaMTX (system scope) writes positions; no staff route does.
CREATE POLICY drone_telemetry_insert ON reports.drone_telemetry FOR INSERT WITH CHECK ({_SYSTEM});

ALTER TABLE reports.drone_alert ENABLE ROW LEVEL SECURITY;
CREATE POLICY drone_alert_read ON reports.drone_alert FOR SELECT USING ({_STREAM});
CREATE POLICY drone_alert_insert ON reports.drone_alert FOR INSERT WITH CHECK ({_SYSTEM});
-- An agent of the drone's room acknowledges an alert.
CREATE POLICY drone_alert_update ON reports.drone_alert FOR UPDATE USING ({_STREAM}) WITH CHECK ({_STREAM});
"""

DOWNGRADE = """
DROP TABLE reports.drone_alert;
DROP TABLE reports.drone_telemetry;
DROP TABLE reports.drone_zone;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
