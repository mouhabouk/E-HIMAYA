# covers: UC-01, UC-05, FR-A-020, FR-A-041, FR-A-070, F-STF-01, F-STF-03, F-STF-04, F-STF-05
"""End-to-end life of reports, from the reporter's phone to the closing and the decisions (Yamen, 2026-11-01).

Four scenarios, each read back as the room, the committees and the reporters see them; at every stage the place is
checked against the boundaries (gouvernorat and délégation found from the polygons) and the summary against what was
done:

* S1: one citizen's report, through the incident, the recommendations, the team's steps and the closing;
* S2: three reports on one incident from a citizen, an approved volunteer and an approved doctor, with a photo, a
  video and a voice message, the reporter's role shown to the room, and the rewards of each;
* S3: an institution's report (a factory) with its card, the team's steps from the staff app, and voice messages
  read at 23:59 and 00:00 that put the mission times on the right day;
* S4: five reports on one forest fire that grows into a disaster: the levels, the axis, the governor's, national
  committee's and minister's decisions, the situation report, the disaster summary and map, the rewards paused then
  released, and the closing.
"""

import base64
import hashlib
import os
import secrets
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_system_sessionmaker
from app.modules.ops.record_suggest import TUNIS
from app.modules.reports.uploads import verify_one
from tests.conftest import HOOK_AUTH, FakeStore, TokenFactory, accept_charter, bearer, report_body
from tests.test_crew import Leader, write
from tests.test_crew_field import JPEG, M4A, _upload
from tests.test_doctors import approve as approve_doctor
from tests.test_doctors import registered as registered_doctor
from tests.test_operations import make_resource, with_profile
from tests.test_orgs import active_org, add_member
from tests.test_rewards import citizen_id, drain, mine, new_citizen

Staff = Callable[..., dict[str, str]]
User = Callable[..., dict[str, str]]

SFAX, JENDOUBA, BEJA = 61, 32, 31
STAFF = "/api/v1/staff"
CRISIS = f"{STAFF}/crisis"
TUS = "/internal/tusd/hooks"
MP4 = b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00" + b"\x00" * 512
OGG = b"OggS\x00\x02" + b"\x00" * 512
# A square around Aïn Draham (lon, lat).
AIN_DRAHAM_AREA = {
    "type": "Polygon",
    "coordinates": [[[8.60, 36.70], [8.80, 36.70], [8.80, 36.85], [8.60, 36.85], [8.60, 36.70]]],
}


@pytest.fixture(autouse=True)
async def _normal_levels() -> AsyncIterator[None]:
    yield
    async with get_system_sessionmaker()() as s, s.begin():
        await s.execute(text("UPDATE ops.level_state SET level = 'normal', reason = NULL"))


@pytest.fixture(autouse=True)
def _signing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    key = base64.b64encode(hashlib.sha256(b"e-himaya scenario key").digest()).decode()
    monkeypatch.setattr(get_settings(), "evidence_signing_key", SecretStr(key))


@pytest.fixture
def user(make_token: TokenFactory) -> User:
    def _user(email: str | None = None, **claims: Any) -> dict[str, str]:
        email = email or f"u{uuid.uuid4().hex[:10]}@example.tn"
        token = make_token(roles=["citizen"], email=email, email_verified=True, name="Ridha Gharbi", **claims)
        return bearer(token)

    return _user


# ---------------------------------------------------------------- helpers


def jitter(lat: float, lon: float, spread: float = 0.002) -> dict[str, float]:
    """A point near a known place, of its own (the shared test database keeps other tests' incidents open)."""
    d = lambda: (secrets.randbelow(2001) - 1000) / 1000 * spread  # noqa: E731
    return {"lat": round(lat + d(), 6), "lon": round(lon + d(), 6), "accuracy_m": 8.0}


async def boundaries_of(place: dict[str, float]) -> tuple[int, int]:
    """The gouvernorat and délégation whose polygon holds the point: the truth the API's answer is checked against."""
    async with get_system_sessionmaker()() as s:
        row = (
            await s.execute(
                text(
                    "SELECT gouvernorat_code, id FROM geo.delegation "
                    "WHERE ST_Contains(boundary, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))"
                ),
                place,
            )
        ).one()
    return int(row[0]), int(row[1])


async def check_place(
    client: httpx.AsyncClient, staff: Staff, report_id: str, place: dict[str, float], want: tuple[int, int]
) -> dict[str, Any]:
    """The room's view of a report puts it where the reporter was: same point, gouvernorat and délégation."""
    assert await boundaries_of(place) == want
    detail = (await client.get(f"{STAFF}/reports/{report_id}", headers=staff(["operator"], want[0]))).json()
    assert (detail["gouvernorat_code"], detail["delegation_id"]) == want, detail
    assert str(detail["address"]["delegation"]["id"]) == str(want[1]) and detail["address"]["delegation"]["name_ar"]
    point = detail["location"]
    assert point["lat"] == pytest.approx(place["lat"], abs=1e-6) and point["lon"] == pytest.approx(
        place["lon"], abs=1e-6
    )
    return detail  # type: ignore[no-any-return]


