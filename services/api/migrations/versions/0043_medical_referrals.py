"""Referrals and medical opinions (phase C1-c, docs/phase-c/design-medical-axis.md §13).

* ``medical.referral`` — a doctor of the gouvernorat group or of the medical committee sent the file to a specialist:
  their phone locked the file key for the specialist (a ``file_key`` with ``via = 'referral'``).
* ``medical.opinion`` — the specialist's advisory opinion, locked on their phone with a new key (AES-256-GCM).
* ``medical.opinion_key`` — that key locked for each reader: the group and committee doctors holding the file, the
  doctor who referred it, and the author.

Everything hangs off ``medical.locked_file`` and goes with it (retention, erasure). Row-level security as in 0042: a
doctor reads their own rows, staff read none; the API writes with the system scope after its own checks.

Revision ID: 0043_medical_referrals
Revises: 0042_locked_medical_files
Create Date: 2026-10-24
"""

# ruff: noqa: S608 (policies are built from the constant SQL fragments below)
from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0043_medical_referrals"
down_revision: str | None = "0042_locked_medical_files"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SYSTEM = "ehimaya.scope() = 'system'"


def _mine(column: str) -> str:
    return f"(ehimaya.scope() = 'public' AND CAST({column} AS text) = ehimaya.subject())"


UPGRADE = rf"""
CREATE TABLE medical.referral (
    report_id    uuid NOT NULL REFERENCES medical.locked_file(report_id) ON DELETE CASCADE,
    doctor_id    uuid NOT NULL REFERENCES identity.doctor(user_id) ON DELETE CASCADE,
    referred_by  uuid REFERENCES identity.doctor(user_id) ON DELETE SET NULL,
    reason       text NOT NULL CHECK (char_length(reason) BETWEEN 3 AND 500),
    at           timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (report_id, doctor_id)
);
CREATE INDEX ix_referral_by ON medical.referral (referred_by);

CREATE TABLE medical.opinion (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id   uuid NOT NULL REFERENCES medical.locked_file(report_id) ON DELETE CASCADE,
    author_id   uuid REFERENCES identity.doctor(user_id) ON DELETE SET NULL,
    specialty   text,
    nonce       bytea NOT NULL CHECK (octet_length(nonce) = 12),
    ciphertext  bytea NOT NULL CHECK (octet_length(ciphertext) BETWEEN 17 AND 32768),
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_opinion_report ON medical.opinion (report_id, created_at);

CREATE TABLE medical.opinion_key (
    opinion_id  uuid NOT NULL REFERENCES medical.opinion(id) ON DELETE CASCADE,
    doctor_id   uuid NOT NULL REFERENCES identity.doctor(user_id) ON DELETE CASCADE,
    eph_public  bytea NOT NULL CHECK (octet_length(eph_public) = 32),
    nonce       bytea NOT NULL CHECK (octet_length(nonce) = 12),
    wrapped     bytea NOT NULL CHECK (octet_length(wrapped) = 48),
    created_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (opinion_id, doctor_id)
);
CREATE INDEX ix_opinion_key_doctor ON medical.opinion_key (doctor_id);

ALTER TABLE medical.referral ENABLE ROW LEVEL SECURITY;
CREATE POLICY medical_referral_select ON medical.referral FOR SELECT
    USING ({_SYSTEM} OR {_mine("doctor_id")} OR {_mine("referred_by")});
CREATE POLICY medical_referral_write ON medical.referral FOR ALL USING ({_SYSTEM}) WITH CHECK ({_SYSTEM});

ALTER TABLE medical.opinion_key ENABLE ROW LEVEL SECURITY;
CREATE POLICY medical_opinion_key_select ON medical.opinion_key FOR SELECT USING ({_SYSTEM} OR {_mine("doctor_id")});
CREATE POLICY medical_opinion_key_write ON medical.opinion_key FOR ALL USING ({_SYSTEM}) WITH CHECK ({_SYSTEM});

ALTER TABLE medical.opinion ENABLE ROW LEVEL SECURITY;
CREATE POLICY medical_opinion_select ON medical.opinion FOR SELECT USING (
    {_SYSTEM} OR EXISTS (SELECT 1 FROM medical.opinion_key k WHERE k.opinion_id = opinion.id
                         AND {_mine("k.doctor_id")}));
CREATE POLICY medical_opinion_write ON medical.opinion FOR ALL USING ({_SYSTEM}) WITH CHECK ({_SYSTEM});
"""

DOWNGRADE = r"""
DROP POLICY medical_opinion_select ON medical.opinion;
DROP TABLE medical.opinion_key;
DROP TABLE medical.opinion;
DROP TABLE medical.referral;
"""


def upgrade() -> None:
    run_script(UPGRADE)


def downgrade() -> None:
    run_script(DOWNGRADE)
