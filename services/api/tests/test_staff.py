from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import SFAX, TUNIS, TokenFactory, accept_charter, bearer, device_headers, report_body
from tests.test_profile import random_cin

Staff = Callable[..., dict[str, str]]


async def _report(client: httpx.AsyncClient, headers: dict[str, str], **kwargs: object) -> dict[str, object]:
    r = await client.post("/api/v1/reports", json=report_body(**kwargs), headers=headers)  # type: ignore[arg-type]
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


async def _ids(client: httpx.AsyncClient, headers: dict[str, str], **params: object) -> list[str]:
    r = await client.get("/api/v1/staff/reports", params={"limit": 500, **params}, headers=headers)
    assert r.status_code == 200, r.text
    return [item["id"] for item in r.json()["items"]]


async def test_reporters_cannot_use_staff_endpoints(client: httpx.AsyncClient, citizen: dict[str, str]) -> None:
    assert (await client.get("/api/v1/staff/reports", headers=citizen)).status_code == 403
    assert (await client.get("/api/v1/staff/kpis", headers=citizen)).status_code == 403


async def test_geographic_scope_is_enforced(client: httpx.AsyncClient, citizen: dict[str, str], staff: Staff) -> None:
    await accept_charter(client, citizen)
    sfax = await _report(client, citizen, location=SFAX)
    tunis = await _report(client, citizen, location=TUNIS)
    since = {"since": (datetime.now(UTC) - timedelta(minutes=5)).isoformat()}

    sfax_ids = await _ids(client, staff(gouvernorat=61), **since)
    assert sfax["id"] in sfax_ids and tunis["id"] not in sfax_ids

    national_ids = await _ids(client, staff(gouvernorat=None), **since)
    assert {sfax["id"], tunis["id"]} <= set(national_ids)

    # Out-of-scope details are hidden as 404 and cannot be changed.
    sfax_operator = staff(gouvernorat=61)
    assert (await client.get(f"/api/v1/staff/reports/{tunis['id']}", headers=sfax_operator)).status_code == 404
    r = await client.post(
        f"/api/v1/staff/reports/{tunis['id']}/status", json={"status": "in_progress"}, headers=sfax_operator
    )
    assert r.status_code == 404


async def test_filters_search_and_pagination(client: httpx.AsyncClient, citizen: dict[str, str], staff: Staff) -> None:
    await accept_charter(client, citizen)
    marker = f"marker-{datetime.now(UTC).timestamp()}"
    flood = await _report(client, citizen, category="flood", text=f"water rising {marker}")
    fire = await _report(client, citizen, category="fire", text=f"smoke {marker}")
    operator = staff(gouvernorat=61)

    assert await _ids(client, operator, q=marker) == [fire["id"], flood["id"]]
    assert await _ids(client, operator, q=marker, category="flood") == [flood["id"]]
    assert await _ids(client, operator, q=marker, category="flood,fire", status="received") == [fire["id"], flood["id"]]
    assert await _ids(client, operator, q=str(fire["tracking_code"])) == [fire["id"]]
    assert await _ids(client, operator, q=marker, bbox="10.5,34.5,11.0,35.0") == [fire["id"], flood["id"]]
    assert await _ids(client, operator, q=marker, bbox="9.0,36.0,10.5,37.0") == []

    page = (await client.get("/api/v1/staff/reports", params={"q": marker, "limit": 1}, headers=operator)).json()
    assert [i["id"] for i in page["items"]] == [fire["id"]]
    assert page["items"][0]["reporter_kind"] == "citizen" and page["items"][0]["media_count"] == 0
    rest = (
        await client.get(
            "/api/v1/staff/reports", params={"q": marker, "limit": 1, "cursor": page["next_cursor"]}, headers=operator
        )
    ).json()
    assert [i["id"] for i in rest["items"]] == [flood["id"]]

    assert (await client.get("/api/v1/staff/reports?status=bogus", headers=operator)).status_code == 422
    assert (await client.get("/api/v1/staff/reports?bbox=1,2,3", headers=operator)).status_code == 422
    assert (await client.get("/api/v1/staff/reports?cursor=%%%", headers=operator)).status_code == 422


