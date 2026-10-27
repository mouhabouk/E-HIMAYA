# covers: FR-A-040, FR-A-042, FR-A-046, BR-01, BR-04, UC-01, UC-02
import re
from datetime import UTC, datetime, timedelta
from itertools import pairwise

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reports import router as reports_router
from tests.conftest import (
    SFAX,
    STAFF_ISS,
    TUNIS,
    TokenFactory,
    accept_charter,
    bearer,
    device_headers,
    outbox_events,
    report_body,
)

CODE = re.compile(r"^EH-\d{2}-(\d{2})-\d{7}$")


async def test_consent_is_required_before_reporting(client: httpx.AsyncClient, citizen: dict[str, str]) -> None:
    r = await client.post("/api/v1/reports", json=report_body(), headers=citizen)
    assert r.status_code == 428
    assert r.json()["detail"] == "consent_required"

    await accept_charter(client, citizen)
    r = await client.post("/api/v1/reports", json=report_body(), headers=citizen)
    assert r.status_code == 201, r.text


async def test_create_assigns_tracking_code_and_gouvernorat(client: httpx.AsyncClient, citizen: dict[str, str]) -> None:
    await accept_charter(client, citizen)
    r = await client.post("/api/v1/reports", json=report_body(SFAX), headers=citizen)
    assert r.status_code == 201
    body = r.json()
    match = CODE.match(body["tracking_code"])
    assert match and match.group(1) == "61"
    assert body["tracking_code"].startswith(f"EH-{datetime.now(UTC).year % 100:02d}-")
    assert body["status"] == "received"
    assert body["gouvernorat_code"] == 61
    assert body["location"] == SFAX
    assert body["media"] == []

    r = await client.post("/api/v1/reports", json=report_body(TUNIS), headers=citizen)
    assert r.json()["gouvernorat_code"] == 11


async def test_tracking_numbers_are_not_sequential(client: httpx.AsyncClient, citizen: dict[str, str]) -> None:
    """Audit R1, S07: codes must not be guessable from a previous one."""
    await accept_charter(client, citizen)
    codes = [
        (await client.post("/api/v1/reports", json=report_body(), headers=citizen)).json()["tracking_code"]
        for _ in range(4)
    ]
    assert all(CODE.match(code) for code in codes)
    numbers = [int(code[-7:]) for code in codes]
    assert len(set(numbers)) == len(numbers)
    assert [b - a for a, b in pairwise(numbers)] != [1, 1, 1]


async def test_offshore_point_waits_for_geo_verification(
    client: httpx.AsyncClient, citizen: dict[str, str], session: AsyncSession
) -> None:
    """Phase 9 §4.2 (changes phase 2): an offshore point is no longer given the nearest gouvernorat; it waits in the
    geo-verification queue with that gouvernorat as candidate. The tracking code keeps the phase 2 format."""
    await accept_charter(client, citizen)
    # A few kilometres off the Sfax coast (drowning, boat in distress).
    r = await client.post(
        "/api/v1/reports",
        json=report_body({"lat": 34.70, "lon": 10.86, "accuracy_m": 10.0}, category="drowning"),
        headers=citizen,
    )
    assert r.status_code == 201
    assert r.json()["gouvernorat_code"] is None
    match = CODE.match(r.json()["tracking_code"])
    assert match and match.group(1) == "61"
    row = (
        await session.execute(
            text("SELECT geo_state, geo_candidates, geo_reason FROM reports.report WHERE id = :id"),
            {"id": r.json()["id"]},
        )
    ).one()
    assert (row.geo_state, row.geo_candidates, row.geo_reason) == ("pending", [61], "outside_boundaries")


async def test_point_outside_tunisia_is_refused(client: httpx.AsyncClient, citizen: dict[str, str]) -> None:
    await accept_charter(client, citizen)
    r = await client.post("/api/v1/reports", json=report_body({"lat": 48.85, "lon": 2.35}), headers=citizen)
    assert r.status_code == 422