async def send_report(
    client: httpx.AsyncClient, headers: dict[str, str], place: dict[str, float], **overrides: Any
) -> dict[str, Any]:
    r = await client.post("/api/v1/reports", json=report_body(place, **overrides), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


async def open_incident(client: httpx.AsyncClient, staff: Staff, report_id: str, code: int) -> str:
    r = await client.post(
        f"{STAFF}/reports/{report_id}/incident",
        json={"action": "new", "override_reason": "حادث مستقل في السيناريو"},
        headers=staff(["operator"], code),
    )
    assert r.status_code == 200, r.text
    return r.json()["incident_id"]  # type: ignore[no-any-return]


async def link(client: httpx.AsyncClient, staff: Staff, report_id: str, incident_id: str, code: int) -> None:
    r = await client.post(
        f"{STAFF}/reports/{report_id}/incident",
        json={"action": "link", "incident_id": incident_id},
        headers=staff(["operator"], code),
    )
    assert r.status_code == 200 and r.json()["incident_id"] == incident_id, r.text


async def incident_of(client: httpx.AsyncClient, staff: Staff, incident_id: str, code: int) -> dict[str, Any]:
    r = await client.get(f"{STAFF}/incidents/{incident_id}", headers=staff(["operator"], code))
    assert r.status_code == 200, r.text
    return r.json()  # type: ignore[no-any-return]


async def close(
    client: httpx.AsyncClient, staff: Staff, incident_id: str, code: int, summary: str, **casualties: int
) -> dict[str, Any]:
    body = {"outcome": "resolved", "summary": summary, "casualties": casualties, "lessons": "تقييم بعد التدخل"}
    r = await client.post(f"{STAFF}/incidents/{incident_id}/close", json=body, headers=staff(["field_commander"], code))
    assert r.status_code == 200, r.text
    return r.json()  # type: ignore[no-any-return]


async def my_status(client: httpx.AsyncClient, headers: dict[str, str], report_id: str) -> str:
    items = (await client.get("/api/v1/reports/mine", headers=headers)).json()["items"]
    return next(i["status"] for i in items if i["id"] == report_id)  # type: ignore[no-any-return]


async def attach(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    store: FakeStore,
    report_id: str,
    data: bytes,
    kind: str,
    filetype: str,
) -> None:
    """A photo, a video or a voice message sent from the reporter's phone (tus upload, then the verification)."""
    meta = {
        "report_id": report_id,
        "kind": kind,
        "filetype": filetype,
        "sha256": hashlib.sha256(data).hexdigest(),
        "filename": f"media.{filetype.split('/')[1]}",
    }
    upload = {"ID": "", "Size": len(data), "SizeIsDeferred": False, "Offset": 0, "MetaData": meta}

    def hook(kind_: str, up: dict[str, Any]) -> dict[str, Any]:
        request = {"Method": "POST", "URI": "/api/v1/uploads/", "Header": {k: [v] for k, v in headers.items()}}
        return {"Type": kind_, "Event": {"Upload": up, "HTTPRequest": request}}

    answer = (await client.post(TUS, headers=HOOK_AUTH, json=hook("pre-create", upload))).json()
    assert "RejectUpload" not in answer, answer
    upload_id = answer["ChangeFileInfo"]["ID"]
    key = f"uploads/{upload_id}"
    store.objects[key] = data
    done = {**upload, "ID": f"{upload_id}+multipart", "Offset": len(data)}
    done["Storage"] = {"Type": "s3store", "Bucket": "ehimaya-media", "Key": key}
    assert (await client.post(TUS, headers=HOOK_AUTH, json=hook("post-finish", done))).status_code == 200
    while await verify_one(get_system_sessionmaker(), store):
        pass


async def leader_on_shift(
    client: httpx.AsyncClient, staff: Staff, names: str, push: str = "fcm-token"
) -> tuple[Leader, dict[str, Any]]:
    leader = Leader(client, staff)
    await leader.register(push_token=f"{push}-{uuid.uuid4().hex[:6]}")
    resource = await make_resource(client, staff)
    r = await leader.post("/shifts", write(resource_id=resource["id"], crew_size=4, crew_names=names))
    assert r.status_code == 201, r.text
    return leader, resource


async def assign(
    client: httpx.AsyncClient, staff: Staff, incident_id: str, resource_id: str, order: str
) -> dict[str, Any]:
    r = await client.post(
        f"{STAFF}/incidents/{incident_id}/assignments",
        json={"resource_id": resource_id, "order": order, "contact_phone": "+216 74 000 111"},
        headers=staff(["operator"]),
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def kinds(detail: dict[str, Any]) -> list[str]:
    return [e["kind"] for e in detail["timeline"]]


# ---------------------------------------------------------------- S1: one citizen's report


async def test_s1_citizen_report_from_sending_to_closing(
    client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory
) -> None:
    citizen = await new_citizen(client, make_token)
    place = jitter(34.80, 10.765)  # Sakiet Ezzit
    rep = await send_report(client, citizen, place, text="حريق في منزل، دخان كثيف والعائلة في الخارج")
    assert rep["status"] == "received" and rep["tracking_code"]
    # Geolocation: the point, the gouvernorat and the délégation are those of the boundaries.
    detail = await check_place(client, staff, rep["id"], place, (SFAX, 6111))
    assert detail["reporter"]["kind"] == "citizen" and detail["reporter"]["roles"] == []
    # Who called stays hidden until the room takes the report in hand (§1.3).
    assert detail["reporter"]["masked"] is True and detail["reporter"]["first_name"] is None
    r = await client.post(f"{STAFF}/reports/{rep['id']}/claim", headers=staff(["operator"], SFAX))
    assert r.status_code == 200, r.text
    assert r.json()["reporter"]["first_name"] == "Amine" and r.json()["reporter"]["phone"].startswith("+216")
    assert detail["priority_score"] is not None

    # The room opens the incident and reads what the decision aid proposes (never applied by itself).
    incident_id = await open_incident(client, staff, rep["id"], SFAX)
    advice = await client.get(f"{STAFF}/incidents/{incident_id}/recommendations", headers=staff(["operator"]))
    assert advice.status_code == 200, advice.text
    assert advice.json()["notice"]["ar"]
    for item in advice.json()["items"]:
        assert item["rationale"]["ar"] and item["confidence"] in ("low", "medium", "high")

    # The decision: one fire engine; the team goes, arrives, reports and is released.
    leader, resource = await leader_on_shift(client, staff, "علي الشريف، منير بن عمر")
    assignment = await assign(client, staff, incident_id, resource["id"], "حريق منزل بساقية الزيت، التوجه فورا")
    path = f"/missions/{assignment['id']}"
    # Once a team is sent, the citizen reads "in progress".
    assert await my_status(client, citizen, rep["id"]) == "in_progress"
    assert (await leader.post(f"{path}/ack", write())).status_code == 200
    r = await leader.post(f"{path}/status", write(status="en_route", lat=place["lat"] + 0.03, lon=place["lon"]))
    assert r.json()["status"] == "en_route" and r.json()["distance_m"] > 2000
    r = await leader.post(f"{path}/status", write(status="on_scene", lat=place["lat"], lon=place["lon"]))
    assert r.json()["status"] == "on_scene" and r.json()["distance_m"] < 150
    assert await my_status(client, citizen, rep["id"]) == "intervened"
    first = write(category="fire", classification="residential_fire", severity=2, backup_needed=False)
    assert (await leader.post(f"{path}/first-report", first)).status_code == 200
    assert (await leader.post(f"{path}/casualties", write(rescued=2))).status_code == 200
    assert (await leader.post(f"{path}/status", write(status="released"))).json()["status"] == "released"

    # Closing, then the summary as the room reads it.
    summary = "أُخمد الحريق وأُنقذ شخصان دون إصابات"
    closed = await close(client, staff, incident_id, SFAX, summary, rescued=2)
    assert closed["status"] == "closed" and closed["closed_at"]
    assert closed["evaluation"]["summary"] == summary and closed["evaluation"]["casualties"]["rescued"] == 2
    assert closed["casualties"]["rescued"] == 2
    assert closed["gouvernorat_code"] == SFAX and closed["report_count"] == 1 and closed["reporter_count"] == 1
    centroid = closed["centroid"]
    assert centroid["lat"] == pytest.approx(place["lat"], abs=1e-4)
    assert centroid["lon"] == pytest.approx(place["lon"], abs=1e-4)
    steps = [e["payload"]["status"] for e in closed["timeline"] if e["kind"] == "assignment_status"]
    assert steps == ["en_route", "on_scene", "released"]
    assert {"crew_ack", "field_report", "casualties"} <= set(kinds(closed))
    assert kinds(closed)[-1] in ("closed", "incident_closed")
    # The citizen follows it to the end, and is credited once the room verified it.
    assert await my_status(client, citizen, rep["id"]) == "closed"
    await drain()
    rewards = await mine(client, citizen)
    assert rewards["balance"] > 0
    assert {h["reason"] for h in rewards["history"]} >= {"report_verified"}


# ---------------------------------------------------------------- S2: a citizen, a volunteer and a doctor


async def approved_volunteer(client: httpx.AsyncClient, staff: Staff, headers: dict[str, str]) -> str:
    """A citizen whose volunteer application the room approved; returns their user id."""
    body = {
        "skills": ["first_aid"],
        "availability": "continuous",
        "period_from": datetime.now(UTC).date().isoformat(),
        "period_to": (datetime.now(UTC) + timedelta(days=180)).date().isoformat(),
    }
    assert (await client.put("/api/v1/me/volunteer", json=body, headers=headers)).status_code == 200
    user_id = await citizen_id(client, headers)
    r = await client.post(
        f"{STAFF}/volunteers/{user_id}/review", json={"decision": "approve"}, headers=staff(["ops_manager"], SFAX)
    )
    assert r.status_code == 200, r.text
    return user_id


async def test_s2_three_reporters_with_media_on_one_incident(
    client: httpx.AsyncClient,
    staff: Staff,
    make_token: TokenFactory,
    user: User,
    fake_store: FakeStore,
) -> None:
    scene = (34.76, 10.73)  # Sfax Médina
    citizen = await new_citizen(client, make_token)
    volunteer = await new_citizen(client, make_token)
    await approved_volunteer(client, staff, volunteer)
    doctor = user()
    await with_profile(client, doctor)
    doctor_id, _ = await registered_doctor(client, staff, doctor)
    await approve_doctor(client, staff, doctor_id)
    await accept_charter(client, doctor)

    # Three people at the same accident, each from where they stand, each with a different piece of evidence.
    places = [jitter(*scene, spread=0.0004) for _ in range(3)]
    texts = [
        "حادث مرور بين سيارة وشاحنة، شخص عالق",
        "أنا متطوع في عين المكان، السائق عالق والمحرك يدخن",
        "طبيب في المكان: مصاب بنزيف، يلزم إسعاف عاجل",
    ]
    reports = []
    for headers, place, words in zip((citizen, volunteer, doctor), places, texts, strict=True):
        reports.append(await send_report(client, headers, place, category="traffic_accident", text=words))
    await attach(client, citizen, fake_store, reports[0]["id"], JPEG + os.urandom(256), "image", "image/jpeg")
    await attach(client, volunteer, fake_store, reports[1]["id"], MP4 + os.urandom(256), "video", "video/mp4")
    await attach(client, doctor, fake_store, reports[2]["id"], OGG + os.urandom(256), "audio", "audio/ogg")

    # Each report sits where it was sent from, and the room sees who sent it: a citizen, a volunteer, a doctor.
    roles = []
    for rep, place in zip(reports, places, strict=True):
        detail = await check_place(client, staff, rep["id"], place, (SFAX, 6114))
        assert detail["media_count"] == 1 and detail["media"][0]["status"] == "stored"
        assert detail["reporter"]["kind"] == "citizen"
        roles.append(detail["reporter"]["roles"])
        media_kind = detail["media"][0]["kind"]
        assert media_kind == {0: "image", 1: "video", 2: "audio"}[len(roles) - 1]
    assert roles == [[], ["volunteer"], ["doctor"]]

    # One incident: the first report opens it, the room links the two others.
    incident_id = await open_incident(client, staff, reports[0]["id"], SFAX)
    for rep in reports[1:]:
        await link(client, staff, rep["id"], incident_id, SFAX)
    incident = await incident_of(client, staff, incident_id, SFAX)
    assert incident["report_count"] == 3 and incident["reporter_count"] == 3
    assert {r["id"] for r in incident["reports"]} == {r["id"] for r in reports}
    assert sum(r["media_count"] for r in incident["reports"]) == 3
    assert kinds(incident).count("report_linked") >= 2
    # The incident's place is among the three reporters (within a few tens of metres).
    lat = sum(p["lat"] for p in places) / 3
    lon = sum(p["lon"] for p in places) / 3
    assert incident["centroid"]["lat"] == pytest.approx(lat, abs=0.001)
    assert incident["centroid"]["lon"] == pytest.approx(lon, abs=0.001)

    leader, resource = await leader_on_shift(client, staff, "هشام الفقي، وليد بن صالح")
    assignment = await assign(client, staff, incident_id, resource["id"], "حادث مرور بصفاقس المدينة، شخص عالق")
    path = f"/missions/{assignment['id']}"
    for step in ("en_route", "on_scene"):
        assert (await leader.post(f"{path}/status", write(status=step))).status_code == 200
    first = write(category="traffic_accident", classification="road_accident", severity=3)
    assert (await leader.post(f"{path}/first-report", first)).status_code == 200
    assert (await leader.post(f"{path}/casualties", write(rescued=1, injured_serious=1))).status_code == 200
    transport = write(triage="red", age_band="30_44", sex="male", hospital="مستشفى الحبيب بورقيبة")
    assert (await leader.post(f"{path}/transports", transport)).status_code == 200
    assert (await leader.post(f"{path}/status", write(status="released"))).status_code == 200

    summary = "أُخرج السائق العالق ونُقل مصاب إلى مستشفى الحبيب بورقيبة"
    closed = await close(client, staff, incident_id, SFAX, summary, rescued=1, injured=1)
    assert closed["evaluation"]["summary"] == summary
    assert closed["casualties"]["rescued"] == 1 and closed["casualties"]["injured_serious"] == 1
    assert closed["casualties"]["transported"] == 1
    assert closed["transports"][0]["hospital"] == "مستشفى الحبيب بورقيبة"
    for headers, rep in zip((citizen, volunteer, doctor), reports, strict=True):
        assert await my_status(client, headers, rep["id"]) == "closed"

    # Rewards: each of the three is credited once for this incident, from the room's verification only; the
    # doctor's report, which the room designates as having helped the rescue, earns the rescue award on top.
    r = await client.post(
        f"{STAFF}/rewards/interventions/{incident_id}/rescue",
        json={"report_ids": [reports[2]["id"]], "note": "تقدير الطبيب ساعد في إنقاذ المصاب"},
        headers=staff(["operator"], SFAX),
    )
    assert r.status_code == 200 and r.json()["awarded"][0]["status"] == "applied", r.text
    await drain()
    await drain()
    by_reason = []
    for headers in (citizen, volunteer, doctor):
        rewards = await mine(client, headers)
        reasons = sorted(h["reason"] for h in rewards["history"] if h["intervention_id"] == incident_id)
        assert rewards["balance"] == sum(h["delta"] for h in rewards["history"])
        by_reason.append(reasons)
    assert by_reason[0] == by_reason[1] == ["accurate_category", "report_verified"]
    assert by_reason[2] == ["accurate_category", "report_helped_rescue", "report_verified"]
    # Sending a photo, a video or a voice message earns nothing by itself (T25: never reward risk or volume).
    assert all("media" not in str(r) for r in by_reason)


# ---------------------------------------------------------------- S3: a factory's report and the team's steps


async def test_s3_factory_report_team_steps_and_midnight_voice(
    client: httpx.AsyncClient,
    staff: Staff,
    user: User,
    fake_store: FakeStore,
    fake_ai: Any,
    session: AsyncSession,
) -> None:
    place = jitter(34.78, 10.70, spread=0.003)  # Sfax South, the industrial road
    spot = {"lat": place["lat"], "lon": place["lon"]}
    admin = user()
    org_id = await active_org(
        client,
        staff,
        admin,
        name="Société Chimique du Sud",
        kind="industrial",
        location=spot,
        address="طريق قابس كلم 4، المنطقة الصناعية",
    )
    r = await client.post(
        f"/api/v1/orgs/{org_id}/hazmat",
        json={"name": "Chlore", "un_number": "1017", "hazard_class": "2.3", "quantity": 500, "unit": "kg"},
        headers=admin,
    )
    assert r.status_code in (200, 201), r.text
    evacuation = {"lat": spot["lat"] + 0.001, "lon": spot["lon"]}
    r = await client.post(
        f"/api/v1/orgs/{org_id}/features",
        json={"kind": "evacuation_point", "label": "نقطة التجمع الشمالية", "location": evacuation},
        headers=admin,
    )
    assert r.status_code in (200, 201), r.text
    r = await client.post(
        f"/api/v1/orgs/{org_id}/team",
        json={"full_name": "سامي العياري", "team_role": "representative", "phone": "22 333 444"},
        headers=admin,
    )
    assert r.status_code in (200, 201), r.text
    member = await add_member(client, admin, org_id, user, "member")
    await accept_charter(client, member)
    rep = await send_report(
        client,
        member,
        place,
        category="chemical_leak",
        text="تسرب غاز الكلور من خزان في المصنع، العمال في نقطة التجمع",
        organization_id=org_id,
    )
    assert rep["organization"]["id"] == org_id

    # The room: the institution's card (hazards, evacuation point, manager) and the place in Sfax South.
    detail = await check_place(client, staff, rep["id"], place, (SFAX, 6113))
    assert detail["reporter_kind"] == "organization" and detail["reporter"]["kind"] == "organization"
    card = detail["organization_card"]
    assert card["name"] == "Société Chimique du Sud" and card["kind"] == "industrial"
    assert card["hazmat"][0]["un_number"] == "1017" and card["hazmat"][0]["quantity"] == 500
    assert card["features"][0]["kind"] == "evacuation_point"
    assert (card["representative"]["full_name"], card["representative"]["phone"]) == ("سامي العياري", "+21622333444")
    assert card["location"]["lat"] == pytest.approx(spot["lat"], abs=1e-6)
    sensitive = next(c for c in detail["analysis"]["priority"]["components"] if c["key"] == "sensitive_sites")
    assert sensitive["detail"]["reason"] == "hazmat" and sensitive["detail"]["org_id"] == org_id

    incident_id = await open_incident(client, staff, rep["id"], SFAX)
    leader, resource = await leader_on_shift(client, staff, "كمال الزواري، أنيس المصمودي، فوزي التريكي")
    assignment = await assign(
        client, staff, incident_id, resource["id"], "تسرب كلور بمصنع، ارتداء أجهزة التنفس، الاقتراب مع الريح"
    )
    assert assignment["crew"]["leader_name"] == "سامي الطرابلسي" and assignment["crew"]["crew_size"] == 4
    assert assignment["resource"]["label"] == resource["label"]

    # The mission sheet (أمر مهمة): an official paper with the times, the reporter, the place on a map with the route
    # in a bold colour, the institution's card and its hazards, the team's names and vehicle, and the signatures.
    sheet_url = f"{STAFF}/assignments/{assignment['id']}/sheet"
    page = (await client.get(sheet_url, params={"format": "html"}, headers=staff(["operator"]))).text
    for words in (
        "أمر مهمة",
        "صفاقس الجنوبية",
        "Société Chimique du Sud",
        "Chlore",
        "1017",
        "نقطة التجمع الشمالية",
        "سامي العياري",
        "كمال الزواري",
        resource["label"],
        "تسرب كلور بمصنع",
        "رئيس الفريق",
        "الإمضاء",
        'stroke="#d32f2f" stroke-width="6"',
        "مواد خطرة في الموقع",
        rep["text"] if "text" in rep else "تسرب غاز الكلور",
    ):
        assert words in page, words
    pdf = await client.get(sheet_url, headers=staff(["operator"]))
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    if out := os.environ.get("SCENARIO_SHEET_OUT"):
        with open(out, "wb") as f:  # noqa: ASYNC230 - a test's optional sample for the review
            f.write(pdf.content)
    assert (await client.get(sheet_url, headers=staff(["operator"], 11))).status_code == 404

    # The staff app, step by step: the mission arrives, the leader acknowledges, goes, arrives, reports, sends a
    # photo, a voice message and a note, counts and is released.
    missions = (await leader.get("/missions")).json()["items"]
    mission = next(m for m in missions if m["id"] == assignment["id"])
    assert mission["status"] == "ordered" and mission["order"].startswith("تسرب كلور")
    assert mission["incident"]["delegation_ar"] == "صفاقس الجنوبية" and mission["incident"]["gouvernorat_code"] == SFAX
    assert mission["incident"]["location"]["lat"] == pytest.approx(place["lat"], abs=1e-4)
    assert mission["contact_phone"] == "+216 74 000 111"
    path = f"/missions/{assignment['id']}"
    on_phone = await leader.client.get(f"/api/v1/crew{path}/sheet", headers=leader.h)
    assert on_phone.status_code == 200 and on_phone.content.startswith(b"%PDF")
    assert (await leader.post(f"{path}/ack", write())).json()["acknowledged_at"]
    r = await leader.post(f"{path}/status", write(status="en_route", lat=34.74, lon=10.76))
    assert r.json()["status"] == "en_route" and r.json()["distance_m"] > 3000
    r = await leader.post(f"{path}/status", write(status="on_scene", lat=place["lat"], lon=place["lon"]))
    assert r.json()["status"] == "on_scene" and r.json()["distance_m"] < 150
    first = write(
        category="chemical_leak",
        classification="industrial_leak",
        severity=3,
        backup_needed=True,
        backup_note="وحدة مختصة في المواد الخطرة",
        crew_danger=True,
    )
    assert (await leader.post(f"{path}/first-report", first)).status_code == 200
    assert (await _upload(leader, path, "photo", JPEG, "image/jpeg")).status_code == 200
    assert (await _upload(leader, path, "voice", M4A, "audio/mp4", duration_s=9.0)).status_code == 200
    assert (await leader.post(f"{path}/notes", write(body="أُغلق الصمام، القياس 0 ppm عند السياج"))).status_code == 200
    assert (await leader.post(f"{path}/casualties", write(injured_light=2))).status_code == 200
    assert (await leader.post(f"{path}/status", write(status="released"))).status_code == 200

    # The voice messages at midnight: a second vehicle ordered at 23:58, whose leader says "تحركنا 23:59" one
    # minute later and "وصلنا 00:00" just after midnight. The times are read on the right days.
    backup, backup_vehicle = await leader_on_shift(client, staff, "رياض القلال، سليم بوزيد")
    second = await assign(client, staff, incident_id, backup_vehicle["id"], "دعم بوحدة المواد الخطرة")
    day = datetime.now(TUNIS).date() - timedelta(days=1)
    ordered = datetime(day.year, day.month, day.day, 23, 58, tzinfo=TUNIS)
    await session.execute(
        text("UPDATE ops.assignment SET created_at = :at WHERE id = :id"), {"at": ordered, "id": second["id"]}
    )
    await session.commit()
    suggest = f"{STAFF}/assignments/{second['id']}/record/suggestions"
    said = [
        ("تحركنا 23:59", ordered + timedelta(minutes=1, seconds=20)),
        ("وصلنا على عين المكان 00:00", ordered + timedelta(minutes=2, seconds=30)),
    ]
    got: dict[str, Any] = {}
    for words, at in said:
        fake_ai.transcript = {"text": words, "language": "ar"}
        r = await _upload(backup, f"/missions/{second['id']}", "voice", M4A, "audio/mp4", duration_s=4.0,
                          device_at=at.astimezone(UTC).isoformat())  # fmt: skip
        assert r.status_code == 200, r.text
        r = await client.post(suggest, json={}, headers=staff(["operator"]))
        assert r.status_code == 200, r.text
        got |= {s["step"]: s for s in r.json()}
    assert got["en_route_at"]["source"] == "team_voice"
    assert datetime.fromisoformat(got["en_route_at"]["at"]) == datetime(day.year, day.month, day.day, 23, 59,
                                                                        tzinfo=TUNIS)  # fmt: skip
    next_day = day + timedelta(days=1)
    assert datetime.fromisoformat(got["on_scene_at"]["at"]) == datetime(
        next_day.year, next_day.month, next_day.day, 0, 0, tzinfo=TUNIS
    )
    # The room applies them: the record keeps the order of the steps across midnight.
    times = {"en_route_at": got["en_route_at"]["at"], "on_scene_at": got["on_scene_at"]["at"]}
    r = await client.put(f"{STAFF}/assignments/{second['id']}/record", json={"times": times}, headers=staff())
    assert r.status_code == 200, r.text
    saved = r.json()
    assert datetime.fromisoformat(saved["on_scene_at"]) - datetime.fromisoformat(saved["en_route_at"]) == timedelta(
        minutes=1
    )

    # The record moved the mission on with the times; the team then releases its vehicle.
    assert saved["status"] == "on_scene", saved
    r = await backup.post(f"/missions/{second['id']}/status", write(status="released"))
    assert r.status_code == 200, r.text

    detail = await incident_of(client, staff, incident_id, SFAX)
    assert [a["kind"] for a in detail["attachments"] if a["assignment_id"] == assignment["id"]] == [
        "photo",
        "voice",
        "text",
    ]
    assert detail["field_reports"][0]["crew_danger"] and detail["casualties"]["injured_light"] == 2
    summary = "أُغلق صمام الخزان وأُخلي المصنع، مصابان بتهيج خفيف"
    closed = await close(client, staff, incident_id, SFAX, summary, injured=2, evacuated=40)
    assert closed["evaluation"]["summary"] == summary and closed["evaluation"]["casualties"]["evacuated"] == 40
    assert {a["status"] for a in closed["assignments"]} <= {"released", "cancelled", "on_scene"}
    assert closed["centroid"]["lat"] == pytest.approx(place["lat"], abs=1e-4)
    # The institution sees its report closed.
    mine_ = (await client.get(f"/api/v1/orgs/{org_id}/reports", headers=admin)).json()["items"]
    assert mine_[0]["tracking_code"] == rep["tracking_code"] and mine_[0]["status"] == "closed"


# ---------------------------------------------------------------- S4: five reports, a fire that becomes a disaster


async def test_s4_five_reports_grow_into_a_disaster_up_to_the_minister(
    client: httpx.AsyncClient, staff: Staff, make_token: TokenFactory, isolated_window: None
) -> None:
    scene = (36.775, 8.695)  # the forest above Aïn Draham
    room = staff(["operator"], JENDOUBA)
    commander = staff(["ops_manager"], None)
    governor = staff(["governor"], JENDOUBA)
    minister = staff(["minister"], None)
    national_committee = staff(["central_committee"], None)
    local_committee = staff(["local_committee"], JENDOUBA)
    citizens = [await new_citizen(client, make_token, gouvernorat=JENDOUBA) for _ in range(5)]
    places = [jitter(*scene, spread=0.003) for _ in range(5)]
    words = [
        "دخان في الغابة فوق عين دراهم",
        "النار تقترب من الطريق الجهوية 17",
        "ألسنة اللهب وصلت إلى المنازل الأولى، الرياح قوية",
        "عائلات تغادر حي الصنوبر، النار في كل مكان",
        "النار تحيط بالمدرسة، أطفال في الداخل",
    ]

    # 1st report: the room opens the incident. Every report sits in Aïn Draham (Jendouba).
    reports = [await send_report(client, citizens[0], places[0], category="fire", text=words[0])]
    await check_place(client, staff, reports[0]["id"], places[0], (JENDOUBA, 3201))
    incident_id = await open_incident(client, staff, reports[0]["id"], JENDOUBA)
    # 2nd and 3rd: linked by the room; the fire grows, the regional committee raises the level to crisis.
    for i in (1, 2):
        reports.append(await send_report(client, citizens[i], places[i], category="fire", text=words[i]))
        await check_place(client, staff, reports[i]["id"], places[i], (JENDOUBA, 3201))
        await link(client, staff, reports[i]["id"], incident_id, JENDOUBA)
    r = await client.post(
        f"{STAFF}/levels",
        json={"gouvernorat_codes": [JENDOUBA], "level": "crisis", "reason": "حريق غابات يقترب من المساكن"},
        headers=local_committee,
    )
    assert r.status_code == 200 and r.json()[0]["level"] == "crisis", r.text
    # A regional committee may not declare a disaster: that is the national committee's decision.
    disaster = {"gouvernorat_codes": [JENDOUBA], "level": "disaster", "reason": "حريق غابات خارج عن السيطرة"}
    assert (await client.post(f"{STAFF}/levels", json=disaster, headers=local_committee)).json()[
        "detail"
    ] == "level_not_allowed"
    # 4th report, then the national committee declares the disaster.
    reports.append(await send_report(client, citizens[3], places[3], category="fire", text=words[3]))
    await link(client, staff, reports[3]["id"], incident_id, JENDOUBA)
    assert (await client.post(f"{STAFF}/levels", json=disaster, headers=national_committee)).status_code == 200
    # 5th report: at disaster level it joins the incident by itself.
    reports.append(await send_report(client, citizens[4], places[4], category="fire", text=words[4]))
    detail = await check_place(client, staff, reports[4]["id"], places[4], (JENDOUBA, 3201))
    assert detail["incident_id"] == incident_id
    incident = await incident_of(client, staff, incident_id, JENDOUBA)
    assert incident["op_level"] == "disaster" and incident["report_count"] == 5 and incident["reporter_count"] == 5
    assert any(e["kind"] == "report_linked" and e["payload"].get("via") == "auto" for e in incident["timeline"])
    assert incident["gouvernorat_code"] == JENDOUBA
    assert abs(incident["centroid"]["lat"] - scene[0]) < 0.01 and abs(incident["centroid"]["lon"] - scene[1]) < 0.01

    # The crisis axis on Aïn Draham with the incident; the governor decides the evacuation.
    r = await client.post(
        f"{CRISIS}/axes",
        json={
            "name": "حرائق غابات عين دراهم",
            "kind": "forest_fire",
            "level": 4,
            "gouvernorat_code": JENDOUBA,
            "area": AIN_DRAHAM_AREA,
            "incident_ids": [incident_id],
        },
        headers=commander,
    )
    assert r.status_code == 201, r.text
    axis = r.json()
    due = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    evacuation = {
        "kind": "decision",
        "category": "evacuation",
        "body": "إخلاء حي الصنوبر والمدرسة فورا نحو دار الشباب",
        "executor": "regional",
        "due_at": due,
    }
    r = await client.post(f"{CRISIS}/axes/{axis['id']}/directives", json=evacuation, headers=governor)
    assert r.status_code == 201 and r.json()["issuer_role"] == "governor" and r.json()["signature"], r.text
    by_governor = r.json()
    room_jendouba = staff(["ops_manager"], JENDOUBA)
    r = await client.post(
        f"{CRISIS}/directives/{by_governor['id']}/status", json={"status": "received"}, headers=room_jendouba
    )
    assert r.status_code == 200, r.text

    # The fire crosses into Béja: the commander escalates to a national axis.
    r = await client.post(
        f"{CRISIS}/axes/{axis['id']}/escalate",
        json={"gouvernorats": [BEJA], "reason": "امتداد الحريق إلى غابات باجة"},
        headers=commander,
    )
    assert r.status_code == 200, r.text
    root = r.json()
    assert root["scope"] == "national" and root["gouvernorats"] == sorted([JENDOUBA, BEJA])

    # The national committee instructs both gouvernorats; Jendouba's committee acknowledges.
    r = await client.post(
        f"{STAFF}/directives",
        json={
            "title": "تعبئة وطنية لحرائق الشمال الغربي",
            "body": "توجيه الأرتال المتنقلة من الولايات المجاورة وطلب طائرات الإطفاء",
            "urgency": "urgent",
            "gouvernorat_codes": [JENDOUBA, BEJA],
        },
        headers=national_committee,
    )
    assert r.status_code == 201 and r.json()["from_level"] == "central", r.text
    national = r.json()
    r = await client.post(
        f"{STAFF}/directives/{national['id']}/ack", json={"note": "تم التنفيذ"}, headers=local_committee
    )
    assert r.status_code == 200 and r.json()["pending_acks"] == [BEJA]

    # The minister: an evacuation decision that overrides the governor's, and the army's support on the root.
    wider = {**evacuation, "body": "إخلاء كل الأحياء المحاذية للغابة وفتح مراكز إيواء"}
    r = await client.post(f"{CRISIS}/axes/{axis['id']}/directives", json=wider, headers=minister)
    assert r.status_code == 201 and r.json()["issuer_role"] == "minister", r.text
    by_minister = r.json()
    support = {"kind": "decision", "category": "support", "body": "تدخل الجيش الوطني بطائرتين", "executor": "central"}
    r = await client.post(f"{CRISIS}/axes/{root['id']}/directives", json=support, headers=minister)
    assert r.status_code == 201, r.text
    seen = (await client.get(f"{CRISIS}/axes/{axis['id']}", headers=room_jendouba)).json()
    by_id = {d["id"]: d for d in seen["directives"]}
    assert by_id[by_governor["id"]]["overridden_by"] == by_minister["id"]
    r = await client.post(
        f"{CRISIS}/directives/{by_minister['id']}/status", json={"status": "done"}, headers=room_jendouba
    )
    assert r.status_code == 200 and r.json()["done_at"], r.text

    # The team on the ground: casualties counted from the staff app feed every summary.
    leader = Leader(client, staff, gouvernorat=JENDOUBA)
    await leader.register(push_token=f"fcm-{uuid.uuid4().hex[:6]}")
    manager = staff(["ops_manager"], JENDOUBA)
    unit = await client.post(
        f"{STAFF}/units",
        json={"name_ar": "الوحدة المحلية بعين دراهم", "name_fr": "Unité d'Aïn Draham", "kind": "unit",
              "gouvernorat_code": JENDOUBA, "location": {"lat": 36.78, "lon": 8.686}},
        headers=manager,
    )  # fmt: skip
    assert unit.status_code == 201, unit.text
    vehicle = await client.post(
        f"{STAFF}/resources",
        json={"unit_id": unit.json()["id"], "kind": "fire_engine", "label": f"CCF-{secrets.token_hex(3)}"},
        headers=staff(["maintenance_officer"], JENDOUBA),
    )
    assert vehicle.status_code == 201, vehicle.text
    r = await leader.post("/shifts", write(resource_id=vehicle.json()["id"], crew_size=5, crew_names="مراد، نزار"))
    assert r.status_code == 201, r.text
    r = await client.post(
        f"{STAFF}/incidents/{incident_id}/assignments",
        json={"resource_id": vehicle.json()["id"], "order": "حماية المدرسة وإخلاؤها"},
        headers=room,
    )
    assert r.status_code == 201, r.text
    path = f"/missions/{r.json()['id']}"
    for step in ("en_route", "on_scene"):
        assert (await leader.post(f"{path}/status", write(status=step))).status_code == 200
    assert (await leader.post(f"{path}/casualties", write(rescued=12, injured_light=3))).status_code == 200
    assert (await leader.post(f"{path}/status", write(status="released"))).status_code == 200

    # The situation report: drafted from the figures, sent by the commander, read by the minister.
    r = await client.post(f"{CRISIS}/axes/{root['id']}/sitreps", headers=commander)
    assert r.status_code == 201, r.text
    sent = await client.post(
        f"{CRISIS}/sitreps/{r.json()['id']}/send",
        json={"assessment": "الحريق محاصر من ثلاث جهات، الإخلاء تم"},
        headers=commander,
    )
    assert sent.status_code == 200 and sent.json()["status"] == "sent", sent.text
    minister_view = (await client.get(f"{CRISIS}/axes/{root['id']}", headers=minister)).json()
    assert sent.json()["id"] in [s["id"] for s in minister_view["sitreps"]]

    # The disaster summary and map for the national committee: the area, the incident at its place, the figures.
    r = await client.get(f"{CRISIS}/disasters/map", params={"axis": axis["id"]}, headers=national_committee)
    assert r.status_code == 200, r.text
    summary = r.json()
    assert [a["id"] for a in summary["areas"]] == [axis["id"]]
    (placed,) = [i for i in summary["incidents"] if i["id"] == incident_id]
    assert summary["figures"]["rescued"] >= 12
    assert placed["gouvernorat_code"] == JENDOUBA and (placed["rescued"], placed["injured"]) == (12, 3)
    assert placed["lat"] == pytest.approx(incident["centroid"]["lat"], abs=1e-4)
    assert placed["lon"] == pytest.approx(incident["centroid"]["lon"], abs=1e-4)
    overview = (await client.get(f"{CRISIS}/command", headers=minister)).json()
    assert overview["role"] == "minister" and JENDOUBA in {g["code"] for g in overview["gouvernorats"]}

    # Closing the incident at disaster level: the citizens' points wait (rewards paused), then come back with the
    # normal level.
    closing = "أُخمد الحريق بعد 18 ساعة، أُنقذ 12 شخصا وأُخلي حيّان"
    closed = await close(client, staff, incident_id, JENDOUBA, closing, rescued=12, injured=3, evacuated=350)
    assert closed["evaluation"]["summary"] == closing and closed["casualties"]["rescued"] == 12
    await drain()
    held = await mine(client, citizens[0])
    assert held["paused"] is True and held["balance"] == 0 and held["pending_points"] > 0
    lower = {"gouvernorat_codes": [JENDOUBA], "level": "normal", "reason": "انتهاء الكارثة"}
    assert (await client.post(f"{STAFF}/levels", json=lower, headers=national_committee)).status_code == 200
    await drain()
    for headers in citizens:
        released = await mine(client, headers)
        assert released["paused"] is False and released["pending_points"] == 0 and released["balance"] > 0
        assert await my_status(client, headers, reports[citizens.index(headers)]["id"]) == "closed"

    # The national axis closes with its figures and a draft for the institutional memory.
    r = await client.post(
        f"{CRISIS}/axes/{root['id']}/close", json={"summary": "انتهت الكارثة وعادت الحياة"}, headers=commander
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "closed" and r.json()["closing"]["rescued"] >= 12 and r.json()["memory_id"]
    assert all(child["status"] == "closed" for child in r.json()["children"])
