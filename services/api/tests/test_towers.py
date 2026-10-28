"""Watch towers (L5b, docs/phase-l/design-l5.md §3.2): the register and its scope, the camera's publish token and the
edge key shown once, the field of view, and the signed fire or smoke an edge computer confirmed in 3 of 5 frames,
relayed by the gateway beside MediaMTX (and every way an event is refused). An event becomes a suggestion in the
alert centre and a stream.alert, never an automatic report."""

import base64
import hashlib
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.modules.audit.models import AuditLog
from app.modules.reports.models import Media, Report
from app.modules.streams.models import LiveStream, StreamDetection
from app.modules.towers import domain
from app.modules.weather.models import AlertSuggestion

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/staff/towers"
INGEST = "/internal/towers/events"
GATEWAY = {"X-Gateway-Token": "test-sensor-gateway-token-0001"}
JENDOUBA, BIZERTE = 32, 23
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64 + b"\xff\xd9"


def _code() -> str:
    return f"TWR-{secrets.token_hex(4)}"


async def _create(client: httpx.AsyncClient, staff: Staff, **extra: Any) -> dict[str, Any]:
    body = {
        "code": _code(),
        "label": "برج عين دراهم [SIM]",
        "lat": 36.78,
        "lon": 8.69,
        "bearing_deg": 90,
        "fov_deg": 60,
        "range_m": 8000,
        **extra,
    }
    r = await client.post(URL, json=body, headers=staff(["ops_manager"], gouvernorat=JENDOUBA))
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def _event(
    tower: str,
    key: str,
    *,
    label: str = "fire",
    confidence: str = "0.87",
    hits: str = "3",
    frames: str = "5",
    at: datetime | None = None,
    frame: bytes | None = JPEG,
) -> dict[str, str]:
    stamp = (at or datetime.now(UTC)).isoformat(timespec="seconds")
    sha = hashlib.sha256(frame).hexdigest() if frame else ""
    return {
        "tower": tower,
        "at": stamp,
        "label": label,
        "confidence": confidence,
        "hits": hits,
        "frames": frames,
        "model": "ehimaya-fire-v3 [SIM]",
        "frame_jpeg_b64": base64.b64encode(frame).decode() if frame else "",
        "sig": domain.sign(key, tower, stamp, label, confidence, hits, frames, sha),
    }


def test_rules_free_of_the_database() -> None:
    key = domain.new_key()
    fields = ("T1", "2026-10-28T20:00:00+01:00", "fire", "0.9", "3", "5", "")
    sig = domain.sign(key, *fields)
    assert domain.signature_valid(key, sig, *fields)
    # The same vector as the gateway's simulator and the edge program (services/sensor-gateway tests).
    vector = "da3de1c6f641ec22d489b15c5bb21af095bb49ba96726ef0440bf02abb79d959"
    assert domain.sign("00" * 32, "TWR-1", "2026-10-28T20:00:00+00:00", "fire", "0.87", "3", "5", "") == vector
    assert not domain.signature_valid(key, sig, *fields[:3], "0.91", *fields[4:])
    assert not domain.signature_valid(key, sig, *fields[:6], "zz")
    assert domain.parse_confidence("1.0") == 1.0 and domain.parse_confidence("1.5") is None
    assert domain.parse_confidence("0.5e1") is None
    assert domain.parse_confirmation("3", "5") == (3, 5)
    assert domain.parse_confirmation("2", "5") is None and domain.parse_confirmation("3", "4") is None
    # The wedge starts and ends at the tower; it opens around the bearing (east here) and reaches the range.
    ring = domain.wedge(36.0, 9.0, 90, 60, 10_000)
    assert ring[0] == ring[-1] == [9.0, 36.0]
    assert all(p[0] > 9.0 for p in ring[1:-1])
    circle = domain.wedge(36.0, 9.0, 0, 360, 1000)
    assert circle[0] == circle[-1] and [9.0, 36.0] not in circle


