"""Suggested activities in the programmes (AI3, docs/phase-l/design-l5.md §4.3): the forecast, the red beaches, the
season and a rise each suggest an activity with its reasons; the room accepts it (an activity with the AI label,
approved as usual) or sets it aside; both are audited; the AI settings switch them off (AI-01)."""

import secrets
from datetime import UTC, date, datetime, time, timedelta

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_system_sessionmaker
from app.modules.schedule import domain, suggest
from app.modules.weather.models import GridPoint, Observation
from tests.test_analytics import seed_incident
from tests.test_schedule import GABES, URL, Staff, add, item, step, week

AI_SETTINGS = "/api/v1/staff/ai/settings"


def future_monday() -> date:
    """A Monday of a future year of its own: every day of its week is still ahead, and no other run shares it."""
    day = date(secrets.choice(range(2200, 2900)), secrets.choice(range(1, 13)), 10)
    return day - timedelta(days=day.weekday())


async def forecast(code: int, observations: list[tuple[date, str | None, str]]) -> None:
    """A [SIM] grid point of the gouvernorat and its forecast at noon of the given days."""
    lat, lon = 33.8 + secrets.randbelow(900) / 10_000, 10.0 + secrets.randbelow(900) / 10_000
    async with get_system_sessionmaker()() as s, s.begin():
        point = 800_000 + secrets.randbelow(99_999)
        s.add(
            GridPoint(
                id=point,
                lat=lat,
                lon=lon,
                location=f"SRID=4326;POINT({lon} {lat})",
                gouvernorat_code=code,
                source="sim",
                simulated=True,
            )
        )
        await s.flush()
        for day, danger, rain in observations:
            s.add(
                Observation(
                    point_id=point,
                    at=datetime.combine(day, time(12), domain.TUNIS),
                    fire_danger=danger,
                    heavy_rain=rain,
                    forecast=True,
                )
            )


def test_the_window_is_the_days_still_ahead() -> None:
    start = date(2026, 10, 26)
    assert suggest.window(start, start + timedelta(days=6), date(2026, 10, 29))[0] == date(2026, 10, 29)
    assert len(suggest.window(start, start + timedelta(days=6), date(2026, 10, 20))) == 7
    assert suggest.window(start, start + timedelta(days=6), date(2026, 11, 3)) == []


