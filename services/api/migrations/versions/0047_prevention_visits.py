"""Prevention certificate: visits, on-site inspection, decision with reservations (phase P3b,
docs/phase-p3/design-prevention.md §7).

* ``org.prevention_visit``: a visit requested by the institution or scheduled by the Office, its inspection (the
  declared snapshot, the checklist results and the comparison report), the decision and the visit report PDF. At most
  one open visit per institution.
* ``org.prevention_reservation``: a reservation of a decision, with its deadline, the institution's answer and its
  lifting by the auditor.
* ``org.certificate``: ``kind`` (``safety`` or ``prevention``) and ``visit_id``; ``created_by`` may be empty, since
  the Office issues the prevention certificate.

Revision ID: 0047_prevention_visits
Revises: 0046_certificate_counter
Create Date: 2026-10-25
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0047_prevention_visits"
down_revision: str | None = "0046_certificate_counter"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = """
CREATE TABLE org.prevention_visit (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id              uuid NOT NULL REFERENCES org.organization(id) ON DELETE CASCADE,
    origin              text NOT NULL CHECK (origin IN ('request', 'scheduled')),
    status              text NOT NULL CHECK (status IN ('requested', 'scheduled', 'inspected', 'decided', 'cancelled')),
    request_note        text CHECK (char_length(request_note) <= 500),
    requested_by        uuid REFERENCES identity.account(user_id) ON DELETE SET NULL,
    requested_by_name   text,
    requested_at        timestamptz,
    scheduled_on        date,
    inspector_name      text CHECK (char_length(inspector_name) <= 120),
    scheduled_by        text,
    scheduled_at        timestamptz,
    inspected_on        date,
    attendees           text CHECK (char_length(attendees) <= 500),
    inspected_by        text,
    inspected_by_name   text,
    declared            jsonb,
    comparison          jsonb,
    decision            text CHECK (decision IN ('approved', 'approved_with_reservations', 'refused')),
    decision_reason     text CHECK (char_length(decision_reason) <= 1000),
    decided_by          text,
    decided_by_name     text,
    decided_at          timestamptz,
    report_object_key   text,
    report_sha256       text CHECK (report_sha256 ~ '^[0-9a-f]{64}$'),
    cancel_reason       text CHECK (char_length(cancel_reason) <= 500),
    cancelled_by        text,
    cancelled_at        timestamptz,
    created_at          timestamptz NOT NULL DEFAULT now(),
    CHECK (status NOT IN ('scheduled', 'inspected', 'decided') OR scheduled_on IS NOT NULL),
    CHECK (status NOT IN ('inspected', 'decided') OR (inspected_on IS NOT NULL AND comparison IS NOT NULL)),
    CHECK ((status = 'decided') = (decision IS NOT NULL)),
    CHECK (decision IS DISTINCT FROM 'refused' OR decision_reason IS NOT NULL)
);
CREATE UNIQUE INDEX ux_prevention_visit_open ON org.prevention_visit (org_id)
    WHERE status IN ('requested', 'scheduled', 'inspected');
CREATE INDEX ix_prevention_visit_org ON org.prevention_visit (org_id, created_at DESC);
CREATE INDEX ix_prevention_visit_queue ON org.prevention_visit (status, created_at, id);

CREATE TABLE org.prevention_reservation (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    visit_id            uuid NOT NULL REFERENCES org.prevention_visit(id) ON DELETE CASCADE,
    org_id              uuid NOT NULL REFERENCES org.organization(id) ON DELETE CASCADE,
    item_key            text CHECK (char_length(item_key) <= 60),
    text                text NOT NULL CHECK (char_length(text) BETWEEN 1 AND 500),
    due_on              date NOT NULL,
    response_note       text CHECK (char_length(response_note) <= 1000),
    responded_by_name   text,
    responded_at        timestamptz,
    lifted_by           text,
    lifted_by_name      text,
    lift_note           text CHECK (char_length(lift_note) <= 500),
    lifted_at           timestamptz,
    created_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_prevention_reservation_visit ON org.prevention_reservation (visit_id, due_on);
CREATE INDEX ix_prevention_reservation_open ON org.prevention_reservation (org_id, due_on) WHERE lifted_at IS NULL;

ALTER TABLE org.certificate ADD COLUMN kind text NOT NULL DEFAULT 'safety' CHECK (kind IN ('safety', 'prevention'));
ALTER TABLE org.certificate ADD COLUMN visit_id uuid REFERENCES org.prevention_visit(id) ON DELETE SET NULL;
ALTER TABLE org.certificate ALTER COLUMN created_by DROP NOT NULL;
ALTER TABLE org.certificate ADD CONSTRAINT ck_certificate_kind
    CHECK (kind = 'safety' AND created_by IS NOT NULL OR kind = 'prevention' AND status IN ('approved', 'revoked'));
"""

DOWNGRADE = """
DELETE FROM org.certificate WHERE kind = 'prevention';
ALTER TABLE org.certificate DROP CONSTRAINT ck_certificate_kind;
ALTER TABLE org.certificate ALTER COLUMN created_by SET NOT NULL;
ALTER TABLE org.certificate DROP COLUMN visit_id;
ALTER TABLE org.certificate DROP COLUMN kind;
DROP TABLE org.prevention_reservation;
DROP TABLE org.prevention_visit;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
