"""The medical committee (phase C1-a, docs/phase-c/design-medical-axis.md §11).

The system administrator appoints, for a fixed term, one or more approved Civil Protection doctors to the national
medical committee. In phase C1-b the phone locks every medical file and every opinion for its members as well; here
only the appointment is stored on ``identity.doctor``:

* ``committee_since`` / ``committee_until`` — the current term (a member while ``committee_until`` is in the future);
* ``committee_by`` — who appointed or renewed (the audit log keeps every appointment and revocation).

Revision ID: 0041_medical_committee
Revises: 0040_doctors
Create Date: 2026-10-24
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0041_medical_committee"
down_revision: str | None = "0040_doctors"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = r"""
ALTER TABLE identity.doctor
    ADD COLUMN committee_since timestamptz,
    ADD COLUMN committee_until timestamptz,
    ADD COLUMN committee_by    text,
    ADD CONSTRAINT ck_doctor_committee CHECK (
        committee_until IS NULL
        OR (kind = 'civil_protection' AND status = 'approved' AND committee_since IS NOT NULL
            AND committee_until > committee_since)
    );
CREATE INDEX ix_doctor_committee ON identity.doctor (committee_until) WHERE committee_until IS NOT NULL;
"""

DOWNGRADE = r"""
DROP INDEX identity.ix_doctor_committee;
ALTER TABLE identity.doctor
    DROP CONSTRAINT ck_doctor_committee,
    DROP COLUMN committee_by,
    DROP COLUMN committee_until,
    DROP COLUMN committee_since;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
