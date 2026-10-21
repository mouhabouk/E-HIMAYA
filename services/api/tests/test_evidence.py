# covers: NFR-07
"""Phase 10 §4.3: evidence anchors — Merkle proofs, chained signed anchors, the time stamp and the chain check."""

import base64
import hashlib
import secrets
import uuid
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import SecretStr
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_system_sessionmaker
from app.modules.evidence import merkle, service, tsa, worker
from app.modules.evidence.models import Anchor
from tests.test_operations import SFAX, Staff, new_report

# A fixed test key: anchors left in the test database by earlier runs stay verifiable.
TEST_KEY = base64.b64encode(hashlib.sha256(b"e-himaya evidence test key").digest()).decode()


@pytest.fixture(autouse=True)
def _evidence_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "evidence_signing_key", SecretStr(TEST_KEY))
    monkeypatch.setattr(get_settings(), "tsa_url", None)


async def _stored_media(session: AsyncSession, report_id: str) -> tuple[str, str]:
    digest = hashlib.sha256(secrets.token_bytes(16)).hexdigest()
    media_id = await session.scalar(
        text(
            "INSERT INTO reports.media (report_id, kind, object_key, sha256, bytes, content_type, status, stored_at) "
            "VALUES (:r, 'image', :key, :sha, 10, 'image/jpeg', 'stored', now()) RETURNING id"
        ),
        {"r": report_id, "key": f"uploads/{uuid.uuid4().hex}", "sha": digest},
    )
    await session.commit()
    return str(media_id), digest


async def _seal() -> int | None:
    async with get_system_sessionmaker()() as s, s.begin():
        anchor = await service.seal(s)
        return anchor.seq if anchor is not None else None


@pytest.mark.parametrize("count", [1, 2, 3, 5, 8, 9])
def test_every_proof_leads_to_the_root(count: int) -> None:
    leaves = [merkle.leaf_hash(uuid.uuid4(), hashlib.sha256(bytes([i])).hexdigest()) for i in range(count)]
    root = merkle.root(leaves)
    for i, leaf in enumerate(leaves):
        assert merkle.root_from_proof(leaf, merkle.proof(leaves, i)) == root
    # A changed hash no longer reaches the root.
    forged = merkle.leaf_hash(uuid.uuid4(), "0" * 64)
    assert merkle.root_from_proof(forged, merkle.proof(leaves, 0)) != root


