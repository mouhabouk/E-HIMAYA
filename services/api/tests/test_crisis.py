"""Disaster and crisis axes (phase L3, docs/phase-l/design-l3.md): the declaration request and its decision, the
interventions an axis suggests and attaching them, figures computed from the interventions, shelters, evacuations
and needs, escalation to a national axis, signed recommendations and decisions with the minister's override, the
executing room's status, situation reports, closing with a memory draft, and who sees what (governor of another
gouvernorat, governor and the sensitive layers, operators proposing)."""

import base64
import hashlib
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import Principal, Realm
from app.modules.crisis import domain, service
from app.modules.crisis.models import Axis
from app.modules.layers import access

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/staff/crisis"
NABEUL, SOUSSE = 21, 51
TEST_KEY = base64.b64encode(hashlib.sha256(b"e-himaya crisis test key").digest()).decode()
# A square around Nabeul town (lon, lat).
AREA = {
    "type": "Polygon",
    "coordinates": [[[10.60, 36.35], [10.85, 36.35], [10.85, 36.55], [10.60, 36.55], [10.60, 36.35]]],
}


@pytest.fixture(autouse=True)
def _key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "evidence_signing_key", SecretStr(TEST_KEY))


def commander(staff: Staff) -> dict[str, str]:
    return staff(["ops_manager"], gouvernorat=None)


def room(staff: Staff, code: int = NABEUL) -> dict[str, str]:
    return staff(["ops_manager"], gouvernorat=code)


def governor(staff: Staff, code: int = NABEUL) -> dict[str, str]:
    return staff(["governor"], gouvernorat=code)


def minister(staff: Staff) -> dict[str, str]:
    return staff(["minister"], gouvernorat=None)


async def incident(
    session: AsyncSession,
    *,
    code: int = NABEUL,
    lat: float = 36.45,
    lon: float = 10.73,
    category: str = "flood",
    **counts: int,
) -> str:
    incident_id = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO ops.incident (id, category, severity, centroid, gouvernorat_code, title) "
            "VALUES (:id, :c, 4, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :g, 'حي الوفاء، فيضان منزل')"
        ),
        {"id": incident_id, "c": category, "lon": lon, "lat": lat, "g": code},
    )
    if counts:
        await session.execute(
            text(
                "INSERT INTO ops.casualty_count (incident_id, deceased, injured_light, rescued) "
                "VALUES (:id, :d, :i, :r)"
            ),
            {
                "id": incident_id,
                "d": counts.get("deceased", 0),
                "i": counts.get("injured", 0),
                "r": counts.get("rescued", 0),
            },
        )
    await session.commit()
    return str(incident_id)


async def open_regional(client: httpx.AsyncClient, staff: Staff, **extra: Any) -> dict[str, Any]:
    body = {"name": "فيضانات نابل، أكتوبر 2026", "kind": "flood", "level": 3, "gouvernorat_code": NABEUL, "area": AREA}
    response = await client.post(f"{URL}/axes", json={**body, **extra}, headers=commander(staff))
    assert response.status_code == 201, response.text
    return response.json()


# --- Pure rules -----------------------------------------------------------------------------------------------------


def test_rules() -> None:
    def p(roles: set[str], code: int | None) -> Principal:
        return Principal(subject="s", realm=Realm.STAFF, roles=frozenset(roles), gouvernorat_code=code, claims={})  # type: ignore[arg-type]

    assert domain.is_commander(p({"ops_manager"}, None)) and not domain.is_commander(p({"ops_manager"}, NABEUL))
    assert domain.can_issue(p({"governor"}, NABEUL), NABEUL) and not domain.can_issue(p({"governor"}, NABEUL), SOUSSE)
    assert domain.can_issue(p({"minister"}, None), SOUSSE) and domain.can_issue(p({"minister"}, None), None)
    assert not domain.can_issue(p({"governor"}, NABEUL), None)
    assert domain.can_update_directive(p({"operator"}, NABEUL), "regional", NABEUL)
    assert not domain.can_update_directive(p({"operator"}, NABEUL), "central", NABEUL)
    assert domain.sitrep_period(None, 4) == timedelta(hours=2)
    assert domain.axis_number(2026, 7) == "AX-2026-007"
    assert domain.compatible("flood", "drowning") and not domain.compatible("forest_fire", "flood")
    earlier = [
        domain.Issued("a", "decision", "evacuation", "governor", "issued", False),
        domain.Issued("b", "decision", "evacuation", "governor", "done", False),
        domain.Issued("c", "recommendation", "evacuation", "governor", "issued", False),
        domain.Issued("d", "decision", "closure", "governor", "issued", False),
    ]
    assert domain.overridden_by_minister("decision", "evacuation", "minister", earlier) == ["a"]
    assert domain.overridden_by_minister("decision", "evacuation", "governor", earlier) == []
    # The governor never sees the sensitive layers; the minister does.
    assert not access.is_minister(p({"governor"}, NABEUL)) and access.is_minister(p({"minister"}, None))


