"""Crew accountability in danger zones (PAR), OS7 (Yamen, 2026-11-12; docs/phase-os7/design-os7.md).

* ``par.setting``: the intervals per gouvernorat (hot zone, warm zone), the grace before the alarm and the automatic
  checks on events. Changed by the operations commander and the regional room; defaults in code when absent.
* ``par.team``: a team (an assignment of a vehicle on shift) inside a danger zone: its members, those temporarily out
  and why, the last confirmation, a special time for the next check, a pause and its reason, the exit headcount.
* ``par.missing``: a missing resource (radio, breathing apparatus ...), who had it, its frozen last place, the
  replacement sent and its recovery.
* ``par.sitrep``: the team leader's word from the scene: under control or not, reinforcement, the text (typed, or
  dictated and corrected).
* ``par.event``: the dated log of the check, filed with the intervention.
* ``par.closure``: the end of the check of an incident, by the commander or when the incident is closed.

Row level security: everything follows the incident's gouvernorat, like the rest of operations.

Revision ID: 0107_par
Revises: 0106_liaison
Create Date: 2026-11-12
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0107_par"
down_revision: str | None = "0106_liaison"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OWN = "ehimaya.sees_all() OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat())"

UPGRADE = f"""
CREATE SCHEMA IF NOT EXISTS par;

CREATE TABLE par.setting (
    gouvernorat_code smallint PRIMARY KEY REFERENCES geo.gouvernorat(code),
    hot_s            integer NOT NULL CHECK (hot_s IN (300, 600, 900)),
    warm_s           integer NOT NULL CHECK (warm_s IN (600, 900, 1200)),
    grace_s          integer NOT NULL CHECK (grace_s BETWEEN 30 AND 180),
    auto_events      text[] NOT NULL DEFAULT '{{}}',
    updated_at       timestamptz NOT NULL DEFAULT now(),
    updated_by_name  text CHECK (char_length(updated_by_name) <= 200)
);

CREATE TABLE par.team (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    assignment_id      uuid NOT NULL REFERENCES ops.assignment(id) ON DELETE CASCADE,
    incident_id        uuid NOT NULL REFERENCES ops.incident(id) ON DELETE CASCADE,
    gouvernorat_code   smallint REFERENCES geo.gouvernorat(code),
    label              text NOT NULL CHECK (char_length(label) BETWEEN 1 AND 120),
    task               text CHECK (char_length(task) <= 200),
    zone               text NOT NULL CHECK (zone IN ('hot', 'warm')),
    members            jsonb NOT NULL DEFAULT '[]',
    away               jsonb NOT NULL DEFAULT '{{}}',
    leader_subject     text NOT NULL,
    leader_name        text CHECK (char_length(leader_name) <= 200),
    entered_at         timestamptz NOT NULL DEFAULT now(),
    last_confirmed_at  timestamptz NOT NULL DEFAULT now(),
    next_at            timestamptz,
    paused_at          timestamptz,
    pause_reason       text CHECK (char_length(pause_reason) <= 400),
    alarmed_at         timestamptz,
    out_at             timestamptz,
    out_count          smallint,
    CONSTRAINT ck_team_pause CHECK ((paused_at IS NULL) = (pause_reason IS NULL))
);
-- One team in a zone per assignment at a time; it can enter again after leaving.
CREATE UNIQUE INDEX uq_team_inside ON par.team (assignment_id) WHERE out_at IS NULL;
CREATE INDEX ix_team_incident ON par.team (incident_id);

CREATE TABLE par.missing (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id          uuid NOT NULL REFERENCES par.team(id) ON DELETE CASCADE,
    incident_id      uuid NOT NULL REFERENCES ops.incident(id) ON DELETE CASCADE,
    gouvernorat_code smallint REFERENCES geo.gouvernorat(code),
    resource         text NOT NULL CHECK (char_length(resource) BETWEEN 2 AND 80),
    carrier          text NOT NULL CHECK (char_length(carrier) BETWEEN 1 AND 200),
    place            text CHECK (char_length(place) <= 200),
    location         geography(POINT, 4326),
    reported_at      timestamptz NOT NULL DEFAULT now(),
    reported_by_name text CHECK (char_length(reported_by_name) <= 200),
    replacement_at   timestamptz,
    replacement_by_name text CHECK (char_length(replacement_by_name) <= 200),
    recovered_at     timestamptz,
    recovered_by_name text CHECK (char_length(recovered_by_name) <= 200)
);
CREATE INDEX ix_missing_incident ON par.missing (incident_id);

