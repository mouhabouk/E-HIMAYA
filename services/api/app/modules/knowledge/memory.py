"""National memory (FR-C-22): after-action records, their versions and the review workflow.

* Every saved change and every transition writes a full snapshot (``knowledge.memory_entry_version``) and an audit
  entry; edits use optimistic locking (``version``).
* draft → in_review → published by a second staff member (the reviewer is neither the author nor the last editor);
  a reviewer may send it back with a note; published or draft entries can be archived with a reason and restored.
* Editing a published entry starts a new draft: readers, the library and the assistant keep seeing the published
  snapshot until the new version is reviewed.
* ``prefill_from_incident`` drafts the after-action review of an incident (timeline, figures, resources, response
  times) without names, phone numbers or citizens' words; nothing is ever published automatically.
"""

import base64
import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import emit
from app.core.security import Principal, Role
from app.modules.audit import service as audit
from app.modules.decision.domain import CATEGORY_LABELS
from app.modules.knowledge import documents
from app.modules.knowledge import schemas as s
from app.modules.knowledge.domain import (
    AUTHOR_ROLES,
    MEMORY_ACCESS,
    REVIEW_ROLES,
    TRANSITIONS,
    Kind,
    Status,
    can_see,
    covers,
)
from app.modules.knowledge.models import MemoryEntry, MemoryEntryVersion
from app.modules.ops import service as incidents
from app.modules.ops.models import Assignment, Incident, Resource, TimelineEvent, Unit
from app.modules.reports.models import Media, Report

CONTENT_FIELDS = (
    "title",
    "event_type",
    "started_at",
    "ended_at",
    "gouvernorats",
    "geometry",
    "incident_ids",
    "summary",
    "strengths",
    "weaknesses",
    "lessons",
    "recommendations",
    "sources",
    "access",
)
_ARABIC = re.compile("[؀-ۿ]")


def _now() -> datetime:
    return datetime.now(UTC)


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, detail)


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "not_found")


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, detail)


def _invalid(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail)


# ---------------------------------------------------------------- permissions


def _has(principal: Principal, roles: tuple[Role, ...]) -> bool:
    return bool(principal.roles & frozenset(roles))


def _involved(principal: Principal, entry: MemoryEntry) -> bool:
    actor = audit.actor_of(principal)
    return actor in (entry.author, entry.updated_by) or any(r.get("id") == actor for r in entry.reviewers)


def sees_working_copy(principal: Principal, entry: MemoryEntry) -> bool:
    """Authors and reviewers whose scope covers the entry (and anyone who worked on it) see drafts and reviews."""
    return _involved(principal, entry) or (
        _has(principal, (*AUTHOR_ROLES, *REVIEW_ROLES)) and covers(principal, entry.gouvernorats)
    )


def sees_published(principal: Principal, entry: MemoryEntry) -> bool:
    return (
        entry.published_version is not None
        and entry.status != Status.ARCHIVED
        and can_see(principal, MEMORY_ACCESS[entry.access], entry.gouvernorats)
    )


def can_edit(principal: Principal, entry: MemoryEntry) -> bool:
    return (
        entry.status in (Status.DRAFT, Status.PUBLISHED)
        and _has(principal, AUTHOR_ROLES)
        and covers(principal, entry.gouvernorats)
    )


def _self_review(principal: Principal, entry: MemoryEntry) -> bool:
    return audit.actor_of(principal) in (entry.author, entry.updated_by)


def can_review(principal: Principal, entry: MemoryEntry) -> bool:
    return (
        entry.status == Status.IN_REVIEW
        and _has(principal, REVIEW_ROLES)
        and covers(principal, entry.gouvernorats)
        and not _self_review(principal, entry)
    )


# ---------------------------------------------------------------- serialisation


async def _geojson(session: AsyncSession, entry: MemoryEntry) -> dict[str, Any] | None:
    if entry.geometry is None:
        return None
    raw = await session.scalar(select(func.ST_AsGeoJSON(MemoryEntry.geometry)).where(MemoryEntry.id == entry.id))
    return json.loads(raw) if raw else None


async def snapshot_of(session: AsyncSession, entry: MemoryEntry) -> dict[str, Any]:
    """Content fields of the working copy, as stored in a version row."""
    values = {name: getattr(entry, name) for name in CONTENT_FIELDS if name != "geometry"}
    values["geometry"] = await _geojson(session, entry)
    return s.EntryFields.model_validate(values).model_dump(mode="json")


