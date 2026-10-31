# covers: review points 3, 17 and 25 (phase D, docs/phase-d/design-d.md)
"""Phase D: the pre-alert of an institution's camera (owner first, the room after the delay) and the push guard."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_system_sessionmaker
from app.modules.notify import outbox
from app.modules.orgs import prealert
from tests.conftest import FakeMediamtx, FakeStore, TokenFactory, bearer
from tests.test_crew import write
from tests.test_crew_field import _mission
from tests.test_orgs import add_member, register
from tests.test_streams import auth, frame, go_live

Staff = Callable[..., dict[str, str]]
User = Callable[..., dict[str, str]]
TUNIS = {"lat": 36.8065, "lon": 10.1815}


@pytest.fixture
def user(make_token: TokenFactory) -> User:
    def _user(email: str | None = None, verified: bool = True, **claims: Any) -> dict[str, str]:
        email = email or f"u{uuid.uuid4().hex[:10]}@example.tn"
        token = make_token(roles=["citizen"], email=email, email_verified=verified, name="User", **claims)
        return bearer(token)

    return _user


async def active_org(client: httpx.AsyncClient, staff: Staff, admin: dict[str, str], **overrides: Any) -> str:
    org = await register(client, admin, **overrides)
    r = await client.post(
        f"/api/v1/staff/orgs/{org['id']}/review",
        json={"decision": "approve"},
        headers=staff(["org_auditor"], gouvernorat=11),
    )
    assert r.status_code == 200, r.text
    return str(org["id"])


async def org_camera(client: httpx.AsyncClient, staff: Staff, user: User) -> tuple[str, dict[str, str], str, str]:
    """An approved institution in Tunis (11), its admin, and a camera registered for it, live."""
    admin = user()
    org_id = await active_org(client, staff, admin, location=TUNIS)
    r = await client.post(
        "/api/v1/staff/streams",
        json={"source": "camera", "label": "Tapo C200 entrepôt", "gouvernorat_code": 11, "org_id": org_id, **TUNIS},
        headers=staff(["ops_manager"], gouvernorat=11),
    )
    assert r.status_code == 201, r.text
    cam = r.json()
    await go_live(client, cam["path"])
    return org_id, admin, cam["id"], cam["path"]


async def confirm_fire(client: httpx.AsyncClient, stream_id: str) -> None:
    for _ in range(3):
        assert (await frame(client, stream_id, fire=0.85)).status_code == 204


async def pending(client: httpx.AsyncClient, admin: dict[str, str], org_id: str) -> list[dict[str, Any]]:
    r = await client.get(f"/api/v1/orgs/{org_id}/prealerts", params={"state": "pending"}, headers=admin)
    assert r.status_code == 200, r.text
    return r.json()  # type: ignore[no-any-return]


async def test_camera_of_an_institution_must_be_in_its_gouvernorat(
    client: httpx.AsyncClient, staff: Staff, user: User
) -> None:
    admin = user()
    org_id = await active_org(client, staff, admin, location=TUNIS)
    r = await client.post(
        "/api/v1/staff/streams",
        json={"source": "drone", "label": "x", "gouvernorat_code": 11, "org_id": org_id},
        headers=staff(["ops_manager"], gouvernorat=11),
    )
    assert r.status_code == 422 and r.json()["detail"] == "invalid_org"


async def test_owner_is_told_first_and_a_false_alarm_never_reaches_the_room(
    client: httpx.AsyncClient, staff: Staff, user: User, session: AsyncSession, fake_store: FakeStore
) -> None:
    org_id, admin, sid, _ = await org_camera(client, staff, user)
    await confirm_fire(client, sid)
    (alert,) = await pending(client, admin, org_id)
    assert alert["label"] == "fire" and alert["state"] == "pending" and alert["has_frame"]
    assert 80 <= alert["seconds_left"] <= 90 and alert["report_id"] is None
    # Another confirming frame does not open a second pre-alert.
    await frame(client, sid, fire=0.95)
    assert len(await pending(client, admin, org_id)) == 1

    # A content-free critical push to the administrator, ids only.
    pushes = (
        await session.execute(
            text("SELECT payload FROM notify.outbox WHERE channel = 'push' AND payload->>'type' = 'prealert'")
        )
    ).scalars()
    data = [p["data"] for p in pushes if p["data"].get("prealert_id") == alert["id"]]
    assert data == [{"prealert_id": alert["id"], "org_id": org_id, "redacted": "1"}]

    # A plain member cannot answer; an answer without a reason is refused.
    member = await add_member(client, admin, org_id, user, "member")
    url = f"/api/v1/orgs/{org_id}/prealerts/{alert['id']}/decision"
    assert (await client.post(url, json={"action": "cancel", "reason": "خطأ"}, headers=member)).status_code == 403
    assert (await client.post(url, json={"action": "cancel"}, headers=admin)).status_code == 422
    r = await client.post(url, json={"action": "cancel", "reason": "تجربة المطبخ"}, headers=admin)
    assert r.status_code == 200 and r.json()["state"] == "cancelled" and r.json()["report_id"] is None
    assert (await client.post(url, json={"action": "confirm"}, headers=admin)).status_code == 409

    # The worker has nothing to raise; the room sees the false alarm in its list.
    async with get_system_sessionmaker()() as s, s.begin():
        await prealert.escalate_due(s, datetime.now(UTC) + timedelta(minutes=5))
    listed = (await client.get("/api/v1/staff/prealerts", headers=staff(["operator"], gouvernorat=11))).json()
    mine = next(p for p in listed if p["id"] == alert["id"])
    assert mine["state"] == "cancelled" and mine["reason"] == "تجربة المطبخ"
    assert not [
        p
        for p in (await client.get("/api/v1/staff/prealerts", headers=staff(["operator"]))).json()
        if p["id"] == alert["id"]
    ]


async def test_confirmation_reports_at_once_with_the_camera(
    client: httpx.AsyncClient, staff: Staff, user: User, fake_store: FakeStore
) -> None:
    org_id, admin, sid, _ = await org_camera(client, staff, user)
    await confirm_fire(client, sid)
    (alert,) = await pending(client, admin, org_id)
    url = f"/api/v1/orgs/{org_id}/prealerts/{alert['id']}/decision"
    r = await client.post(url, json={"action": "confirm"}, headers=admin)
    assert r.status_code == 200, r.text
    report_id = r.json()["report_id"]
    assert r.json()["state"] == "confirmed" and report_id
    operator = staff(["operator"], gouvernorat=11)
    report = (await client.get(f"/api/v1/staff/reports/{report_id}", headers=operator)).json()
    assert report["category"] == "fire" and report["source"] == "iot"
    stream = (await client.get(f"/api/v1/staff/streams/{sid}", headers=operator)).json()
    assert stream["report_id"] == report_id
    frame_url = await client.get(f"/api/v1/orgs/{org_id}/prealerts/{alert['id']}/frame", headers=admin)
    assert frame_url.status_code == 200 and frame_url.json()["url"]


async def test_no_answer_raises_it_to_the_room_after_the_delay(
    client: httpx.AsyncClient, staff: Staff, user: User, session: AsyncSession, fake_store: FakeStore
) -> None:
    org_id, admin, sid, _ = await org_camera(client, staff, user)
    await confirm_fire(client, sid)
    (alert,) = await pending(client, admin, org_id)
    async with get_system_sessionmaker()() as s, s.begin():
        assert await prealert.escalate_due(s, datetime.now(UTC)) == 0
    async with get_system_sessionmaker()() as s, s.begin():
        assert await prealert.escalate_due(s, datetime.now(UTC) + timedelta(seconds=91)) >= 1
    listed = (await client.get(f"/api/v1/orgs/{org_id}/prealerts", headers=admin)).json()
    raised = next(p for p in listed if p["id"] == alert["id"])
    assert raised["state"] == "escalated" and raised["report_id"]
    # The institution sees the report in its own list (it was sent on its behalf).
    text_ = (
        await session.execute(
            text("SELECT source, organization_id FROM reports.report WHERE id = :id"), {"id": raised["report_id"]}
        )
    ).one()
    assert text_.source == "iot" and str(text_.organization_id) == org_id


async def test_the_delay_is_a_setting(client: httpx.AsyncClient, staff: Staff) -> None:
    r = await client.get("/api/v1/staff/settings", headers=staff(["sysadmin"], gouvernorat=None))
    assert r.status_code == 200
    spec = next(t for t in r.json()["thresholds"] if t["name"] == "orgs.prealert_seconds")
    assert (spec["default"], spec["low"], spec["high"], spec["unit"]) == (90, 30, 600, "seconds")


# ---------------------------------------------------------------- review point 3: nothing personal through Firebase


def test_push_data_refuses_unknown_keys_and_free_text() -> None:
    assert outbox.check_push_data({"report_id": uuid.uuid4(), "status": "in_progress"})["status"] == "in_progress"
    with pytest.raises(outbox.PersonalDataInPush):
        outbox.check_push_data({"name": "Mohamed"})
    with pytest.raises(outbox.PersonalDataInPush):
        outbox.check_push_data({"status": "فريق في الطريق"})
    with pytest.raises(outbox.PersonalDataInPush):
        outbox.check_push_data({"id": "a" * 65})


def test_every_push_in_the_code_uses_allowed_keys_only() -> None:
    """A static check over the code: every literal data key given to a push is in the allowed list."""
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "app"
    seen: set[str] = set()
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in ("push", "staff_push") or not (
                isinstance(node.func.value, ast.Name) and node.func.value.id == "outbox"
            ):
                continue
            for arg in node.args:
                if isinstance(arg, ast.Dict):
                    seen |= {k.value for k in arg.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    assert seen and seen <= outbox.PUSH_DATA_KEYS, seen - outbox.PUSH_DATA_KEYS


# ---------------------------------------------------------------- review point 16: the demonstration seed


async def test_demo_seed_is_idempotent_and_raises_a_simulated_prealert(session: AsyncSession) -> None:
    from app import demo

    sub = str(uuid.uuid4())
    first = await demo.seed(sub, 21)
    assert first["leader_code"] and first["org_id"]
    again = await demo.seed(sub, 21)
    assert again["org_id"] == first["org_id"]
    raised = await demo.raise_prealert("smoke")
    row = (
        await session.execute(
            text("SELECT state, simulated, label FROM org.prealert WHERE id = :id"), {"id": raised["prealert_id"]}
        )
    ).one()
    assert (row.state, row.simulated, row.label) == ("pending", True, "smoke")
    # The shared test database keeps the institution between runs: this run's owner is its admin, once.
    roles = (
        (
            await session.execute(
                text("SELECT role FROM org.member WHERE org_id = :o AND user_id = :u"),
                {"o": first["org_id"], "u": first["owner_user_id"]},
            )
        )
        .scalars()
        .all()
    )
    assert roles == ["admin"]


async def test_team_streams_from_the_staff_app(
    client: httpx.AsyncClient, staff: Staff, fake_mediamtx: FakeMediamtx
) -> None:
    """Review point 17: the leader streams the scene of his mission; the room sees it with the incident."""
    leader, path, incident_id, place = await _mission(client, staff)
    r = await leader.post(f"{path}/stream")
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["whip_url"].endswith(f"/{created['path']}/whip")
    assert (await leader.post(f"{path}/stream")).json()["detail"] == "stream_already_active"
    # WebRTC only, with its token.
    assert (
        await auth(client, action="publish", path=created["path"], protocol="rtmp", token=created["publish_token"])
        == 401
    )
    assert (
        await auth(client, action="publish", path=created["path"], protocol="webrtc", token=created["publish_token"])
        == 200
    )
    await go_live(client, created["path"])
    stream_id = created["stream_id"]
    assert (await leader.post(f"/streams/{stream_id}/location", place)).status_code == 204

    room = staff(["operator"])
    wall = await client.get("/api/v1/staff/streams", params={"status": "live"}, headers=room)
    assert wall.status_code == 200, wall.text
    mine = next(s for s in wall.json()["items"] if s["id"] == stream_id)
    assert mine["source"] == "crew"
    assert mine["incident_id"] == incident_id
    assert mine["tracking_code"]  # the incident's first report

    # Another leader's phone does not reach it.
    other, *_ = await _mission(client, staff)
    assert (await other.get(f"/streams/{stream_id}")).status_code == 404

    stopped = await leader.post(f"/streams/{stream_id}/stop")
    assert stopped.json()["status"] == "ended"
    assert created["path"] in fake_mediamtx.kicked
    # Released, the mission no longer streams.
    assert (await leader.post(f"{path}/status", write(status="released"))).status_code == 200
    assert (await leader.post(f"{path}/stream")).json()["detail"] == "mission_closed"


async def test_dictation_of_a_free_text_field(
    client: httpx.AsyncClient, staff: Staff, fake_ai: Any, fake_store: Any
) -> None:
    """Review point 19: the text for the field, the audio deleted, the text kept measured, the log for the AI admin."""
    operator = staff(["operator"])
    field = f"report.note{uuid.uuid4().hex[:6]}"
    fake_ai.transcript = {"text": "حريق في غابة قرب المعتمدية", "language": "ar"}
    r = await client.post(
        "/api/v1/staff/dictation",
        params={"field": field, "lang": "ar"},
        content=b"OggS-audio",
        headers={**operator, "Content-Type": "audio/ogg"},
    )
    assert r.status_code == 200, r.text
    heard = r.json()
    assert heard["text"] == "حريق في غابة قرب المعتمدية"
    assert fake_store.objects == {} and fake_store.deleted[-1].startswith("dictation/")
    # Never a field that is not free text by name: the pattern refuses spaces and capitals.
    bad = await client.post(
        "/api/v1/staff/dictation",
        params={"field": "Bad Field"},
        content=b"x",
        headers={**operator, "Content-Type": "audio/ogg"},
    )
    assert bad.status_code == 422

    url = f"/api/v1/staff/dictation/{heard['dictation_id']}/kept"
    assert (await client.post(url, json={"text": "x y"}, headers=staff(["operator"]))).status_code == 404
    kept = await client.post(url, json={"text": "حريق في غابة قرب معتمدية نابل"}, headers=operator)
    assert kept.status_code == 200, kept.text
    assert kept.json() == {"words": 6, "word_errors": 1, "wer": 0.1667}
    assert (await client.post(url, json={"text": "x"}, headers=operator)).json()["detail"] == "dictation_already_kept"

    assert (await client.get("/api/v1/staff/dictation", headers=operator)).status_code == 403
    log = await client.get("/api/v1/staff/dictation", params={"field": field}, headers=staff(["ai_admin"]))
    assert log.status_code == 200, log.text
    body = log.json()
    stat = next(f for f in body["fields"] if f["field"] == field)
    assert stat == {"field": field, "dictations": 1, "kept": 1, "mean_wer": 0.1667}
    assert body["items"][0]["kept"] == "حريق في غابة قرب معتمدية نابل"
    async with get_system_sessionmaker()() as s:
        raw = await s.scalar(text("SELECT text_enc FROM ai.dictation WHERE id = :i"), {"i": heard["dictation_id"]})
        assert raw is not None and "حريق".encode() not in bytes(raw)


async def test_incident_media_in_one_gallery(
    client: httpx.AsyncClient, staff: Staff, fake_mediamtx: FakeMediamtx, _isolated_infra: FakeStore
) -> None:
    """Review point 21: the team's photos and voice notes and the streams, in time order, with the counts."""
    from tests.test_crew_field import JPEG, M4A, _upload

    leader, path, incident_id, _ = await _mission(client, staff)
    assert (await _upload(leader, path, "photo", JPEG, "image/jpeg")).status_code == 200
    assert (await _upload(leader, path, "voice", M4A, "audio/mp4", duration_s=8.0)).status_code == 200
    created = (await leader.post(f"{path}/stream")).json()
    await go_live(client, created["path"])

    url = f"/api/v1/staff/incidents/{incident_id}/media"
    r = await client.get(url, headers=staff(["operator"]))
    assert r.status_code == 200, r.text
    gallery = r.json()
    assert gallery["counts"] == {"photo": 1, "voice": 1, "stream": 1}
    assert gallery["live_streams"] == 1
    kinds = [(i["kind"], i["origin"], bool(i["url"])) for i in gallery["items"]]
    assert kinds == [("photo", "team", True), ("voice", "team", True), ("stream", "team", False)]
    assert gallery["items"][2]["live"] is True and gallery["items"][2]["stream_id"] == created["stream_id"]
    # Another gouvernorat's room does not see it; the reading is audited.
    assert (await client.get(url, headers=staff(["operator"], gouvernorat=11))).status_code == 404
    async with get_system_sessionmaker()() as s:
        n = await s.scalar(
            text("SELECT count(*) FROM audit.log WHERE action = 'incident.media' AND target = :t"),
            {"t": f"incident:{incident_id}"},
        )
        assert n == 1


