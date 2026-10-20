"""Dashboard endpoints of the rewards module (FR-A-070, FR-A-071, FR-C-20; docs/api/phase-8-contract.md §3).

Humans award: points follow the configured rules automatically, but badges above bronze, nominations and
certificates are decided by a staff member, every decision is audited and can be revoked with a reason.
Citizens are shown under a pseudonym; names and phone appear only on request (``with_contact``, audited) for the
roles that already read reporters' identity on reports. Scope: a citizen belongs to the gouvernorat of their
profile, a nomination and a certificate to their subject's; national roles see all.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service as audit
from app.modules.identity.models import Profile
from app.modules.ops import service as incidents
from app.modules.ops.models import Incident
from app.modules.orgs.models import Organization
from app.modules.reports.models import Report
from app.modules.reports.staff_router import READ_ROLES, WRITE_ROLES
from app.modules.rewards import certificates, schemas, service
from app.modules.rewards.domain import LEVEL_ORDER, SUBJECT_OF, BadgeStatus, Level, Reason, pseudonym
from app.modules.rewards.models import (
    BadgeAward,
    LedgerEntry,
    Nomination,
    PendingAward,
    RewardCertificate,
    RewardRule,
)
from app.modules.rewards.router import history_item, pdf_response
from app.modules.volunteers.models import Volunteer

router = APIRouter(prefix="/api/v1/staff/rewards", tags=["staff", "rewards"])
Session = Annotated[AsyncSession, Depends(get_session)]

MANAGE_ROLES = (Role.OPS_MANAGER, Role.LOCAL_COMMITTEE, Role.CENTRAL_COMMITTEE)
RULE_ROLES = (Role.CENTRAL_COMMITTEE, Role.SYSADMIN)
Reader = Annotated[Principal, Depends(require_roles(*READ_ROLES))]
SettingsReader = Annotated[Principal, Depends(require_roles(*READ_ROLES, Role.SYSADMIN))]
Manager = Annotated[Principal, Depends(require_roles(*MANAGE_ROLES))]
RuleAdmin = Annotated[Principal, Depends(require_roles(*RULE_ROLES))]
RescueWriter = Annotated[Principal, Depends(require_roles(*WRITE_ROLES))]
LEADERBOARD_SIZE = 50


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "not_found")


def _in_scope(principal: Principal, gouvernorat_code: int | None) -> bool:
    return principal.is_national or (gouvernorat_code is not None and gouvernorat_code == principal.gouvernorat_code)


def _scope(principal: Principal, column: Any) -> Any:
    return True if principal.is_national else column == principal.gouvernorat_code


def _actor(principal: Principal) -> str:
    return audit.actor_of(principal)


# ---------------------------------------------------------------- settings and rules


@router.get("/settings", response_model=schemas.SettingsOut)
async def get_rewards_settings(principal: SettingsReader, session: Session) -> schemas.SettingsOut:
    levels = service.thresholds()
    return schemas.SettingsOut(
        daily_cap=get_settings().rewards_daily_cap,
        thresholds=schemas.Thresholds(**{level.value: points for level, points in levels.items()}),
        paused_gouvernorats=await service.disaster_codes(session),
    )


def _rule_out(rule: RewardRule) -> schemas.RuleOut:
    return schemas.RuleOut(
        id=rule.id,
        reason=rule.reason,
        category=rule.category,
        points=rule.points,
        multiplier=float(rule.multiplier) if rule.multiplier is not None else None,
        enabled=rule.enabled,
        is_default=rule.is_default,
        description=rule.description,
        updated_at=rule.updated_at,
        updated_by=rule.updated_by,
    )


def _rule_snapshot(rule: RewardRule) -> dict[str, Any]:
    return {
        "reason": rule.reason,
        "category": rule.category,
        "points": rule.points,
        "multiplier": float(rule.multiplier) if rule.multiplier is not None else None,
        "enabled": rule.enabled,
    }


def _national(principal: Principal) -> None:
    if not principal.is_national:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "national_scope_required")


@router.get("/rules", response_model=list[schemas.RuleOut])
async def list_rules(principal: SettingsReader, session: Session) -> list[schemas.RuleOut]:
    rows = await session.scalars(
        select(RewardRule).order_by(RewardRule.reason, RewardRule.category.nulls_first(), RewardRule.id)
    )
    return [_rule_out(r) for r in rows]


@router.post("/rules", response_model=schemas.RuleOut, status_code=status.HTTP_201_CREATED)
async def create_rule(principal: RuleAdmin, session: Session, body: schemas.RuleIn) -> schemas.RuleOut:
    _national(principal)
    exists = await session.scalar(
        select(RewardRule.id).where(RewardRule.reason == body.reason, RewardRule.category == body.category.value)
    )
    if exists is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "rule_exists")
    rule = RewardRule(
        reason=body.reason,
        category=body.category.value,
        points=body.points if body.reason != "accurate_category" else None,
        multiplier=Decimal(str(body.multiplier)) if body.reason == "accurate_category" else None,
        enabled=body.enabled,
        is_default=False,
        description={},
        updated_at=service.now_utc(),
        updated_by=audit.name_of(principal) or _actor(principal),
    )
    session.add(rule)
    await session.flush()
    await audit.record(
        session,
        actor=_actor(principal),
        action="rewards.rule.create",
        target=f"reward_rule:{rule.id}",
        details=_rule_snapshot(rule),
    )
    await session.commit()
    await session.refresh(rule)
    return _rule_out(rule)


async def _rule(session: AsyncSession, rule_id: uuid.UUID) -> RewardRule:
    rule = await session.get(RewardRule, rule_id, with_for_update=True)
    if rule is None:
        raise _not_found()
    return rule


@router.patch("/rules/{rule_id}", response_model=schemas.RuleOut)
async def update_rule(
    principal: RuleAdmin, session: Session, rule_id: uuid.UUID, body: schemas.RulePatch
) -> schemas.RuleOut:
    _national(principal)
    rule = await _rule(session, rule_id)
    before = _rule_snapshot(rule)
    fields = body.model_fields_set
    if "points" in fields:
        if rule.reason == Reason.ACCURATE_CATEGORY.value or body.points is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_rule")
        rule.points = body.points
    if "multiplier" in fields:
        if rule.reason != Reason.ACCURATE_CATEGORY.value or body.multiplier is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_rule")
        rule.multiplier = Decimal(str(body.multiplier))
    if "enabled" in fields and body.enabled is not None:
        rule.enabled = body.enabled
    rule.updated_at = service.now_utc()
    rule.updated_by = audit.name_of(principal) or _actor(principal)
    await audit.record(
        session,
        actor=_actor(principal),
        action="rewards.rule.update",
        target=f"reward_rule:{rule.id}",
        details={"from": before, "to": _rule_snapshot(rule)},
    )
    await session.commit()
    await session.refresh(rule)
    return _rule_out(rule)


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(principal: RuleAdmin, session: Session, rule_id: uuid.UUID) -> Response:
    _national(principal)
    rule = await _rule(session, rule_id)
    if rule.is_default:
        raise HTTPException(status.HTTP_409_CONFLICT, "default_rule")
    await audit.record(
        session,
        actor=_actor(principal),
        action="rewards.rule.delete",
        target=f"reward_rule:{rule.id}",
        details=_rule_snapshot(rule),
    )
    await session.delete(rule)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- citizens and ledger


_BALANCE = (
    select(LedgerEntry.citizen_id, func.sum(LedgerEntry.delta).label("balance"))
    .group_by(LedgerEntry.citizen_id)
    .subquery()
)
_PENDING = (
    select(PendingAward.citizen_id, func.sum(PendingAward.points).label("pending"))
    .group_by(PendingAward.citizen_id)
    .subquery()
)


async def _confirmed_levels(session: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, list[Level]]:
    out: dict[uuid.UUID, list[Level]] = {i: [] for i in ids}
    if ids:
        rows = await session.execute(
            select(BadgeAward.citizen_id, BadgeAward.level).where(
                BadgeAward.citizen_id.in_(ids), BadgeAward.status == BadgeStatus.CONFIRMED.value
            )
        )
        for citizen_id, level in rows.all():
            out[citizen_id].append(Level(level))
    for levels in out.values():
        levels.sort(key=LEVEL_ORDER.index)
    return out


def _contact(profile: Profile | None) -> schemas.Contact | None:
    if profile is None:
        return None
    return schemas.Contact(first_name=profile.first_name, last_name=profile.last_name, phone=profile.phone)


async def _audit_contact(session: AsyncSession, principal: Principal, ids: list[uuid.UUID]) -> None:
    await audit.record(
        session,
        actor=_actor(principal),
        action="rewards.citizens.contact",
        details={"citizens": [str(i) for i in ids][:200]},
    )


@router.get("/citizens", response_model=schemas.CitizenPage)
async def list_citizens(
    principal: Reader,
    session: Session,
    gouvernorat: int | None = None,
    with_contact: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: str | None = None,
) -> schemas.CitizenPage:
    """Citizens holding points, a queued award or a badge, ordered by id (pseudonyms unless ``with_contact``)."""
    holders = (
        select(LedgerEntry.citizen_id.label("citizen_id"))
        .union(select(PendingAward.citizen_id), select(BadgeAward.citizen_id))
        .subquery()
    )
    query = (
        select(holders.c.citizen_id, Profile, _BALANCE.c.balance, _PENDING.c.pending)
        .outerjoin(Profile, Profile.user_id == holders.c.citizen_id)
        .outerjoin(_BALANCE, _BALANCE.c.citizen_id == holders.c.citizen_id)
        .outerjoin(_PENDING, _PENDING.c.citizen_id == holders.c.citizen_id)
        .where(_scope(principal, Profile.gouvernorat_code))
    )
    if gouvernorat is not None:
        query = query.where(Profile.gouvernorat_code == gouvernorat)
    if cursor:
        (after,) = service.decode_cursor(cursor, 1)
        try:
            query = query.where(holders.c.citizen_id > uuid.UUID(after))
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_cursor") from exc
    rows = (await session.execute(query.order_by(holders.c.citizen_id).limit(limit))).all()
    ids = [r[0] for r in rows]
    levels = await _confirmed_levels(session, ids)
    items = [
        schemas.CitizenItem(
            citizen_id=citizen_id,
            pseudonym=pseudonym(citizen_id),
            gouvernorat_code=profile.gouvernorat_code if profile else None,
            balance=int(balance or 0),
            pending_points=int(pending or 0),
            badges=levels[citizen_id],
            contact=_contact(profile) if with_contact else None,
        )
        for citizen_id, profile, balance, pending in rows
    ]
    if with_contact and ids:
        await _audit_contact(session, principal, ids)
        await session.commit()
    return schemas.CitizenPage(items=items, next_cursor=service.encode_cursor(ids[-1]) if len(rows) == limit else None)


async def _citizen_in_scope(session: AsyncSession, principal: Principal, citizen_id: uuid.UUID) -> Profile | None:
    profile = await session.get(Profile, citizen_id)
    if not _in_scope(principal, profile.gouvernorat_code if profile else None):
        raise _not_found()
    return profile


async def _citizen_detail(
    session: AsyncSession, principal: Principal, citizen_id: uuid.UUID, with_contact: bool
) -> schemas.CitizenDetail:
    profile = await _citizen_in_scope(session, principal, citizen_id)
    rows, _ = await service.ledger_page(session, citizen_id, 200, None)
    return schemas.CitizenDetail(
        citizen_id=citizen_id,
        pseudonym=pseudonym(citizen_id),
        gouvernorat_code=profile.gouvernorat_code if profile else None,
        balance=await service.balance_of(session, citizen_id),
        pending_points=await service.pending_points_of(session, citizen_id),
        badges=(await _confirmed_levels(session, [citizen_id]))[citizen_id],
        contact=_contact(profile) if with_contact else None,
        history=[
            schemas.StaffHistoryItem(
                **history_item(entry, code).model_dump(), created_by=entry.created_by, note=entry.note, revoked=revoked
            )
            for entry, code, revoked in rows
        ],
    )


@router.get("/citizens/{citizen_id}", response_model=schemas.CitizenDetail)
async def get_citizen(
    principal: Reader, session: Session, citizen_id: uuid.UUID, with_contact: bool = False
) -> schemas.CitizenDetail:
    detail = await _citizen_detail(session, principal, citizen_id, with_contact)
    if with_contact:
        await _audit_contact(session, principal, [citizen_id])
        await session.commit()
    return detail


@router.post("/citizens/{citizen_id}/adjust", response_model=schemas.CitizenDetail)
async def adjust(
    principal: Manager, session: Session, citizen_id: uuid.UUID, body: schemas.AdjustIn
) -> schemas.CitizenDetail:
    await _citizen_in_scope(session, principal, citizen_id)
    if not await service.eligible(session, citizen_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "not_eligible")
    await service.lock_citizen(session, citizen_id)
    now = service.now_utc()
    entry = LedgerEntry(
        citizen_id=citizen_id,
        delta=body.delta,
        reason=Reason.MANUAL.value,
        note=body.reason,
        created_by=_actor(principal),
        created_at=now,
    )
    session.add(entry)
    await session.flush()
    if body.delta > 0:
        await service.check_badges(session, citizen_id, now)
    await audit.record(
        session,
        actor=_actor(principal),
        action="rewards.adjust",
        target=f"citizen:{citizen_id}",
        reason=body.reason,
        details={"delta": body.delta, "ledger_id": entry.id},
    )
    await session.commit()
    return await _citizen_detail(session, principal, citizen_id, False)


@router.post("/ledger/{entry_id}/revoke", response_model=schemas.CitizenDetail)
async def revoke_entry(
    principal: Manager, session: Session, entry_id: int, body: schemas.ReasonIn
) -> schemas.CitizenDetail:
    entry = await session.get(LedgerEntry, entry_id)
    if entry is None:
        raise _not_found()
    await _citizen_in_scope(session, principal, entry.citizen_id)
    await service.lock_citizen(session, entry.citizen_id)
    if entry.reason == Reason.REVOCATION.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    if await session.scalar(select(LedgerEntry.id).where(LedgerEntry.revokes_id == entry.id)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "already_revoked")
    if entry.delta == 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "nothing_to_revoke")
    revocation = LedgerEntry(
        citizen_id=entry.citizen_id,
        delta=-entry.delta,
        reason=Reason.REVOCATION.value,
        report_id=entry.report_id,
        intervention_id=entry.intervention_id,
        revokes_id=entry.id,
        note=body.reason,
        created_by=_actor(principal),
        created_at=service.now_utc(),
    )
    session.add(revocation)
    await session.flush()
    await audit.record(
        session,
        actor=_actor(principal),
        action="rewards.ledger.revoke",
        target=f"citizen:{entry.citizen_id}",
        reason=body.reason,
        details={"ledger_id": entry.id, "delta": -entry.delta, "original_reason": entry.reason},
    )
    await session.commit()
    return await _citizen_detail(session, principal, entry.citizen_id, False)


# ---------------------------------------------------------------- badges


def _badge_item(badge: BadgeAward, balance: int | None) -> schemas.BadgeItem:
    return schemas.BadgeItem(
        id=badge.id,
        citizen_id=badge.citizen_id,
        pseudonym=pseudonym(badge.citizen_id),
        level=Level(badge.level),
        status=badge.status,
        balance=int(balance or 0),
        awarded_at=badge.awarded_at,
        decided_at=badge.decided_at,
        decided_by=badge.decided_by,
        reason=badge.reason,
    )


@router.get("/badges", response_model=schemas.BadgePage)
async def list_badges(
    principal: Reader,
    session: Session,
    status_: Annotated[schemas.BadgeStatusName | None, Query(alias="status")] = None,
    level: Level | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: str | None = None,
) -> schemas.BadgePage:
    query = (
        select(BadgeAward, _BALANCE.c.balance)
        .outerjoin(Profile, Profile.user_id == BadgeAward.citizen_id)
        .outerjoin(_BALANCE, _BALANCE.c.citizen_id == BadgeAward.citizen_id)
        .where(_scope(principal, Profile.gouvernorat_code))
    )
    if status_ is not None:
        query = query.where(BadgeAward.status == status_)
    if level is not None:
        query = query.where(BadgeAward.level == level.value)
    if cursor:
        at, rid = service.decode_cursor(cursor, 2)
        try:
            last_at, last_id = datetime.fromisoformat(at), uuid.UUID(rid)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_cursor") from exc
        query = query.where(
            or_(BadgeAward.awarded_at > last_at, and_(BadgeAward.awarded_at == last_at, BadgeAward.id > last_id))
        )
    rows = (await session.execute(query.order_by(BadgeAward.awarded_at, BadgeAward.id).limit(limit))).all()
    next_cursor = service.encode_cursor(rows[-1][0].awarded_at, rows[-1][0].id) if len(rows) == limit else None
    return schemas.BadgePage(items=[_badge_item(b, bal) for b, bal in rows], next_cursor=next_cursor)


async def _badge(session: AsyncSession, principal: Principal, badge_id: uuid.UUID) -> BadgeAward:
    badge = await session.get(BadgeAward, badge_id, with_for_update=True)
    if badge is None:
        raise _not_found()
    await _citizen_in_scope(session, principal, badge.citizen_id)
    return badge


_BADGE_ACTIONS = {
    BadgeStatus.CONFIRMED: "rewards.badge.confirm",
    BadgeStatus.REJECTED: "rewards.badge.reject",
    BadgeStatus.REVOKED: "rewards.badge.revoke",
}


async def _decide_badge(
    session: AsyncSession, principal: Principal, badge: BadgeAward, target: BadgeStatus, reason: str | None
) -> schemas.BadgeItem:
    allowed = {
        BadgeStatus.CONFIRMED: {BadgeStatus.PENDING},
        BadgeStatus.REJECTED: {BadgeStatus.PENDING},
        BadgeStatus.REVOKED: {BadgeStatus.PENDING, BadgeStatus.CONFIRMED},
    }[target]
    if BadgeStatus(badge.status) not in allowed:
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    previous = badge.status
    badge.status, badge.decided_at, badge.decided_by, badge.reason = (
        target.value,
        service.now_utc(),
        _actor(principal),
        reason,
    )
    if target is BadgeStatus.REVOKED:
        cert = await session.scalar(
            select(RewardCertificate).where(
                RewardCertificate.badge_award_id == badge.id, RewardCertificate.revoked_at.is_(None)
            )
        )
        if cert is not None:
            certificates.revoke(cert, _actor(principal), reason or "badge_revoked")
    await audit.record(
        session,
        actor=_actor(principal),
        action=_BADGE_ACTIONS[target],
        target=f"reward_badge:{badge.id}",
        reason=reason,
        details={"from": previous, "to": target.value, "level": badge.level, "citizen": str(badge.citizen_id)},
    )
    await session.commit()
    return _badge_item(badge, await service.balance_of(session, badge.citizen_id))


@router.post("/badges/{badge_id}/confirm", response_model=schemas.BadgeItem)
async def confirm_badge(principal: Manager, session: Session, badge_id: uuid.UUID) -> schemas.BadgeItem:
    badge = await _badge(session, principal, badge_id)
    return await _decide_badge(session, principal, badge, BadgeStatus.CONFIRMED, None)


@router.post("/badges/{badge_id}/reject", response_model=schemas.BadgeItem)
async def reject_badge(
    principal: Manager, session: Session, badge_id: uuid.UUID, body: schemas.ReasonIn
) -> schemas.BadgeItem:
    badge = await _badge(session, principal, badge_id)
    return await _decide_badge(session, principal, badge, BadgeStatus.REJECTED, body.reason)


@router.post("/badges/{badge_id}/revoke", response_model=schemas.BadgeItem)
async def revoke_badge(
    principal: Manager, session: Session, badge_id: uuid.UUID, body: schemas.ReasonIn
) -> schemas.BadgeItem:
    badge = await _badge(session, principal, badge_id)
    return await _decide_badge(session, principal, badge, BadgeStatus.REVOKED, body.reason)


# ---------------------------------------------------------------- nominations


async def _subject_label(session: AsyncSession, subject_kind: str, subject_id: uuid.UUID | None) -> str | None:
    if subject_id is None:
        return None
    if subject_kind == "org":
        org = await session.get(Organization, subject_id)
        return org.name if org else None
    return pseudonym(subject_id)


async def _nomination_out(session: AsyncSession, n: Nomination) -> schemas.NominationOut:
    return schemas.NominationOut(
        id=n.id,
        kind=n.kind,
        subject_kind=n.subject_kind,
        subject_id=n.subject_id,
        subject_label=await _subject_label(session, n.subject_kind, n.subject_id),
        gouvernorat_code=n.gouvernorat_code,
        year=n.year,
        reason=n.reason,
        evidence=schemas.Evidence.model_validate(n.evidence),
        status=n.status,
        proposed_by=n.proposed_by,
        decided_by=n.decided_by,
        decided_at=n.decided_at,
        decision_reason=n.decision_reason,
        created_at=n.created_at,
    )


async def _subject_gouvernorat(session: AsyncSession, kind: str, subject_id: uuid.UUID) -> int | None:
    """Gouvernorat of a nomination's subject; 404 subject_not_found when it is not a valid subject."""
    if kind == "org":
        org = await session.get(Organization, subject_id)
        if org is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "subject_not_found")
        return org.gouvernorat_code
    if not await service.eligible(session, subject_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "subject_not_found")
    if kind == "volunteer":
        volunteer = await session.get(Volunteer, subject_id)
        if volunteer is None or volunteer.status not in ("approved", "suspended"):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "subject_not_found")
    profile = await session.get(Profile, subject_id)
    return profile.gouvernorat_code if profile else None


