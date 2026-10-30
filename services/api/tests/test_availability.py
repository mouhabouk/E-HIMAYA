"""Availability calendar of volunteers and doctors (phase N, docs/phase-n/design-n.md §8)."""

from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.availability.domain import TUNIS, Slot, covers, planned_state
from tests.test_operations import Staff, approved_volunteer, citizen_user, near, new_incident, random_place

__all__ = ["citizen_user"]

ME = "/api/v1/me/availability"


def test_slots_cover_their_days_and_hours() -> None:
    # Wednesday 2026-11-04, 22:30 in Tunis.
    at = datetime(2026, 11, 4, 22, 30, tzinfo=TUNIS).astimezone(UTC)
    nights = Slot("available", (), date(2026, 11, 1), None, time(20), time(6))
    weekend = Slot("available", (6, 7), date(2026, 11, 1), None, time(8), time(20))
    trip = Slot("unavailable", (), date(2026, 11, 3), date(2026, 11, 5), time(0), time(23, 59))
    assert covers(nights, at) and not covers(weekend, at) and covers(trip, at)
    assert planned_state([nights], at) == "available"
    # A planned absence wins over a recurring presence.
    assert planned_state([nights, trip], at) == "unavailable"
    assert planned_state([weekend], at) is None
    assert not covers(trip, datetime(2026, 11, 6, 10, tzinfo=TUNIS))


def _around_now(kind: str) -> dict[str, Any]:
    local = datetime.now(TUNIS)
    return {
        "kind": kind,
        "starts_on": (local.date() - timedelta(days=1)).isoformat(),
        "from_time": (local - timedelta(hours=1)).time().replace(microsecond=0).isoformat(),
        "to_time": (local + timedelta(hours=1)).time().replace(microsecond=0).isoformat(),
    }


async def test_calendar_keeps_the_call_up_away_and_shows_to_the_staff(
    client: httpx.AsyncClient,
    staff: Staff,
    citizen_user: Callable[[], dict[str, str]],
    session: AsyncSession,
    channels: Any,
) -> None:
    headers = citizen_user()
    # Only a declared volunteer keeps a calendar under that role.
    r = await client.get(ME, params={"role": "volunteer"}, headers=headers)
    assert r.status_code == 404 and r.json()["detail"] == "not_a_volunteer"

    place = random_place()
    incident_id, _ = await new_incident(client, staff, place)
    volunteer_id = await approved_volunteer(client, staff, headers, near(place, 0.01))
    mine = (await client.get(ME, params={"role": "volunteer"}, headers=headers)).json()
    assert mine == {"role": "volunteer", "slots": [], "planned_now": None}

    bad = {
        "kind": "available",
        "starts_on": "2026-11-05",
        "ends_on": "2026-11-01",
        "from_time": "08:00",
        "to_time": "12:00",
    }
    assert (
        await client.put(ME, params={"role": "volunteer"}, json={"slots": [bad]}, headers=headers)
    ).status_code == 422
    empty = {**bad, "ends_on": None, "to_time": "08:00"}
    assert (
        await client.put(ME, params={"role": "volunteer"}, json={"slots": [empty]}, headers=headers)
    ).status_code == 422
    many = {"slots": [_around_now("available")] * 21}
    assert (await client.put(ME, params={"role": "volunteer"}, json=many, headers=headers)).status_code == 422

    suggest = f"/api/v1/staff/incidents/{incident_id}/volunteer-suggestions?skill=diving&radius_km=10"
    operator = staff(["operator"])
    assert volunteer_id in [s["volunteer_id"] for s in (await client.get(suggest, headers=operator)).json()]

    away = {"slots": [_around_now("available"), _around_now("unavailable")]}
    r = await client.put(ME, params={"role": "volunteer"}, json=away, headers=headers)
    assert r.status_code == 200, r.text
    assert len(r.json()["slots"]) == 2 and r.json()["planned_now"] == "unavailable"
    state = await session.scalar(
        text("SELECT identity.planned_state(CAST(:u AS uuid), 'volunteer', now())"), {"u": volunteer_id}
    )
    assert state == "unavailable"
    # The call-up does not suggest them while the calendar says unavailable.
    assert volunteer_id not in [s["volunteer_id"] for s in (await client.get(suggest, headers=operator)).json()]
    detail = (await client.get(f"/api/v1/staff/volunteers/{volunteer_id}", headers=operator)).json()
    assert detail["calendar"]["planned_now"] == "unavailable" and len(detail["calendar"]["slots"]) == 2

    back = {"slots": [_around_now("available")]}
    r = await client.put(ME, params={"role": "volunteer"}, json=back, headers=headers)
    assert r.json()["planned_now"] == "available"
    assert volunteer_id in [s["volunteer_id"] for s in (await client.get(suggest, headers=operator)).json()]
    audited = await session.scalar(
        text("SELECT count(*) FROM audit.log WHERE action = 'availability.replace' AND target = :t"),
        {"t": f"volunteer:{volunteer_id}"},
    )
    assert audited == 2

    # Right of access, then erasure: the calendar goes with the account.
    exported = (await client.get("/api/v1/me/export", headers=headers)).json()
    assert len(exported["availability"]) == 1
    r = await client.post("/api/v1/me/delete", json={"confirm": "DELETE"}, headers=headers)
    assert r.status_code == 202, r.text
    left = await session.scalar(
        text("SELECT count(*) FROM identity.availability_slot WHERE user_id = CAST(:u AS uuid)"), {"u": volunteer_id}
    )
    assert left == 0
