"""Personnel management, phase H1 (Yamen, 2026-11-08; docs/phase-h/design-h.md).

The personnel department of a gouvernorat (and the central one, for every gouvernorat) keeps the administrative file
of each member of staff, apart from the operations rooms:

* ``inv.agent.category``: intervention, room (logistics) or administrative staff. Room staff are not counted among
  those ready to intervene; they are counted on their own line of the general strength.
* ``inv.agent.post``: the function held (leader, driver, first-aider...), set by an appointment.
* ``personnel.event``: the dated entries of the file: a rank, an appointment, a transfer, a sanction, a reward, with
  the reference of the decision. The current rank and unit follow the latest rank, appointment or transfer.
* ``personnel.absence``: leave and absences with their kind and dates (sick, rest, annual, compensatory, paternity,
  maternity, mission, training, other). No diagnosis is ever stored: a sick leave keeps its certificate reference.

Row level security: a regional department sees its own gouvernorat only, the central one every gouvernorat. The file
follows the member of staff: a transfer to another gouvernorat moves its entries with it.

Revision ID: 0096_personnel
Revises: 0095_stage_messages
Create Date: 2026-11-08
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0096_personnel"
down_revision: str | None = "0095_stage_messages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OWN = "ehimaya.sees_all() OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat())"

UPGRADE = f"""
ALTER TABLE inv.agent ADD COLUMN category text NOT NULL DEFAULT 'intervention'
    CONSTRAINT ck_agent_category CHECK (category IN ('intervention', 'room', 'admin'));
ALTER TABLE inv.agent ADD COLUMN post text CONSTRAINT ck_agent_post CHECK (char_length(post) <= 80);

CREATE SCHEMA IF NOT EXISTS personnel;

CREATE TABLE personnel.event (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id         uuid NOT NULL REFERENCES inv.agent(id) ON DELETE CASCADE,
    gouvernorat_code smallint NOT NULL REFERENCES geo.gouvernorat(code),
    kind             text NOT NULL CHECK (kind IN ('rank', 'appointment', 'transfer', 'sanction', 'reward')),
    effective_on     date NOT NULL,
    -- rank: the new rank; appointment: the function; sanction or reward: its kind (blame, warning, commendation...).
    title            text CHECK (char_length(title) BETWEEN 1 AND 120),
    -- transfer (and an appointment to another unit): the unit joined, and the one left.
    unit_id          uuid REFERENCES ops.unit(id),
    from_unit_id     uuid REFERENCES ops.unit(id),
    -- what the event replaced (rank, post, unit, gouvernorat), put back if it is cancelled while still the latest.
    previous         jsonb NOT NULL DEFAULT '{{}}',
    reference        text CHECK (char_length(reference) <= 120),
    note             text CHECK (char_length(note) <= 1000),
    created_by       text NOT NULL,
    created_by_name  text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    cancelled_at     timestamptz,
    cancelled_by_name text,
    cancel_reason    text CHECK (char_length(cancel_reason) <= 500),
    CONSTRAINT ck_event_title CHECK (kind = 'transfer' OR title IS NOT NULL),
    CONSTRAINT ck_event_unit CHECK (kind <> 'transfer' OR unit_id IS NOT NULL)
);
CREATE INDEX ix_event_agent ON personnel.event (agent_id, effective_on DESC);
CREATE INDEX ix_event_gouvernorat ON personnel.event (gouvernorat_code, kind, effective_on);

CREATE TABLE personnel.absence (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id         uuid NOT NULL REFERENCES inv.agent(id) ON DELETE CASCADE,
    gouvernorat_code smallint NOT NULL REFERENCES geo.gouvernorat(code),
    kind             text NOT NULL CHECK (kind IN ('sick', 'rest', 'annual', 'compensatory', 'paternity',
                                                    'maternity', 'mission', 'training', 'other')),
    starts_on        date NOT NULL,
    ends_on          date NOT NULL,
    reference        text CHECK (char_length(reference) <= 120),
    note             text CHECK (char_length(note) <= 1000),
    version          integer NOT NULL DEFAULT 1,
    created_by       text NOT NULL,
    created_by_name  text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    updated_by_name  text,
    cancelled_at     timestamptz,
    cancelled_by_name text,
    cancel_reason    text CHECK (char_length(cancel_reason) <= 500),
    CONSTRAINT ck_absence_dates CHECK (ends_on >= starts_on),
    CONSTRAINT ck_absence_length CHECK (ends_on - starts_on <= 730)
);
CREATE INDEX ix_absence_agent ON personnel.absence (agent_id, starts_on);
CREATE INDEX ix_absence_period ON personnel.absence (gouvernorat_code, starts_on, ends_on)
    WHERE cancelled_at IS NULL;

ALTER TABLE personnel.event ENABLE ROW LEVEL SECURITY;
CREATE POLICY event_own ON personnel.event USING ({_OWN}) WITH CHECK ({_OWN});
ALTER TABLE personnel.absence ENABLE ROW LEVEL SECURITY;
CREATE POLICY absence_own ON personnel.absence USING ({_OWN}) WITH CHECK ({_OWN});
"""

DOWNGRADE = """
DROP SCHEMA personnel CASCADE;
ALTER TABLE inv.agent DROP COLUMN post;
ALTER TABLE inv.agent DROP COLUMN category;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