async def test_suggestions_accepted_or_set_aside(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession
) -> None:
    room = staff(["operator"], gouvernorat=GABES)
    monday = future_monday()
    hot, wet = monday + timedelta(days=1), monday + timedelta(days=3)
    await forecast(GABES, [(hot, "very_high", "none"), (wet, "low", "warning"), (monday, "moderate", "none")])
    period = await week(client, room, monday)
    pid = period["period"]["id"]

    listed = await client.get(f"{URL}/periods/{pid}/suggestions", params={"lang": "fr"}, headers=room)
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["enabled"] and body["can_accept"]
    found = {s["key"]: s for s in body["items"]}
    fire, flood = found[f"fire_patrol:{hot.isoformat()}"], found[f"flood_readiness:{wet.isoformat()}"]
    assert fire["activity"] == "patrol" and fire["on_date"] == hot.isoformat() and fire["simulated"]
    assert "très élevé" in fire["title"] and fire["reasons"]
    # The check comes the day before the rain.
    assert flood["activity"] == "readiness_check" and flood["on_date"] == (wet - timedelta(days=1)).isoformat()
    # A moderate danger calls nothing.
    assert f"fire_patrol:{monday.isoformat()}" not in found

    # Another gouvernorat's room neither reads nor takes them.
    other = staff(["operator"], gouvernorat=23)
    assert (await client.get(f"{URL}/periods/{pid}/suggestions", headers=other)).status_code == 404

    accept = f"{URL}/periods/{pid}/suggestions/{fire['key']}/accept"
    stale = await client.post(accept, json={"version": 0}, headers=room)
    assert stale.status_code == 409
    taken = await client.post(accept, json={"version": period["period"]["version"], "lang": "fr"}, headers=room)
    assert taken.status_code == 200, taken.text
    activity = next(i for i in taken.json()["items"] if i["suggested"])
    assert activity["title"] == fire["title"] and activity["on_date"] == hot.isoformat()
    assert "[données simulées]" in activity["notes"]
    again = await client.post(accept, json={"version": taken.json()["period"]["version"]}, headers=room)
    assert (again.status_code, again.json()["detail"]) == (409, "suggestion_gone")

    dismiss = f"{URL}/periods/{pid}/suggestions/{flood['key']}/dismiss"
    assert (await client.post(dismiss, json={"reason": "المعدات جاهزة"}, headers=room)).status_code == 204
    left = {s["key"] for s in (await client.get(f"{URL}/periods/{pid}/suggestions", headers=room)).json()["items"]}
    assert fire["key"] not in left and flood["key"] not in left
    logged = (
        await session.execute(
            text(
                "SELECT action, details->>'key' FROM audit.log WHERE target = :t "
                "AND action LIKE 'schedule.suggestion_%' ORDER BY id"
            ),
            {"t": pid},
        )
    ).all()
    assert [tuple(r) for r in logged] == [
        ("schedule.suggestion_accepted", fire["key"]),
        ("schedule.suggestion_dismissed", flood["key"]),
    ]

    # Switched off in the AI settings: nothing is suggested and nothing is taken (AI-01).
    committee = staff(["central_committee"], gouvernorat=None)
    settings = (await client.get(AI_SETTINGS, headers=committee)).json()
    off = {**settings, "assist": {**settings["assist"], "programme_suggestions": False}}
    try:
        assert (await client.put(AI_SETTINGS, json=off, headers=committee)).status_code == 200
        quiet = (await client.get(f"{URL}/periods/{pid}/suggestions", headers=room)).json()
        assert quiet == {"enabled": False, "can_accept": False, "items": []}
        refused = await client.post(dismiss, json={}, headers=room)
        assert (refused.status_code, refused.json()["detail"]) == (409, "suggestions_off")
    finally:
        await client.put(AI_SETTINGS, json=settings, headers=committee)

    # Once sent for approval, the programme is locked and takes no suggestion.
    detail = await add(client, room, period, item(monday))
    assert (await step(client, room, detail, "submit")).status_code == 200
    locked = (await client.get(f"{URL}/periods/{pid}/suggestions", headers=room)).json()
    assert locked["enabled"] and not locked["can_accept"] and locked["items"] == []


async def test_season_and_rise_from_the_incidents() -> None:
    monday = future_monday()
    days = [monday + timedelta(days=n) for n in range(7)]
    now = datetime.combine(monday, time(8), domain.TUNIS).astimezone(UTC)
    code = 82  # Sidi Bouzid: few other tests write incidents there.
    async with get_system_sessionmaker()() as s, s.begin():
        # Fires on the same days of each of the past three years.
        for years in (1, 2, 3):
            for n in (0, 2):
                at = datetime.combine(days[n] - timedelta(weeks=52 * years), time(14), domain.TUNIS)
                await seed_incident(s, code, "fire", at)
        # Drownings in the last days, none before.
        for n in (2, 5, 9):
            await seed_incident(s, code, "drowning", now - timedelta(days=n))
    async with get_system_sessionmaker()() as s:
        found = await suggest.suggestions(s, code, days[0], days[-1], now, "fr", set(), set())
        keys = {x.key: x for x in found}
        assert keys["season:fire"].activity == "prevention_visit" and keys["season:fire"].on_date == days[0]
        assert "6 interventions" in keys["season:fire"].reasons[0]
        assert keys["rise:drowning"].activity == "readiness_check"
        # What the room already set aside stays aside.
        aside = await suggest.suggestions(s, code, days[0], days[-1], now, "ar", {"season:fire"}, set())
        assert "season:fire" not in {x.key for x in aside}
