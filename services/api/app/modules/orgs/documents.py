"""Institution documents through tus (FR-B-004): versioned uploads with integrity (NFR-07).

The tusd hooks (``reports.uploads``) hand uploads whose metadata says ``target=org_document`` to this
module. Each upload adds a version to a document; it becomes current only once the server has re-read
the object and found the SHA-256 declared by the client (``uploading`` → ``verifying`` → ``stored``).
"""

import hmac
import re
import unicodedata
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import Principal
from app.core.storage import ObjectStore
from app.modules.audit import service as audit
from app.modules.orgs import domain, service
from app.modules.orgs.domain import OrgRole
from app.modules.orgs.models import Document, DocumentVersion, Organization

OBJECT_PREFIX = "uploads/"
NOTE_MAX = 200
FILENAME_MAX = 200
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _clean(value: str, limit: int) -> str | None:
    """Printable text only (no control or bidi-override characters), trimmed."""
    kept = "".join(ch for ch in value if unicodedata.category(ch)[0] != "C").strip()
    return kept[:limit] or None


def clean_filename(raw: str) -> str | None:
    return _clean(raw.replace("\\", "/").rsplit("/", 1)[-1], FILENAME_MAX)


async def pre_create(
    session: AsyncSession, upload: dict[str, Any], meta: dict[str, str], principal: Principal | None
) -> dict[str, Any]:
    """Authorize an upload and register its version. Raises HTTPException with the client's error code."""
    size: int = upload["Size"]
    filetype, sha256 = meta.get("filetype", ""), meta.get("sha256", "").lower()
    note = meta.get("note") or None
    if not _SHA256.match(sha256):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_sha256")
    if note is not None and len(note) > NOTE_MAX:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_note")
    try:
        document_id = uuid.UUID(meta.get("document_id", ""))
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document_not_found") from None
    if principal is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication_required")
    user = await service.get_portal_user(principal, session)

    doc = await session.scalar(select(Document).where(Document.id == document_id).with_for_update())
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document_not_found")
    try:
        await service.membership(session, user, doc.org_id, OrgRole.EDITOR)
    except HTTPException as exc:
        # A non-member must not learn that the document exists.
        if exc.detail == "org_not_found":
            raise HTTPException(status.HTTP_404_NOT_FOUND, "document_not_found") from None
        raise
    if filetype not in domain.DOCUMENT_TYPES[doc.kind]:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "unsupported_media_type")
    if size > domain.document_max_bytes(filetype):
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "document_too_large")

    last = await session.scalar(select(func.max(DocumentVersion.version)).where(DocumentVersion.document_id == doc.id))
    upload_id = uuid.uuid4().hex
    version = DocumentVersion(
        document_id=doc.id,
        version=(last or 0) + 1,
        upload_id=upload_id,
        object_key=f"{OBJECT_PREFIX}{upload_id}",
        filename=clean_filename(meta.get("filename", "")),
        content_type=filetype,
        bytes=size,
        sha256=sha256,
        note=_clean(note, NOTE_MAX) if note else None,
        status="uploading",
        uploaded_by=user.user_id,
        uploaded_by_name=user.display_name,
    )
    session.add(version)
    await session.commit()
    return {
        "ChangeFileInfo": {
            "ID": upload_id,
            "MetaData": {
                "target": "org_document",
                "document_id": str(doc.id),
                "version": str(version.version),
                "filetype": filetype,
                "sha256": sha256,
            },
        }
    }


async def by_upload(session: AsyncSession, upload_id: str) -> DocumentVersion | None:
    return await session.scalar(select(DocumentVersion).where(DocumentVersion.upload_id == upload_id).with_for_update())


async def post_finish(session: AsyncSession, upload_id: str, storage_key: str | None) -> bool:
    version = await by_upload(session, upload_id)
    if version is None:
        return False
    if version.status == "uploading":
        if storage_key:
            version.object_key = storage_key
        version.status = "verifying"
        await session.commit()
    return True


async def post_terminate(session: AsyncSession, upload_id: str) -> bool:
    version = await by_upload(session, upload_id)
    if version is None:
        return False
    if version.status == "uploading":
        version.status = "rejected"
        await session.commit()
    return True


async def verify_one(sessionmaker: async_sessionmaker[AsyncSession], store: ObjectStore) -> bool:
    """Verify one finished document upload. Returns False when nothing was waiting."""
    async with sessionmaker() as session, session.begin():
        version = await session.scalar(
            select(DocumentVersion)
            .where(DocumentVersion.status == "verifying")
            .order_by(DocumentVersion.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if version is None:
            return False
        digest, size = await store.sha256(version.object_key)
        doc = await session.get(Document, version.document_id)
        assert doc is not None
        if hmac.compare_digest(digest, version.sha256):
            version.status = "stored"
            version.bytes = size
            version.stored_at = datetime.now(UTC)
            doc.updated_at = version.stored_at
            org = await session.get(Organization, doc.org_id)
            assert org is not None
            # A new current version can complete the file: the dashboard sees the new completeness.
            await service.touch(session, org)
            await service.org_event(session, org.id)
        else:
            version.status = "rejected"
            await store.delete(version.object_key, f"{version.object_key}.info")
            await audit.record(
                session,
                actor=audit.SYSTEM_ACTOR,
                action="org_document.rejected",
                target=f"org_document:{doc.id}:v{version.version}",
                reason="sha256_mismatch",
                details={"declared": version.sha256, "computed": digest},
            )
        return True
