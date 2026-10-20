"""Points engine (FR-A-070, FR-A-071): rules, idempotent awards, daily cap, pause at level disaster, badges.

Every automatic award has a ``dedup_key`` (unique in the ledger and in the queue), so replaying an outbox event,
two worker processes or a staff click repeated never pays twice. Awards for one citizen are serialised by a
transaction-level advisory lock (daily cap and badge thresholds are read-then-write).

Who earns (safety rule T25, docs/api/phase-8-contract.md §3):
* only registered citizens (account kind ``citizen``, active, not erased): anonymous reports, institution accounts
  and the detached owner of anonymised reports earn nothing;
* ``report_verified`` when the report is closed (never received or rejected) and its incident was not closed as
  a false alarm; once per citizen per incident, whatever the number of their reports in it;
* ``accurate_category`` when the category the citizen chose is the incident's verified one (multiplier on the
  verified points, booked as its own row);
* ``report_helped_rescue`` only when a staff member designates the report on the closed intervention;
* ``volunteer_mission`` when a volunteer assignment the operations room created is released after the mission.
"""

import base64
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.config import get_settings
from app.modules.identity.models import DETACHED_ACCOUNT_ID, Account, AccountKind, AccountStatus
from app.modules.ops.models import Assignment, Incident, LevelState, OpLevel
from app.modules.reports.domain import Status
from app.modules.reports.models import Report
from app.modules.rewards.domain import (
    AUTO_CONFIRMED,
    CAPPED_REASONS,
    LEVEL_ORDER,
    BadgeStatus,
    Level,
    Reason,
)
from app.modules.rewards.models import BadgeAward, LedgerEntry, PendingAward, RewardRule

TUNIS_TZ = ZoneInfo("Africa/Tunis")
SYSTEM_ACTOR = "system:rewards"

Outcome = Literal["applied", "queued", "duplicate", "skipped"]


def now_utc() -> datetime:
    return datetime.now(UTC)


def thresholds() -> dict[Level, int]:
    s = get_settings()
    return {
        Level.BRONZE: s.rewards_badge_bronze,
        Level.SILVER: s.rewards_badge_silver,
        Level.GOLD: s.rewards_badge_gold,
        Level.AMBASSADOR: s.rewards_badge_ambassador,
    }


def day_start(at: datetime) -> datetime:
    """Midnight (Africa/Tunis) of the day ``at`` falls in, as an aware datetime."""
    local = at.astimezone(TUNIS_TZ)
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


def year_bounds(year: int) -> tuple[datetime, datetime]:
    return datetime(year, 1, 1, tzinfo=TUNIS_TZ), datetime(year + 1, 1, 1, tzinfo=TUNIS_TZ)


async def lock_citizen(session: AsyncSession, citizen_id: uuid.UUID) -> None:
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": f"ehimaya.rewards.{citizen_id}"}
    )


async def eligible(session: AsyncSession, user_id: uuid.UUID | None) -> bool:
    """Registered, active, not erased citizen: the only accounts that earn points (FR-A-072)."""
    if user_id is None or user_id == DETACHED_ACCOUNT_ID:
        return False
    account = await session.get(Account, user_id)
    return (
        account is not None
        and account.kind is AccountKind.CITIZEN
        and account.status is AccountStatus.ACTIVE
        and account.deleted_at is None
    )


async def disaster_codes(session: AsyncSession) -> list[int]:
    return list(
        await session.scalars(
            select(LevelState.gouvernorat_code)
            .where(LevelState.level == OpLevel.DISASTER)
            .order_by(LevelState.gouvernorat_code)
        )
    )


async def paused_in(session: AsyncSession, gouvernorat_code: int | None) -> bool:
    if gouvernorat_code is None:
        return False
    level = await session.scalar(select(LevelState.level).where(LevelState.gouvernorat_code == gouvernorat_code))
    return level is OpLevel.DISASTER


# ---------------------------------------------------------------- rules


async def rule_for(session: AsyncSession, reason: Reason, category: str | None) -> RewardRule | None:
    """The category override of ``reason`` when there is one, else its default; None when that rule is off."""
    rows = list(
        await session.scalars(
            select(RewardRule).where(
                RewardRule.reason == reason.value,
                (RewardRule.category.is_(None)) | (RewardRule.category == category),
            )
        )
    )
    chosen = next((r for r in rows if r.category is not None), None) or next(
        (r for r in rows if r.category is None), None
    )
    return chosen if chosen is not None and chosen.enabled else None


