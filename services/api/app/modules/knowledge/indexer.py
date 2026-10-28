"""Indexer of the events library: worker loop ``knowledge`` and the backfill command.

Each cycle (one worker at a time, ``pg_try_advisory_xact_lock``):

1. Outbox consumer: domain events of ``events.outbox`` after the stored cursor name the items that changed
   (``report.*``, ``incident.updated``, ``media.stored``, ``call.recording``, ``analytics.report_ready``,
   ``memory.updated``); each item is rebuilt from its source (``documents.refresh``). Outbox ids come from a sequence,
   so a lower id may commit after a higher one: the cursor stops at a gap and passes it only once it is older than
   ``GAP_GRACE_S`` (a rolled-back insert leaves a permanent gap).
2. Sweep (every ``SWEEP_INTERVAL_S``): the source tables are read after per-source watermarks, a safety net for
   changes that published no event, and the first run indexes everything already there.
3. Prune (every ``PRUNE_INTERVAL_S``): rows whose source is gone or no longer searchable (anonymised or rejected
   report, archived entry…) become tombstones, their text wiped at once.
4. Embeddings: rows without a vector get the multilingual-e5 vector of the AI service (report texts and procedure
   passages reuse the vector computed at their source).
5. Push: changed rows (``os_dirty``) go to OpenSearch in bulk; tombstones are deleted there, then here.
"""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.events import open_payload
from app.modules.ai.client import AiClient, AiRejected, AiUnavailable, get_ai_client
from app.modules.knowledge import documents
from app.modules.knowledge.domain import Kind
from app.modules.knowledge.models import IndexState, SearchDoc
from app.modules.knowledge.opensearch import Engine, OpenSearch, SearchUnavailable, get_engine

log = structlog.get_logger()

LOCK_KEY = "ehimaya.knowledge.indexer"
IDLE_S = 2.0
OUTBOX_BATCH = 500
GAP_GRACE_S = 60
SWEEP_INTERVAL_S = 60
SWEEP_BATCH = 500
# Rows changed in the last minutes are left to the next sweep (their transaction may still be open).
SWEEP_SETTLE = timedelta(minutes=2)
PRUNE_INTERVAL_S = 600
PRUNE_BATCH = 500
EMBED_BATCH = 16
EMBED_CHARS = 2000
PUSH_BATCH = 200
SOURCE_VECTOR_KINDS = (Kind.REPORT.value, Kind.PROCEDURE.value)

Ref = tuple[str, str]  # (kind or "report_media", id)
_KINDS = frozenset(k.value for k in Kind)


# ---------------------------------------------------------------- state


async def _state(session: AsyncSession, key: str) -> dict[str, Any]:
    row = await session.get(IndexState, key)
    return dict(row.value) if row is not None else {}


async def _save(session: AsyncSession, key: str, value: dict[str, Any]) -> None:
    row = await session.get(IndexState, key)
    if row is None:
        session.add(IndexState(key=key, value=value))
    else:
        row.value, row.updated_at = value, datetime.now(UTC)
    await session.flush()


async def _locked(session: AsyncSession) -> bool:
    return bool(await session.scalar(text("SELECT pg_try_advisory_xact_lock(hashtext(:k))"), {"k": LOCK_KEY}))


# ---------------------------------------------------------------- refreshing items


async def apply(session: AsyncSession, refs: set[Ref]) -> dict[str, int]:
    """Rebuild every referenced item from its source (the caller commits)."""
    counts = {"upserted": 0, "deleted": 0, "unchanged": 0}
    expanded: set[tuple[Kind, str]] = set()
    for kind, ref_id in refs:
        if kind == "report_media":
            try:
                report_id = uuid.UUID(ref_id)
            except ValueError:
                continue
            media = await session.execute(text("SELECT id FROM reports.media WHERE report_id = :r"), {"r": report_id})
            expanded.update((Kind.TRANSCRIPT, str(m.id)) for m in media)
        elif kind in _KINDS:
            expanded.add((Kind(kind), ref_id))
    for kind_, ref_id in sorted(expanded):
        counts[await documents.refresh(session, kind_, ref_id)] += 1
    return counts