async def test_menu_order_set_by_the_system_administrator(client: httpx.AsyncClient, staff: Staff) -> None:
    """Review point 9: the menu's order is a national setting the system administrator saves; checked and audited."""
    sysadmin = staff(["sysadmin"], gouvernorat=None)
    items = (await client.get("/api/v1/staff/settings", headers=staff(["operator"]))).json()["items"]
    current = next(i for i in items if i["key"] == "menu.order")
    assert current["editable"] is False
    url = "/api/v1/staff/settings/menu.order"
    order = {"groups": ["alerts", "ops"], "items": {"ops": ["/map", "/incidents", "/"]}}
    body = {"value": order, "version": current["version"], "reason": "ترتيب القائمة للعرض"}
    assert (await client.put(url, json=body, headers=staff(["operator"], gouvernorat=None))).status_code == 403
    for bad in (
        {"groups": ["ops", "ops"], "items": {}},
        {"groups": ["nowhere"], "items": {}},
        {"groups": [], "items": {"ops": ["javascript:alert(1)"]}},
    ):
        r = await client.put(url, json={**body, "value": bad}, headers=sysadmin)
        assert (r.status_code, r.json()["detail"]) == (422, "invalid_setting")
    r = await client.put(url, json=body, headers=sysadmin)
    assert r.status_code == 200, r.text
    assert r.json()["value"] == order
    # Back to the built-in order for the other tests.
    reset = {
        "value": {"groups": [], "items": {}},
        "version": r.json()["version"],
        "reason": "العودة إلى الترتيب الأصلي",
    }
    assert (await client.put(url, json=reset, headers=sysadmin)).status_code == 200


