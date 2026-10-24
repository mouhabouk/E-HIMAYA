"""Background delivery: message fan-out jobs (``notify.dispatch``), individual messages (``notify.outbox``),
and the periodic housekeeping of phase 5 (expiries, call-out timeouts, institution digests).

Network calls never run inside a database transaction: a job or a batch is claimed with a short lease,
sent, then recorded. A crashed worker's lease expires and another instance resumes from the cursor.
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta
from functools import partial
from typing import Any

import structlog
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import metrics
from app.core.config import get_settings
from app.core.events import emit
from app.modules.audit import service as audit
from app.modules.notify import service, templates
from app.modules.notify.models import Device, Dispatch, Message, OrgDigest, Outbox
from app.modules.notify.providers import Push, Result, get_providers
from app.modules.settings import domain as settings_domain
from app.modules.settings import service as settings_service

log = structlog.get_logger()

BATCH = 200
CONCURRENCY = 20
LEASE = timedelta(seconds=120)
OUTBOX_MAX_ATTEMPTS = 8
SMS_MAX_CHARS = 300
DIGEST_EVERY = timedelta(days=7)
# Phase 10 §5.2: an alert channel that failed for this share of its recipients, or could not send at all, is
# reported to the people who publish alerts.
DEGRADED_FAILURE_RATE = 0.10


def _now() -> datetime:
    return datetime.now(UTC)


async def _gather(calls: list[Callable[[], Awaitable[Result]]]) -> list[Result]:
    semaphore = asyncio.Semaphore(CONCURRENCY)

    async def run(call: Callable[[], Awaitable[Result]]) -> Result:
        async with semaphore:
            try:
                return await call()
            except Exception as exc:  # one bad recipient never stops the batch
                return Result(ok=False, error=type(exc).__name__)

    return list(await asyncio.gather(*(run(c) for c in calls)))


def _localized(value: dict[str, str], lang: str) -> str:
    return value.get(lang) or value.get("ar") or ""


def _push_for(message: Message, purpose: str, token: str, platform: str, locale: str) -> Push:
    if message.audience == "user":
        # A notification to one person is personal: content-free push, read in the app inbox (A8).
        kind = "alert_cancelled" if purpose == "cancel" else message.kind
        return Push(
            token,
            platform,
            templates.pick(templates.PERSONAL_PUSH_TITLE, locale),
            templates.pick(templates.PERSONAL_PUSH_BODY, locale),
            {"type": kind, "id": str(message.id), "redacted": "1"},
        )
    if purpose == "cancel":
        title = templates.pick(templates.ALERT_CANCELLED_TITLE, locale)
        return Push(
            token,
            platform,
            title,
            _localized(message.title, locale),
            {"type": "alert_cancelled", "id": str(message.id)},
        )
    data = {"type": message.kind, "id": str(message.id)}
    if message.severity:
        data["severity"] = message.severity
    return Push(
        token,
        platform,
        _localized(message.title, locale),
        _localized(message.body, locale),
        data,
        alert=message.kind == "alert",
        critical=message.kind == "alert" and message.severity == "high",
    )


def _count_failures(channel: str, results: list[Result]) -> None:
    failed = sum(1 for r in results if not r.ok)
    if failed:
        metrics.NOTIFY_FAILURES.labels(channel=channel).inc(failed)


# ---------------------------------------------------------------- fan-out jobs


async def _claim_job(sessionmaker: async_sessionmaker[AsyncSession]) -> tuple[Dispatch, Message] | None:
    async with sessionmaker() as session, session.begin():
        job = await session.scalar(
            select(Dispatch)
            .where((Dispatch.status == "pending") | ((Dispatch.status == "running") & (Dispatch.lease_until <= _now())))
            .order_by(Dispatch.started_at.nulls_first())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if job is None:
            return None
        message = await session.get(Message, job.message_id)
        assert message is not None
        job.status, job.lease_until = "running", _now() + LEASE
        job.started_at = job.started_at or _now()
        await session.flush()
        session.expunge_all()
        return job, message


async def _batch(
    sessionmaker: async_sessionmaker[AsyncSession], job: Dispatch, message: Message
) -> tuple[list[Result], str | None, int, list[str]]:
    """Send one batch. Returns results, the new cursor, the batch size and the tokens to forget."""
    providers = get_providers()
    after = job.cursor or ""
    async with sessionmaker() as session:
        if job.channel == "push":
            rows = (
                await session.execute(text(service.DEVICES_SQL), {"mid": message.id, "after": after, "limit": BATCH})
            ).all()
        else:
            rows = (
                await session.execute(
                    text(service.profiles_sql(job.channel)), {"mid": message.id, "after": after, "limit": BATCH}
                )
            ).all()
    calls: list[Callable[[], Awaitable[Result]]] = []
    if job.channel == "push":
        for token, platform, locale in rows:
            push = _push_for(message, job.purpose, token, platform, locale)
            calls.append(partial(providers.push.send, push))
    elif job.channel == "sms":
        for _phone_key, locale, secret in rows:
            sms_text = f"{_localized(message.title, locale)}: {_localized(message.body, locale)}"[:SMS_MAX_CHARS]
            calls.append(partial(providers.sms.send, service.phone_of(secret), sms_text))
    else:
        for address, locale, _secret in rows:
            lang = locale if locale in ("ar", "fr", "en") else "ar"
            body = f"{_localized(message.body, lang)}\n\n{templates.pick(templates.SIGNATURE, lang)}"
            calls.append(partial(providers.email.send, address, _localized(message.title, lang), body))
    results = await _gather(calls)
    _count_failures(job.channel, results)
    gone = [rows[i][0] for i, r in enumerate(results) if r.unregistered] if job.channel == "push" else []
    cursor = rows[-1][0] if rows else job.cursor
    return results, cursor, len(rows), gone


async def real_send_allowed(sessionmaker: async_sessionmaker[AsyncSession]) -> bool:
    """Phase 9 §7.4: outside production the providers are the simulators (SIMULATION) and alerts go out as before;
    in production an alert reaches a real provider only when ``NOTIFY_REAL_SEND`` (with its approval reference) and
    the platform setting ``notify.real_send_enabled`` are both on. Neither is on in this phase."""
    settings = get_settings()
    if settings.app_env != "production":
        return True
    if not settings.notify_real_send:
        return False
    async with sessionmaker() as session:
        return bool(await settings_service.get(session, settings_domain.NOTIFY_REAL_SEND))


def degraded(row: Dispatch, message: Message) -> str | None:
    """Why a finished alert dispatch needs a person's attention, or None."""
    if message.kind != "alert" or row.purpose != "publish" or row.status not in ("done", "skipped"):
        return None
    if row.status == "skipped" and row.error == "not_configured":
        return "not_configured"
    total = row.sent + row.failed
    if total and row.failed / total >= DEGRADED_FAILURE_RATE:
        return "failures"
    return None


