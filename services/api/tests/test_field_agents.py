# covers: F-STF-01, F-STF-02
"""Field agents and the mission flow after Yamen's review (phase F, docs/phase-f/design-f.md): the room chief adds
agents and hands them a one-time code, the phone activates itself and renews its tokens, a lost phone is disabled; the
leader's round button, the skipped step, the end without intervention, the toll, the spoken intervention report, a
mission opened from the field and the point the room picks on the map."""

import secrets
import uuid
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.test_crew import Staff, new_incident, write
from tests.test_operations import make_resource, random_place

AGENTS = "/api/v1/staff/field-agents"


def matricule() -> str:
    return f"M{secrets.randbelow(10**8):08d}"


class Agent:
    """An agent the room chief of Sfax (61) added, and the phone they activated."""

    def __init__(self, client: httpx.AsyncClient, staff: Staff, function: str = "leader") -> None:
        self.client, self.staff, self.function = client, staff, function
        self.matricule = matricule()
        self.row: dict[str, Any] = {}
        self.tokens: dict[str, Any] = {}

    @property
    def chief(self) -> dict[str, str]:
        return self.staff(["ops_manager"], 61)

    async def add(self) -> dict[str, Any]:
        r = await self.client.post(
            AGENTS,
            json={
                "matricule": self.matricule,
                "name": "منير الحاج",
                "function": self.function,
                "phone": "+216 98 000 000",
            },
            headers=self.chief,
        )
        assert r.status_code == 201, r.text
        self.row = r.json()
        return self.row

    async def activate(self, code: str | None = None) -> httpx.Response:
        return await self.client.post(
            "/api/v1/field/activate",
            json={
                "matricule": self.matricule,
                "code": code or self.row["code"],
                "device": {
                    "platform": "android",
                    "model": "Galaxy A15",
                    "device_ref": "ref-1",
                    "sim_number": "+21698111222",
                },
            },
        )

    async def ready(self) -> "Agent":
        await self.add()
        r = await self.activate()
        assert r.status_code == 200, r.text
        self.tokens = r.json()
        return self

    @property
    def h(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens['access_token']}", "X-Staff-Device": self.tokens["device_id"]}

    async def post(self, path: str, body: dict[str, Any] | None = None) -> httpx.Response:
        return await self.client.post(f"/api/v1/crew{path}", json=body or {}, headers=self.h)

    async def get(self, path: str) -> httpx.Response:
        return await self.client.get(f"/api/v1/crew{path}", headers=self.h)