def refs_of_event(subject: str, payload: dict[str, Any]) -> set[Ref]:
    """Library items an event says changed."""
    refs: set[Ref] = set()

    def add(kind: str, value: Any) -> None:
        if value:
            refs.add((kind, str(value)))

    if subject.startswith("report."):
        report = payload.get("report") or {}
        add(Kind.REPORT, report.get("id"))
        add("report_media", report.get("id"))
        add(Kind.INCIDENT, report.get("incident_id"))
    elif subject == "incident.updated":
        add(Kind.INCIDENT, (payload.get("incident") or {}).get("id"))
    elif subject == "media.stored":
        add(Kind.TRANSCRIPT, (payload.get("media") or {}).get("id"))
    elif subject == "call.recording":
        add(Kind.TRANSCRIPT, payload.get("media_id"))
    elif subject == "analytics.report_ready":
        add(Kind.REPORT_DOC, payload.get("report_id"))
    elif subject == "memory.updated":
        add(Kind.MEMORY, (payload.get("entry") or {}).get("id"))
    return refs


async def consume_outbox(session: AsyncSession, *, batch: int = OUTBOX_BATCH) -> int:
    """Apply the events after the cursor (the caller holds the indexer lock and commits). Returns rows read."""
    state = await _state(session, "outbox")
    if "id" not in state:
        # First start: the sweep indexes what exists; events from now on.
        last = await session.scalar(text("SELECT coalesce(max(id), 0) FROM events.outbox"))
        await _save(session, "outbox", {"id": int(last or 0)})
        return 0
    cursor = int(state["id"])
    rows = (
        await session.execute(
            text("SELECT id, subject, payload FROM events.outbox WHERE id > :c ORDER BY id LIMIT :n"),
            {"c": cursor, "n": batch},
        )
    ).all()
    if not rows:
        return 0
    now = datetime.now(UTC)
    refs: set[Ref] = set()
    expected, advanced, blocked = cursor + 1, cursor, False
    gap = state.get("gap")
    for row in rows:
        if not blocked and row.id != expected:
            since = datetime.fromisoformat(gap["since"]) if gap and gap.get("at") == expected else None
            if since is not None and (now - since).total_seconds() >= GAP_GRACE_S:
                gap = None  # rolled back long ago: pass it
            else:
                gap = gap if since is not None else {"at": expected, "since": now.isoformat()}
                blocked = True
        if not blocked:
            advanced, expected = row.id, row.id + 1
        try:
            payload = open_payload(row.payload)
        except Exception:
            log.warning("knowledge.unreadable_event", outbox_id=row.id)
            continue
        refs |= refs_of_event(row.subject, payload)
    await apply(session, refs)
    value: dict[str, Any] = {"id": advanced}
    if blocked and gap:
        value["gap"] = gap
    await _save(session, "outbox", value)
    return len(rows)


# ---------------------------------------------------------------- sweep and prune

# name → (SQL returning ts, id after a (ts, id) watermark, refs of one row)
_SWEEPS: dict[str, tuple[str, Callable[[str], list[Ref]]]] = {
    "report": (
        "SELECT updated_at AS ts, id::text AS id FROM reports.report "
        "WHERE (updated_at, id::text) > (:ts, :id) AND updated_at < :settled ORDER BY 1, 2 LIMIT :n",
        lambda i: [(Kind.REPORT, i), ("report_media", i)],
    ),
    "incident": (
        "SELECT updated_at AS ts, id::text AS id FROM ops.incident "
        "WHERE (updated_at, id::text) > (:ts, :id) AND updated_at < :settled ORDER BY 1, 2 LIMIT :n",
        lambda i: [(Kind.INCIDENT, i)],
    ),
    "memory": (
        "SELECT updated_at AS ts, id::text AS id FROM knowledge.memory_entry "
        "WHERE (updated_at, id::text) > (:ts, :id) AND updated_at < :settled ORDER BY 1, 2 LIMIT :n",
        lambda i: [(Kind.MEMORY, i)],
    ),
    "procedure": (
        "SELECT indexed_at AS ts, id FROM decision.procedure_chunk "
        "WHERE (indexed_at, id) > (:ts, :id) AND indexed_at < :settled ORDER BY 1, 2 LIMIT :n",
        lambda i: [(Kind.PROCEDURE, i)],
    ),
    "call": (
        "SELECT updated_at AS ts, recording_media_id::text AS id FROM telephony.call "
        "WHERE recording_media_id IS NOT NULL AND (updated_at, recording_media_id::text) > (:ts, :id) "
        "AND updated_at < :settled ORDER BY 1, 2 LIMIT :n",
        lambda i: [(Kind.TRANSCRIPT, i)],
    ),
    "register": (
        "SELECT updated_at AS ts, id::text AS id FROM register.document "
        "WHERE (updated_at, id::text) > (:ts, :id) AND updated_at < :settled ORDER BY 1, 2 LIMIT :n",
        lambda i: [(Kind.REGISTER, i)],
    ),
    "report_doc": (
        "SELECT updated_at AS ts, id::text AS id FROM analytics.report "
        "WHERE (updated_at, id::text) > (:ts, :id) AND updated_at < :settled ORDER BY 1, 2 LIMIT :n",
        lambda i: [(Kind.REPORT_DOC, i)],
    ),
}

