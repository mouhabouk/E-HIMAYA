"""Certificate revocation and signing key identifier (phase 10, docs/api/phase-10-contract.md §4.1).

* ``org.certificate.status`` accepts ``revoked`` (reached from ``approved`` only, by an institutions auditor), with
  ``revoked_at``, ``revoked_by`` and ``revoke_reason``.
* ``key_id``: the first 16 hex characters of the SHA-256 of the raw Ed25519 public key that signed the certificate,
  so the key can be rotated without invalidating what it signed. Certificates approved before this migration have
  none and are checked against every known key.

Downgrade: revoked certificates go back to ``approved`` only if the revocation columns are dropped, which would make
them valid again; the downgrade therefore refuses to run while a certificate is revoked.

Revision ID: 0027_orgs_certificate_revocation
Revises: 0026_access_sign_out
Create Date: 2026-10-21
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0027_orgs_certificate_revocation"
down_revision: str | None = "0026_access_sign_out"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    run_script(
        """
        ALTER TABLE org.certificate DROP CONSTRAINT certificate_status_check;
        ALTER TABLE org.certificate ADD CONSTRAINT certificate_status_check
            CHECK (status IN ('draft', 'submitted', 'approved', 'rejected', 'revoked'));
        ALTER TABLE org.certificate
            ADD COLUMN key_id        char(16),
            ADD COLUMN revoked_at    timestamptz,
            ADD COLUMN revoked_by    text,
            ADD COLUMN revoke_reason text,
            ADD CONSTRAINT ck_certificate_revocation CHECK (
                (status = 'revoked') = (revoked_at IS NOT NULL AND revoke_reason IS NOT NULL)
            );
        """
    )


def downgrade() -> None:
    run_script(
        """
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM org.certificate WHERE status = 'revoked') THEN
                RAISE EXCEPTION 'revoked certificates exist: downgrading would make them valid again';
            END IF;
        END $$;
        ALTER TABLE org.certificate DROP CONSTRAINT ck_certificate_revocation;
        ALTER TABLE org.certificate DROP COLUMN key_id, DROP COLUMN revoked_at, DROP COLUMN revoked_by,
            DROP COLUMN revoke_reason;
        ALTER TABLE org.certificate DROP CONSTRAINT certificate_status_check;
        ALTER TABLE org.certificate ADD CONSTRAINT certificate_status_check
            CHECK (status IN ('draft', 'submitted', 'approved', 'rejected'));
        """
    )
