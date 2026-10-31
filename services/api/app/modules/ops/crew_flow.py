"""The mission flow of the staff app after Yamen's review (phase F, docs/phase-f/design-f.md).

The round button gives the same steps as before (``crew.step`` and ``crew.milestone``); this module adds what the
review brought: the nature the team confirms, a step skipped with its reason, the end without intervention, the toll
and the intervention report written at the end (typed, or spoken and corrected), the point the room picks on the map,
and a mission the team opens from the field. Every write carries the phone's id, as in ``crew``: sent twice, applied
once.
"""

import uuid
from typing import Any

from fastapi import HTTPException, status
from geoalchemy2 import Geography
from sqlalchemy import cast, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal
from app.core.storage import ObjectStore
from app.modules.ai.client import AiClient
from app.modules.audit import service as audit
from app.modules.decision import voice
from app.modules.decision.schemas import VoiceOut
from app.modules.ops import crew, interventions, resources, schemas
from app.modules.ops import service as incidents
from app.modules.ops.models import Assignment, FieldReport, Incident, Resource
from app.modules.reports import intake
from app.modules.reports.domain import Category
from app.modules.reports.models import Report
from app.modules.reports.schemas import LocationIn, RoomReportIn

#: The report category a nature chosen by the team files under (the nature itself is kept on the assignment).
NATURE_CATEGORY: dict[str, Category] = {
    "fire": Category.FIRE,
    "flood": Category.FLOOD,
    "traffic_accident": Category.TRAFFIC_ACCIDENT,
    "medical": Category.MEDICAL,
    "drowning": Category.DROWNING,
    "landslide": Category.LANDSLIDE,
    "chemical_leak": Category.CHEMICAL_LEAK,
}

#: The words of a toll or an intervention report, told to Whisper as for the commander's orders (``voice.PROMPTS``).
FIELD_PROMPTS = {
    "ar": (
        "محضر تدخل الحماية المدنية: حريق منزل، حادث مرور، فيضان، إنقاذ، جريح، جرحى، وفاة، متوفى، إسعاف، نقل إلى "
        "المستشفى، أضرار مادية، سيارة، شاحنة، محل، غابة، إخماد، تبريد، الوحدة، الطريق الوطنية"
    ),
    "fr": (
        "Procès-verbal d'intervention de la Protection civile : incendie, accident de la circulation, inondation, "
        "sauvetage, blessé, décès, évacuation vers l'hôpital, dégâts matériels, véhicule, local, extinction."
    ),
}


async def nature(
    session: AsyncSession, principal: Principal, assignment_id: uuid.UUID, body: schemas.NatureIn
) -> Assignment:
    assignment, _ = await crew._mission(session, principal, assignment_id)
    if await crew._seen(session, body.client_id) is not None:
        return assignment
    crew._event(session, principal, body, "nature", assignment, {"nature": body.nature})
    if assignment.crew_nature != body.nature:
        assignment.crew_nature = body.nature
        crew._timeline(session, assignment, "crew_nature", crew._who(principal), nature=body.nature)
        await crew._announce(session, assignment)
    return assignment


async def skip(
    session: AsyncSession, principal: Principal, assignment_id: uuid.UUID, body: schemas.SkipIn
) -> Assignment:
    """A step the mission does not need (no one to take to hospital, no stop on the way back), with why."""
    assignment, _ = await crew._mission(session, principal, assignment_id)
    if await crew._seen(session, body.client_id) is not None:
        return assignment
    if assignment.status not in ("on_scene", "released") or assignment.left_scene_at is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    field = f"{body.step}_at"
    if getattr(assignment, field) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "step_done")
    crew._event(session, principal, body, "skip", assignment, {"step": body.step, "reason": body.reason})
    assignment.skipped = {**(assignment.skipped or {}), body.step: body.reason}
    crew._timeline(session, assignment, "crew_skip", crew._who(principal), step=body.step, reason=body.reason)
    await crew._announce(session, assignment)
    return assignment


