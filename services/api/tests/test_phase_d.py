# covers: review points 3 and 25 (phase D, docs/phase-d/design-d.md)
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
from tests.conftest import FakeStore, TokenFactory, bearer
from tests.test_orgs import add_member, register
from tests.test_streams import frame, go_live

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
    member = (
        (await session.execute(text("SELECT role FROM org.member WHERE org_id = :o"), {"o": first["org_id"]}))
        .scalars()
        .all()
    )
    assert member == ["admin"]
