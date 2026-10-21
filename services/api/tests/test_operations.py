"""Phase 5: levels and committees, units and resources, interventions, volunteers and call-outs."""

import secrets
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import date, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_system_sessionmaker
from app.modules.ai import scoring
from app.modules.ai.settings import PrioritySettings
from app.modules.notify import delivery
from app.modules.reports.domain import Category
from tests.conftest import TokenFactory, accept_charter, bearer, device_headers, report_body

Staff = Callable[..., dict[str, str]]
SFAX = {"lat": 34.7406, "lon": 10.7603, "accuracy_m": 8.0}


@pytest.fixture(autouse=True)
async def _normal_levels() -> AsyncIterator[None]:
    yield
    async with get_system_sessionmaker()() as s, s.begin():
        await s.execute(text("UPDATE ops.level_state SET level = 'normal', reason = NULL"))


def near(location: dict[str, float], dlat: float = 0.0, dlon: float = 0.0) -> dict[str, float]:
    return {**location, "lat": location["lat"] + dlat, "lon": location["lon"] + dlon}


def random_place() -> dict[str, float]:
    # Inside Sfax gouvernorat, away from other tests' fixed points.
    return {
        "lat": 34.60 + secrets.randbelow(1000) / 10_000,
        "lon": 10.50 + secrets.randbelow(1000) / 10_000,
        "accuracy_m": 10.0,
    }


