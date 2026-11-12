# covers: I1
"""Periodic inspections, phase I1 (docs/phase-i/design-i.md): the inspector registers from the app, the inspector
general activates the account and the code leaves by SMS, the phone activates itself; a mission order names a unit by
its gouvernorat, kind and name, or an operations room; the report is scored by the server, sealed once sent and sent
once; only the inspections of the rooms reach the rooms (Yamen 2026-11-11), a regional room its own, the central room
every room's; the system administrator alone deletes and restores."""

import base64
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import field_tokens
from app.core.db import get_system_sessionmaker
from app.modules.inspections import domain, service
from app.modules.notify.models import Outbox
from tests.conftest import bearer

STAFF = "/api/v1/staff/inspections"
ROOMS = "/api/v1/staff/inspection-results"
ADMIN = "/api/v1/staff/inspection-admin"
APP = "/api/v1/inspect"
SFAX = 61
PNG = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64).decode()


def general(staff: Any) -> dict[str, str]:
    return staff(["inspector_general"], None)


def matricule() -> str:
    return f"I{secrets.randbelow(10**8):08d}"


class Inspector:
    """An inspector who registered from the app, was activated by the inspector general and activated the phone."""

    def __init__(self, client: httpx.AsyncClient, staff: Any, session: AsyncSession, kind: str = "internal") -> None:
        self.client, self.staff, self.session, self.kind = client, staff, session, kind
        self.matricule = matricule()
        self.phone = f"+216 98 {secrets.randbelow(10**6):06d}"
        self.id = ""
        self.tokens: dict[str, Any] = {}

    async def register(self) -> httpx.Response:
        body: dict[str, Any] = {
            "kind": self.kind,
            "matricule": self.matricule,
            "name": "سامي التفقّدي",
            "phone": self.phone,
            "via": "sms",
            "device_model": "Galaxy A55",
        }
        if self.kind == "external":
            body["organisation"] = "هيئة الرقابة"
        return await self.client.post(f"{APP}/register", json=body)

    async def find(self) -> dict[str, Any]:
        rows = (await self.client.get(f"{STAFF}/inspectors", headers=general(self.staff))).json()
        return next(r for r in rows if r["matricule"] == self.matricule)

    async def code(self) -> str:
        row = await self.session.scalar(
            select(Outbox)
            .where(Outbox.channel == "sms", Outbox.address == self.phone)
            .order_by(Outbox.id.desc())
            .limit(1)
        )
        assert row is not None and row.payload["secret"] is True
        return str(row.payload["text"]).split("التفقّد ")[1].split(".")[0]

    async def activate_phone(self, code: str | None = None) -> httpx.Response:
        return await self.client.post(
            f"{APP}/activate",
            json={
                "matricule": self.matricule,
                "code": code or await self.code(),
                "device": {"platform": "android", "model": "Galaxy A55"},
            },
        )

    async def ready(self) -> "Inspector":
        assert (await self.register()).status_code == 201
        return await self.ready_registered()

    async def ready_registered(self) -> "Inspector":
        self.id = (await self.find())["id"]
        body = {"expires_on": str(service.today() + timedelta(days=30))} if self.kind == "external" else {}
        r = await self.client.post(f"{STAFF}/inspectors/{self.id}/activate", json=body, headers=general(self.staff))
        assert r.status_code == 200, r.text
        r = await self.activate_phone()
        assert r.status_code == 200, r.text
        self.tokens = r.json()
        return self

    @property
    def h(self) -> dict[str, str]:
        return bearer(self.tokens["access_token"])


def unit_site(name: str, kind: str = "centre", gouvernorat: int = SFAX) -> dict[str, Any]:
    return {"target": "unit", "gouvernorat_code": gouvernorat, "unit_kind": kind, "unit_name": name}


def room_site(room: str, gouvernorat: int | None = None) -> dict[str, Any]:
    return {"target": "room", "room": room, "gouvernorat_code": gouvernorat}


async def plan(client: httpx.AsyncClient, staff: Any, inspector: Inspector, *sites: dict[str, Any]) -> dict[str, Any]:
    r = await client.post(
        f"{STAFF}/missions",
        json={
            "on_date": str(service.today()),
            "at_time": "09:00",
            "kind": "surprise",
            "inspector_id": inspector.id,
            "sites": list(sites),
            "publish": True,
        },
        headers=general(staff),
    )
    assert r.status_code == 201, r.text
    return dict(r.json())


