"""Location history for 72 hours (phase B2, docs/phase-b/design-b2.md §6, addition 7b §2).

* ``safety.location_history`` — whether the person turned it on, until when (at most 72 h ahead).
* ``safety.location_point`` — the positions the phone sent (encrypted), deleted 72 h after they were taken, or at
  once when the person turns it off.
* ``identity.consent`` accepts the purpose ``location_history`` (its own consent, withdrawn when turned off).
* Setting ``safety.location_history`` = false: the feature stays off (the API answers ``403 feature_off`` and the app
  hides it) until a system administrator turns it on after the Office's legal review and the declaration to the
  national personal data authority (INPDP).

Row-level security: the owner and the system scope only. Staff read a person's points through the API alone, after a
missing-person report and a reason, with the system scope, audited and notified to the person.

Revision ID: 0039_location_history
Revises: 0038_report_medical_attachment
Create Date: 2026-10-23
"""

# ruff: noqa: S608 (policies are built from the constant SQL fragments below)

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0039_location_history"
down_revision: str | None = "0038_report_medical_attachment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OWNER = "(ehimaya.scope() = 'system' OR (ehimaya.scope() = 'public' AND CAST(owner_id AS text) = ehimaya.subject()))"

UPGRADE = rf"""
CREATE TABLE safety.location_history (
    owner_id    uuid PRIMARY KEY REFERENCES identity.account(user_id) ON DELETE CASCADE,
    started_at  timestamptz NOT NULL DEFAULT now(),
    until       timestamptz NOT NULL
);

CREATE TABLE safety.location_point (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    owner_id     uuid NOT NULL REFERENCES identity.account(user_id) ON DELETE CASCADE,
    at           timestamptz NOT NULL,
    position_enc bytea NOT NULL
);
CREATE INDEX ix_safety_location_point_owner ON safety.location_point (owner_id, at);
CREATE INDEX ix_safety_location_point_at ON safety.location_point (at);

ALTER TABLE safety.location_history ENABLE ROW LEVEL SECURITY;
CREATE POLICY safety_history_all ON safety.location_history USING {_OWNER} WITH CHECK {_OWNER};
ALTER TABLE safety.location_point ENABLE ROW LEVEL SECURITY;
CREATE POLICY safety_point_all ON safety.location_point USING {_OWNER} WITH CHECK {_OWNER};

ALTER TABLE identity.consent DROP CONSTRAINT ck_consent_purpose;
ALTER TABLE identity.consent DROP CONSTRAINT ck_consent_withdrawal;
ALTER TABLE identity.consent
    ADD CONSTRAINT ck_consent_purpose CHECK (purpose IN ('charter', 'volunteer_location', 'location_history')),
    ADD CONSTRAINT ck_consent_withdrawal CHECK (withdrawn_at IS NULL OR purpose <> 'charter');

INSERT INTO platform.setting (key, value) VALUES ('safety.location_history', 'false') ON CONFLICT (key) DO NOTHING;
"""

DOWNGRADE = r"""
DELETE FROM platform.setting WHERE key = 'safety.location_history';
DELETE FROM identity.consent WHERE purpose = 'location_history';
ALTER TABLE identity.consent DROP CONSTRAINT ck_consent_purpose;
ALTER TABLE identity.consent DROP CONSTRAINT ck_consent_withdrawal;
ALTER TABLE identity.consent
    ADD CONSTRAINT ck_consent_purpose CHECK (purpose IN ('charter', 'volunteer_location')),
    ADD CONSTRAINT ck_consent_withdrawal CHECK (withdrawn_at IS NULL OR purpose = 'volunteer_location');
DROP TABLE safety.location_point;
DROP TABLE safety.location_history;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
