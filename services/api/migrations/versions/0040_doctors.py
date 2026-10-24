"""Doctors (phase C1-a, docs/phase-c/design-medical-axis.md §2): a registered citizen declares themselves a doctor.

* ``identity.doctor`` — kind ``volunteer`` (a specialist who accepts medical files to give an opinion) or
  ``civil_protection`` (a doctor of the Civil Protection, who will receive the files of their gouvernorat), the
  specialties, the registration number with the medical council (encrypted), the workplace and its gouvernorat (the
  group the doctor belongs to), and the availability. Reviewed like volunteers before any medical file reaches them.
* ``identity.doctor_review`` — every decision, with its reason.

No medical file is read here: the locked files and the doctors' keys come in phase C1-b.

Revision ID: 0040_doctors
Revises: 0039_location_history
Create Date: 2026-10-24
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0040_doctors"
down_revision: str | None = "0039_location_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = r"""
CREATE TABLE identity.doctor (
    user_id                    uuid PRIMARY KEY REFERENCES identity.account(user_id) ON DELETE CASCADE,
    kind                       text NOT NULL CHECK (kind IN ('volunteer', 'civil_protection')),
    status                     text NOT NULL DEFAULT 'pending'
                               CHECK (status IN ('pending', 'approved', 'rejected', 'suspended', 'withdrawn')),
    specialties                text[] NOT NULL CHECK (cardinality(specialties) BETWEEN 1 AND 4),
    licence_no_enc             bytea,
    workplace                  text NOT NULL CHECK (char_length(workplace) BETWEEN 2 AND 150),
    gouvernorat_code           smallint NOT NULL REFERENCES geo.gouvernorat(code),
    -- Civil Protection doctors only: their unit and staff number (encrypted).
    cp_unit                    text CHECK (char_length(cp_unit) <= 150),
    cp_staff_no_enc            bytea,
    terms_version              text NOT NULL,
    submitted_at               timestamptz NOT NULL DEFAULT now(),
    reviewed_at                timestamptz,
    reviewed_by                text,
    review_reason              text,
    available_until            timestamptz,
    version                    integer NOT NULL DEFAULT 1,
    updated_at                 timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_doctor_cp CHECK (kind <> 'civil_protection' OR status = 'withdrawn' OR cp_unit IS NOT NULL)
);
CREATE INDEX ix_doctor_status ON identity.doctor (status, gouvernorat_code);
CREATE INDEX ix_doctor_specialties ON identity.doctor USING gin (specialties);

CREATE TABLE identity.doctor_review (
    id                bigserial PRIMARY KEY,
    user_id           uuid NOT NULL REFERENCES identity.doctor(user_id) ON DELETE CASCADE,
    decision          text NOT NULL,
    reason            text,
    actor             text NOT NULL,
    at                timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_doctor_review_user ON identity.doctor_review (user_id, at DESC);
"""

DOWNGRADE = r"""
DROP TABLE identity.doctor_review;
DROP TABLE identity.doctor;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