async def _check_evidence(session: AsyncSession, evidence: schemas.Evidence) -> None:
    if evidence.report_ids:
        found = await session.scalar(select(func.count()).where(Report.id.in_(evidence.report_ids)))
        if found != len(set(evidence.report_ids)):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_evidence")
    if evidence.intervention_ids:
        found = await session.scalar(select(func.count()).where(Incident.id.in_(evidence.intervention_ids)))
        if found != len(set(evidence.intervention_ids)):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_evidence")


@router.get("/nominations", response_model=schemas.NominationPage)
async def list_nominations(
    principal: Reader,
    session: Session,
    status_: Annotated[schemas.NominationStatus | None, Query(alias="status")] = None,
    kind: str | None = None,
    year: int | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: str | None = None,
) -> schemas.NominationPage:
    query = select(Nomination).where(_scope(principal, Nomination.gouvernorat_code))
    if status_ is not None:
        query = query.where(Nomination.status == status_)
    if kind is not None:
        query = query.where(Nomination.kind == kind)
    if year is not None:
        query = query.where(Nomination.year == year)
    if cursor:
        at, rid = service.decode_cursor(cursor, 2)
        try:
            last_at, last_id = datetime.fromisoformat(at), uuid.UUID(rid)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_cursor") from exc
        query = query.where(
            or_(Nomination.created_at < last_at, and_(Nomination.created_at == last_at, Nomination.id < last_id))
        )
    rows = list(await session.scalars(query.order_by(Nomination.created_at.desc(), Nomination.id.desc()).limit(limit)))
    next_cursor = service.encode_cursor(rows[-1].created_at, rows[-1].id) if len(rows) == limit else None
    return schemas.NominationPage(items=[await _nomination_out(session, n) for n in rows], next_cursor=next_cursor)