async def no_intervention(
    session: AsyncSession, principal: Principal, assignment_id: uuid.UUID, body: schemas.NoInterventionIn
) -> Assignment:
    """The mission ends without intervention (false alarm, put out before the team came...): cancelled before the
    arrival, released after it. The times already given stay, so the arrival time still counts."""
    assignment, _ = await crew._mission(session, principal, assignment_id)
    if await crew._seen(session, body.client_id) is not None:
        return assignment
    if assignment.status in ("released", "cancelled"):
        raise HTTPException(status.HTTP_409_CONFLICT, "mission_over")
    crew._event(session, principal, body, "no_intervention", assignment, {"reason": body.reason})
    at = crew.device_time(body, assignment)
    assignment.no_intervention_reason = body.reason
    target = "released" if assignment.status == "on_scene" else "cancelled"
    await interventions._set_assignment_status(
        session, assignment, target, crew._who(principal), at=at, source=crew.VIA.get()
    )
    crew._timeline(session, assignment, "crew_no_intervention", crew._who(principal), reason=body.reason)
    await crew._announce(session, assignment)
    if assignment.resource_id is not None:
        await resources.announce(session, assignment.resource_id)
    return assignment


async def transcribe(
    session: AsyncSession,
    principal: Principal,
    assignment_id: uuid.UUID,
    client: AiClient | None,
    store: ObjectStore,
    data: bytes,
    content_type: str,
    lang: str,
) -> VoiceOut:
    """A spoken toll or report: transcribed, the audio deleted, the text sent back for the leader to correct."""
    assignment, _ = await crew._mission(session, principal, assignment_id)
    incident = await session.get(Incident, assignment.incident_id)
    assert incident is not None
    return await voice.transcribe(
        session, principal, incident, client, store, data, content_type, lang, prompts=FIELD_PROMPTS
    )


async def _incident_category(session: AsyncSession, assignment: Assignment) -> str:
    incident = await session.get(Incident, assignment.incident_id)
    return incident.category if incident is not None else Category.OTHER.value


async def _corrected(
    session: AsyncSession, principal: Principal, assignment: Assignment, voice_id: uuid.UUID | None, text: str | None
) -> dict[str, Any] | None:
    """The transcript a text was corrected from: measured and learnt from, as the commander's voice messages."""
    if voice_id is None or not text:
        return None
    incident = await session.get(Incident, assignment.incident_id)
    if incident is None:
        return None
    await voice.corrected(session, principal, incident, voice_id, text)
    return {"voice_id": str(voice_id)}


async def toll(
    session: AsyncSession, principal: Principal, assignment_id: uuid.UUID, body: schemas.TollIn
) -> Assignment:
    """Material damage and the description of the incident, at the end of the mission (the people are the live
    counters, ``crew.casualties``)."""
    assignment, _ = await crew._mission(session, principal, assignment_id)
    if await crew._seen(session, body.client_id) is not None:
        return assignment
    crew._event(session, principal, body, "toll", assignment, {"damage": body.damage})
    answers: dict[str, Any] = {"damage": body.damage}
    spoken = await _corrected(session, principal, assignment, body.voice_id, body.description)
    if spoken is not None:
        answers["voice"] = spoken
    session.add(
        FieldReport(
            incident_id=assignment.incident_id,
            assignment_id=assignment.id,
            kind="toll",
            category=await _incident_category(session, assignment),
            answers=answers,
            note=body.description,
            author=principal.subject,
            author_name=audit.name_of(principal),
            device_at=body.device_at,
        )
    )
    crew._timeline(session, assignment, "crew_toll", crew._who(principal), damage=body.damage)
    await crew._announce(session, assignment)
    return assignment


