"""The digital dry run (L5a, docs/phase-l/design-l5.md §2): dormant until the administrator grants it, approved by
each gouvernorat, played to the rooms with real resources booked inside the dry run only, stopped by any
participating room, evaluated by an independent evaluator, and never trusted for its texts (§2.4)."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import text

from app.core.db import get_system_sessionmaker

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/staff/drills"
RULES = "/api/v1/staff/features/rules"
NABEUL, BIZERTE, GABES = 21, 23, 61


async def grant(client: httpx.AsyncClient, staff: Staff, key: str, **target: Any) -> str:
    body = {"feature_key": key, "effect": "grant", "reason": "[SIM] تفعيل العملية البيضاء", **target}
    r = await client.post(RULES, json=body, headers=staff(["sysadmin"], gouvernorat=None))
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


async def revoke(client: httpx.AsyncClient, staff: Staff, rule_id: str) -> None:
    r = await client.post(
        f"{RULES}/{rule_id}/revoke",
        json={"reason": "[SIM] نهاية الاختبار"},
        headers=staff(["sysadmin"], gouvernorat=None),
    )
    assert r.status_code == 200, r.text


async def unit_with(code: int, kinds: list[str]) -> list[uuid.UUID]:
    unit = uuid.uuid4()
    ids = [uuid.uuid4() for _ in kinds]
    async with get_system_sessionmaker()() as s, s.begin():
        await s.execute(
            text(
                "INSERT INTO ops.unit (id, name_ar, name_fr, kind, gouvernorat_code, location) VALUES "
                "(:u, 'وحدة [SIM]', 'Unité [SIM]', 'unit', :g, "
                "CAST(ST_SetSRID(ST_MakePoint(10.7, 36.4), 4326) AS geography))"
            ),
            {"u": unit, "g": code},
        )
        for rid, kind in zip(ids, kinds, strict=True):
            await s.execute(
                text("INSERT INTO ops.resource (id, unit_id, kind, label) VALUES (:r, :u, :k, :l)"),
                {"r": rid, "u": unit, "k": kind, "l": f"[SIM] {kind} {rid.hex[:6]}"},
            )
    return ids


def plan(**over: Any) -> dict[str, Any]:
    body = {
        "title": "[SIM] فيضان نابل وبنزرت",
        "objective": "اختبار جاهزية القاعتين والموارد أمام فيضان",
        "hazard_key": "flood",
        "gouvernorats": [NABEUL, BIZERTE],
        "planned_start": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        "duration_min": 60,
    }
    body.update(over)
    return body


async def test_dormant_until_the_administrator_grants_it(client: httpx.AsyncClient, staff: Staff) -> None:
    central = staff(["ops_manager"], gouvernorat=None)
    # Nobody holds the dry run by default, not even the central room.
    assert (await client.get(URL, headers=central)).status_code == 403
    assert (await client.post(URL, json=plan(), headers=central)).status_code == 403
    mine = (await client.get("/api/v1/staff/features/mine", headers=central)).json()
    assert "drill" in mine["hidden"] and "drill.stop" not in mine["hidden"]
    page = await grant(client, staff, "drill", target_kind="role", target="ops_manager")
    try:
        assert (await client.get(URL, headers=central)).status_code == 200
        # The page opens the reads; planning is a button of its own.
        assert (await client.post(URL, json=plan(), headers=central)).status_code == 403
        button = await grant(client, staff, "drill.plan", target_kind="role", target="ops_manager")
        try:
            r = await client.post(URL, json=plan(), headers=central)
            assert r.status_code == 201, r.text
            assert r.json()["status"] == "draft"
            assert [p["decision"] for p in r.json()["participants"]] == ["pending", "pending"]
        finally:
            await revoke(client, staff, button)
    finally:
        await revoke(client, staff, page)


async def test_a_dry_run_from_plan_to_report(client: httpx.AsyncClient, staff: Staff) -> None:
    rules = [
        await grant(client, staff, key, target_kind="role", target="ops_manager")
        for key in ("drill", "drill.plan", "drill.scenario", "drill.approve", "drill.start", "drill.respond")
    ]
    evaluator_sub = f"eval-{uuid.uuid4()}"
    rules += [
        await grant(client, staff, key, target_kind="user", target=evaluator_sub) for key in ("drill", "drill.evaluate")
    ]
    try:
        central = staff(["ops_manager"], gouvernorat=None)
        nabeul = staff(["ops_manager"], gouvernorat=NABEUL)
        bizerte = staff(["ops_manager"], gouvernorat=BIZERTE)
        gabes = staff(["ops_manager"], gouvernorat=GABES)
        evaluator = staff(["ops_manager"], gouvernorat=GABES, sub=evaluator_sub)
        boats = await unit_with(NABEUL, ["boat", "boat"])

        # A regional room plans only its own gouvernorat.
        r = await client.post(URL, json=plan(), headers=nabeul)
        assert r.status_code == 403 and r.json()["detail"] == "out_of_scope"
        r = await client.post(URL, json=plan(evaluator=evaluator_sub, evaluator_name="[SIM] مقيّم"), headers=central)
        assert r.status_code == 201, r.text
        ex = r.json()
        eid = ex["id"]
        # Gabès is not in the dry run: it does not even see it.
        assert (await client.get(f"{URL}/{eid}", headers=gabes)).status_code == 404

        # The scenario: a written inject, then reports [SIM] from the generator.
        inject = {
            "offset_min": 0,
            "gouvernorat_code": NABEUL,
            "kind": "evacuation",
            "title": "[SIM] عائلات محاصرة في منزل تميم",
            "needs": {"boat": 3},
            "expected": "فتح محور وإرسال القوارب حسب المخطط الأزرق",
        }
        r = await client.post(f"{URL}/{eid}/injects", json=inject, headers=central)
        assert r.status_code == 201, r.text
        iid = r.json()["id"]
        assert (await client.post(f"{URL}/{eid}/injects", json={**inject, "offset_min": 60}, headers=central)).json()[
            "detail"
        ] == "offset_after_end"
        r = await client.post(f"{URL}/{eid}/generate", json={"count": 20, "seed": 7}, headers=central)
        assert r.status_code == 201, r.text
        gen = r.json()
        assert len(gen) == 20 and all(g["generated"] and g["title"].startswith("[SIM]") for g in gen)
        again = await client.post(f"{URL}/{eid}/generate", json={"count": 20, "seed": 7}, headers=central)
        assert [g["offset_min"] for g in again.json()] == [g["offset_min"] for g in gen]
        # The rooms never read the whole scenario.
        assert (await client.get(f"{URL}/{eid}/injects", headers=nabeul)).status_code == 403

        # Approval of each gouvernorat.
        assert (await client.post(f"{URL}/{eid}/start", headers=central)).status_code == 409
        r = await client.post(f"{URL}/{eid}/submit", headers=central)
        assert r.status_code == 200 and r.json()["status"] == "submitted", r.text
        r = await client.post(f"{URL}/{eid}/approvals", json={"decision": "approved"}, headers=nabeul)
        assert r.json()["status"] == "submitted"
        assert (await client.post(f"{URL}/{eid}/approvals", json={"decision": "refused"}, headers=bizerte)).json()[
            "detail"
        ] == "reason_required"
        r = await client.post(f"{URL}/{eid}/approvals", json={"decision": "approved"}, headers=bizerte)
        assert r.json()["status"] == "ready" and r.json()["can_start"] is False
        assert (await client.get(f"{URL}/{eid}", headers=central)).json()["can_start"] is True

        r = await client.post(f"{URL}/{eid}/start", headers=central)
        assert r.status_code == 200 and r.json()["status"] == "running", r.text

        # Nabeul sees its due injects and books its real boats inside the dry run only.
        feed = (await client.get(f"{URL}/{eid}/feed", headers=nabeul)).json()
        assert iid in [item["inject"]["id"] for item in feed["items"]]
        assert feed["free"].get("boat", 0) >= 2
        assert {r["id"] for r in feed["free_resources"]} >= {str(b) for b in boats}
        answer = {"action": "dispatched", "text": "[SIM] قاربان نحو منزل تميم", "resource_ids": [str(b) for b in boats]}
        r = await client.post(f"{URL}/{eid}/injects/{iid}/responses", json=answer, headers=nabeul)
        assert r.status_code == 201, r.text
        assert len(r.json()["bookings"]) == 2
        # A booked boat is not free twice in the same dry run, and Bizerte cannot book Nabeul's boats.
        r = await client.post(f"{URL}/{eid}/injects/{iid}/responses", json=answer, headers=nabeul)
        assert r.status_code == 409 and r.json()["detail"] == "resource_not_free"
        r = await client.post(f"{URL}/{eid}/injects/{iid}/responses", json=answer, headers=bizerte)
        assert r.status_code == 404
        async with get_system_sessionmaker()() as s:
            statuses = (
                await s.execute(text("SELECT status FROM ops.resource WHERE id = ANY(:ids)"), {"ids": boats})
            ).scalars()
            assert set(statuses) == {"available"}

        # The evaluator marks the inject; a participant cannot.
        mark = {"plan_followed": "partly", "score": 3, "notes": "[SIM] قاربان من ثلاثة"}
        assert (await client.put(f"{URL}/{eid}/injects/{iid}/evaluation", json=mark, headers=nabeul)).status_code == 403
        r = await client.put(f"{URL}/{eid}/injects/{iid}/evaluation", json=mark, headers=evaluator)
        assert r.status_code == 200, r.text

        # Any participating room stops at once (a real incident comes first).
        r = await client.post(f"{URL}/{eid}/stop", json={"reason": "[SIM] حادث حقيقي في بنزرت"}, headers=bizerte)
        assert r.status_code == 200 and r.json()["status"] == "stopped", r.text

        r = await client.post(f"{URL}/{eid}/stress", json=STRESS, headers=central)
        assert r.status_code == 201, r.text
        report = (await client.get(f"{URL}/{eid}/report", headers=central)).json()
        line = next(x for x in report["injects"] if x["inject"]["id"] == iid)
        assert line["answered"] is True and line["booked"] == {"boat": 2} and line["shortfall"] == {"boat": 1}
        assert line["evaluation"]["score"] == 3
        boat = next(x for x in report["resources"] if x["gouvernorat_code"] == NABEUL and x["kind"] == "boat")
        assert boat["peak_booked"] == 2 and boat["short"] >= 1
        assert report["stress"][0]["attacks_blocked"] == STRESS["attacks_blocked"]
        r = await client.post(f"{URL}/{eid}/close", json={"conclusion": "[SIM] نقص في القوارب"}, headers=central)
        assert r.json()["status"] == "closed"

        async with get_system_sessionmaker()() as s:
            actions = (
                await s.execute(
                    text("SELECT action FROM audit.log WHERE target = :t ORDER BY id"), {"t": f"drill:{eid}"}
                )
            ).scalars()
            assert {"drill.create", "drill.submit", "drill.approved", "drill.start", "drill.stop"} <= set(actions)
    finally:
        for rule_id in rules:
            await revoke(client, staff, rule_id)


STRESS = {
    "environment": "isolated",
    "reports_sent": 12000,
    "reports_accepted": 11800,
    "reports_refused": 200,
    "errors_5xx": 0,
    "peak_per_second": 16.2,
    "latency_p95_ms": 420.0,
    "latency_p99_ms": 900.0,
    "duration_s": 900,
    "attacks_sent": 200,
    "attacks_blocked": 200,
    "attack_kinds": ["sql_injection", "script", "oversize"],
}


async def test_the_stop_cannot_be_hidden_and_texts_are_never_trusted(client: httpx.AsyncClient, staff: Staff) -> None:
    rules = [
        await grant(client, staff, key, target_kind="role", target="ops_manager")
        for key in ("drill", "drill.plan", "drill.scenario", "drill.approve", "drill.start")
    ]
    try:
        nabeul = staff(["ops_manager"], gouvernorat=NABEUL)
        r = await client.post(URL, json=plan(gouvernorats=[NABEUL], evaluator="someone"), headers=nabeul)
        eid = r.json()["id"]
        # Texts are checked, never pasted into a query: an injection is stored as plain text or refused.
        payload = "[SIM] '; DROP TABLE drill.exercise; --"
        r = await client.post(
            f"{URL}/{eid}/injects",
            json={"offset_min": 1, "kind": "report", "title": payload, "needs": {"boat": 1}},
            headers=nabeul,
        )
        assert r.status_code == 201 and r.json()["title"] == payload
        for bad in (
            {"offset_min": 1, "kind": "report", "title": "x" * 201},
            {"offset_min": 1, "kind": "sql", "title": "[SIM] نوع مجهول"},
            {"offset_min": 1, "kind": "report", "title": "[SIM] حاجة مجهولة", "needs": {"tank": 1}},
            {"offset_min": 1, "kind": "report", "title": "[SIM] حاجة مفرطة", "needs": {"boat": 999}},
            {"offset_min": 1, "kind": "report", "title": "[SIM] حقل زائد", "extra": "1"},
        ):
            assert (await client.post(f"{URL}/{eid}/injects", json=bad, headers=nabeul)).status_code == 422, bad
        assert (await client.get(f"{URL}/{eid}", headers=nabeul)).status_code == 200
        r = await client.post(f"{URL}/{eid}/generate", json={"count": 301}, headers=nabeul)
        assert r.status_code == 422

        await client.post(f"{URL}/{eid}/submit", headers=nabeul)
        await client.post(f"{URL}/{eid}/approvals", json={"decision": "approved"}, headers=nabeul)
        assert (await client.post(f"{URL}/{eid}/start", headers=nabeul)).status_code == 200
        # Even a hiding of the stop button does not take it from a participating room during a run.
        hide = await client.post(
            RULES,
            json={
                "feature_key": "drill.stop",
                "effect": "hide",
                "target_kind": "role",
                "target": "ops_manager",
                "reason": "[SIM] محاولة حجب الإيقاف",
            },
            headers=staff(["sysadmin"], gouvernorat=None),
        )
        assert hide.status_code == 201, hide.text
        rules.append(str(hide.json()["id"]))
        r = await client.post(f"{URL}/{eid}/stop", json={"reason": "[SIM] حادث حقيقي"}, headers=nabeul)
        assert r.status_code == 200 and r.json()["status"] == "stopped", r.text
        # A room outside the dry run cannot stop it.
        assert (
            await client.post(f"{URL}/{eid}/stop", json={"reason": "[SIM] من خارج"}, headers=staff(["ops_manager"]))
        ).status_code == 404
    finally:
        for rule_id in rules:
            await revoke(client, staff, rule_id)