# --- Life cycle -----------------------------------------------------------------------------------------------------


async def test_request_accept_suggest_attach_and_figures(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession
) -> None:
    inside = await incident(session, deceased=1, injured=3, rescued=12)
    outside = await incident(session, lat=36.90, lon=10.90)  # in Nabeul, outside the area
    fire = await incident(session, category="fire", lat=36.46, lon=10.74)  # inside, but a fire still fits "other" only
    request = await client.post(
        f"{URL}/requests",
        json={
            "name": "فيضانات نابل، أكتوبر 2026",
            "kind": "flood",
            "level": 3,
            "facts": "أمطار غزيرة وفيضان الأودية",
            "area": AREA,
        },
        headers=room(staff),
    )
    assert request.status_code == 201, request.text
    # The regional room cannot decide; the commander sees the request and accepts it.
    assert (
        await client.post(f"{URL}/requests/{request.json()['id']}/decide", json={"accept": True}, headers=room(staff))
    ).status_code == 403
    pending = (await client.get(f"{URL}/requests", headers=commander(staff))).json()["items"]
    assert request.json()["id"] in [r["id"] for r in pending]
    decided = await client.post(
        f"{URL}/requests/{request.json()['id']}/decide", json={"accept": True}, headers=commander(staff)
    )
    assert decided.status_code == 200 and decided.json()["status"] == "accepted"
    axis_id = decided.json()["axis_id"]

    suggested = (await client.get(f"{URL}/axes/{axis_id}/suggestions", headers=room(staff))).json()["items"]
    ids = {i["id"] for i in suggested}
    assert inside in ids and outside not in ids and fire not in ids
    # An operator proposes, the regional manager attaches.
    assert (
        await client.post(
            f"{URL}/axes/{axis_id}/incidents",
            json={"incident_id": inside},
            headers=staff(["operator"], gouvernorat=NABEUL),
        )
    ).status_code == 204
    assert (await client.get(f"{URL}/axes/{axis_id}", headers=room(staff))).json()["axis"]["figures"]["incidents"] == 0
    assert (
        await client.post(f"{URL}/axes/{axis_id}/incidents", json={"incident_id": inside}, headers=room(staff))
    ).status_code == 204
    detail = (await client.get(f"{URL}/axes/{axis_id}", headers=room(staff))).json()
    f = detail["axis"]["figures"]
    assert (f["incidents"], f["deceased"], f["injured"], f["rescued"]) == (1, 1, 3, 12)
    assert any(e["kind"] == "incident_proposed" for e in detail["timeline"])
    assert detail["incidents"][0]["title"]  # the room reads the title

    # Shelters, evacuations, needs.
    shelter = await client.post(
        f"{URL}/axes/{axis_id}/shelters",
        json={"name": "معهد نابل", "capacity": 300, "occupants": 120, "location": {"lat": 36.45, "lon": 10.73}},
        headers=room(staff),
    )
    assert shelter.status_code == 201, shelter.text
    assert (
        await client.patch(
            f"{URL}/axes/{axis_id}/shelters/{shelter.json()['id']}", json={"occupants": 400}, headers=room(staff)
        )
    ).status_code == 422
    assert (
        await client.post(
            f"{URL}/axes/{axis_id}/evacuations",
            json={"name": "حي الوفاء", "evacuated": 85, "area": AREA},
            headers=room(staff),
        )
    ).status_code == 201
    need = await client.post(
        f"{URL}/axes/{axis_id}/needs", json={"label": "مضخات شفط", "quantity": 3}, headers=room(staff)
    )
    assert need.status_code == 201
    # Another gouvernorat's room sees nothing.
    assert (await client.get(f"{URL}/axes/{axis_id}", headers=room(staff, SOUSSE))).status_code == 404

    # The governor of Nabeul reads the axis without titles or names; the governor of Sousse does not see it.
    seen = (await client.get(f"{URL}/axes/{axis_id}", headers=governor(staff))).json()
    assert seen["axis"]["figures"]["evacuated"] == 85 and seen["axis"]["figures"]["sheltered"] == 120
    assert seen["incidents"][0]["title"] is None and seen["axis"]["opened_by_name"] is None
    assert all(e["actor_name"] is None for e in seen["timeline"])
    assert (await client.get(f"{URL}/axes/{axis_id}", headers=governor(staff, SOUSSE))).status_code == 404
    listed = (await client.get(f"{URL}/axes", headers=governor(staff, SOUSSE))).json()["items"]
    assert axis_id not in [a["id"] for a in listed]
    # Governors and ministers do not reach the reports and interventions lists.
    assert (await client.get("/api/v1/staff/incidents", headers=governor(staff))).status_code == 403