# ---------------------------------------------------------------- S2-5: a volunteer answers a call-out by SMS


def _eh3(key: str, volunteer: str, callout: str, reply: str, eta: int = 0, at: datetime | None = None) -> str:
    """The message the citizen app writes (apps/mobile/lib/features/volunteer/callout_sms.dart)."""
    from app.modules.volunteers import callout_sms

    ts = str(int((at or datetime.now(UTC)).timestamp()))
    v, c = volunteer.replace("-", ""), callout.replace("-", "")
    signed = "|".join(("EH3", v, c, reply, str(eta), ts))
    return f"EH3 {v} {c} {reply} {eta} {ts} {callout_sms.sign(key, signed)}"


async def test_volunteer_answers_a_callout_by_signed_sms(
    client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory, channels: Any
) -> None:
    from tests.test_crew_offline import _sms
    from tests.test_operations import approved_volunteer, near, new_incident, random_place

    place = random_place()
    incident_id, _ = await new_incident(client, staff, place)
    me = bearer(make_token(roles=["citizen"], email=f"v{uuid.uuid4().hex[:8]}@example.tn", email_verified=True))
    volunteer = await approved_volunteer(client, staff, me, near(place, 0.01))
    r = await client.post(
        f"/api/v1/staff/incidents/{incident_id}/callouts",
        json={"skill": "diving", "requested": 1, "radius_km": 10, "message": "غريق", "volunteer_ids": [volunteer]},
        headers=staff(["operator"]),
    )
    assert r.status_code == 201, r.text
    callout = r.json()["id"]
    key = (await client.post("/api/v1/me/volunteer/sms-key", headers=me)).json()
    assert key["volunteer_id"] == volunteer
    again = (await client.post("/api/v1/me/volunteer/sms-key", headers=me)).json()
    assert again["key"] == key["key"]  # made once, kept on the phone

    # A wrong key, an accept without minutes: ignored, nothing changes.
    assert (await _sms(client, _eh3("0" * 32, volunteer, callout, "accept", 15)))["reason"] == "invalid_signature"
    assert (await _sms(client, _eh3(key["key"], volunteer, callout, "accept", 0)))["reason"] == "eta_required"
    accepted = _eh3(key["key"], volunteer, callout, "accept", 15, datetime.now(UTC) - timedelta(seconds=30))
    assert (await _sms(client, accepted))["status"] == "applied"
    mine = (await client.get("/api/v1/me/callouts", headers=me)).json()
    assert mine[0]["my_status"] == "accepted"
    # The same message again (a replay) is ignored; then «وصلت».
    assert (await _sms(client, accepted))["reason"] == "replayed"
    assert (await _sms(client, _eh3(key["key"], volunteer, callout, "arrived")))["status"] == "applied"
    mine = (await client.get("/api/v1/me/callouts", headers=me)).json()
    assert mine[0]["my_status"] == "arrived"
    async with get_system_sessionmaker()() as s:
        actions = (
            await s.scalars(
                text("SELECT action FROM audit.log WHERE target = :t ORDER BY at"), {"t": f"callout:{callout}"}
            )
        ).all()
        assert actions[-2:] == ["volunteer.sms_accept", "volunteer.sms_arrived"]
