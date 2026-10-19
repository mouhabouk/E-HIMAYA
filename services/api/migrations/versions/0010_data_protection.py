"""Data protection (phase 5.5, A5/A6): field-level encryption of personal data at rest, retention support.

* Encrypted (AES-256-GCM, ``app.core.crypto`` format, column name as associated data), clear column dropped:
  ``identity.profile`` phone → ``phone_enc`` (+ ``phone_hash`` blind index) and address → ``address_enc``
  (``medical_enc`` already existed); ``reports.report`` text_original / text_ar → ``*_enc`` (+ ``search_tokens``,
  blind indexes of the words for the dashboard search); ``reports.media`` transcript → ``transcript_enc`` and
  ``analysis->translation_ar`` → ``translation_ar_enc``; ``identity.volunteer`` other_skill / notes → ``*_enc``;
  ``ai.analysis`` extraction (holds a summary of the text) → ``extraction_enc``.
* ``events.outbox`` payloads (they embed report text and volunteer phones) are sealed in place.
* Retention support: ``identity.account.deleted_at``, ``reports.report.anonymised_at``, the detached-reporter
  account (all zeros uuid), ``identity.erasure_request`` and the indexes the purge jobs use.

Existing rows are encrypted in batches with the keys of the running configuration (FIELD_ENCRYPTION_KEY[S]),
keyset-paginated and idempotent (only rows whose encrypted column is still empty are processed). The
downgrade decrypts everything back into clear columns.

Revision ID: 0010_data_protection
Revises: 0009_abuse_controls
Create Date: 2026-10-19
"""

import base64
import json
from collections.abc import Callable, Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

from app.core.crypto import get_cipher, search_tokens
from migrations.sqlutil import run_script

revision: str = "0010_data_protection"
down_revision: str | None = "0009_abuse_controls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BATCH = 500
DETACHED_ACCOUNT = "00000000-0000-0000-0000-000000000000"
# Contexts are frozen here: they must match the ORM columns of the application (app/modules/*/models.py).
SEARCH_CONTEXT = "reports.report.search"
PHONE_CONTEXT = "identity.profile.phone"
EVENTS_CONTEXT = "events.outbox"
# (table, primary key, clear expression, encrypted column, context, clear column dropped afterwards)
COLUMNS: list[tuple[str, str, str, str, str, str | None]] = [
    ("identity.profile", "user_id", "phone", "phone_enc", PHONE_CONTEXT, "phone"),
    ("identity.profile", "user_id", "address", "address_enc", "identity.profile.address", "address"),
    ("reports.report", "id", "text_original", "text_original_enc", "reports.report.text_original", "text_original"),
    ("reports.report", "id", "text_ar", "text_ar_enc", "reports.report.text_ar", "text_ar"),
    ("reports.media", "id", "transcript", "transcript_enc", "reports.media.transcript", "transcript"),
    ("reports.media", "id", "analysis->>'translation_ar'", "translation_ar_enc", "reports.media.translation_ar", None),
    (
        "identity.volunteer",
        "user_id",
        "other_skill",
        "other_skill_enc",
        "identity.volunteer.other_skill",
        "other_skill",
    ),
    ("identity.volunteer", "user_id", "notes", "notes_enc", "identity.volunteer.notes", "notes"),
    ("ai.analysis", "report_id", "extraction::text", "extraction_enc", "ai.analysis.extraction", "extraction"),
]


def _batches(sql: str, pk: str) -> Any:
    """Yield keyset-paginated batches of ``sql`` (selects the key as ``k``, has an ``{after}`` placeholder)."""
    bind = op.get_bind()
    last: Any = None
    while True:
        after = "" if last is None else f"AND {pk} > :last"
        params = {"n": BATCH} if last is None else {"n": BATCH, "last": last}
        rows = bind.execute(sa.text(sql.replace("{after}", after)), params).all()
        if not rows:
            return
        yield rows
        last = rows[-1].k