@router.post("/nominations", response_model=schemas.NominationOut, status_code=status.HTTP_201_CREATED)
async def create_nomination(principal: Manager, session: Session, body: schemas.NominationIn) -> schemas.NominationOut:
    if SUBJECT_OF[body.kind] != body.subject_kind:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_subject")
    gouvernorat = await _subject_gouvernorat(session, body.subject_kind, body.subject_id)
    if not _in_scope(principal, gouvernorat):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "subject_not_found")
    await _check_evidence(session, body.evidence)
    duplicate = await session.scalar(
        select(Nomination.id).where(
            Nomination.kind == body.kind.value,
            Nomination.subject_id == body.subject_id,
            Nomination.year == body.year,
            Nomination.status != "rejected",
        )
    )
    if duplicate is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "duplicate_nomination")
    now = service.now_utc()
    nomination = Nomination(
        kind=body.kind.value,
        subject_kind=body.subject_kind,
        subject_id=body.subject_id,
        gouvernorat_code=gouvernorat,
        year=body.year,
        reason=body.reason,
        evidence=body.evidence.model_dump(mode="json"),
        status="proposed",
        proposed_by=_actor(principal),
        created_at=now,
        updated_at=now,
    )
    session.add(nomination)
    await session.flush()
    await audit.record(
        session,
        actor=_actor(principal),
        action="rewards.nomination.create",
        target=f"nomination:{nomination.id}",
        reason=body.reason,
        details={"kind": nomination.kind, "subject_kind": body.subject_kind, "year": body.year},
    )
    await session.commit()
    await session.refresh(nomination)
    return await _nomination_out(session, nomination)


