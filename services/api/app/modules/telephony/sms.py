"""SMS reports (FR-A-048, contract §5): ``EH1 <category> <lat>,<lon> <acc>m <client_uuid8>``.

With no internet at all, the app opens the SMS app with that body addressed to SMS_REPORT_NUMBER; the operator's SMS
gateway posts it to ``POST /internal/sms/inbound`` (HMAC-signed, internal.py) and a report with ``source=sms`` is
created. ``acc`` is whole metres rounded up (``0m`` = unknown); ``client_uuid8`` is the first 8 hex digits of the
report's client_uuid on the phone.

An 8-hex prefix can collide, so deduplication never relies on it alone (docs/api/phase-7-contract.md, implementation
notes): an SMS and an app report are the same report only with the same prefix AND category, within
SMS_DEDUP_WINDOW_H, AND the same sender when it is known (a registered citizen with a verified phone), otherwise
within 5 km of each other.

* gateway retry (same message id) → the same report;
* the same SMS sent twice (same sender, prefix, category, window) → the same report;
* the app synced the report first → the SMS points to it (no second report);
* the SMS arrived first → when the app syncs (``create_report``), the SMS report adopts the app's client_uuid and
  becomes the citizen's report (``adopt_sms_report``), so the citizen sees one report and one tracking code.

No message text is stored: only keyed hashes of the message id and sender, the sender's number encrypted (call back),
the prefix and the category.
"""

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from geoalchemy2 import Geography
from sqlalchemy import Text, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.crypto import get_cipher, pseudonym
from app.core.db import as_system
from app.core.events import emit
from app.modules.ai import pipeline
from app.modules.ai.models import Analysis
from app.modules.geo.service import admin_address
from app.modules.identity.models import Account, AccountKind, AccountStatus, Profile, phone_index
from app.modules.identity.service import Reporter, _upsert_account
from app.modules.reports import schemas as report_schemas
from app.modules.reports.domain import LAT_MAX, LAT_MIN, LON_MAX, LON_MIN, Category, Status
from app.modules.reports.models import Report, StatusHistory
from app.modules.reports.service import (
    ReportRow,
    get_report_row,
    locate_gouvernorat,
    next_tracking_code,
    staff_report,
)
from app.modules.settings import service as platform_settings
from app.modules.telephony.domain import normalize_caller
from app.modules.telephony.models import SmsInbound

log = structlog.get_logger()

_BODY = re.compile(
    r"^\s*EH1\s+(?P<category>[a-z_]{2,32})\s+(?P<lat>-?\d{1,2}(?:\.\d{1,8})?)\s*,\s*(?P<lon>-?\d{1,3}(?:\.\d{1,8})?)"
    r"\s+(?P<acc>\d{1,5})m\s+(?P<prefix>[0-9a-f]{8})\s*$",
    re.IGNORECASE,
)
_MESSAGE_CONTEXT = "telephony.sms_inbound.message_id"
_SENDER_CONTEXT = "telephony.sms_inbound.sender"
SMS_ACTOR = "sms"


@dataclass(frozen=True, slots=True)
class SmsReport:
    category: Category
    lat: float
    lon: float
    accuracy_m: float | None
    prefix: str


def parse(text: str) -> SmsReport | None:
    """The report carried by an SMS body, or None when it is not a valid ``EH1`` message."""
    match = _BODY.match(text or "")
    if match is None:
        return None
    try:
        category = Category(match.group("category").lower())
    except ValueError:
        return None
    lat, lon = float(match.group("lat")), float(match.group("lon"))
    if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
        return None
    accuracy = int(match.group("acc"))
    return SmsReport(category, lat, lon, float(accuracy) if accuracy > 0 else None, match.group("prefix").lower())


def message_hash(message_id: str) -> bytes:
    return get_cipher().blind_index(message_id, context=_MESSAGE_CONTEXT)


def sender_hash(number: str) -> bytes:
    return get_cipher().blind_index(number, context=_SENDER_CONTEXT)


def _point(lat: float, lon: float) -> Any:
    return cast(func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326), Geography)


# ---------------------------------------------------------------- reporter of an SMS


async def _verified_owner(session: AsyncSession, number: str) -> uuid.UUID | None:
    """The registered citizen whose verified phone is ``number`` (one only), else None."""
    owners = list(
        await session.scalars(
            select(Profile.user_id)
            .join(Account, Account.user_id == Profile.user_id)
            .where(
                Profile.phone_hash == phone_index(number),
                Profile.phone_verified_at.is_not(None),
                Account.deleted_at.is_(None),
            )
            .limit(2)
        )
    )
    return owners[0] if len(owners) == 1 else None