async def test_replay_is_idempotent(client: httpx.AsyncClient, citizen: dict[str, str]) -> None:
    await accept_charter(client, citizen)
    body = report_body()
    first = await client.post("/api/v1/reports", json=body, headers=citizen)
    again = await client.post("/api/v1/reports", json=body, headers=citizen)
    assert first.status_code == 201 and again.status_code == 200
    assert first.json()["id"] == again.json()["id"]
    assert first.json()["tracking_code"] == again.json()["tracking_code"]


async def test_client_uuid_of_someone_else_conflicts(
    client: httpx.AsyncClient, citizen: dict[str, str], make_token: TokenFactory
) -> None:
    other = bearer(make_token(roles=["citizen"]))
    await accept_charter(client, citizen)
    await accept_charter(client, other)
    body = report_body()
    assert (await client.post("/api/v1/reports", json=body, headers=citizen)).status_code == 201
    r = await client.post("/api/v1/reports", json=body, headers=other)
    assert r.status_code == 409
    assert r.json()["detail"] == "client_uuid_conflict"


async def test_future_device_time_is_clamped(client: httpx.AsyncClient, citizen: dict[str, str]) -> None:
    await accept_charter(client, citizen)
    future = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    body = (await client.post("/api/v1/reports", json=report_body(created_at=future), headers=citizen)).json()
    assert datetime.fromisoformat(body["created_at"]) <= datetime.fromisoformat(body["received_at"])


async def test_offline_report_keeps_device_time(client: httpx.AsyncClient, citizen: dict[str, str]) -> None:
    await accept_charter(client, citizen)
    earlier = datetime.now(UTC) - timedelta(hours=3)
    body = (
        await client.post("/api/v1/reports", json=report_body(created_at=earlier.isoformat()), headers=citizen)
    ).json()
    assert abs(datetime.fromisoformat(body["created_at"]) - earlier) < timedelta(seconds=1)


async def test_anonymous_reporting_with_device_key(client: httpx.AsyncClient, session: AsyncSession) -> None:
    device = device_headers()
    await accept_charter(client, device)
    r = await client.post("/api/v1/reports", json=report_body(category="sos", text=None), headers=device)
    assert r.status_code == 201, r.text
    report_id = r.json()["id"]

    row = (
        await session.execute(
            text(
                "SELECT a.kind::text AS kind, a.keycloak_sub, length(a.anon_pseudonym) AS plen "
                "FROM reports.report r JOIN identity.account a USING (user_id) WHERE r.id = :id"
            ),
            {"id": report_id},
        )
    ).one()
    assert row.kind == "anonymous" and row.keycloak_sub is None and row.plen == 32

    # Same device → same account; another device sees nothing of it.
    mine = (await client.get("/api/v1/reports/mine", headers=device)).json()["items"]
    assert [item["id"] for item in mine] == [report_id]
    other = device_headers()
    assert (await client.get("/api/v1/reports/mine", headers=other)).json()["items"] == []


@pytest.mark.parametrize("key", ["short", "!!not-base64!!", "A" * 60])
async def test_invalid_device_key(client: httpx.AsyncClient, key: str) -> None:
    r = await client.get("/api/v1/reports/mine", headers={"X-Device-Key": key})
    assert r.status_code == 400
    assert r.json()["detail"] == "invalid_device_key"


