"""The menu of 20 systems in 4 blocks (Yamen 2026-11-13) and the administrator's hand on a whole system: the menu's one
source agrees with the catalogue, a system hidden or suspended closes all its pages, its message reaches its users, the
administrator never locks themself out, and a system granted in one go stays under the fixed ceiling."""

import json
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from app.modules.features import registry
from app.modules.features.registry import SYSTEM_PREFIX, menu_systems, system_of_nav

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/staff/features"
GABES = 61
SOURCE = Path(__file__).resolve().parents[3] / "apps" / "dashboard" / "src" / "menu" / "menu.json"


def admin(staff: Staff) -> dict[str, str]:
    return staff(["sysadmin"], gouvernorat=None)


async def rule(client: httpx.AsyncClient, staff: Staff, **body: Any) -> httpx.Response:
    body.setdefault("reason", "[SIM] اختبار الأنظمة الفرعية")
    return await client.post(f"{URL}/rules", json=body, headers=admin(staff))


async def revoke(client: httpx.AsyncClient, staff: Staff, rule_id: str) -> None:
    r = await client.post(
        f"{URL}/rules/{rule_id}/revoke", json={"reason": "[SIM] نهاية الاختبار"}, headers=admin(staff)
    )
    assert r.status_code == 200, r.text


def test_the_menu_source_and_the_catalogue_agree() -> None:
    menu = registry.load_menu()
    if SOURCE.exists():
        # The API's copy is the dashboard's source, byte for byte (scripts/menu/sync.py).
        assert json.loads(SOURCE.read_text(encoding="utf-8")) == menu
    systems = menu_systems(menu)
    assert len(systems) == 20
    assert [len(b["systems"]) for b in menu["blocks"]] == [11, 4, 3, 2]
    assert [s.number for s in systems] == list(range(1, 21))
    reg = registry.get()
    navs = {f.nav for f in reg.features.values() if f.nav}
    # Every built entry of the menu is a page or a tab of the catalogue, or a screen of one (the operations room is a
    # view of the live map); planned ones have no screen yet.
    for s in systems:
        for path in s.paths:
            assert path in navs or any(path.startswith(n + "/") for n in navs if n != "/"), (
                f"{path} of system {s.key} has no page in the catalogue"
            )
    # Every dashboard page of the catalogue is in the menu, filed under its system.
    for f in reg.features.values():
        if f.kind == "page" and f.nav:
            expected = "home" if f.nav == "/" else system_of_nav(systems, f.nav)
            assert expected is not None, f"page {f.key} ({f.nav}) is in no system of the menu"
            assert f.group == expected, f"page {f.key} is filed under {f.group}, the menu says {expected}"


async def test_a_hidden_system_closes_all_its_pages(client: httpx.AsyncClient, staff: Staff) -> None:
    roles = sorted(r.value for r in registry.get().features["liaison"].roles)
    reader = staff([roles[0]], gouvernorat=None, sub=f"sys-{uuid.uuid4()}")
    assert (await client.get("/api/v1/staff/liaison/bodies", headers=reader)).status_code == 200
    r = await rule(
        client, staff, feature_key=f"{SYSTEM_PREFIX}partners", effect="hide", target_kind="role", target=roles[0]
    )
    assert r.status_code == 201, r.text
    try:
        refused = await client.get("/api/v1/staff/liaison/bodies", headers=reader)
        assert refused.status_code == 403 and refused.json()["detail"] == "feature_hidden"
        mine = (await client.get(f"{URL}/mine", headers=reader)).json()
        assert "liaison" in mine["hidden"] and mine["suspended"] == {}
    finally:
        await revoke(client, staff, r.json()["id"])
    assert (await client.get("/api/v1/staff/liaison/bodies", headers=reader)).status_code == 200


async def test_a_suspended_system_shows_its_message(client: httpx.AsyncClient, staff: Staff) -> None:
    roles = sorted(r.value for r in registry.get().features["liaison"].roles)
    reader = staff([roles[0]], gouvernorat=None, sub=f"sys-{uuid.uuid4()}")
    key = f"{SYSTEM_PREFIX}partners"
    # A message is needed, and only a whole system is suspended.
    assert (await rule(client, staff, feature_key=key, effect="suspend", target_kind="everyone", target="*")).json()[
        "detail"
    ] == "suspend_needs_message"
    message = {"ar": "[SIM] صيانة نظام الاتصال حتى الساعة 10", "fr": "", "en": ""}
    page = await rule(
        client, staff, feature_key="liaison", effect="suspend", target_kind="everyone", target="*", message=message
    )
    assert page.json()["detail"] == "suspend_needs_system"
    r = await rule(
        client, staff, feature_key=key, effect="suspend", target_kind="everyone", target="*", message=message
    )
    assert r.status_code == 201, r.text
    assert r.json()["message"]["ar"] == message["ar"]
    try:
        assert (await client.get("/api/v1/staff/liaison/bodies", headers=reader)).status_code == 403
        mine = (await client.get(f"{URL}/mine", headers=reader)).json()
        assert mine["suspended"]["partners"]["ar"] == message["ar"]
        listed = (await client.get(f"{URL}/systems", headers=admin(staff))).json()
        partners = next(s for s in listed if s["key"] == "partners")
        assert [x["effect"] for x in partners["rules"]] == ["suspend"]
        assert [p["key"] for p in partners["pages"]] == ["liaison"]
        # A system is granted page by page, never as one rule.
        grant = await rule(client, staff, feature_key=key, effect="grant", target_kind="role", target=roles[0])
        assert grant.status_code == 422
    finally:
        await revoke(client, staff, r.json()["id"])