def _update(table: str, pk: str, assignments: str, values: list[dict[str, Any]]) -> None:
    if values:
        op.get_bind().execute(sa.text(f"UPDATE {table} SET {assignments} WHERE {pk} = :k"), values)  # noqa: S608


def _encrypt(table: str, pk: str, clear: str, enc: str, context: str) -> None:
    cipher = get_cipher()
    sql = f"SELECT {pk} AS k, {clear} AS v FROM {table} WHERE ({clear}) IS NOT NULL AND {enc} IS NULL {{after}} ORDER BY {pk} LIMIT :n"  # noqa: S608
    for rows in _batches(sql, pk):
        _update(table, pk, f"{enc} = :v", [{"k": r.k, "v": cipher.encrypt(r.v, context=context)} for r in rows])


def _decrypt(table: str, pk: str, target: str, enc: str, context: str, cast: str = "") -> None:
    cipher = get_cipher()
    sql = f"SELECT {pk} AS k, {enc} AS v FROM {table} WHERE {enc} IS NOT NULL {{after}} ORDER BY {pk} LIMIT :n"  # noqa: S608
    value = f"CAST(:v AS {cast})" if cast else ":v"
    for rows in _batches(sql, pk):
        _update(
            table,
            pk,
            f"{target} = {value}",
            [{"k": r.k, "v": cipher.decrypt(bytes(r.v), context=context)} for r in rows],
        )


def _reseal_events(transform: Callable[[dict[str, Any]], dict[str, Any] | None]) -> None:
    sql = "SELECT id AS k, payload::text AS v FROM events.outbox WHERE true {after} ORDER BY id LIMIT :n"
    for rows in _batches(sql, "id"):
        values = []
        for r in rows:
            changed = transform(json.loads(r.v))
            if changed is not None:
                values.append({"k": r.k, "v": json.dumps(changed, ensure_ascii=False)})
        _update("events.outbox", "id", "payload = CAST(:v AS jsonb)", values)