def _person(actor: str, name: str | None) -> s.Person:
    return s.Person(id=actor, name=name)


async def entry_out(session: AsyncSession, principal: Principal, entry: MemoryEntry) -> s.EntryOut:
    """The entry as this caller may see it: the working copy, or the published snapshot for readers."""
    if sees_working_copy(principal, entry):
        content = await snapshot_of(session, entry)
        state: dict[str, Any] = {"status": entry.status, "version": entry.version}
    elif sees_published(principal, entry):
        assert entry.published_version is not None
        row = await session.get(MemoryEntryVersion, (entry.id, entry.published_version))
        if row is None:
            raise _not_found()
        content = dict(row.snapshot)
        state = {"status": Status.PUBLISHED.value, "version": entry.published_version}
    else:
        raise _not_found()
    return s.EntryOut(
        **content,
        **state,
        id=entry.id,
        published_version=entry.published_version,
        author=_person(entry.author, entry.author_name),
        updated_by=_person(entry.updated_by, entry.updated_by_name),
        reviewers=[s.Review.model_validate(r) for r in entry.reviewers],
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        published_at=entry.published_at,
        can_edit=can_edit(principal, entry),
        can_review=can_review(principal, entry),
    )


def _summary(principal: Principal, entry: MemoryEntry, published: dict[str, Any] | None) -> s.EntrySummary:
    working = sees_working_copy(principal, entry)
    source: dict[str, Any] = (
        {name: getattr(entry, name) for name in ("title", "event_type", "started_at", "ended_at", "gouvernorats")}
        | {"access": entry.access}
        if working or published is None
        else published
    )
    return s.EntrySummary(
        id=entry.id,
        title=s.Title.model_validate(source["title"]),
        event_type=source["event_type"],
        started_at=source["started_at"],
        ended_at=source["ended_at"],
        gouvernorats=list(source["gouvernorats"]),
        access=source["access"],
        status=entry.status if working else Status.PUBLISHED.value,
        version=entry.version if working else entry.published_version or entry.version,
        published_version=entry.published_version,
        author=_person(entry.author, entry.author_name),
        updated_at=entry.updated_at,
    )


# ---------------------------------------------------------------- reads


async def get_visible(
    session: AsyncSession, principal: Principal, entry_id: uuid.UUID, lock: bool = False
) -> MemoryEntry:
    entry = await session.get(MemoryEntry, entry_id, with_for_update=lock)
    if entry is None or not (sees_working_copy(principal, entry) or sees_published(principal, entry)):
        raise _not_found()
    return entry


