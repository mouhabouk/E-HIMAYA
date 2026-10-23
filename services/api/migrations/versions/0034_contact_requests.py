"""Contact us: requests with a number and a status (phase B1, docs/phase-b/design.md §2ter).

* ``contact.request`` — a request from the app: kind (access to information under law 2016-22, non-urgent hazard,
  question, suggestion, app problem, partnership), number ``CT-YYYY-NNNNNN``, status, gouvernorat (optional), subject,
  encrypted name / phone / e-mail / message / answer, due date (access to information only), version.
* ``contact.request_event`` — history: creation, status changes, answer, move, internal notes (encrypted).

Row-level security: system and national scopes read every request; a gouvernorat reads its own; the citizen (public
scope) reads their own, and only the events marked visible. Only staff scopes update. Setting
``contact.access_info_days`` (20). Downgrade drops the schema and the setting.

Revision ID: 0034_contact_requests
Revises: 0033_emergency_guide
Create Date: 2026-10-23
"""

# ruff: noqa: S608 (policies are built from the constant SQL fragments below)

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0034_contact_requests"
down_revision: str | None = "0033_emergency_guide"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STAFF = "ehimaya.scope() IN ('system', 'national', 'gouvernorat')"
_SEES = (
    "(ehimaya.sees_all() OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat()) "
    "OR (ehimaya.scope() = 'public' AND CAST(user_id AS text) = ehimaya.subject()))"
)
_STAFF_SEES = "(ehimaya.sees_all() OR (ehimaya.regional() AND gouvernorat_code = ehimaya.gouvernorat()))"

UPGRADE = rf"""
CREATE SCHEMA IF NOT EXISTS contact;

CREATE SEQUENCE contact.request_seq;

CREATE TABLE contact.request (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    number           text NOT NULL UNIQUE DEFAULT (
        'CT-' || to_char(now() AT TIME ZONE 'Africa/Tunis', 'YYYY') || '-'
        || lpad(CAST(nextval('contact.request_seq') AS text), 6, '0')),
    kind             text NOT NULL,
    status           text NOT NULL DEFAULT 'received',
    user_id          uuid REFERENCES identity.account(user_id) ON DELETE SET NULL,
    gouvernorat_code smallint REFERENCES geo.gouvernorat(code),
    subject          text NOT NULL,
    name_enc         bytea,
    phone_enc        bytea,
    email_enc        bytea,
    message_enc      bytea NOT NULL,
    answer_enc       bytea,
    locale           text NOT NULL DEFAULT 'ar',
    platform         text,
    due_at           timestamptz,
    answered_at      timestamptz,
    closed_at        timestamptz,
    assigned_to      text,
    assigned_name    text,
    version          integer NOT NULL DEFAULT 1,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_contact_kind CHECK (kind IN ('access_info', 'hazard', 'question', 'suggestion', 'app_problem',
                                               'partnership')),
    CONSTRAINT ck_contact_status CHECK (status IN ('received', 'in_progress', 'answered', 'closed', 'rejected')),
    CONSTRAINT ck_contact_subject CHECK (length(subject) BETWEEN 1 AND 120),
    CONSTRAINT ck_contact_locale CHECK (locale IN ('ar', 'fr', 'en'))
);
CREATE INDEX ix_contact_request_inbox ON contact.request (status, gouvernorat_code, created_at DESC);
CREATE INDEX ix_contact_request_user ON contact.request (user_id, created_at DESC);

CREATE TABLE contact.request_event (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id       uuid NOT NULL REFERENCES contact.request(id) ON DELETE CASCADE,
    action           text NOT NULL,
    status           text,
    gouvernorat_code smallint,
    note_enc         bytea,
    visible          boolean NOT NULL DEFAULT false,
    actor            text NOT NULL,
    actor_name       text,
    at               timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_contact_event_action CHECK (action IN ('created', 'status', 'answer', 'note', 'move'))
);
CREATE INDEX ix_contact_event_request ON contact.request_event (request_id, at);

ALTER TABLE contact.request ENABLE ROW LEVEL SECURITY;
CREATE POLICY contact_request_select ON contact.request FOR SELECT USING {_SEES};
CREATE POLICY contact_request_insert ON contact.request FOR INSERT WITH CHECK (ehimaya.scope() <> 'none');
CREATE POLICY contact_request_update ON contact.request FOR UPDATE USING {_STAFF_SEES} WITH CHECK ({_STAFF});
CREATE POLICY contact_request_delete ON contact.request FOR DELETE USING (ehimaya.scope() = 'system');

-- The request's own policy applies inside the EXISTS; the citizen sees only what is meant for them.
ALTER TABLE contact.request_event ENABLE ROW LEVEL SECURITY;
CREATE POLICY contact_event_select ON contact.request_event FOR SELECT USING (
    EXISTS (SELECT 1 FROM contact.request r WHERE r.id = request_id) AND (visible OR {_STAFF}));
CREATE POLICY contact_event_insert ON contact.request_event FOR INSERT WITH CHECK (ehimaya.scope() <> 'none');
CREATE POLICY contact_event_delete ON contact.request_event FOR DELETE USING (ehimaya.scope() = 'system');

INSERT INTO platform.setting (key, value) VALUES ('contact.access_info_days', '20') ON CONFLICT (key) DO NOTHING;
"""

DOWNGRADE = r"""
DELETE FROM platform.setting WHERE key = 'contact.access_info_days';
DROP TABLE contact.request_event;
DROP TABLE contact.request;
DROP SEQUENCE contact.request_seq;
DROP SCHEMA contact;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