def upgrade() -> None:
    run_script(
        """
-- An erased account (and the detached-reporter account) keeps its id for the reports, without identifier.
ALTER TABLE identity.account ADD COLUMN IF NOT EXISTS deleted_at timestamptz;
ALTER TABLE identity.account DROP CONSTRAINT ck_account_identity_shape;
ALTER TABLE identity.account ADD CONSTRAINT ck_account_identity_shape CHECK (
    (kind = 'anonymous' AND keycloak_sub IS NULL AND anon_pseudonym IS NOT NULL)
    OR (kind <> 'anonymous' AND keycloak_sub IS NOT NULL AND anon_pseudonym IS NULL)
    OR (deleted_at IS NOT NULL AND keycloak_sub IS NULL AND anon_pseudonym IS NULL));
INSERT INTO identity.account (user_id, kind, status, deleted_at)
    VALUES ('00000000-0000-0000-0000-000000000000', 'anonymous', 'active', now())
    ON CONFLICT (user_id) DO NOTHING;

ALTER TABLE identity.profile
    ADD COLUMN IF NOT EXISTS phone_enc   bytea,
    ADD COLUMN IF NOT EXISTS phone_hash  bytea,
    ADD COLUMN IF NOT EXISTS address_enc bytea;
ALTER TABLE reports.report
    ADD COLUMN IF NOT EXISTS text_original_enc bytea,
    ADD COLUMN IF NOT EXISTS text_ar_enc       bytea,
    ADD COLUMN IF NOT EXISTS search_tokens     bytea[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS anonymised_at     timestamptz;
ALTER TABLE reports.media
    ADD COLUMN IF NOT EXISTS transcript_enc     bytea,
    ADD COLUMN IF NOT EXISTS translation_ar_enc bytea;
ALTER TABLE identity.volunteer
    ADD COLUMN IF NOT EXISTS other_skill_enc bytea,
    ADD COLUMN IF NOT EXISTS notes_enc       bytea;
ALTER TABLE ai.analysis ADD COLUMN IF NOT EXISTS extraction_enc bytea;

CREATE TABLE IF NOT EXISTS identity.erasure_request (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    keycloak_sub  text NOT NULL,
    requested_at  timestamptz NOT NULL DEFAULT now(),
    disabled_at   timestamptz
);
"""
    )
    for table, pk, clear, enc, context, _drop in COLUMNS:
        _encrypt(table, pk, clear, enc, context)

    cipher = get_cipher()
    # Blind indexes: phone (exact lookup, SMS de-duplication) and report words (dashboard search).
    phones = "SELECT user_id AS k, phone AS v FROM identity.profile WHERE phone IS NOT NULL AND phone_hash IS NULL {after} ORDER BY user_id LIMIT :n"
    for rows in _batches(phones, "user_id"):
        values = [{"k": r.k, "v": cipher.blind_index(r.v, context=PHONE_CONTEXT)} for r in rows]
        _update("identity.profile", "user_id", "phone_hash = :v", values)
    words = "SELECT id AS k, text_original AS a, text_ar AS b FROM reports.report WHERE cardinality(search_tokens) = 0 AND (text_original IS NOT NULL OR text_ar IS NOT NULL) {after} ORDER BY id LIMIT :n"
    for rows in _batches(words, "id"):
        values = [{"k": r.k, "v": search_tokens([r.a, r.b], context=SEARCH_CONTEXT)} for r in rows]
        _update("reports.report", "id", "search_tokens = :v", values)

    def _seal(payload: dict[str, Any]) -> dict[str, Any] | None:
        if set(payload) == {"sealed"}:
            return None
        text = json.dumps(payload, ensure_ascii=False)
        return {"sealed": base64.b64encode(cipher.encrypt(text, context=EVENTS_CONTEXT)).decode("ascii")}

    _reseal_events(_seal)

    drops = "\n".join(
        f"ALTER TABLE {table} DROP COLUMN IF EXISTS {drop};" for table, _pk, _c, _e, _ctx, drop in COLUMNS if drop
    )
    op.execute("UPDATE reports.media SET analysis = analysis - 'translation_ar' WHERE analysis ? 'translation_ar'")
    run_script(drops)
    run_script(
        """

CREATE INDEX IF NOT EXISTS ix_profile_phone_hash ON identity.profile (phone_hash) WHERE phone_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_report_search_tokens ON reports.report USING gin (search_tokens);
-- Retention jobs (app/modules/privacy/retention.py).
CREATE INDEX IF NOT EXISTS ix_report_to_anonymise ON reports.report (updated_at)
    WHERE status IN ('closed', 'rejected') AND anonymised_at IS NULL;
CREATE INDEX IF NOT EXISTS ix_outbox_published ON events.outbox (published_at) WHERE published_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_notify_outbox_done ON notify.outbox (created_at) WHERE status <> 'pending';
CREATE INDEX IF NOT EXISTS ix_device_updated ON notify.device (updated_at);
"""
    )