async def test_directives_signed_override_and_status(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession
) -> None:
    axis = await open_regional(client, staff)
    axis_id = axis["id"]
    due = (datetime.now(UTC) + timedelta(hours=3)).isoformat()
    body = {
        "kind": "decision",
        "category": "evacuation",
        "body": "إخلاء حي الوفاء فورا",
        "executor": "regional",
        "due_at": due,
    }
    # The room cannot issue; the governor of Sousse cannot issue on Nabeul.
    assert (await client.post(f"{URL}/axes/{axis_id}/directives", json=body, headers=room(staff))).status_code == 403
    assert (
        await client.post(f"{URL}/axes/{axis_id}/directives", json=body, headers=governor(staff, SOUSSE))
    ).status_code == 404
    first = await client.post(f"{URL}/axes/{axis_id}/directives", json=body, headers=governor(staff))
    assert first.status_code == 201, first.text
    d = first.json()
    assert d["issuer_role"] == "governor" and d["number"] == 1 and d["signature"] and d["key_id"]
    # The signature verifies against the server key over the canonical payload.
    key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(TEST_KEY))
    row = (
        await session.execute(
            text("SELECT issued_by, issued_at, due_at FROM crisis.directive WHERE id = :id"), {"id": d["id"]}
        )
    ).one()
    payload = domain.signed_payload(
        directive_id=d["id"], axis_number=axis["number"], number=1, kind="decision", category="evacuation",
        body=body["body"], executor="regional", executor_name=None, due_at=row.due_at, issuer_role="governor",
        issued_by=row.issued_by, issued_at=row.issued_at,
    )  # fmt: skip
    key.public_key().verify(base64.b64decode(d["signature"]), payload)

    # The minister's decision of the same category overrides the governor's.
    second = await client.post(
        f"{URL}/axes/{axis_id}/directives",
        json={**body, "body": "إخلاء الأحياء المنخفضة كلها"},
        headers=minister(staff),
    )
    assert second.status_code == 201 and second.json()["issuer_role"] == "minister"
    detail = (await client.get(f"{URL}/axes/{axis_id}", headers=room(staff))).json()
    by_id = {x["id"]: x for x in detail["directives"]}
    assert by_id[d["id"]]["overridden_by"] == second.json()["id"] and not by_id[d["id"]]["can_update"]
    assert (
        await client.post(f"{URL}/directives/{d['id']}/status", json={"status": "received"}, headers=room(staff))
    ).status_code == 409

    # The executing room updates the status; "failed" needs a reason; the governor cannot update.
    target = second.json()["id"]
    assert (
        await client.post(f"{URL}/directives/{target}/status", json={"status": "received"}, headers=governor(staff))
    ).status_code == 403
    assert (
        await client.post(
            f"{URL}/directives/{target}/status",
            json={"status": "received"},
            headers=staff(["operator"], gouvernorat=NABEUL),
        )
    ).status_code == 200
    assert (
        await client.post(f"{URL}/directives/{target}/status", json={"status": "failed"}, headers=room(staff))
    ).status_code == 422
    done = await client.post(f"{URL}/directives/{target}/status", json={"status": "done"}, headers=room(staff))
    assert (
        done.status_code == 200
        and done.json()["done_at"]
        and [e["status"] for e in done.json()["events"]] == ["issued", "received", "done"]
    )
    figures = (await client.get(f"{URL}/axes/{axis_id}", headers=minister(staff))).json()["axis"]["figures"]
    assert (figures["decisions"], figures["decisions_done"], figures["done_share"]) == (1, 1, 1.0)
    # A partner executor needs a name; a deadline in the past is refused.
    assert (
        await client.post(
            f"{URL}/axes/{axis_id}/directives", json={**body, "executor": "partner"}, headers=minister(staff)
        )
    ).status_code == 422
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    assert (
        await client.post(f"{URL}/axes/{axis_id}/directives", json={**body, "due_at": past}, headers=minister(staff))
    ).status_code == 422


