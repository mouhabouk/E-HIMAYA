"""Locked medical files (phase C1-b, docs/phase-c/design-medical-axis.md §12).

* ``identity.doctor`` gains the doctor's X25519 public key and the backup of their private key, locked by their own
  code on the phone (Argon2id + AES-256-GCM): the server can never open it.
* ``medical.locked_file`` — the part of a reporter's medical file that is not on the emergency card, locked on the
  phone (AES-256-GCM). Hangs off ``reports.medical_attachment``: it goes with it (retention, erasure).
* ``medical.file_key`` — the file key locked for one doctor (ephemeral X25519 + HKDF + AES-256-GCM), with the reason
  the doctor received it (``gouvernorat``, ``committee``; ``referral`` comes in C1-c).
* ``medical.file_opening`` — each time a doctor opened a file (the reason is required from a committee member).

Row-level security: a doctor (public scope) sees only their own keys and openings, and the files they hold a key for;
staff never read the ``medical`` schema. The API writes with the system scope after its own checks.

Revision ID: 0042_locked_medical_files
Revises: 0041_medical_committee
Create Date: 2026-10-24
"""

# ruff: noqa: S608 (policies are built from the constant SQL fragments below)
from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0042_locked_medical_files"
down_revision: str | None = "0041_medical_committee"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SYSTEM = "ehimaya.scope() = 'system'"


def _mine(column: str) -> str:
    return f"(ehimaya.scope() = 'public' AND CAST({column} AS text) = ehimaya.subject())"


UPGRADE = rf"""
ALTER TABLE identity.doctor
    ADD COLUMN public_key  bytea CHECK (octet_length(public_key) = 32),
    ADD COLUMN key_backup  jsonb,
    ADD COLUMN key_set_at  timestamptz,
    ADD CONSTRAINT ck_doctor_key CHECK ((public_key IS NULL) = (key_backup IS NULL));

CREATE SCHEMA IF NOT EXISTS medical;

CREATE TABLE medical.locked_file (
    report_id   uuid PRIMARY KEY REFERENCES reports.medical_attachment(report_id) ON DELETE CASCADE,
    nonce       bytea NOT NULL CHECK (octet_length(nonce) = 12),
    ciphertext  bytea NOT NULL CHECK (octet_length(ciphertext) BETWEEN 17 AND 65536),
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE medical.file_key (
    report_id   uuid NOT NULL REFERENCES medical.locked_file(report_id) ON DELETE CASCADE,
    doctor_id   uuid NOT NULL REFERENCES identity.doctor(user_id) ON DELETE CASCADE,
    via         text NOT NULL CHECK (via IN ('gouvernorat', 'committee', 'referral')),
    eph_public  bytea NOT NULL CHECK (octet_length(eph_public) = 32),
    nonce       bytea NOT NULL CHECK (octet_length(nonce) = 12),
    wrapped     bytea NOT NULL CHECK (octet_length(wrapped) = 48),
    created_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (report_id, doctor_id)
);
CREATE INDEX ix_file_key_doctor ON medical.file_key (doctor_id, created_at DESC);

CREATE TABLE medical.file_opening (
    id           bigserial PRIMARY KEY,
    report_id    uuid NOT NULL REFERENCES medical.locked_file(report_id) ON DELETE CASCADE,
    doctor_id    uuid NOT NULL REFERENCES identity.doctor(user_id) ON DELETE CASCADE,
    as_committee boolean NOT NULL,
    reason       text,
    at           timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_file_opening_reason CHECK (NOT as_committee OR reason IS NOT NULL)
);
CREATE INDEX ix_file_opening_report ON medical.file_opening (report_id, at);

ALTER TABLE medical.file_key ENABLE ROW LEVEL SECURITY;
CREATE POLICY medical_file_key_select ON medical.file_key FOR SELECT USING ({_SYSTEM} OR {_mine("doctor_id")});
CREATE POLICY medical_file_key_write ON medical.file_key FOR ALL USING ({_SYSTEM}) WITH CHECK ({_SYSTEM});

ALTER TABLE medical.locked_file ENABLE ROW LEVEL SECURITY;
CREATE POLICY medical_locked_file_select ON medical.locked_file FOR SELECT USING (
    {_SYSTEM} OR EXISTS (SELECT 1 FROM medical.file_key k WHERE k.report_id = locked_file.report_id
                         AND {_mine("k.doctor_id")}));
CREATE POLICY medical_locked_file_write ON medical.locked_file FOR ALL USING ({_SYSTEM}) WITH CHECK ({_SYSTEM});

ALTER TABLE medical.file_opening ENABLE ROW LEVEL SECURITY;
CREATE POLICY medical_file_opening_select ON medical.file_opening FOR SELECT
    USING ({_SYSTEM} OR {_mine("doctor_id")});
CREATE POLICY medical_file_opening_write ON medical.file_opening FOR ALL USING ({_SYSTEM}) WITH CHECK ({_SYSTEM});
"""

DOWNGRADE = r"""
DROP SCHEMA medical CASCADE;
ALTER TABLE identity.doctor
    DROP CONSTRAINT ck_doctor_key,
    DROP COLUMN key_set_at,
    DROP COLUMN key_backup,
    DROP COLUMN public_key;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
