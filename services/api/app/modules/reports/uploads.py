"""Resumable media uploads (tus 1.0 via tusd) and evidence integrity (NFR-07).

tusd stores the bytes in S3 and calls these hooks:

* ``pre-create``: authorize the upload (same identity as the API: bearer token or device key), check the
  report, kind, type and size, fix the object name and register the media row (``uploading``).
* ``post-finish``: the object is complete; mark the media ``verifying``.
* ``post-terminate``: the client abandoned the upload; mark it ``rejected``.

A background worker then re-reads every finished object, recomputes SHA-256 and compares it with the
hash declared by the device: ``stored`` when they match, ``rejected`` (object deleted) otherwise.
"""

import asyncio
import hmac
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import structlog
from anyio import to_thread
from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.db import get_session
from app.core.events import emit
from app.core.security import get_token_verifier
from app.core.storage import ObjectStore, get_store
from app.modules.ai import pipeline
from app.modules.audit import service as audit
from app.modules.identity.service import resolve_reporter
from app.modules.reports.domain import MEDIA_MAX_BYTES, MEDIA_PER_REPORT, MEDIA_TYPES, MEDIA_UPLOAD_WINDOW_H
from app.modules.reports.models import Media, Report
from app.modules.reports.service import media_out

log = structlog.get_logger()
router = APIRouter(include_in_schema=False)

OBJECT_PREFIX = "uploads/"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class HookRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: str = Field(alias="Type")
    event: dict[str, Any] = Field(alias="Event")


def _reject(status_code: int, code: str) -> dict[str, Any]:
    return {
        "RejectUpload": True,
        "HTTPResponse": {
            "StatusCode": status_code,
            "Body": f'{{"detail":"{code}"}}',
            "Header": {"Content-Type": "application/json"},
        },
    }


def _header(event: dict[str, Any], name: str) -> str | None:
    """A header of the client's tus request, as relayed by tusd in the hook event."""
    headers: dict[str, list[str]] = event.get("HTTPRequest", {}).get("Header") or {}
    for key, values in headers.items():
        if key.lower() == name.lower() and values:
            return values[0]
    return None


async def _pre_create(session: AsyncSession, event: dict[str, Any]) -> dict[str, Any]:
    upload = event.get("Upload", {})
    meta: dict[str, str] = upload.get("MetaData") or {}
    kind, filetype, sha256 = meta.get("kind", ""), meta.get("filetype", ""), meta.get("sha256", "").lower()
    size = upload.get("Size")

    if upload.get("IsPartial") or upload.get("IsFinal"):
        return _reject(400, "concatenation_not_supported")
    if upload.get("SizeIsDeferred") or not isinstance(size, int) or size <= 0:
        return _reject(400, "upload_length_required")
    if kind not in MEDIA_TYPES or filetype not in MEDIA_TYPES[kind]:
        return _reject(415, "unsupported_media_type")
    if size > MEDIA_MAX_BYTES[kind]:
        return _reject(413, "media_too_large")
    if not _SHA256.match(sha256):
        return _reject(400, "invalid_sha256")
    try:
        report_id = uuid.UUID(meta.get("report_id", ""))
    except ValueError:
        return _reject(400, "invalid_report_id")

    authorization = _header(event, "Authorization")
    principal = None
    try:
        if authorization and authorization.lower().startswith("bearer "):
            principal = await to_thread.run_sync(get_token_verifier().verify, authorization[7:].strip())
        reporter = await resolve_reporter(session, principal, _header(event, "X-Device-Key"))
    except HTTPException as exc:
        return _reject(exc.status_code, str(exc.detail))

    report = await session.get(Report, report_id)
    if report is None or report.user_id != reporter.user_id:
        return _reject(404, "report_not_found")
    if datetime.now(UTC) - report.received_at > timedelta(hours=MEDIA_UPLOAD_WINDOW_H):
        return _reject(409, "upload_window_closed")
    count = await session.scalar(
        select(func.count(Media.id)).where(Media.report_id == report_id, Media.status != "rejected")
    )
    if (count or 0) >= MEDIA_PER_REPORT:
        return _reject(409, "too_many_media")

    upload_id = uuid.uuid4().hex
    session.add(
        Media(
            report_id=report_id,
            kind=kind,
            object_key=f"{OBJECT_PREFIX}{upload_id}",
            sha256=sha256,
            bytes=size,
            upload_id=upload_id,
            content_type=filetype,
            status="uploading",
        )
    )
    await session.commit()
    # The device's file name is personal data we do not need: it is not kept in the object metadata.
    return {
        "ChangeFileInfo": {
            "ID": upload_id,
            "MetaData": {"report_id": str(report_id), "kind": kind, "filetype": filetype, "sha256": sha256},
        }
    }


