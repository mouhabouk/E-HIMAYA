"""Phase D, the demonstration and the apps (review points 25, 19 and S2-1, docs/phase-d/design-d.md).

* ``reports.live_stream.org_id``: the camera of an institution; ``org.prealert``: what the camera saw, the owner's
  answer within the delay (``orgs.prealert_seconds``) and the report it became.
* ``ai.dictation``: one line per dictated text (who, which field, the model's text and the text the user kept,
  the word error rate); the audio itself is never stored.
* ``reports.live_stream.assignment_id``/``incident_id`` and the source ``crew``: a team streams from the staff app
  (review point 17).
* ``identity.volunteer.sms_key_enc``/``sms_last_at``: a volunteer answers a call-out by signed SMS (``EH3``, S2-5).
* ``ops.field_attachment.transcript_enc``: the text of a team's voice message, read once for the mission times.

Revision ID: 0088_phase_d
Revises: 0087_field_agents
Create Date: 2026-10-31
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0088_phase_d"
down_revision: str | None = "0087_field_agents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = """
ALTER TABLE reports.live_stream
    ADD COLUMN org_id uuid REFERENCES org.organization(id) ON DELETE SET NULL,
    ADD CONSTRAINT ck_live_stream_org_camera CHECK (org_id IS NULL OR source IN ('camera', 'sim'));
CREATE INDEX ix_live_stream_org ON reports.live_stream (org_id) WHERE org_id IS NOT NULL;

-- A team streams from the staff app (review point 17): its mission and incident, one active stream per mission.
ALTER TABLE reports.live_stream
    DROP CONSTRAINT ck_live_stream_source,
    ADD CONSTRAINT ck_live_stream_source CHECK (source IN ('app', 'drone', 'camera', 'sim', 'crew')),
    ADD COLUMN assignment_id uuid REFERENCES ops.assignment(id) ON DELETE SET NULL,
    ADD COLUMN incident_id uuid REFERENCES ops.incident(id) ON DELETE SET NULL,
    ADD CONSTRAINT ck_live_stream_crew CHECK (source <> 'crew' OR (assignment_id IS NOT NULL AND created_by IS NOT NULL));
CREATE UNIQUE INDEX ux_live_stream_crew_active ON reports.live_stream (assignment_id)
    WHERE assignment_id IS NOT NULL AND status IN ('pending', 'live');
CREATE INDEX ix_live_stream_incident ON reports.live_stream (incident_id) WHERE incident_id IS NOT NULL;

CREATE TABLE org.prealert (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id       uuid NOT NULL REFERENCES org.organization(id) ON DELETE CASCADE,
    stream_id    uuid REFERENCES reports.live_stream(id) ON DELETE SET NULL,
    source       text NOT NULL CHECK (source IN ('camera', 'sensor')),
    label        text NOT NULL CHECK (label IN ('fire', 'smoke')),
    confidence   real NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    media_id     uuid REFERENCES reports.media(id) ON DELETE SET NULL,
    simulated    boolean NOT NULL DEFAULT false,
    state        text NOT NULL DEFAULT 'pending'
                 CHECK (state IN ('pending', 'cancelled', 'confirmed', 'escalated')),
    raised_at    timestamptz NOT NULL DEFAULT now(),
    deadline_at  timestamptz NOT NULL,
    decided_by   uuid REFERENCES identity.account(user_id),
    decided_at   timestamptz,
    reason       text CHECK (length(reason) <= 200),
    report_id    uuid REFERENCES reports.report(id) ON DELETE SET NULL,
    CONSTRAINT ck_prealert_deadline CHECK (deadline_at > raised_at),
    CONSTRAINT ck_prealert_cancel_reason CHECK (state <> 'cancelled' OR reason IS NOT NULL),
    CONSTRAINT ck_prealert_decided CHECK ((state IN ('cancelled', 'confirmed')) = (decided_at IS NOT NULL))
);
CREATE INDEX ix_prealert_org ON org.prealert (org_id, raised_at DESC);
CREATE INDEX ix_prealert_due ON org.prealert (deadline_at) WHERE state = 'pending';
CREATE UNIQUE INDEX ux_prealert_pending_stream ON org.prealert (stream_id)
    WHERE state = 'pending' AND stream_id IS NOT NULL;

CREATE TABLE ai.dictation (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    actor       text NOT NULL,
    field       text NOT NULL CHECK (field ~ '^[a-z0-9_.]{2,60}$'),
    language    text,
    model       text,
    duration_s  real,
    text_enc    bytea,
    kept_enc    bytea,
    wer         real,
    created_at  timestamptz NOT NULL DEFAULT now(),
    corrected_at timestamptz
);
CREATE INDEX ix_dictation_field ON ai.dictation (field, created_at DESC);

ALTER TABLE ops.field_attachment ADD COLUMN transcript_enc bytea, ADD COLUMN transcribed_at timestamptz;
-- The transcript is written by the room's request for suggestions, on the incidents the room sees.
CREATE POLICY field_attachment_update ON ops.field_attachment FOR UPDATE USING (
    EXISTS (SELECT 1 FROM ops.incident i WHERE i.id = incident_id)) WITH CHECK (ehimaya.scope() <> 'none');

-- S2-5: a volunteer's signed SMS answers to a call-out (EH3): the key, and the last message applied (no replay).
ALTER TABLE identity.volunteer ADD COLUMN sms_key_enc bytea, ADD COLUMN sms_last_at timestamptz;
"""

DOWNGRADE = """
ALTER TABLE identity.volunteer DROP COLUMN IF EXISTS sms_key_enc, DROP COLUMN IF EXISTS sms_last_at;
DROP POLICY IF EXISTS field_attachment_update ON ops.field_attachment;
ALTER TABLE ops.field_attachment DROP COLUMN IF EXISTS transcript_enc, DROP COLUMN IF EXISTS transcribed_at;
DROP TABLE ai.dictation;
DROP TABLE org.prealert;
DELETE FROM reports.live_stream WHERE source = 'crew';
ALTER TABLE reports.live_stream
    DROP CONSTRAINT IF EXISTS ck_live_stream_crew,
    DROP COLUMN IF EXISTS assignment_id,
    DROP COLUMN IF EXISTS incident_id,
    DROP CONSTRAINT ck_live_stream_source,
    ADD CONSTRAINT ck_live_stream_source CHECK (source IN ('app', 'drone', 'camera', 'sim'));
ALTER TABLE reports.live_stream DROP CONSTRAINT ck_live_stream_org_camera, DROP COLUMN org_id;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
