"""Intervention plans by hazard (phase PL1, docs/phase-pl/design-plans.md §2).

A plan is a document of the register of kind ``plan`` with a hazard. Its PDF is recorded once; a new version repeals
the previous one, which stays readable. The plans page shows, for every hazard in its colour, the national plan in
force and the plans of the gouvernorats the reader sees; a crisis axis is offered the plans of its hazard.
"""

from collections import defaultdict
from datetime import datetime

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal
from app.modules.audit import service as audit
from app.modules.register import domain, schemas, service
from app.modules.register.models import Document, Hazard

# A version that is still worth showing when no version is in force (drafts are not plans yet).
_PUBLISHED = ("in_force", "expired", "repealed")
_ORDER = {"in_force": 0, "expired": 1, "repealed": 2}


def manages_hazards(p: Principal) -> bool:
    """The central room keeps the list of hazards and their colours."""
    return p.is_national and domain.writes(p)


def hazard_out(h: Hazard) -> schemas.HazardOut:
    return schemas.HazardOut(
        key=h.key,
        name=dict(h.name),
        colour=h.colour,
        icon=h.icon,
        position=h.position,
        active=h.active,
        updated_by_name=h.updated_by_name,
        updated_at=h.updated_at,
    )


async def hazards(session: AsyncSession, *, active_only: bool = False) -> list[Hazard]:
    query = select(Hazard).order_by(Hazard.position, Hazard.key)
    if active_only:
        query = query.where(Hazard.active.is_(True))
    return list(await session.scalars(query))


async def save_hazard(
    session: AsyncSession, principal: Principal, key: str, body: schemas.HazardIn, now: datetime
) -> Hazard:
    if not manages_hazards(principal):
        raise service.forbidden()
    hazard = await session.get(Hazard, key)
    created = hazard is None
    if hazard is None:
        hazard = Hazard(key=key)
        session.add(hazard)
    before = None if created else {"colour": hazard.colour, "active": hazard.active}
    hazard.name = {lang: body.name.get(lang, "") for lang in ("ar", "fr", "en")}
    if not all(hazard.name.values()):
        raise service.error(status.HTTP_422_UNPROCESSABLE_CONTENT, "name_required")
    hazard.colour = body.colour
    hazard.icon = body.icon
    hazard.position = body.position
    hazard.active = body.active
    hazard.updated_by, hazard.updated_by_name, hazard.updated_at = (
        audit.actor_of(principal),
        audit.name_of(principal),
        now,
    )
    await session.flush()
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="register.hazard_saved",
        target=key,
        details={"created": created, "before": before, "colour": body.colour, "active": body.active},
    )
    return hazard


def _rank(doc: Document) -> tuple[int, int, float]:
    """In force first, then the most recently issued, then the most recently recorded."""
    return (_ORDER.get(doc.status, 9), -doc.issued_on.toordinal(), -doc.created_at.timestamp())


async def _readable_plans(session: AsyncSession, principal: Principal, hazard_keys: list[str]) -> list[Document]:
    """Published plans of these hazards the reader may read (row-level security does the gouvernorats)."""
    if not hazard_keys:
        return []
    docs = await session.scalars(
        select(Document).where(
            Document.kind == "plan",
            Document.hazard_key.in_(hazard_keys),
            Document.status.in_(_PUBLISHED),
        )
    )
    return [d for d in docs if service.readable(principal, d)]


async def overview(session: AsyncSession, principal: Principal) -> schemas.PlansOut:
    listed = await hazards(session, active_only=True)
    docs = await _readable_plans(session, principal, [h.key for h in listed])
    groups: dict[tuple[str, int | None], list[Document]] = defaultdict(list)
    for d in docs:
        groups[(d.hazard_key or "", d.gouvernorat_code)].append(d)
    chosen = {k: sorted(v, key=_rank)[0] for k, v in groups.items()}
    names = await service.gouvernorat_names(session)
    counts = await service.open_recommendations(session, [d.id for d in chosen.values()])

    def plan(key: tuple[str, int | None]) -> schemas.PlanOut:
        return schemas.PlanOut(
            document=service.document_out(principal, chosen[key], names, counts), versions=len(groups[key])
        )

    out = []
    for h in listed:
        regional = sorted((k for k in chosen if k[0] == h.key and k[1] is not None), key=lambda k: k[1] or 0)
        out.append(
            schemas.HazardPlans(
                hazard=hazard_out(h),
                national=plan((h.key, None)) if (h.key, None) in chosen else None,
                regional=[plan(k) for k in regional],
            )
        )
    return schemas.PlansOut(
        hazards=out,
        can_create=domain.writes(principal),
        can_manage_hazards=manages_hazards(principal),
    )


async def for_axis(
    session: AsyncSession, principal: Principal, axis_kind: str, gouvernorats: list[int]
) -> list[Document]:
    """The plans in force of the axis' hazard: the national one, then those of the axis' gouvernorats."""
    key = domain.AXIS_KIND_TOPICS.get(axis_kind)
    if key is None:
        return []
    docs = [
        d
        for d in await _readable_plans(session, principal, [key])
        if d.status == "in_force" and (d.gouvernorat_code is None or d.gouvernorat_code in gouvernorats)
    ]
    best: dict[int | None, Document] = {}
    for d in sorted(docs, key=_rank):
        best.setdefault(d.gouvernorat_code, d)
    return sorted(best.values(), key=lambda d: (d.gouvernorat_code is not None, d.gouvernorat_code or 0))