async def test_detail_shows_reporter_and_is_audited(
    client: httpx.AsyncClient, make_token: TokenFactory, staff: Staff, session: AsyncSession
) -> None:
    citizen = bearer(make_token(roles=["citizen"]))
    profile = {
        "first_name": "Amira",
        "last_name": "Ben Salah",
        "cin": random_cin(),
        "phone": "+21698123456",
        "gouvernorat_code": 61,
        "delegation_id": 6101,
        "locale": "fr",
    }
    assert (await client.put("/api/v1/me/profile", json=profile, headers=citizen)).status_code == 200
    await accept_charter(client, citizen)
    report = await _report(client, citizen)
    operator = staff(gouvernorat=61)

    detail = (await client.get(f"/api/v1/staff/reports/{report['id']}", headers=operator)).json()
    assert detail["reporter"] == {
        "kind": "citizen",
        "first_name": "Amira",
        "last_name": "Ben Salah",
        "phone": "+21698123456",
    }
    assert [h["status"] for h in detail["history"]] == ["received"]
    assert detail["allowed_transitions"] == ["in_progress", "rejected"]
    assert detail["location"] == SFAX

    audited = await session.scalar(
        text("SELECT count(*) FROM audit.log WHERE action = 'report.view' AND target = :t"),
        {"t": f"report:{report['id']}"},
    )
    assert audited == 1

    device = device_headers()
    await accept_charter(client, device)
    anonymous = await _report(client, device)
    detail = (await client.get(f"/api/v1/staff/reports/{anonymous['id']}", headers=operator)).json()
    assert detail["reporter"] == {"kind": "anonymous", "first_name": None, "last_name": None, "phone": None}


async def test_status_lifecycle(
    client: httpx.AsyncClient, citizen: dict[str, str], staff: Staff, session: AsyncSession
) -> None:
    await accept_charter(client, citizen)
    report = await _report(client, citizen)
    url = f"/api/v1/staff/reports/{report['id']}/status"
    operator = staff(roles=["operator"], gouvernorat=61)

    r = await client.post(url, json={"status": "closed"}, headers=operator)
    assert r.status_code == 409 and r.json()["detail"] == "invalid_transition"

    r = await client.post(url, json={"status": "in_progress", "note": "فريق في الطريق"}, headers=operator)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "in_progress"
    assert r.json()["allowed_transitions"] == ["closed", "intervened", "ongoing", "rejected"]
    for target in ("intervened", "ongoing", "closed"):
        assert (await client.post(url, json={"status": target}, headers=operator)).status_code == 200
    assert (await client.post(url, json={"status": "ongoing"}, headers=operator)).status_code == 409

    track = (await client.get(f"/api/v1/reports/track/{report['tracking_code']}")).json()
    assert [h["status"] for h in track["history"]] == ["received", "in_progress", "intervened", "ongoing", "closed"]
    assert track["status"] == "closed"

    mine = (await client.get("/api/v1/reports/mine", headers=citizen)).json()["items"]
    assert next(i for i in mine if i["id"] == report["id"])["status"] == "closed"

    row = (
        await session.execute(
            text("SELECT first_response_at IS NOT NULL AS responded FROM reports.report WHERE id = :id"),
            {"id": report["id"]},
        )
    ).one()
    assert row.responded
    actions = await session.scalar(
        text("SELECT count(*) FROM audit.log WHERE action = 'report.status' AND target = :t"),
        {"t": f"report:{report['id']}"},
    )
    assert actions == 4
    events = await session.scalar(
        text(
            "SELECT count(*) FROM events.outbox WHERE subject = 'report.status_changed' "
            "AND payload->'report'->>'id' = :id"
        ),
        {"id": report["id"]},
    )
    assert events == 4


async def test_committees_can_read_but_not_change(
    client: httpx.AsyncClient, citizen: dict[str, str], staff: Staff
) -> None:
    await accept_charter(client, citizen)
    report = await _report(client, citizen)
    committee = staff(roles=["local_committee"], gouvernorat=61)
    assert (await client.get(f"/api/v1/staff/reports/{report['id']}", headers=committee)).status_code == 200
    r = await client.post(
        f"/api/v1/staff/reports/{report['id']}/status", json={"status": "in_progress"}, headers=committee
    )
    assert r.status_code == 403
    sysadmin = staff(roles=["sysadmin"], gouvernorat=None)
    assert (await client.get("/api/v1/staff/reports", headers=sysadmin)).status_code == 403


async def test_kpis(client: httpx.AsyncClient, citizen: dict[str, str], staff: Staff) -> None:
    await accept_charter(client, citizen)
    since = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    operator = staff(gouvernorat=61)
    before = (await client.get("/api/v1/staff/kpis", params={"since": since}, headers=operator)).json()

    first = await _report(client, citizen, category="medical")
    await _report(client, citizen, category="medical")
    await _report(client, citizen, location=TUNIS)  # outside the operator's scope
    await client.post(f"/api/v1/staff/reports/{first['id']}/status", json={"status": "in_progress"}, headers=operator)

    after = (await client.get("/api/v1/staff/kpis", params={"since": since}, headers=operator)).json()
    assert after["total"] - before["total"] == 2
    assert after["by_category"]["medical"] - before["by_category"]["medical"] == 2
    assert after["by_status"]["in_progress"] - before["by_status"]["in_progress"] == 1
    assert {g["code"] for g in after["by_gouvernorat"]} == {61}
    assert after["avg_first_response_s"] is not None and after["avg_first_response_s"] >= 0

    default = (await client.get("/api/v1/staff/kpis", headers=staff(gouvernorat=None))).json()
    assert set(default["by_status"]) == {"received", "in_progress", "intervened", "ongoing", "closed", "rejected"}
