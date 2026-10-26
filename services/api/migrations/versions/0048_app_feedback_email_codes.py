"""App rating and a work e-mail confirmed by code (phase P5b, docs/phase-p5/design-simple.md §2.2 and §2.4).

* ``feedback.app_rating`` — a rating of the app (1 to 5 stars) with an optional encrypted remark, the platform, the
  build and the language. Not a "contact us" request: no number, no due date, no answer.
* ``identity.email_code`` — the work e-mail a signed-in account confirms with a 6-digit code (one row per account):
  the encrypted address, an HMAC of the code, its expiry and the attempts left, and once confirmed ``verified_at``.
  Lets an account signed in with a phone number register an institution (F-APP-12).

Row-level security on ``feedback.app_rating``: system and national scopes read every rating, the citizen (public
scope) reads their own. ``identity.email_code`` is read only by the API for the caller's own account, like
``identity.profile``. Downgrade drops both.

Revision ID: 0048_app_feedback_email_codes
Revises: 0047_prevention_visits
Create Date: 2026-10-26
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0048_app_feedback_email_codes"
down_revision: str | None = "0047_prevention_visits"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = r"""
CREATE SCHEMA IF NOT EXISTS feedback;

CREATE TABLE feedback.app_rating (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     uuid REFERENCES identity.account(user_id) ON DELETE CASCADE,
    stars       smallint NOT NULL CHECK (stars BETWEEN 1 AND 5),
    remark_enc  bytea,
    platform    text CHECK (platform IN ('android', 'ios')),
    build       integer CHECK (build BETWEEN 1 AND 1000000),
    version     text CHECK (char_length(version) <= 20),
    locale      text NOT NULL DEFAULT 'ar' CHECK (locale IN ('ar', 'fr', 'en')),
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_app_rating_created ON feedback.app_rating (created_at DESC);
CREATE INDEX ix_app_rating_user ON feedback.app_rating (user_id, created_at DESC);

ALTER TABLE feedback.app_rating ENABLE ROW LEVEL SECURITY;
CREATE POLICY app_rating_select ON feedback.app_rating FOR SELECT USING (
    ehimaya.sees_all() OR (ehimaya.scope() = 'public' AND CAST(user_id AS text) = ehimaya.subject()));
CREATE POLICY app_rating_insert ON feedback.app_rating FOR INSERT WITH CHECK (ehimaya.scope() <> 'none');
CREATE POLICY app_rating_delete ON feedback.app_rating FOR DELETE USING (
    ehimaya.scope() = 'system' OR (ehimaya.scope() = 'public' AND CAST(user_id AS text) = ehimaya.subject()));

CREATE TABLE identity.email_code (
    user_id       uuid PRIMARY KEY REFERENCES identity.account(user_id) ON DELETE CASCADE,
    email_enc     bytea NOT NULL,
    code_hmac     bytea,
    expires_at    timestamptz,
    attempts_left smallint NOT NULL DEFAULT 5 CHECK (attempts_left BETWEEN 0 AND 5),
    verified_at   timestamptz,
    updated_at    timestamptz NOT NULL DEFAULT now()
);
"""

DOWNGRADE = r"""
DROP TABLE identity.email_code;
DROP TABLE feedback.app_rating;
DROP SCHEMA feedback;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