async def test_no_identity_is_401(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/v1/reports", json=report_body())
    assert r.status_code == 401
    assert r.json()["detail"] == "authentication_required"


async def test_staff_cannot_report(client: httpx.AsyncClient, make_token: TokenFactory) -> None:
    token = make_token(issuer=STAFF_ISS, roles=["operator"], scope_level="national")
    r = await client.post("/api/v1/reports", json=report_body(), headers=bearer(token))
    assert r.status_code == 403
    assert r.json()["detail"] == "reporter_realm_required"


async def test_quarantined_pseudonym_is_blocked(client: httpx.AsyncClient, session: AsyncSession) -> None:
    device = device_headers()
    await accept_charter(client, device)
    await session.execute(
        text(
            "UPDATE identity.account SET status = 'banned' WHERE user_id = "
            "(SELECT user_id FROM identity.consent ORDER BY id DESC LIMIT 1)"
        )
    )
    await session.commit()
    r = await client.post("/api/v1/reports", json=report_body(), headers=device)
    assert r.status_code == 403
    assert r.json()["detail"] == "anon_blocked"


async def test_my_reports_pagination(client: httpx.AsyncClient, citizen: dict[str, str]) -> None:
    await accept_charter(client, citizen)
    ids = [(await client.post("/api/v1/reports", json=report_body(), headers=citizen)).json()["id"] for _ in range(3)]
    page = (await client.get("/api/v1/reports/mine?limit=2", headers=citizen)).json()
    assert [i["id"] for i in page["items"]] == ids[::-1][:2]
    assert page["next_before"]
    rest = (
        await client.get("/api/v1/reports/mine", params={"limit": 2, "before": page["next_before"]}, headers=citizen)
    ).json()
    assert [i["id"] for i in rest["items"]] == [ids[0]]
    assert rest["next_before"] is None


async def test_public_tracking_exposes_status_only(client: httpx.AsyncClient) -> None:
    device = device_headers()
    await accept_charter(client, device)
    code = (await client.post("/api/v1/reports", json=report_body(), headers=device)).json()["tracking_code"]
    r = await client.get(f"/api/v1/reports/track/{code}")
    assert r.status_code == 200
    body = r.json()
    # Phase P4d (F-APP-38): the team's two steps are status too, never who or where.
    assert set(body) == {
        "tracking_code",
        "status",
        "received_at",
        "updated_at",
        "history",
        "team_en_route_at",
        "team_on_scene_at",
    }
    assert body["status"] == "received"
    assert [h["status"] for h in body["history"]] == ["received"]

    assert (await client.get("/api/v1/reports/track/EH-26-61-9999999")).status_code == 404
    assert (await client.get("/api/v1/reports/track/not-a-code")).status_code == 422


async def test_tracking_is_rate_limited(client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reports_router, "TRACK_LIMIT", 3)
    codes = [(await client.get("/api/v1/reports/track/EH-26-61-9999998")).status_code for _ in range(4)]
    assert codes == [404, 404, 404, 429]


async def test_report_creation_is_rate_limited(
    client: httpx.AsyncClient, citizen: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(reports_router, "CREATE_LIMIT", 2)
    await accept_charter(client, citizen)
    codes = [(await client.post("/api/v1/reports", json=report_body(), headers=citizen)).status_code for _ in range(3)]
    assert codes == [201, 201, 429]


async def test_creation_queues_an_event(
    client: httpx.AsyncClient, citizen: dict[str, str], session: AsyncSession
) -> None:
    await accept_charter(client, citizen)
    report_id = (await client.post("/api/v1/reports", json=report_body(), headers=citizen)).json()["id"]
    [payload] = [e for e in await outbox_events(session, "report.created") if e["report"]["id"] == report_id]
    # Sealed at rest: the report text never appears in the outbox table.
    raw = await session.scalar(text("SELECT string_agg(payload::text, '') FROM events.outbox"))
    assert "دخان كثيف" not in raw and payload["report"]["text"] == "دخان كثيف قرب المخزن"
    assert payload["report"]["reporter_kind"] == "citizen"
    assert payload["report"]["gouvernorat_code"] == 61


async def test_categories_are_localized(client: httpx.AsyncClient) -> None:
    ar = (await client.get("/api/v1/reports/categories")).json()
    fr = (await client.get("/api/v1/reports/categories?lang=fr")).json()
    assert {c["code"] for c in ar} == {
        "sos",
        "fire",
        "flood",
        "traffic_accident",
        "drowning",
        "landslide",
        "chemical_leak",
        "medical",
        "other",
    }
    assert next(c for c in ar if c["code"] == "fire")["label"] == "حريق"
    assert next(c for c in fr if c["code"] == "fire")["label"] == "Incendie"