async def _nomination(
    session: AsyncSession, principal: Principal, nomination_id: uuid.UUID, lock: bool = False
) -> Nomination:
    nomination = await session.get(Nomination, nomination_id, with_for_update=lock)
    if nomination is None or not _in_scope(principal, nomination.gouvernorat_code):
        raise _not_found()
    return nomination


@router.get("/nominations/{nomination_id}", response_model=schemas.NominationOut)
async def get_nomination(principal: Reader, session: Session, nomination_id: uuid.UUID) -> schemas.NominationOut:
    return await _nomination_out(session, await _nomination(session, principal, nomination_id))


@router.patch("/nominations/{nomination_id}", response_model=schemas.NominationOut)
async def update_nomination(
    principal: Manager, session: Session, nomination_id: uuid.UUID, body: schemas.NominationPatch
) -> schemas.NominationOut:
    nomination = await _nomination(session, principal, nomination_id, lock=True)
    if nomination.status != "proposed":
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    if body.reason is not None:
        nomination.reason = body.reason
    if body.evidence is not None:
        await _check_evidence(session, body.evidence)
        nomination.evidence = body.evidence.model_dump(mode="json")
    nomination.updated_at = service.now_utc()
    await audit.record(
        session,
        actor=_actor(principal),
        action="rewards.nomination.update",
        target=f"nomination:{nomination.id}",
        details={"fields": sorted(body.model_fields_set)},
    )
    await session.commit()
    await session.refresh(nomination)
    return await _nomination_out(session, nomination)