# ---------------------------------------------------------------- balance and badges


async def balance_of(session: AsyncSession, citizen_id: uuid.UUID) -> int:
    total = await session.scalar(
        select(func.coalesce(func.sum(LedgerEntry.delta), 0)).where(LedgerEntry.citizen_id == citizen_id)
    )
    return int(total or 0)


async def pending_points_of(session: AsyncSession, citizen_id: uuid.UUID) -> int:
    total = await session.scalar(
        select(func.coalesce(func.sum(PendingAward.points), 0)).where(PendingAward.citizen_id == citizen_id)
    )
    return int(total or 0)


async def check_badges(session: AsyncSession, citizen_id: uuid.UUID, now: datetime) -> list[Level]:
    """Award every badge whose threshold the balance reached (once per level). Returns the new ones."""
    balance = await balance_of(session, citizen_id)
    reached = [level for level, points in thresholds().items() if balance >= points]
    created: list[Level] = []
    for level in reached:
        auto = level in AUTO_CONFIRMED
        result = await session.execute(
            insert(BadgeAward)
            .values(
                citizen_id=citizen_id,
                level=level.value,
                status=(BadgeStatus.CONFIRMED if auto else BadgeStatus.PENDING).value,
                balance_at_award=balance,
                awarded_at=now,
                decided_at=now if auto else None,
                decided_by=SYSTEM_ACTOR if auto else None,
            )
            .on_conflict_do_nothing(index_elements=["citizen_id", "level"])
            .returning(BadgeAward.id)
        )
        if result.first() is not None:
            created.append(level)
    return created


def next_badge(balance: int, confirmed: set[Level]) -> tuple[Level, int] | None:
    for level in LEVEL_ORDER:
        points = thresholds()[level]
        if level not in confirmed and balance < points:
            return level, points
    return None


# ---------------------------------------------------------------- awards


@dataclass(frozen=True, slots=True)
class Award:
    citizen_id: uuid.UUID
    reason: Reason
    points: int
    dedup_key: str
    gouvernorat_code: int | None
    report_id: uuid.UUID | None = None
    intervention_id: uuid.UUID | None = None
    rule_id: uuid.UUID | None = None
    multiplier: Decimal | None = None


async def _known(session: AsyncSession, dedup_key: str) -> bool:
    in_ledger = await session.scalar(select(LedgerEntry.id).where(LedgerEntry.dedup_key == dedup_key))
    if in_ledger is not None:
        return True
    return await session.scalar(select(PendingAward.id).where(PendingAward.dedup_key == dedup_key)) is not None


async def _capped_today(session: AsyncSession, citizen_id: uuid.UUID, now: datetime) -> int:
    used = await session.scalar(
        select(func.coalesce(func.sum(LedgerEntry.delta), 0)).where(
            LedgerEntry.citizen_id == citizen_id,
            LedgerEntry.reason.in_([r.value for r in CAPPED_REASONS]),
            LedgerEntry.created_at >= day_start(now),
            LedgerEntry.created_at < day_start(now) + timedelta(days=1),
        )
    )
    return int(used or 0)


async def _apply(session: AsyncSession, award: Award, now: datetime) -> Outcome:
    delta, capped = award.points, False
    if award.reason in CAPPED_REASONS:
        remaining = max(get_settings().rewards_daily_cap - await _capped_today(session, award.citizen_id, now), 0)
        if delta > remaining:
            delta, capped = remaining, True
    result = await session.execute(
        insert(LedgerEntry)
        .values(
            citizen_id=award.citizen_id,
            delta=delta,
            reason=award.reason.value,
            report_id=award.report_id,
            intervention_id=award.intervention_id,
            rule_id=award.rule_id,
            multiplier=award.multiplier,
            capped=capped,
            dedup_key=award.dedup_key,
            created_at=now,
        )
        .on_conflict_do_nothing(index_elements=["dedup_key"])
        .returning(LedgerEntry.id)
    )
    if result.first() is None:
        return "duplicate"
    if delta > 0:
        await check_badges(session, award.citizen_id, now)
    return "applied"


