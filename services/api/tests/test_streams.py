"""Live streaming and vision (phase 6, docs/api/phase-6-contract.md): citizen and staff endpoints, MediaMTX auth and
hooks, recording-segment ingestion, detection confirmation, the stream life cycle, privacy and retention."""

import base64
import hashlib
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.modules.privacy import retention
from app.modules.streams import internal, worker
from app.modules.streams.domain import viewer_token
from app.modules.streams.schemas import MediamtxAuthIn
from app.modules.streams.vision import VisionBusy, VisionUnavailable
from tests.conftest import (
    FakeMediamtx,
    FakeStore,
    TokenFactory,
    accept_charter,
    bearer,
    device_headers,
    outbox_events,
    report_body,
)

Staff = Callable[..., dict[str, str]]
HOOK = {"X-Hook-Token": "test-mediamtx-hook-token-0001"}
VISION = {"X-Vision-Token": "test-vision-callback-token-0001"}
SIM = {"X-Sim-Token": "test-stream-sim-token-0000001"}
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 64


# ---------------------------------------------------------------- helpers


async def new_citizen(client: httpx.AsyncClient, make_token: TokenFactory) -> dict[str, str]:
    headers = bearer(make_token(roles=["citizen"]))
    await accept_charter(client, headers)
    return headers