async def test_register_scope_and_secrets_shown_once(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession
) -> None:
    created = await _create(client, staff)
    tower, key = created["tower"], created["edge_key"]
    assert len(key) == 64 and created["publish_token"] and created["publish_url_rtsp"].endswith(f"live/{tower['id']}")
    assert tower["stream_status"] == "pending" and tower["last_event"] is None
    assert len(tower["field_of_view"]) == 19 and tower["field_of_view"][0] == [8.69, 36.78]
    # It is a fixed camera stream of the gouvernorat, so the existing stream wall shows it too.
    stream = await session.get(LiveStream, tower["id"])
    assert stream is not None and stream.source == "camera" and stream.gouvernorat_code == JENDOUBA
    listed = (await client.get(URL, headers=staff(["operator"], gouvernorat=JENDOUBA))).json()
    mine = next(t for t in listed["items"] if t["id"] == tower["id"])
    assert "edge_key" not in mine and listed["can_manage"] is False
    logs = (await session.scalars(select(AuditLog).where(AuditLog.target == f"stream:{tower['id']}"))).all()
    assert logs and all(key not in str(log.details) and created["publish_token"] not in str(log.details) for log in logs)
    other = (await client.get(URL, headers=staff(["operator"], gouvernorat=BIZERTE))).json()
    assert tower["id"] not in {t["id"] for t in other["items"]}
    central = (await client.get(URL, headers=staff(["operator"], gouvernorat=None))).json()
    assert tower["id"] in {t["id"] for t in central["items"]}
    # Only the operations manager registers, in their own gouvernorat; the code is unique.
    body = {"code": _code(), "label": "x [SIM]", "lat": 36.9, "lon": 8.7, "bearing_deg": 0, "fov_deg": 90}
    body["range_m"] = 5000
    assert (await client.post(URL, json=body, headers=staff(["operator"], gouvernorat=JENDOUBA))).status_code == 403
    manager = staff(["ops_manager"], gouvernorat=JENDOUBA)
    assert (await client.post(URL, json=body | {"gouvernorat_code": BIZERTE}, headers=manager)).status_code == 403
    assert (await client.post(URL, json=body | {"code": tower["code"].lower()}, headers=manager)).status_code == 409
    assert (await client.post(URL, json=body | {"fov_deg": 2}, headers=manager)).status_code == 422
    # Turning the camera moves its wedge; another gouvernorat's manager cannot (it reads as missing).
    edit = {"label": "برج [SIM]", "lat": 36.78, "lon": 8.69, "bearing_deg": 270, "fov_deg": 60, "range_m": 8000}
    r = await client.put(f"{URL}/{tower['id']}", json=edit, headers=staff(["ops_manager"], gouvernorat=BIZERTE))
    assert r.status_code == 404
    r = await client.put(f"{URL}/{tower['id']}", json=edit, headers=manager)
    assert r.status_code == 200 and all(p[0] <= 8.69 for p in r.json()["field_of_view"])
    # Rotation: a new key, and the old one no longer signs.
    rotated = await client.post(f"{URL}/{tower['id']}/key", headers=manager)
    assert rotated.status_code == 200 and rotated.json()["edge_key"] != key
    r = await client.post(INGEST, json=_event(tower["code"], key), headers=GATEWAY)
    assert r.json() == {"accepted": False, "reason": "bad_signature", "suggestion": False}


async def test_gateway_is_local_and_token_bound(client: httpx.AsyncClient, staff: Staff) -> None:
    created = await _create(client, staff)
    body = _event(created["tower"]["code"], created["edge_key"], label="smoke")
    assert (await client.post(INGEST, json=body)).status_code == 401
    outside = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, client=("203.0.113.9", 4000)), base_url="http://api.test"
    )
    async with outside:
        assert (await outside.post(INGEST, json=body, headers=GATEWAY)).status_code == 403
    r = await client.post(INGEST, json=body, headers=GATEWAY)
    assert r.status_code == 200 and r.json() == {"accepted": True, "reason": None, "suggestion": True}


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"tower": "NOPE-1"}, "unknown_tower"),
        ({"frame_jpeg_b64": base64.b64encode(b"GIF89a").decode()}, "bad_frame"),
        ({"confidence": "0.99"}, "bad_signature"),
    ],
)
async def test_tampered_events_are_refused(
    client: httpx.AsyncClient, staff: Staff, change: dict[str, str], reason: str
) -> None:
    created = await _create(client, staff)
    body = _event(created["tower"]["code"], created["edge_key"]) | change
    r = await client.post(INGEST, json=body, headers=GATEWAY)
    assert r.json() == {"accepted": False, "reason": reason, "suggestion": False}


