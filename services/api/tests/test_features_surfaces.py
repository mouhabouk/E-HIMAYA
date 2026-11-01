"""Phase 5 (Yamen 2026-11-01): the administrator's rules reach the field app, the citizen app and the portal. A button
of the field app is hidden from a team or lent to an agent; a window of the citizen app or of the portal is closed for
everyone (anonymous callers too) or for a public role; the emergency report, the SOS and the crew's alerts stay open."""

import uuid
from typing import Any

import httpx

from app.modules.features import registry
from tests.test_crew import Leader
from tests.test_features import Staff, revoke, rule


async def test_a_field_app_button_hidden_from_one_team_leader(client: httpx.AsyncClient, staff: Staff) -> None:
    leader = Leader(client, staff)
    await leader.register()
    other = Leader(client, staff)
    await other.register()
    r = await rule(
        client, staff, feature_key="field_missions.record", effect="hide", target_kind="user", target=leader.sub
    )
    assert r.status_code == 201, r.text
    hidden = r.json()
    try:
        assert "field_missions.record" in (await leader.get("/me")).json()["hidden_features"]
        assert "field_missions.record" not in (await other.get("/me")).json()["hidden_features"]
        missing = f"/missions/{uuid.uuid4()}/record"
        r = await leader.post(missing, {"client_id": str(uuid.uuid4()), "device_at": "2026-11-01T08:00:00Z"})
        assert r.status_code == 403 and r.json()["detail"] == "feature_hidden"
        # The other leader reaches the route (and learns the mission is not theirs).
        r = await other.post(missing, {"client_id": str(uuid.uuid4()), "device_at": "2026-11-01T08:00:00Z"})
        assert r.json()["detail"] != "feature_hidden"
    finally:
        await revoke(client, staff, hidden["id"])


def test_the_field_app_lends_the_team_leader_role() -> None:
    import app.main  # noqa: F401 - installs the registry

    reg = registry.get()
    record = reg.features["field_missions.record"]
    assert record.group == "field_app" and record.act_as is not None and record.act_as.value == "team_leader"
    assert reg.features["field_prevention.visit"].act_as.value == "org_auditor"  # type: ignore[union-attr]
    assert "safety" in reg.features["field_missions.alerts"].flags
    # Every write of the field app is a button of its own (a page grant never opens a write).
    for method, path in reg.routes:
        chain = reg.match(method, path)
        if path.startswith(registry.CREW + "/") and method != "GET" and chain:
            assert chain[0].kind == "button", (method, path)


async def test_a_citizen_window_closed_for_everyone(client: httpx.AsyncClient, staff: Staff, citizen: Any) -> None:
    assert (await client.get("/api/v1/emergency-guide")).status_code == 200
    r = await rule(client, staff, feature_key="citizen_guide", effect="hide", target_kind="everyone", target="*")
    assert r.status_code == 201, r.text
    closed = r.json()
    try:
        r = await client.get("/api/v1/emergency-guide")
        assert r.status_code == 403 and r.json()["detail"] == "feature_hidden"
        assert (await client.get("/api/v1/emergency-guide", headers=citizen)).status_code == 403
        assert "citizen_guide" in (await client.get("/api/v1/app/features")).json()["hidden"]
        assert "citizen_guide" in (await client.get("/api/v1/app/features", headers=citizen)).json()["hidden"]
        # The app's plumbing stays open.
        assert (await client.get("/api/v1/app/version")).status_code == 200
    finally:
        await revoke(client, staff, closed["id"])
    assert (await client.get("/api/v1/emergency-guide")).status_code == 200
    assert "citizen_guide" not in (await client.get("/api/v1/app/features")).json()["hidden"]