@router.delete("/nominations/{nomination_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_nomination(principal: Manager, session: Session, nomination_id: uuid.UUID) -> Response:
    nomination = await _nomination(session, principal, nomination_id, lock=True)
    if nomination.status != "proposed":
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    await audit.record(
        session,
        actor=_actor(principal),
        action="rewards.nomination.delete",
        target=f"nomination:{nomination.id}",
        details={"kind": nomination.kind, "year": nomination.year},
    )
    await session.delete(nomination)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _decide_nomination(
    session: AsyncSession,
    principal: Principal,
    nomination_id: uuid.UUID,
    decision: Literal["approved", "rejected"],
    reason: str | None,
) -> schemas.NominationOut:
    nomination = await _nomination(session, principal, nomination_id, lock=True)
    if nomination.status != "proposed":
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    actor = _actor(principal)
    # Four eyes: the staff member who proposed does not decide.
    if nomination.proposed_by == actor:
        raise HTTPException(status.HTTP_409_CONFLICT, "same_reviewer")
    now = service.now_utc()
    nomination.status, nomination.decided_by, nomination.decided_at = decision, actor, now
    nomination.decision_reason, nomination.updated_at = reason, now
    await audit.record(
        session,
        actor=actor,
        action=f"rewards.nomination.{'approve' if decision == 'approved' else 'reject'}",
        target=f"nomination:{nomination.id}",
        reason=reason,
        details={"kind": nomination.kind, "year": nomination.year},
    )
    await session.commit()
    await session.refresh(nomination)
    return await _nomination_out(session, nomination)


@router.post("/nominations/{nomination_id}/approve", response_model=schemas.NominationOut)
async def approve_nomination(
    principal: Manager, session: Session, nomination_id: uuid.UUID, body: schemas.OptionalReasonIn | None = None
) -> schemas.NominationOut:
    return await _decide_nomination(session, principal, nomination_id, "approved", body.reason if body else None)


@router.post("/nominations/{nomination_id}/reject", response_model=schemas.NominationOut)
async def reject_nomination(
    principal: Manager, session: Session, nomination_id: uuid.UUID, body: schemas.ReasonIn
) -> schemas.NominationOut:
    return await _decide_nomination(session, principal, nomination_id, "rejected", body.reason)


# ---------------------------------------------------------------- certificates


async def _certificate_out(session: AsyncSession, cert: RewardCertificate) -> schemas.CertificateOut:
    return schemas.CertificateOut(
        id=cert.id,
        code=cert.code,
        kind=cert.kind,
        distinction=cert.distinction,
        subject_label=await _subject_label(session, cert.subject_kind, cert.subject_id),
        initials=cert.initials,
        year=cert.year,
        issued_at=cert.issued_at,
        issued_by=cert.issued_by,
        revoked_at=cert.revoked_at,
        revoked_reason=cert.revoked_reason,
        verify_url=certificates.verify_url(cert.code),
    )


@router.get("/certificates", response_model=schemas.CertificatePage)
async def list_certificates(
    principal: Reader,
    session: Session,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: str | None = None,
) -> schemas.CertificatePage:
    query = select(RewardCertificate).where(_scope(principal, RewardCertificate.gouvernorat_code))
    if cursor:
        at, rid = service.decode_cursor(cursor, 2)
        try:
            last_at, last_id = datetime.fromisoformat(at), uuid.UUID(rid)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_cursor") from exc
        query = query.where(
            or_(
                RewardCertificate.issued_at < last_at,
                and_(RewardCertificate.issued_at == last_at, RewardCertificate.id < last_id),
            )
        )
    rows = list(
        await session.scalars(
            query.order_by(RewardCertificate.issued_at.desc(), RewardCertificate.id.desc()).limit(limit)
        )
    )
    next_cursor = service.encode_cursor(rows[-1].issued_at, rows[-1].id) if len(rows) == limit else None
    return schemas.CertificatePage(items=[await _certificate_out(session, c) for c in rows], next_cursor=next_cursor)


@router.post("/certificates", response_model=schemas.CertificateOut, status_code=status.HTTP_201_CREATED)
async def issue_certificate(
    principal: Manager, session: Session, body: schemas.CertificateIn
) -> schemas.CertificateOut:
    badge = nomination = None
    if body.badge_award_id is not None:
        badge = await _badge(session, principal, body.badge_award_id)
        existing = await session.scalar(
            select(RewardCertificate.id).where(RewardCertificate.badge_award_id == badge.id)
        )
    else:
        assert body.nomination_id is not None
        nomination = await _nomination(session, principal, body.nomination_id, lock=True)
        existing = await session.scalar(
            select(RewardCertificate.id).where(RewardCertificate.nomination_id == nomination.id)
        )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "certificate_exists")
    cert = await certificates.issue(session, _actor(principal), badge=badge, nomination=nomination)
    await audit.record(
        session,
        actor=_actor(principal),
        action="rewards.certificate.issue",
        target=f"reward_certificate:{cert.id}",
        details={"code": cert.code, "distinction": cert.distinction, "kind": cert.kind},
    )
    await session.commit()
    return await _certificate_out(session, cert)