async def _report_degraded(session: AsyncSession, row: Dispatch, message: Message, reason: str) -> None:
    out = await service.message_out(session, message)
    codes = await service.area_codes(session, message)
    details = {"channel": row.channel, "reason": reason, "sent": row.sent, "failed": row.failed}
    await emit(
        session,
        "alert.delivery_degraded",
        {"message": out.model_dump(mode="json"), "gouvernorat_codes": codes, **details},
    )
    await audit.record(
        session,
        actor="system",
        action="alert.delivery_degraded",
        target=f"notification:{message.id}",
        details=details,
        gouvernorats=codes or None,
    )
    log.warning("notify.delivery_degraded", message_id=str(message.id), **details)


async def run_job(sessionmaker: async_sessionmaker[AsyncSession]) -> bool:
    """Advance one fan-out job by one batch. Returns False when nothing was waiting."""
    claimed = await _claim_job(sessionmaker)
    if claimed is None:
        return False
    job, message = claimed
    provider = getattr(get_providers(), job.channel)
    skipped: str | None = None
    if not provider.configured:
        skipped = "not_configured"
    elif message.kind == "alert" and not await real_send_allowed(sessionmaker):
        skipped = "real_send_disabled"
    if skipped is not None:
        results: list[Result] = []
        cursor, size, final = job.cursor, 0, "skipped"
        gone: list[str] = []
    else:
        results, cursor, size, gone = await _batch(sessionmaker, job, message)
        final = "done" if size < BATCH else "running"
    async with sessionmaker() as session, session.begin():
        row = await session.get(Dispatch, (job.message_id, job.channel, job.purpose), with_for_update=True)
        if row is None or row.status != "running":
            return True  # cancelled meanwhile
        row.sent += sum(1 for r in results if r.ok)
        row.failed += sum(1 for r in results if not r.ok)
        row.cursor = cursor
        row.status = final
        # A job with more recipients is released at once, so the next batch is claimed without waiting.
        row.lease_until = None if final != "running" else _now()
        if final != "running":
            row.finished_at = _now()
            row.error = skipped if final == "skipped" else None
        if gone:
            await session.execute(delete(Device).where(Device.token.in_(gone)))
        current = await session.get(Message, job.message_id)
        if current is not None:
            await service.announce(session, current)
            reason = degraded(row, current)
            if reason is not None:
                await _report_degraded(session, row, current, reason)
    return True


