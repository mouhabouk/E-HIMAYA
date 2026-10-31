"""Dictation of free-text fields (phase D, review point 19, docs/phase-d/design-d.md §5).

A microphone sits next to the free-text fields of the dashboard and the staff app (notes, descriptions, the log); never
next to a number, a date, a choice or a name. The recording goes to the local transcription service (faster-whisper,
services/ai) and is deleted at once, as for the commander's voice messages (AI5b). The text is put into the field for
the user to correct; when the form is saved, the app sends the text the user kept (``/kept``), and the pair gives the
word error rate per field: the corrections log the AI administrator reads (``GET /api/v1/staff/dictation``).

The texts are encrypted at rest and leave the database only for the AI administrator, field by field.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.ratelimit import enforce, opaque
from app.core.security import REALM_ROLES, Principal, Realm, Role, require_roles
from app.core.storage import get_store
from app.modules.ai.client import get_ai_client
from app.modules.ai.models import Dictation
from app.modules.audit import service as audit
from app.modules.decision import voice

router = APIRouter(prefix="/api/v1/staff/dictation", tags=["dictation"])
AnyStaff = Annotated[Principal, Depends(require_roles(*REALM_ROLES[Realm.STAFF]))]
AiAdmin = Annotated[Principal, Depends(require_roles(Role.AI_ADMIN))]
Session = Annotated[AsyncSession, Depends(get_session)]

FIELD_PATTERN = r"^[a-z0-9_.]{2,60}$"
PER_HOUR = 120
WINDOW_S = 3600
MAX_TEXT = 4000

# A neutral hint: the words of the field reports, so Whisper spells the trade's words right.
PROMPTS = {
    "ar": "ملاحظات الحماية المدنية بتونس: حريق، دخان، حادث مرور، إسعاف، شاحنة إطفاء، صهريج، مصابين، إجلاء، المعتمدية.",
    "fr": "Notes de la Protection civile tunisienne : incendie, fumée, accident, ambulance, fourgon-pompe, blessés.",
}


class DictationOut(BaseModel):
    dictation_id: uuid.UUID
    text: str
    language: str | None
    model: str | None
    duration_s: float


class KeptIn(BaseModel):
    text: str = Field(max_length=MAX_TEXT)


class KeptOut(BaseModel):
    words: int
    word_errors: int
    wer: float | None


class FieldStat(BaseModel):
    field: str
    dictations: int
    kept: int
    mean_wer: float | None


class CorrectionRow(BaseModel):
    id: uuid.UUID
    field: str
    language: str | None
    model: str | None
    created_at: datetime
    text: str | None
    kept: str | None
    wer: float | None


class DictationLog(BaseModel):
    fields: list[FieldStat]
    items: list[CorrectionRow]


async def _body(request: Request) -> bytes:
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > voice.MAX_BYTES:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "media_too_large")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post(
    "",
    response_model=DictationOut,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {t: {"schema": {"type": "string", "format": "binary"}} for t in sorted(voice.VOICE_TYPES)},
        }
    },
)
async def dictate(
    principal: AnyStaff,
    session: Session,
    request: Request,
    field: Annotated[str, Query(pattern=FIELD_PATTERN)],
    lang: Annotated[Literal["ar", "fr"], Query()] = "ar",
) -> DictationOut:
    """A recording of at most 60 s as the raw request body: the text for the field, the audio deleted."""
    await enforce(f"dictation:{opaque(principal.subject)}", PER_HOUR, WINDOW_S)
    content_type = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    result = await voice.run_transcription(
        get_ai_client(), get_store(), await _body(request), content_type, lang, PROMPTS.get(lang), "dictation"
    )
    language = result.get("language")
    row = Dictation(
        id=uuid.uuid4(),
        actor=audit.actor_of(principal),
        field=field,
        language=language if language in ("ar", "fr", "en") else None,
        model=str(result.get("model") or "whisper"),
        duration_s=float(result.get("duration_s") or 0.0),
        text=str(result.get("text") or "").strip()[:MAX_TEXT],
    )
    session.add(row)
    await session.commit()
    assert row.text is not None
    return DictationOut(
        dictation_id=row.id, text=row.text, language=row.language, model=row.model, duration_s=row.duration_s or 0.0
    )


@router.post("/{dictation_id}/kept", response_model=KeptOut)
async def kept(principal: AnyStaff, session: Session, dictation_id: uuid.UUID, body: KeptIn) -> KeptOut:
    """The text the user kept once the form is saved: the word errors against the model's text. Once."""
    row = await session.scalar(select(Dictation).where(Dictation.id == dictation_id).with_for_update())
    if row is None or row.actor != audit.actor_of(principal):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "dictation_not_found")
    if row.corrected_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "dictation_already_kept")
    reference, hypothesis = voice.words_of(body.text), voice.words_of(row.text or "")
    errors = voice.word_errors(reference, hypothesis)
    row.kept = body.text.strip()
    row.wer = round(errors / len(reference), 4) if reference else None
    row.corrected_at = datetime.now(UTC)
    out = KeptOut(words=len(reference), word_errors=errors, wer=row.wer)
    await session.commit()
    return out


@router.get("", response_model=DictationLog)
async def corrections_log(
    principal: AiAdmin,
    session: Session,
    field: Annotated[str | None, Query(pattern=FIELD_PATTERN)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> DictationLog:
    """The corrections log: the error rate per field, and the latest pairs (of one field when asked). Audited."""
    stats = (
        await session.execute(
            select(
                Dictation.field,
                func.count(Dictation.id),
                func.count(Dictation.corrected_at),
                func.avg(Dictation.wer),
            )
            .group_by(Dictation.field)
            .order_by(Dictation.field)
        )
    ).all()
    query = select(Dictation).order_by(Dictation.created_at.desc()).limit(limit)
    if field is not None:
        query = query.where(Dictation.field == field)
    rows = list(await session.scalars(query))
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="dictation.read",
        target=f"dictation:{field or '*'}",
        details={"count": len(rows)},
    )
    await session.commit()
    return DictationLog(
        fields=[
            FieldStat(field=f, dictations=n, kept=k, mean_wer=round(float(w), 4) if w is not None else None)
            for f, n, k, w in stats
        ],
        items=[
            CorrectionRow(
                id=r.id,
                field=r.field,
                language=r.language,
                model=r.model,
                created_at=r.created_at,
                text=r.text,
                kept=r.kept,
                wer=r.wer,
            )
            for r in rows
        ],
    )