async def test_a_window_closed_for_one_public_role(client: httpx.AsyncClient, staff: Staff, citizen: Any) -> None:
    r = await rule(client, staff, feature_key="citizen_guide", effect="hide", target_kind="role", target="citizen")
    assert r.status_code == 201, r.text
    closed = r.json()
    try:
        assert (await client.get("/api/v1/safety-tips", headers=citizen)).json()["detail"] == "feature_hidden"
        # Anonymous callers hold no role: the window stays open for them.
        assert (await client.get("/api/v1/safety-tips")).status_code == 200
    finally:
        await revoke(client, staff, closed["id"])


async def test_what_the_administrator_cannot_do(client: httpx.AsyncClient, staff: Staff) -> None:
    async def refused(**body: Any) -> dict[str, Any]:
        r = await rule(client, staff, **body)
        assert r.status_code == 422, r.text
        return r.json()  # type: ignore[no-any-return]

    # The emergency report, the SOS and the crew's alerts are never hidden.
    for key in ("citizen_reports.send", "citizen_safety.sos", "field_missions.alerts"):
        assert (await refused(feature_key=key, effect="hide", target_kind="everyone", target="*"))["reason"] == "safety"
    # A window of the citizen app is never granted (nobody acts as somebody else there).
    body = {"feature_key": "citizen_beaches", "effect": "grant", "target_kind": "everyone", "target": "*"}
    assert (await refused(**body))["reason"] == "fixed"
    # A public role is a target of the public windows only; "everyone" is national and has no target.
    r = await rule(client, staff, feature_key="analytics", effect="hide", target_kind="role", target="citizen")
    assert r.json()["detail"] == "unknown_role"
    r = await rule(client, staff, feature_key="citizen_beaches", effect="hide", target_kind="everyone", target="x")
    assert r.json()["detail"] == "everyone_rule_is_global"
    # The administrator never closes the permissions page for everyone.
    r = await rule(client, staff, feature_key="permissions", effect="hide", target_kind="everyone", target="*")
    assert r.json()["detail"] == "self_lockout"


async def test_the_administrators_message_shows_at_once(client: httpx.AsyncClient, staff: Staff) -> None:
    sysadmin = staff(["sysadmin"], gouvernorat=None)
    url = "/api/v1/staff/settings/app.announcement"
    current = (await client.get("/api/v1/staff/settings", headers=sysadmin)).json()
    version = next(x["version"] for x in current["items"] if x["key"] == "app.announcement")
    message = {
        "active": True,
        "tone": "warn",
        "text": {
            "ar": "[SIM] صيانة مبرمجة الليلة",
            "fr": "[SIM] Maintenance ce soir",
            "en": "[SIM] Maintenance tonight",
        },
        "surfaces": ["citizen_app", "dashboard"],
        "ends_at": None,
    }
    body = {"value": message, "version": version, "reason": "[SIM] اختبار الرسالة"}
    r = await client.put(url, json=body, headers=sysadmin)
    assert r.status_code == 200, r.text
    try:
        shown = (await client.get("/api/v1/app/features")).json()["announcement"]
        assert shown == {"tone": "warn", **message["text"]}  # type: ignore[dict-item]
        assert (await client.get("/api/v1/app/features?surface=portal")).json()["announcement"] is None
        mine = (await client.get("/api/v1/staff/features/mine", headers=staff(["operator"]))).json()
        assert mine["announcement"]["ar"] == "[SIM] صيانة مبرمجة الليلة"
        # Only the system administrator writes it; an active message needs its Arabic text and a surface.
        bad = {**body, "version": version + 1, "value": {**message, "surfaces": []}}
        assert (await client.put(url, json=bad, headers=sysadmin)).json()["detail"] == "invalid_setting"
        r = await client.put(url, json={**body, "version": version + 1}, headers=staff(["central_committee"], None))
        assert r.status_code == 403
    finally:
        off = {"value": {**message, "active": False}, "version": version + 1, "reason": "[SIM] نهاية الاختبار"}
        assert (await client.put(url, json=off, headers=sysadmin)).status_code == 200