async def sms_account(session: AsyncSession, number: str) -> Account:
    """The account an SMS report belongs to: the citizen with this verified phone, else an anonymous identity
    derived from the number (HMAC with the pseudonym secret, like a device key: not reversible)."""
    owner = await _verified_owner(session, number)
    if owner is not None:
        account = await session.get(Account, owner)
        assert account is not None
        return account
    return await _upsert_account(session, AccountKind.ANONYMOUS, sub=None, anon=pseudonym(f"sms:{number}".encode()))


# ---------------------------------------------------------------- inbound SMS


@dataclass(frozen=True, slots=True)
class Outcome:
    status: str  # created | duplicate | ignored
    report: Report | None = None
    reason: str | None = None


async def _report_of(session: AsyncSession, report_id: uuid.UUID | None) -> Report | None:
    return await session.get(Report, report_id) if report_id is not None else None


async def _matching_app_report(
    session: AsyncSession, parsed: SmsReport, owner: uuid.UUID | None, since: datetime
) -> Report | None:
    """An app report already synced for this SMS: same prefix, category and window; same sender when known."""
    query = select(Report).where(
        func.left(cast(Report.client_uuid, Text), 8) == parsed.prefix,
        Report.category == parsed.category.value,
        Report.received_at >= since,
        Report.source != "sms",
    )
    if owner is not None:
        query = query.where(Report.user_id == owner)
    else:
        query = query.where(
            func.ST_DWithin(
                Report.location,
                _point(parsed.lat, parsed.lon),
                await platform_settings.threshold(session, "telephony.sms_match_m"),
            )
        )
    return await session.scalar(query.order_by(Report.received_at.desc()).limit(1))


async def receive(
    session: AsyncSession, message_id: str, sender: str, text: str, received_at: datetime | None
) -> Outcome:
    """Handle one SMS from the gateway (the caller commits). Never raises for a bad message: the gateway would
    retry it forever; the outcome says why it was ignored."""
    settings = get_settings()
    now = datetime.now(UTC)
    digest = message_hash(message_id)
    seen = await session.scalar(select(SmsInbound).where(SmsInbound.message_hash == digest))
    if seen is not None:
        report = await _report_of(session, seen.report_id)
        return Outcome("duplicate" if report else "ignored", report, None if report else seen.reason)

    number = normalize_caller(sender)
    parsed = parse(text)
    row = SmsInbound(
        message_hash=digest,
        sender_hash=sender_hash(number) if number else None,
        sender_number=number,
        client_prefix=parsed.prefix if parsed else None,
        category=parsed.category.value if parsed else None,
        outcome="rejected",
        received_at=now,
    )
    session.add(row)
    if parsed is None or number is None:
        row.reason = "unparseable" if parsed is None else "no_sender"
        await session.flush()
        return Outcome("ignored", reason=row.reason)

    since = now - timedelta(hours=settings.sms_dedup_window_h)
    # The same SMS sent again by the same person.
    repeated = await session.scalar(
        select(SmsInbound)
        .where(
            SmsInbound.sender_hash == row.sender_hash,
            SmsInbound.client_prefix == parsed.prefix,
            SmsInbound.category == parsed.category.value,
            SmsInbound.received_at >= since,
            SmsInbound.report_id.is_not(None),
        )
        .order_by(SmsInbound.received_at.desc())
        .limit(1)
    )
    if repeated is not None and (report := await _report_of(session, repeated.report_id)) is not None:
        row.outcome, row.report_id, row.reason = "duplicate", report.id, "repeated_sms"
        await session.flush()
        return Outcome("duplicate", report, "repeated_sms")

    account = await sms_account(session, number)
    if account.status == AccountStatus.BANNED:
        row.reason = "sender_banned"
        await session.flush()
        return Outcome("ignored", reason=row.reason)
    owner = account.user_id if account.kind is not AccountKind.ANONYMOUS else None
    synced = await _matching_app_report(session, parsed, owner, since)
    if synced is not None:
        row.outcome, row.report_id, row.reason, row.merged_at = "duplicate", synced.id, "app_report", now
        await session.flush()
        return Outcome("duplicate", synced, "app_report")

    report = await _create_report(session, account, parsed, received_at, now)
    row.outcome, row.report_id = "created", report.id
    await session.flush()
    return Outcome("created", report)