async def intervention_report(
    session: AsyncSession, principal: Principal, assignment_id: uuid.UUID, body: schemas.InterventionReportIn
) -> Assignment:
    """The intervention report (محضر التدخل), from the mission's page at any time."""
    assignment, _ = await crew._mission(session, principal, assignment_id)
    if await crew._seen(session, body.client_id) is not None:
        return assignment
    crew._event(session, principal, body, "report", assignment)
    spoken = await _corrected(session, principal, assignment, body.voice_id, body.text)
    session.add(
        FieldReport(
            incident_id=assignment.incident_id,
            assignment_id=assignment.id,
            kind="report",
            category=await _incident_category(session, assignment),
            answers={"voice": spoken} if spoken is not None else None,
            note=body.text,
            author=principal.subject,
            author_name=audit.name_of(principal),
            device_at=body.device_at,
        )
    )
    crew._timeline(session, assignment, "crew_report", crew._who(principal))
    await crew._announce(session, assignment)
    return assignment


async def open_mission(session: AsyncSession, principal: Principal, body: schemas.OpenMissionIn) -> Assignment:
    """A mission the team opens from the field (a crash on its way): a report entered for the room, its incident, and
    the team's vehicle on it. The room sees the new incident at once."""
    seen = await crew._seen(session, body.client_id)
    if seen is not None and seen.assignment_id is not None:
        found = await session.get(Assignment, seen.assignment_id)
        if found is not None:
            return found
    shift = await crew.open_shift(session, principal)
    if shift is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no_open_shift")
    resource = await session.get(Resource, shift.resource_id, with_for_update=True)
    if resource is None or resource.status != "available":
        raise HTTPException(status.HTTP_409_CONFLICT, "resource_busy")
    category = NATURE_CATEGORY.get(body.nature, Category.OTHER)
    report_id = await intake.create(
        session,
        principal,
        RoomReportIn(
            category=category,
            location=LocationIn(lat=body.lat, lon=body.lon, accuracy_m=None),
            channel="other",
            text=body.note,
        ),
    )
    report = await session.get(Report, report_id, with_for_update=True)
    assert report is not None
    actor = crew._who(principal)
    incident = await incidents._create(session, report, actor)
    await incidents._attach(session, report, incident, actor, "field")
    assignment = Assignment(
        incident_id=incident.id,
        kind="resource",
        resource_id=resource.id,
        status="ordered",
        created_by=actor,
        shift_id=shift.id,
        crew_count=shift.crew_size,
        crew_nature=body.nature,
        field_initiated=True,
        target_location=cast(func.ST_SetSRID(func.ST_MakePoint(body.lon, body.lat), 4326), Geography),
    )
    session.add(assignment)
    resource.status, resource.updated_at = "assigned", crew._now()
    await session.flush()
    await session.refresh(assignment)
    crew._event(session, principal, body, "open", assignment, {"nature": body.nature})
    crew._timeline(session, assignment, "assignment_created", actor, resource=resource.label, field_initiated=True)
    await crew._announce(session, assignment)
    await resources.announce(session, resource.id)
    return assignment


async def set_target(
    session: AsyncSession, principal: Principal, assignment_id: uuid.UUID, body: schemas.TargetIn
) -> Assignment:
    """The room picks the point the team must reach on the map (it may differ from the incident's centre)."""
    assignment = await session.get(Assignment, assignment_id, with_for_update=True)
    if assignment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    await incidents.get_in_scope(session, principal, assignment.incident_id)
    if assignment.status in ("released", "cancelled"):
        raise HTTPException(status.HTTP_409_CONFLICT, "mission_over")
    assignment.target_location = cast(func.ST_SetSRID(func.ST_MakePoint(body.lon, body.lat), 4326), Geography)
    assignment.target_note = body.note
    crew._timeline(
        session, assignment, "assignment_target", crew._who(principal), lat=round(body.lat, 6), lon=round(body.lon, 6)
    )
    await crew._announce(session, assignment)
    return assignment