async def test_events_checked_kept_and_suggested(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession
) -> None:
    created = await _create(client, staff)
    tower, key = created["tower"], created["edge_key"]
    code = tower["code"]
    now = datetime.now(UTC)
    refused = {
        "bad_time": _event(code, key, at=now - timedelta(hours=1)),
        "bad_value": _event(code, key, label="person"),
        "not_confirmed": _event(code, key, hits="2"),
        "low_confidence": _event(code, key, confidence="0.2"),
    }
    for reason, body in refused.items():
        r = await client.post(INGEST, json=body, headers=GATEWAY)
        assert r.json()["reason"] == reason, (reason, r.text)
    smoke = _event(code, key, label="smoke", confidence="0.7", at=now - timedelta(minutes=2))
    r = await client.post(INGEST, json=smoke, headers=GATEWAY)
    assert r.json() == {"accepted": True, "reason": None, "suggestion": True}
    assert (await client.post(INGEST, json=smoke, headers=GATEWAY)).json()["reason"] == "replay"
    # Fire after smoke raises the suggestion; a second fire does not repeat it.
    fire = _event(code, key, at=now - timedelta(minutes=1))
    assert (await client.post(INGEST, json=fire, headers=GATEWAY)).json()["suggestion"] is True
    again = _event(code, key, confidence="0.9", frame=None)
    assert (await client.post(INGEST, json=again, headers=GATEWAY)).json() == {
        "accepted": True,
        "reason": None,
        "suggestion": False,
    }
    suggestions = (
        await session.scalars(
            select(AlertSuggestion)
            .where(AlertSuggestion.evidence["tower_id"].astext == tower["id"])
            .order_by(AlertSuggestion.created_at)
        )
    ).all()
    assert [(s.metric, s.severity) for s in suggestions] == [("tower_smoke", "medium"), ("tower_fire", "high")]
    first = suggestions[1]
    assert first.hazard == "forest_fire" and first.simulated and first.gouvernorat_codes == [JENDOUBA]
    assert first.evidence["hits"] == 3 and first.evidence["frames"] == 5 and first.evidence["bearing_deg"] == 90
    # The frame is kept beside the camera's stream; the detection is confirmed; no report is ever created.
    media = await session.get(Media, first.evidence["media_id"])
    assert media is not None and media.report_id is None and media.analysis and media.analysis["source"] == "edge"
    detections = (
        await session.scalars(select(StreamDetection).where(StreamDetection.stream_id == tower["id"]))
    ).all()
    assert len(detections) == 3 and all(d.confirmed and (d.model or "").startswith("edge") for d in detections)
    assert await session.scalar(select(Report.id).where(Report.id == tower["id"])) is None
    reader = staff(["operator"], gouvernorat=JENDOUBA)
    listed = (await client.get(URL, headers=reader)).json()
    mine = next(t for t in listed["items"] if t["id"] == tower["id"])
    assert mine["last_event"]["label"] == "fire" and mine["last_event"]["confidence"] == pytest.approx(0.9)
    hist = (await client.get(f"{URL}/{tower['id']}/events", headers=reader)).json()
    assert [e["label"] for e in hist["items"]] == ["fire", "fire", "smoke"]
    page = await client.get("/api/v1/staff/weather/suggestions", headers=staff(["content_editor"], gouvernorat=JENDOUBA))
    assert page.status_code == 200, page.text
    assert {s["metric"] for s in page.json()["items"]} >= {"tower_fire", "tower_smoke"}
