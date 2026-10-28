"""Permissions of the system administrator (L4 §8): the catalogue, the rules, a preview, and the caller's own."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import ApiError
from app.core.db import as_system, get_session
from app.core.security import REALM_ROLES, Principal, Realm, Role, require_roles
from app.modules.audit import service as audit
from app.modules.features import registry, schemas, service
from app.modules.features.models import FeatureRule
from app.modules.features.registry import TECHNICAL, Feature

router = APIRouter(prefix="/api/v1/staff/features", tags=["features"])

Session = Annotated[AsyncSession, Depends(get_session)]
AnyStaff = Annotated[Principal, Depends(require_roles(*REALM_ROLES[Realm.STAFF]))]
STAFF_ROLES = REALM_ROLES[Realm.STAFF]


async def _administrator(principal: Annotated[Principal, Depends(require_roles(Role.SYSADMIN))]) -> Principal:
    if not principal.is_national:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "national_scope_required")
    return principal


Admin = Annotated[Principal, Depends(_administrator)]


def _feature_out(f: Feature) -> schemas.FeatureOut:
    return schemas.FeatureOut(
        key=f.key,
        kind=f.kind,
        names=schemas.Names(ar=f.names[0], fr=f.names[1], en=f.names[2]),
        parent=f.parent,
        group=f.group,
        nav=f.nav,
        flags=sorted(f.flags),
        roles=sorted(r.value for r in f.roles),
        act_as=f.act_as.value if f.act_as else None,
        grantable=f.act_as is not None,
        routes=list(f.routes),
    )


def _rule_out(row: FeatureRule, now: datetime) -> schemas.RuleOut:
    if row.revoked_at is not None:
        state = "revoked"
    elif row.ends_at is not None and row.ends_at <= now:
        state = "ended"
    elif row.starts_at is not None and row.starts_at > now:
        state = "scheduled"
    else:
        state = "active"
    return schemas.RuleOut(
        id=row.id,
        feature_key=row.feature_key,
        effect=row.effect,
        target_kind=row.target_kind,
        target=row.target,
        target_name=row.target_name,
        gouvernorat_code=row.gouvernorat_code,
        reason=row.reason,
        starts_at=row.starts_at,
        ends_at=row.ends_at,
        created_by_name=row.created_by_name,
        created_at=row.created_at,
        revoked_at=row.revoked_at,
        revoked_by_name=row.revoked_by_name,
        revoke_reason=row.revoke_reason,
        state=state,
    )


@router.get("/mine", response_model=schemas.Mine)
async def mine(principal: AnyStaff) -> schemas.Mine:
    rules = await service.rules_in_force()
    eff = service.effective(principal, rules, datetime.now(UTC))
    granted = [k for k, e in eff.items() if e.granted and not e.hidden]
    features = registry.get().features
    return schemas.Mine(
        granted=granted,
        hidden=[k for k, e in eff.items() if e.hidden],
        lent={k: act_as.value for k in granted if (act_as := features[k].act_as) is not None},
    )


@router.get("/catalogue", response_model=list[schemas.FeatureOut])
async def catalogue(principal: Admin) -> list[schemas.FeatureOut]:
    reg = registry.get()
    return [_feature_out(reg.features[k]) for k in reg.order]


@router.get("/rules", response_model=list[schemas.RuleOut])
async def list_rules(
    principal: Admin,
    session: Session,
    feature: str | None = None,
    include_ended: bool = False,
) -> list[schemas.RuleOut]:
    now = datetime.now(UTC)
    async with as_system(session):
        query = select(FeatureRule).order_by(FeatureRule.created_at.desc()).limit(1000)
        if feature:
            query = query.where(FeatureRule.feature_key == feature)
        rows = list(await session.scalars(query))
    out = [_rule_out(r, now) for r in rows]
    return out if include_ended else [r for r in out if r.state in ("active", "scheduled")]


def _refuse(code: str, **extra: object) -> ApiError:
    return ApiError(status.HTTP_422_UNPROCESSABLE_CONTENT, code, **extra)


def _check(principal: Principal, body: schemas.RuleIn, feature: Feature, now: datetime) -> None:
    if body.target_kind == "role":
        if body.target not in {r.value for r in STAFF_ROLES}:
            raise _refuse("unknown_role")
    elif body.gouvernorat_code is not None:
        raise _refuse("user_rule_has_no_gouvernorat")
    if body.ends_at is not None and (body.ends_at <= now or (body.starts_at and body.ends_at <= body.starts_at)):
        raise _refuse("invalid_period")
    if body.effect == "hide":
        if feature.page == service.PERMISSIONS and (
            (body.target_kind == "role" and body.target == Role.SYSADMIN.value)
            or (body.target_kind == "user" and body.target == principal.subject)
        ):
            raise _refuse("self_lockout")
        return
    # The fixed ceiling (Yamen 2026-10-28): checked here for what is known, and again on every request.
    if feature.act_as is None:
        raise _refuse("ceiling", reason="fixed")
    if body.target_kind == "role":
        role = Role(body.target)
        if role in TECHNICAL:
            raise _refuse("ceiling", reason="technical_account")
        if "personal" in feature.flags and role in service.NO_PERSONAL:
            raise _refuse("ceiling", reason="personal_data")
        if "national" in feature.flags and body.gouvernorat_code is not None:
            raise _refuse("ceiling", reason="national_scope")


@router.post("/rules", response_model=schemas.RuleOut, status_code=status.HTTP_201_CREATED)
async def create_rule(principal: Admin, session: Session, body: schemas.RuleIn) -> schemas.RuleOut:
    feature = registry.get().features.get(body.feature_key)
    if feature is None:
        raise _refuse("unknown_feature")
    now = datetime.now(UTC)
    _check(principal, body, feature, now)
    async with as_system(session):
        row = FeatureRule(
            feature_key=feature.key,
            effect=body.effect,
            target_kind=body.target_kind,
            target=body.target,
            target_name=body.target_name,
            gouvernorat_code=body.gouvernorat_code,
            reason=body.reason,
            starts_at=body.starts_at,
            ends_at=body.ends_at,
            created_by=audit.actor_of(principal),
            created_by_name=audit.name_of(principal),
            created_at=now,
        )
        session.add(row)
        await session.flush()
        await audit.record(
            session,
            actor=audit.actor_of(principal),
            action=f"features.{body.effect}",
            target=str(row.id),
            reason=body.reason,
            details={
                "feature": feature.key,
                "target_kind": body.target_kind,
                "target": body.target,
                "starts_at": body.starts_at.isoformat() if body.starts_at else None,
                "ends_at": body.ends_at.isoformat() if body.ends_at else None,
            },
            gouvernorats=[body.gouvernorat_code] if body.gouvernorat_code else None,
        )
        out = _rule_out(row, now)
        await session.commit()
    service.invalidate()
    return out


@router.post("/rules/{rule_id}/revoke", response_model=schemas.RuleOut)
async def revoke_rule(
    principal: Admin, session: Session, rule_id: uuid.UUID, body: schemas.RevokeIn
) -> schemas.RuleOut:
    now = datetime.now(UTC)
    async with as_system(session):
        row = await session.get(FeatureRule, rule_id)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        if row.revoked_at is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "already_revoked")
        row.revoked_at = now
        row.revoked_by_name = audit.name_of(principal)
        row.revoke_reason = body.reason
        await audit.record(
            session,
            actor=audit.actor_of(principal),
            action="features.revoke",
            target=str(row.id),
            reason=body.reason,
            details={"feature": row.feature_key, "target_kind": row.target_kind, "target": row.target},
            gouvernorats=[row.gouvernorat_code] if row.gouvernorat_code else None,
        )
        out = _rule_out(row, now)
        await session.commit()
    service.invalidate()
    return out


@router.get("/preview", response_model=list[schemas.PreviewRow])
async def preview(
    principal: Admin,
    session: Session,
    roles: Annotated[str, Query(max_length=400, description="Comma-separated roles")],
    gouvernorat: int | None = None,
    subject: str | None = None,
) -> list[schemas.PreviewRow]:
    """What an account with these roles (and this subject, for its own rules) sees once the rules apply."""
    wanted = frozenset(Role(r) for r in roles.split(",") if r in {x.value for x in STAFF_ROLES})
    who = Principal(subject or f"preview:{uuid.uuid4()}", Realm.STAFF, wanted, gouvernorat)
    now = datetime.now(UTC)
    async with as_system(session):
        rules = await service.load(session, now)
    return [
        schemas.PreviewRow(key=k, default=e.default, hidden=e.hidden, granted=e.granted, refused=e.refused, open=e.open)
        for k, e in service.effective(who, rules, now).items()
    ]
