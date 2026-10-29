"""Indicators out of their habit (AI4, docs/phase-l/design-l5.md §4.4).

``ai.anomaly``: an indicator of a gouvernorat or a delegation (the number of reports, the arrival time, the completion
rate of the programme) found outside its usual series on a day, with the figures it was compared to. Kept once per
indicator, place and day, so it is audited once and listed in the alert centre; nothing is sent to a citizen.

Revision ID: 0075_anomalies
Revises: 0074_programme_suggestions
Create Date: 2026-10-29
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0075_anomalies"
down_revision: str | None = "0074_programme_suggestions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OWN = "ehimaya.sees_all() OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat())"

UPGRADE = f"""
CREATE TABLE ai.anomaly (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    indicator        text NOT NULL CHECK (indicator IN ('reports', 'arrival', 'completion')),
    unit_key         text NOT NULL CHECK (char_length(unit_key) BETWEEN 3 AND 40),
    gouvernorat_code smallint NOT NULL REFERENCES geo.gouvernorat(code),
    delegation_id    integer REFERENCES geo.delegation(id),
    day              date NOT NULL,
    value            double precision NOT NULL,
    mean             double precision NOT NULL,
    std              double precision NOT NULL CHECK (std >= 0),
    z                double precision NOT NULL,
    baseline         text NOT NULL CHECK (baseline IN ('season', 'recent')),
    points           smallint NOT NULL CHECK (points > 0),
    n                integer NOT NULL CHECK (n >= 0),
    raised_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_anomaly UNIQUE (indicator, unit_key, day)
);
CREATE INDEX ix_anomaly_day ON ai.anomaly (day DESC, gouvernorat_code);

ALTER TABLE ai.anomaly ENABLE ROW LEVEL SECURITY;
CREATE POLICY anomaly_select ON ai.anomaly FOR SELECT USING ({_OWN});
CREATE POLICY anomaly_insert ON ai.anomaly FOR INSERT WITH CHECK (ehimaya.sees_all());
"""

DOWNGRADE = """
DROP TABLE ai.anomaly;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
