# covers: FR-A-050, UC-06
"""News from the field (Yamen 2026-11-09): an agent on shift streams from the staff app without a mission."""

import httpx
from sqlalchemy import text

from app.core.db import get_system_sessionmaker
from tests.conftest import FakeMediamtx
from tests.test_crew import Staff
from tests.test_crew_field import _mission as _leader_mission
from tests.test_field_agents import Agent
from tests.test_field_agents import _mission as _crew_mission
from tests.test_streams import auth, go_live


async def test_agent_streams_news_from_the_field(
    client: httpx.AsyncClient, staff: Staff, fake_mediamtx: FakeMediamtx
) -> None:
    leader, crew, _assignment, place = await _crew_mission(client, staff)
    # A member of the crew (not the leader) streams what they see, with no mission.
    r = await crew.post("/streams")
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["whip_url"].endswith(f"/{created['path']}/whip")
    assert (await crew.post("/streams")).json()["detail"] == "stream_already_active"
    # WebRTC only, with its token, like the team's mission stream.
    token = created["publish_token"]
    assert await auth(client, action="publish", path=created["path"], protocol="rtmp", token=token) == 401
    assert await auth(client, action="publish", path=created["path"], protocol="webrtc", token=token) == 200
    await go_live(client, created["path"])
    stream_id = created["stream_id"]
    assert (await crew.post(f"/streams/{stream_id}/location", place)).status_code == 204

    # The room of the gouvernorat sees it on the wall as news, with the vehicle's name; another gouvernorat does not.
    wall = await client.get("/api/v1/staff/streams", params={"status": "live"}, headers=staff(["operator"], 61))
    assert wall.status_code == 200, wall.text
    mine = next(s for s in wall.json()["items"] if s["id"] == stream_id)
    assert (mine["source"], mine["news"], mine["incident_id"], mine["report_id"]) == ("crew", True, None, None)
    assert mine["label"] and mine["last_location"]
    other = await client.get("/api/v1/staff/streams", params={"status": "live"}, headers=staff(["operator"], 11))
    assert stream_id not in [s["id"] for s in other.json()["items"]]

    # Only the agent who opened it reads or stops it; the leader of the same vehicle does not.
    assert (await leader.get(f"/streams/{stream_id}")).status_code == 404
    assert (await leader.post(f"/streams/{stream_id}/stop")).status_code == 404
    assert (await crew.get(f"/streams/{stream_id}")).json()["status"] == "live"
    stopped = await crew.post(f"/streams/{stream_id}/stop")
    assert stopped.json()["status"] == "ended"
    assert created["path"] in fake_mediamtx.kicked
    # Ended, a new piece of news may start.
    assert (await crew.post("/streams")).status_code == 201

    async with get_system_sessionmaker()() as s:
        n = await s.scalar(
            text("SELECT count(*) FROM audit.log WHERE action = 'crew.news_stream' AND target = :t"),
            {"t": f"stream:{stream_id}"},
        )
        assert n == 1


async def test_news_needs_a_shift_and_a_field_role(client: httpx.AsyncClient, staff: Staff) -> None:
    # An activated agent who is on no shift cannot stream.
    alone = await Agent(client, staff, "agent").ready()
    assert (await alone.post("/streams")).json()["detail"] == "no_open_shift"
    # The room does not open news streams from the staff routes.
    r = await client.post("/api/v1/crew/streams", json={}, headers=staff(["operator"], 61))
    assert r.status_code == 403
    # A leader streams news too, and the agents of their crew cannot reach the leader's mission stream.
    leader, path, _incident, _place = await _leader_mission(client, staff)
    r = await leader.post("/streams")
    assert r.status_code == 201, r.text
    mission_stream = (await leader.post(f"{path}/stream")).json()["stream_id"]
    assert (await alone.get(f"/streams/{mission_stream}")).status_code == 404
