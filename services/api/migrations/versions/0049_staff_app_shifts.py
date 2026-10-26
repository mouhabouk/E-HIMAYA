"""Staff app: devices, shifts, mission steps, first field report and casualties (phase P4a,
docs/phase-p4/design-staff.md §4).

* ``ops.staff_device`` — a team leader's phone bound to their staff account (push token, last seen). Revoking it is the
  remote wipe: the API answers ``410 device_revoked`` and the app erases everything.
* ``ops.shift`` — a team leader on duty with one vehicle (``ops.resource``) and a crew. One open shift per leader and
  per vehicle.
* ``ops.assignment`` gains ``shift_id`` (the shift that holds the vehicle when the order is given or acknowledged) and
  ``acknowledged_at`` (the leader saw the mission).
* ``ops.crew_event`` — every write from the staff app, keyed by the id the phone generates: a write sent twice is
  applied once. Keeps the phone's clock (``device_at``) next to the server's.
* ``ops.field_report`` — the first field report (confirmed category and classification, severity 1 to 4, backup
  needed, danger to the crew).
* ``ops.casualty_count`` — live counters of an incident (injured, deceased, rescued, trapped).
* ``ops.casualty_transport`` — a person taken to hospital: triage colour, age band, sex, hospital. No name.
* ``notify.outbox`` takes a third channel, ``staff_push``: a content-free push to one staff device (its token in
  ``address``), for the mission alert.

Row-level security: devices and shifts are read in the leader's gouvernorat (and by the leader); a shift is also read
wherever one of its assignments is; the other tables follow their incident. Downgrade drops everything.

Revision ID: 0049_staff_app_shifts
Revises: 0048_app_feedback_email_codes
Create Date: 2026-10-26
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0049_staff_app_shifts"
down_revision: str | None = "0048_app_feedback_email_codes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = r"""
CREATE TABLE ops.staff_device (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    subject           text NOT NULL,
    holder_name       text CHECK (char_length(holder_name) <= 120),
    gouvernorat_code  smallint NOT NULL REFERENCES geo.gouvernorat(code),
    label             text CHECK (char_length(label) <= 80),
    platform          text NOT NULL CHECK (platform IN ('android', 'ios')),
    app_build         integer CHECK (app_build BETWEEN 1 AND 1000000),
    push_token        text CHECK (char_length(push_token) <= 4096),
    created_at        timestamptz NOT NULL DEFAULT now(),
    last_seen_at      timestamptz NOT NULL DEFAULT now(),
    revoked_at        timestamptz,
    revoked_by        text
);
CREATE INDEX ix_staff_device_subject ON ops.staff_device (subject) WHERE revoked_at IS NULL;
CREATE INDEX ix_staff_device_gouvernorat ON ops.staff_device (gouvernorat_code, last_seen_at DESC);

CREATE TABLE ops.shift (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    subject           text NOT NULL,
    leader_name       text CHECK (char_length(leader_name) <= 120),
    device_id         uuid NOT NULL REFERENCES ops.staff_device(id),
    resource_id       uuid NOT NULL REFERENCES ops.resource(id),
    gouvernorat_code  smallint NOT NULL REFERENCES geo.gouvernorat(code),
    crew_size         smallint NOT NULL CHECK (crew_size BETWEEN 1 AND 20),
    crew_names        text CHECK (char_length(crew_names) <= 300),
    started_at        timestamptz NOT NULL DEFAULT now(),
    ended_at          timestamptz
);
CREATE UNIQUE INDEX ux_shift_open_resource ON ops.shift (resource_id) WHERE ended_at IS NULL;
CREATE UNIQUE INDEX ux_shift_open_subject ON ops.shift (subject) WHERE ended_at IS NULL;
CREATE INDEX ix_shift_gouvernorat ON ops.shift (gouvernorat_code, started_at DESC);

ALTER TABLE ops.assignment
    ADD COLUMN shift_id uuid REFERENCES ops.shift(id),
    ADD COLUMN acknowledged_at timestamptz;