async def test_the_administrator_keeps_the_settings(client: httpx.AsyncClient, staff: Staff) -> None:
    key = f"{SYSTEM_PREFIX}settings"
    message = {"ar": "[SIM] تعطيل الإعدادات", "fr": "", "en": ""}
    r = await rule(
        client, staff, feature_key=key, effect="suspend", target_kind="everyone", target="*", message=message
    )
    assert r.status_code == 201, r.text
    try:
        assert (await client.get(f"{URL}/systems", headers=admin(staff))).status_code == 200
        assert (await client.get(f"{URL}/rules", headers=admin(staff))).status_code == 200
    finally:
        await revoke(client, staff, r.json()["id"])


async def test_a_system_granted_in_one_go_stays_under_the_ceiling(client: httpx.AsyncClient, staff: Staff) -> None:
    subject = f"sys-{uuid.uuid4()}"
    body = {
        "mode": "read",
        "target_kind": "user",
        "target": subject,
        "reason": "[SIM] منح نظام الشواطئ للقراءة",
    }
    assert (await client.post(f"{URL}/systems/nowhere/grant", json=body, headers=admin(staff))).status_code == 404
    r = await client.post(f"{URL}/systems/coastal/grant", json=body, headers=admin(staff))
    assert r.status_code == 201, r.text
    assert "coastal" in r.json()["features"]
    assert not any(k.startswith("coastal.") and "ack" in k for k in r.json()["features"])
    assignment = r.json()["id"]
    # A governor is never granted personal data: the settings system grants him nothing of the accounts or the audit.
    gov = await client.post(
        f"{URL}/systems/settings/grant",
        json={**body, "target_kind": "role", "target": "governor", "mode": "write"},
        headers=admin(staff),
    )
    assert gov.status_code in (201, 422), gov.text
    granted = gov.json().get("features", [])
    assert "accounts" not in granted and "audit" not in granted
    listed = (await client.get(f"{URL}/profile-assignments", headers=admin(staff))).json()
    assert any(a["id"] == assignment for a in listed)
    done = await client.post(
        f"{URL}/profile-assignments/{assignment}/revoke", json={"reason": "[SIM] نهاية الاختبار"}, headers=admin(staff)
    )
    assert done.status_code == 204
    if gov.status_code == 201:
        await client.post(
            f"{URL}/profile-assignments/{gov.json()['id']}/revoke",
            json={"reason": "[SIM] نهاية الاختبار"},
            headers=admin(staff),
        )


async def test_the_menu_order_names_systems(client: httpx.AsyncClient, staff: Staff) -> None:
    url = "/api/v1/staff/settings/menu.order"
    current = (await client.get("/api/v1/staff/settings", headers=admin(staff))).json()["items"]
    version = next(s["version"] for s in current if s["key"] == "menu.order")
    old = {"value": {"groups": ["ops"], "items": {}}, "version": version, "reason": "[SIM] مجموعة قديمة"}
    assert (await client.put(url, json=old, headers=admin(staff))).status_code == 422
    value = {
        "groups": ["home", "reports"],
        "items": {"gis": ["/map", "/reports/geo-queue"]},
        "systems": {"vision": {"names": {"ar": "[SIM] الرؤية"}, "tone": "teal", "icon": "visibility"}},
    }
    ok = await client.put(
        url, json={"value": value, "version": version, "reason": "[SIM] تسمية نظام"}, headers=admin(staff)
    )
    assert ok.status_code == 200, ok.text
    back = {
        "value": {"groups": [], "items": {}, "systems": {}},
        "version": ok.json()["version"],
        "reason": "[SIM] رجوع",
    }
    assert (await client.put(url, json=back, headers=admin(staff))).status_code == 200


async def test_the_inspections_bin_is_lent_to_the_inspector_general(client: httpx.AsyncClient, staff: Staff) -> None:
    """Yamen 2026-11-13: deleting and restoring inspections stays with the administrator, who may lend it."""
    sub = f"ig-{uuid.uuid4()}"
    general = staff(["inspector_general"], gouvernorat=None, sub=sub)
    assert (await client.get("/api/v1/staff/inspection-admin/bin", headers=general)).status_code == 403
    assert (await client.get("/api/v1/staff/inspection-admin/bin", headers=admin(staff))).status_code == 200
    r = await rule(client, staff, feature_key="inspection_admin", effect="grant", target_kind="user", target=sub)
    assert r.status_code == 201, r.text
    try:
        assert (await client.get("/api/v1/staff/inspection-admin/bin", headers=general)).status_code == 200
        # The page's grant opens the reads only; a delete needs the grant of its own button.
        refused = await client.post(
            "/api/v1/staff/inspection-admin/delete", json={"reason": "[SIM] x", "confirm": "x"}, headers=general
        )
        assert refused.status_code == 403, refused.text
    finally:
        await revoke(client, staff, r.json()["id"])
    assert (await client.get("/api/v1/staff/inspection-admin/bin", headers=general)).status_code == 403
