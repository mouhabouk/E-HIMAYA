"""Inventory of encrypted columns and re-encryption under the active key version (key rotation).

Rotation procedure (docs/api/phase-5-5-contract.md):
1. add the new key: ``FIELD_ENCRYPTION_KEYS=2:<base64>`` (it becomes active, the old one stays readable);
2. restart, then ``python -m app.modules.privacy.cli reencrypt`` until it reports 0 remaining;
3. retire the old version (version 1, FIELD_ENCRYPTION_KEY, stays: it roots the blind indexes).
"""

import base64
import json
from dataclasses import dataclass

from sqlalchemy import Table, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.crypto import EncryptedJSON, EncryptedText, get_cipher
from app.core.db import Base
from app.core.events import SEAL_CONTEXT
from app.modules import models as _models  # noqa: F401  (registers every table)


@dataclass(frozen=True, slots=True)
class EncryptedColumn:
    table: str  # schema-qualified
    key: str  # single-column primary key
    column: str
    context: str


# Encrypted by hand (not through a column type): the CIN, written with its blind index.
_MANUAL = [EncryptedColumn("identity.profile", "user_id", "cin_enc", "identity.profile.cin")]


def _qualified(table: Table) -> str:
    return f"{table.schema}.{table.name}" if table.schema else table.name


def encrypted_columns() -> list[EncryptedColumn]:
    """Every column holding ciphertext, found from the ORM column types (plus the manual ones)."""
    found: list[EncryptedColumn] = list(_MANUAL)
    for table in Base.metadata.sorted_tables:
        keys = [c.name for c in table.primary_key.columns]
        for column in table.columns:
            if isinstance(column.type, EncryptedText | EncryptedJSON):
                assert len(keys) == 1, f"{table.name}: re-encryption needs a single-column key"
                found.append(EncryptedColumn(_qualified(table), keys[0], column.name, column.type.context))
    return found


async def _reencrypt_column(
    sessionmaker: async_sessionmaker[AsyncSession], col: EncryptedColumn, batch: int, dry_run: bool
) -> int:
    cipher = get_cipher()
    done = 0
    last: object = None
    while True:
        after = "" if last is None else f"AND {col.key} > :last"
        params: dict[str, object] = {"active": cipher.active, "n": batch}
        if last is not None:
            params["last"] = last
        async with sessionmaker() as session, session.begin():
            rows = (
                await session.execute(
                    text(
                        f"SELECT {col.key} AS k, {col.column} AS v FROM {col.table} "  # noqa: S608 (identifiers from the ORM metadata)
                        f"WHERE {col.column} IS NOT NULL AND get_byte({col.column}, 0) <> :active {after} "
                        f"ORDER BY {col.key} LIMIT :n FOR UPDATE SKIP LOCKED"
                    ),
                    params,
                )
            ).all()
            if not rows:
                return done
            if not dry_run:
                values = [
                    {
                        "k": r.k,
                        "v": cipher.encrypt(cipher.decrypt(bytes(r.v), context=col.context), context=col.context),
                    }
                    for r in rows
                ]
                await session.execute(
                    text(f"UPDATE {col.table} SET {col.column} = :v WHERE {col.key} = :k"),  # noqa: S608 (identifiers from the ORM metadata)
                    values,
                )
            done += len(rows)
            last = rows[-1].k


async def _reencrypt_events(sessionmaker: async_sessionmaker[AsyncSession], batch: int, dry_run: bool) -> int:
    cipher = get_cipher()
    done, last = 0, 0
    while True:
        async with sessionmaker() as session, session.begin():
            rows = (
                await session.execute(
                    text(
                        "SELECT id, payload->>'sealed' AS sealed FROM events.outbox "
                        "WHERE payload ? 'sealed' AND get_byte(decode(payload->>'sealed', 'base64'), 0) <> :active "
                        "AND id > :last ORDER BY id LIMIT :n FOR UPDATE SKIP LOCKED"
                    ),
                    {"active": cipher.active, "last": last, "n": batch},
                )
            ).all()
            if not rows:
                return done
            if not dry_run:
                values = []
                for r in rows:
                    clear = cipher.decrypt(base64.b64decode(r.sealed), context=SEAL_CONTEXT)
                    sealed = base64.b64encode(cipher.encrypt(clear, context=SEAL_CONTEXT)).decode("ascii")
                    values.append({"id": r.id, "payload": json.dumps({"sealed": sealed})})
                await session.execute(
                    text("UPDATE events.outbox SET payload = CAST(:payload AS jsonb) WHERE id = :id"), values
                )
            done += len(rows)
            last = rows[-1].id


async def reencrypt(
    sessionmaker: async_sessionmaker[AsyncSession], *, batch: int = 500, dry_run: bool = False
) -> dict[str, int]:
    """Re-encrypt every value not under the active key version. Returns the count per column.

    Safe to interrupt and re-run, and to run while the API serves (row locks, short transactions).
    With ``dry_run`` nothing is written: the counts are what remains to be re-encrypted.
    """
    counts: dict[str, int] = {}
    for col in encrypted_columns():
        counts[f"{col.table}.{col.column}"] = await _reencrypt_column(sessionmaker, col, batch, dry_run)
    counts["events.outbox.payload"] = await _reencrypt_events(sessionmaker, batch, dry_run)
    return counts
