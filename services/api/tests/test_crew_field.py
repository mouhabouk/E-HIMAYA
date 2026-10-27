# covers: F-STF-03, F-STF-04, F-STF-05, F-DSH-35
"""Staff app, the field side (phase P4b, docs/phase-p4/design-staff.md §5): situation reports and updates, alerts
seen by the room, photos, voice notes and texts, hospitals picked from the map, detailed reports from the templates
the Office approves, and the number the room gives the team."""

import secrets
import uuid
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import FakeStore
from tests.test_crew import Leader, Staff, _on_shift, new_incident, write

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 200
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200
M4A = b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 200


def _place() -> dict[str, float]:
    # Inside Sfax gouvernorat, in an area of its own: the incidents of these tests stay open and must not come
    # within the duplicate radius of the incidents other tests create with ``random_place``.
    return {
        "lat": 34.45 + secrets.randbelow(1000) / 10_000,
        "lon": 10.30 + secrets.randbelow(1000) / 10_000,
        "accuracy_m": 10.0,
    }


async def _mission(
    client: httpx.AsyncClient, staff: Staff, *, on_scene: bool = True, **assign: Any
) -> tuple[Leader, str, str, dict[str, float]]:
    """A leader on shift with one mission (on scene unless asked otherwise); returns its path and incident."""
    leader, resource = await _on_shift(client, staff)
    place = _place()
    incident_id, _ = await new_incident(client, staff, place)
    r = await client.post(
        f"/api/v1/staff/incidents/{incident_id}/assignments",
        json={"resource_id": resource["id"], "order": "حريق، التوجه فورا", **assign},
        headers=staff(["operator"]),
    )
    assert r.status_code == 201, r.text
    path = f"/missions/{r.json()['id']}"
    if on_scene:
        for step in ("en_route", "on_scene"):
            assert (await leader.post(f"{path}/status", write(status=step))).status_code == 200
    return leader, path, incident_id, place


async def _upload(
    leader: Leader, path: str, kind: str, data: bytes, content_type: str, **params: Any
) -> httpx.Response:
    query = {"kind": kind, "client_id": str(uuid.uuid4()), **params}
    return await leader.client.post(
        f"/api/v1/crew{path}/attachments",
        params=query,
        content=data,
        headers={**leader.h, "Content-Type": content_type},
    )


async def _incident(client: httpx.AsyncClient, staff: Staff, incident_id: str) -> dict[str, Any]:
    r = await client.get(f"/api/v1/staff/incidents/{incident_id}", headers=staff(["operator"]))
    assert r.status_code == 200, r.text
    return r.json()  # type: ignore[no-any-return]


async def test_situation_reports_and_counters(client: httpx.AsyncClient, staff: Staff) -> None:
    leader, path, incident_id, _ = await _mission(client, staff)
    first = write(category="fire", severity=2, backup_kinds=["ambulance", "extrication", "ambulance"])
    r = await leader.post(f"{path}/situation", first)
    assert r.status_code == 200, r.text
    report = r.json()["field_report"]
    assert (
        report["kind"] == "first" and report["backup_needed"] and report["backup_kinds"] == ["ambulance", "extrication"]
    )
    assert (
        await leader.post(f"{path}/situation", write(category="fire", severity=3, backup_kinds=["tank"]))
    ).status_code == 422

    r = await leader.post(f"{path}/situation", write(category="fire", severity=4))
    update = r.json()["field_report"]
    assert update["kind"] == "update" and update["severity"] == 4 and update["backup_kinds"] == []

    r = await leader.post(f"{path}/casualties", write(injured_light=2, injured_serious=1, deceased=1))
    counts = r.json()["casualties"]
    assert (counts["injured_light"], counts["injured_serious"], counts["deceased"], counts["transported"]) == (
        2,
        1,
        1,
        0,
    )

    detail = await _incident(client, staff, incident_id)
    assert [f["kind"] for f in detail["field_reports"]] == ["update", "first"]
    assert detail["casualties"]["injured_serious"] == 1
    entries = [e for e in detail["timeline"] if e["kind"] == "field_report"]
    assert {e["payload"]["report"] for e in entries} == {"first", "update"}


