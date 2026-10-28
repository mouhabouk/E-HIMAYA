"""Resources register of every gouvernorat (phase R1, docs/phase-r/design-resources.md §2): the national catalogue,
vehicles with their specifications, equipment by quantity, staff with their specialities, the monthly confirmation of a
unit, the xlsx import with its preview, the CSV export, and who sees what (a regional room its own gouvernorat, the
central room all of them, the governor and the minister the counts only, the staff names the operations rooms only)."""

import io
import secrets
import uuid
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import httpx
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog
from app.modules.inventory import domain
from app.modules.programmes.domain import FileError, normalize

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/staff/inventory"
GABES, BIZERTE = 61, 23


async def _unit(client: httpx.AsyncClient, staff: Staff, code: int) -> dict[str, Any]:
    lat, lon = (33.88, 10.1) if code == GABES else (37.27, 9.87)
    r = await client.post(
        "/api/v1/staff/units",
        json={
            "name_ar": f"وحدة {secrets.token_hex(3)}",
            "name_fr": f"Unité {secrets.token_hex(3)}",
            "kind": "unit",
            "gouvernorat_code": code,
            "location": {"lat": lat, "lon": lon},
        },
        headers=staff(["ops_manager"], gouvernorat=code),
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def _manager(staff: Staff, code: int | None = GABES) -> dict[str, str]:
    return staff(["ops_manager"], gouvernorat=code)


def _matricule() -> str:
    return f"M{secrets.token_hex(4).upper()}"


# ---------------------------------------------------------------- reading and checking


REFS = (
    {
        normalize(label): domain.CategoryRef(
            "fire_engine", "vehicle", (("capacity_l", "number"), ("four_wd", "bool")), 0, True
        )
        for label in ("fire_engine", "شاحنة إطفاء")
    }
    | {normalize(label): domain.CategoryRef("diving", "skill", (), 3, True) for label in ("diving", "غوص")}
    | {normalize("مضخة"): domain.CategoryRef("pump", "equipment", (("flow_lpm", "number"),), 0, True)}
)


def test_specifications_and_skills_are_typed() -> None:
    engine = REFS[normalize("شاحنة إطفاء")]
    assert domain.check_specs({"capacity_l": "2 000".replace(" ", ""), "four_wd": "نعم", "seats": 4}, engine) == {
        "capacity_l": 2000,
        "four_wd": True,
    }
    try:
        domain.check_specs({"capacity_l": "كثير"}, engine)
        raise AssertionError
    except ValueError as exc:
        assert str(exc) == "capacity_l"
    assert domain.parse_skills("غوص:2:2027-06-30؛ diving:3", REFS) == [
        {"skill_key": "diving", "level": 3, "cert_expires": None}
    ]
    for wrong in ("غوص:4", "طبخ"):
        try:
            domain.parse_skills(wrong, REFS)
            raise AssertionError
        except ValueError:
            pass
    assert domain.matches({"capacity_l": 2500, "four_wd": True}, {"capacity_l": [2000, None], "four_wd": True})
    assert not domain.matches({"capacity_l": 1500}, {"capacity_l": [2000, None]})
    assert not domain.matches({}, {"capacity_l": [2000, None]})


def _workbook(vehicles: list[list[Any]], stock: list[list[Any]], agents: list[list[Any]]) -> bytes:
    book = Workbook()
    sheets = [("الآليات", vehicles), ("المعدات", stock), ("الأعوان", agents)]
    for i, (name, rows) in enumerate(sheets):
        sheet = book.active if i == 0 else book.create_sheet()
        assert sheet is not None
        sheet.title = name
        entity = domain.ENTITIES[i]
        sheet.append([labels[0] for labels in domain.COLUMNS[entity].values()])
        for row in rows:
            sheet.append(row)
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def test_a_file_is_checked_row_by_row() -> None:
    unit = uuid.uuid4()
    units = {normalize("وحدة قابس"): unit}
    # Columns: unit, category, label, code, state, year, notes, then the specifications.
    vehicles = [
        ["وحدة قابس", "شاحنة إطفاء", "إطفاء 1", "GB-01", "جاهزة", 2019, None, 2000, None, None, None, None, "نعم"],
        ["وحدة قابس", "شاحنة إطفاء", "إطفاء 1", "GB-02", "جاهزة", 2019],
        ["وحدة مجهولة", "شاحنة إطفاء", "إطفاء 3"],
        ["وحدة قابس", "شاحنة إطفاء", "إطفاء 4", None, "مفقودة", 1900],
    ]
    stock = [["وحدة قابس", "مضخة", 4, 1, None, None, 800]]
    agents = [
        [_matricule(), "علي التونسي", "عريف", "وحدة قابس", "في الخدمة", "20000000", "غوص:2:2027-06-30"],
        ["X", "اسم"],
        [_matricule(), "سامي", None, "وحدة قابس", None, None, "غوص:9"],
    ]
    parsed = domain.parse("register.xlsx", _workbook(vehicles, stock, agents), None, units, REFS)
    assert parsed.format == "xlsx"
    assert [r["label"] for r in parsed.rows["vehicles"]] == ["إطفاء 1", "إطفاء 4"]
    first = parsed.rows["vehicles"][0]
    assert first == {**first, "specs": {"capacity_l": 2000, "four_wd": True}, "state": "ready", "year": 2019}
    assert parsed.rows["stock"][0] == {
        **parsed.rows["stock"][0],
        "qty_ready": 4,
        "qty_broken": 1,
        "specs": {"flow_lpm": 800},
    }
    assert parsed.rows["agents"][0]["skills"] == [
        {"skill_key": "diving", "level": 2, "cert_expires": date(2027, 6, 30)}
    ]
    assert {(p.entity, p.code, p.line) for p in parsed.errors} == {
        ("vehicles", "duplicate_row", 3),
        ("vehicles", "unit_unknown", 4),
        ("agents", "unit_unknown", 3),
        ("agents", "skill_invalid", 4),
    }
    assert {(p.code, p.line) for p in parsed.warnings} == {("state_unknown", 5), ("year_invalid", 5)}
    try:
        domain.parse("register.csv", b"a,b\n1,2\n", None, units, REFS)
        raise AssertionError
    except FileError as exc:
        assert exc.code == "entity_required"


# ---------------------------------------------------------------- catalogue


async def test_the_catalogue_is_kept_by_the_central_room(client: httpx.AsyncClient, staff: Staff) -> None:
    found = (await client.get(f"{URL}/catalogue", headers=staff(["governor"], gouvernorat=GABES))).json()
    assert found["can_manage"] is False
    by_key = {c["key"]: c for c in found["items"]}
    assert [s["key"] for s in by_key["fire_engine"]["specs"]] == ["capacity_l", "flow_lpm", "four_wd"]
    assert by_key["diving"] == {**by_key["diving"], "kind": "skill", "family": None, "levels": 3}
    key = f"t_{secrets.token_hex(3)}"
    body = {
        "key": key,
        "kind": "equipment",
        "family": "equipment",
        "name": {"ar": "منشار", "fr": "Tronçonneuse", "en": "Chainsaw"},
        "specs": [{"key": "power_kw", "unit": "kW", "name": {"ar": "القدرة", "fr": "Puissance", "en": "Power"}}],
    }
    assert (await client.post(f"{URL}/catalogue", json=body, headers=_manager(staff))).status_code == 403
    central = _manager(staff, None)
    assert (await client.post(f"{URL}/catalogue", json={**body, "family": None}, headers=central)).status_code == 422
    r = await client.post(f"{URL}/catalogue", json=body, headers=central)
    assert r.status_code == 201, r.text
    assert (await client.post(f"{URL}/catalogue", json=body, headers=central)).status_code == 409
    r = await client.patch(f"{URL}/catalogue/{key}", json={"active": False}, headers=central)
    assert r.json()["active"] is False
    unit = await _unit(client, staff, GABES)
    r = await client.post(f"{URL}/stock", json={"unit_id": unit["id"], "category_key": key}, headers=_manager(staff))
    assert r.json()["detail"] == "category_inactive"


# ---------------------------------------------------------------- the register and who sees it


async def test_each_gouvernorat_keeps_and_sees_its_own(client: httpx.AsyncClient, staff: Staff) -> None:
    gabes, bizerte = await _unit(client, staff, GABES), await _unit(client, staff, BIZERTE)
    manager = _manager(staff)
    vehicle = {
        "unit_id": gabes["id"],
        "category_key": "fire_engine",
        "label": f"إطفاء {secrets.token_hex(2)}",
        "code": "GB-17",
        "specs": {"capacity_l": 2000, "four_wd": True},
        "year": 2018,
    }
    r = await client.post(f"{URL}/vehicles", json=vehicle, headers=manager)
    assert r.status_code == 201, r.text
    created = r.json()
    assert created == {
        **created,
        "kind": "fire_engine",
        "state": "ready",
        "specs": {"capacity_l": 2000, "four_wd": True},
    }
    assert (await client.post(f"{URL}/vehicles", json=vehicle, headers=manager)).json()["detail"] == "label_taken"
    wrong = {**vehicle, "label": "x", "specs": {"length_m": 30}}
    assert (await client.post(f"{URL}/vehicles", json=wrong, headers=manager)).json()["detail"] == "spec_unknown"
    # Another gouvernorat's unit does not exist for this room; an operator does not write.
    elsewhere = {**vehicle, "unit_id": bizerte["id"]}
    assert (await client.post(f"{URL}/vehicles", json=elsewhere, headers=manager)).status_code == 404
    operator = staff(["operator"], gouvernorat=GABES)
    assert (await client.post(f"{URL}/vehicles", json={**vehicle, "label": "y"}, headers=operator)).status_code == 403
    # Out for maintenance, with a reason; the version is kept.
    patch = {**vehicle, "state": "maintenance", "version": created["version"]}
    assert (await client.patch(f"{URL}/vehicles/{created['id']}", json=patch, headers=manager)).status_code == 422
    r = await client.patch(
        f"{URL}/vehicles/{created['id']}", json={**patch, "reason": "عطب في المضخة"}, headers=manager
    )
    assert r.json()["state"] == "maintenance"
    stale = {**patch, "reason": "مرة أخرى"}
    assert (await client.patch(f"{URL}/vehicles/{created['id']}", json=stale, headers=manager)).status_code == 409

    ids = lambda r: {v["id"] for v in r.json()["items"]}  # noqa: E731
    assert created["id"] in ids(await client.get(f"{URL}/vehicles", headers=operator))
    assert created["id"] not in ids(
        await client.get(f"{URL}/vehicles", headers=staff(["operator"], gouvernorat=BIZERTE))
    )
    assert created["id"] in ids(await client.get(f"{URL}/vehicles", headers=staff(["operator"], gouvernorat=None)))
    # The governor and the minister: the counts only.
    for counts_only in (staff(["governor"], gouvernorat=GABES), staff(["minister"], gouvernorat=None)):
        assert (await client.get(f"{URL}/vehicles", headers=counts_only)).status_code == 403
        assert (await client.get(f"{URL}/agents", headers=counts_only)).status_code == 403
    overview = (await client.get(f"{URL}/overview", headers=staff(["governor"], gouvernorat=GABES))).json()
    assert [g["code"] for g in overview["gouvernorats"]] == [GABES]
    assert overview["gouvernorats"][0]["vehicles"]["maintenance"] >= 1
    assert overview["can_list"] is False and overview["can_see_names"] is False
    national = (await client.get(f"{URL}/overview", headers=staff(["minister"], gouvernorat=None))).json()
    assert len(national["gouvernorats"]) == 24
    engines = next(c for c in national["categories"] if c["key"] == "fire_engine")
    assert engines["maintenance"] >= 1

    history = (await client.get(f"{URL}/revisions", params={"entity_id": created["id"]}, headers=operator)).json()
    assert [(h["action"], h["reason"]) for h in history["items"]] == [("update", "عطب في المضخة"), ("create", None)]
    assert (
        await client.request("DELETE", f"{URL}/vehicles/{created['id']}", json={}, headers=manager)
    ).status_code == 422
    r = await client.request("DELETE", f"{URL}/vehicles/{created['id']}", json={"reason": "بيعت الآلية"}, headers=manager)
    assert r.status_code == 204


async def test_equipment_by_quantity(client: httpx.AsyncClient, staff: Staff) -> None:
    unit = await _unit(client, staff, GABES)
    manager = _manager(staff)
    body = {"unit_id": unit["id"], "category_key": "pump", "specs": {"flow_lpm": 800}, "qty_ready": 4, "qty_broken": 1}
    r = await client.post(f"{URL}/stock", json=body, headers=manager)
    assert r.status_code == 201, r.text
    line = r.json()
    assert (await client.post(f"{URL}/stock", json=body, headers=manager)).json()["detail"] == "stock_exists"
    # The same type with other specifications is another line.
    assert (
        await client.post(f"{URL}/stock", json={**body, "specs": {"flow_lpm": 1500}}, headers=manager)
    ).status_code == 201
    assert (
        await client.post(f"{URL}/stock", json={**body, "category_key": "fire_engine"}, headers=manager)
    ).status_code == 422
    r = await client.patch(
        f"{URL}/stock/{line['id']}",
        json={**body, "qty_ready": 3, "qty_broken": 2, "reason": "عطب مضخة"},
        headers=manager,
    )
    assert (r.json()["qty_ready"], r.json()["qty_broken"], r.json()["version"]) == (3, 2, 2)
    units = (await client.get(f"{URL}/units", params={"gouvernorat": GABES}, headers=manager)).json()["items"]
    row = next(u for u in units if u["id"] == unit["id"])
    assert row == {**row, "equipment_ready": 3 + 4, "equipment_broken": 2 + 1, "stale": True, "verified_at": None}
    r = await client.post(f"{URL}/units/{unit['id']}/verify", headers=manager)
    assert r.json()["stale"] is False
    assert (await client.post(f"{URL}/units/{unit['id']}/verify", headers=_manager(staff, BIZERTE))).status_code == 404


async def test_staff_names_stay_in_the_operations_rooms(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession
) -> None:
    unit = await _unit(client, staff, GABES)
    manager = _manager(staff)
    matricule = _matricule()
    expires = (date.today() - timedelta(days=1)).isoformat()
    body = {
        "unit_id": unit["id"],
        "matricule": matricule,
        "full_name": "علي التونسي",
        "rank": "عريف",
        "phone": "20000000",
        "skills": [{"skill_key": "diving", "level": 2, "cert_expires": "2030-01-01"}, {"skill_key": "k9", "level": 2}],
    }
    r = await client.post(f"{URL}/agents", json=body, headers=manager)
    assert r.status_code == 201, r.text
    agent = r.json()
    assert agent["skills"] == [
        {"skill_key": "diving", "level": 2, "cert_expires": "2030-01-01", "expired": False},
        {"skill_key": "k9", "level": 0, "cert_expires": None, "expired": False},
    ]
    assert (await client.post(f"{URL}/agents", json=body, headers=manager)).json()["detail"] == "matricule_taken"
    # Bizerte cannot reuse the matricule either, though it cannot see the agent.
    other = await _unit(client, staff, BIZERTE)
    r = await client.post(f"{URL}/agents", json={**body, "unit_id": other["id"]}, headers=_manager(staff, BIZERTE))
    assert r.json()["detail"] == "matricule_taken"
    bad = {**body, "matricule": _matricule(), "skills": [{"skill_key": "diving", "level": 4}]}
    assert (await client.post(f"{URL}/agents", json=bad, headers=manager)).json()["detail"] == "skill_level_invalid"
    changed = {
        **body,
        "availability": "leave",
        "skills": [{"skill_key": "diving", "level": 2, "cert_expires": expires}],
    }
    r = await client.patch(f"{URL}/agents/{agent['id']}", json=changed, headers=manager)
    assert r.json()["skills"][0]["expired"] is True

    room = (
        await client.get(f"{URL}/agents", params={"skill": "diving"}, headers=staff(["operator"], gouvernorat=GABES))
    ).json()
    found = next(a for a in room["items"] if a["id"] == agent["id"])
    assert (found["full_name"], found["phone"], room["can_export_names"]) == ("علي التونسي", "20000000", True)
    commander = (await client.get(f"{URL}/agents", headers=staff(["field_commander"], gouvernorat=GABES))).json()
    hidden = next(a for a in commander["items"] if a["id"] == agent["id"])
    assert (hidden["full_name"], hidden["phone"], hidden["matricule"], hidden["rank"]) == (None, None, None, "عريف")
    history = (
        await client.get(
            f"{URL}/revisions", params={"entity_id": agent["id"]}, headers=staff(["field_commander"], gouvernorat=GABES)
        )
    ).json()
    assert all("full_name" not in h["snapshot"] and "phone" not in h["snapshot"] for h in history["items"])

    overview = (await client.get(f"{URL}/overview", headers=staff(["governor"], gouvernorat=GABES))).json()
    diving = next(s for s in overview["skills"] if s["key"] == "diving")
    assert diving["agents"] >= 1 and diving["expired"] >= 1

    # Export: the names leave with the room of the gouvernorat only; every export is audited.
    own = await client.get(f"{URL}/export", params={"entity": "agents"}, headers=staff(["operator"], gouvernorat=GABES))
    assert own.status_code == 200 and "علي التونسي" in own.text and own.text.startswith("﻿gouvernorat,unit,matricule")
    central = await client.get(
        f"{URL}/export",
        params={"entity": "agents", "gouvernorat": GABES},
        headers=staff(["operator"], gouvernorat=None),
    )
    assert "علي التونسي" not in central.text and "20000000" not in central.text and "diving:2" in central.text
    elsewhere = await client.get(
        f"{URL}/export", params={"entity": "agents", "gouvernorat": GABES}, headers=_manager(staff, BIZERTE)
    )
    assert elsewhere.status_code == 403
    entries = (
        await session.scalars(
            select(AuditLog).where(AuditLog.action == "inventory.export").order_by(AuditLog.id.desc()).limit(2)
        )
    ).all()
    assert [e.details["names"] for e in entries] == [False, True]
    r = await client.request("DELETE", f"{URL}/agents/{agent['id']}", json={"reason": "تقاعد العون"}, headers=manager)
    assert r.status_code == 204


# ---------------------------------------------------------------- import


async def test_import_preview_then_apply(client: httpx.AsyncClient, staff: Staff) -> None:
    unit = await _unit(client, staff, GABES)
    name = unit["name_ar"]
    manager = _manager(staff)
    matricule = _matricule()
    label = f"إطفاء {secrets.token_hex(2)}"
    vehicles = [[name, "شاحنة إطفاء", label, "GB-1", "جاهزة", 2020, None, 2000]]
    stock = [[name, "مضخة", 3, 0, None, None, 600]]
    agents = [[matricule, "سامي الغواص", "رقيب", name, "في الخدمة", None, "غوص:3:2030-01-01؛ إنقاذ بالحبال"]]
    bad = _workbook([*vehicles, ["وحدة لا توجد", "شاحنة إطفاء", "x"]], stock, agents)

    async def send(data: bytes, **params: Any) -> httpx.Response:
        return await client.post(
            f"{URL}/imports",
            params={"file_name": "register.xlsx", **params},
            content=data,
            headers=manager,
        )

    preview = (await send(bad)).json()
    assert preview == {
        **preview,
        "applied": False,
        "gouvernorat_code": GABES,
        "vehicles": {"new": 1, "changed": 0, "unchanged": 0},
        "stock": {"new": 1, "changed": 0, "unchanged": 0},
        "agents": {"new": 1, "changed": 0, "unchanged": 0},
    }
    assert preview["errors"] == [{"code": "unit_unknown", "entity": "vehicles", "line": 3, "value": "وحدة لا توجد"}]
    assert (await send(bad, apply="true", reason="التحميل الأول")).json()["detail"] == "import_has_errors"
    good = _workbook(vehicles, stock, agents)
    assert (await send(good, apply="true")).json()["detail"] == "reason_required"
    # The central room names the gouvernorat; a regional room imports its own only.
    assert (await send(good, gouvernorat=BIZERTE)).status_code == 403
    applied = (await send(good, apply="true", reason="التحميل الأول")).json()
    assert applied["applied"] is True and applied["agents"]["new"] == 1
    again = (await send(good)).json()
    assert [again[e] for e in ("vehicles", "stock", "agents")] == [{"new": 0, "changed": 0, "unchanged": 1}] * 3
    room = staff(["operator"], gouvernorat=GABES)
    found = next(
        a for a in (await client.get(f"{URL}/agents", headers=room)).json()["items"] if a["matricule"] == matricule
    )
    assert [(s["skill_key"], s["level"]) for s in found["skills"]] == [("diving", 3), ("rope_rescue", 0)]
    vehicles[0][4] = "معطلة"
    changed = (await send(_workbook(vehicles, stock, agents), apply="true", reason="تحيين شهري")).json()
    assert changed["vehicles"] == {"new": 0, "changed": 1, "unchanged": 0}
    listed = (await client.get(f"{URL}/vehicles", params={"unit_id": unit["id"]}, headers=room)).json()["items"]
    assert [(v["label"], v["state"], v["specs"]) for v in listed] == [(label, "broken", {"capacity_l": 2000})]
    # The same matricule in Bizerte's file is refused.
    other = await _unit(client, staff, BIZERTE)
    agents_b = [[matricule, "سامي", None, other["name_ar"]]]
    r = await client.post(
        f"{URL}/imports",
        params={"file_name": "b.xlsx"},
        content=_workbook([], [], agents_b),
        headers=_manager(staff, BIZERTE),
    )
    assert [e["code"] for e in r.json()["errors"]] == ["matricule_elsewhere"]
    template = await client.get(f"{URL}/template", headers=manager)
    assert template.status_code == 200 and template.content[:2] == b"PK"
    assert (await client.get(f"{URL}/template", headers=_manager(staff, None))).json()[
        "detail"
    ] == "gouvernorat_required"