async def grant(session: AsyncSession, award: Award, now: datetime | None = None) -> Outcome:
    """Book an automatic award, or queue it while its gouvernorat is at level disaster. Idempotent."""
    now = now or now_utc()
    await lock_citizen(session, award.citizen_id)
    if await _known(session, award.dedup_key):
        return "duplicate"
    if await paused_in(session, award.gouvernorat_code):
        await session.execute(
            insert(PendingAward)
            .values(
                citizen_id=award.citizen_id,
                reason=award.reason.value,
                points=award.points,
                report_id=award.report_id,
                intervention_id=award.intervention_id,
                rule_id=award.rule_id,
                multiplier=award.multiplier,
                dedup_key=award.dedup_key,
                gouvernorat_code=award.gouvernorat_code,
                queued_at=now,
            )
            .on_conflict_do_nothing(index_elements=["dedup_key"])
        )
        return "queued"
    return await _apply(session, award, now)


async def release_pending(session: AsyncSession, now: datetime | None = None, batch: int = 200) -> int:
    """Apply awards queued in gouvernorats no longer at level disaster (the caller commits). Returns how many."""
    now = now or now_utc()
    paused = await disaster_codes(session)
    query = select(PendingAward).order_by(PendingAward.id).limit(batch).with_for_update(skip_locked=True)
    if paused:
        query = query.where(PendingAward.gouvernorat_code.is_(None) | PendingAward.gouvernorat_code.not_in(paused))
    rows = list(await session.scalars(query))
    for row in rows:
        await session.delete(row)
        await session.flush()
        if not await eligible(session, row.citizen_id):
            continue
        await lock_citizen(session, row.citizen_id)
        await _apply(
            session,
            Award(
                citizen_id=row.citizen_id,
                reason=Reason(row.reason),
                points=row.points,
                dedup_key=row.dedup_key,
                gouvernorat_code=row.gouvernorat_code,
                report_id=row.report_id,
                intervention_id=row.intervention_id,
                rule_id=row.rule_id,
                multiplier=row.multiplier,
            ),
            now,
        )
    return len(rows)


def _false_alarm(incident: Incident | None) -> bool:
    return incident is not None and (incident.evaluation or {}).get("outcome") == "false_alarm"


async def award_report(session: AsyncSession, report_id: uuid.UUID, now: datetime | None = None) -> list[Outcome]:
    """``report_verified`` (and ``accurate_category``) for a closed report. Safe to call any number of times."""
    report = await session.get(Report, report_id)
    if report is None or report.status != Status.CLOSED.value or report.anonymised_at is not None:
        return []
    if not await eligible(session, report.user_id):
        return []
    incident = await session.get(Incident, report.incident_id) if report.incident_id else None
    if _false_alarm(incident):
        return []
    rule = await rule_for(session, Reason.REPORT_VERIFIED, report.category)
    if rule is None or not rule.points:
        return []
    # Once per citizen per incident: later reports of the same person in the same incident earn nothing more.
    scope = f"incident:{incident.id}" if incident is not None else f"report:{report.id}"
    gouvernorat = report.gouvernorat_code or (incident.gouvernorat_code if incident else None)
    outcomes = [
        await grant(
            session,
            Award(
                citizen_id=report.user_id,
                reason=Reason.REPORT_VERIFIED,
                points=rule.points,
                dedup_key=f"report_verified:{report.user_id}:{scope}",
                gouvernorat_code=gouvernorat,
                report_id=report.id,
                intervention_id=incident.id if incident else None,
                rule_id=rule.id,
            ),
            now,
        )
    ]
    # The verified category is the incident's (set by the operations room); "other" is not a choice to reward.
    if incident is not None and report.category == incident.category and report.category != "other":
        accurate = await rule_for(session, Reason.ACCURATE_CATEGORY, report.category)
        if accurate is not None and accurate.multiplier is not None:
            bonus = int((Decimal(rule.points) * (accurate.multiplier - 1)).to_integral_value())
            if bonus > 0:
                outcomes.append(
                    await grant(
                        session,
                        Award(
                            citizen_id=report.user_id,
                            reason=Reason.ACCURATE_CATEGORY,
                            points=bonus,
                            dedup_key=f"accurate_category:{report.user_id}:{scope}",
                            gouvernorat_code=gouvernorat,
                            report_id=report.id,
                            intervention_id=incident.id,
                            rule_id=accurate.id,
                            multiplier=accurate.multiplier,
                        ),
                        now,
                    )
                )
    return outcomes


