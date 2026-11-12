"""Permission profiles (OS3, Yamen 2026-11-11: «Profil للقراءة والكتابة أو للقراءة فقط ... حسب الصلاحيات الممنوحة من
مدير النظام»).

A profile names a set of dashboard pages, each ``read`` (the page and its tabs: every GET under it) or ``write`` (its
buttons too). The administrator grants it in one go to an account (the inspector general) or to a role, for a period
or not; it writes the usual grant rules of the catalogue (``access.feature_rule``) under one assignment, revoked
together. The fixed ceiling still holds: a feature the target may never receive (personal data for a governor, a
national feature for a gouvernorat) is skipped and reported, never granted.
"""

import uuid
from collections import defaultdict
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import ApiError
from app.core.db import as_system
from app.modules.audit import service as audit
from app.modules.features import registry, schemas, service
from app.modules.features.models import FeatureProfile, FeatureRule
from app.modules.features.registry import Feature
from app.modules.features.router import Admin, Session, _check, _rule_out

router = APIRouter(prefix="/api/v1/staff/features", tags=["features"])


def features_of(page: str, mode: str) -> list[Feature]:
    """The page and its tabs (read), and its buttons too (write); empty for a page the catalogue does not know."""
    reg = registry.get().features
    top = reg.get(page)
    if top is None or top.kind != "page":
        return []
    children = [f for f in reg.values() if f.parent == page]
    return [top, *(f for f in children if f.kind == "tab" or (mode == "write" and f.kind == "button"))]


def _items(rows: list[dict[str, str]]) -> list[schemas.ProfileItemOut]:
    out = []
    for item in rows:
        found = features_of(item["page"], item["mode"])
        page = registry.get().features.get(item["page"])
        out.append(
            schemas.ProfileItemOut(
                page=item["page"],
                mode=item["mode"],
                known=bool(found),
                names=schemas.Names(ar=page.names[0], fr=page.names[1], en=page.names[2]) if page else None,
                features=[f.key for f in found],
            )
        )
    return out


async def _active(session: AsyncSession, now: datetime) -> dict[uuid.UUID, set[uuid.UUID]]:
    rows = (
        await session.execute(
            select(FeatureRule.profile_id, FeatureRule.profile_assignment_id).where(
                FeatureRule.profile_assignment_id.is_not(None),
                FeatureRule.revoked_at.is_(None),
                (FeatureRule.ends_at.is_(None)) | (FeatureRule.ends_at > now),
            )
        )
    ).all()
    found: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for profile, assignment in rows:
        if profile is not None and assignment is not None:
            found[profile].add(assignment)
    return found


def _out(row: FeatureProfile, active: dict[uuid.UUID, set[uuid.UUID]]) -> schemas.ProfileOut:
    return schemas.ProfileOut(
        id=row.id,
        name=row.name,
        description=row.description,
        builtin=row.builtin,
        items=_items(row.items),
        active_assignments=len(active.get(row.id, ())),
        updated_at=row.updated_at,
    )


def _unique(items: list[schemas.ProfileItem]) -> list[dict[str, str]]:
    pages: dict[str, str] = {}
    for item in items:
        # The same page twice: the wider mode wins.
        pages[item.page] = "write" if "write" in (item.mode, pages.get(item.page)) else "read"
    return [{"page": k, "mode": v} for k, v in pages.items()]


@router.get("/profiles", response_model=list[schemas.ProfileOut])
async def list_profiles(principal: Admin, session: Session) -> list[schemas.ProfileOut]:
    async with as_system(session):
        rows = list(
            await session.scalars(select(FeatureProfile).order_by(FeatureProfile.builtin.desc(), FeatureProfile.name))
        )
        active = await _active(session, datetime.now(UTC))
    return [_out(r, active) for r in rows]


async def _save(session: AsyncSession, row: FeatureProfile, principal: Admin, action: str) -> schemas.ProfileOut:
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "feature_profile_taken") from exc
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action=action,
        target=str(row.id),
        details={"name": row.name, "items": row.items},
    )
    out = _out(row, await _active(session, datetime.now(UTC)))
    await session.commit()
    return out


@router.post("/profiles", response_model=schemas.ProfileOut, status_code=status.HTTP_201_CREATED)
async def create_profile(principal: Admin, session: Session, body: schemas.ProfileIn) -> schemas.ProfileOut:
    async with as_system(session):
        row = FeatureProfile(
            name=body.name.strip(),
            description=body.description,
            items=_unique(body.items),
            created_by=audit.actor_of(principal),
            created_by_name=audit.name_of(principal),
        )
        session.add(row)
        return await _save(session, row, principal, "features.profile.create")