def _encode(at: datetime, entry_id: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(f"{at.isoformat()}|{entry_id}".encode()).decode().rstrip("=")


def _decode(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        at, eid = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode().split("|", 1)
        return datetime.fromisoformat(at), uuid.UUID(eid)
    except ValueError as exc:
        raise _invalid("invalid_cursor") from exc


async def list_entries(
    session: AsyncSession,
    principal: Principal,
    *,
    q: str | None,
    statuses: list[str],
    access: str | None,
    event_type: str | None,
    gouvernorat: int | None,
    limit: int,
    cursor: str | None,
) -> s.EntryPage:
    query = select(MemoryEntry)
    if q:
        pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.where(
            or_(MemoryEntry.title["ar"].astext.ilike(pattern), MemoryEntry.title["fr"].astext.ilike(pattern))
        )
    if access:
        query = query.where(MemoryEntry.access == access)
    if event_type:
        query = query.where(MemoryEntry.event_type == event_type)
    if gouvernorat is not None:
        query = query.where(MemoryEntry.gouvernorats.contains([gouvernorat]))
    if not principal.is_national and not _has(principal, (*AUTHOR_ROLES, *REVIEW_ROLES)):
        query = query.where(MemoryEntry.published_version.is_not(None))
    if cursor:
        at, eid = _decode(cursor)
        query = query.where(or_(MemoryEntry.updated_at < at, and_(MemoryEntry.updated_at == at, MemoryEntry.id < eid)))
    query = query.order_by(MemoryEntry.updated_at.desc(), MemoryEntry.id.desc())

    items: list[s.EntrySummary] = []
    last: MemoryEntry | None = None
    exhausted = False
    rows: list[MemoryEntry] = []
    offset = 0
    page = max(limit * 2, 50)
    while len(items) < limit:
        rows = list(await session.scalars(query.offset(offset).limit(page)))
        offset += len(rows)
        if len(rows) < page:
            exhausted = True
        for entry in rows:
            last = entry
            working = sees_working_copy(principal, entry)
            published: dict[str, Any] | None = None
            if not working:
                if not sees_published(principal, entry):
                    continue
                version = await session.get(MemoryEntryVersion, (entry.id, entry.published_version))
                if version is None:
                    continue
                published = dict(version.snapshot)
            effective = entry.status if working else Status.PUBLISHED.value
            if statuses and effective not in statuses:
                continue
            items.append(_summary(principal, entry, published))
            if len(items) == limit:
                break
        if exhausted:
            break
    more = len(items) == limit and last is not None and (not exhausted or last is not rows[-1])
    return s.EntryPage(items=items, next_cursor=_encode(last.updated_at, last.id) if more and last else None)


async def versions(session: AsyncSession, principal: Principal, entry_id: uuid.UUID) -> s.VersionList:
    entry = await get_visible(session, principal, entry_id)
    query = select(MemoryEntryVersion).where(MemoryEntryVersion.entry_id == entry.id)
    if not sees_working_copy(principal, entry):
        # Readers only see the history of what was published.
        query = query.where(MemoryEntryVersion.change == "published")
    rows = await session.scalars(query.order_by(MemoryEntryVersion.version.desc()))
    return s.VersionList(items=[_version_summary(r) for r in rows])


def _version_summary(row: MemoryEntryVersion) -> s.VersionSummary:
    return s.VersionSummary(
        version=row.version,
        status=row.status,
        change=row.change,
        note=row.note,
        created_at=row.created_at,
        created_by=_person(row.created_by, row.created_by_name),
    )


async def version(session: AsyncSession, principal: Principal, entry_id: uuid.UUID, number: int) -> s.VersionOut:
    entry = await get_visible(session, principal, entry_id)
    row = await session.get(MemoryEntryVersion, (entry.id, number))
    if row is None or (not sees_working_copy(principal, entry) and row.change != "published"):
        raise _not_found()
    return s.VersionOut(**_version_summary(row).model_dump(), entry=s.EntryFields.model_validate(row.snapshot))


# ---------------------------------------------------------------- validation of what is written


async def _check_geometry(session: AsyncSession, geometry: s.Geometry | None) -> str | None:
    if geometry is None:
        return None
    raw = json.dumps(geometry.model_dump())
    try:
        async with session.begin_nested():
            valid = await session.scalar(
                text(
                    "SELECT ST_IsValid(g) AND ST_Within(g, ST_MakeEnvelope(7, 30, 12, 38, 4326)) "
                    "FROM (SELECT ST_SetSRID(ST_GeomFromGeoJSON(:g), 4326) AS g) t"
                ),
                {"g": raw},
            )
    except DBAPIError as exc:
        raise _invalid("invalid_geometry") from exc
    if not valid:
        raise _invalid("invalid_geometry")
    return raw


async def _check_references(session: AsyncSession, principal: Principal, fields: s.EntryFields) -> None:
    for incident_id in fields.incident_ids:
        incident = await session.get(Incident, incident_id)
        if incident is None or not incidents.in_scope(principal, incident):
            raise _invalid("invalid_incident")
    for source in fields.sources:
        if source.media_id is None:
            continue
        media = await session.get(Media, source.media_id)
        if media is None or media.status != "stored":
            raise _invalid("invalid_source")
        report = await session.get(Report, media.report_id) if media.report_id else None
        code = report.gouvernorat_code if report is not None else None
        if not principal.is_national and (code is None or not principal.can_access_gouvernorat(code)):
            raise _invalid("invalid_source")


async def _validate(session: AsyncSession, principal: Principal, fields: s.EntryFields) -> str | None:
    if not covers(principal, fields.gouvernorats):
        raise _forbidden("out_of_scope")
    await _check_references(session, principal, fields)
    return await _check_geometry(session, fields.geometry)


def _assign(entry: MemoryEntry, fields: s.EntryFields, geometry: str | None) -> None:
    data = fields.model_dump(mode="json")
    entry.title = data["title"]
    entry.event_type = fields.event_type.value
    entry.started_at, entry.ended_at = fields.started_at, fields.ended_at
    entry.gouvernorats = list(fields.gouvernorats)
    entry.incident_ids = list(fields.incident_ids)
    for name in documents.SECTIONS:
        setattr(entry, name, data[name])
    entry.sources = data["sources"]
    entry.access = fields.access
    entry.geometry = func.ST_SetSRID(func.ST_GeomFromGeoJSON(geometry), 4326) if geometry else None


async def _record(
    session: AsyncSession, principal: Principal, entry: MemoryEntry, change: str, note: str | None = None
) -> None:
    """Snapshot, audit entry, event and library row of one saved change (the caller commits)."""
    await session.flush()
    await session.refresh(entry)
    session.add(
        MemoryEntryVersion(
            entry_id=entry.id,
            version=entry.version,
            snapshot=await snapshot_of(session, entry),
            status=entry.status,
            change=change,
            note=note,
            created_by=audit.actor_of(principal),
            created_by_name=audit.name_of(principal),
        )
    )
    await session.flush()
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action=f"memory.{change}",
        target=f"memory:{entry.id}",
        reason=note,
        details={"version": entry.version, "status": entry.status, "access": entry.access},
    )
    try:
        # The library row now, so a published entry is searchable at once; on a race with the indexer (which also
        # reacts to the event below), the indexer's row wins.
        async with session.begin_nested():
            await documents.refresh(session, Kind.MEMORY, str(entry.id))
    except IntegrityError:
        pass
    await emit(
        session,
        "memory.updated",
        {
            "entry": {
                "id": str(entry.id),
                "status": entry.status,
                "version": entry.version,
                "published_version": entry.published_version,
                "gouvernorats": list(entry.gouvernorats),
            }
        },
    )


# ---------------------------------------------------------------- writes


async def create(session: AsyncSession, principal: Principal, body: s.EntryIn) -> MemoryEntry:
    geometry = await _validate(session, principal, body)
    actor, name = audit.actor_of(principal), audit.name_of(principal)
    entry = MemoryEntry(
        status=Status.DRAFT.value,
        author=actor,
        author_name=name,
        updated_by=actor,
        updated_by_name=name,
        version=1,
        reviewers=[],
    )
    _assign(entry, body, geometry)
    session.add(entry)
    await _record(session, principal, entry, "created")
    return entry


async def update(session: AsyncSession, principal: Principal, entry_id: uuid.UUID, patch: s.EntryPatch) -> MemoryEntry:
    entry = await get_visible(session, principal, entry_id, lock=True)
    if not sees_working_copy(principal, entry) or not _has(principal, AUTHOR_ROLES):
        raise _forbidden("insufficient_role")
    if entry.status == Status.IN_REVIEW:
        raise _conflict("entry_in_review")
    if entry.status == Status.ARCHIVED:
        raise _conflict("entry_archived")
    if not covers(principal, entry.gouvernorats):
        raise _forbidden("out_of_scope")
    if patch.version != entry.version:
        raise _conflict("version_conflict")
    current = await snapshot_of(session, entry)
    changes = patch.model_dump(mode="json", exclude={"version"}, exclude_unset=True)
    fields = s.EntryFields.model_validate({**current, **changes})
    geometry = await _validate(session, principal, fields)
    if fields.model_dump(mode="json") == current:
        return entry
    _assign(entry, fields, geometry)
    entry.version += 1
    entry.status = Status.DRAFT.value
    entry.updated_by, entry.updated_by_name = audit.actor_of(principal), audit.name_of(principal)
    entry.updated_at = _now()
    await _record(session, principal, entry, "edited")
    return entry


async def transition(
    session: AsyncSession, principal: Principal, entry_id: uuid.UUID, body: s.TransitionIn
) -> MemoryEntry:
    entry = await get_visible(session, principal, entry_id, lock=True)
    if not sees_working_copy(principal, entry):
        raise _forbidden("insufficient_role")
    if body.version != entry.version:
        raise _conflict("version_conflict")
    rule = TRANSITIONS.get((entry.status, body.to))
    if rule is None:
        raise _conflict("invalid_transition")
    roles, note_required, change = rule
    if not _has(principal, roles):
        raise _forbidden("insufficient_role")
    if not covers(principal, entry.gouvernorats):
        raise _forbidden("out_of_scope")
    if note_required and not body.note:
        raise _invalid("note_required")
    now = _now()
    actor, name = audit.actor_of(principal), audit.name_of(principal)
    if change in ("published", "changes_requested"):
        if change == "published" and _self_review(principal, entry):
            # A second staff member reviews: never the author nor the last editor of the reviewed version.
            raise _forbidden("self_review_forbidden")
        decision = "approved" if change == "published" else "changes_requested"
        entry.reviewers = [
            *entry.reviewers,
            {
                "id": actor,
                "name": name,
                "decision": decision,
                "note": body.note,
                "at": now.isoformat(),
                "version": entry.version + 1,
            },
        ]
    entry.status = body.to
    entry.version += 1
    if change == "published":
        entry.published_version, entry.published_at = entry.version, now
    entry.updated_at = now
    await _record(session, principal, entry, change, body.note)
    return entry


async def remove(session: AsyncSession, principal: Principal, entry_id: uuid.UUID) -> None:
    entry = await get_visible(session, principal, entry_id, lock=True)
    if not sees_working_copy(principal, entry):
        raise _forbidden("insufficient_role")
    if entry.status != Status.DRAFT or entry.published_version is not None:
        raise _conflict("entry_published_once")
    if audit.actor_of(principal) != entry.author and not _has(principal, REVIEW_ROLES):
        raise _forbidden("insufficient_role")
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="memory.deleted",
        target=f"memory:{entry.id}",
        details={"version": entry.version},
    )
    await session.delete(entry)
    await session.flush()
    await documents.refresh(session, Kind.MEMORY, str(entry_id))


