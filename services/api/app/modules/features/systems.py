"""The systems of the menu as a whole (Yamen 2026-11-13: «أريد لمدير النظام التصرف في الأنظمة الفرعية»).

The menu groups the dashboard's pages in 20 systems (``menu.json``). Above the page, the tab and the button, the
national system administrator acts on a system in one go:

* hides it, or suspends it with a message, for everyone, a role (in every gouvernorat or one) or an account: one rule on
  ``system.<key>`` (``POST /features/rules``), revoked like any rule;
* grants it to an account or a role, read only or read and write, for a period or not: the grant rules of each of its
  pages are written under one assignment (like a profile), the fixed ceiling skipping what the target may never
  receive; revoked together (``POST /features/profile-assignments/{id}/revoke``).

The name, colour, icon and order of a system, and moving a page to another, are the ``menu.order`` setting; the menu
source stays the default and the administrator's choices are saved over it, every change audited.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.access import ApiError
from app.core.db import as_system
from app.modules.audit import service as audit
from app.modules.features import registry, schemas, service
from app.modules.features.models import FeatureRule
from app.modules.features.profiles import features_of
from app.modules.features.registry import SYSTEM_PREFIX, Feature
from app.modules.features.router import Admin, Session, _check, _rule_out

router = APIRouter(prefix="/api/v1/staff/features/systems", tags=["features"])


def _names(f: Feature) -> schemas.Names:
    return schemas.Names(ar=f.names[0], fr=f.names[1], en=f.names[2])


def grantable(system: str, mode: str) -> list[Feature]:
    """What a grant of the whole system writes: each page with its tabs (and its buttons for ``write``), and a tab of
    another page that shows in this system's menu (the locations to verify, under the GIS)."""
    reg = registry.get()
    out: list[Feature] = []
    for f in reg.system_pages(system):
        if f.kind == "page":
            out.extend(features_of(f.key, mode))
        elif f.parent is not None and reg.features[f.parent].system != system:
            out.append(f)
    return list({f.key: f for f in out}.values())


@router.get("", response_model=list[schemas.SystemOut])
async def list_systems(principal: Admin, session: Session) -> list[schemas.SystemOut]:
    reg = registry.get()
    now = datetime.now(UTC)
    async with as_system(session):
        rows = list(
            await session.scalars(
                select(FeatureRule)
                .where(FeatureRule.feature_key.like(SYSTEM_PREFIX + "%"), FeatureRule.revoked_at.is_(None))
                .order_by(FeatureRule.created_at.desc())
            )
        )
    rules = [_rule_out(r, now) for r in rows]
    out = []
    for s in reg.systems:
        feature = reg.features[SYSTEM_PREFIX + s.key]
        out.append(
            schemas.SystemOut(
                key=s.key,
                number=s.number,
                block=s.block,
                names=_names(feature),
                pages=[
                    schemas.SystemPage(key=f.key, kind=f.kind, names=_names(f), nav=f.nav, flags=sorted(f.flags))
                    for f in reg.system_pages(s.key)
                    if f.kind in ("page", "tab")
                ],
                planned=list(s.planned),
                rules=[r for r in rules if r.feature_key == feature.key and r.state in ("active", "scheduled")],
            )
        )
    return out


@router.post("/{key}/grant", response_model=schemas.AssignmentOut, status_code=status.HTTP_201_CREATED)
async def grant_system(
    principal: Admin, session: Session, key: str, body: schemas.SystemGrantIn
) -> schemas.AssignmentOut:
    if not any(s.key == key for s in registry.get().systems):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown_system")
    now = datetime.now(UTC)
    assignment = uuid.uuid4()
    granted: list[str] = []
    skipped: list[schemas.Skipped] = []
    fields = body.model_dump(exclude={"mode"})
    async with as_system(session):
        for feature in grantable(key, body.mode):
            rule = schemas.RuleIn(feature_key=feature.key, effect="grant", **fields)
            try:
                _check(principal, rule, feature, now)
            except ApiError as exc:
                if exc.detail != "ceiling":
                    raise
                skipped.append(schemas.Skipped(feature_key=feature.key, reason=str(exc.extra.get("reason"))))
                continue
            session.add(
                FeatureRule(
                    feature_key=feature.key,
                    effect="grant",
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
                    profile_assignment_id=assignment,
                )
            )
            granted.append(feature.key)
        if not granted:
            raise ApiError(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "system_grants_nothing",
                skipped=[s.model_dump() for s in skipped],
            )
        await session.flush()
        await audit.record(
            session,
            actor=audit.actor_of(principal),
            action="features.system.grant",
            target=str(assignment),
            reason=body.reason,
            details={
                "system": key,
                "mode": body.mode,
                "target_kind": body.target_kind,
                "target": body.target,
                "features": granted,
                "skipped": [s.feature_key for s in skipped],
            },
            gouvernorats=[body.gouvernorat_code] if body.gouvernorat_code else None,
        )
        await session.commit()
    service.invalidate()
    return schemas.AssignmentOut(
        id=assignment,
        profile_id=None,
        target_kind=body.target_kind,
        target=body.target,
        target_name=body.target_name,
        gouvernorat_code=body.gouvernorat_code,
        reason=body.reason,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        created_by_name=audit.name_of(principal),
        created_at=now,
        state="scheduled" if body.starts_at and body.starts_at > now else "active",
        features=granted,
        skipped=skipped,
    )
