"""Institution alerts with acknowledgement, awareness by kind, drills and events, maintenance log (phase P2b,
docs/phase-p2/design-institutions-app.md §5).

* ``notify.message``: ``org_kinds`` narrows an "organizations" message to some kinds (empty: every kind) and
  ``ack_required`` asks each institution to confirm it has read it. ``notify.org_ack`` keeps who confirmed and when.
* ``content.safety_tip.org_kinds``: a tip tagged with kinds is awareness for those institutions, not a citizen tip.
* ``org.activity``: drills held and public events declared by an institution.
* ``org.maintenance``: one row per maintenance of an equipment, with an optional photo kept as an institution
  document of the new kind ``maintenance_photo``.

Revision ID: 0045_org_alerts_activities
Revises: 0044_institution_kinds
Create Date: 2026-10-25
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0045_org_alerts_activities"
down_revision: str | None = "0044_institution_kinds"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = (
    "'health', 'industrial', 'energy', 'tourism', 'education', 'social_care', 'public_admin', "
    "'culture_sport', 'commercial', 'transport', 'religious', 'other'"
)

UPGRADE = f"""
ALTER TABLE notify.message ADD COLUMN org_kinds text[] NOT NULL DEFAULT '{{}}'
    CHECK (org_kinds <@ ARRAY[{KINDS}]::text[]);
ALTER TABLE notify.message ADD COLUMN ack_required boolean NOT NULL DEFAULT false;
ALTER TABLE notify.message ADD CONSTRAINT message_org_target_check
    CHECK ((cardinality(org_kinds) = 0 AND NOT ack_required) OR audience = 'organizations');

CREATE TABLE notify.org_ack (
    message_id     uuid NOT NULL REFERENCES notify.message(id) ON DELETE CASCADE,
    org_id         uuid NOT NULL REFERENCES org.organization(id) ON DELETE CASCADE,
    acked_by       uuid REFERENCES identity.account(user_id) ON DELETE SET NULL,
    acked_by_name  text,
    acked_at       timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (message_id, org_id)
);
CREATE INDEX ix_org_ack_org ON notify.org_ack (org_id);

ALTER TABLE content.safety_tip ADD COLUMN org_kinds text[] NOT NULL DEFAULT '{{}}'
    CHECK (org_kinds <@ ARRAY[{KINDS}]::text[]);

CREATE TABLE org.activity (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id            uuid NOT NULL REFERENCES org.organization(id) ON DELETE CASCADE,
    kind              text NOT NULL CHECK (kind IN ('drill', 'event')),
    title             text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 120),
    starts_on         date NOT NULL,
    ends_on           date,
    participants      integer CHECK (participants BETWEEN 0 AND 1000000),
    notes             text CHECK (char_length(notes) <= 1000),
    created_by        uuid REFERENCES identity.account(user_id) ON DELETE SET NULL,
    created_by_name   text,
    created_at        timestamptz NOT NULL DEFAULT now(),
    CHECK (ends_on IS NULL OR (kind = 'event' AND ends_on >= starts_on))
);
CREATE INDEX ix_activity_org ON org.activity (org_id, starts_on DESC);
CREATE INDEX ix_activity_event ON org.activity (starts_on) WHERE kind = 'event';

ALTER TABLE org.document DROP CONSTRAINT document_kind_check;
ALTER TABLE org.document ADD CONSTRAINT document_kind_check
    CHECK (kind IN ('safety_file', 'safety_plan', 'sds', 'other', 'maintenance_photo'));

CREATE TABLE org.maintenance (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id             uuid NOT NULL REFERENCES org.organization(id) ON DELETE CASCADE,
    equipment_id       uuid NOT NULL REFERENCES org.equipment(id) ON DELETE CASCADE,
    done_on            date NOT NULL,
    note               text CHECK (char_length(note) <= 500),
    document_id        uuid REFERENCES org.document(id) ON DELETE SET NULL,
    recorded_by        uuid REFERENCES identity.account(user_id) ON DELETE SET NULL,
    recorded_by_name   text,
    recorded_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_maintenance_equipment ON org.maintenance (equipment_id, done_on DESC);
"""

DOWNGRADE = """
DROP TABLE org.maintenance;
DELETE FROM org.document WHERE kind = 'maintenance_photo';
ALTER TABLE org.document DROP CONSTRAINT document_kind_check;
ALTER TABLE org.document ADD CONSTRAINT document_kind_check
    CHECK (kind IN ('safety_file', 'safety_plan', 'sds', 'other'));
DROP TABLE org.activity;
ALTER TABLE content.safety_tip DROP COLUMN org_kinds;
DROP TABLE notify.org_ack;
ALTER TABLE notify.message DROP CONSTRAINT message_org_target_check;
ALTER TABLE notify.message DROP COLUMN ack_required;
ALTER TABLE notify.message DROP COLUMN org_kinds;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
