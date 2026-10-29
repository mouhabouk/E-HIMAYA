"""The commander's voice messages (AI5b, docs/phase-ai5/design-ai5.md §7).

``decision.command_voice``: one voice message a commander recorded on an incident. The audio is transcribed locally
(faster-whisper, with the vocabulary of the orders) and then deleted; only the transcript is kept, encrypted. The
commander corrects it before sending, and the corrected text is kept next to it (``corrected_enc``) with the number
of words and of word errors between the two: the measure of the transcription on the commander's own words (word
error rate), and the corrections the assistant learns from (a sample of the self-learning centre, migration 0076).

Rows follow the incident's visibility (row-level security, like the commander's decisions).

Revision ID: 0078_command_voice
Revises: 0077_command_decisions
Create Date: 2026-10-29
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0078_command_voice"
down_revision: str | None = "0077_command_decisions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INCIDENT = "EXISTS (SELECT 1 FROM ops.incident i WHERE i.id = incident_id)"

UPGRADE = f"""
CREATE TABLE decision.command_voice (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id      uuid NOT NULL REFERENCES ops.incident(id) ON DELETE CASCADE,
    lang             text CHECK (lang IN ('ar', 'fr', 'en')),
    model            text NOT NULL,
    duration_s       real NOT NULL CHECK (duration_s >= 0),
    transcript_enc   bytea NOT NULL,
    corrected_enc    bytea,
    words            integer CHECK (words >= 0),
    word_errors      integer CHECK (word_errors >= 0),
    created_by       text NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    sent_at          timestamptz,
    CONSTRAINT ck_command_voice_sent CHECK ((sent_at IS NULL) = (corrected_enc IS NULL)),
    CONSTRAINT ck_command_voice_measured CHECK ((sent_at IS NULL) = (words IS NULL AND word_errors IS NULL))
);
CREATE INDEX ix_command_voice_sent ON decision.command_voice (sent_at DESC) WHERE sent_at IS NOT NULL;

ALTER TABLE decision.command_voice ENABLE ROW LEVEL SECURITY;
CREATE POLICY command_voice_all ON decision.command_voice USING ({_INCIDENT}) WITH CHECK ({_INCIDENT});
"""

DOWNGRADE = """
DROP TABLE decision.command_voice;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