async def new_report(client: httpx.AsyncClient, location: dict[str, float], **overrides: Any) -> dict[str, Any]:
    headers = device_headers()
    await accept_charter(client, headers)
    r = await client.post("/api/v1/reports", json=report_body(location, **overrides), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


async def new_incident(client: httpx.AsyncClient, staff: Staff, location: dict[str, float]) -> tuple[str, str]:
    report = await new_report(client, location)
    r = await client.post(
        f"/api/v1/staff/reports/{report['id']}/incident", json={"action": "new"}, headers=staff(["operator"])
    )
    assert r.status_code == 200, r.text
    return r.json()["incident_id"], report["id"]


async def report_status(client: httpx.AsyncClient, staff: Staff, report_id: str) -> str:
    r = await client.get(f"/api/v1/staff/reports/{report_id}", headers=staff(["operator"]))
    return r.json()["status"]  # type: ignore[no-any-return]


# ---------------------------------------------------------------- levels and committees


async def test_levels_permissions_and_priority(client: httpx.AsyncClient, staff: Staff) -> None:
    r = await client.get("/api/v1/staff/levels", headers=staff(["content_editor"]))
    assert r.status_code == 200 and len(r.json()) == 24
    assert {row["level"] for row in r.json()} == {"normal"}

    local = staff(["local_committee"], gouvernorat=61)
    body = {"gouvernorat_codes": [61], "level": "crisis", "reason": "فيضانات واسعة"}
    assert (await client.post("/api/v1/staff/levels", json=body, headers=staff(["operator"]))).status_code == 403
    assert (await client.post("/api/v1/staff/levels", json={**body, "gouvernorat_codes": [11]}, headers=local)).json()[
        "detail"
    ] == "level_not_allowed"
    assert (await client.post("/api/v1/staff/levels", json={**body, "level": "disaster"}, headers=local)).json()[
        "detail"
    ] == "level_not_allowed"

    report = await new_report(client, random_place())
    before = report_priority = None
    detail = (await client.get(f"/api/v1/staff/reports/{report['id']}", headers=staff())).json()
    before = detail["priority_score"]

    r = await client.post("/api/v1/staff/levels", json=body, headers=local)
    assert r.status_code == 200, r.text
    assert r.json()[0]["level"] == "crisis" and r.json()[0]["reason"] == "فيضانات واسعة"

    detail = (await client.get(f"/api/v1/staff/reports/{report['id']}", headers=staff())).json()
    report_priority = detail["priority_score"]
    component = next(c for c in detail["analysis"]["priority"]["components"] if c["key"] == "op_level")
    assert component["value"] == 0.7 and component["detail"]["level"] == "crisis"
    assert report_priority >= before

    central = staff(["central_committee"], gouvernorat=None)
    r = await client.post(
        "/api/v1/staff/levels",
        json={"gouvernorat_codes": [61], "level": "disaster", "reason": "إعلان كارثة"},
        headers=central,
    )
    assert r.status_code == 200
    # Lowering a disaster is central only.
    lower = {"gouvernorat_codes": [61], "level": "normal", "reason": "عودة إلى الوضع العادي"}
    assert (await client.post("/api/v1/staff/levels", json=lower, headers=local)).status_code == 403
    assert (await client.post("/api/v1/staff/levels", json=lower, headers=central)).status_code == 200


def test_op_level_is_a_bonus() -> None:
    settings = PrioritySettings()
    facts = scoring.Facts(category=Category.FIRE, reporter_kind="citizen")
    normal = scoring.priority(facts, 70, settings)
    crisis = scoring.priority(
        scoring.Facts(category=Category.FIRE, reporter_kind="citizen", op_level="crisis"), 70, settings
    )
    assert crisis["score"] >= normal["score"]
    component = next(c for c in normal["components"] if c["key"] == "op_level")
    assert component["value"] is None and component["detail"]["reason"] == "normal_level"
    # Saved settings from before phase 5 lack the new weight: it takes its default.
    old = {"weights": {k: v for k, v in settings.weights.items() if k != "op_level"}}
    assert PrioritySettings.model_validate(old).weights["op_level"] == 10


async def test_disaster_groups_automatically(client: httpx.AsyncClient, staff: Staff, isolated_window: None) -> None:
    place = random_place()
    central = staff(["central_committee"], gouvernorat=None)
    r = await client.post(
        "/api/v1/staff/levels",
        json={"gouvernorat_codes": [61], "level": "disaster", "reason": "كارثة طبيعية"},
        headers=central,
    )
    assert r.status_code == 200
    first = await new_report(client, place)
    second = await new_report(client, near(place, 0.0005))
    detail = (await client.get(f"/api/v1/staff/reports/{second['id']}", headers=staff())).json()
    assert detail["incident_id"] is not None
    incident = (await client.get(f"/api/v1/staff/incidents/{detail['incident_id']}", headers=staff())).json()
    assert {r["id"] for r in incident["reports"]} == {first["id"], second["id"]}
    assert incident["op_level"] == "disaster"
    assert any(e["kind"] == "report_linked" and e["payload"].get("via") == "auto" for e in incident["timeline"])


async def test_directives_and_acknowledgement(client: httpx.AsyncClient, staff: Staff) -> None:
    central = staff(["central_committee"], gouvernorat=None)
    sfax = staff(["local_committee"], gouvernorat=61)
    tunis = staff(["local_committee"], gouvernorat=11)
    r = await client.post(
        "/api/v1/staff/directives",
        json={"title": "رفع الجاهزية", "body": "تعبئة كل الوحدات", "urgency": "urgent", "gouvernorat_codes": [61]},
        headers=central,
    )
    assert r.status_code == 201, r.text
    directive = r.json()
    assert directive["from_level"] == "central" and directive["pending_acks"] == [61]

    pending = (await client.get("/api/v1/staff/directives?pending=true", headers=sfax)).json()["items"]
    assert directive["id"] in [d["id"] for d in pending]
    assert directive["id"] not in [
        d["id"] for d in (await client.get("/api/v1/staff/directives", headers=tunis)).json()["items"]
    ]
    assert (
        await client.post(f"/api/v1/staff/directives/{directive['id']}/ack", json={}, headers=tunis)
    ).status_code == 404

    r = await client.post(f"/api/v1/staff/directives/{directive['id']}/ack", json={"note": "تم"}, headers=sfax)
    assert r.status_code == 200 and r.json()["pending_acks"] == [] and r.json()["acks"][0]["note"] == "تم"
    assert (await client.post(f"/api/v1/staff/directives/{directive['id']}/ack", json={}, headers=sfax)).json()[
        "detail"
    ] == "already_acknowledged"

    # A local committee instructs its own gouvernorat only.
    local = {"title": "تعليمات محلية", "body": "…", "gouvernorat_codes": [11]}
    assert (await client.post("/api/v1/staff/directives", json=local, headers=sfax)).json()["detail"] == "out_of_scope"
    r = await client.post("/api/v1/staff/directives", json={**local, "gouvernorat_codes": []}, headers=sfax)
    assert r.status_code == 201 and r.json()["gouvernorat_codes"] == [61] and r.json()["from_level"] == "local"


async def test_performance(client: httpx.AsyncClient, staff: Staff) -> None:
    await new_report(client, random_place())
    r = await client.get("/api/v1/staff/committee/performance", headers=staff(["local_committee"], gouvernorat=61))
    assert r.status_code == 200, r.text
    body = r.json()
    assert [row["gouvernorat_code"] for row in body["rows"]] == [61]
    assert body["rows"][0]["reports"] >= 1 and body["national"]["reports"] == body["rows"][0]["reports"]
    national = (
        await client.get("/api/v1/staff/committee/performance", headers=staff(["central_committee"], None))
    ).json()
    assert len(national["rows"]) == 24
    assert (await client.get("/api/v1/staff/committee/performance", headers=staff(["operator"]))).status_code == 403


# ---------------------------------------------------------------- units, resources, interventions


async def make_resource(client: httpx.AsyncClient, staff: Staff, kind: str = "fire_engine") -> dict[str, Any]:
    manager = staff(["ops_manager"], gouvernorat=61)
    r = await client.post(
        "/api/v1/staff/units",
        json={
            "name_ar": "الوحدة الجهوية بصفاقس",
            "name_fr": "Unité régionale de Sfax",
            "kind": "unit",
            "gouvernorat_code": 61,
            "location": {"lat": 34.74, "lon": 10.76},
            "phone": "74 000 000",
        },
        headers=manager,
    )
    assert r.status_code == 201, r.text
    unit = r.json()
    r = await client.post(
        "/api/v1/staff/resources",
        json={"unit_id": unit["id"], "kind": kind, "label": f"FPT-{secrets.token_hex(3)}"},
        headers=manager,
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


async def test_units_and_resources_scope(client: httpx.AsyncClient, staff: Staff) -> None:
    resource = await make_resource(client, staff)
    assert resource["status"] == "available" and resource["gouvernorat_code"] == 61
    assert resource["location"] == {"lat": 34.74, "lon": 10.76}  # the unit's position
    tunis_manager = staff(["ops_manager"], gouvernorat=11)
    unit_body = {
        "name_ar": "وحدة",
        "name_fr": "Unité",
        "kind": "unit",
        "gouvernorat_code": 61,
        "location": {"lat": 34.7, "lon": 10.7},
    }
    assert (await client.post("/api/v1/staff/units", json=unit_body, headers=tunis_manager)).json()[
        "detail"
    ] == "out_of_scope"
    assert (await client.post("/api/v1/staff/units", json=unit_body, headers=staff(["operator"]))).status_code == 403
    items = (await client.get("/api/v1/staff/resources?status=available", headers=staff(["operator"], 11))).json()[
        "items"
    ]
    assert resource["id"] not in [i["id"] for i in items]
    summary = (await client.get("/api/v1/staff/resources/summary", headers=staff(["operator"]))).json()
    assert summary["by_kind"]["fire_engine"]["available"] >= 1
    geo = (await client.get("/api/v1/staff/resources/map", headers=staff(["operator"]))).json()
    assert {f["properties"]["layer"] for f in geo["features"]} >= {"unit", "resource"}
    r = await client.delete(f"/api/v1/staff/units/{resource['unit_id']}", headers=staff(["ops_manager"]))
    assert r.json()["detail"] == "unit_in_use"


async def test_intervention_flow(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    operator = staff(["operator"])
    incident_id, report_id = await new_incident(client, staff, random_place())
    resource = await make_resource(client, staff)

    r = await client.patch(
        f"/api/v1/staff/incidents/{incident_id}",
        json={"title": "حريق مستودع", "classification": "rockfall"},
        headers=operator,
    )
    assert r.json()["detail"] == "invalid_classification"
    r = await client.patch(
        f"/api/v1/staff/incidents/{incident_id}",
        json={"title": "حريق مستودع", "classification": "industrial_fire"},
        headers=operator,
    )
    assert r.status_code == 200 and r.json()["classification"] == "industrial_fire"

    r = await client.post(
        f"/api/v1/staff/incidents/{incident_id}/assignments",
        json={"resource_id": resource["id"], "order": "التوجه فورا"},
        headers=operator,
    )
    assert r.status_code == 201, r.text
    assignment = r.json()
    assert assignment["status"] == "ordered" and assignment["resource"]["label"] == resource["label"]
    assert await report_status(client, staff, report_id) == "in_progress"
    again = await client.post(
        f"/api/v1/staff/incidents/{incident_id}/assignments", json={"resource_id": resource["id"]}, headers=operator
    )
    assert again.json()["detail"] == "resource_busy"

    path = f"/api/v1/staff/assignments/{assignment['id']}/status"
    assert (await client.post(path, json={"status": "released"}, headers=operator)).json()[
        "detail"
    ] == "invalid_transition"
    assert (await client.post(path, json={"status": "en_route"}, headers=operator)).json()["en_route_at"]
    assert (await client.post(path, json={"status": "on_scene"}, headers=operator)).status_code == 200
    assert await report_status(client, staff, report_id) == "intervened"

    close = {"outcome": "resolved", "summary": "أُخمد الحريق دون إصابات", "casualties": {"evacuated": 12}}
    closer = staff(["field_commander"])
    assert (
        await client.post(f"/api/v1/staff/incidents/{incident_id}/close", json=close, headers=operator)
    ).status_code == 403
    r = await client.post(f"/api/v1/staff/incidents/{incident_id}/close", json=close, headers=closer)
    assert r.json()["detail"] == "assignments_active"
    assert (await client.post(path, json={"status": "released", "note": "عودة"}, headers=operator)).status_code == 200
    resources_now = (await client.get("/api/v1/staff/resources", headers=operator)).json()["items"]
    assert next(i for i in resources_now if i["id"] == resource["id"])["status"] == "available"

    r = await client.post(f"/api/v1/staff/incidents/{incident_id}/close", json=close, headers=closer)
    assert r.status_code == 200, r.text
    detail = r.json()
    assert detail["status"] == "closed" and detail["evaluation"]["casualties"]["evacuated"] == 12
    assert {e["kind"] for e in detail["timeline"]} >= {"assignment_created", "assignment_status", "evaluated"}
    assert await report_status(client, staff, report_id) == "closed"

    # The reporter was told of every step on their phone (content-free push: ids and status only).
    pushes = (
        (
            await session.execute(
                text(
                    "SELECT payload->'data'->>'status' FROM notify.outbox o "
                    "JOIN reports.report r ON r.user_id = o.user_id "
                    "WHERE r.id = :rid AND o.payload->>'type' = 'report_status' ORDER BY o.id"
                ),
                {"rid": report_id},
            )
        )
        .scalars()
        .all()
    )
    assert pushes == ["in_progress", "intervened", "closed"]


# ---------------------------------------------------------------- volunteers and call-outs


@pytest.fixture
def citizen_user(make_token: TokenFactory) -> Callable[[], dict[str, str]]:
    def _make() -> dict[str, str]:
        email = f"v{uuid.uuid4().hex[:8]}@example.tn"
        return bearer(make_token(roles=["citizen"], email=email, email_verified=True, name="Volunteer"))

    return _make


async def with_profile(client: httpx.AsyncClient, headers: dict[str, str], gouvernorat: int = 61) -> None:
    r = await client.put(
        "/api/v1/me/profile",
        json={
            "first_name": "Amine",
            "last_name": "Ben Salah",
            "cin": f"{secrets.randbelow(100_000_000):08d}",
            "phone": f"+2169{secrets.randbelow(10_000_000):07d}",
            "gouvernorat_code": gouvernorat,
            "delegation_id": gouvernorat * 100 + 1,
            "locale": "fr",
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text


def application(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "skills": ["first_aid", "diving"],
        "availability": "continuous",
        "period_from": date.today().isoformat(),
        "period_to": (date.today() + timedelta(days=180)).isoformat(),
        "notes": "مسعف متطوع منذ 2020",
    }
    body.update(overrides)
    return body


async def approved_volunteer(
    client: httpx.AsyncClient, staff: Staff, headers: dict[str, str], location: dict[str, float]
) -> str:
    await with_profile(client, headers)
    assert (await client.put("/api/v1/me/volunteer", json=application(), headers=headers)).status_code == 200
    me = (await client.get("/api/v1/me", headers=headers)).json()
    items = (await client.get("/api/v1/staff/volunteers?status=pending&limit=200", headers=staff())).json()["items"]
    volunteer_id = next(i["id"] for i in items if i["phone"] and i["status"] == "pending" and i["id"] not in SEEN)
    SEEN.add(volunteer_id)
    del me
    r = await client.post(
        f"/api/v1/staff/volunteers/{volunteer_id}/review", json={"decision": "approve"}, headers=staff(["ops_manager"])
    )
    assert r.status_code == 200, r.text
    r = await client.post(
        "/api/v1/me/volunteer/readiness",
        json={"ready": True, "lat": location["lat"], "lon": location["lon"], "accuracy_m": 12, "hours": 4},
        headers=headers,
    )
    assert r.status_code == 200 and r.json()["ready"], r.text
    return volunteer_id


SEEN: set[str] = set()


async def test_volunteer_application_and_review(
    client: httpx.AsyncClient, staff: Staff, citizen_user: Callable[[], dict[str, str]], session: AsyncSession
) -> None:
    headers = citizen_user()
    assert (await client.get("/api/v1/me/volunteer", headers=headers)).json()["detail"] == "not_volunteer"
    assert (await client.put("/api/v1/me/volunteer", json=application(), headers=headers)).json()[
        "detail"
    ] == "profile_incomplete"
    assert (await client.put("/api/v1/me/volunteer", json=application(), headers=device_headers())).json()[
        "detail"
    ] == "registration_required"
    await with_profile(client, headers)
    bad = application(period_to=(date.today() - timedelta(days=1)).isoformat())
    assert (await client.put("/api/v1/me/volunteer", json=bad, headers=headers)).json()["detail"] == "invalid_period"
    r = await client.put("/api/v1/me/volunteer", json=application(), headers=headers)
    assert r.status_code == 200 and r.json()["status"] == "pending"
    assert (
        await client.post(
            "/api/v1/me/volunteer/readiness", json={"ready": True, "lat": 34.7, "lon": 10.7}, headers=headers
        )
    ).json()["detail"] == "volunteer_not_approved"

    items = (await client.get("/api/v1/staff/volunteers?status=pending&skill=diving", headers=staff())).json()["items"]
    mine = [i for i in items if i["id"] not in SEEN]
    volunteer_id = mine[0]["id"]
    SEEN.add(volunteer_id)
    assert items[0]["status"] == "pending"
    assert (await client.get("/api/v1/staff/volunteers?status=pending", headers=staff(["operator"], 11))).json()[
        "items"
    ] == [] or volunteer_id not in [
        i["id"] for i in (await client.get("/api/v1/staff/volunteers", headers=staff(["operator"], 11))).json()["items"]
    ]
    review = f"/api/v1/staff/volunteers/{volunteer_id}/review"
    assert (await client.post(review, json={"decision": "approve"}, headers=staff(["operator"]))).status_code == 403
    assert (await client.post(review, json={"decision": "reject"}, headers=staff(["ops_manager"]))).json()[
        "detail"
    ] == "reason_required"
    r = await client.post(
        review, json={"decision": "reject", "reason": "شهادة الإسعاف غير مرفقة"}, headers=staff(["ops_manager"])
    )
    assert r.status_code == 200 and r.json()["status"] == "rejected" and r.json()["reviews"][0]["decision"] == "reject"
    # FR-A-021: the decision is e-mailed in the volunteer's language.
    mail = (
        await session.execute(
            text(
                "SELECT payload FROM notify.outbox WHERE channel = 'email' AND payload->>'text' LIKE :p "
                "ORDER BY id DESC LIMIT 1"
            ),
            {"p": "%Motif : شهادة الإسعاف غير مرفقة%"},
        )
    ).scalar_one()
    assert "candidature" in mail["subject"]

    # Resubmitting goes back to review; approval allows readiness.
    assert (await client.put("/api/v1/me/volunteer", json=application(), headers=headers)).json()["status"] == "pending"
    assert (
        await client.post(review, json={"decision": "approve"}, headers=staff(["local_committee"]))
    ).status_code == 200
    r = await client.post(
        "/api/v1/me/volunteer/readiness", json={"ready": True, "lat": 34.74, "lon": 10.76, "hours": 2}, headers=headers
    )
    assert r.status_code == 200 and r.json()["ready"]
    assert (
        await client.put("/api/v1/me/volunteer/location", json={"lat": 34.75, "lon": 10.77}, headers=headers)
    ).status_code == 204
    geo = (await client.get("/api/v1/staff/volunteers/map?skill=diving", headers=staff())).json()
    point = next(f for f in geo["features"] if f["properties"]["id"] == volunteer_id)
    assert point["geometry"]["coordinates"] == [10.77, 34.75]
    detail = (await client.get(f"/api/v1/staff/volunteers/{volunteer_id}", headers=staff())).json()
    assert detail["ready"] and detail["email"].endswith("@example.tn")

    # New skills are checked again: back to pending, readiness and position dropped.
    r = await client.put(
        "/api/v1/me/volunteer", json=application(skills=["firefighting"], version=r.json()["version"]), headers=headers
    )
    assert r.json()["status"] == "pending" and not r.json()["ready"]
    geo = (await client.get("/api/v1/staff/volunteers/map", headers=staff())).json()
    assert volunteer_id not in [f["properties"]["id"] for f in geo["features"]]
    assert (await client.delete("/api/v1/me/volunteer", headers=headers)).status_code == 204
    assert (await client.get("/api/v1/me/volunteer", headers=headers)).json()["status"] == "withdrawn"


async def test_callout_flow(
    client: httpx.AsyncClient, staff: Staff, citizen_user: Callable[[], dict[str, str]], channels: Any
) -> None:
    place = random_place()
    incident_id, report_id = await new_incident(client, staff, place)
    first, second = citizen_user(), citizen_user()
    v1 = await approved_volunteer(client, staff, first, near(place, 0.01))
    v2 = await approved_volunteer(client, staff, second, near(place, 0.02))
    operator = staff(["operator"])

    suggestions = (
        await client.get(
            f"/api/v1/staff/incidents/{incident_id}/volunteer-suggestions?skill=diving&radius_km=10", headers=operator
        )
    ).json()
    ranked = [s["volunteer_id"] for s in suggestions if s["volunteer_id"] in (v1, v2)]
    assert ranked == [v1, v2]
    assert (
        await client.get(
            f"/api/v1/staff/incidents/{incident_id}/volunteer-suggestions?skill=firefighting", headers=operator
        )
    ).json() == [] or all(
        s["volunteer_id"] not in (v1, v2)
        for s in (
            await client.get(
                f"/api/v1/staff/incidents/{incident_id}/volunteer-suggestions?skill=firefighting", headers=operator
            )
        ).json()
    )

    r = await client.post(
        f"/api/v1/staff/incidents/{incident_id}/callouts",
        json={
            "skill": "diving",
            "requested": 1,
            "radius_km": 10,
            "message": "غريق قرب الميناء",
            "volunteer_ids": [v1, v2],
        },
        headers=operator,
    )
    assert r.status_code == 201, r.text
    callout = r.json()
    assert callout["status"] == "open" and {t["volunteer_id"] for t in callout["targets"]} == {v1, v2}

    mine = (await client.get("/api/v1/me/callouts", headers=first)).json()
    assert mine[0]["id"] == callout["id"] and mine[0]["my_status"] == "sent" and mine[0]["incident_category"] == "fire"
    respond = f"/api/v1/me/callouts/{callout['id']}/respond"
    assert (await client.post(respond, json={"response": "accept"}, headers=first)).json()["detail"] == "eta_required"
    r = await client.post(respond, json={"response": "accept", "eta_minutes": 12}, headers=first)
    assert r.status_code == 200 and r.json()["my_status"] == "accepted" and r.json()["status"] == "filled"
    # Filled: the other volunteer can no longer accept.
    assert (await client.post(respond, json={"response": "accept", "eta_minutes": 5}, headers=second)).json()[
        "detail"
    ] == "callout_closed"
    assert await report_status(client, staff, report_id) == "in_progress"

    staff_view = (await client.get(f"/api/v1/staff/callouts/{callout['id']}", headers=operator)).json()
    target = next(t for t in staff_view["targets"] if t["volunteer_id"] == v1)
    assert target["eta_minutes"] == 12 and target["position"] is not None and staff_view["accepted"] == 1
    incident = (await client.get(f"/api/v1/staff/incidents/{incident_id}", headers=operator)).json()
    assignment = next(a for a in incident["assignments"] if a["kind"] == "volunteer")
    assert assignment["status"] == "en_route" and assignment["volunteer"]["id"] == v1

    r = await client.post(f"/api/v1/me/callouts/{callout['id']}/arrived", headers=first)
    assert r.status_code == 200 and r.json()["my_status"] == "arrived"
    assert await report_status(client, staff, report_id) == "intervened"
    incident = (await client.get(f"/api/v1/staff/incidents/{incident_id}", headers=operator)).json()
    assert next(a for a in incident["assignments"] if a["kind"] == "volunteer")["status"] == "on_scene"

    # A push reached each called volunteer's devices, on the alert channel.
    await client.put(
        "/api/v1/devices", json={"token": "tok-" + "v" * 30, "platform": "android", "locale": "fr"}, headers=second
    )
    while await delivery.run_outbox(get_system_sessionmaker()):
        pass
    callout_pushes = [p for (p,) in channels.push.sent if p.data.get("type") == "callout"]
    # Content-free (A8): generic text in the device's language, ids only; the app reads /me/callouts.
    assert any(
        p.token == "tok-" + "v" * 30
        and p.alert
        and p.data == {"callout_id": callout["id"], "redacted": "1", "type": "callout"}
        and (p.title, p.body) == ("e-Himaya", "Vous avez une nouvelle mise à jour")
        for p in callout_pushes
    )

    r = await client.post(f"/api/v1/staff/callouts/{callout['id']}/cancel", headers=operator)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