_EPOCH = datetime(2000, 1, 1, tzinfo=UTC)


async def sweep(session: AsyncSession, *, batch: int = SWEEP_BATCH, settle: timedelta = SWEEP_SETTLE) -> int:
    """One batch per source after its watermark (the caller holds the lock and commits). Returns rows seen."""
    seen = 0
    settled = datetime.now(UTC) - settle
    analytics = await documents.analytics_available(session)
    for name, (sql, refs_of) in _SWEEPS.items():
        if name == "report_doc" and not analytics:
            continue
        state = await _state(session, f"sweep:{name}")
        ts = datetime.fromisoformat(state["ts"]) if "ts" in state else _EPOCH
        rows = (
            await session.execute(text(sql), {"ts": ts, "id": state.get("id", ""), "settled": settled, "n": batch})
        ).all()
        if not rows:
            continue
        refs: set[Ref] = {ref for row in rows for ref in refs_of(row.id)}
        await apply(session, refs)
        await _save(session, f"sweep:{name}", {"ts": rows[-1].ts.isoformat(), "id": rows[-1].id})
        seen += len(rows)
    return seen


_STALE: dict[Kind, str] = {
    Kind.REPORT: "NOT EXISTS (SELECT 1 FROM reports.report r WHERE r.id::text = d.ref_id "
    "AND r.anonymised_at IS NULL AND r.status <> 'rejected')",
    Kind.INCIDENT: "NOT EXISTS (SELECT 1 FROM ops.incident i WHERE i.id::text = d.ref_id "
    "AND i.status NOT IN ('dissolved', 'merged'))",
    Kind.MEMORY: "NOT EXISTS (SELECT 1 FROM knowledge.memory_entry m WHERE m.id::text = d.ref_id "
    "AND m.published_version IS NOT NULL AND m.status <> 'archived')",
    Kind.PROCEDURE: "NOT EXISTS (SELECT 1 FROM decision.procedure_chunk c WHERE c.id = d.ref_id)",
    Kind.TRANSCRIPT: "NOT EXISTS (SELECT 1 FROM reports.media m WHERE m.id::text = d.ref_id "
    "AND m.status = 'stored' AND m.transcript_enc IS NOT NULL) OR EXISTS (SELECT 1 FROM reports.media m "
    "JOIN reports.report r ON r.id = m.report_id WHERE m.id::text = d.ref_id "
    "AND (r.anonymised_at IS NOT NULL OR r.status = 'rejected'))",
    Kind.REPORT_DOC: "NOT EXISTS (SELECT 1 FROM analytics.report a WHERE a.id::text = d.ref_id AND a.status = 'ready')",
}


async def prune(session: AsyncSession, *, batch: int = PRUNE_BATCH) -> int:
    """Tombstone rows whose source no longer qualifies (the caller commits). Returns rows deleted."""
    analytics = await documents.analytics_available(session)
    refs: set[Ref] = set()
    for kind, condition in _STALE.items():
        if kind is Kind.REPORT_DOC and not analytics:
            condition = "true"
        rows = await session.execute(
            text(
                f"SELECT ref_id FROM knowledge.search_doc d WHERE d.kind = :kind AND NOT d.deleted "  # noqa: S608
                f"AND ({condition}) LIMIT :n"
            ),
            {"kind": kind.value, "n": batch},
        )
        refs.update((kind.value, r.ref_id) for r in rows)
    counts = await apply(session, refs)
    return counts["deleted"]


# ---------------------------------------------------------------- embeddings and push


