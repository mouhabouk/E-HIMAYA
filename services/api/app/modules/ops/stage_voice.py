"""A spoken word at every step of the mission (Yamen, 2026-11-01): from «غادرت الوحدة» on, the team leader holds the
microphone, says what the team sees ("الدخان كثيف، الطريق مغلق، نسلك الطريق الثانوية"), and the room reads it on the
incident's timeline under the step the team was at.

1. ``POST /crew/missions/{id}/stage-voice``: the audio is transcribed by the local service and deleted, as every
   spoken text of the staff app; the transcript is then tidied (spelling, the trade's words, punctuation, hesitations)
   by the local language model, which may not add, drop or change a fact (``services/ai`` ``/v1/tidy``); without the
   model, simple rules do the clean-up. Nothing is sent to the room yet.
2. The leader reads and corrects the text on the phone, then ``POST /crew/missions/{id}/stage-message`` sends it: a
   text of the scene tagged with the step, measured against the transcript (word error rate) and kept as a learning
   sample like the commander's voice messages. A typed message takes the same road without ``voice_id``.

The step is the mission's own, read on the server when the message arrives (a message the phone kept while out of
coverage is filed under the step the mission had reached, writes being applied in order).
"""

import re
import uuid
from typing import Literal

import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal
from app.core.storage import ObjectStore
from app.modules.ai.client import AiClient, AiRejected, AiUnavailable
from app.modules.audit import service as audit
from app.modules.ops import crew, crew_flow, schemas
from app.modules.ops.models import Assignment, FieldAttachment

log = structlog.get_logger()

Stage = Literal["en_route", "on_scene", "left_scene", "at_hospital", "available", "back_at_unit"]
#: The steps after leaving the unit, latest first, with the time that marks each.
_REACHED: tuple[tuple[Stage, str], ...] = (
    ("back_at_unit", "back_at_unit_at"),
    ("available", "available_at"),
    ("at_hospital", "at_hospital_at"),
    ("left_scene", "left_scene_at"),
    ("on_scene", "on_scene_at"),
    ("en_route", "en_route_at"),
)
STAGES: tuple[Stage, ...] = tuple(reversed([s for s, _ in _REACHED]))

_FILLERS = re.compile(
    r"(?<![\w])(?:euh+|heu+|hum+|bah|ben|e+h+|امم+|ام+|اه+|ااه+|إيه+|يعني يعني)(?![\w])[،,]?\s*", re.IGNORECASE
)
_TWICE = re.compile(r"(?<![\w])(\w+)(?:\s+\1)+(?![\w])")
_SPACES = re.compile(r"\s+")
_SPACE_BEFORE = re.compile(r"\s+([،,.!?؟؛:])")


def stage_of(assignment: Assignment) -> Stage | None:
    """The last step the mission reached after leaving the unit; None before «غادرت الوحدة» or once cancelled."""
    if assignment.status == "cancelled":
        return None
    for stage, field in _REACHED:
        if getattr(assignment, field) is not None:
            return stage
    return None


def rules_tidy(text: str) -> str:
    """The clean-up without the language model: hesitations, a word said twice, spaces, a closing full stop."""
    out = _FILLERS.sub("", text)
    out = _TWICE.sub(r"\1", out)
    out = _SPACE_BEFORE.sub(r"\1", _SPACES.sub(" ", out)).strip(" ،,")
    if out and out[-1] not in ".!?؟":
        out += "."
    return out


async def tidy(client: AiClient | None, text: str, lang: str | None) -> tuple[str, Literal["model", "rules"]]:
    if not text.strip():
        return "", "rules"
    if client is not None:
        try:
            answer = await client.tidy(text, lang)
        except (AiUnavailable, AiRejected) as exc:
            log.info("stage_voice.tidy_unavailable", error=str(exc))
        else:
            if answer.get("tidied") and str(answer.get("text") or "").strip():
                return str(answer["text"]).strip()[:1000], "model"
    return rules_tidy(text)[:1000], "rules"


async def _left(session: AsyncSession, principal: Principal, assignment_id: uuid.UUID) -> tuple[Assignment, Stage]:
    assignment, _ = await crew._mission(session, principal, assignment_id)
    stage = stage_of(assignment)
    if stage is None:
        detail = "mission_over" if assignment.status == "cancelled" else "not_left_yet"
        raise HTTPException(status.HTTP_409_CONFLICT, detail)
    return assignment, stage


async def transcribe(
    session: AsyncSession,
    principal: Principal,
    assignment_id: uuid.UUID,
    client: AiClient | None,
    store: ObjectStore,
    data: bytes,
    content_type: str,
    lang: str,
) -> schemas.StageVoiceOut:
    _assignment, stage = await _left(session, principal, assignment_id)
    heard = await crew_flow.transcribe(session, principal, assignment_id, client, store, data, content_type, lang)
    text, by = await tidy(client, heard.text, heard.language or lang)
    return schemas.StageVoiceOut(
        voice_id=heard.voice_id,
        transcript=heard.text,
        text=text,
        tidied_by=by,
        stage=stage,
        language=heard.language,
        duration_s=heard.duration_s,
    )


async def send(
    session: AsyncSession, principal: Principal, assignment_id: uuid.UUID, body: schemas.StageMessageIn
) -> Assignment:
    assignment, stage = await _left(session, principal, assignment_id)
    if await crew._seen(session, body.client_id) is not None:
        return assignment
    await crew._room_for_attachment(session, assignment)
    spoken = await crew_flow._corrected(session, principal, assignment, body.voice_id, body.text)
    crew._event(session, principal, body, "attachment", assignment, {"kind": "text", "stage": stage})
    session.add(
        FieldAttachment(
            incident_id=assignment.incident_id,
            assignment_id=assignment.id,
            kind="text",
            body=body.text,
            stage=stage,
            spoken=spoken is not None,
            created_by=principal.subject,
            created_by_name=audit.name_of(principal),
            device_at=body.device_at,
        )
    )
    crew._timeline(
        session, assignment, "field_attachment", crew._who(principal), media="stage", stage=stage, spoken=bool(spoken)
    )
    await crew._announce(session, assignment)
    return assignment
