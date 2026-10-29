"""The commander's voice messages (AI5b, docs/phase-ai5/design-ai5.md §7).

The commander presses the microphone on the incident page and speaks an order or a question in Tunisian Derja, Arabic
or French. The audio goes to the local transcription service (faster-whisper, services/ai) with the vocabulary of the
orders as its hint, and is deleted at once: only the transcript is kept, encrypted. The transcript is shown in the
command box for the commander to correct; nothing is sent until the commander sends it. When the corrected text is
sent (``CommandTextIn.voice_id``), it is kept next to the transcript with the word errors between the two:

* the measure: the word error rate on the commanders' own words, in the commander model card;
* the learning: one sample of the self-learning centre (``source = 'voice'``, anonymised, labelled by the commander),
  so the vocabulary hint and, later, the transcription model are improved from the corrections.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal
from app.core.storage import ObjectStore
from app.modules.ai.client import AiClient, AiRejected, AiUnavailable
from app.modules.audit import service as audit
from app.modules.decision import orders
from app.modules.decision import schemas as s
from app.modules.decision.models import CommandVoice
from app.modules.learning.anonymize import anonymize
from app.modules.learning.models import Sample
from app.modules.learning.samples import split_of
from app.modules.ops.models import Incident

log = structlog.get_logger()

SOURCE_VOICE = "voice"
VOICE_TYPES = frozenset({"audio/webm", "audio/ogg", "audio/mp4", "audio/aac", "audio/mpeg", "audio/wav", "audio/x-wav"})
MAX_BYTES = 4 * 1024 * 1024
MAX_SECONDS = 60.0

# The words the commander's orders are made of: Whisper spells them better when it is told them (initial prompt).
PROMPTS = {
    "ar": (
        "أوامر قائد العمليات في الحماية المدنية بتونس: ابعثوا زوز شاحنات إطفاء، صهريج ماء، سيارة إسعاف، كميون، "
        "فوڨون، قارب، درون، رافعة، نبّهوا السكان، ارفعوا المستوى إلى الأزمة، الكارثة، جيبوا متطوعين، "
        "عيطوا للوالي، المسلك الأقرب، كم صهريج متاح؟"
    ),
    "fr": (
        "Ordres du commandant des opérations, Protection civile tunisienne : envoyez deux fourgons-pompes, "
        "un camion-citerne, une ambulance, un bateau, un drone, alertez la population, passez au niveau crise, "
        "catastrophe, mobilisez des volontaires, appelez le gouverneur, l'itinéraire le plus court."
    ),
}


def words_of(text: str) -> list[str]:
    return orders.normalise(text).split()


def word_errors(reference: list[str], hypothesis: list[str]) -> int:
    """Substitutions, insertions and deletions turning the transcript into the corrected text (word level)."""
    previous = list(range(len(hypothesis) + 1))
    for i, ref in enumerate(reference, start=1):
        current = [i] + [0] * len(hypothesis)
        for j, hyp in enumerate(hypothesis, start=1):
            current[j] = min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ref != hyp))
        previous = current
    return previous[-1]


async def transcribe(
    session: AsyncSession,
    principal: Principal,
    incident: Incident,
    client: AiClient | None,
    store: ObjectStore,
    data: bytes,
    content_type: str,
    lang: str,
) -> s.VoiceOut:
    if content_type not in VOICE_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "unsupported_media_type")
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "audio_undecodable")
    if client is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "transcription_unavailable")
    key = f"command-voice/{uuid.uuid4().hex}"
    await store.put(key, data, content_type)
    try:
        result: dict[str, Any] = await client.transcribe(
            store.presign_get(key, expires_s=600, internal=True), language=lang, prompt=PROMPTS.get(lang)
        )
    except AiUnavailable as exc:
        log.warning("command.voice_unavailable", error=str(exc))
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "transcription_unavailable") from exc
    except AiRejected as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "audio_undecodable") from exc
    finally:
        # The audio is never kept.
        await store.delete(key)
    duration = float(result.get("duration_s") or 0.0)
    if duration > MAX_SECONDS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "audio_too_long")
    text = str(result.get("text") or "").strip()[:1000]
    if not text:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "nothing_heard")
    language = result.get("language")
    row = CommandVoice(
        id=uuid.uuid4(),
        incident_id=incident.id,
        lang=language if language in ("ar", "fr", "en") else None,
        model=str(result.get("model") or "whisper"),
        duration_s=duration,
        transcript=text,
        created_by=audit.actor_of(principal),
    )
    session.add(row)
    await session.flush()
    return s.VoiceOut(voice_id=row.id, text=text, language=row.lang, model=row.model, duration_s=duration)


async def corrected(
    session: AsyncSession, principal: Principal, incident: Incident, voice_id: uuid.UUID, text: str
) -> None:
    """The text the commander sent after correcting a transcript: the measure and a learning sample."""
    row = await session.scalar(select(CommandVoice).where(CommandVoice.id == voice_id).with_for_update())
    actor = audit.actor_of(principal)
    if row is None or row.incident_id != incident.id or row.created_by != actor:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "voice_not_found")
    if row.sent_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "voice_already_sent")
    reference, hypothesis = words_of(text), words_of(row.transcript)
    row.corrected = text
    row.words = len(reference)
    row.word_errors = word_errors(reference, hypothesis)
    row.sent_at = datetime.now(UTC)
    group = str(incident.id)
    session.add(
        Sample(
            source=SOURCE_VOICE,
            source_id=str(row.id),
            group_key=group,
            text=anonymize(text),
            label={
                "transcript": anonymize(row.transcript),
                "lang": row.lang,
                "words": row.words,
                "word_errors": row.word_errors,
            },
            label_origin="commander",
            split=split_of(group),
            labelled_by=actor,
        )
    )
    await session.flush()
