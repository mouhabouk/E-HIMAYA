"""The call-taking card on the team's mission (OS2 follow-up, Yamen 2026-11-10).

The team leader reads the card the room answered during the call and completes it from the scene: questions left
unanswered or answered «doesn't know», and answers the scene contradicts. The team's answers are kept next to the
caller's (never over them), with what they give; the result never goes below the call's band (Yamen: the field
raises the band, it does not lower it).

Revision ID: 0101_call_card_field
Revises: 0100_call_cards
Create Date: 2026-11-10
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0101_call_card_field"
down_revision: str | None = "0100_call_cards"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = """'ack', 'status', 'first_report', 'casualties', 'transport', 'alert', 'attachment', 'detailed_report',
    'milestone', 'record', 'skip', 'no_intervention', 'nature', 'toll', 'report', 'open'"""

UPGRADE = f"""
ALTER TABLE reports.call_card_answer
    ADD COLUMN field_answers jsonb,
    ADD COLUMN field_outcome jsonb,
    ADD COLUMN field_by      text,
    ADD COLUMN field_by_name text CHECK (char_length(field_by_name) <= 200),
    ADD COLUMN field_at      timestamptz,
    ADD CONSTRAINT ck_call_card_answer_field CHECK (
        (field_answers IS NULL) = (field_outcome IS NULL) AND (field_answers IS NULL) = (field_at IS NULL)
    );
ALTER TABLE ops.crew_event DROP CONSTRAINT crew_event_kind_check;
ALTER TABLE ops.crew_event ADD CONSTRAINT crew_event_kind_check CHECK (kind IN ({KINDS}, 'call_card'));
"""

DOWNGRADE = f"""
DELETE FROM ops.crew_event WHERE kind = 'call_card';
ALTER TABLE ops.crew_event DROP CONSTRAINT crew_event_kind_check;
ALTER TABLE ops.crew_event ADD CONSTRAINT crew_event_kind_check CHECK (kind IN ({KINDS}));
ALTER TABLE reports.call_card_answer
    DROP CONSTRAINT ck_call_card_answer_field,
    DROP COLUMN field_at,
    DROP COLUMN field_by_name,
    DROP COLUMN field_by,
    DROP COLUMN field_outcome,
    DROP COLUMN field_answers;
"""  # noqa: S608 (constant SQL, nothing is interpolated from input)


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