async def embed_pending(session: AsyncSession, ai: AiClient, *, batch: int = EMBED_BATCH) -> int:
    """Vectors for rows without one (the caller commits). Returns rows embedded."""
    rows = list(
        await session.scalars(
            select(SearchDoc)
            .where(
                SearchDoc.embedding.is_(None),
                SearchDoc.deleted.is_(False),
                SearchDoc.kind.not_in(SOURCE_VECTOR_KINDS),
            )
            .order_by(SearchDoc.updated_at)
            .limit(batch)
            .with_for_update(skip_locked=True)
        )
    )
    if not rows:
        return 0
    answer = await ai.embed([f"{r.title}\n{documents.stored_body(r)}"[:EMBED_CHARS] for r in rows])
    vectors = answer.get("vectors") or []
    if len(vectors) != len(rows) or any(len(v) != 768 for v in vectors):
        raise AiRejected("embedding_dimension")
    for row, vector in zip(rows, vectors, strict=True):
        row.embedding, row.embedding_model = vector, str(answer.get("model") or "")
    await session.flush()
    return len(rows)


def _document(row: SearchDoc) -> dict[str, Any]:
    return {
        "kind": row.kind,
        "ref_id": row.ref_id,
        "title": row.title,
        "body": documents.stored_body(row),
        "lang": row.lang,
        "date": row.date.isoformat() if row.date else None,
        "gouvernorats": list(row.gouvernorats),
        "access": row.access,
        "categories": list(row.categories),
        "incident_id": str(row.incident_id) if row.incident_id else None,
    }


async def push(session: AsyncSession, engine: Engine, *, batch: int = PUSH_BATCH) -> int:
    """Send changed rows to OpenSearch (the caller commits). Raises SearchUnavailable; rows then stay dirty."""
    rows = list(
        await session.scalars(
            select(SearchDoc)
            .where(SearchDoc.os_dirty.is_(True))
            .order_by(SearchDoc.updated_at)
            .limit(batch)
            .with_for_update(skip_locked=True)
        )
    )
    if not rows:
        return 0
    upserts = [_document(r) for r in rows if not r.deleted]
    deletes = [(r.kind, r.ref_id) for r in rows if r.deleted]
    await engine.bulk(upserts, deletes)
    for row in rows:
        if row.deleted:
            await session.delete(row)
        else:
            row.os_dirty = False
    await session.flush()
    return len(rows)


async def drop_tombstones(session: AsyncSession) -> None:
    """Without OpenSearch, tombstones have nobody to wait for."""
    await session.execute(delete(SearchDoc).where(SearchDoc.deleted.is_(True)))


# ---------------------------------------------------------------- loop


async def _step(sessionmaker: async_sessionmaker[AsyncSession], work: Callable[[AsyncSession], Awaitable[int]]) -> int:
    async with sessionmaker() as session, session.begin():
        if not await _locked(session):
            return 0
        return await work(session)


async def cycle(
    sessionmaker: async_sessionmaker[AsyncSession], *, sweep_now: bool, prune_now: bool, embed: bool = True
) -> int:
    """One pass of the loop; returns how much work was done (0 = idle). Raises AiUnavailable/AiRejected after the
    other steps when embedding failed."""
    done = await _step(sessionmaker, consume_outbox)
    if sweep_now:
        done += await _step(sessionmaker, sweep)
    if prune_now:
        done += await _step(sessionmaker, prune)
    engine = get_engine()
    if engine is None:
        await _step(sessionmaker, _drop)
    else:
        done += await _step(sessionmaker, lambda s: push(s, engine))
    ai = get_ai_client() if embed else None
    if ai is not None:
        done += await _step(sessionmaker, lambda s: embed_pending(s, ai))
    return done


async def _drop(session: AsyncSession) -> int:
    await drop_tombstones(session)
    return 0