async def test_alerts_seen_by_the_room(client: httpx.AsyncClient, staff: Staff) -> None:
    # Before arriving: backup and danger can be sent from the order on.
    leader, path, incident_id, _ = await _mission(client, staff, on_scene=False)
    backup = write(kind="backup", items=["fire_engine", "water_tanker"])
    r = await leader.post(f"{path}/alerts", backup)
    assert r.status_code == 200, r.text
    assert (await leader.post(f"{path}/alerts", backup)).status_code == 200  # sent twice, applied once
    assert (await leader.post(f"{path}/alerts", write(kind="danger", items=["ambulance"]))).json()[
        "detail"
    ] == "invalid_item"
    r = await leader.post(f"{path}/alerts", write(kind="danger", items=["collapse", "gas"]))
    alerts = r.json()["alerts"]
    assert [a["kind"] for a in alerts] == ["danger", "backup"] and alerts[1]["items"] == ["fire_engine", "water_tanker"]
    assert all(a["seen_at"] is None for a in alerts)

    detail = await _incident(client, staff, incident_id)
    assert len(detail["alerts"]) == 2 and detail["alerts"][0]["resource_label"]
    assert detail["assignments"][0]["crew"]["unseen_alerts"] == 2

    alert_id = detail["alerts"][1]["id"]
    # Another gouvernorat's room cannot see it; a citizen-facing role cannot mark it.
    assert (
        await client.post(f"/api/v1/staff/crew-alerts/{alert_id}/seen", headers=staff(["operator"], 11))
    ).status_code == 404
    assert (
        await client.post(f"/api/v1/staff/crew-alerts/{alert_id}/seen", headers=staff(["content_editor"]))
    ).status_code == 403
    r = await client.post(f"/api/v1/staff/crew-alerts/{alert_id}/seen", headers=staff(["operator"], name="ليلى"))
    assert r.status_code == 200 and r.json()["seen_at"] and r.json()["seen_by_name"] == "ليلى"

    mission = (await leader.get("/missions")).json()["items"][0]
    seen = next(a for a in mission["alerts"] if a["id"] == alert_id)
    assert seen["seen_at"] and seen["seen_by_name"] == "ليلى"
    detail = await _incident(client, staff, incident_id)
    assert detail["assignments"][0]["crew"]["unseen_alerts"] == 1
    assert {"crew_alert", "crew_alert_seen"} <= {e["kind"] for e in detail["timeline"]}
    # The crews page counts what is still unseen per team.
    shifts = (await client.get("/api/v1/staff/shifts", headers=staff(["operator"]))).json()
    shift_id = detail["assignments"][0]["crew"]["shift_id"]
    assert next(s for s in shifts if s["id"] == shift_id)["unseen_alerts"] == 1


async def test_photos_voice_notes_and_texts(
    client: httpx.AsyncClient, staff: Staff, _isolated_infra: FakeStore
) -> None:
    leader, path, incident_id, _ = await _mission(client, staff)
    r = await _upload(leader, path, "photo", JPEG, "image/jpeg")
    assert r.status_code == 200, r.text
    photo = r.json()["attachments"][0]
    assert photo["kind"] == "photo" and photo["url"] is None and photo["bytes"] == len(JPEG)

    # The bytes decide: a PNG declared as JPEG, an empty body, a voice note without its length are refused.
    assert (await _upload(leader, path, "photo", PNG, "image/jpeg")).json()["detail"] == "type_mismatch"
    assert (await _upload(leader, path, "photo", b"", "image/jpeg")).json()["detail"] == "empty_file"
    assert (await _upload(leader, path, "photo", JPEG, "application/pdf")).status_code == 415
    assert (await _upload(leader, path, "voice", M4A, "audio/mp4")).json()["detail"] == "invalid_duration"
    big = JPEG + b"\x00" * (8 * 1024 * 1024)
    assert (await _upload(leader, path, "photo", big, "image/jpeg")).status_code == 413
    r = await _upload(leader, path, "voice", M4A, "audio/mp4", duration_s=12.5)
    assert r.status_code == 200, r.text
    assert (await leader.post(f"{path}/notes", write(body="السقف آيل للسقوط"))).status_code == 200

    stored = [k for k in _isolated_infra.objects if k.startswith(f"field/{incident_id}/")]
    assert len(stored) == 2 and any(k.endswith(".jpg") for k in stored)

    detail = await _incident(client, staff, incident_id)
    kinds = [(a["kind"], a["body"], bool(a["url"])) for a in detail["attachments"]]
    assert kinds == [("photo", None, True), ("voice", None, True), ("text", "السقف آيل للسقوط", False)]
    assert detail["attachments"][1]["duration_s"] == 12.5