async def award_mission(session: AsyncSession, assignment_id: uuid.UUID, now: datetime | None = None) -> Outcome:
    """``volunteer_mission`` once a volunteer assignment (created by a call-out) is released after the mission."""
    assignment = await session.get(Assignment, assignment_id)
    if (
        assignment is None
        or assignment.kind != "volunteer"
        or assignment.status != "released"
        or assignment.on_scene_at is None
        or assignment.volunteer_id is None
    ):
        return "skipped"
    if not await eligible(session, assignment.volunteer_id):
        return "skipped"
    incident = await session.get(Incident, assignment.incident_id)
    if incident is None or _false_alarm(incident):
        return "skipped"
    rule = await rule_for(session, Reason.VOLUNTEER_MISSION, incident.category)
    if rule is None or not rule.points:
        return "skipped"
    return await grant(
        session,
        Award(
            citizen_id=assignment.volunteer_id,
            reason=Reason.VOLUNTEER_MISSION,
            points=rule.points,
            dedup_key=f"volunteer_mission:{assignment.volunteer_id}:incident:{incident.id}",
            gouvernorat_code=incident.gouvernorat_code,
            intervention_id=incident.id,
            rule_id=rule.id,
        ),
        now,
    )


async def award_rescue(
    session: AsyncSession, incident: Incident, report_id: uuid.UUID, now: datetime | None = None
) -> tuple[Outcome, str | None]:
    """``report_helped_rescue`` for a report a staff member designated on the evaluated intervention."""
    report = await session.get(Report, report_id)
    if report is None or report.incident_id != incident.id:
        return "skipped", "not_in_incident"
    if report.status != Status.CLOSED.value:
        return "skipped", "report_not_closed"
    if not await eligible(session, report.user_id):
        return "skipped", "not_eligible"
    rule = await rule_for(session, Reason.REPORT_HELPED_RESCUE, report.category)
    if rule is None or not rule.points:
        return "skipped", "rule_disabled"
    outcome = await grant(
        session,
        Award(
            citizen_id=report.user_id,
            reason=Reason.REPORT_HELPED_RESCUE,
            points=rule.points,
            dedup_key=f"report_helped_rescue:{report.user_id}:incident:{incident.id}",
            gouvernorat_code=report.gouvernorat_code or incident.gouvernorat_code,
            report_id=report.id,
            intervention_id=incident.id,
            rule_id=rule.id,
        ),
        now,
    )
    return outcome, None


# ---------------------------------------------------------------- cursors


def encode_cursor(*parts: object) -> str:
    raw = "|".join(p.isoformat() if isinstance(p, datetime) else str(p) for p in parts)
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str, count: int) -> list[str]:
    try:
        parts = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode().split("|")
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_cursor") from exc
    if len(parts) != count:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_cursor")
    return parts


def ledger_cursor(cursor: str | None) -> int | None:
    if cursor is None:
        return None
    (value,) = decode_cursor(cursor, 1)
    try:
        return int(value)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_cursor") from exc


async def ledger_page(
    session: AsyncSession, citizen_id: uuid.UUID, limit: int, cursor: str | None
) -> tuple[list[tuple[LedgerEntry, str | None, bool]], str | None]:
    """Newest first: (entry, tracking code of its report, revoked by a later row)."""
    revocation = aliased(LedgerEntry)
    query = (
        select(LedgerEntry, Report.tracking_code, revocation.id)
        .outerjoin(Report, Report.id == LedgerEntry.report_id)
        .outerjoin(revocation, revocation.revokes_id == LedgerEntry.id)
        .where(LedgerEntry.citizen_id == citizen_id)
    )
    before = ledger_cursor(cursor)
    if before is not None:
        query = query.where(LedgerEntry.id < before)
    rows = (await session.execute(query.order_by(LedgerEntry.id.desc()).limit(limit))).all()
    items: list[tuple[LedgerEntry, str | None, bool]] = [
        (entry, code, revoked is not None) for entry, code, revoked in rows
    ]
    next_cursor = encode_cursor(rows[-1][0].id) if len(rows) == limit else None
    return items, next_cursor
