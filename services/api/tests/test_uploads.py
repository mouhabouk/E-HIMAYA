import hashlib
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_sessionmaker
from app.modules.reports.uploads import verify_one
from tests.conftest import FakeStore, TokenFactory, accept_charter, bearer, device_headers, report_body

HOOK = "/internal/tusd/hooks/test-hook-secret-test-hook-secret"


def _hook(kind: str, headers: dict[str, str], upload: dict[str, Any]) -> dict[str, Any]:
    return {
        "Type": kind,
        "Event": {
            "Upload": upload,
            "HTTPRequest": {
                "Method": "POST",
                "URI": "/api/v1/uploads/",
                "Header": {k: [v] for k, v in headers.items()},
            },
        },
    }


def _upload(report_id: str, data: bytes, **meta: str) -> dict[str, Any]:
    metadata = {
        "report_id": report_id,
        "kind": "image",
        "filetype": "image/jpeg",
        "sha256": hashlib.sha256(data).hexdigest(),
        "filename": "IMG_2041.jpg",
        **meta,
    }
    return {"ID": "", "Size": len(data), "SizeIsDeferred": False, "Offset": 0, "MetaData": metadata}


async def _report(client: httpx.AsyncClient, headers: dict[str, str]) -> str:
    await accept_charter(client, headers)
    r = await client.post("/api/v1/reports", json=report_body(), headers=headers)
    assert r.status_code == 201
    return str(r.json()["id"])


async def _pre_create(client: httpx.AsyncClient, headers: dict[str, str], upload: dict[str, Any]) -> dict[str, Any]:
    r = await client.post(HOOK, json=_hook("pre-create", headers, upload))
    assert r.status_code == 200, r.text
    return r.json()  # type: ignore[no-any-return]


async def test_hook_requires_secret(client: httpx.AsyncClient) -> None:
    r = await client.post("/internal/tusd/hooks/wrong", json={"Type": "pre-create", "Event": {}})
    assert r.status_code == 404


async def test_full_upload_flow(
    client: httpx.AsyncClient, citizen: dict[str, str], fake_store: FakeStore, session: AsyncSession
) -> None:
    report_id = await _report(client, citizen)
    data = os.urandom(4096)
    answer = await _pre_create(client, citizen, _upload(report_id, data))
    assert "RejectUpload" not in answer
    upload_id = answer["ChangeFileInfo"]["ID"]
    assert "filename" not in answer["ChangeFileInfo"]["MetaData"]

    report = (await client.get("/api/v1/reports/mine", headers=citizen)).json()["items"][0]
    assert report["media"][0]["status"] == "uploading"

    key = f"uploads/{upload_id}"
    fake_store.objects[key] = data
    finished = {**_upload(report_id, data), "ID": f"{upload_id}+multipart-xyz", "Offset": len(data)}
    finished["Storage"] = {"Type": "s3store", "Bucket": "ehimaya-media", "Key": key}
    assert (await client.post(HOOK, json=_hook("post-finish", citizen, finished))).status_code == 200

    assert await verify_one(get_sessionmaker(), fake_store) is True
    media = (await client.get("/api/v1/reports/mine", headers=citizen)).json()["items"][0]["media"][0]
    assert media["status"] == "stored" and media["bytes"] == len(data)
    assert media["sha256"] == hashlib.sha256(data).hexdigest()

    event = await session.scalar(
        text("SELECT payload FROM events.outbox WHERE subject = 'media.stored' AND payload->>'report_id' = :id"),
        {"id": report_id},
    )
    assert event["gouvernorat_code"] == 61 and event["media"]["status"] == "stored"


async def test_hash_mismatch_rejects_and_deletes(
    client: httpx.AsyncClient, fake_store: FakeStore, session: AsyncSession
) -> None:
    device = device_headers()
    report_id = await _report(client, device)
    declared = os.urandom(1024)
    answer = await _pre_create(client, device, _upload(report_id, declared))
    upload_id = answer["ChangeFileInfo"]["ID"]
    key = f"uploads/{upload_id}"
    fake_store.objects[key] = b"tampered" + declared[8:]
    finished = {**_upload(report_id, declared), "ID": upload_id, "Storage": {"Key": key}}
    await client.post(HOOK, json=_hook("post-finish", device, finished))

    assert await verify_one(get_sessionmaker(), fake_store) is True
    assert key in fake_store.deleted and f"{key}.info" in fake_store.deleted
    status = await session.scalar(text("SELECT status FROM reports.media WHERE upload_id = :u"), {"u": upload_id})
    assert status == "rejected"
    reason = await session.scalar(
        text("SELECT reason FROM audit.log WHERE action = 'media.rejected' ORDER BY seq DESC LIMIT 1")
    )
    assert reason == "sha256_mismatch"


async def test_nothing_to_verify(fake_store: FakeStore) -> None:
    while await verify_one(get_sessionmaker(), fake_store):  # drain leftovers from other tests
        pass
    assert await verify_one(get_sessionmaker(), fake_store) is False


async def test_pre_create_rejections(
    client: httpx.AsyncClient, citizen: dict[str, str], make_token: TokenFactory, session: AsyncSession
) -> None:
    report_id = await _report(client, citizen)
    data = b"x" * 100

    async def code(headers: dict[str, str], upload: dict[str, Any]) -> tuple[int, str]:
        answer = await _pre_create(client, headers, upload)
        assert answer.get("RejectUpload") is True
        return answer["HTTPResponse"]["StatusCode"], answer["HTTPResponse"]["Body"]

    assert await code({}, _upload(report_id, data)) == (401, '{"detail":"authentication_required"}')
    stranger = bearer(make_token(roles=["citizen"]))
    assert (await code(stranger, _upload(report_id, data)))[0] == 404
    assert (await code(citizen, _upload(str(uuid.uuid4()), data)))[0] == 404
    assert (await code(citizen, _upload(report_id, data, kind="image", filetype="application/pdf")))[0] == 415
    assert (await code(citizen, _upload(report_id, data, kind="document")))[0] == 415
    assert (await code(citizen, _upload(report_id, data, sha256="abc")))[0] == 400
    assert (await code(citizen, _upload("not-a-uuid", data)))[0] == 400
    too_big = {**_upload(report_id, data), "Size": 21 * 1024 * 1024}
    assert (await code(citizen, too_big))[0] == 413
    deferred = {**_upload(report_id, data), "SizeIsDeferred": True}
    assert (await code(citizen, deferred))[0] == 400

    for _ in range(10):
        assert "RejectUpload" not in await _pre_create(client, citizen, _upload(report_id, data))
    assert await code(citizen, _upload(report_id, data)) == (409, '{"detail":"too_many_media"}')

    late_id = await _report(client, citizen)
    await session.execute(
        text("UPDATE reports.report SET received_at = :t WHERE id = :id"),
        {"t": datetime.now(UTC) - timedelta(hours=25), "id": late_id},
    )
    await session.commit()
    assert (await code(citizen, _upload(late_id, data)))[0] == 409


async def test_terminated_upload_is_rejected(
    client: httpx.AsyncClient, citizen: dict[str, str], session: AsyncSession
) -> None:
    report_id = await _report(client, citizen)
    data = b"y" * 10
    upload_id = (await _pre_create(client, citizen, _upload(report_id, data)))["ChangeFileInfo"]["ID"]
    await client.post(HOOK, json=_hook("post-terminate", citizen, {"ID": f"{upload_id}+mp"}))
    status = await session.scalar(text("SELECT status FROM reports.media WHERE upload_id = :u"), {"u": upload_id})
    assert status == "rejected"
