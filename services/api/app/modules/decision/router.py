"""Decision support endpoints (docs/api/phase-7-contract.md §3). Incidents are read in the staff member's scope
(404 outside it, like every incident endpoint); nothing here changes an incident except the assistant's timeline
entry, which is audited."""

import math
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.ratelimit import enforce, opaque
from app.core.security import Principal, require_roles
from app.core.storage import get_store
from app.modules.ai import settings as ai_settings
from app.modules.ai.client import get_ai_client
from app.modules.decision import assistant, command, context, recommendations, responders, routing, voice
from app.modules.decision import schemas as s
from app.modules.decision.models import CommandDecision
from app.modules.ops import service as incidents
from app.modules.reports.staff_router import READ_ROLES

router = APIRouter(prefix="/api/v1/staff", tags=["staff", "decision"])

StaffReader = Annotated[Principal, Depends(require_roles(*READ_ROLES))]
Session = Annotated[AsyncSession, Depends(get_session)]

# Per staff member: routing calls (map clicks) and recommendation refreshes, each one a routing-engine matrix.
ROUTE_LIMIT, ROUTE_WINDOW_S = 120, 60
RECOMMEND_LIMIT, RECOMMEND_WINDOW_S = 60, 60
ASSISTANT_WINDOW_S = 3600


def parse_point(value: str) -> routing.Point:
    lat_text, sep, lon_text = value.partition(",")
    try:
        lat, lon = float(lat_text), float(lon_text)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_point") from exc
    if not sep or not (math.isfinite(lat) and math.isfinite(lon)) or abs(lat) > 90 or abs(lon) > 180:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_point")
    point = routing.Point(lat, lon)
    if not point.covered():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "out_of_coverage")
    return point


@router.get("/route", response_model=s.RouteOut)
async def route(
    principal: StaffReader,
    from_: Annotated[str, Query(alias="from", max_length=64, description="lat,lon")],
    to: Annotated[str, Query(max_length=64, description="lat,lon")],
    profile: Literal["car", "truck"] = "car",
) -> s.RouteOut:
    await enforce(f"route:{opaque(principal.subject)}", ROUTE_LIMIT, ROUTE_WINDOW_S)
    result = await routing.route(parse_point(from_), parse_point(to), profile)
    return s.RouteOut.model_validate(result.as_dict())


@router.get("/incidents/{incident_id}/recommendations", response_model=s.Recommendations)
async def get_recommendations(principal: StaffReader, session: Session, incident_id: uuid.UUID) -> s.Recommendations:
    incident = await incidents.get_in_scope(session, principal, incident_id)
    await enforce(f"recommend:{opaque(principal.subject)}", RECOMMEND_LIMIT, RECOMMEND_WINDOW_S)
    situation = await context.gather(session, incident)
    return await recommendations.recommend(session, principal, situation)


@router.get("/incidents/{incident_id}/responders", response_model=s.RespondersOut)
async def get_responders(principal: StaffReader, session: Session, incident_id: uuid.UUID) -> s.RespondersOut:
    incident = await incidents.get_in_scope(session, principal, incident_id)
    situation = await context.gather(session, incident)
    return s.RespondersOut(incident_id=incident.id, items=await responders.suggest(session, principal, situation))


@router.post("/incidents/{incident_id}/assistant", response_model=s.AssistantOut)
async def ask_assistant(
    principal: StaffReader, session: Session, incident_id: uuid.UUID, body: s.AssistantIn
) -> s.AssistantOut:
    incident = await incidents.get_in_scope(session, principal, incident_id)
    await enforce(f"assistant:{opaque(principal.subject)}", get_settings().assistant_per_hour, ASSISTANT_WINDOW_S)
    answer = await assistant.ask(session, principal, incident, body)
    await session.commit()
    return answer


# ---------------------------------------------------------------- commander's assistant (AI5a)


async def commander_on(session: AsyncSession) -> None:
    """AI-01: the assistant can be switched off in the AI settings; the classic recommendations stay."""
    if not (await ai_settings.load(session)).assist.commander:
        raise HTTPException(status.HTTP_409_CONFLICT, "commander_off")


@router.get("/incidents/{incident_id}/command", response_model=s.CommandBoard)
async def get_command_board(principal: StaffReader, session: Session, incident_id: uuid.UUID) -> s.CommandBoard:
    """Numbered proposals for the commander, each kept with the situation it was made in (refreshed on each call)."""
    incident = await incidents.get_in_scope(session, principal, incident_id)
    await commander_on(session)
    await enforce(f"recommend:{opaque(principal.subject)}", RECOMMEND_LIMIT, RECOMMEND_WINDOW_S)
    out = await command.board(session, principal, incident)
    await session.commit()
    return out


@router.post("/incidents/{incident_id}/command", response_model=s.CommandTextOut)
async def post_command_text(
    principal: StaffReader, session: Session, incident_id: uuid.UUID, body: s.CommandTextIn
) -> s.CommandTextOut:
    """A typed or dictated text: a question is answered from sources, an order becomes a proposal card."""
    incident = await incidents.get_in_scope(session, principal, incident_id)
    await commander_on(session)
    command.require_commander(principal)
    await enforce(f"command:{opaque(principal.subject)}", get_settings().assistant_per_hour, ASSISTANT_WINDOW_S)
    out = await command.command_text(session, principal, incident, body)
    await session.commit()
    return out


@router.post("/command/decisions/{decision_id}", response_model=s.CommandCard)
async def decide_command(
    principal: StaffReader, session: Session, decision_id: uuid.UUID, body: s.DecideIn
) -> s.CommandCard:
    """Adopt, adopt modified or reject a proposal. Nothing is executed: the card's actions open the usual flows."""
    row = await session.get(CommandDecision, decision_id, with_for_update=True)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    await incidents.get_in_scope(session, principal, row.incident_id)
    await commander_on(session)
    command.require_commander(principal)
    out = await command.decide(session, principal, row, body)
    await session.commit()
    return out


async def _voice_body(request: Request) -> bytes:
    """The recording, refused as soon as it grows past ``voice.MAX_BYTES``."""
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > voice.MAX_BYTES:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "media_too_large")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post(
    "/incidents/{incident_id}/command/voice",
    response_model=s.VoiceOut,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {t: {"schema": {"type": "string", "format": "binary"}} for t in sorted(voice.VOICE_TYPES)},
        }
    },
)
async def post_command_voice(
    principal: StaffReader,
    session: Session,
    request: Request,
    incident_id: uuid.UUID,
    lang: Annotated[Literal["ar", "fr"], Query()] = "ar",
) -> s.VoiceOut:
    """A voice message as the raw request body (AI5b): transcribed locally, the audio deleted, the text returned for
    the commander to correct; nothing is sent until the commander sends the text."""
    incident = await incidents.get_in_scope(session, principal, incident_id)
    await commander_on(session)
    command.require_commander(principal)
    await enforce(f"command:{opaque(principal.subject)}", get_settings().assistant_per_hour, ASSISTANT_WINDOW_S)
    content_type = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    out = await voice.transcribe(
        session, principal, incident, get_ai_client(), get_store(), await _voice_body(request), content_type, lang
    )
    await session.commit()
    return out