# ---------------------------------------------------------------- after-action review from an incident


def _duration(start: datetime | None, end: datetime | None) -> str | None:
    if start is None or end is None or end < start:
        return None
    minutes = int((end - start) / timedelta(minutes=1))
    return f"{minutes // 60} h {minutes % 60:02d} min" if minutes >= 60 else f"{minutes} min"


def _place(value: str | None) -> tuple[str, str]:
    """Put a staff text in the section of its language (the author translates the other one)."""
    if not value:
        return "", ""
    return (value, "") if _ARABIC.search(value) else ("", value)


def _table(header: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return ""
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(cell.replace("|", "/") for cell in row) + " |" for row in rows]
    return "\n".join(lines)


async def prefill_from_incident(session: AsyncSession, principal: Principal, incident_id: uuid.UUID) -> MemoryEntry:
    """A draft after-action review of an incident: facts only, no personal data; the author completes it."""
    incident = await incidents.get_in_scope(session, principal, incident_id)
    if incident.status in ("dissolved", "merged"):
        raise _conflict("incident_not_reviewable")
    members = list(await session.scalars(select(Report).where(Report.incident_id == incident.id)))
    first_report = min((r.received_at for r in members), default=incident.opened_at)
    assignments = (
        await session.execute(
            select(Assignment, Resource, Unit)
            .outerjoin(Resource, Resource.id == Assignment.resource_id)
            .outerjoin(Unit, Unit.id == Resource.unit_id)
            .where(Assignment.incident_id == incident.id)
            .order_by(Assignment.created_at)
        )
    ).all()
    events = list(
        await session.scalars(
            select(TimelineEvent)
            .where(TimelineEvent.incident_id == incident.id, TimelineEvent.kind != "assistant")
            .order_by(TimelineEvent.at, TimelineEvent.id)
        )
    )
    evaluation = incident.evaluation or {}
    casualties = evaluation.get("casualties") or {}
    first_assignment = min((a.created_at for a, _, _ in assignments), default=None)
    on_scene = min((a.on_scene_at for a, _, _ in assignments if a.on_scene_at), default=None)
    times = {
        "assign": _duration(first_report, first_assignment),
        "scene": _duration(first_report, on_scene),
        "close": _duration(first_report, incident.closed_at),
    }
    volunteers = sum(1 for a, _, _ in assignments if a.volunteer_id is not None)
    resources = [
        [
            (unit.name_ar if unit else "—"),
            resource.label,
            resource.kind,
            assignment.status,
            assignment.created_at.strftime("%Y-%m-%d %H:%M"),
            assignment.on_scene_at.strftime("%H:%M") if assignment.on_scene_at else "—",
        ]
        for assignment, resource, unit in assignments
        if resource is not None
    ]
    timeline = [[e.at.strftime("%Y-%m-%d %H:%M"), e.kind] for e in events]
    figures = {
        "reports": len(members),
        "reporters": len({m.user_id for m in members}),
        "severity": incident.severity if incident.severity is not None else "—",
        "level": incident.op_level.value,
        **{k: casualties.get(k, 0) for k in ("rescued", "injured", "deceased", "evacuated")},
    }
    figures_ar = _table(
        ["المؤشر", "القيمة"],
        [
            ["عدد البلاغات", str(figures["reports"])],
            ["عدد المبلّغين", str(figures["reporters"])],
            ["الأولوية القصوى", str(figures["severity"])],
            ["المستوى العملياتي", str(figures["level"])],
            ["تم إنقاذهم", str(figures["rescued"])],
            ["مصابون", str(figures["injured"])],
            ["وفيات", str(figures["deceased"])],
            ["تم إجلاؤهم", str(figures["evacuated"])],
            ["متطوعون مكلّفون", str(volunteers)],
            ["أول تكليف بعد البلاغ الأول", times["assign"] or "—"],
            ["الوصول إلى المكان بعد البلاغ الأول", times["scene"] or "—"],
            ["الإغلاق بعد البلاغ الأول", times["close"] or "—"],
        ],
    )
    figures_fr = _table(
        ["Indicateur", "Valeur"],
        [
            ["Signalements", str(figures["reports"])],
            ["Personnes ayant signalé", str(figures["reporters"])],
            ["Priorité maximale", str(figures["severity"])],
            ["Niveau opérationnel", str(figures["level"])],
            ["Personnes secourues", str(figures["rescued"])],
            ["Blessés", str(figures["injured"])],
            ["Décès", str(figures["deceased"])],
            ["Personnes évacuées", str(figures["evacuated"])],
            ["Volontaires engagés", str(volunteers)],
            ["Premier engagement après le premier signalement", times["assign"] or "—"],
            ["Arrivée sur place après le premier signalement", times["scene"] or "—"],
            ["Clôture après le premier signalement", times["close"] or "—"],
        ],
    )
    resources_ar = _table(["الوحدة", "الوسيلة", "النوع", "الحالة", "التكليف", "في المكان"], resources)
    resources_fr = _table(["Unité", "Moyen", "Type", "État", "Engagé", "Sur place"], resources)
    timeline_ar = _table(["الوقت", "الحدث"], timeline)
    timeline_fr = _table(["Heure", "Événement"], timeline)
    summary_ar, summary_fr = _place(evaluation.get("summary"))
    lessons_ar, lessons_fr = _place(evaluation.get("lessons"))
    summary = {
        "ar": "\n\n".join(
            p
            for p in (
                summary_ar,
                "### الأرقام\n\n" + figures_ar,
                "### الوسائل المستعملة\n\n" + resources_ar if resources_ar else "",
                "### الخط الزمني\n\n" + timeline_ar if timeline_ar else "",
            )
            if p
        ),
        "fr": "\n\n".join(
            p
            for p in (
                summary_fr,
                "### Chiffres\n\n" + figures_fr,
                "### Moyens engagés\n\n" + resources_fr if resources_fr else "",
                "### Chronologie\n\n" + timeline_fr if timeline_fr else "",
            )
            if p
        ),
    }
    label = CATEGORY_LABELS.get(incident.category, CATEGORY_LABELS["other"])
    day = incident.opened_at.date().isoformat()
    title = (
        {"ar": incident.title, "fr": incident.title}
        if incident.title and len(incident.title) >= 3
        else {"ar": f"{label['ar']} — {day}", "fr": f"{label['fr'].capitalize()} — {day}"}
    )
    area = await session.scalar(
        text("SELECT ST_AsGeoJSON(ST_Multi(area::geometry)) FROM ops.incident WHERE id = :id AND area IS NOT NULL"),
        {"id": incident.id},
    )
    fields = s.EntryIn.model_validate(
        {
            "title": title,
            "event_type": incident.category,
            "started_at": first_report if first_report < incident.opened_at else incident.opened_at,
            "ended_at": incident.closed_at,
            "gouvernorats": [incident.gouvernorat_code] if incident.gouvernorat_code else [],
            "geometry": json.loads(area) if area else None,
            "incident_ids": [incident.id],
            "summary": summary,
            "lessons": {"ar": lessons_ar, "fr": lessons_fr},
            "access": "gouvernorat",
        }
    )
    if not covers(principal, fields.gouvernorats):
        # A national incident (no gouvernorat) reviewed by regional staff stays in their gouvernorat.
        fields.gouvernorats = [principal.gouvernorat_code] if principal.gouvernorat_code else []
    return await create(session, principal, fields)