async def test_escalate_sitrep_worker_and_close(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    axis = await open_regional(client, staff, level=4)
    axis_id = axis["id"]
    attached = await incident(session, deceased=2)
    assert (
        await client.post(f"{URL}/axes/{axis_id}/incidents", json={"incident_id": attached}, headers=room(staff))
    ).status_code == 204
    # Only the commander escalates.
    assert (
        await client.post(
            f"{URL}/axes/{axis_id}/escalate",
            json={"gouvernorats": [SOUSSE], "reason": "امتداد الفيضانات"},
            headers=room(staff),
        )
    ).status_code == 403
    root = await client.post(
        f"{URL}/axes/{axis_id}/escalate",
        json={"gouvernorats": [SOUSSE], "reason": "امتداد الفيضانات"},
        headers=commander(staff),
    )
    assert root.status_code == 200, root.text
    r = root.json()
    assert r["scope"] == "national" and r["gouvernorats"] == [NABEUL, SOUSSE] and r["figures"]["deceased"] == 2
    assert {c["gouvernorat_code"] for c in r["children"]} == {NABEUL, SOUSSE}
    # The governor of Sousse now sees the root and the Sousse sub-axis, not Nabeul's.
    seen = (await client.get(f"{URL}/axes/{r['id']}", headers=governor(staff, SOUSSE))).json()
    assert [c["gouvernorat_code"] for c in seen["axis"]["children"]] == [SOUSSE]
    # A governor cannot issue on the national root, the minister can.
    body = {"kind": "recommendation", "category": "support", "body": "طلب دعم من الجيش", "executor": "central"}
    assert (
        await client.post(f"{URL}/axes/{r['id']}/directives", json=body, headers=governor(staff))
    ).status_code == 403
    assert (
        await client.post(f"{URL}/axes/{r['id']}/directives", json=body, headers=minister(staff))
    ).status_code == 201

    # The worker drafts a situation report when one is due; the commander sends it with an assessment.
    await session.execute(
        text("UPDATE crisis.axis SET next_sitrep_at = now() - interval '1 minute' WHERE id = :id"), {"id": r["id"]}
    )
    await session.commit()
    result = await service.tick(session)
    await session.commit()
    assert result["sitreps"] >= 1
    sitreps = (await client.get(f"{URL}/axes/{r['id']}", headers=commander(staff))).json()["sitreps"]
    draft = next(s for s in sitreps if s["axis_id"] == r["id"] and s["status"] == "draft")
    # The minister does not read drafts.
    assert draft["id"] not in [
        s["id"] for s in (await client.get(f"{URL}/axes/{r['id']}", headers=minister(staff))).json()["sitreps"]
    ]
    sent = await client.post(
        f"{URL}/sitreps/{draft['id']}/send", json={"assessment": "الوضع تحت السيطرة جزئيا"}, headers=commander(staff)
    )
    assert sent.status_code == 200 and sent.json()["status"] == "sent"
    assert draft["id"] in [
        s["id"] for s in (await client.get(f"{URL}/axes/{r['id']}", headers=minister(staff))).json()["sitreps"]
    ]

    # The command overview: the minister ranks gouvernorats; the governor of Nabeul sees his only.
    overview = (await client.get(f"{URL}/command", headers=minister(staff))).json()
    assert overview["role"] == "minister" and {g["code"] for g in overview["gouvernorats"]} >= {NABEUL, SOUSSE}
    mine = (await client.get(f"{URL}/command", headers=governor(staff))).json()
    assert mine["role"] == "governor" and {g["code"] for g in mine["gouvernorats"]} == {NABEUL}
    assert (await client.get(f"{URL}/boundaries", headers=minister(staff))).json()["features"]

    # Closing: the national root only, by the commander, with figures and a memory draft.
    assert (
        await client.post(
            f"{URL}/axes/{axis_id}/close", json={"summary": "انتهت الأزمة وعادت المياه"}, headers=commander(staff)
        )
    ).status_code == 409
    closed = await client.post(
        f"{URL}/axes/{r['id']}/close", json={"summary": "انتهت الأزمة وعادت المياه"}, headers=commander(staff)
    )
    assert closed.status_code == 200, closed.text
    c = closed.json()
    assert c["status"] == "closed" and c["closing"]["deceased"] == 2 and c["memory_id"]
    assert all(child["status"] == "closed" for child in c["children"])
    memory = await client.get(f"/api/v1/staff/memory/{c['memory_id']}", headers=commander(staff))
    assert memory.status_code == 200 and memory.json()["status"] == "draft"


async def test_directive_deadline_reminder_and_overdue(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession
) -> None:
    axis = await open_regional(client, staff)
    due = (datetime.now(UTC) + timedelta(minutes=30)).isoformat()
    body = {
        "kind": "decision",
        "category": "closure",
        "body": "غلق الطريق الجهوية 27",
        "executor": "regional",
        "due_at": due,
    }
    d = (await client.post(f"{URL}/axes/{axis['id']}/directives", json=body, headers=governor(staff))).json()
    await service.tick(session)
    await session.commit()
    row = (
        await session.execute(
            text("SELECT reminded_at, overdue_at FROM crisis.directive WHERE id = :id"), {"id": d["id"]}
        )
    ).one()
    assert row.reminded_at is not None and row.overdue_at is None
    await session.execute(
        text("UPDATE crisis.directive SET due_at = now() - interval '1 minute' WHERE id = :id"), {"id": d["id"]}
    )
    await session.commit()
    await service.tick(session)
    await session.commit()
    detail = (await client.get(f"{URL}/axes/{axis['id']}", headers=governor(staff))).json()
    assert next(x for x in detail["directives"] if x["id"] == d["id"])["overdue"]
    assert any(e["kind"] == "directive_overdue" for e in detail["timeline"])


async def test_rls_keeps_axes_in_their_gouvernorat(
    session: AsyncSession, client: httpx.AsyncClient, staff: Staff
) -> None:
    axis = await open_regional(client, staff)
    from app.core.db import DbScope, get_engine, make_sessionmaker

    regional = make_sessionmaker(get_engine(), scope=DbScope.staff(gouvernorat_code=SOUSSE, subject="t"))
    async with regional() as s:
        assert await s.get(Axis, uuid.UUID(axis["id"])) is None
    nabeul = make_sessionmaker(get_engine(), scope=DbScope.staff(gouvernorat_code=NABEUL, subject="t"))
    async with nabeul() as s:
        assert await s.get(Axis, uuid.UUID(axis["id"])) is not None


def test_live_route() -> None:
    from app.modules.reports.live import _route

    routed = _route("axis.opened", {"axis": {}, "gouvernorat_codes": [NABEUL]})
    assert routed is not None and routed[0] == "crisis"


async def test_disaster_map_for_the_committees(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    """Phase N (docs/phase-n/design-n.md §3): the disaster view shows the places of the chosen disasters only, to the
    rooms and to the committees, each in its gouvernorat."""
    inside = await incident(session, deceased=1, rescued=4)
    elsewhere = await incident(session, lat=36.90, lon=10.90)  # not attached: never on the disaster map
    nabeul = await open_regional(client, staff, incident_ids=[inside])
    sousse = await open_regional(
        client, staff, name="حرائق سوسة، أكتوبر 2026", kind="forest_fire", gouvernorat_code=SOUSSE
    )
    both = {"axis": f"{nabeul['id']},{sousse['id']}"}

    national = await client.get(
        f"{URL}/disasters/map", params=both, headers=staff(["central_committee"], gouvernorat=None)
    )
    assert national.status_code == 200, national.text
    body = national.json()
    assert {a["id"] for a in body["areas"]} == {nabeul["id"], sousse["id"]}
    assert [i["id"] for i in body["incidents"]] == [inside] and elsewhere not in str(body)
    assert body["figures"]["deceased"] == 1 and body["figures"]["rescued"] == 4

    # The regional committee of Sousse: its own disaster, not Nabeul's (row-level security).
    regional = await client.get(
        f"{URL}/disasters/map", params=both, headers=staff(["local_committee"], gouvernorat=SOUSSE)
    )
    assert regional.status_code == 200 and {a["id"] for a in regional.json()["areas"]} == {sousse["id"]}
    assert regional.json()["incidents"] == []
    # The committees read the disasters but act on none of them.
    assert (await client.get(f"{URL}/axes", headers=staff(["local_committee"], gouvernorat=SOUSSE))).status_code == 200
    assert (
        await client.post(
            f"{URL}/axes/{sousse['id']}/close",
            json={"summary": "انتهت الحرائق"},
            headers=staff(["central_committee"], gouvernorat=None),
        )
    ).status_code == 403
    assert (
        await client.get(f"{URL}/disasters/map", params=both, headers=staff(["doctor"], gouvernorat=NABEUL))
    ).status_code == 403
    assert (await client.get(f"{URL}/disasters/map", headers=commander(staff))).status_code == 422
    bad = await client.get(f"{URL}/disasters/map", params={"axis": "x"}, headers=commander(staff))
    assert bad.status_code == 422 and bad.json()["detail"] == "invalid_selection"
