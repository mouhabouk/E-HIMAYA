"""Crew accountability in danger zones, OS7 (docs/phase-os7/design-os7.md).

The team leader's phone and the rooms' board work together: entering the zone, the crew, away and back, the alarm,
the set time, the pause, the missing resource, the word from the scene, the headcount, the end and the archive.
"""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import text

from app.core.db import get_system_sessionmaker
from app.modules.features import registry
from tests.test_crew import Leader, _on_shift
from tests.test_operations import new_incident

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/staff/par"
SFAX = 61


def _place() -> dict[str, float]:
    # Inland in Sfax gouvernorat, in an area of its own (the sea is close to the east).
    return {"lat": 34.85 + uuid.uuid4().int % 1000 / 10_000, "lon": 10.30 + uuid.uuid4().int % 1000 / 10_000}


@pytest.fixture
def par(client: httpx.AsyncClient) -> httpx.AsyncClient:
    return client


async def _mission(par: httpx.AsyncClient, staff: Staff) -> tuple[str, Leader, str]:
    incident_id, _ = await new_incident(par, staff, {**_place(), "accuracy_m": 10.0})
    leader, resource = await _on_shift(par, staff)
    r = await par.post(
        f"/api/v1/staff/incidents/{incident_id}/assignments",
        json={"resource_id": resource["id"], "order": "إطفاء وبحث"},
        headers=staff(["operator"], SFAX),
    )
    assert r.status_code == 201, r.text
    return incident_id, leader, f"/missions/{r.json()['id']}/par"


async def _age(team_id: str, minutes: int) -> None:
    async with get_system_sessionmaker()() as s, s.begin():
        await s.execute(
            text(
                "UPDATE par.team SET last_confirmed_at = last_confirmed_at - make_interval(mins => :m) WHERE id = :id"
            ),
            {"m": minutes, "id": team_id},
        )


async def test_the_catalogue_names_the_check(par: httpx.AsyncClient) -> None:
    reg = registry.get()
    assert {"par", "par.timing", "field_par", "field_par.check"} <= set(reg.features)
    mine = [(m, p) for m, p in reg.routes if p.startswith(("/par/", "/@crew/missions/{assignment_id}/par"))]
    assert len(mine) == 20
    for method, path in mine:
        chain = reg.match(method, path)
        assert chain and [f for f in chain if f.kind == "page"][-1].key in ("par", "field_par"), (method, path)
        # A write is granted or hidden by its own button.
        assert method == "GET" or chain[0].kind == "button", (method, path)
    for key in ("par", "field_par"):
        for child in [f for f in reg.features.values() if f.parent == key]:
            for route in child.routes:
                assert tuple(route.split(" ", 1)) in reg.routes, route