async def knowledge_forever(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    """Worker loop ``knowledge``: keep knowledge.search_doc and OpenSearch in line with the platform's data."""
    indices_ready = False
    last_sweep = last_prune = embed_retry_at = 0.0
    loop = asyncio.get_running_loop()
    while True:
        done = 0
        now = loop.time()
        sweep_now, prune_now = now - last_sweep >= SWEEP_INTERVAL_S, now - last_prune >= PRUNE_INTERVAL_S
        try:
            engine = get_engine()
            if engine is not None and not indices_ready:
                await engine.ensure_indices()
                indices_ready = True
            done = await cycle(sessionmaker, sweep_now=sweep_now, prune_now=prune_now, embed=now >= embed_retry_at)
        except asyncio.CancelledError:
            raise
        except (AiUnavailable, AiRejected) as exc:
            log.info("knowledge.embed_deferred", error=str(exc))
            embed_retry_at = now + SWEEP_INTERVAL_S
        except SearchUnavailable as exc:
            log.warning("knowledge.opensearch_unavailable", error=str(exc))
            indices_ready = False
            await asyncio.sleep(10)
        except Exception:
            log.exception("knowledge.index_failed")
            await asyncio.sleep(10)
        last_sweep = now if sweep_now else last_sweep
        last_prune = now if prune_now else last_prune
        if done == 0:
            await asyncio.sleep(IDLE_S)


# ---------------------------------------------------------------- backfill


_ALL: dict[Kind, str] = {
    Kind.MEMORY: "SELECT id::text AS id FROM knowledge.memory_entry WHERE published_version IS NOT NULL",
    Kind.REPORT_DOC: "SELECT id::text AS id FROM analytics.report WHERE status = 'ready'",
    Kind.INCIDENT: "SELECT id::text AS id FROM ops.incident WHERE status NOT IN ('dissolved', 'merged')",
    Kind.REPORT: "SELECT id::text AS id FROM reports.report WHERE anonymised_at IS NULL AND status <> 'rejected'",
    Kind.TRANSCRIPT: "SELECT id::text AS id FROM reports.media WHERE transcript_enc IS NOT NULL AND status = 'stored'",
    Kind.PROCEDURE: "SELECT id FROM decision.procedure_chunk",
}


async def backfill(
    sessionmaker: async_sessionmaker[AsyncSession],
    kinds: list[Kind] | None = None,
    *,
    rebuild: bool = False,
    batch: int = 200,
) -> dict[str, int]:
    """Rebuild knowledge.search_doc from every source, then push everything to OpenSearch.

    ``rebuild``: fill new OpenSearch indices (current mapping, INDEX_VERSION) and move the aliases to them at the end,
    so searches keep working on the old indices meanwhile; the old indices are then deleted.
    """
    counts: dict[str, int] = {"upserted": 0, "deleted": 0, "unchanged": 0, "pushed": 0}
    async with sessionmaker() as session:
        analytics = await documents.analytics_available(session)
    for kind in kinds or list(Kind):
        if kind is Kind.REPORT_DOC and not analytics:
            continue
        async with sessionmaker() as session:
            ids = [r.id for r in await session.execute(text(_ALL[kind]))]
        for start in range(0, len(ids), batch):
            async with sessionmaker() as session, session.begin():
                result = await apply(session, {(kind.value, i) for i in ids[start : start + batch]})
            for name, value in result.items():
                counts[name] += value
    async with sessionmaker() as session, session.begin():
        await prune(session, batch=1_000_000)
        where = "true" if not kinds else "kind = ANY(:kinds)"
        await session.execute(
            text(f"UPDATE knowledge.search_doc SET os_dirty = true WHERE {where}"),  # noqa: S608
            {"kinds": [k.value for k in kinds or []]},
        )
    engine = get_engine()
    if engine is None:
        async with sessionmaker() as session, session.begin():
            await drop_tombstones(session)
        return counts
    if rebuild and isinstance(engine, OpenSearch):
        suffix = "r" + datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        await engine.create_rebuild(suffix)
        while True:
            async with sessionmaker() as session, session.begin():
                rows = list(
                    await session.scalars(
                        select(SearchDoc).where(SearchDoc.os_dirty.is_(True)).limit(500).with_for_update()
                    )
                )
                if not rows:
                    break
                await engine.bulk_to([_document(r) for r in rows if not r.deleted], [], suffix)
                for row in rows:
                    if row.deleted:
                        await session.delete(row)
                    else:
                        row.os_dirty = False
                counts["pushed"] += len(rows)
        await engine.switch_to(suffix)
        return counts
    await engine.ensure_indices()
    while True:
        async with sessionmaker() as session, session.begin():
            pushed = await push(session, engine, batch=500)
        counts["pushed"] += pushed
        if pushed == 0:
            break
    return counts
