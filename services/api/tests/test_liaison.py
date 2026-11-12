"""Informing the partner bodies by phone, OS20 (docs/phase-os20/design-os20.md): the contact system and its scope, the
level of a report, the bodies informed, their calls, the follow-ups, the history and the picker."""

import secrets
import uuid
from collections.abc import Callable
from typing import Any

import httpx

from tests.test_operations import new_incident

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/staff/liaison"
SFAX = 61
TUNIS = 11


def _place() -> dict[str, float]:
    # Inside Sfax gouvernorat, away from the other tests' incidents (a located report needs its accuracy).
    return {
        "lat": 34.85 + secrets.randbelow(800) / 10_000,
        "lon": 10.30 + secrets.randbelow(800) / 10_000,
        "accuracy_m": 10.0,
    }


def _tag() -> str:
    return secrets.token_hex(3)


async def _body(client: httpx.AsyncClient, headers: dict[str, str], **body: Any) -> dict[str, Any]:
    payload = {
        "category": "regional",
        "name": f"معتمدية التجربة {_tag()}",
        "domain": "الإدارة المحلية",
        "officials": [{"name": "ع. ب.", "role": "المعتمد", "phones": ["74 000 650"], "duty": "24/24"}],
        **body,
    }
    r = await client.post(f"{URL}/bodies", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


async def _agency_body(client: httpx.AsyncClient, headers: dict[str, str], agency: str) -> dict[str, Any]:
    """The Sfax body of a service (created once: one active body per service and gouvernorat)."""
    bodies = (await client.get(f"{URL}/bodies", params={"gouvernorat": SFAX}, headers=headers)).json()
    for b in bodies:
        if b["agency"] == agency and b["gouvernorat_code"] == SFAX:
            return b  # type: ignore[no-any-return]
    return await _body(
        client,
        headers,
        category="security",
        agency=agency,
        name=f"إقليم {agency} بصفاقس",
        public_phone="197",
        officials=[
            {"name": "م. ع.", "role": "رئيس الإقليم", "phones": ["74 000 197"], "position": 1},
            {"name": "ر. س.", "role": "نائب", "phones": ["74 000 198"], "position": 2},
        ],
    )


# ---------------------------------------------------------------- the contact system


async def test_contact_system_follows_the_rooms(client: httpx.AsyncClient, staff: Staff) -> None:
    sfax = staff(["operator"], SFAX, name="عون صفاقس")
    tunis = staff(["operator"], TUNIS)
    central = staff(["operator"], None, name="عون القاعة المركزية")
    tag = _tag()
    mine = await _body(
        client, sfax, name=f"والي صفاقس {tag}", category="regional", location={"lat": 34.74, "lon": 10.76}
    )
    assert mine["gouvernorat_code"] == SFAX and mine["editable"] and mine["created_by_name"] == "عون صفاقس"
    assert mine["officials"][0]["phones"] == ["74 000 650"] and mine["location"]["lat"] == 34.74

    # A regional room reads its gouvernorat and the national bodies, never another gouvernorat's.
    seen = (await client.get(f"{URL}/bodies", headers=tunis)).json()
    assert all(b["gouvernorat_code"] in (None, TUNIS) for b in seen)
    assert {"central_room", "director_general"} <= {b["agency"] for b in seen}
    assert mine["id"] not in {b["id"] for b in seen}
    assert (await client.get(f"{URL}/bodies/{mine['id']}", headers=tunis)).status_code == 404

    # It adds bodies of its own gouvernorat only, and keeps none of the national ones.
    r = await client.post(
        f"{URL}/bodies", json={"category": "public", "name": "مستشفى", "gouvernorat_code": TUNIS}, headers=sfax
    )
    assert r.status_code == 403 and r.json()["detail"] == "outside_gouvernorat"
    national = next(b for b in seen if b["agency"] == "central_room")
    assert not national["editable"]
    patch = {"domain": "تجربة", "version": national["version"]}
    r = await client.patch(f"{URL}/bodies/{national['id']}", json=patch, headers=sfax)
    assert r.status_code == 403 and r.json()["detail"] == "not_owner"

    # The central room reads every body and keeps the national ones; a regional body stays its room's.
    every = (await client.get(f"{URL}/bodies", headers=central)).json()
    theirs = next(b for b in every if b["id"] == mine["id"])
    assert not theirs["editable"]
    r = await client.patch(f"{URL}/bodies/{mine['id']}", json={"domain": "x y", "version": 1}, headers=central)
    assert r.status_code == 403
    ministry = await _body(client, central, category="ministry", name=f"وزارة التجهيز {tag}", officials=[])
    assert ministry["gouvernorat_code"] is None and ministry["editable"]
    assert ministry["id"] in {b["id"] for b in (await client.get(f"{URL}/bodies", headers=sfax)).json()}

    # Search: by an official's phone; the gouvernorat filter adds the national bodies.
    found = (await client.get(f"{URL}/bodies", params={"q": "000 650"}, headers=sfax)).json()
    assert mine["id"] in {b["id"] for b in found}
    filtered = (await client.get(f"{URL}/bodies", params={"gouvernorat": SFAX}, headers=central)).json()
    assert {b["gouvernorat_code"] for b in filtered} <= {None, SFAX} and mine["id"] in {b["id"] for b in filtered}

    # The owning room updates: the version guards concurrent edits.
    r = await client.patch(
        f"{URL}/bodies/{mine['id']}", json={"address": "شارع الحبيب بورقيبة", "version": 1}, headers=sfax
    )
    assert r.status_code == 200 and r.json()["version"] == 2 and r.json()["address"] == "شارع الحبيب بورقيبة"
    r = await client.patch(f"{URL}/bodies/{mine['id']}", json={"address": "قديم", "version": 1}, headers=sfax)
    assert r.status_code == 409 and r.json()["detail"] == "version_conflict"

    # Officials: added, updated and archived by the owning room.
    r = await client.post(
        f"{URL}/bodies/{mine['id']}/officials",
        json={"name": "س. ك.", "role": "الكاتب العام", "phones": ["74 000 651", "98 000 651"], "position": 2},
        headers=sfax,
    )
    assert r.status_code == 201, r.text
    official = r.json()
    assert (
        await client.post(f"{URL}/bodies/{mine['id']}/officials", json={"name": "x y", "phones": ["1"]}, headers=sfax)
    ).status_code == 422
    assert (
        await client.patch(f"{URL}/officials/{official['id']}", json={"duty": "8:00-17:00"}, headers=central)
    ).status_code == 403
    r = await client.patch(f"{URL}/officials/{official['id']}", json={"duty": "8:00-17:00"}, headers=sfax)
    assert r.status_code == 200 and r.json()["duty"] == "8:00-17:00"
    assert (await client.delete(f"{URL}/officials/{official['id']}", headers=sfax)).status_code == 204
    names = [o["name"] for o in (await client.get(f"{URL}/bodies/{mine['id']}", headers=sfax)).json()["officials"]]
    assert names == ["ع. ب."]

    # The internal national bodies are never archived; a regional body is, by its room.
    r = await client.post(f"{URL}/bodies/{national['id']}/archive", headers=central)
    assert r.status_code == 409 and r.json()["detail"] == "internal_body"
    r = await client.post(f"{URL}/bodies/{mine['id']}/archive", headers=sfax)
    assert r.status_code == 200 and r.json()["status"] == "archived"
    assert mine["id"] not in {b["id"] for b in (await client.get(f"{URL}/bodies", headers=sfax)).json()}

    # Readers only read.
    viewer = staff(["content_editor"], SFAX)
    assert (
        await client.post(f"{URL}/bodies", json={"category": "public", "name": "ب ب"}, headers=viewer)
    ).status_code == 403


# ---------------------------------------------------------------- a report


async def test_a_report_informs_bodies_by_phone(client: httpx.AsyncClient, staff: Staff) -> None:
    room = staff(["operator"], SFAX, name="عون صفاقس")
    police = await _agency_body(client, room, "police")
    incident_id, _ = await new_incident(client, staff, _place())
    view = (await client.get(f"{URL}/incidents/{incident_id}", headers=room)).json()
    assert view["level"] is None and view["parties"] == []
    # A fire: the engine suggests the police and STEG; the police is matched with the Sfax body.
    by_agency = {s["agency"]: s for s in view["suggestions"]}
    assert {"police", "steg"} <= set(by_agency)
    assert by_agency["police"]["body_id"] == police["id"] and not by_agency["police"]["missing"]
    assert by_agency["police"]["reason"]["ar"]

    # Level 1: handled in the room; no body can then be added.
    r = await client.put(f"{URL}/incidents/{incident_id}/level", json={"level": 1}, headers=room)
    assert r.status_code == 200 and r.json()["level"]["level"] == 1 and r.json()["level"]["set_by_name"] == "عون صفاقس"
    body = {"parties": [{"body_id": police["id"], "suggested": True, "reason": "تأمين الطوق"}]}
    r = await client.post(f"{URL}/incidents/{incident_id}/parties", json=body, headers=room)
    assert r.status_code == 409 and r.json()["detail"] == "level_room_only"

    # Level 2: several bodies at once, the first official in calling order unless one is chosen.
    assert (
        await client.put(f"{URL}/incidents/{incident_id}/level", json={"level": 2}, headers=room)
    ).status_code == 200
    missing = await _body(client, room, origin_incident_id=incident_id)
    second = police["officials"][1]["id"]
    body = {
        "parties": [
            {"body_id": police["id"], "suggested": True, "reason": "تأمين الطوق"},
            {"body_id": missing["id"], "official_id": missing["officials"][0]["id"]},
            {"body_id": police["id"]},
        ]
    }
    r = await client.post(f"{URL}/incidents/{incident_id}/parties", json=body, headers=room)
    assert r.status_code == 200, r.text
    parties = {p["body_id"]: p for p in r.json()["parties"]}
    assert len(r.json()["parties"]) == 2
    assert parties[police["id"]]["official_name"] == "م. ع." and parties[police["id"]]["phones"] == ["74 000 197"]
    assert parties[police["id"]]["suggested"] and parties[police["id"]]["last_result"] is None
    assert next(s for s in r.json()["suggestions"] if s["agency"] == "police")["in_report"]
    # Level 1 is refused once bodies are informed; an official of another body is refused.
    r = await client.put(f"{URL}/incidents/{incident_id}/level", json={"level": 1}, headers=room)
    assert r.status_code == 409 and r.json()["detail"] == "parties_informed"
    pid = parties[police["id"]]["id"]
    bad = {"official_id": missing["officials"][0]["id"]}
    assert (
        await client.patch(f"{URL}/incidents/{incident_id}/parties/{pid}", json=bad, headers=room)
    ).status_code == 422

    # No answer: a reminder to call back; then the deputy answers and promises a patrol.
    call = {"number": "74 000 197", "via": "manual", "result": "no_answer", "follow_up_min": 10}
    r = await client.post(f"{URL}/incidents/{incident_id}/parties/{pid}/calls", json=call, headers=room)
    assert r.status_code == 201, r.text
    first = r.json()
    assert first["follow_up_at"] and not first["follow_up_due"] and first["by_name"] == "عون صفاقس"
    pending = (await client.get(f"{URL}/follow-ups", params={"incident_id": incident_id}, headers=room)).json()
    assert [c["id"] for c in pending] == [first["id"]]
    answered = {
        "official_id": second,
        "number": "74 000 198",
        "via": "manual",
        "result": "answered",
        "asked": "تأمين الطوق وتحويل المرور",
        "promised": "دورية في الطريق",
        "eta_min": 10,
        "note": "يتصل بالقاعة عند الوصول",
    }
    r = await client.post(f"{URL}/incidents/{incident_id}/parties/{pid}/calls", json=answered, headers=room)
    assert r.status_code == 201 and r.json()["official_name"] == "ر. س."
    r = await client.post(f"{URL}/calls/{first['id']}/follow-up-done", headers=room)
    assert r.status_code == 200 and r.json()["follow_up_done_at"]
    assert (await client.get(f"{URL}/follow-ups", params={"incident_id": incident_id}, headers=room)).json() == []
    # A softphone call that the platform does not know is refused.
    soft = {**answered, "via": "softphone", "telephony_call_id": str(uuid.uuid4())}
    r = await client.post(f"{URL}/incidents/{incident_id}/parties/{pid}/calls", json=soft, headers=room)
    assert r.status_code == 404 and r.json()["detail"] == "telephony_call_not_found"

    view = (await client.get(f"{URL}/incidents/{incident_id}", headers=room)).json()
    party = next(p for p in view["parties"] if p["id"] == pid)
    assert party["last_result"] == "answered" and len(party["calls"]) == 2 and party["official_name"] == "ر. س."
    # A party once called stays in the report; one chosen by mistake is removed.
    r = await client.delete(f"{URL}/incidents/{incident_id}/parties/{pid}", headers=room)
    assert r.status_code == 409 and r.json()["detail"] == "party_called"
    other = parties[missing["id"]]["id"]
    r = await client.delete(f"{URL}/incidents/{incident_id}/parties/{other}", headers=room)
    assert r.status_code == 200 and [p["id"] for p in r.json()["parties"]] == [pid]

    # The history of the reports keeps the bodies informed with their last result; the log keeps the calls.
    rows = (await client.get(f"{URL}/history", headers=room)).json()
    row = next(h for h in rows if h["incident_id"] == incident_id)
    assert row["level"] == 2 and row["parties"][0]["body_name"] == police["name"]
    assert row["parties"][0]["last_result"] == "answered" and row["parties"][0]["calls"] == 2
    log = (await client.get(f"{URL}/calls", params={"incident_id": incident_id}, headers=room)).json()
    assert [c["result"] for c in log] == ["answered", "no_answer"] and log[0]["incident_category"] == "fire"

    # The next fire: the picker offers the engine's bodies, the police used before and the reports' history.
    later, _ = await new_incident(client, staff, _place())
    picker = (await client.get(f"{URL}/incidents/{later}/picker", headers=room)).json()
    assert any(u["body_id"] == police["id"] for u in picker["used_before"])
    assert incident_id in {h["incident_id"] for h in picker["history"]}
    assert later not in {h["incident_id"] for h in picker["history"]}

    # Another regional room reads nothing of this report; the central room reads it all.
    assert (await client.get(f"{URL}/incidents/{incident_id}", headers=staff(["operator"], TUNIS))).status_code in (
        403,
        404,
    )
    tunis_history = (await client.get(f"{URL}/history", headers=staff(["operator"], TUNIS))).json()
    assert incident_id not in {h["incident_id"] for h in tunis_history}
    central = (await client.get(f"{URL}/incidents/{incident_id}", headers=staff(["operator"], None))).json()
    assert [p["id"] for p in central["parties"]] == [pid]


async def test_the_central_room_adds_a_missing_body_from_a_report(client: httpx.AsyncClient, staff: Staff) -> None:
    central = staff(["operator"], None, name="عون القاعة المركزية")
    incident_id, _ = await new_incident(client, staff, _place())
    # The missing body belongs to the report's gouvernorat: its regional room keeps it from now on.
    body = await _body(client, central, gouvernorat_code=SFAX, origin_incident_id=incident_id)
    assert body["gouvernorat_code"] == SFAX and not body["editable"]
    sfax = (await client.get(f"{URL}/bodies/{body['id']}", headers=staff(["operator"], SFAX))).json()
    assert sfax["editable"] and sfax["created_by_name"] == "عون القاعة المركزية"
    r = await client.post(
        f"{URL}/incidents/{incident_id}/parties", json={"parties": [{"body_id": body["id"]}]}, headers=central
    )
    assert r.status_code == 200 and r.json()["level"]["level"] == 2
    # The internal bodies: the central room is suggested when the priority is high.
    view = (await client.get(f"{URL}/incidents/{incident_id}", headers=central)).json()
    assert all(s["kind"] in ("internal", "external") for s in view["suggestions"])