async def test_room_chief_adds_agents_and_codes(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    agent = Agent(client, staff, "agent")
    # Only the room chief or the regional account administrator, in their own gouvernorat.
    body = {"matricule": agent.matricule, "name": "منير الحاج", "function": "agent"}
    assert (await client.post(AGENTS, json=body, headers=staff(["operator"]))).status_code == 403
    r = await client.post(AGENTS, json={**body, "gouvernorat_code": 11}, headers=staff(["ops_manager"], 61))
    assert r.json()["detail"] == "out_of_scope"
    row = await agent.add()
    assert row["status"] == "pending" and len(row["code"]) == 9 and row["code"][4] == "-"
    assert row["phone"] == "+216 98 000 000" and row["device"] is None
    # The professional number is unique in its gouvernorat.
    assert (await client.post(AGENTS, json=body, headers=agent.chief)).json()["detail"] == "matricule_taken"
    # The code is shown once; the platform keeps its fingerprint only, and the phone number encrypted.
    listed = next(a for a in (await client.get(AGENTS, headers=agent.chief)).json() if a["id"] == row["id"])
    assert listed["code"] is None and listed["code_expires_at"]
    stored = (
        await session.execute(
            text("SELECT code_hash, phone_enc FROM ops.field_agent WHERE id = :id"), {"id": row["id"]}
        )
    ).one()
    assert row["code"].replace("-", "") not in stored.code_hash and b"98 000 000" not in bytes(stored.phone_enc)
    assert row["id"] not in [a["id"] for a in (await client.get(AGENTS, headers=staff(["ops_manager"], 11))).json()]

    # Wrong tries lock the code; a new code starts again.
    for _ in range(5):
        r = await agent.activate("ABCD-EFGH")
        assert r.status_code == 401 and r.json()["detail"] == "activation_refused"
    other = Agent(client, staff)
    other.matricule = agent.matricule[::-1]
    assert (await other.activate(row["code"])).json()["detail"] == "activation_refused"
    renewed = (await client.post(f"{AGENTS}/{row['id']}/code", headers=agent.chief)).json()
    assert renewed["code"] != row["code"]
    assert (await agent.activate(row["code"])).status_code == 401
    r = await agent.activate(renewed["code"].lower().replace("-", ""))
    assert r.status_code == 200, r.text
    tokens = r.json()
    assert tokens["function"] == "agent" and tokens["charter_accepted"] is False and tokens["gouvernorat_code"] == 61
    # A code works once.
    assert (await agent.activate(renewed["code"])).status_code == 401

    listed = next(a for a in (await client.get(AGENTS, headers=agent.chief)).json() if a["id"] == row["id"])
    assert listed["status"] == "active" and listed["device"]["model"] == "Galaxy A15"
    assert listed["device"]["sim_number"] == "+21698111222"
    r = await client.patch(f"{AGENTS}/{row['id']}", json={"imei": "356789012345678"}, headers=agent.chief)
    assert r.json()["device"]["imei"] == "356789012345678"


async def test_tokens_charter_and_lost_phone(client: httpx.AsyncClient, staff: Staff) -> None:
    agent = await Agent(client, staff, "agent").ready()
    me = (await agent.get("/me")).json()
    assert me["roles"] == ["field_agent"] and me["activated_agent"] is True and me["charter_accepted"] is False
    assert me["field"] == {"hold_ms": 1500, "undo_seconds": 10}
    r = await agent.post("/charter", {"version": "2026.1", "sms": True, "location": True})
    assert r.status_code == 204
    assert (await agent.get("/me")).json()["charter_accepted"] is True
    # An agent reads the missions of their shift but does not write them.
    assert (await agent.get("/missions")).json()["items"] == []
    assert (await agent.post("/resources")).status_code in (403, 405)
    assert (await agent.get("/resources")).status_code == 403

    # The refresh token turns once.
    first = agent.tokens["refresh_token"]
    r = await client.post("/api/v1/field/token", json={"refresh_token": first})
    assert r.status_code == 200, r.text
    agent.tokens = r.json()
    assert agent.tokens["refresh_token"] != first
    assert (await client.post("/api/v1/field/token", json={"refresh_token": first})).json()[
        "detail"
    ] == "refresh_refused"

    # Lost phone: disabled from the room, the session ends now and the app erases itself.
    r = await client.post(f"{AGENTS}/{agent.row['id']}/disable", json={"reason": "هاتف ضائع"}, headers=agent.chief)
    assert r.json()["status"] == "disabled" and r.json()["device"]["revoked_at"]
    assert (await agent.get("/me")).status_code in (401, 410)
    r = await client.post("/api/v1/field/token", json={"refresh_token": agent.tokens["refresh_token"]})
    assert r.status_code == 410 and r.json()["detail"] == "device_revoked"
    # A new code brings the agent back on a new phone; deletion hides the account but keeps its phones.
    code = (await client.post(f"{AGENTS}/{agent.row['id']}/code", headers=agent.chief)).json()["code"]
    assert (await agent.activate(code)).status_code == 200
    r = await client.post(f"{AGENTS}/{agent.row['id']}/delete", json={"reason": "انتهاء الخدمة"}, headers=agent.chief)
    assert r.json()["status"] == "deleted"
    assert agent.row["id"] not in [a["id"] for a in (await client.get(AGENTS, headers=agent.chief)).json()]


async def _mission(client: httpx.AsyncClient, staff: Staff) -> tuple[Agent, Agent, dict[str, Any], dict[str, float]]:
    leader = await Agent(client, staff).ready()
    crew = await Agent(client, staff, "driver").ready()
    picked = [a["id"] for a in (await leader.get("/agents")).json()]
    assert crew.row["id"] in picked and leader.row["id"] not in picked
    resource = await make_resource(client, staff)
    r = await leader.post("/shifts", write(resource_id=resource["id"], crew_size=2, crew_agent_ids=[crew.row["id"]]))
    assert r.status_code == 201, r.text
    assert [c["name"] for c in r.json()["crew"]] == ["منير الحاج"]
    place = random_place()
    incident_id, _ = await new_incident(client, staff, place)
    r = await client.post(
        f"/api/v1/staff/incidents/{incident_id}/assignments",
        json={"resource_id": resource["id"], "order": "حريق منزل"},
        headers=staff(["operator"]),
    )
    assert r.status_code == 201, r.text
    return leader, crew, r.json(), place


async def test_mission_flow(client: httpx.AsyncClient, staff: Staff) -> None:
    leader, crew, assignment, place = await _mission(client, staff)
    path = f"/missions/{assignment['id']}"
    # The room picks the point on the map; the team reads it.
    r = await client.put(
        f"/api/v1/staff/assignments/{assignment['id']}/target",
        json={"lat": place["lat"] + 0.001, "lon": place["lon"], "note": "المدخل الخلفي"},
        headers=staff(["operator"]),
    )
    assert r.status_code == 200, r.text
    assert abs(r.json()["target"]["lat"] - place["lat"] - 0.001) < 1e-6 and r.json()["target_note"] == "المدخل الخلفي"
    assert (
        await client.put(
            f"/api/v1/staff/assignments/{assignment['id']}/target",
            json={"lat": 36.8, "lon": 10.1},
            headers=staff(["operator"], 11),
        )
    ).status_code == 404
    # The crew sees the mission, read-only.
    seen = (await crew.get("/missions")).json()["items"]
    assert [m["id"] for m in seen] == [assignment["id"]] and seen[0]["target_note"] == "المدخل الخلفي"
    assert (await crew.post(f"{path}/status", write(status="en_route"))).status_code == 403

    nature = write(nature="fire")
    assert (await leader.post(f"{path}/nature", nature)).json()["crew_nature"] == "fire"
    assert (await leader.post(f"{path}/nature", nature)).status_code == 200
    assert (await leader.post(f"{path}/skip", write(step="at_hospital", reason="no_transport"))).status_code == 409
    await leader.post(f"{path}/status", write(status="en_route"))
    await leader.post(f"{path}/status", write(status="on_scene", lat=place["lat"], lon=place["lon"]))
    await leader.post(f"{path}/milestone", write(step="left_scene"))
    mission = (await leader.post(f"{path}/skip", write(step="at_hospital", reason="no_transport"))).json()
    assert mission["skipped"] == {"at_hospital": "no_transport"}
    assert (await leader.post(f"{path}/milestone", write(step="back_at_unit"))).json()["status"] == "released"

    toll = write(damage="moderate", description="احتراق غرفة وأثاث")
    mission = (await leader.post(f"{path}/toll", toll)).json()
    assert mission["toll"]["answers"]["damage"] == "moderate" and mission["toll"]["note"] == "احتراق غرفة وأثاث"
    report = write(text="تم إخماد الحريق وتبريد المكان")
    assert (await leader.post(f"{path}/report", report)).json()["intervention_report"]["note"].startswith("تم إخماد")
    detail = await client.get(f"/api/v1/staff/incidents/{assignment['incident_id']}", headers=staff(["operator"]))
    row = next(a for a in detail.json()["assignments"] if a["id"] == assignment["id"])
    assert row["crew_nature"] == "fire" and row["skipped"] == {"at_hospital": "no_transport"} and row["target"]


async def test_no_intervention_and_field_mission(client: httpx.AsyncClient, staff: Staff) -> None:
    leader, _crew, assignment, place = await _mission(client, staff)
    path = f"/missions/{assignment['id']}"
    await leader.post(f"{path}/status", write(status="en_route"))
    r = await leader.post(f"{path}/no-intervention", write(reason="false_alarm"))
    assert r.json()["status"] == "cancelled" and r.json()["no_intervention_reason"] == "false_alarm"
    assert r.json()["en_route_at"]
    assert (await leader.post(f"{path}/no-intervention", write(reason="false_alarm"))).json()[
        "detail"
    ] == "mission_over"

    # A crash on the way back: the team opens the mission, the room sees a new incident.
    body = write(nature="traffic_accident", lat=place["lat"] + 0.01, lon=place["lon"], note="اصطدام سيارتين")
    r = await leader.post("/missions/open", body)
    assert r.status_code == 201, r.text
    opened = r.json()
    assert opened["field_initiated"] is True and opened["crew_nature"] == "traffic_accident" and opened["target"]
    assert (
        opened["incident"]["category"] == "traffic_accident" and opened["incident"]["id"] != assignment["incident_id"]
    )
    assert (await leader.post("/missions/open", body)).json()["id"] == opened["id"]  # sent twice, opened once
    r = await client.get(f"/api/v1/staff/incidents/{opened['incident']['id']}", headers=staff(["operator"]))
    assert r.status_code == 200


async def test_spoken_report(client: httpx.AsyncClient, staff: Staff, fake_ai: Any, fake_store: Any) -> None:
    leader, _crew, assignment, _ = await _mission(client, staff)
    url = f"/api/v1/crew/missions/{assignment['id']}/voice"
    fake_ai.transcript = {"text": "تم اخماد الحريق", "language": "ar"}
    r = await client.post(url, content=b"audio", headers={**leader.h, "Content-Type": "audio/webm"})
    assert r.status_code == 200, r.text
    voice = r.json()
    assert voice["text"] == "تم اخماد الحريق" and "محضر" in (fake_ai.transcribe_options["prompt"] or "")
    assert not fake_store.objects  # the audio is never kept
    corrected = write(text="تم إخماد الحريق نهائيا", voice_id=voice["voice_id"])
    r = await leader.post(f"/missions/{assignment['id']}/report", corrected)
    assert r.json()["intervention_report"]["answers"]["voice"]["voice_id"] == voice["voice_id"]
    # A transcript is corrected once.
    again = write(text="نص آخر", voice_id=voice["voice_id"])
    assert (await leader.post(f"/missions/{assignment['id']}/report", again)).json()["detail"] == "voice_already_sent"
    assert uuid.UUID(voice["voice_id"])