async def _certificate(
    session: AsyncSession, principal: Principal, cert_id: uuid.UUID, lock: bool = False
) -> RewardCertificate:
    cert = await session.get(RewardCertificate, cert_id, with_for_update=lock)
    if cert is None or not _in_scope(principal, cert.gouvernorat_code):
        raise _not_found()
    return cert


@router.get(
    "/certificates/{cert_id}/pdf",
    response_model=None,
    responses={302: {"description": "presigned URL"}, 200: {"model": schemas.DownloadOut}},
)
async def certificate_pdf(
    principal: Reader, session: Session, cert_id: uuid.UUID, accept: Annotated[str | None, Header()] = None
) -> Response:
    """302 to the PDF (``Accept: application/json``: ``{"url"}``), audited."""
    cert = await _certificate(session, principal, cert_id)
    if cert.pdf_object_key is None:
        raise _not_found()
    await audit.record(
        session, actor=_actor(principal), action="rewards.certificate.download", target=f"reward_certificate:{cert.id}"
    )
    await session.commit()
    return pdf_response(cert.pdf_object_key, accept)


@router.post("/certificates/{cert_id}/revoke", response_model=schemas.CertificateOut)
async def revoke_certificate(
    principal: Manager, session: Session, cert_id: uuid.UUID, body: schemas.ReasonIn
) -> schemas.CertificateOut:
    cert = await _certificate(session, principal, cert_id, lock=True)
    certificates.revoke(cert, _actor(principal), body.reason)
    await audit.record(
        session,
        actor=_actor(principal),
        action="rewards.certificate.revoke",
        target=f"reward_certificate:{cert.id}",
        reason=body.reason,
        details={"code": cert.code},
    )
    await session.commit()
    return await _certificate_out(session, cert)


