"""Separate consent to share the volunteer's location (phase 10, docs/api/phase-10-contract.md §4.2).

* ``identity.consent.purpose``: ``charter`` (the privacy charter, as before) or ``volunteer_location``. For the
  location consent ``charter_version`` holds the version of the location notice the volunteer read.
* ``withdrawn_at``: a withdrawn location consent is kept (proof of what was consented, and when it ended) until the
  retention job removes it.
* At most one location consent in force per account.

Downgrade: location consents are deleted, then the columns are dropped.

Revision ID: 0029_identity_consent_purpose
Revises: 0028_notify_four_eyes
Create Date: 2026-10-21
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0029_identity_consent_purpose"
down_revision: str | None = "0028_notify_four_eyes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    run_script(
        """
        ALTER TABLE identity.consent
            ADD COLUMN purpose      text NOT NULL DEFAULT 'charter',
            ADD COLUMN withdrawn_at timestamptz,
            ADD CONSTRAINT ck_consent_purpose CHECK (purpose IN ('charter', 'volunteer_location')),
            ADD CONSTRAINT ck_consent_withdrawal CHECK (withdrawn_at IS NULL OR purpose = 'volunteer_location');
        CREATE UNIQUE INDEX ux_consent_location_in_force ON identity.consent (user_id)
            WHERE purpose = 'volunteer_location' AND withdrawn_at IS NULL;
        """
    )


def downgrade() -> None:
    run_script(
        """
        DELETE FROM identity.consent WHERE purpose <> 'charter';
        DROP INDEX identity.ux_consent_location_in_force;
        ALTER TABLE identity.consent DROP CONSTRAINT ck_consent_withdrawal, DROP CONSTRAINT ck_consent_purpose,
            DROP COLUMN withdrawn_at, DROP COLUMN purpose;
        """
    )