CREATE INDEX ix_assignment_shift ON ops.assignment (shift_id) WHERE shift_id IS NOT NULL;

CREATE TABLE ops.crew_event (
    client_id      uuid PRIMARY KEY,
    assignment_id  uuid REFERENCES ops.assignment(id) ON DELETE CASCADE,
    shift_id       uuid REFERENCES ops.shift(id) ON DELETE CASCADE,
    kind           text NOT NULL CHECK (kind IN ('ack', 'status', 'first_report', 'casualties', 'transport')),
    payload        jsonb NOT NULL DEFAULT '{}'::jsonb,
    subject        text NOT NULL,
    device_at      timestamptz,
    received_at    timestamptz NOT NULL DEFAULT now(),
    CHECK (assignment_id IS NOT NULL OR shift_id IS NOT NULL)
);
CREATE INDEX ix_crew_event_assignment ON ops.crew_event (assignment_id, received_at);

CREATE TABLE ops.field_report (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id     uuid NOT NULL REFERENCES ops.incident(id) ON DELETE CASCADE,
    assignment_id   uuid NOT NULL REFERENCES ops.assignment(id) ON DELETE CASCADE,
    kind            text NOT NULL DEFAULT 'first' CHECK (kind IN ('first')),
    category        text NOT NULL,
    classification  text,
    severity        smallint NOT NULL CHECK (severity BETWEEN 1 AND 4),
    backup_needed   boolean NOT NULL DEFAULT false,
    backup_note     text CHECK (char_length(backup_note) <= 300),
    crew_danger     boolean NOT NULL DEFAULT false,
    author          text NOT NULL,
    author_name     text,
    device_at       timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_field_report_incident ON ops.field_report (incident_id, created_at DESC);

CREATE TABLE ops.casualty_count (
    incident_id   uuid PRIMARY KEY REFERENCES ops.incident(id) ON DELETE CASCADE,
    injured       integer NOT NULL DEFAULT 0 CHECK (injured BETWEEN 0 AND 10000),
    deceased      integer NOT NULL DEFAULT 0 CHECK (deceased BETWEEN 0 AND 10000),
    rescued       integer NOT NULL DEFAULT 0 CHECK (rescued BETWEEN 0 AND 10000),
    trapped       integer NOT NULL DEFAULT 0 CHECK (trapped BETWEEN 0 AND 10000),
    updated_by    text,
    updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ops.casualty_transport (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id     uuid NOT NULL REFERENCES ops.incident(id) ON DELETE CASCADE,
    assignment_id   uuid NOT NULL REFERENCES ops.assignment(id) ON DELETE CASCADE,
    triage          text NOT NULL CHECK (triage IN ('red', 'yellow', 'green', 'black')),
    age_band        text NOT NULL CHECK (age_band IN ('child', 'adult', 'elderly', 'unknown')),
    sex             text NOT NULL CHECK (sex IN ('female', 'male', 'unknown')),
    hospital        text NOT NULL CHECK (char_length(hospital) BETWEEN 1 AND 120),
    created_by      text NOT NULL,
    created_by_name text,
    device_at       timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_casualty_transport_incident ON ops.casualty_transport (incident_id, created_at);

ALTER TABLE notify.outbox
    DROP CONSTRAINT outbox_channel_check,
    DROP CONSTRAINT ck_outbox_target,
    ADD CONSTRAINT outbox_channel_check CHECK (channel IN ('push', 'email', 'staff_push')),
    ADD CONSTRAINT ck_outbox_target CHECK (
        (channel = 'push') = (user_id IS NOT NULL) AND (channel IN ('email', 'staff_push')) = (address IS NOT NULL));

ALTER TABLE ops.staff_device ENABLE ROW LEVEL SECURITY;
CREATE POLICY staff_device_select ON ops.staff_device FOR SELECT USING (
    ehimaya.sees_all() OR subject = ehimaya.subject()
    OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat()));
CREATE POLICY staff_device_insert ON ops.staff_device FOR INSERT WITH CHECK (ehimaya.scope() <> 'none');
CREATE POLICY staff_device_update ON ops.staff_device FOR UPDATE USING (
    ehimaya.sees_all() OR subject = ehimaya.subject()
    OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat())) WITH CHECK (ehimaya.scope() <> 'none');

ALTER TABLE ops.shift ENABLE ROW LEVEL SECURITY;
CREATE POLICY shift_select ON ops.shift FOR SELECT USING (
    ehimaya.sees_all() OR subject = ehimaya.subject()
    OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat())
    OR EXISTS (SELECT 1 FROM ops.assignment a WHERE a.shift_id = shift.id));