# ---------------------------------------------------------------- rescue flag on an intervention


@router.post("/interventions/{incident_id}/rescue", response_model=schemas.RescueOut)
async def flag_rescue(
    principal: RescueWriter, session: Session, incident_id: uuid.UUID, body: schemas.RescueIn
) -> schemas.RescueOut:
    """Designate the reports that helped a rescue, on a closed and evaluated intervention (+500 by default)."""
    incident = await incidents.get_in_scope(session, principal, incident_id)
    outcome = (incident.evaluation or {}).get("outcome")
    if incident.status != "closed" or outcome is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "incident_not_evaluated")
    if outcome == "false_alarm":
        raise HTTPException(status.HTTP_409_CONFLICT, "false_alarm")
    results: list[schemas.RescueResult] = []
    for report_id in dict.fromkeys(body.report_ids):
        result, why = await service.award_rescue(session, incident, report_id)
        results.append(schemas.RescueResult(report_id=report_id, status=result, reason=why))
    await audit.record(
        session,
        actor=_actor(principal),
        action="rewards.rescue",
        target=f"incident:{incident.id}",
        reason=body.note,
        details={"reports": [{"report_id": str(r.report_id), "status": r.status} for r in results]},
    )
    await session.commit()
    return schemas.RescueOut(awarded=results)