async def test_hospitals_from_the_map(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    leader, path, _, place = await _mission(client, staff)
    layer_id = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO geo.layer (id, key, name, icon, colour, simulated, created_by, updated_by) "
            "VALUES (:id, :key, CAST(:name AS jsonb), 'hospital', '#C62828', true, 'test', 'test')"
        ),
        {
            "id": layer_id,
            "key": f"test_hospitals_{layer_id.hex[:8]}",
            "name": '{"ar": "مستشفيات", "fr": "Hôpitaux", "en": "Hospitals"}',
        },
    )
    near, far = uuid.uuid4(), uuid.uuid4()
    for fid, name, dlat in ((near, "مستشفى قريب", 0.001), (far, "مستشفى بعيد", 0.003)):
        await session.execute(
            text(
                "INSERT INTO geo.layer_feature (id, layer_id, ref, name, location) "
                "VALUES (:id, :layer, :ref, :name, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography)"
            ),
            {
                "id": fid,
                "layer": layer_id,
                "ref": fid.hex,
                "name": name,
                "lat": place["lat"] + dlat,
                "lon": place["lon"],
            },
        )
    await session.commit()

    found = (await leader.get(f"{path}/hospitals")).json()
    assert [h["id"] for h in found[:2]] == [str(near), str(far)]
    assert 100 <= found[0]["distance_m"] <= 130 and found[0]["simulated"] is True

    r = await leader.post(
        f"{path}/transports", write(triage="yellow", age_band="60_plus", sex="female", hospital_ref=str(near))
    )
    assert r.status_code == 200, r.text
    taken = r.json()["transports"][0]
    assert taken["hospital"] == "مستشفى قريب" and taken["hospital_ref"] == str(near) and taken["age_band"] == "60_plus"
    assert r.json()["casualties"]["transported"] == 1
    unknown = write(triage="red", age_band="30_44", sex="male", hospital_ref=str(uuid.uuid4()))
    assert (await leader.post(f"{path}/transports", unknown)).json()["detail"] == "unknown_hospital"
    neither = write(triage="red", age_band="30_44", sex="male")
    assert (await leader.post(f"{path}/transports", neither)).json()["detail"] == "hospital_required"
    # The former age bands are read but no longer sent.
    old = write(triage="red", age_band="adult", sex="male", hospital="مستشفى")
    assert (await leader.post(f"{path}/transports", old)).status_code == 422

    # The other tests count the layers: this one goes (its features with it, the transport keeps the name).
    await session.execute(text("DELETE FROM geo.layer WHERE id = :id"), {"id": layer_id})
    await session.commit()


async def test_detailed_report_and_templates(client: httpx.AsyncClient, staff: Staff) -> None:
    leader, path, incident_id, _ = await _mission(client, staff)
    mission = next(m for m in (await leader.get("/missions")).json()["items"] if path.endswith(m["id"]))
    template = mission["template"]
    assert template["category"] == "fire" and template["status"] == "approved"
    keys = {f["key"]: f for f in template["fields"]}
    assert {"place", "extent", "spread_risk", "area_ha"} <= set(keys)

    answers = {"place": "industrial", "extent": "partial", "cause": "unknown", "spread_risk": True, "state": "partial"}
    body = write(template_id=template["id"], answers=answers)
    for bad, code in (
        ({**answers, "colour": "red"}, "unknown_field"),
        ({**answers, "place": "boat"}, "invalid_answer"),
        ({**answers, "area_ha": -1}, "invalid_answer"),
        ({k: v for k, v in answers.items() if k != "extent"}, "answer_required"),
    ):
        r = await leader.post(f"{path}/detailed-report", write(template_id=template["id"], answers=bad))
        assert r.json()["detail"] == code, bad
    r = await leader.post(f"{path}/detailed-report", {**body, "note": "المخزن الخلفي"})
    assert r.status_code == 200, r.text
    detailed = r.json()["detailed_report"]
    assert (
        detailed["kind"] == "detailed"
        and detailed["severity"] is None
        and detailed["template_version"] == template["version"]
    )
    assert detailed["answers"]["place"] == "industrial" and detailed["note"] == "المخزن الخلفي"
    assert r.json()["field_report"] is None  # a detailed report is not a situation report

    # The Office edits: a regional manager may not; central command drafts version 2 and approves it.
    regional = staff(["ops_manager"], 61)
    office = staff(["central_committee"], None, name="الديوان")
    fields = [
        *template["fields"],
        {"key": "hydrants", "type": "count", "label": {"ar": "حنفيات", "fr": "Poteaux", "en": "Hydrants"}},
    ]
    draft_body = {"category": "fire", "fields": fields}
    assert (await client.post("/api/v1/staff/report-templates", json=draft_body, headers=regional)).status_code == 403
    r = await client.post("/api/v1/staff/report-templates", json=draft_body, headers=office)
    assert r.status_code == 201, r.text
    draft = r.json()
    assert draft["status"] == "draft" and draft["version"] >= 2 and draft["simulated"] is False
    assert (await client.post("/api/v1/staff/report-templates", json=draft_body, headers=office)).json()[
        "detail"
    ] == "draft_exists"
    dup = {"fields": [fields[0], fields[0]]}
    assert (await client.patch(f"/api/v1/staff/report-templates/{draft['id']}", json=dup, headers=office)).json()[
        "detail"
    ] == "duplicate_field"
    one_option = {"fields": [{**fields[0], "options": fields[0]["options"][:1]}]}
    assert (
        await client.patch(f"/api/v1/staff/report-templates/{draft['id']}", json=one_option, headers=office)
    ).json()["detail"] == "options_required"

    # Until approved, the phone keeps the current version.
    mission = next(m for m in (await leader.get("/missions")).json()["items"] if path.endswith(m["id"]))
    assert mission["template"]["id"] == template["id"]
    r = await client.post(f"/api/v1/staff/report-templates/{draft['id']}/approve", headers=office)
    assert r.status_code == 200 and r.json()["approved_by_name"] == "الديوان"
    listed = (await client.get("/api/v1/staff/report-templates", headers=staff(["operator"]))).json()
    assert template["id"] not in [t["id"] for t in listed]
    retired = (await client.get("/api/v1/staff/report-templates?retired=true", headers=office)).json()
    assert next(t for t in retired if t["id"] == template["id"])["status"] == "retired"

    # A report on the retired version is refused; the earlier one keeps its version.
    assert (await leader.post(f"{path}/detailed-report", write(template_id=template["id"], answers=answers))).json()[
        "detail"
    ] == "template_not_current"
    mission = next(m for m in (await leader.get("/missions")).json()["items"] if path.endswith(m["id"]))
    assert mission["template"]["id"] == draft["id"]
    r = await leader.post(f"{path}/detailed-report", write(template_id=draft["id"], answers={**answers, "hydrants": 2}))
    assert r.status_code == 200 and r.json()["detailed_report"]["answers"]["hydrants"] == 2

    detail = await _incident(client, staff, incident_id)
    assert [f["template_version"] for f in detail["field_reports"] if f["kind"] == "detailed"] == [
        draft["version"],
        template["version"],
    ]

    # The fire template stays for the next tests: put version 1's fields back as the approved one.
    restore = await client.post(
        "/api/v1/staff/report-templates", json={"category": "fire", "fields": template["fields"]}, headers=office
    )
    assert (
        await client.post(f"/api/v1/staff/report-templates/{restore.json()['id']}/approve", headers=office)
    ).status_code == 200