CREATE POLICY shift_insert ON ops.shift FOR INSERT WITH CHECK (ehimaya.scope() <> 'none');
CREATE POLICY shift_update ON ops.shift FOR UPDATE USING (
    ehimaya.sees_all() OR subject = ehimaya.subject()
    OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat())) WITH CHECK (ehimaya.scope() <> 'none');

ALTER TABLE ops.crew_event ENABLE ROW LEVEL SECURITY;
CREATE POLICY crew_event_select ON ops.crew_event FOR SELECT USING (
    ehimaya.sees_all() OR subject = ehimaya.subject()
    OR (assignment_id IS NOT NULL AND EXISTS (SELECT 1 FROM ops.assignment a WHERE a.id = assignment_id)));
CREATE POLICY crew_event_insert ON ops.crew_event FOR INSERT WITH CHECK (ehimaya.scope() <> 'none');

ALTER TABLE ops.field_report ENABLE ROW LEVEL SECURITY;
CREATE POLICY field_report_select ON ops.field_report FOR SELECT USING (
    EXISTS (SELECT 1 FROM ops.incident i WHERE i.id = incident_id));
CREATE POLICY field_report_insert ON ops.field_report FOR INSERT WITH CHECK (ehimaya.scope() <> 'none');

ALTER TABLE ops.casualty_count ENABLE ROW LEVEL SECURITY;
CREATE POLICY casualty_count_select ON ops.casualty_count FOR SELECT USING (
    EXISTS (SELECT 1 FROM ops.incident i WHERE i.id = incident_id));
CREATE POLICY casualty_count_insert ON ops.casualty_count FOR INSERT WITH CHECK (ehimaya.scope() <> 'none');
CREATE POLICY casualty_count_update ON ops.casualty_count FOR UPDATE USING (
    EXISTS (SELECT 1 FROM ops.incident i WHERE i.id = incident_id)) WITH CHECK (ehimaya.scope() <> 'none');

ALTER TABLE ops.casualty_transport ENABLE ROW LEVEL SECURITY;
CREATE POLICY casualty_transport_select ON ops.casualty_transport FOR SELECT USING (
    EXISTS (SELECT 1 FROM ops.incident i WHERE i.id = incident_id));
CREATE POLICY casualty_transport_insert ON ops.casualty_transport FOR INSERT WITH CHECK (ehimaya.scope() <> 'none');
"""

DOWNGRADE = r"""
DELETE FROM notify.outbox WHERE channel = 'staff_push';
ALTER TABLE notify.outbox
    DROP CONSTRAINT outbox_channel_check,
    DROP CONSTRAINT ck_outbox_target,
    ADD CONSTRAINT outbox_channel_check CHECK (channel IN ('push', 'email')),
    ADD CONSTRAINT ck_outbox_target CHECK (
        (channel = 'push') = (user_id IS NOT NULL) AND (channel = 'email') = (address IS NOT NULL));
DROP TABLE ops.casualty_transport;
DROP TABLE ops.casualty_count;
DROP TABLE ops.field_report;
DROP TABLE ops.crew_event;
DROP POLICY shift_select ON ops.shift;
ALTER TABLE ops.assignment DROP COLUMN acknowledged_at, DROP COLUMN shift_id;
DROP TABLE ops.shift;
DROP TABLE ops.staff_device;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
