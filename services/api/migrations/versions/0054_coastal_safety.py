"""Coastal safety: marine weather, daily drowning risk, coastal alerts and anonymous beach presence (phase L1b,
docs/phase-l/design-l1b-coastal.md, item 4).

* ``coastal.beach``: one row per beach (a place of the beaches layer): the direction of the open sea from it (to tell an
  onshore wind), and when its marine weather was last fetched and is due again.
* ``coastal.marine_hour``: hourly marine weather at a beach (waves, sea surface temperature, current), from Open-Meteo
  Marine or the simulator ([SIM]).
* ``coastal.beach_day``: the drowning risk of a beach for one day (0 to 100, green / yellow / red) and the factors that
  gave its points.
* ``coastal.alert``: a beach that turned yellow or red for a day, for the coastal rooms (acknowledged by an operator).
* ``coastal.settings``: the declared rules (one row), changed by the Office with an audit record.
* ``coastal.presence``: "I am at this beach" sent by a citizen who agreed, keyed by a keyed hash of a random daily
  token: no account, no position; the count per beach is all that is read, and rows older than a day are purged.

Row-level security: the risk and marine values are public data; alerts follow the gouvernorat scope of the staff;
presence rows are read by the staff only (as counts), and written by anyone through the API.

Revision ID: 0054_coastal_safety
Revises: 0053_layer_management
Create Date: 2026-10-27
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0054_coastal_safety"
down_revision: str | None = "0053_layer_management"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = r"""
CREATE SCHEMA IF NOT EXISTS coastal;

CREATE TABLE coastal.beach (
    feature_id    uuid PRIMARY KEY REFERENCES geo.layer_feature(id) ON DELETE CASCADE,
    seaward_deg   real CHECK (seaward_deg IS NULL OR (seaward_deg >= 0 AND seaward_deg < 360)),
    fetched_at    timestamptz,
    next_fetch_at timestamptz NOT NULL DEFAULT '2000-01-01T00:00:00Z',
    attempts      smallint NOT NULL DEFAULT 0,
    source        text,
    simulated     boolean NOT NULL DEFAULT false
);
CREATE INDEX ix_coastal_beach_due ON coastal.beach (next_fetch_at);

CREATE TABLE coastal.marine_hour (
    feature_id            uuid NOT NULL REFERENCES coastal.beach(feature_id) ON DELETE CASCADE,
    at                    timestamptz NOT NULL,
    wave_height_m         real,
    wave_period_s         real,
    wave_direction_deg    real,
    sea_temp_c            real,
    current_kmh           real,
    current_direction_deg real,
    PRIMARY KEY (feature_id, at)
);

CREATE TABLE coastal.beach_day (
    feature_id  uuid NOT NULL REFERENCES coastal.beach(feature_id) ON DELETE CASCADE,
    day         date NOT NULL,
    score       smallint NOT NULL CHECK (score BETWEEN 0 AND 100),
    level       text NOT NULL CHECK (level IN ('green', 'yellow', 'red')),
    factors     jsonb NOT NULL DEFAULT '[]'::jsonb,
    inputs      jsonb NOT NULL DEFAULT '{}'::jsonb,
    source      text,
    simulated   boolean NOT NULL DEFAULT false,
    computed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (feature_id, day)
);
CREATE INDEX ix_coastal_beach_day_day ON coastal.beach_day (day, level);

CREATE TABLE coastal.alert (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    feature_id       uuid NOT NULL REFERENCES coastal.beach(feature_id) ON DELETE CASCADE,
    day              date NOT NULL,
    level            text NOT NULL CHECK (level IN ('yellow', 'red')),
    previous_level   text CHECK (previous_level IN ('green', 'yellow', 'red')),
    score            smallint NOT NULL,
    gouvernorat_code smallint REFERENCES geo.gouvernorat(code),
    simulated        boolean NOT NULL DEFAULT false,
    created_at       timestamptz NOT NULL DEFAULT now(),
    acked_by         text,
    acked_by_name    text,
    acked_at         timestamptz,
    CONSTRAINT uq_coastal_alert UNIQUE (feature_id, day, level)
);
CREATE INDEX ix_coastal_alert_open ON coastal.alert (day, acked_at);

CREATE TABLE coastal.settings (
    id         smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    rules      jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_by text,
    updated_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO coastal.settings (id) VALUES (1);

CREATE TABLE coastal.presence (
    feature_id uuid NOT NULL REFERENCES coastal.beach(feature_id) ON DELETE CASCADE,
    token_hash bytea NOT NULL,
    at         timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (feature_id, token_hash)
);
CREATE INDEX ix_coastal_presence_at ON coastal.presence (at);

ALTER TABLE coastal.beach ENABLE ROW LEVEL SECURITY;
CREATE POLICY beach_select ON coastal.beach FOR SELECT USING (true);
CREATE POLICY beach_write ON coastal.beach FOR ALL USING (ehimaya.sees_all()) WITH CHECK (ehimaya.sees_all());

ALTER TABLE coastal.marine_hour ENABLE ROW LEVEL SECURITY;
CREATE POLICY marine_hour_select ON coastal.marine_hour FOR SELECT USING (true);
CREATE POLICY marine_hour_write ON coastal.marine_hour FOR ALL USING (ehimaya.scope() = 'system')
    WITH CHECK (ehimaya.scope() = 'system');

ALTER TABLE coastal.beach_day ENABLE ROW LEVEL SECURITY;
CREATE POLICY beach_day_select ON coastal.beach_day FOR SELECT USING (true);
CREATE POLICY beach_day_write ON coastal.beach_day FOR ALL USING (ehimaya.scope() = 'system')
    WITH CHECK (ehimaya.scope() = 'system');

ALTER TABLE coastal.alert ENABLE ROW LEVEL SECURITY;
CREATE POLICY alert_select ON coastal.alert FOR SELECT USING (
    ehimaya.sees_all() OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat()));
CREATE POLICY alert_insert ON coastal.alert FOR INSERT WITH CHECK (ehimaya.scope() = 'system');
CREATE POLICY alert_update ON coastal.alert FOR UPDATE USING (
    ehimaya.sees_all() OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat()));
CREATE POLICY alert_delete ON coastal.alert FOR DELETE USING (ehimaya.scope() = 'system');

ALTER TABLE coastal.settings ENABLE ROW LEVEL SECURITY;
CREATE POLICY settings_select ON coastal.settings FOR SELECT USING (true);
CREATE POLICY settings_update ON coastal.settings FOR UPDATE USING (ehimaya.sees_all());

ALTER TABLE coastal.presence ENABLE ROW LEVEL SECURITY;
CREATE POLICY presence_select ON coastal.presence FOR SELECT USING (
    ehimaya.scope() IN ('system', 'national', 'gouvernorat'));
CREATE POLICY presence_insert ON coastal.presence FOR INSERT WITH CHECK (ehimaya.scope() <> 'none');
CREATE POLICY presence_update ON coastal.presence FOR UPDATE USING (ehimaya.scope() <> 'none');
CREATE POLICY presence_delete ON coastal.presence FOR DELETE USING (ehimaya.scope() = 'system');
"""

DOWNGRADE = r"""
DROP SCHEMA coastal CASCADE;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
