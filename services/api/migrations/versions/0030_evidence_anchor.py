"""Evidence anchoring (phase 10, docs/api/phase-10-contract.md §4.3).

* Schema ``evidence``. ``evidence.anchor``: one sealed batch, chained to the previous one by ``prev_anchor_hash`` and
  signed with Ed25519. It covers the media whose SHA-256 is known (``evidence.leaf``, kept even after the media row
  is erased, so an earlier proof stays checkable) and the head of the audit chain at sealing time.
* ``evidence.leaf``: the Merkle leaves of an anchor, in order. A media row is anchored at most once.
* RLS: every staff scope reads, only the system scope (the worker) writes. A trigger refuses any change except
  filling in the time-stamp fields, and any deletion.

Downgrade: the schema is dropped with its anchors.

Revision ID: 0030_evidence_anchor
Revises: 0029_identity_consent_purpose
Create Date: 2026-10-21
"""

from collections.abc import Sequence

from migrations.sqlutil import run_script

revision: str = "0030_evidence_anchor"
down_revision: str | None = "0029_identity_consent_purpose"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_READ = "ehimaya.scope() IN ('system', 'national', 'gouvernorat')"
_WRITE = "ehimaya.scope() = 'system'"


def _policies(table: str) -> str:
    name = table.split(".")[1]
    return f"""
        ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
        CREATE POLICY {name}_select ON {table} FOR SELECT USING ({_READ});
        CREATE POLICY {name}_insert ON {table} FOR INSERT WITH CHECK ({_WRITE});
        CREATE POLICY {name}_update ON {table} FOR UPDATE USING ({_WRITE}) WITH CHECK ({_WRITE});
        CREATE POLICY {name}_delete ON {table} FOR DELETE USING ({_WRITE});
    """


def upgrade() -> None:
    run_script(
        """
        CREATE SCHEMA evidence;
        CREATE TABLE evidence.anchor (
            id               bigserial PRIMARY KEY,
            seq              bigint NOT NULL UNIQUE CHECK (seq > 0),
            from_at          timestamptz,
            to_at            timestamptz NOT NULL,
            media_count      integer NOT NULL CHECK (media_count >= 0),
            media_root       char(64),
            audit_seq        bigint,
            audit_hash       char(64),
            prev_anchor_hash char(64),
            anchor_hash      char(64) NOT NULL UNIQUE,
            signature        text,
            key_id           char(16),
            tsa_url          text,
            tsa_token        bytea,
            tsa_error        text,
            created_at       timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_anchor_root CHECK ((media_count = 0) = (media_root IS NULL)),
            CONSTRAINT ck_anchor_chain CHECK ((seq = 1) = (prev_anchor_hash IS NULL)),
            CONSTRAINT ck_anchor_signed CHECK ((signature IS NULL) = (key_id IS NULL))
        );
        CREATE INDEX ix_anchor_tsa_pending ON evidence.anchor (seq) WHERE tsa_url IS NOT NULL AND tsa_token IS NULL;
        CREATE TABLE evidence.leaf (
            anchor_id bigint NOT NULL REFERENCES evidence.anchor (id) ON DELETE CASCADE,
            idx       integer NOT NULL CHECK (idx >= 0),
            media_id  uuid NOT NULL UNIQUE,
            sha256    char(64) NOT NULL,
            PRIMARY KEY (anchor_id, idx)
        );
        -- Sealed is sealed: only the time-stamp fields of an anchor are filled in later, nothing is removed.
        CREATE FUNCTION evidence.refuse_change() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            -- Nested: plpgsql does not short-circuit, and evidence.leaf has none of these columns.
            IF TG_OP = 'UPDATE' AND TG_TABLE_NAME = 'anchor' THEN
                IF (NEW.id, NEW.seq, NEW.from_at, NEW.to_at, NEW.media_count, NEW.media_root, NEW.audit_seq,
                    NEW.audit_hash, NEW.prev_anchor_hash, NEW.anchor_hash, NEW.signature, NEW.key_id,
                    NEW.created_at)
                   IS NOT DISTINCT FROM
                   (OLD.id, OLD.seq, OLD.from_at, OLD.to_at, OLD.media_count, OLD.media_root, OLD.audit_seq,
                    OLD.audit_hash, OLD.prev_anchor_hash, OLD.anchor_hash, OLD.signature, OLD.key_id,
                    OLD.created_at) THEN
                    RETURN NEW;
                END IF;
            END IF;
            RAISE EXCEPTION 'evidence.% is append-only', TG_TABLE_NAME USING ERRCODE = 'insufficient_privilege';
        END $$;
        CREATE TRIGGER anchor_frozen BEFORE UPDATE OR DELETE ON evidence.anchor
            FOR EACH ROW EXECUTE FUNCTION evidence.refuse_change();
        CREATE TRIGGER leaf_frozen BEFORE UPDATE OR DELETE ON evidence.leaf
            FOR EACH ROW EXECUTE FUNCTION evidence.refuse_change();
        """
        + _policies("evidence.anchor")
        + _policies("evidence.leaf")
    )


def downgrade() -> None:
    run_script("DROP SCHEMA evidence CASCADE;")