async def test_template_drafts_are_discarded_and_retired(client: httpx.AsyncClient, staff: Staff) -> None:
    office = staff(["ops_manager"], None)
    field = {"key": "boats", "type": "count", "label": {"ar": "قوارب", "fr": "Bateaux", "en": "Boats"}}
    body = {"category": "drowning", "classification": "well", "fields": [field]}
    assert (
        await client.post("/api/v1/staff/report-templates", json={**body, "classification": "rockfall"}, headers=office)
    ).json()["detail"] == "invalid_classification"
    r = await client.post("/api/v1/staff/report-templates", json=body, headers=office)
    assert r.status_code == 201, r.text
    draft = r.json()
    assert (await client.post(f"/api/v1/staff/report-templates/{draft['id']}/retire", headers=office)).json()[
        "detail"
    ] == "not_approved"
    assert (await client.delete(f"/api/v1/staff/report-templates/{draft['id']}", headers=office)).status_code == 204
    r = await client.post("/api/v1/staff/report-templates", json=body, headers=office)
    approved = (await client.post(f"/api/v1/staff/report-templates/{r.json()['id']}/approve", headers=office)).json()
    assert approved["classification"] == "well" and approved["status"] == "approved"
    # The category-wide template stays approved next to the one of the classification.
    listed = (await client.get("/api/v1/staff/report-templates", headers=office)).json()
    assert {(t["classification"], t["status"]) for t in listed if t["category"] == "drowning"} >= {
        (None, "approved"),
        ("well", "approved"),
    }
    r = await client.post(f"/api/v1/staff/report-templates/{approved['id']}/retire", headers=office)
    assert r.json()["status"] == "retired"


async def test_contact_phone_for_the_scene(client: httpx.AsyncClient, staff: Staff) -> None:
    leader, path, incident_id, _ = await _mission(client, staff, on_scene=False, contact_phone="+216 98 123 456")
    mission = next(m for m in (await leader.get("/missions")).json()["items"] if path.endswith(m["id"]))
    assert mission["contact_phone"] == "+216 98 123 456"
    detail = await _incident(client, staff, incident_id)
    assert detail["assignments"][0]["contact_phone"] == "+216 98 123 456"
    _, resource = await _on_shift(client, staff)
    r = await client.post(
        f"/api/v1/staff/incidents/{incident_id}/assignments",
        json={"resource_id": resource["id"], "contact_phone": "call me"},
        headers=staff(["operator"]),
    )
    assert r.status_code == 422