async def test_a_team_in_the_danger_zone(par: httpx.AsyncClient, staff: Staff) -> None:
    room = staff(["operator"], SFAX, name="رئيس القاعة")
    incident_id, leader, path = await _mission(par, staff)

    r = await leader.get(path)
    assert r.status_code == 200, r.text
    assert r.json()["team"] is None and "جهاز لاسلكي" in r.json()["resources"]
    assert (await leader.post(f"{path}/confirm")).json()["detail"] == "not_inside"

    # Entering: the crew of the shift, the leader first; the timer of the hot zone (10 min by default).
    r = await leader.post(f"{path}/enter", {"zone": "hot"})
    assert r.status_code == 200, r.text
    team = r.json()["team"]
    assert team["status"] == "ok" and team["interval_s"] == 600
    assert [m["key"] for m in team["members"]] == ["m0", "m1", "m2", "m3"]
    assert team["members"][0]["name"] == "سامي الطرابلسي" and team["members"][1]["name"] == "علي"
    assert (await leader.post(f"{path}/enter", {"zone": "hot"})).json()["detail"] == "already_inside"

    # A member out for air is not asked for until back; the leader stays.
    r = await leader.post(f"{path}/away", {"member": "m2", "why": "air"})
    assert r.status_code == 200 and r.json()["team"]["present"] == 3 and r.json()["team"]["away"] == 1
    assert (await leader.post(f"{path}/away", {"member": "m0", "why": "rest"})).json()["detail"] == "leader_stays"
    assert (await leader.post(f"{path}/back", {"member": "m2"})).json()["team"]["away"] == 0

    # Past the interval and the grace: the room sees the alarm, logged once.
    await _age(team["id"], 12)
    board = (await par.get(f"{URL}/incidents/{incident_id}", headers=room)).json()
    assert board["teams"][0]["status"] == "alarm" and board["kpis"]["not_confirmed"] == 1
    (await par.get(f"{URL}/incidents/{incident_id}", headers=room)).json()
    board = (await par.get(f"{URL}/incidents/{incident_id}", headers=room)).json()
    assert [e["kind"] for e in board["events"]].count("alarm") == 1
    r = await leader.post(f"{path}/confirm")
    assert r.json()["team"]["status"] == "ok"

    # The room sets the next check; a past time is refused.
    soon = datetime.now(UTC) + timedelta(minutes=3)
    r = await par.post(f"{URL}/incidents/{incident_id}/next", json={"at": soon.isoformat()}, headers=room)
    assert r.status_code == 200, r.text
    assert 100 < r.json()["teams"][0]["remaining_s"] <= 180
    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    r = await par.post(f"{URL}/incidents/{incident_id}/next", json={"at": past}, headers=room)
    assert (r.status_code, r.json()["detail"]) == (422, "time_passed")

    # A pause needs a reason; the phone cannot confirm while paused; the timer goes on after.
    body = {"reason": "other"}
    r = await par.post(f"{URL}/incidents/{incident_id}/pause", json=body, headers=room)
    assert r.json()["detail"] == "reason_detail_required"
    r = await par.post(f"{URL}/incidents/{incident_id}/pause", json={"reason": "defensive"}, headers=room)
    assert r.status_code == 200 and r.json()["teams"][0]["status"] == "paused"
    assert "الدفاع" in r.json()["teams"][0]["pause_reason"]
    assert (await leader.post(f"{path}/confirm")).json()["detail"] == "paused"
    r = await par.post(f"{URL}/incidents/{incident_id}/resume", json={}, headers=room)
    assert r.json()["teams"][0]["status"] in ("ok", "soon")

    # A missing radio, with who had it; the word from the scene, dictated and corrected.
    r = await leader.post(f"{path}/missing", {"resource": "جهاز لاسلكي", "member": "m1", "place": "الطابق الثاني"})
    assert r.status_code == 200 and r.json()["team"]["status"] == "missing"
    missing = r.json()["missing"][0]
    assert missing["carrier"] == "علي"
    r = await leader.post(
        f"{path}/sitrep",
        {
            "situation": "progress",
            "reinforcement": True,
            "text": "الحريق محصور في الطابق الثاني",
            "voice_seconds": 12,
            "transcript": "الحريق محسور في الطابق الثاني",
        },
    )
    assert r.status_code == 200 and r.json()["last_sitrep"]["edited"] is True

    # The check cannot end with a team inside or a resource missing.
    r = await par.post(f"{URL}/incidents/{incident_id}/close", headers=room)
    assert r.json()["detail"] == "teams_inside"
    r = await leader.post(f"{path}/exit", {"members": ["m0", "m1", "m2"]})
    assert r.json()["detail"] == "headcount_incomplete"
    r = await leader.post(f"{path}/exit", {"members": ["m0", "m1", "m2", "m3"]})
    assert r.json()["team"]["status"] == "out" and r.json()["team"]["out_count"] == 4
    assert (await par.post(f"{URL}/incidents/{incident_id}/close", headers=room)).json()["detail"] == "missing_open"
    url = f"{URL}/incidents/{incident_id}/missing/{missing['id']}/recovered"
    assert (await par.post(url, headers=room)).status_code == 200
    r = await par.post(f"{URL}/incidents/{incident_id}/close", headers=room)
    assert r.status_code == 200, r.text
    closure = r.json()["closure"]
    assert closure["automatic"] is False and closure["summary"]["agents"] == 4 and closure["summary"]["sitreps"] == 1

    # Archived, off the live follow-up, kept with the intervention.
    live = (await par.get(f"{URL}/incidents", headers=room)).json()
    assert incident_id not in [x["incident_id"] for x in live]
    archived = (await par.get(f"{URL}/incidents", params={"closed": True}, headers=room)).json()
    assert incident_id in [x["incident_id"] for x in archived]
    assert (await leader.post(f"{path}/enter", {"zone": "warm"})).json()["detail"] == "par_closed"


async def test_settings_scope_and_the_closed_incident(par: httpx.AsyncClient, staff: Staff) -> None:
    commander = staff(["field_commander"], SFAX, name="قائد العمليات")
    body = {"hot_s": 300, "warm_s": 1200, "grace_s": 90, "auto_events": ["collapse"]}
    r = await par.put(f"{URL}/settings", json=body, headers=commander)
    assert r.status_code == 200, r.text
    assert r.json()["hot_s"] == 300 and r.json()["updated_by_name"] == "قائد العمليات"
    # Another gouvernorat's settings are not this room's; a value outside the choices is refused.
    assert (
        await par.put(f"{URL}/settings", json=body, params={"gouvernorat": 11}, headers=commander)
    ).status_code == 404
    assert (await par.put(f"{URL}/settings", json={**body, "hot_s": 400}, headers=commander)).status_code == 422
    assert (await par.put(f"{URL}/settings", json=body, headers=staff(["team_leader"], SFAX))).status_code == 403

    incident_id, leader, path = await _mission(par, staff)
    r = await leader.post(f"{path}/enter", {"zone": "hot"})
    assert r.json()["team"]["interval_s"] == 300
    # Another gouvernorat's room does not see the board.
    tunis = staff(["operator"], 11)
    assert (await par.get(f"{URL}/incidents/{incident_id}", headers=tunis)).status_code in (403, 404)
    # The intervention is closed: the check ends by itself, archived.
    async with get_system_sessionmaker()() as s, s.begin():
        await s.execute(text("UPDATE ops.incident SET status = 'closed' WHERE id = :id"), {"id": incident_id})
    board = (await par.get(f"{URL}/incidents/{incident_id}", headers=commander)).json()
    assert board["closure"]["automatic"] is True and board["teams"][0]["status"] == "out"
    await par.put(f"{URL}/settings", json={**body, "hot_s": 600, "warm_s": 900, "grace_s": 60}, headers=commander)