def downgrade() -> None:
    run_script(
        """
DROP INDEX IF EXISTS notify.ix_device_updated;
DROP INDEX IF EXISTS notify.ix_notify_outbox_done;
DROP INDEX IF EXISTS events.ix_outbox_published;
DROP INDEX IF EXISTS reports.ix_report_to_anonymise;
DROP INDEX IF EXISTS reports.ix_report_search_tokens;
DROP INDEX IF EXISTS identity.ix_profile_phone_hash;

ALTER TABLE identity.profile ADD COLUMN IF NOT EXISTS phone text, ADD COLUMN IF NOT EXISTS address text;
ALTER TABLE reports.report ADD COLUMN IF NOT EXISTS text_original text, ADD COLUMN IF NOT EXISTS text_ar text;
ALTER TABLE reports.media ADD COLUMN IF NOT EXISTS transcript text;
ALTER TABLE identity.volunteer ADD COLUMN IF NOT EXISTS other_skill text, ADD COLUMN IF NOT EXISTS notes text;
ALTER TABLE ai.analysis ADD COLUMN IF NOT EXISTS extraction jsonb;
"""
    )
    for table, pk, _clear, enc, context, drop in COLUMNS:
        if drop is not None:
            _decrypt(table, pk, drop, enc, context, cast="jsonb" if drop == "extraction" else "")
    _restore_translations()

    cipher = get_cipher()

    def _open(payload: dict[str, Any]) -> dict[str, Any] | None:
        if set(payload) != {"sealed"}:
            return None
        opened: dict[str, Any] = json.loads(cipher.decrypt(base64.b64decode(payload["sealed"]), context=EVENTS_CONTEXT))
        return opened

    _reseal_events(_open)

    run_script(
        """
ALTER TABLE reports.report ADD CONSTRAINT ck_report_text_length CHECK (char_length(text_original) <= 4000);
ALTER TABLE identity.volunteer
    ADD CONSTRAINT volunteer_other_skill_check CHECK (char_length(other_skill) <= 100),
    ADD CONSTRAINT volunteer_notes_check CHECK (char_length(notes) <= 500);

DROP TABLE IF EXISTS identity.erasure_request;
ALTER TABLE ai.analysis DROP COLUMN IF EXISTS extraction_enc;
ALTER TABLE identity.volunteer DROP COLUMN IF EXISTS other_skill_enc, DROP COLUMN IF EXISTS notes_enc;
ALTER TABLE reports.media DROP COLUMN IF EXISTS transcript_enc, DROP COLUMN IF EXISTS translation_ar_enc;
ALTER TABLE reports.report
    DROP COLUMN IF EXISTS text_original_enc,
    DROP COLUMN IF EXISTS text_ar_enc,
    DROP COLUMN IF EXISTS search_tokens,
    DROP COLUMN IF EXISTS anonymised_at;
ALTER TABLE identity.profile
    DROP COLUMN IF EXISTS phone_enc,
    DROP COLUMN IF EXISTS phone_hash,
    DROP COLUMN IF EXISTS address_enc;
DELETE FROM identity.account a WHERE a.user_id = '00000000-0000-0000-0000-000000000000'
    AND NOT EXISTS (SELECT 1 FROM reports.report r WHERE r.user_id = a.user_id);
-- Erased accounts get an unreachable random pseudonym so they fit the previous identity shape.
UPDATE identity.account SET kind = 'anonymous', anon_pseudonym = gen_random_bytes(32)
    WHERE deleted_at IS NOT NULL AND keycloak_sub IS NULL AND anon_pseudonym IS NULL;
ALTER TABLE identity.account DROP CONSTRAINT ck_account_identity_shape;
ALTER TABLE identity.account ADD CONSTRAINT ck_account_identity_shape CHECK (
    (kind = 'anonymous' AND keycloak_sub IS NULL AND anon_pseudonym IS NOT NULL)
    OR (kind <> 'anonymous' AND keycloak_sub IS NOT NULL AND anon_pseudonym IS NULL));
ALTER TABLE identity.account DROP COLUMN IF EXISTS deleted_at;
"""
    )


def _restore_translations() -> None:
    cipher = get_cipher()
    sql = "SELECT id AS k, translation_ar_enc AS v FROM reports.media WHERE translation_ar_enc IS NOT NULL {after} ORDER BY id LIMIT :n"
    for rows in _batches(sql, "id"):
        values = [{"k": r.k, "v": cipher.decrypt(bytes(r.v), context="reports.media.translation_ar")} for r in rows]
        _update(
            "reports.media",
            "id",
            "analysis = jsonb_set(coalesce(analysis, '{}'::jsonb), '{translation_ar}', to_jsonb(CAST(:v AS text)))",
            values,
        )
