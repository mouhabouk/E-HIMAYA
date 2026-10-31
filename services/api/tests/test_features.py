"""What the system administrator grants and hides (L4, docs/phase-l/design-l4.md §8): the catalogue covers every staff
route, a hidden page or button is refused by the API, a granted button works on its routes only, and the fixed
security rules stay a ceiling nobody lifts."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import text

from app.modules.features import registry
from app.modules.features.registry import TECHNICAL

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/staff/features"
GABES = 61
# Shared by every page: the alert level in the header, the caller's own permissions, the account lookup.
# Tools of every page, guarded by their roles: the levels, one's own features, the user lookup and the dictation of a
# free-text field (phase D, review point 19).
SHARED = {
    ("GET", "/levels"),
    ("GET", "/features/mine"),
    ("POST", "/users/lookup"),
    ("POST", "/dictation"),
    ("POST", "/dictation/{dictation_id}/kept"),
}


def admin(staff: Staff) -> dict[str, str]:
    return staff(["sysadmin"], gouvernorat=None)


async def rule(client: httpx.AsyncClient, staff: Staff, **body: Any) -> httpx.Response:
    body.setdefault("reason", "[SIM] اختبار الصلاحيات")
    return await client.post(f"{URL}/rules", json=body, headers=admin(staff))


async def revoke(client: httpx.AsyncClient, staff: Staff, rule_id: str) -> None:
    r = await client.post(
        f"{URL}/rules/{rule_id}/revoke", json={"reason": "[SIM] نهاية الاختبار"}, headers=admin(staff)
    )
    assert r.status_code == 200, r.text


def test_the_catalogue_covers_every_staff_route() -> None:
    import app.main  # noqa: F401 - installs the registry

    reg = registry.get()
    assert len(reg.order) == len(set(reg.order))
    unowned = {route for route in reg.routes if not reg.match(*route)}
    assert unowned == SHARED
    for method, path in reg.routes:
        chain = reg.match(method, path)
        if method != "GET" and chain:
            # A write is granted or hidden by its own button, unless its whole page is fixed.
            assert chain[0].kind != "page" or "fixed" in chain[0].flags, (method, path)
    for key in reg.order:
        f = reg.features[key]
        assert f.act_as is None or f.act_as not in TECHNICAL, key
        assert f.kind != "page" or (f.nav and f.group), key
        # Every route a feature names exists.
        for route in f.routes:
            method, path = route.split(" ", 1)
            if f.kind != "page":
                assert (method, path) in reg.routes, route


async def test_a_hidden_page_and_a_granted_button(client: httpx.AsyncClient, staff: Staff) -> None:
    sub = f"feat-{uuid.uuid4()}"
    operator = staff(["operator"], gouvernorat=GABES, sub=sub)
    other = staff(["operator"], gouvernorat=GABES)
    assert (await client.get("/api/v1/staff/schedule/settings", headers=operator)).status_code == 200
    # The operator may not choose the approval path of the gouvernorat...
    put = {"approval": "head"}
    r = await client.put(f"/api/v1/staff/schedule/settings/{GABES}", json=put, headers=operator)
    assert r.status_code == 403
    # ... until the administrator grants that button to this account.
    r = await rule(client, staff, feature_key="schedule.settings", effect="grant", target_kind="user", target=sub)
    assert r.status_code == 201, r.text
    granted = r.json()
    assert granted["state"] == "active"
    r = await client.put(f"/api/v1/staff/schedule/settings/{GABES}", json=put, headers=operator)
    assert r.status_code == 200, r.text
    # The answers show the granted button as editable for this account.
    rows = (await client.get("/api/v1/staff/schedule/settings", headers=operator)).json()
    assert [x["can_edit"] for x in rows] == [True]
    # Only there: the other buttons of the page, and the other operators, are as before.
    assert (await client.put(f"/api/v1/staff/schedule/settings/{GABES}", json=put, headers=other)).status_code == 403
    mine = (await client.get(f"{URL}/mine", headers=operator)).json()
    # Only the dormant dry run is hidden from the account until the administrator grants it.
    assert all(key.split(".")[0] == "drill" for key in mine.pop("hidden"))
    assert mine == {"granted": ["schedule.settings"], "lent": {"schedule.settings": "ops_manager"}}
    # Never beyond the account's gouvernorat.
    r = await client.put("/api/v1/staff/schedule/settings/23", json=put, headers=operator)
    assert r.status_code in (403, 404)

    # A hidden page is refused by the API, its buttons with it, even the granted one.
    r = await rule(client, staff, feature_key="schedule", effect="hide", target_kind="user", target=sub)
    assert r.status_code == 201
    hidden = r.json()
    r = await client.get("/api/v1/staff/schedule/settings", headers=operator)
    assert (r.status_code, r.json()["detail"]) == (403, "feature_hidden")
    r = await client.put(f"/api/v1/staff/schedule/settings/{GABES}", json=put, headers=operator)
    assert r.json()["detail"] == "feature_hidden"
    assert (await client.get("/api/v1/staff/schedule/settings", headers=other)).status_code == 200
    mine = (await client.get(f"{URL}/mine", headers=operator)).json()
    assert "schedule" in mine["hidden"] and "schedule.settings" in mine["hidden"]

    # Revoked, both rules end; the list keeps them with who and why.
    await revoke(client, staff, hidden["id"])
    await revoke(client, staff, granted["id"])
    assert (await client.get("/api/v1/staff/schedule/settings", headers=operator)).status_code == 200
    r = await client.put(f"/api/v1/staff/schedule/settings/{GABES}", json=put, headers=operator)
    assert r.status_code == 403
    rows = (await client.get(f"{URL}/rules", params={"include_ended": True}, headers=admin(staff))).json()
    mine_rows = [x for x in rows if x["target"] == sub]
    assert {x["state"] for x in mine_rows} == {"revoked"}
    assert all(x["revoke_reason"] for x in mine_rows)


async def test_a_role_rule_and_a_period(client: httpx.AsyncClient, staff: Staff, session: Any) -> None:
    # A role hidden in one gouvernorat only, and a rule that starts tomorrow (no effect yet).
    r = await rule(
        client,
        staff,
        feature_key="library",
        effect="hide",
        target_kind="role",
        target="field_commander",
        gouvernorat_code=GABES,
    )
    assert r.status_code == 201, r.text
    hidden = r.json()
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    r = await rule(
        client,
        staff,
        feature_key="analytics",
        effect="hide",
        target_kind="role",
        target="field_commander",
        gouvernorat_code=GABES,
        starts_at=tomorrow,
    )
    later = r.json()
    assert later["state"] == "scheduled"
    try:
        url = "/api/v1/staff/library/tree"
        assert (await client.get(url, headers=staff(["field_commander"], gouvernorat=GABES))).status_code == 403
        assert (await client.get(url, headers=staff(["field_commander"], gouvernorat=23))).status_code == 200
        assert (await client.get(url, headers=staff(["operator"], gouvernorat=GABES))).status_code == 200
        r = await client.get("/api/v1/staff/analytics/overview", headers=staff(["field_commander"], gouvernorat=GABES))
        assert r.status_code != 403
        # The preview shows the administrator what such an account sees.
        r = await client.get(
            f"{URL}/preview", params={"roles": "field_commander", "gouvernorat": GABES}, headers=admin(staff)
        )
        rows = {x["key"]: x for x in r.json()}
        assert rows["library"]["hidden"] and not rows["library"]["open"]
        assert rows["analytics"]["open"] and rows["map"]["open"] and not rows["accounts"]["open"]
    finally:
        await revoke(client, staff, hidden["id"])
        await revoke(client, staff, later["id"])
    # Every change is in the audit log, with its reason.
    actions = (
        (
            await session.execute(
                text("SELECT action FROM audit.log WHERE target = ANY(:t) ORDER BY seq"),
                {"t": [hidden["id"], later["id"]]},
            )
        )
        .scalars()
        .all()
    )
    assert actions == ["features.hide", "features.hide", "features.revoke", "features.revoke"]


async def test_the_fixed_ceiling(client: httpx.AsyncClient, staff: Staff) -> None:
    async def refused(**body: Any) -> str:
        r = await rule(client, staff, **body)
        assert r.status_code == 422, r.text
        return str(r.json().get("reason") or r.json()["detail"])

    # Personal data never to a governor or a minister; sensitive layers, accounts and the audit never at all.
    assert (
        await refused(feature_key="incidents", effect="grant", target_kind="role", target="governor") == "personal_data"
    )
    assert await refused(feature_key="reports.claim", effect="grant", target_kind="role", target="minister") == (
        "personal_data"
    )
    assert await refused(feature_key="layers", effect="grant", target_kind="role", target="operator") == "fixed"
    assert await refused(feature_key="accounts", effect="grant", target_kind="user", target="x") == "fixed"
    assert await refused(feature_key="settings.basemap", effect="grant", target_kind="role", target="ops_manager") == (
        "fixed"
    )
    # Technical accounts never receive operational rights; national features never to a role of one gouvernorat.
    assert await refused(feature_key="schedule.edit", effect="grant", target_kind="role", target="sysadmin") == (
        "technical_account"
    )
    assert (
        await refused(
            feature_key="reports.refer", effect="grant", target_kind="role", target="operator", gouvernorat_code=GABES
        )
        == "national_scope"
    )
    # The administrator never locks the permissions page away from administrators, or from themselves.
    assert await refused(feature_key="permissions", effect="hide", target_kind="role", target="sysadmin") == (
        "self_lockout"
    )
    assert await refused(feature_key="nope", effect="hide", target_kind="role", target="operator") == "unknown_feature"
    assert await refused(feature_key="map", effect="hide", target_kind="role", target="citizen") == "unknown_role"

    # A grant to one governor's account passes the form but never the request: the ceiling is checked again there.
    sub = f"gov-{uuid.uuid4()}"
    r = await rule(client, staff, feature_key="incidents", effect="grant", target_kind="user", target=sub)
    assert r.status_code == 201
    granted = r.json()
    try:
        governor = staff(["governor"], gouvernorat=GABES, sub=sub)
        assert (await client.get("/api/v1/staff/incidents", headers=governor)).status_code == 403
        assert (await client.get(f"{URL}/mine", headers=governor)).json()["granted"] == []
        r = await client.get(
            f"{URL}/preview", params={"roles": "governor", "gouvernorat": GABES, "subject": sub}, headers=admin(staff)
        )
        row = next(x for x in r.json() if x["key"] == "incidents")
        assert (row["granted"], row["refused"], row["open"]) == (False, "personal_data", False)
    finally:
        await revoke(client, staff, granted["id"])


async def test_only_the_national_administrator(client: httpx.AsyncClient, staff: Staff) -> None:
    body = {"feature_key": "map", "effect": "hide", "target_kind": "role", "target": "operator", "reason": "[SIM] x x"}
    for headers in (staff(["sysadmin"], gouvernorat=GABES), staff(["ops_manager"], gouvernorat=None)):
        assert (await client.post(f"{URL}/rules", json=body, headers=headers)).status_code == 403
        assert (await client.get(f"{URL}/catalogue", headers=headers)).status_code == 403
    catalogue = (await client.get(f"{URL}/catalogue", headers=admin(staff))).json()
    keys = {f["key"]: f for f in catalogue}
    assert keys["schedule.approve"]["parent"] == "schedule" and keys["schedule.approve"]["act_as"] == "ops_manager"
    assert keys["layers"]["grantable"] is False and keys["incidents"]["flags"] == ["personal"]
    assert keys["schedule"]["names"]["ar"] == "البرمجة"