# ---------------------------------------------------------------- leaderboard


@router.get("/leaderboard", response_model=schemas.LeaderboardOut)
async def leaderboard(
    principal: Reader,
    session: Session,
    scope: Literal["gouvernorat", "national"] = "gouvernorat",
    gouvernorat: int | None = None,
    period: Literal["year"] = "year",
    year: Annotated[int | None, Query(ge=2020, le=2100)] = None,
) -> schemas.LeaderboardOut:
    """Points earned in the year (Africa/Tunis), pseudonyms only; erased accounts are gone from the ledger."""
    del period
    year = year or service.now_utc().astimezone(service.TUNIS_TZ).year
    if scope == "national":
        _national(principal)
        code = None
    else:
        code = gouvernorat if gouvernorat is not None else principal.gouvernorat_code
        if code is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "gouvernorat_required")
        if not _in_scope(principal, code):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "out_of_scope")
    start, end = service.year_bounds(year)
    points = func.sum(LedgerEntry.delta).label("points")
    query = (
        select(LedgerEntry.citizen_id, points, Profile.gouvernorat_code)
        .outerjoin(Profile, Profile.user_id == LedgerEntry.citizen_id)
        .where(LedgerEntry.created_at >= start, LedgerEntry.created_at < end)
        .group_by(LedgerEntry.citizen_id, Profile.gouvernorat_code)
        .having(func.sum(LedgerEntry.delta) > 0)
        .order_by(points.desc(), LedgerEntry.citizen_id)
        .limit(LEADERBOARD_SIZE)
    )
    if code is not None:
        query = query.where(Profile.gouvernorat_code == code)
    rows = (await session.execute(query)).all()
    return schemas.LeaderboardOut(
        scope=scope,
        gouvernorat_code=code,
        year=year,
        items=[
            schemas.LeaderboardItem(
                rank=index + 1, pseudonym=pseudonym(citizen_id), points=int(total), gouvernorat_code=gouvernorat_code
            )
            for index, (citizen_id, total, gouvernorat_code) in enumerate(rows)
        ],
    )
