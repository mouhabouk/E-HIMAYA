"""Phase 10 §4.2: a volunteer shares their position only with their consent, and staff see it coarsened."""

import uuid
from collections.abc import Callable

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.volunteers.service import coarse_distance, coarse_point
from tests.conftest import TokenFactory, bearer
from tests.test_operations import Staff, approved_volunteer

CONSENT = "/api/v1/me/consents"
BODY = {"purpose": "volunteer_location", "version": "1"}


@pytest.fixture
def citizen(make_token: TokenFactory) -> Callable[[], dict[str, str]]:
    def _make() -> dict[str, str]:
        email = f"v{uuid.uuid4().hex[:8]}@example.tn"
        return bearer(make_token(roles=["citizen"], email=email, email_verified=True, name="Volunteer"))

    return _make


async def test_withdrawal_ends_readiness_and_drops_the_position(
    client: httpx.AsyncClient, staff: Staff, citizen: Callable[[], dict[str, str]], session: AsyncSession
) -> None:
    headers = citizen()
    volunteer_id = await approved_volunteer(client, staff, headers, {"lat": 34.74, "lon": 10.76})
    # Giving it again is harmless and not audited twice.
    assert (await client.post(CONSENT, json=BODY, headers=headers)).status_code == 204
    given = await session.scalar(
        text("SELECT count(*) FROM audit.log WHERE action = 'consent.volunteer_location' AND target = :t"),
        {"t": f"volunteer:{volunteer_id}"},
    )
    assert given == 1
    assert (await client.get("/api/v1/me/volunteer", headers=headers)).json()["location_consent"] is True

    assert (await client.delete(f"{CONSENT}/volunteer_location", headers=headers)).status_code == 204
    me = (await client.get("/api/v1/me/volunteer", headers=headers)).json()
    assert me["ready"] is False and me["location_consent"] is False
    geo = (await client.get("/api/v1/staff/volunteers/map", headers=staff())).json()
    assert volunteer_id not in [f["properties"]["id"] for f in geo["features"]]
    r = await client.put("/api/v1/me/volunteer/location", json={"lat": 34.7, "lon": 10.7}, headers=headers)
    assert r.status_code == 409
    r = await client.post(
        "/api/v1/me/volunteer/readiness", json={"ready": True, "lat": 34.7, "lon": 10.7}, headers=headers
    )
    assert (r.status_code, r.json()["detail"]) == (409, "location_consent_required")
    assert await session.scalar(
        text("SELECT count(*) FROM audit.log WHERE action = 'consent.volunteer_location_withdraw' AND target = :t"),
        {"t": f"volunteer:{volunteer_id}"},
    )

    # Consent can be given again; the withdrawn one stays on record (privacy export).
    assert (await client.post(CONSENT, json=BODY, headers=headers)).status_code == 204
    rows = await session.execute(
        text(
            "SELECT withdrawn_at IS NOT NULL FROM identity.consent "
            "WHERE user_id = :u AND purpose = 'volunteer_location' ORDER BY accepted_at"
        ),
        {"u": volunteer_id},
    )
    assert [r[0] for r in rows] == [True, False]


async def test_unknown_notice_version(client: httpx.AsyncClient, citizen: Callable[[], dict[str, str]]) -> None:
    r = await client.post(CONSENT, json=BODY | {"version": "0"}, headers=citizen())
    assert (r.status_code, r.json()["detail"]) == (422, "unknown_notice_version")
    r = await client.post(CONSENT, json=BODY | {"purpose": "charter"}, headers=citizen())
    assert r.status_code == 422


def test_coarsening() -> None:
    assert [coarse_distance(m) for m in (0, 24, 26, 480, 499, 520, 1449, 1451)] == [0, 0, 50, 500, 500, 500, 1400, 1500]
    assert coarse_point(10.770312, 34.750121) == [10.77, 34.75]