@router.patch("/profiles/{profile_id}", response_model=schemas.ProfileOut)
async def update_profile(
    principal: Admin, session: Session, profile_id: uuid.UUID, body: schemas.ProfileIn
) -> schemas.ProfileOut:
    """A change applies to the next grants; the rules already written stay as granted until revoked."""
    async with as_system(session):
        row = await session.get(FeatureProfile, profile_id, with_for_update=True)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        row.name, row.description, row.items = body.name.strip(), body.description, _unique(body.items)
        row.updated_by_name, row.updated_at = audit.name_of(principal), datetime.now(UTC)
        return await _save(session, row, principal, "features.profile.update")


@router.delete("/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(principal: Admin, session: Session, profile_id: uuid.UUID) -> None:
    async with as_system(session):
        row = await session.get(FeatureProfile, profile_id, with_for_update=True)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        if row.builtin:
            raise HTTPException(status.HTTP_409_CONFLICT, "profile_builtin")
        if (await _active(session, datetime.now(UTC))).get(row.id):
            raise HTTPException(status.HTTP_409_CONFLICT, "profile_in_use")
        await session.delete(row)
        await audit.record(
            session, actor=audit.actor_of(principal), action="features.profile.delete", details={"name": row.name}
        )
        await session.commit()


@router.post("/profiles/{profile_id}/assign", response_model=schemas.AssignmentOut, status_code=status.HTTP_201_CREATED)
async def assign_profile(
    principal: Admin, session: Session, profile_id: uuid.UUID, body: schemas.AssignIn
) -> schemas.AssignmentOut:
    now = datetime.now(UTC)
    assignment = uuid.uuid4()
    granted: list[str] = []
    skipped: list[schemas.Skipped] = []
    async with as_system(session):
        profile = await session.get(FeatureProfile, profile_id)
        if profile is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        for item in profile.items:
            found = features_of(item["page"], item["mode"])
            if not found:
                skipped.append(schemas.Skipped(feature_key=item["page"], reason="unknown_feature"))
            for feature in found:
                rule = schemas.RuleIn(feature_key=feature.key, effect="grant", **body.model_dump())
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
                        profile_id=profile.id,
                        profile_assignment_id=assignment,
                    )
                )
                granted.append(feature.key)
        if not granted:
            raise ApiError(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "profile_grants_nothing",
                skipped=[s.model_dump() for s in skipped],
            )
        await session.flush()
        await audit.record(
            session,
            actor=audit.actor_of(principal),
            action="features.profile.assign",
            target=str(assignment),
            reason=body.reason,
            details={
                "profile": profile.name,
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
        profile_id=profile_id,
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


@router.get("/profile-assignments", response_model=list[schemas.AssignmentOut])
async def list_assignments(
    principal: Admin, session: Session, profile_id: uuid.UUID | None = None, include_ended: bool = False
) -> list[schemas.AssignmentOut]:
    now = datetime.now(UTC)
    async with as_system(session):
        query = select(FeatureRule).where(FeatureRule.profile_assignment_id.is_not(None))
        if profile_id is not None:
            query = query.where(FeatureRule.profile_id == profile_id)
        rows = list(await session.scalars(query.order_by(FeatureRule.created_at.desc()).limit(5000)))
    groups: dict[uuid.UUID, list[FeatureRule]] = defaultdict(list)
    for r in rows:
        assert r.profile_assignment_id is not None
        groups[r.profile_assignment_id].append(r)
    out = []
    for key, rules in groups.items():
        first = rules[0]
        state = _rule_out(first, now).state
        if not include_ended and state not in ("active", "scheduled"):
            continue
        out.append(
            schemas.AssignmentOut(
                id=key,
                profile_id=first.profile_id,
                target_kind=first.target_kind,
                target=first.target,
                target_name=first.target_name,
                gouvernorat_code=first.gouvernorat_code,
                reason=first.reason,
                starts_at=first.starts_at,
                ends_at=first.ends_at,
                created_by_name=first.created_by_name,
                created_at=first.created_at,
                state=state,
                features=sorted(r.feature_key for r in rules),
            )
        )
    return out


@router.post("/profile-assignments/{assignment_id}/revoke", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_assignment(
    principal: Admin, session: Session, assignment_id: uuid.UUID, body: schemas.RevokeIn
) -> None:
    now = datetime.now(UTC)
    async with as_system(session):
        done = await session.execute(
            update(FeatureRule)
            .where(FeatureRule.profile_assignment_id == assignment_id, FeatureRule.revoked_at.is_(None))
            .values(revoked_at=now, revoked_by_name=audit.name_of(principal), revoke_reason=body.reason)
        )
        if not done.rowcount:  # type: ignore[attr-defined]
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
        await audit.record(
            session,
            actor=audit.actor_of(principal),
            action="features.profile.revoke",
            target=str(assignment_id),
            reason=body.reason,
        )
        await session.commit()
    service.invalidate()