async def _create_report(
    session: AsyncSession, account: Account, parsed: SmsReport, sent_at: datetime | None, now: datetime
) -> Report:
    created_at = min(sent_at, now) if sent_at is not None else now
    gouvernorat = await locate_gouvernorat(session, parsed.lat, parsed.lon)
    address = await admin_address(session, parsed.lat, parsed.lon)
    report = Report(
        tracking_code=await next_tracking_code(session, now, gouvernorat),
        client_uuid=None,
        user_id=account.user_id,
        category=parsed.category.value,
        location=_point(parsed.lat, parsed.lon),
        location_accuracy_m=parsed.accuracy_m,
        gouvernorat_code=gouvernorat,
        delegation_id=address.delegation_id,
        sector_code=address.sector_code,
        municipality_id=address.municipality_id,
        status=Status.RECEIVED.value,
        source="sms",
        created_at=created_at,
        received_at=now,
        updated_at=now,
    )
    session.add(report)
    await session.flush()
    session.add(StatusHistory(report_id=report.id, status=Status.RECEIVED.value, at=now, actor=SMS_ACTOR))
    await pipeline.baseline(session, report)
    row = ReportRow(report, parsed.lat, parsed.lon)
    analysis = await session.get(Analysis, report.id)
    await emit(
        session,
        "report.created",
        {"report": staff_report(row, account.kind.value, 0, analysis).model_dump(mode="json")},
    )
    log.info("sms.report_created", report_id=str(report.id), gouvernorat=gouvernorat)
    return report


def reply_text(tracking_code: str) -> str:
    """Acknowledgement SMS sent back to the sender (Arabic and French, one SMS)."""
    return f"ء-حماية: تم استلام بلاغك. رقم المتابعة {tracking_code}. e-Himaya: signalement reçu, suivi {tracking_code}"


# ---------------------------------------------------------------- app sync after an SMS


async def _reporter_phone_hash(session: AsyncSession, reporter: Reporter) -> bytes | None:
    if reporter.is_anonymous:
        return None
    profile = await session.get(Profile, reporter.user_id)
    if profile is None or profile.phone_verified_at is None or not profile.phone:
        return None
    number = normalize_caller(profile.phone)
    return sender_hash(number) if number else None


async def adopt_sms_report(
    session: AsyncSession, reporter: Reporter, body: report_schemas.ReportIn
) -> ReportRow | None:
    """Called by ``reports.service.create_report`` before creating a report: when the same report already arrived
    by SMS, that report takes the app's client_uuid (and text) and is returned instead of a second one."""
    settings = get_settings()
    now = datetime.now(UTC)
    prefix = str(body.client_uuid)[:8]
    phone = await _reporter_phone_hash(session, reporter)
    query = (
        select(SmsInbound, Report)
        .join(Report, Report.id == SmsInbound.report_id)
        .where(
            SmsInbound.client_prefix == prefix,
            SmsInbound.category == body.category.value,
            SmsInbound.outcome == "created",
            SmsInbound.merged_at.is_(None),
            SmsInbound.received_at >= now - timedelta(hours=settings.sms_dedup_window_h),
            Report.client_uuid.is_(None),
            Report.source == "sms",
        )
    )
    if phone is not None:
        query = query.where(SmsInbound.sender_hash == phone)
    else:
        query = query.where(
            func.ST_DWithin(
                Report.location,
                _point(body.location.lat, body.location.lon),
                await platform_settings.threshold(session, "telephony.sms_match_m"),
            )
        )
    # The SMS report is not the reporter's yet: found and taken over with the system scope (row-level security), the
    # ownership rule below being the check.
    async with as_system(session):
        adopted = await _adopt(session, reporter, body, query, now)
    return await get_report_row(session, adopted) if adopted is not None else None


async def _adopt(
    session: AsyncSession, reporter: Reporter, body: report_schemas.ReportIn, query: Any, now: datetime
) -> uuid.UUID | None:
    found = (await session.execute(query.order_by(SmsInbound.received_at.desc()).limit(1).with_for_update())).first()
    if found is None:
        return None
    sms, report = found
    owner = await session.get(Account, report.user_id)
    # A report owned by another registered citizen (their verified phone sent it) is never taken over.
    if owner is not None and owner.kind is not AccountKind.ANONYMOUS and owner.user_id != reporter.user_id:
        return None
    report.client_uuid = body.client_uuid
    report.user_id = reporter.user_id
    if body.text and body.text.strip() and report.text_original is None:
        report.text_original = body.text.strip()
        report.lang_original = body.lang
    if body.location.accuracy_m is not None and (
        report.location_accuracy_m is None or body.location.accuracy_m < report.location_accuracy_m
    ):
        report.location = _point(body.location.lat, body.location.lon)
        report.location_accuracy_m = body.location.accuracy_m
    report.updated_at = now
    sms.merged_at = now
    await session.flush()
    log.info("sms.report_adopted", report_id=str(report.id))
    adopted: uuid.UUID = report.id
    return adopted