async def inspect(
    client: httpx.AsyncClient, inspector: Inspector, site_id: str, **overrides: Any
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Start, answer every item well, and send the report of one site."""
    r = await client.post(
        f"{APP}/inspections", json={"site_id": site_id, "lat": 34.74, "lon": 10.76}, headers=inspector.h
    )
    assert r.status_code == 200, r.text
    report = r.json()
    answers = {item["key"]: "ok" for item in report["profile"]["items"]}
    body: dict[str, Any] = {
        "client_id": str(uuid.uuid4()),
        "answers": answers,
        "present": 10,
        "expected": 10,
        "exit_seconds": 90,
        "summary": "[SIM] وحدة جاهزة",
        "head_name": "رئيس الوحدة",
        "inspector_signature": PNG,
        "head_signature": PNG,
        "signed_at": datetime.now(UTC).isoformat(),
        "recommendations": [
            {"kind": "detailed", "item_key": "p0", "text": "[SIM] تحيين قائمة المناوبة", "priority": "high"},
            {"kind": "detailed", "item_key": "r0", "text": "[SIM] صيانة المضخّة", "priority": "low"},
            {"kind": "general", "text": "[SIM] توصية عامّة"},
        ],
    } | overrides
    r = await client.post(f"{APP}/inspections/{report['id']}/submit", json=body, headers=inspector.h)
    assert r.status_code == 200, r.text
    return report, {**r.json(), "body": body}


# ---------------------------------------------------------------- the model


def test_the_default_model_scores_as_the_prototype() -> None:
    config = {
        "axes": [{"key": "p", "weight": 35}, {"key": "r", "weight": 40}],
        "items": [{"key": "p0", "axis": "p", "weight": 35}, {"key": "r0", "axis": "r", "weight": 40}],
        "values": {"ok": 100, "note": 60, "ko": 20},
        "weights": {"items": 75, "presence": 15, "exit": 10},
        "exit": {"fast": 120, "ok": 180, "fast_value": 100, "ok_value": 75, "slow_value": 50},
        "levels": [{"name": "جاهز", "min": 85}, {"name": "جاهز بتحفّظ", "min": 70}, {"name": "غير جاهز", "min": 0}],
    }
    assert domain.score(config, {"p0": "ok", "r0": "ok"}, 10, 10, 90) == 100
    # Items 100*35+20*40 / 75 = 57.3; presence 50; exit 75 -> (57.3*75 + 50*15 + 75*10) / 100 = 58.
    assert domain.score(config, {"p0": "ok", "r0": "ko"}, 5, 10, 150) == 58
    # No exercise: its weight goes to the items.
    assert domain.score(config, {"p0": "ok", "r0": "ok"}, 10, 10, None) == 100
    assert domain.verdict(config, 86) == "جاهز"
    assert domain.verdict(config, 70) == "جاهز بتحفّظ"
    assert domain.verdict(config, 10) == "غير جاهز"


async def test_a_model_whose_weights_do_not_add_up_is_refused(client: httpx.AsyncClient, staff: Any) -> None:
    current = (await client.get(f"{STAFF}/profile", headers=general(staff))).json()
    config = current["config"]
    config["weights"]["exit"] += 5
    r = await client.put(f"{STAFF}/profile", json={"name": "[SIM] خاطئ", "config": config}, headers=general(staff))
    assert r.status_code == 422
    assert r.json()["detail"] == "weights_invalid"
    # The operations rooms never reach the settings.
    assert (await client.get(f"{STAFF}/profile", headers=staff(["operator"], None))).status_code == 403


# ---------------------------------------------------------------- the accounts


async def test_register_activate_and_the_code_by_sms(
    client: httpx.AsyncClient, staff: Any, session: AsyncSession
) -> None:
    inspector = Inspector(client, staff, session)
    r = await inspector.register()
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "pending"
    assert inspector.phone[-3:] in r.json()["destination"] and "•" in r.json()["destination"]
    assert (await inspector.register()).status_code == 409
    row = await inspector.find()
    assert row["status"] == "pending"
    inspector.id = row["id"]
    # An account not activated has no code yet.
    assert (await inspector.activate_phone("ABCD-EFGH")).status_code == 401
    r = await client.post(f"{STAFF}/inspectors/{inspector.id}/activate", json={}, headers=general(staff))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "code_sent"
    code = await inspector.code()
    assert len(code.replace("-", "")) == 8
    r = await inspector.activate_phone()
    assert r.status_code == 200, r.text
    tokens = r.json()
    # The code is single use.
    assert (await inspector.activate_phone(code)).status_code == 401
    r = await client.post(f"{APP}/token", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200, r.text
    assert (await client.get(f"{APP}/missions", headers=bearer(r.json()["access_token"]))).status_code == 200
    assert (await inspector.find())["status"] == "active"


async def test_the_sms_leaves_and_its_code_is_wiped(
    client: httpx.AsyncClient, staff: Any, session: AsyncSession, channels: Any
) -> None:
    from app.modules.notify import delivery

    inspector = Inspector(client, staff, session)
    await inspector.register()
    inspector.id = (await inspector.find())["id"]
    await client.post(f"{STAFF}/inspectors/{inspector.id}/activate", json={}, headers=general(staff))
    code = await inspector.code()
    while await delivery.run_outbox(get_system_sessionmaker()):
        pass
    assert any(sent[0] == inspector.phone and code in sent[1] for sent in channels.sms.sent)
    session.expire_all()
    row = await session.scalar(select(Outbox).where(Outbox.address == inspector.phone).order_by(Outbox.id.desc()))
    assert row is not None and row.status == "sent"
    assert code not in str(row.payload)


async def test_an_external_inspector_needs_an_end_date_and_a_lost_phone_ends_the_session(
    client: httpx.AsyncClient, staff: Any, session: AsyncSession
) -> None:
    inspector = Inspector(client, staff, session, kind="external")
    await inspector.register()
    inspector.id = (await inspector.find())["id"]
    r = await client.post(f"{STAFF}/inspectors/{inspector.id}/activate", json={}, headers=general(staff))
    assert r.status_code == 422
    await inspector.ready_registered()
    tokens = inspector.tokens
    assert tokens["kind"] == "external"
    r = await client.post(f"{STAFF}/inspectors/{inspector.id}/lost", headers=general(staff))
    assert r.status_code == 200
    assert r.json()["status"] == "blocked"
    assert (await client.get(f"{APP}/missions", headers=inspector.h)).status_code in (401, 410)
    assert (await client.post(f"{APP}/token", json={"refresh_token": tokens["refresh_token"]})).status_code == 401


async def test_a_platform_token_never_carries_a_staff_role(client: httpx.AsyncClient) -> None:
    token, _ = field_tokens.issue(
        subject=f"insp:{uuid.uuid4()}",
        name="x",
        username="x",
        roles=["sysadmin", "inspector_general"],
        gouvernorat_code=None,
        device_id=str(uuid.uuid4()),
    )
    assert (await client.get(f"{ADMIN}/bin", headers=bearer(token))).status_code == 403
    assert (await client.get(f"{STAFF}/dashboard", headers=bearer(token))).status_code == 403


# ---------------------------------------------------------------- missions and reports


async def test_a_unit_is_named_by_gouvernorat_kind_and_name(
    client: httpx.AsyncClient, staff: Any, session: AsyncSession
) -> None:
    inspector = await Inspector(client, staff, session).ready()
    name = f"[SIM] ساقية الزيت {secrets.token_hex(3)}"
    mission = await plan(client, staff, inspector, unit_site(name, "advanced_centre"), room_site("regional", SFAX))
    assert mission["ref"].startswith(f"OM-{service.today().year}-")
    unit, room = mission["sites"]
    assert unit["unit_kind"] == "advanced_centre" and unit["unit_name"] == name
    assert unit["name"] == f"مركز مقدّم {name}"
    assert room["name"].startswith("القاعة الجهوية للعمليات")
    # The same unit twice in one order, a unit without its kind, a regional room without its gouvernorat.
    for sites in (
        [unit_site(name, "advanced_centre"), unit_site(f"  {name} ", "advanced_centre")],
        [{"target": "unit", "gouvernorat_code": SFAX, "unit_name": name}],
        [room_site("regional")],
    ):
        r = await client.post(
            f"{STAFF}/missions",
            json={
                "on_date": str(service.today()),
                "at_time": "10:00",
                "kind": "periodic",
                "inspector_id": inspector.id,
                "sites": sites,
            },
            headers=general(staff),
        )
        assert r.status_code == 422, (sites, r.text)
    mine = (await client.get(f"{APP}/missions", headers=inspector.h)).json()
    assert [m["ref"] for m in mine] == [mission["ref"]]
    # The model comes with the missions: the app opens a place's report without network.
    assert [i["key"] for i in mine[0]["profile"]["items"]]
    r = await client.get(f"/api/v1/verify/om/{mission['ref']}")
    assert r.status_code == 200
    assert r.json()["places"] == 2 and "unit_name" not in r.text


async def test_a_report_is_scored_sealed_and_sent_once(
    client: httpx.AsyncClient, staff: Any, session: AsyncSession
) -> None:
    inspector = await Inspector(client, staff, session).ready()
    mission = await plan(client, staff, inspector, unit_site(f"[SIM] مركز {secrets.token_hex(3)}"))
    site = mission["sites"][0]
    report, receipt = await inspect(client, inspector, site["id"])
    assert receipt["score"] == 100 and receipt["verdict"] == "جاهز"
    assert receipt["receipt"].startswith("T-")
    # The same send again (the app's queue after a lost answer) gives the same receipt; another is refused.
    again = await client.post(f"{APP}/inspections/{report['id']}/submit", json=receipt["body"], headers=inspector.h)
    assert again.status_code == 200 and again.json()["receipt"] == receipt["receipt"]
    other = receipt["body"] | {"client_id": str(uuid.uuid4())}
    assert (
        await client.post(f"{APP}/inspections/{report['id']}/submit", json=other, headers=inspector.h)
    ).status_code == 409
    assert (
        await client.put(f"{APP}/inspections/{report['id']}", json={"present": 1}, headers=inspector.h)
    ).status_code == 409
    # The database itself refuses to change a sealed report.
    with pytest.raises(Exception, match="inspection_sealed"):
        async with get_system_sessionmaker()() as fresh, fresh.begin():
            await fresh.execute(text("UPDATE insp.inspection SET score = 1 WHERE id = :id"), {"id": report["id"]})
    # A unit's report is never disclosed to a room, and its recommendations go to nobody.
    record = (await client.get(f"{STAFF}/records/{report['id']}", headers=general(staff))).json()
    assert record["disclosure"] == {}
    assert {x["audience"] for x in record["recommendations"]} == {"none"}
    r = await client.put(
        f"{STAFF}/records/{report['id']}/disclosure",
        json={"room": "central", "inspection": True},
        headers=general(staff),
    )
    assert r.status_code == 409
    # Another inspector never reaches this report.
    stranger = await Inspector(client, staff, session).ready()
    assert (
        await client.put(f"{APP}/inspections/{report['id']}", json={"present": 1}, headers=stranger.h)
    ).status_code == 404


# ---------------------------------------------------------------- the rooms


async def test_only_the_rooms_inspections_reach_the_rooms(
    client: httpx.AsyncClient, staff: Any, session: AsyncSession
) -> None:
    inspector = await Inspector(client, staff, session).ready()
    unit_name = f"[SIM] وحدة {secrets.token_hex(3)}"
    mission = await plan(
        client, staff, inspector, unit_site(unit_name), room_site("regional", SFAX), room_site("central")
    )
    unit, regional, central = mission["sites"]
    unit_report, _ = await inspect(client, inspector, unit["id"])
    regional_report, _ = await inspect(client, inspector, regional["id"])
    central_report, _ = await inspect(client, inspector, central["id"])

    sfax_room = staff(["operator"], SFAX)
    other_room = staff(["operator"], 11)
    central_room = staff(["ops_manager"], None)
    seen_sfax = {r["id"]: r for r in (await client.get(ROOMS, headers=sfax_room)).json()}
    seen_other = {r["id"] for r in (await client.get(ROOMS, headers=other_room)).json()}
    seen_central = {r["id"]: r for r in (await client.get(ROOMS, headers=central_room)).json()}
    # The unit's report stays in the inspections system.
    assert unit_report["id"] not in seen_sfax and unit_report["id"] not in seen_central
    # The regional room reads its own room's report, never the central room's nor another gouvernorat's.
    assert regional_report["id"] in seen_sfax and central_report["id"] not in seen_sfax
    assert regional_report["id"] not in seen_other
    # The central room reads every room's report (the default policy shows it the score).
    assert {regional_report["id"], central_report["id"]} <= set(seen_central)
    assert seen_central[regional_report["id"]]["score"] == 100
    # The default policy: the regional room reads the verdict but not the score; high to both, low to central.
    mine = seen_sfax[regional_report["id"]]
    assert mine["verdict"] == "جاهز" and mine["score"] is None
    assert [x["priority"] for x in mine["recommendations"]] == ["high"]
    assert {x["priority"] for x in seen_central[regional_report["id"]]["recommendations"]} == {"high", "low"}

    # The inspector general hides it from the regional room: the server drops it.
    r = await client.put(
        f"{STAFF}/records/{regional_report['id']}/disclosure",
        json={"room": "regional", "inspection": False},
        headers=general(staff),
    )
    assert r.status_code == 200, r.text
    assert regional_report["id"] not in {r["id"] for r in (await client.get(ROOMS, headers=sfax_room)).json()}

    # The programme: the central room only; the inspections in progress are dormant until granted.
    assert (await client.get(f"{ROOMS}/upcoming", headers=sfax_room)).status_code == 403
    assert (await client.get(f"{ROOMS}/upcoming", headers=central_room)).status_code == 200
    assert (await client.get(f"{ROOMS}/live", headers=central_room)).status_code == 403


# ---------------------------------------------------------------- the dashboard and the deletion


async def test_the_places_and_the_dashboard(client: httpx.AsyncClient, staff: Any, session: AsyncSession) -> None:
    inspector = await Inspector(client, staff, session).ready()
    name = f"[SIM] نقطة {secrets.token_hex(3)}"
    mission = await plan(client, staff, inspector, unit_site(name, "guard_post"))
    await inspect(client, inspector, mission["sites"][0]["id"])
    rows = (await client.get(f"{STAFF}/places", params={"gouvernorat_code": SFAX}, headers=general(staff))).json()
    assert rows[0]["target"] == "room" and rows[0]["gouvernorat_code"] == SFAX
    unit = next(r for r in rows if r["unit_name"] == name)
    assert unit["unit_kind"] == "guard_post" and unit["last_score"] == 100
    found = (await client.get(f"{STAFF}/records", params={"search": name[6:]}, headers=general(staff))).json()
    assert [r["place"] for r in found] == [f"نقطة حراسة {name}"]
    board = (await client.get(f"{STAFF}/dashboard", headers=general(staff))).json()
    assert board["month_missions"] >= 1 and board["rooms_without_plan"] >= 0


async def test_only_the_system_administrator_deletes_and_restores(
    client: httpx.AsyncClient, staff: Any, session: AsyncSession
) -> None:
    inspector = await Inspector(client, staff, session).ready()
    mission = await plan(client, staff, inspector, unit_site(f"[SIM] شاطئ {secrets.token_hex(3)}", "beach"))
    report, _ = await inspect(client, inspector, mission["sites"][0]["id"])
    body = {"scope": "one", "inspection_id": report["id"], "reason": "[SIM] تقرير تجريبي للحذف", "confirm": "حذف"}
    assert (await client.post(f"{ADMIN}/delete", json=body, headers=general(staff))).status_code == 403
    sysadmin = staff(["sysadmin"], None)
    wrong = body | {"confirm": "نعم"}
    assert (await client.post(f"{ADMIN}/delete", json=wrong, headers=sysadmin)).status_code == 422
    r = await client.post(f"{ADMIN}/delete", json=body, headers=sysadmin)
    assert r.status_code == 200 and r.json()["deleted"] == 1
    assert (await client.get(f"{STAFF}/records/{report['id']}", headers=general(staff))).status_code == 404
    assert report["id"] in {x["id"] for x in (await client.get(f"{ADMIN}/bin", headers=sysadmin)).json()}
    r = await client.post(f"{ADMIN}/bin/{report['id']}/restore", headers=sysadmin)
    assert r.status_code == 204
    assert (await client.get(f"{STAFF}/records/{report['id']}", headers=general(staff))).status_code == 200