CREATE TABLE par.sitrep (
    id               bigserial PRIMARY KEY,
    team_id          uuid NOT NULL REFERENCES par.team(id) ON DELETE CASCADE,
    incident_id      uuid NOT NULL REFERENCES ops.incident(id) ON DELETE CASCADE,
    gouvernorat_code smallint REFERENCES geo.gouvernorat(code),
    at               timestamptz NOT NULL DEFAULT now(),
    situation        text NOT NULL CHECK (situation IN ('controlled', 'progress', 'not_controlled')),
    reinforcement    boolean NOT NULL DEFAULT false,
    text             text CHECK (char_length(text) <= 2000),
    voice_seconds    smallint CHECK (voice_seconds BETWEEN 1 AND 600),
    transcript       text CHECK (char_length(transcript) <= 2000),
    by_name          text CHECK (char_length(by_name) <= 200)
);
CREATE INDEX ix_sitrep_incident ON par.sitrep (incident_id, at DESC);

CREATE TABLE par.event (
    id               bigserial PRIMARY KEY,
    incident_id      uuid NOT NULL REFERENCES ops.incident(id) ON DELETE CASCADE,
    team_id          uuid REFERENCES par.team(id) ON DELETE CASCADE,
    gouvernorat_code smallint REFERENCES geo.gouvernorat(code),
    at               timestamptz NOT NULL DEFAULT now(),
    kind             text NOT NULL CHECK (char_length(kind) BETWEEN 2 AND 40),
    text             text NOT NULL CHECK (char_length(text) BETWEEN 1 AND 600),
    by_name          text CHECK (char_length(by_name) <= 200)
);
CREATE INDEX ix_event_incident ON par.event (incident_id, at DESC);

CREATE TABLE par.closure (
    incident_id      uuid PRIMARY KEY REFERENCES ops.incident(id) ON DELETE CASCADE,
    gouvernorat_code smallint REFERENCES geo.gouvernorat(code),
    closed_at        timestamptz NOT NULL DEFAULT now(),
    closed_by_name   text CHECK (char_length(closed_by_name) <= 200),
    automatic        boolean NOT NULL DEFAULT false,
    summary          jsonb NOT NULL DEFAULT '{{}}'
);

ALTER TABLE par.setting ENABLE ROW LEVEL SECURITY;
CREATE POLICY setting_own ON par.setting USING ({_OWN}) WITH CHECK ({_OWN});
ALTER TABLE par.team ENABLE ROW LEVEL SECURITY;
CREATE POLICY team_own ON par.team USING ({_OWN}) WITH CHECK ({_OWN});
ALTER TABLE par.missing ENABLE ROW LEVEL SECURITY;
CREATE POLICY missing_own ON par.missing USING ({_OWN}) WITH CHECK ({_OWN});
ALTER TABLE par.sitrep ENABLE ROW LEVEL SECURITY;
CREATE POLICY sitrep_own ON par.sitrep USING ({_OWN}) WITH CHECK ({_OWN});
ALTER TABLE par.event ENABLE ROW LEVEL SECURITY;
CREATE POLICY event_own ON par.event USING ({_OWN}) WITH CHECK ({_OWN});
ALTER TABLE par.closure ENABLE ROW LEVEL SECURITY;
CREATE POLICY closure_own ON par.closure USING ({_OWN}) WITH CHECK ({_OWN});

-- The change journal (migration 0097): the tables that hold names or the word from the scene keep no value.
SELECT audit.journal_attach('par.setting', false);
SELECT audit.journal_attach('par.team', true);
SELECT audit.journal_attach('par.missing', true);
SELECT audit.journal_attach('par.sitrep', true);
SELECT audit.journal_attach('par.event', true);
SELECT audit.journal_attach('par.closure', true);
"""

DOWNGRADE = """
DROP SCHEMA par CASCADE;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