async def test_seal_proof_and_chain(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    report = await new_report(client, SFAX)
    first_id, first_sha = await _stored_media(session, report["id"])
    second_id, _ = await _stored_media(session, report["id"])
    seq = await _seal()
    assert seq is not None
    # Nothing new: no empty anchor.
    assert await _seal() is None

    r = await client.get(f"/api/v1/staff/media/{first_id}/proof", headers=staff())
    assert r.status_code == 200, r.text
    proof: dict[str, Any] = r.json()
    anchor = proof["anchor"]
    assert proof["sha256"] == first_sha and anchor["seq"] == seq and anchor["media_count"] >= 2
    # A third party recomputes everything from the response alone.
    leaf = hashlib.sha256(b"\x00" + uuid.UUID(first_id).bytes + bytes.fromhex(first_sha)).digest()
    assert leaf.hex() == proof["leaf_hash"]
    assert merkle.root_from_proof(leaf, proof["path"]) == anchor["media_root"]
    assert hashlib.sha256(proof["anchor_line"].encode()).hexdigest() == anchor["anchor_hash"]
    public = Ed25519PublicKey.from_public_bytes(base64.b64decode(proof["public_key"]))
    public.verify(base64.b64decode(anchor["signature"]), anchor["anchor_hash"].encode())

    # The next anchor is chained to this one.
    third_id, _ = await _stored_media(session, report["id"])
    next_seq = await _seal()
    assert next_seq == seq + 1
    nxt = (await client.get(f"/api/v1/staff/media/{third_id}/proof", headers=staff())).json()["anchor"]
    assert nxt["prev_anchor_hash"] == anchor["anchor_hash"]
    second = (await client.get(f"/api/v1/staff/media/{second_id}/proof", headers=staff())).json()
    assert second["anchor"]["seq"] == seq

    async with get_system_sessionmaker()() as s:
        chain = await service.verify_chain(s)
    assert not [p for p in chain.problems if p["seq"] >= seq], chain.problems


async def test_proof_access(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    report = await new_report(client, SFAX)
    media_id, _ = await _stored_media(session, report["id"])
    url = f"/api/v1/staff/media/{media_id}/proof"
    r = await client.get(url, headers=staff())
    assert (r.status_code, r.json()["detail"]) == (409, "not_anchored_yet")
    await _seal()
    # Another gouvernorat cannot see the report, so not its media either.
    assert (await client.get(url, headers=staff(["operator"], gouvernorat=11))).status_code == 404
    assert (await client.get(f"/api/v1/staff/media/{uuid.uuid4()}/proof", headers=staff())).status_code == 404

    anchors = "/api/v1/staff/evidence/anchors"
    assert (await client.get(anchors, headers=staff())).status_code == 403
    r = await client.get(f"{anchors}?limit=1", headers=staff(["security_admin"], gouvernorat=None))
    assert r.status_code == 200 and r.json()["items"][0]["key_id"]


async def test_tampering_is_detected(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    report = await new_report(client, SFAX)
    media_id, _ = await _stored_media(session, report["id"])
    seq = await _seal()
    assert seq is not None
    # The anchor itself cannot be changed or removed, even by the owner role.
    with pytest.raises(DBAPIError, match="append-only"):
        async with get_system_sessionmaker()() as s, s.begin():
            await s.execute(text("UPDATE evidence.anchor SET media_count = 0 WHERE seq = :s"), {"s": seq})
    with pytest.raises(DBAPIError, match="append-only"):
        async with get_system_sessionmaker()() as s, s.begin():
            await s.execute(text("DELETE FROM evidence.leaf WHERE media_id = :m"), {"m": media_id})
    # A media hash changed afterwards shows in the chain check (rolled back: the database stays clean).
    async with get_system_sessionmaker()() as s, s.begin():
        await s.execute(text("UPDATE reports.media SET sha256 = :h WHERE id = :m"), {"h": "f" * 64, "m": media_id})
        chain = await service.verify_chain(s)
        await s.rollback()
    assert {"seq": seq, "problem": "media_changed", "media_id": media_id} in chain.problems


async def test_only_known_keys_sign(client: httpx.AsyncClient, session: AsyncSession) -> None:
    report = await new_report(client, SFAX)
    await _stored_media(session, report["id"])
    seq = await _seal()
    async with get_system_sessionmaker()() as s:
        anchor = await s.scalar(select(Anchor).where(Anchor.seq == seq))
    assert anchor is not None and service.signature_valid(anchor)
    assert not service.signature_valid(anchor, keys={})


def test_time_stamp_request_and_response() -> None:
    digest = hashlib.sha256(b"anchor").digest()
    body = tsa.request(digest, nonce=7)
    assert body[0] == 0x30 and digest in body and body.endswith(b"\x01\x01\xff")
    assert tsa.granted(bytes.fromhex("30053003020100")) and tsa.granted(bytes.fromhex("30053003020101"))
    assert not tsa.granted(bytes.fromhex("30053003020102")) and not tsa.granted(b"")


async def test_time_stamp_is_requested_and_failures_never_block(
    client: httpx.AsyncClient, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[bytes] = []
    answer = {"status": 200, "body": bytes.fromhex("30053003020100")}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.content)
        return httpx.Response(answer["status"], content=answer["body"])  # type: ignore[arg-type]

    real = tsa.timestamp

    async def fake(anchor_hash: str, *, transport: httpx.AsyncBaseTransport | None = None) -> bytes:
        return await real(anchor_hash, transport=httpx.MockTransport(handler))

    monkeypatch.setattr(tsa, "timestamp", fake)
    monkeypatch.setattr(get_settings(), "tsa_url", "https://tsa.test/")
    report = await new_report(client, SFAX)

    answer["status"] = 503
    await _stored_media(session, report["id"])
    seq = await worker.run_once(get_system_sessionmaker())
    assert seq is not None
    row = (
        await session.execute(text("SELECT tsa_token, tsa_error FROM evidence.anchor WHERE seq = :s"), {"s": seq})
    ).one()
    assert row.tsa_token is None and row.tsa_error == "http_503"

    answer["status"] = 200
    await worker.run_once(get_system_sessionmaker())
    session.expire_all()
    token = await session.scalar(text("SELECT tsa_token FROM evidence.anchor WHERE seq = :s"), {"s": seq})
    assert token == answer["body"]
    anchor_hash = await session.scalar(text("SELECT anchor_hash FROM evidence.anchor WHERE seq = :s"), {"s": seq})
    assert bytes.fromhex(anchor_hash) in seen[-1]