async def _media_by_upload(session: AsyncSession, event: dict[str, Any]) -> Media | None:
    upload_id = str(event.get("Upload", {}).get("ID", "")).split("+", 1)[0]
    if not upload_id:
        return None
    return await session.scalar(select(Media).where(Media.upload_id == upload_id).with_for_update())


async def _post_finish(session: AsyncSession, event: dict[str, Any]) -> dict[str, Any]:
    media = await _media_by_upload(session, event)
    if media is None or media.status != "uploading":
        return {}
    storage = event.get("Upload", {}).get("Storage") or {}
    if storage.get("Key"):
        media.object_key = storage["Key"]
    media.status = "verifying"
    await session.commit()
    return {}


async def _post_terminate(session: AsyncSession, event: dict[str, Any]) -> dict[str, Any]:
    media = await _media_by_upload(session, event)
    if media is not None and media.status == "uploading":
        media.status = "rejected"
        await session.commit()
    return {}


_HANDLERS = {"pre-create": _pre_create, "post-finish": _post_finish, "post-terminate": _post_terminate}


@router.post("/internal/tusd/hooks/{secret}")
async def tusd_hook(
    secret: Annotated[str, Path(max_length=256)],
    body: HookRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    expected = get_settings().tusd_hook_secret
    if expected is None or not hmac.compare_digest(secret.encode(), expected.get_secret_value().encode()):
        raise HTTPException(404, "not_found")
    handler = _HANDLERS.get(body.type)
    if handler is None:
        return {}
    return await handler(session, body.event)


# ---------------------------------------------------------------- verification worker


async def verify_one(sessionmaker: async_sessionmaker[AsyncSession], store: ObjectStore) -> bool:
    """Verify one finished upload. Returns False when nothing was waiting."""
    async with sessionmaker() as session, session.begin():
        media = await session.scalar(
            select(Media)
            .where(Media.status == "verifying")
            .order_by(Media.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if media is None:
            return False
        digest, size = await store.sha256(media.object_key)
        report = await session.get(Report, media.report_id) if media.report_id else None
        if hmac.compare_digest(digest, media.sha256):
            media.status = "stored"
            media.bytes = size
            media.stored_at = datetime.now(UTC)
            if media.report_id is not None:
                # New evidence: re-analyse (transcription of audio/video, credibility, priority).
                await pipeline.enqueue(session, media.report_id)
            await emit(
                session,
                "media.stored",
                {
                    "report_id": str(media.report_id),
                    "gouvernorat_code": report.gouvernorat_code if report else None,
                    "media": media_out(media).model_dump(mode="json"),
                },
            )
        else:
            media.status = "rejected"
            await store.delete(media.object_key, f"{media.object_key}.info")
            await audit.record(
                session,
                actor=audit.SYSTEM_ACTOR,
                action="media.rejected",
                target=f"media:{media.id}",
                reason="sha256_mismatch",
                details={"declared": media.sha256, "computed": digest},
            )
        return True


async def verify_forever(sessionmaker: async_sessionmaker[AsyncSession], idle_s: float = 1.0) -> None:
    while True:
        try:
            worked = await verify_one(sessionmaker, get_store())
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("media.verify_failed")
            worked = False
        if not worked:
            await asyncio.sleep(idle_s)