# ---------------------------------------------------------------- individual messages


async def run_outbox(sessionmaker: async_sessionmaker[AsyncSession], limit: int = 50) -> int:
    async with sessionmaker() as session, session.begin():
        rows = list(
            await session.scalars(
                select(Outbox)
                .where(Outbox.status == "pending", Outbox.next_attempt_at <= _now())
                .order_by(Outbox.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )
        for row in rows:
            row.next_attempt_at = _now() + LEASE
        devices: dict[Any, list[tuple[str, str, str]]] = {}
        users = {r.user_id for r in rows if r.channel == "push" and r.user_id is not None}
        if users:
            for d in await session.scalars(select(Device).where(Device.user_id.in_(users))):
                devices.setdefault(d.user_id, []).append((d.token, d.platform, d.locale))
        await session.flush()
        session.expunge_all()
    if not rows:
        return 0
    providers = get_providers()
    outcomes: dict[int, tuple[str, str | None]] = {}
    gone: list[str] = []
    for row in rows:
        if row.channel == "push":
            targets = devices.get(row.user_id, [])
            if not providers.push.configured or not targets:
                outcomes[row.id] = ("skipped", "not_configured" if targets else "no_device")
                continue
            p = row.payload
            data = {k: str(v) for k, v in (p.get("data") or {}).items()} | {"type": p["type"]}
            calls: list[Callable[[], Awaitable[Result]]] = [
                partial(
                    providers.push.send,
                    Push(
                        t,
                        plat,
                        _localized(p["title"], loc),
                        _localized(p["body"], loc),
                        data,
                        bool(p.get("alert")),
                        bool(p.get("critical")),
                    ),
                )
                for t, plat, loc in targets
            ]
            results = await _gather(calls)
            _count_failures("push", results)
            gone += [targets[i][0] for i, r in enumerate(results) if r.unregistered]
            ok = any(r.ok for r in results)
            outcomes[row.id] = ("sent", None) if ok else ("retry", results[0].error if results else None)
        else:
            if not providers.email.configured:
                outcomes[row.id] = ("skipped", "not_configured")
                continue
            assert row.address is not None
            result = await providers.email.send(row.address, row.payload["subject"], row.payload["text"])
            _count_failures("email", [result])
            outcomes[row.id] = ("sent", None) if result.ok else ("retry", result.error)
    async with sessionmaker() as session, session.begin():
        for row_id, (state, error) in outcomes.items():
            record = await session.get(Outbox, row_id, with_for_update=True)
            if record is None:
                continue
            record.last_error = error
            if state == "retry":
                record.attempts += 1
                if record.attempts >= OUTBOX_MAX_ATTEMPTS:
                    record.status = "failed"
                else:
                    record.next_attempt_at = _now() + timedelta(seconds=min(30 * 2**record.attempts, 3600))
            else:
                record.status = state
                record.sent_at = _now() if state == "sent" else None
        if gone:
            await session.execute(delete(Device).where(Device.token.in_(gone)))
    return len(rows)


# ---------------------------------------------------------------- housekeeping


async def institution_digests(session: AsyncSession, today: date) -> int:
    """Weekly e-mail to institution admins listing expired trainings and overdue maintenance (FR-B-005/006).

    Sent when the list changed, or a week after the last digest while items remain.
    """
    from app.modules.orgs import service as orgs
    from app.modules.orgs.models import Equipment, Member, Organization, TeamMember

    sent = 0
    for org in await session.scalars(select(Organization).where(Organization.status == "active")):
        team = list(await session.scalars(select(TeamMember).where(TeamMember.org_id == org.id)))
        equipment = list(await session.scalars(select(Equipment).where(Equipment.org_id == org.id)))
        alerts = orgs.alerts_of(team, equipment, today)
        if not alerts:
            continue
        names = {m.id: m.full_name for m in team} | {e.id: e.kind for e in equipment}
        fingerprint = ",".join(sorted(f"{a.kind}:{a.ref}" for a in alerts))
        digest = await session.get(OrgDigest, org.id, with_for_update=True)
        if digest is not None and digest.fingerprint == fingerprint and digest.sent_at > _now() - DIGEST_EVERY:
            continue
        admins = await session.scalars(
            select(Member.email).where(Member.org_id == org.id, Member.role == "admin", Member.email.is_not(None))
        )
        recipients = [e for e in admins if e]
        if not recipients:
            continue
        items = {
            lang: "\n".join(
                "• " + templates.DIGEST_ITEM[a.kind][lang].format(name=names.get(a.ref, "")) for a in alerts
            )
            for lang in ("ar", "fr", "en")
        }
        link = f"{_portal_url()}/orgs/{org.id}"
        body = templates.multilingual(
            {lang: templates.DIGEST_BODY[lang].format(org=org.name, items=items[lang], link=link) for lang in items}
        )
        subject = templates.DIGEST_SUBJECT["ar"].format(org=org.name)
        from app.modules.notify import outbox

        for address in recipients:
            outbox.email(session, address, subject, body)
        if digest is None:
            session.add(OrgDigest(org_id=org.id, fingerprint=fingerprint, sent_at=_now()))
        else:
            digest.fingerprint, digest.sent_at = fingerprint, _now()
        sent += 1
    return sent


def _portal_url() -> str:
    from app.core.config import get_settings

    return get_settings().portal_public_url


_last_digest: date | None = None


async def housekeeping(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    global _last_digest
    from app.modules.doctors import service as doctors
    from app.modules.ops import interventions
    from app.modules.safety import service as safety
    from app.modules.volunteers import service as volunteers

    async with sessionmaker() as session, session.begin():
        for message_id in await service.expire_alerts(session):
            message = await session.get(Message, message_id)
            if message is not None:
                await service.announce(session, message)
        await interventions.expire_targets(session)
        await volunteers.expire_readiness(session)
        await doctors.expire_availability(session)
        # Safety checks past their time (phase B2): checked every minute, so a check fires at most a minute late.
        await safety.fire_due_checks(session)
        today = _now().date()
        if _last_digest != today:
            # Several API instances may run this; the digest row lock and fingerprint keep it to one e-mail.
            await session.execute(text("SELECT pg_advisory_xact_lock(hashtext('ehimaya.org_digest'))"))
            await institution_digests(session, today)
            _last_digest = today


async def deliver_forever(sessionmaker: async_sessionmaker[AsyncSession], idle_s: float = 1.0) -> None:
    last_housekeeping = 0.0
    loop = asyncio.get_running_loop()
    while True:
        try:
            worked = await run_job(sessionmaker)
            worked = bool(await run_outbox(sessionmaker)) or worked
            if loop.time() - last_housekeeping > 60:
                await housekeeping(sessionmaker)
                last_housekeeping = loop.time()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("notify.delivery_failed")
            worked = False
        if not worked:
            await asyncio.sleep(idle_s)