async def new_report(client: httpx.AsyncClient, headers: dict[str, str], **overrides: Any) -> dict[str, Any]:
    r = await client.post("/api/v1/reports", json=report_body(**overrides), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


async def open_stream(client: httpx.AsyncClient, headers: dict[str, str], report_id: str) -> dict[str, Any]:
    r = await client.post(f"/api/v1/reports/{report_id}/streams", headers=headers)
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


async def citizen_stream(client: httpx.AsyncClient, make_token: TokenFactory) -> tuple[dict[str, str], dict[str, Any]]:
    headers = await new_citizen(client, make_token)
    report = await new_report(client, headers)
    stream = await open_stream(client, headers, report["id"])
    stream["report_id"] = report["id"]
    return headers, stream


async def hook(client: httpx.AsyncClient, event: str, path: str, **extra: Any) -> httpx.Response:
    return await client.post("/internal/mediamtx/hooks", json={"event": event, "path": path, **extra}, headers=HOOK)


async def auth(client: httpx.AsyncClient, **body: Any) -> int:
    payload = {"user": "", "password": "", "token": "", "ip": "10.0.0.7", "query": "", "id": None, **body}
    return (await client.post("/internal/mediamtx/auth", json=payload)).status_code


async def go_live(client: httpx.AsyncClient, path: str) -> None:
    r = await hook(client, "ready", path, source_type="webRTCSession", source_id=str(uuid.uuid4()))
    assert r.status_code == 204, r.text


async def frame(client: httpx.AsyncClient, stream_id: str, **labels: float) -> httpx.Response:
    body = {
        "stream_id": stream_id,
        "at": datetime.now(UTC).isoformat(),
        "model": "test-detector-1",
        "detections": [{"label": k, "confidence": v, "boxes": [[0.1, 0.2, 0.4, 0.6, v]]} for k, v in labels.items()],
        "frame_jpeg_b64": base64.b64encode(JPEG).decode(),
    }
    return await client.post("/internal/vision/detections", json=body, headers=VISION)


async def row(session: AsyncSession, stream_id: str) -> Any:
    await session.rollback()
    return (await session.execute(text("SELECT * FROM reports.live_stream WHERE id = :id"), {"id": stream_id})).one()


# ---------------------------------------------------------------- citizen endpoints (§2)


async def test_citizen_opens_a_stream(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession
) -> None:
    headers, stream = await citizen_stream(client, make_token)
    assert stream["path"] == f"live/{stream['stream_id']}"
    assert stream["whip_url"] == f"http://localhost:8889/live/{stream['stream_id']}/whip"
    assert len(stream["publish_token"]) == 43 and stream["simulated"] is False
    assert stream["max_duration_s"] == 900 and stream["location_interval_s"] == 10
    expires = datetime.fromisoformat(stream["expires_at"])
    assert timedelta(minutes=9) < expires - datetime.now(UTC) <= timedelta(minutes=10)

    stored = await row(session, stream["stream_id"])
    assert stored.status == "pending" and stored.source == "app" and stored.gouvernorat_code == 61
    # Only a keyed hash of the token is kept.
    assert stream["publish_token"].encode() not in bytes(stored.publish_token_hash)
    assert len(bytes(stored.publish_token_hash)) == 32

    r = await client.get(f"/api/v1/streams/{stream['stream_id']}", headers=headers)
    assert r.json() == {
        "stream_id": stream["stream_id"],
        "status": "pending",
        "started_at": None,
        "ended_at": None,
        "end_reason": None,
    }
    # One pending or live stream per report.
    r = await client.post(f"/api/v1/reports/{stream['report_id']}/streams", headers=headers)
    assert r.status_code == 409 and r.json() == {"detail": "stream_already_active"}


async def test_only_the_owner_of_an_open_report(
    client: httpx.AsyncClient, make_token: TokenFactory, staff: Staff
) -> None:
    owner = await new_citizen(client, make_token)
    other = await new_citizen(client, make_token)
    report = await new_report(client, owner)
    r = await client.post(f"/api/v1/reports/{report['id']}/streams", headers=other)
    assert r.status_code == 404 and r.json() == {"detail": "report_not_found"}
    stream = await open_stream(client, owner, report["id"])
    for call in (
        client.get(f"/api/v1/streams/{stream['stream_id']}", headers=other),
        client.post(f"/api/v1/streams/{stream['stream_id']}/stop", headers=other),
        client.post(
            f"/api/v1/streams/{stream['stream_id']}/location", json={"lat": 34.74, "lon": 10.76}, headers=other
        ),
    ):
        assert (await call).status_code == 404

    closed = await new_report(client, owner)
    operator = staff(gouvernorat=61)
    for target in ("in_progress", "closed"):
        r = await client.post(f"/api/v1/staff/reports/{closed['id']}/status", json={"status": target}, headers=operator)
        assert r.status_code == 200, r.text
    r = await client.post(f"/api/v1/reports/{closed['id']}/streams", headers=owner)
    assert r.status_code == 409 and r.json() == {"detail": "report_closed"}


async def test_anonymous_device_can_stream(client: httpx.AsyncClient) -> None:
    headers = device_headers()
    await accept_charter(client, headers)
    report = await new_report(client, headers)
    stream = await open_stream(client, headers, report["id"])
    assert (await client.get(f"/api/v1/streams/{stream['stream_id']}", headers=headers)).status_code == 200


async def test_stream_creation_is_rate_limited(client: httpx.AsyncClient, make_token: TokenFactory) -> None:
    headers = await new_citizen(client, make_token)
    codes = []
    for _ in range(7):
        report = await new_report(client, headers)
        codes.append((await client.post(f"/api/v1/reports/{report['id']}/streams", headers=headers)).status_code)
    assert codes == [201] * 6 + [429]
    r = await client.post(f"/api/v1/reports/{report['id']}/streams", headers=headers)
    assert r.json() == {"detail": "rate_limited"} and int(r.headers["Retry-After"]) >= 1


async def test_location_is_throttled_and_streamed_to_the_dashboard(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession
) -> None:
    headers, stream = await citizen_stream(client, make_token)
    sid = stream["stream_id"]
    url = f"/api/v1/streams/{sid}/location"
    r = await client.post(url, json={"lat": 34.741, "lon": 10.761, "accuracy_m": 12.0}, headers=headers)
    assert r.status_code == 204
    # Within 3 s: accepted and ignored.
    assert (await client.post(url, json={"lat": 34.742, "lon": 10.762}, headers=headers)).status_code == 204
    points = await session.scalar(
        text("SELECT count(*) FROM reports.stream_location WHERE stream_id = :id"), {"id": sid}
    )
    assert points == 1
    events = [e for e in await outbox_events(session, "stream.location") if e["stream_id"] == sid]
    assert len(events) == 1 and events[0]["gouvernorat_code"] == 61 and events[0]["lat"] == 34.741
    # Out of Tunisia → 422; ended stream → 409.
    assert (await client.post(url, json={"lat": 48.85, "lon": 2.35}, headers=headers)).status_code == 422
    assert (await client.post(f"/api/v1/streams/{sid}/stop", headers=headers)).status_code == 200
    r = await client.post(url, json={"lat": 34.741, "lon": 10.761}, headers=headers)
    assert r.status_code == 409 and r.json() == {"detail": "stream_not_active"}


async def test_citizen_stop_is_idempotent_and_kicks(
    client: httpx.AsyncClient, make_token: TokenFactory, fake_mediamtx: FakeMediamtx
) -> None:
    headers, stream = await citizen_stream(client, make_token)
    await go_live(client, stream["path"])
    first = await client.post(f"/api/v1/streams/{stream['stream_id']}/stop", headers=headers)
    assert first.status_code == 200
    assert first.json()["status"] == "ended" and first.json()["end_reason"] == "publisher_stopped"
    second = await client.post(f"/api/v1/streams/{stream['stream_id']}/stop", headers=headers)
    assert second.json() == first.json()
    assert fake_mediamtx.kicked == [stream["path"]]


# ---------------------------------------------------------------- MediaMTX authorization (§3)


async def test_auth_decision_table(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession, staff: Staff
) -> None:
    _, stream = await citizen_stream(client, make_token)
    path, token = stream["path"], stream["publish_token"]
    _, other = await citizen_stream(client, make_token)
    now = int(datetime.now(UTC).timestamp())
    viewer = viewer_token(path, now + 300)
    flipped = "B" if token.endswith("A") else "A"  # one character off, never the token itself

    table: list[tuple[dict[str, Any], int]] = [
        # publish: the stream's own token, in any of the three places MediaMTX passes it
        ({"action": "publish", "path": path, "protocol": "webrtc", "token": token}, 200),
        ({"action": "publish", "path": path, "protocol": "webrtc", "password": token}, 200),
        ({"action": "publish", "path": path, "protocol": "webrtc", "query": f"token={token}"}, 200),
        ({"action": "publish", "path": f"/{path}", "protocol": "webrtc", "token": token}, 200),
        ({"action": "publish", "path": path, "protocol": "webrtc", "token": other["publish_token"]}, 401),
        ({"action": "publish", "path": path, "protocol": "webrtc", "token": token[:-1] + flipped}, 401),
        ({"action": "publish", "path": path, "protocol": "webrtc"}, 401),
        # citizen streams are WHIP only
        ({"action": "publish", "path": path, "protocol": "rtsp", "password": token}, 401),
        ({"action": "publish", "path": "live/not-a-uuid", "protocol": "webrtc", "token": token}, 401),
        ({"action": "publish", "path": f"live/{uuid.uuid4()}", "protocol": "webrtc", "token": token}, 401),
        ({"action": "publish", "path": "other/thing", "protocol": "webrtc", "token": token}, 401),
        # read: internal vision credentials, or a viewer token of that exact path
        (
            {
                "action": "read",
                "path": path,
                "protocol": "rtsp",
                "user": "vision",
                "password": "test-vision-read-password-0001",
            },
            200,
        ),
        (
            {
                "action": "read",
                "path": path,
                "protocol": "rtsp",
                "user": "vision",
                "password": "wrong-password-wrong-0001",
            },
            401,
        ),
        ({"action": "read", "path": path, "protocol": "webrtc", "token": viewer}, 200),
        ({"action": "read", "path": path, "protocol": "hls", "query": f"token={viewer}"}, 200),
        ({"action": "playback", "path": path, "protocol": "", "token": viewer}, 200),
        ({"action": "read", "path": other["path"], "protocol": "webrtc", "token": viewer}, 401),
        ({"action": "read", "path": path, "protocol": "webrtc", "token": viewer_token(path, now - 1)}, 401),
        ({"action": "read", "path": path, "protocol": "webrtc", "token": token}, 401),
        ({"action": "read", "path": path, "protocol": "webrtc"}, 401),
        # control API, metrics, pprof: the internal API user only
        ({"action": "api", "path": "", "user": "ehimaya-api", "password": "test-mediamtx-api-password-0001"}, 200),
        ({"action": "metrics", "path": "", "user": "ehimaya-api", "password": "test-mediamtx-api-password-0001"}, 200),
        ({"action": "pprof", "path": "", "user": "ehimaya-api", "password": "nope-nope-nope-nope-nope-0001"}, 401),
        ({"action": "api", "path": "", "user": "vision", "password": "test-vision-read-password-0001"}, 401),
        ({"action": "api", "path": "", "token": viewer}, 401),
        ({"action": "something", "path": path, "token": token}, 401),
    ]
    for body, expected in table:
        assert await auth(client, **body) == expected, body

    # Once the start window has passed, the token no longer publishes.
    await session.execute(
        text("UPDATE reports.live_stream SET expires_at = now() - interval '1 second' WHERE id = :id"),
        {"id": stream["stream_id"]},
    )
    await session.commit()
    assert await auth(client, action="publish", path=path, protocol="webrtc", token=token) == 401


async def test_publish_token_is_single_session(client: httpx.AsyncClient, make_token: TokenFactory) -> None:
    _, stream = await citizen_stream(client, make_token)
    body = {"action": "publish", "path": stream["path"], "protocol": "webrtc", "token": stream["publish_token"]}
    assert await auth(client, **body) == 200
    await go_live(client, stream["path"])
    # While live, a second publisher is refused; after the end, the token is dead.
    assert await auth(client, **body) == 401
    await hook(client, "not_ready", stream["path"])
    assert await auth(client, **body) == 401
    viewer = viewer_token(stream["path"], int(datetime.now(UTC).timestamp()) + 300)
    assert await auth(client, action="read", path=stream["path"], protocol="webrtc", token=viewer) == 401


async def test_auth_denials_are_logged_without_tokens(
    client: httpx.AsyncClient, make_token: TokenFactory, capsys: pytest.CaptureFixture[str]
) -> None:
    _, stream = await citizen_stream(client, make_token)
    wrong = "x" * 43
    assert await auth(client, action="publish", path=stream["path"], protocol="webrtc", token=wrong) == 401
    out = capsys.readouterr().out
    assert "mediamtx.auth_denied" in out and "bad_publish_token" in out
    assert wrong not in out and stream["publish_token"] not in out and "10.0.0.7" not in out


async def test_decide_is_pure(client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession) -> None:
    _, stream = await citizen_stream(client, make_token)
    body = MediamtxAuthIn(action="publish", path=stream["path"], protocol="webrtc", token=stream["publish_token"])
    assert (await internal.decide(session, body)).allowed
    later = datetime.now(UTC) + timedelta(minutes=11)
    decision = await internal.decide(session, body, now=later)
    assert not decision.allowed and decision.reason == "not_publishable_pending"


# ---------------------------------------------------------------- hooks (§3)


async def test_hook_requires_the_token(client: httpx.AsyncClient) -> None:
    body = {"event": "ready", "path": f"live/{uuid.uuid4()}"}
    assert (await client.post("/internal/mediamtx/hooks", json=body)).status_code == 404
    wrong = {"X-Hook-Token": "wrong-token-wrong-token-0001"}
    assert (await client.post("/internal/mediamtx/hooks", json=body, headers=wrong)).status_code == 404
    # An unknown path is acknowledged (logged) so MediaMTX does not retry forever.
    assert (await client.post("/internal/mediamtx/hooks", json=body, headers=HOOK)).status_code == 204


async def test_hooks_lifecycle(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession, fake_mediamtx: FakeMediamtx
) -> None:
    headers, stream = await citizen_stream(client, make_token)
    sid, path = stream["stream_id"], stream["path"]
    await go_live(client, path)
    live = await row(session, sid)
    assert live.status == "live" and live.started_at is not None and live.vision_state == "requested"
    started = [e for e in await outbox_events(session, "stream.started") if e["stream_id"] == sid]
    assert len(started) == 1 and started[0]["gouvernorat_code"] == 61
    assert started[0]["stream"]["status"] == "live" and started[0]["stream"]["simulated"] is False
    # A repeated ready hook changes nothing.
    await go_live(client, path)
    assert len([e for e in await outbox_events(session, "stream.started") if e["stream_id"] == sid]) == 1

    r = await hook(client, "not_ready", path, source_type="webRTCSession")
    assert r.status_code == 204
    ended = await row(session, sid)
    assert ended.status == "ended" and ended.end_reason == "publisher_stopped" and ended.publish_token_hash is None
    assert ended.vision_state == "stopping"
    assert len([e for e in await outbox_events(session, "stream.ended") if e["stream_id"] == sid]) == 1
    summary = (await client.get(f"/api/v1/streams/{sid}", headers=headers)).json()
    assert summary["status"] == "ended" and summary["end_reason"] == "publisher_stopped"

    # A ready hook on a stream that may not be live (ended) gets its publisher kicked.
    await go_live(client, path)
    assert fake_mediamtx.kicked == [path]
    assert (await row(session, sid)).status == "ended"


# ---------------------------------------------------------------- recording segments


@pytest.fixture
def recordings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(get_settings(), "stream_recordings_dir", tmp_path)
    return tmp_path


def segment(recordings: Path, path: str, name: str, data: bytes) -> Path:
    directory = recordings / path
    directory.mkdir(parents=True, exist_ok=True)
    file = directory / name
    file.write_bytes(data)
    return file


async def drain(store: FakeStore) -> int:
    sessionmaker = get_sessionmaker()
    count = 0
    while await worker.ingest_one(sessionmaker, store):
        count += 1
    return count


async def test_segments_are_hashed_stored_and_deleted(
    client: httpx.AsyncClient,
    make_token: TokenFactory,
    session: AsyncSession,
    recordings: Path,
    fake_store: FakeStore,
    staff: Staff,
) -> None:
    _, stream = await citizen_stream(client, make_token)
    sid, path = stream["stream_id"], stream["path"]
    await go_live(client, path)
    first = segment(recordings, path, "2026-10-19_10-00-00-000000.mp4", b"\x00\x00\x00\x18ftypiso5" + b"a" * 1000)
    second = segment(recordings, path, "2026-10-19_10-01-00-000000.mp4", b"\x00\x00\x00\x18ftypiso5" + b"b" * 2000)
    for file, duration in ((first, 60.0), (second, 12.5)):
        r = await hook(client, "segment_complete", path, segment_path=str(file), segment_duration_s=duration)
        assert r.status_code == 204
    # The same hook twice (MediaMTX retry) is queued once.
    await hook(client, "segment_complete", path, segment_path=str(first), segment_duration_s=60.0)
    assert await drain(fake_store) == 2

    rows = (
        await session.execute(
            text(
                "SELECT object_key, sha256, bytes, duration_s, kind, status, report_id FROM reports.media "
                "WHERE stream_id = :id ORDER BY object_key"
            ),
            {"id": sid},
        )
    ).all()
    assert [r.object_key for r in rows] == [f"recordings/{sid}/1.mp4", f"recordings/{sid}/2.mp4"]
    assert rows[0].sha256 == hashlib.sha256(fake_store.objects[rows[0].object_key]).hexdigest()
    assert rows[1].bytes == 2012 and rows[1].duration_s == 12.5
    assert all(r.kind == "recording" and r.status == "stored" and str(r.report_id) == stream["report_id"] for r in rows)
    assert not first.exists() and not second.exists()
    events = [e for e in await outbox_events(session, "stream.recording") if e["stream_id"] == sid]
    assert len(events) == 2 and events[0]["gouvernorat_code"] == 61

    # The dashboard lists them and downloads through a short-lived link (audited).
    operator = staff(gouvernorat=61)
    detail = (await client.get(f"/api/v1/staff/streams/{sid}", headers=operator)).json()
    assert detail["recordings_count"] == 2 and [r["duration_s"] for r in detail["recordings"]] == [60.0, 12.5]
    media_id = detail["recordings"][0]["media_id"]
    r = await client.get(f"/api/v1/staff/streams/{sid}/recordings/{media_id}", headers=operator)
    assert r.status_code == 302 and r.headers["location"].startswith(f"http://s3.test/recordings/{sid}/")
    assert fake_store.presigned[-1][1] == "video/mp4"
    audit = await session.scalar(
        text("SELECT count(*) FROM audit.log WHERE action = 'stream.recording.download' AND target = :t"),
        {"t": f"media:{media_id}"},
    )
    assert audit == 1
    assert (
        await client.get(f"/api/v1/staff/streams/{sid}/recordings/{uuid.uuid4()}", headers=operator)
    ).status_code == 404


async def test_segment_paths_are_confined(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession, recordings: Path, fake_store: FakeStore
) -> None:
    _, stream = await citizen_stream(client, make_token)
    _, other = await citizen_stream(client, make_token)
    sid, path = stream["stream_id"], stream["path"]
    outside = recordings.parent / "secret.mp4"
    outside.write_bytes(b"not a recording")
    foreign = segment(recordings, other["path"], "x.mp4", b"other stream")
    for candidate in (
        str(outside),
        f"{recordings}/{path}/../../{other['path']}/x.mp4",
        str(foreign),
        f"/etc/passwd-{uuid.uuid4()}",
    ):
        await hook(client, "segment_complete", path, segment_path=candidate, segment_duration_s=1.0)
    missing = f"{recordings}/{path}/gone.mp4"
    await hook(client, "segment_complete", path, segment_path=missing, segment_duration_s=1.0)
    assert await drain(fake_store) == 5
    states = (
        await session.execute(
            text("SELECT segment_path, state FROM reports.stream_segment WHERE stream_id = :id"), {"id": sid}
        )
    ).all()
    assert {s.state for s in states if s.segment_path != missing} == {"failed"}
    assert next(s.state for s in states if s.segment_path == missing) == "missing"
    assert outside.exists() and foreign.exists() and not fake_store.objects


async def test_orphan_segments_are_picked_up(
    client: httpx.AsyncClient,
    make_token: TokenFactory,
    session: AsyncSession,
    recordings: Path,
    fake_store: FakeStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, stream = await citizen_stream(client, make_token)
    old = segment(recordings, stream["path"], "old.mp4", b"orphan segment")
    segment(recordings, f"live/{uuid.uuid4()}", "unknown.mp4", b"no stream")
    segment(recordings, "live/not-a-stream", "junk.mp4", b"junk")
    monkeypatch.setattr(get_settings(), "stream_segment_orphan_after_s", 0)
    assert await worker.queue_orphans(get_sessionmaker()) == 1
    assert await worker.queue_orphans(get_sessionmaker()) == 0
    assert await drain(fake_store) == 1
    assert not old.exists() and f"recordings/{stream['stream_id']}/1.mp4" in fake_store.objects


async def test_upload_failure_is_retried(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession, recordings: Path, fake_store: FakeStore
) -> None:
    _, stream = await citizen_stream(client, make_token)
    file = segment(recordings, stream["path"], "a.mp4", b"segment bytes")
    await hook(client, "segment_complete", stream["path"], segment_path=str(file), segment_duration_s=3.0)

    class Down(FakeStore):
        async def put(self, key: str, data: bytes, content_type: str) -> None:
            raise ConnectionError("s3 down")

    assert await worker.ingest_one(get_sessionmaker(), Down()) is True
    state = (
        await session.execute(
            text("SELECT state, attempts, last_error FROM reports.stream_segment WHERE segment_path = :p"),
            {"p": str(file)},
        )
    ).one()
    assert state.state == "pending" and state.attempts == 1 and state.last_error == "ConnectionError"
    assert file.exists()
    await session.execute(
        text("UPDATE reports.stream_segment SET next_attempt_at = now() WHERE segment_path = :p"), {"p": str(file)}
    )
    await session.commit()
    assert await drain(fake_store) == 1 and not file.exists()


# ---------------------------------------------------------------- vision detections


async def test_fire_is_confirmed_in_three_of_five_frames(
    client: httpx.AsyncClient,
    make_token: TokenFactory,
    session: AsyncSession,
    staff: Staff,
    fake_store: FakeStore,
) -> None:
    _, stream = await citizen_stream(client, make_token)
    sid = stream["stream_id"]
    await go_live(client, stream["path"])
    # Wrong token → 404; below VISION_MIN_CONFIDENCE → dropped.
    body = {"stream_id": sid, "at": datetime.now(UTC).isoformat(), "detections": []}
    assert (await client.post("/internal/vision/detections", json=body)).status_code == 404
    assert (await frame(client, sid, fire=0.3)).status_code == 204
    assert (await frame(client, sid, fire=0.7, person=0.9)).status_code == 204
    assert (await frame(client, sid, smoke=0.5)).status_code == 204
    assert (await frame(client, sid, fire=0.65)).status_code == 204
    assert not [e for e in await outbox_events(session, "stream.alert") if e["stream_id"] == sid]
    # Third frame at ≥ 0.6 in the last five: confirmed.
    assert (await frame(client, sid, fire=0.8)).status_code == 204
    alerts = [e for e in await outbox_events(session, "stream.alert") if e["stream_id"] == sid]
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert["label"] == "fire" and alert["confidence"] == 0.8 and alert["report_id"] == stream["report_id"]
    assert alert["gouvernorat_code"] == 61 and alert["media_id"]
    # Cool-down: the next confirming frame does not alert again.
    await frame(client, sid, fire=0.9)
    assert len([e for e in await outbox_events(session, "stream.alert") if e["stream_id"] == sid]) == 1

    stored = await row(session, sid)
    assert stored.max_fire_confidence == pytest.approx(0.9) and stored.max_smoke_confidence == pytest.approx(0.5)
    labels = (
        await session.execute(
            text("SELECT label, confidence, confirmed FROM reports.stream_detection WHERE stream_id = :id ORDER BY id"),
            {"id": sid},
        )
    ).all()
    assert [r.label for r in labels] == ["fire", "person", "smoke", "fire", "fire", "fire"]
    assert [r.confirmed for r in labels if r.label == "fire"] == [False, False, True, True]
    frame_media = (
        await session.execute(
            text("SELECT kind, analysis, report_id, object_key FROM reports.media WHERE id = :id"),
            {"id": alert["media_id"]},
        )
    ).one()
    assert frame_media.kind == "image" and frame_media.analysis["source"] == "vision"
    assert fake_store.objects[frame_media.object_key] == JPEG

    # The report's priority now counts the confirmed fire.
    operator = staff(gouvernorat=61)
    report = (await client.get(f"/api/v1/staff/reports/{stream['report_id']}", headers=operator)).json()
    component = next(c for c in report["analysis"]["priority"]["components"] if c["key"] == "vision_fire")
    assert component["value"] == pytest.approx(0.9, abs=0.001) and component["detail"]["label"] == "fire"
    detail = (await client.get(f"/api/v1/staff/streams/{sid}", headers=operator)).json()
    assert detail["max_fire_confidence"] == pytest.approx(0.9) and len(detail["detections"]) == 6
    assert detail["detections"][0]["boxes"] == [[0.1, 0.2, 0.4, 0.6, 0.9]]


async def test_confirmed_detection_reaches_the_incident_timeline(
    client: httpx.AsyncClient, make_token: TokenFactory, staff: Staff
) -> None:
    _, stream = await citizen_stream(client, make_token)
    operator = staff(gouvernorat=61)
    r = await client.post(
        f"/api/v1/staff/reports/{stream['report_id']}/incident", json={"action": "new"}, headers=operator
    )
    assert r.status_code == 200, r.text
    incident_id = r.json()["incident_id"]
    await go_live(client, stream["path"])
    for _ in range(3):
        await frame(client, stream["stream_id"], smoke=0.75)
    incident = (await client.get(f"/api/v1/staff/incidents/{incident_id}", headers=operator)).json()
    entry = next(e for e in incident["timeline"] if e["kind"] == "vision_alert")
    assert entry["payload"]["label"] == "smoke" and entry["payload"]["stream_id"] == stream["stream_id"]


async def test_detections_of_an_ended_stream_are_ignored(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession
) -> None:
    _, stream = await citizen_stream(client, make_token)
    assert (await frame(client, stream["stream_id"], fire=0.9)).status_code == 204  # pending: not live yet
    body = {"stream_id": str(uuid.uuid4()), "at": datetime.now(UTC).isoformat(), "detections": []}
    assert (await client.post("/internal/vision/detections", json=body, headers=VISION)).status_code == 204
    count = await session.scalar(
        text("SELECT count(*) FROM reports.stream_detection WHERE stream_id = :id"), {"id": stream["stream_id"]}
    )
    assert count == 0


# ---------------------------------------------------------------- staff (§4)


async def test_staff_list_scope_viewer_and_stop(
    client: httpx.AsyncClient,
    make_token: TokenFactory,
    session: AsyncSession,
    staff: Staff,
    fake_mediamtx: FakeMediamtx,
) -> None:
    headers, stream = await citizen_stream(client, make_token)
    sid = stream["stream_id"]
    await go_live(client, stream["path"])
    await client.post(f"/api/v1/streams/{sid}/location", json={"lat": 34.75, "lon": 10.77}, headers=headers)
    sfax, tunis, national = staff(gouvernorat=61), staff(gouvernorat=11), staff(gouvernorat=None)

    listed = (await client.get("/api/v1/staff/streams?status=live", headers=sfax)).json()["items"]
    item = next(i for i in listed if i["id"] == sid)
    assert item["tracking_code"].startswith("EH-") and item["source"] == "app" and item["status"] == "live"
    assert item["last_location"] == {"lat": 34.75, "lon": 10.77} and item["simulated"] is False
    assert item["duration_s"] is not None and item["recordings_count"] == 0
    assert sid not in {i["id"] for i in (await client.get("/api/v1/staff/streams", headers=tunis)).json()["items"]}
    assert sid in {
        i["id"] for i in (await client.get("/api/v1/staff/streams?status=all", headers=national)).json()["items"]
    }
    assert (await client.get(f"/api/v1/staff/streams/{sid}", headers=tunis)).status_code == 404
    assert (await client.post(f"/api/v1/staff/streams/{sid}/viewer", headers=tunis)).status_code == 404
    assert (await client.get("/api/v1/staff/streams", headers=staff(roles=["content_editor"]))).status_code == 403
    assert (await client.get("/api/v1/staff/streams")).status_code == 401
    assert (await client.get("/api/v1/staff/streams?status=bogus", headers=sfax)).status_code == 422

    detail = (await client.get(f"/api/v1/staff/streams/{sid}", headers=sfax)).json()
    assert detail["track"][0]["lat"] == 34.75 and detail["recordings"] == [] and detail["detections"] == []

    viewer = (await client.post(f"/api/v1/staff/streams/{sid}/viewer", headers=sfax)).json()
    assert viewer["whep_url"] == f"http://localhost:8889/live/{sid}/whep"
    assert viewer["hls_url"] == f"http://localhost:8888/live/{sid}/index.m3u8"
    assert await auth(client, action="read", path=stream["path"], protocol="webrtc", token=viewer["token"]) == 200
    assert await auth(client, action="publish", path=stream["path"], protocol="webrtc", token=viewer["token"]) == 401
    actions = list(
        await session.scalars(
            text("SELECT action FROM audit.log WHERE target = :t ORDER BY seq"), {"t": f"stream:{sid}"}
        )
    )
    assert actions == ["stream.detail", "stream.view"]

    # Committee members read but do not stop.
    committee = staff(roles=["local_committee"], gouvernorat=61)
    assert (await client.post(f"/api/v1/staff/streams/{sid}/stop", headers=committee)).status_code == 403
    stopped = await client.post(f"/api/v1/staff/streams/{sid}/stop", headers=sfax)
    assert stopped.status_code == 200 and stopped.json()["status"] == "ended"
    assert fake_mediamtx.kicked == [stream["path"]]
    summary = (await client.get(f"/api/v1/streams/{sid}", headers=headers)).json()
    assert summary["end_reason"] == "staff_stopped"
    r = await client.post(f"/api/v1/staff/streams/{sid}/viewer", headers=sfax)
    assert r.status_code == 409 and r.json() == {"detail": "stream_not_active"}
    ended = (await client.get("/api/v1/staff/streams?status=ended", headers=sfax)).json()["items"]
    assert sid in {i["id"] for i in ended}


async def test_cursor_pagination(client: httpx.AsyncClient, make_token: TokenFactory, staff: Staff) -> None:
    for _ in range(3):
        await citizen_stream(client, make_token)
    national = staff(gouvernorat=None)
    first = (await client.get("/api/v1/staff/streams?status=all&limit=2", headers=national)).json()
    assert len(first["items"]) == 2 and first["next_cursor"]
    second = (
        await client.get(f"/api/v1/staff/streams?status=all&limit=2&cursor={first['next_cursor']}", headers=national)
    ).json()
    assert not {i["id"] for i in first["items"]} & {i["id"] for i in second["items"]}
    assert (await client.get("/api/v1/staff/streams?cursor=@@@", headers=national)).status_code == 422


async def test_fixed_sources(
    client: httpx.AsyncClient, session: AsyncSession, staff: Staff, fake_mediamtx: FakeMediamtx
) -> None:
    body = {"source": "drone", "label": "Drone PC Sfax 1", "gouvernorat_code": 61, "lat": 34.74, "lon": 10.76}
    assert (await client.post("/api/v1/staff/streams", json=body, headers=staff(gouvernorat=61))).status_code == 403
    manager = staff(roles=["ops_manager"], gouvernorat=61)
    r = await client.post("/api/v1/staff/streams", json={**body, "gouvernorat_code": 11}, headers=manager)
    assert r.status_code == 403 and r.json() == {"detail": "out_of_scope"}
    # Phase 9 §10: registering sources is an operational act, no longer open to sysadmin.
    r = await client.post("/api/v1/staff/streams", json=body, headers=staff(roles=["sysadmin"], gouvernorat=None))
    assert r.status_code == 403
    r = await client.post(
        "/api/v1/staff/streams",
        json={**body, "gouvernorat_code": 99},
        headers=staff(roles=["ops_manager"], gouvernorat=None),
    )
    assert r.status_code == 422
    r = await client.post("/api/v1/staff/streams", json=body, headers=manager)
    assert r.status_code == 201, r.text
    drone = r.json()
    assert drone["publish_url_rtsp"] == f"rtsp://localhost:8554/live/{drone['id']}"
    assert drone["publish_url_rtmp"] == f"rtmp://localhost:1935/live/{drone['id']}"
    path, token = drone["path"], drone["publish_token"]

    publish = {"action": "publish", "path": path, "protocol": "rtmp", "query": f"token={token}"}
    assert await auth(client, **publish) == 200
    assert await auth(client, **{**publish, "protocol": "rtsp", "query": "", "user": "drone", "password": token}) == 200
    await hook(client, "ready", path, source_type="rtmpConn")
    await hook(client, "not_ready", path, source_type="rtmpConn")
    # A dropped drone link may reconnect with the same token…
    assert await auth(client, **publish) == 200
    await hook(client, "ready", path, source_type="rtmpConn")
    listed = (await client.get("/api/v1/staff/streams", headers=manager)).json()["items"]
    item = next(i for i in listed if i["id"] == drone["id"])
    assert item["report_id"] is None and item["label"] == "Drone PC Sfax 1" and item["last_location"]["lat"] == 34.74
    # …until staff stop it: then it is retired.
    await hook(client, "not_ready", path, source_type="rtmpConn")
    stopped = await client.post(f"/api/v1/staff/streams/{drone['id']}/stop", headers=manager)
    assert stopped.status_code == 200
    assert await auth(client, **publish) == 401
    assert fake_mediamtx.kicked == [path]
    audit = list(
        await session.scalars(
            text("SELECT action FROM audit.log WHERE target = :t ORDER BY seq"), {"t": f"stream:{drone['id']}"}
        )
    )
    assert audit == ["stream.register", "stream.stop"]


# ---------------------------------------------------------------- life cycle worker


async def test_sweep_expires_and_ends_streams(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession, fake_mediamtx: FakeMediamtx
) -> None:
    headers, unused = await citizen_stream(client, make_token)
    _, long = await citizen_stream(client, make_token)
    await go_live(client, long["path"])
    await session.execute(
        text("UPDATE reports.live_stream SET expires_at = now() - interval '1 second' WHERE id = :id"),
        {"id": unused["stream_id"]},
    )
    await session.execute(
        text("UPDATE reports.live_stream SET started_at = now() - interval '16 minutes' WHERE id = :id"),
        {"id": long["stream_id"]},
    )
    await session.commit()
    kicked = await worker.sweep(get_sessionmaker())
    assert long["path"] in kicked and long["path"] in fake_mediamtx.kicked
    expired = await row(session, unused["stream_id"])
    assert expired.status == "expired" and expired.end_reason == "token_expired"
    assert (await row(session, long["stream_id"])).end_reason == "max_duration"
    # The report may stream again.
    assert (await client.post(f"/api/v1/reports/{unused['report_id']}/streams", headers=headers)).status_code == 201


async def test_expired_stream_is_replaced_at_once(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession
) -> None:
    headers, stream = await citizen_stream(client, make_token)
    await session.execute(
        text("UPDATE reports.live_stream SET expires_at = now() - interval '1 second' WHERE id = :id"),
        {"id": stream["stream_id"]},
    )
    await session.commit()
    again = await open_stream(client, headers, stream["report_id"])
    assert again["stream_id"] != stream["stream_id"]
    assert (await row(session, stream["stream_id"])).status == "expired"


class FakeVision:
    def __init__(self) -> None:
        self.watching: dict[str, tuple[str, str]] = {}
        self.fail: Exception | None = None
        self.detect_result: dict[str, Any] = {"model": "fake-yolo", "detections": []}
        self.images: list[bytes] = []

    async def watch(self, stream_id: str, rtsp_url: str, callback_url: str) -> None:
        if self.fail:
            raise self.fail
        self.watching[stream_id] = (rtsp_url, callback_url)

    async def unwatch(self, stream_id: str) -> None:
        if self.fail:
            raise self.fail
        self.watching.pop(stream_id, None)

    async def detect(self, image: bytes, content_type: str) -> dict[str, Any]:
        if self.fail:
            raise self.fail
        self.images.append(image)
        return self.detect_result


async def test_vision_watch_list_follows_live_streams(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession
) -> None:
    _, stream = await citizen_stream(client, make_token)
    sid = stream["stream_id"]
    await go_live(client, stream["path"])
    # Streams left live by other tests are out of the way (the worker takes 20 per pass, oldest first).
    await session.execute(
        text("UPDATE reports.live_stream SET vision_state = 'idle' WHERE id <> :id AND vision_state <> 'idle'"),
        {"id": sid},
    )
    await session.commit()
    vision = FakeVision()
    vision.fail = VisionBusy("busy")
    await worker.sync_vision(get_sessionmaker(), vision)
    busy = await row(session, sid)
    assert busy.vision_state == "requested" and busy.vision_attempts == 1
    assert busy.vision_next_attempt_at > datetime.now(UTC)

    vision.fail = None
    await session.execute(
        text("UPDATE reports.live_stream SET vision_next_attempt_at = now() WHERE id = :id"), {"id": sid}
    )
    await session.commit()
    await worker.sync_vision(get_sessionmaker(), vision)
    assert vision.watching[sid] == (
        f"rtsp://mediamtx:8554/live/{sid}",
        "http://api:8000/internal/vision/detections",
    )
    assert (await row(session, sid)).vision_state == "watching"
    await hook(client, "not_ready", stream["path"])
    await worker.sync_vision(get_sessionmaker(), vision)
    assert sid not in vision.watching and (await row(session, sid)).vision_state == "idle"


async def test_without_vision_service_nothing_waits(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession
) -> None:
    _, stream = await citizen_stream(client, make_token)
    await go_live(client, stream["path"])
    await worker.sync_vision(get_sessionmaker(), None)
    assert (await row(session, stream["stream_id"])).vision_state == "disabled"


async def test_uploaded_images_are_analysed(
    client: httpx.AsyncClient,
    make_token: TokenFactory,
    session: AsyncSession,
    fake_store: FakeStore,
    staff: Staff,
) -> None:
    headers = await new_citizen(client, make_token)
    report = await new_report(client, headers)
    media_id = uuid.uuid4()
    key = f"uploads/{media_id.hex}"
    fake_store.objects[key] = JPEG
    await session.execute(
        text(
            "INSERT INTO reports.media (id, report_id, kind, object_key, sha256, bytes, content_type, verified_type, "
            "status, stored_at) VALUES (:id, :r, 'image', :k, :h, :b, 'image/jpeg', 'image/jpeg', 'stored', now())"
        ),
        {"id": media_id, "r": report["id"], "k": key, "h": hashlib.sha256(JPEG).hexdigest(), "b": len(JPEG)},
    )
    # Images left by other tests are out of the way (only this one is waiting).
    await session.execute(
        text(
            'UPDATE reports.media SET analysis = COALESCE(analysis, \'{}\') || \'{"vision": {"state": "done"}}\' '
            "WHERE kind = 'image' AND id <> :id"
        ),
        {"id": media_id},
    )
    await session.commit()
    vision = FakeVision()
    sessionmaker = get_sessionmaker()

    # Service down: retried later, nothing else waits.
    vision.fail = VisionUnavailable("ConnectError")
    assert await worker.analyse_image(sessionmaker, vision, fake_store) is True
    analysis = await session.scalar(text("SELECT analysis FROM reports.media WHERE id = :id"), {"id": media_id})
    assert analysis["vision"]["state"] == "retry" and analysis["vision"]["attempts"] == 1
    await session.rollback()

    vision.fail = None
    vision.detect_result = {
        "model": "fake-yolo",
        "detections": [
            {"label": "fire", "confidence": 0.82, "boxes": [[0.2, 0.2, 0.5, 0.7, 0.82]]},
            {"label": "person", "confidence": 0.3, "boxes": []},
        ],
    }
    await session.execute(
        text(
            "UPDATE reports.media SET analysis = jsonb_set(analysis, '{vision,next_attempt_at}', "
            "to_jsonb(now()::text)) WHERE id = :id"
        ),
        {"id": media_id},
    )
    await session.commit()
    assert await worker.analyse_image(sessionmaker, vision, fake_store) is True
    assert vision.images == [JPEG]
    analysis = await session.scalar(text("SELECT analysis FROM reports.media WHERE id = :id"), {"id": media_id})
    assert analysis["vision"]["state"] == "done" and [d["label"] for d in analysis["vision"]["detections"]] == ["fire"]
    confirmed = await session.scalar(
        text("SELECT confirmed FROM reports.stream_detection WHERE media_id = :id"), {"id": media_id}
    )
    assert confirmed is True
    await session.rollback()
    detail = (await client.get(f"/api/v1/staff/reports/{report['id']}", headers=staff(gouvernorat=61))).json()
    component = next(c for c in detail["analysis"]["priority"]["components"] if c["key"] == "vision_fire")
    assert component["detail"]["source"] == "image" and component["value"] == pytest.approx(0.82, abs=0.001)


# ---------------------------------------------------------------- privacy and retention


async def test_export_and_delete(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession, fake_mediamtx: FakeMediamtx
) -> None:
    headers, stream = await citizen_stream(client, make_token)
    sid = stream["stream_id"]
    await go_live(client, stream["path"])
    await client.post(
        f"/api/v1/streams/{sid}/location", json={"lat": 34.75, "lon": 10.77, "accuracy_m": 5}, headers=headers
    )
    export = (await client.get("/api/v1/me/export", headers=headers)).json()
    exported = next(s for s in export["streams"] if s["id"] == sid)
    assert exported["report_id"] == stream["report_id"] and exported["status"] == "live"
    assert exported["track"][0]["lat"] == 34.75 and exported["track"][0]["accuracy_m"] == 5
    assert "publish_token" not in str(exported)

    r = await client.post("/api/v1/me/delete", json={"confirm": "DELETE"}, headers=headers)
    assert r.status_code == 202
    ended = await row(session, sid)
    assert ended.status == "ended" and ended.publish_token_hash is None
    assert fake_mediamtx.kicked == [stream["path"]]
    details = await session.scalar(
        text("SELECT details FROM audit.log WHERE action = 'user.delete' AND target = :t"),
        {"t": f"account:{ended.user_id}"},
    )
    assert details["streams_ended"] == 1


async def test_retention_of_streams(
    client: httpx.AsyncClient,
    make_token: TokenFactory,
    session: AsyncSession,
    staff: Staff,
    fake_store: FakeStore,
    recordings: Path,
) -> None:
    headers, stream = await citizen_stream(client, make_token)
    sid = stream["stream_id"]
    await go_live(client, stream["path"])
    await client.post(f"/api/v1/streams/{sid}/location", json={"lat": 34.7512, "lon": 10.7734}, headers=headers)
    file = segment(recordings, stream["path"], "r.mp4", b"citizen recording")
    await hook(client, "segment_complete", stream["path"], segment_path=str(file), segment_duration_s=2.0)
    await hook(client, "not_ready", stream["path"])
    await drain(fake_store)
    operator = staff(gouvernorat=61)
    for target in ("in_progress", "closed"):
        await client.post(
            f"/api/v1/staff/reports/{stream['report_id']}/status", json={"status": target}, headers=operator
        )

    manager = staff(roles=["ops_manager"], gouvernorat=61)
    drone = (
        await client.post(
            "/api/v1/staff/streams",
            json={"source": "camera", "label": "Cam port", "gouvernorat_code": 61},
            headers=manager,
        )
    ).json()
    await hook(client, "ready", drone["path"], source_type="rtspSession")
    cam_file = segment(recordings, drone["path"], "c.mp4", b"camera recording")
    await hook(client, "segment_complete", drone["path"], segment_path=str(cam_file), segment_duration_s=2.0)
    await hook(client, "not_ready", drone["path"])
    await drain(fake_store)
    cam_key = f"recordings/{drone['id']}/1.mp4"
    assert cam_key in fake_store.objects

    long_ago = datetime.now(UTC) - timedelta(days=6 * 365)
    await session.execute(
        text("UPDATE reports.report SET updated_at = :t WHERE id = :id"), {"t": long_ago, "id": stream["report_id"]}
    )
    await session.execute(
        text("UPDATE reports.live_stream SET ended_at = :t WHERE id = :id"), {"t": long_ago, "id": drone["id"]}
    )
    await session.commit()
    sessionmaker = get_sessionmaker()
    assert await retention.run_job(sessionmaker, "reports", retention.anonymise_reports) >= 1
    assert await retention.run_job(sessionmaker, "streams", retention.purge_streams) >= 1

    anonymised = await row(session, sid)
    assert str(anonymised.user_id) == "00000000-0000-0000-0000-000000000000"
    points = await session.scalar(
        text("SELECT count(*) FROM reports.stream_location WHERE stream_id = :id"), {"id": sid}
    )
    media = await session.scalar(text("SELECT count(*) FROM reports.media WHERE stream_id = :id"), {"id": sid})
    assert points == 0 and media == 0 and f"recordings/{sid}/1.mp4" in fake_store.deleted
    coarse = await session.scalar(
        text("SELECT ST_Y(CAST(last_location AS geometry)) FROM reports.live_stream WHERE id = :id"), {"id": sid}
    )
    assert coarse == pytest.approx(34.75)
    gone = await session.scalar(text("SELECT count(*) FROM reports.live_stream WHERE id = :id"), {"id": drone["id"]})
    assert gone == 0 and cam_key in fake_store.deleted


# ---------------------------------------------------------------- simulation


async def test_sim_stream_registration(
    client: httpx.AsyncClient, staff: Staff, fake_mediamtx: FakeMediamtx, monkeypatch: pytest.MonkeyPatch
) -> None:
    label = f"camera {uuid.uuid4().hex[:8]}"
    body = {"label": label, "gouvernorat_code": 11, "lat": 36.8, "lon": 10.18}
    assert (await client.post("/internal/sim/streams", json=body)).status_code == 404
    r = await client.post("/internal/sim/streams", json=body, headers=SIM)
    assert r.status_code == 201, r.text
    sim = r.json()
    assert sim["rtsp_url"] == f"rtsp://localhost:8554/live/{sim['id']}"
    publish = {
        "action": "publish",
        "path": sim["path"],
        "protocol": "rtsp",
        "user": "sim",
        "password": sim["publish_token"],
    }
    assert await auth(client, **publish) == 200
    await hook(client, "ready", sim["path"], source_type="rtspSession")
    listed = (await client.get("/api/v1/staff/streams", headers=staff(gouvernorat=11))).json()["items"]
    item = next(i for i in listed if i["id"] == sim["id"])
    assert item["simulated"] is True and item["source"] == "sim" and item["label"] == f"[SIM] {label}"
    status = (await client.get(f"/internal/sim/streams/{sim['id']}", headers=SIM)).json()
    assert status == {"id": sim["id"], "status": "live", "recordings_count": 0, "simulated": True}

    # A restarted simulator replaces its stream.
    again = (await client.post("/internal/sim/streams", json=body, headers=SIM)).json()
    assert again["id"] != sim["id"] and fake_mediamtx.kicked == [sim["path"]]
    assert await auth(client, **publish) == 401
    monkeypatch.setattr(get_settings(), "app_env", "production")
    assert (await client.post("/internal/sim/streams", json=body, headers=SIM)).status_code == 404


async def test_live_feed_routes_stream_events_by_scope() -> None:
    from app.modules.reports.live import _route

    for subject in ("stream.started", "stream.ended", "stream.location", "stream.alert", "stream.recording"):
        route = _route(subject, {"stream_id": "x", "gouvernorat_code": 61})
        assert route is not None and route[0] == "reports"
