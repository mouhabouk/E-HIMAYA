"""Indicators out of their habit (AI4, docs/phase-l/design-l5.md §4.4): each indicator against its usual series (the
season, else the weeks before), a calm alert with its explanation, kept and audited once, in the alert centre and the
situation now, switched off in the AI settings (AI-01)."""

import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_system_sessionmaker
from app.modules.anomaly import service
from tests.test_analytics import KEF, _account, seed_report

Staff = Callable[..., dict[str, str]]
AI_SETTINGS = "/api/v1/staff/ai/settings"


def test_the_habit_and_what_leaves_it() -> None:
    steady = {b: (4.0 + (b % 3) - 1, 4) for b in range(1, 9)}
    judged = service.judge("reports", {0: (20.0, 20), **steady}, set(range(9)))
    assert judged is not None
    mean, _std, z, baseline, points = judged
    assert baseline == "recent" and points == 8 and round(mean) == 4 and z > 3
    assert service.out_of_habit("reports", 20, 20, mean, z)
    # Too short a series says nothing; a week before the first record is no zero.
    assert service.judge("reports", {0: (20.0, 20), 1: (4.0, 4)}, {1}) is None
    assert service.judge("reports", {0: (20.0, 20), **steady}, set()) is None
    # A longer arrival is out of habit, a shorter one is not; a small gap is never.
    assert service.out_of_habit("arrival", 24, 6, 14, 3.3)
    assert not service.out_of_habit("arrival", 4, 6, 14, -3.3)
    assert not service.out_of_habit("arrival", 16, 6, 14, 3.0)
    assert not service.out_of_habit("arrival", 24, 2, 14, 3.3)
    assert service.out_of_habit("completion", 0.4, 10, 0.85, -4)
    assert not service.out_of_habit("completion", 0.95, 10, 0.6, 4)


async def test_reports_out_of_habit(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    # A future year of its own: no other run writes reports there.
    now = datetime(secrets.choice(range(2400, 2900)), 6, 15, 12, tzinfo=UTC)
    async with get_system_sessionmaker()() as s, s.begin():
        user = await _account(s)
        # Four reports a week in the season and in the weeks before, then twenty this week.
        weeks = [*range(1, 9), *service.SEASON]
        for b in weeks:
            for n in range(4):
                await seed_report(s, user, now - timedelta(weeks=b, hours=6 + n), KEF)
        for n in range(20):
            await seed_report(s, user, now - timedelta(hours=2 + n), KEF)

    async with get_system_sessionmaker()() as s:
        found = await service.detect(s, now=now, codes=[KEF])
        await s.commit()
        again = await service.detect(s, now=now, codes=[KEF])
        await s.commit()
        explained = await service.explain(s, found, "fr")
    reports = next(a for a in found if a.indicator == "reports")
    assert reports.value == 20 and reports.baseline == "season" and reports.z > 3
    assert [a.id for a in again] == [a.id for a in found]
    sentence = next(e for e in explained if e["indicator"] == "reports")["text"]
    assert "Signalements dans le gouvernorat" in sentence and "20" in sentence and "4 ± 0" in sentence
    raised = await session.scalar(
        text(
            "SELECT count(*) FROM audit.log WHERE action = 'ai.anomaly_raised' "
            "AND target = :t AND details->>'value' = '20.0'"
        ),
        {"t": f"reports:g:{KEF}"},
    )
    assert raised == 1


async def test_the_alert_centre_and_the_switch(client: httpx.AsyncClient, staff: Staff) -> None:
    room = staff(["operator"], gouvernorat=KEF)
    listed = await client.get("/api/v1/staff/anomalies", params={"lang": "ar"}, headers=room)
    assert listed.status_code == 200, listed.text
    assert listed.json()["enabled"] and all(a["gouvernorat_code"] == KEF for a in listed.json()["items"])
    assert (await client.get("/api/v1/staff/anomalies", headers=staff(["citizen"], gouvernorat=KEF))).status_code == 403
    centre = staff(["ops_manager"], gouvernorat=None)
    now = await client.get("/api/v1/staff/window/now", headers=centre)
    assert now.status_code == 200 and now.json()["anomalies"] is not None

    committee = staff(["central_committee"], gouvernorat=None)
    settings = (await client.get(AI_SETTINGS, headers=committee)).json()
    off = {**settings, "assist": {**settings["assist"], "anomalies": False}}
    try:
        assert (await client.put(AI_SETTINGS, json=off, headers=committee)).status_code == 200
        quiet = (await client.get("/api/v1/staff/anomalies", headers=room)).json()
        assert quiet == {"enabled": False, "items": []}
        assert (await client.get("/api/v1/staff/window/now", headers=centre)).json()["anomalies"] is None
    finally:
        await client.put(AI_SETTINGS, json=settings, headers=committee)


async def test_completion_out_of_habit() -> None:
    now = datetime(secrets.choice(range(2400, 2900)), 3, 20, 18, tzinfo=UTC)
    today = now.date()
    async with get_system_sessionmaker()() as s, s.begin():
        # Nine weeks of approved programmes: everything done, then three in ten this week.
        for b in range(9):
            start = today - timedelta(days=7 * b + 6)
            period = await s.scalar(
                text(
                    "INSERT INTO sched.period (gouvernorat_code, span, starts_on, ends_on, status) "
                    "VALUES (:g, 'week', :s, :e, 'approved') RETURNING id"
                ),
                {"g": KEF, "s": start, "e": start + timedelta(days=6)},
            )
            for n in range(10):
                state = "done" if b > 0 or n < 3 else "not_done"
                await s.execute(
                    text(
                        "INSERT INTO sched.item (period_id, gouvernorat_code, activity, title, on_date, status, "
                        "status_manual, status_reason) VALUES (:p, :g, 'patrol', '[SIM] دورية', :d, :st, true, :r)"
                    ),
                    {"p": period, "g": KEF, "d": start + timedelta(days=n % 7), "st": state, "r": "[SIM] سبب"},
                )
    async with get_system_sessionmaker()() as s:
        found = await service.detect(s, now=now, codes=[KEF])
        await s.commit()
        explained = await service.explain(s, found, "ar")
    completion = next(a for a in found if a.indicator == "completion")
    assert completion.value == 0.3 and completion.mean == 1 and completion.baseline == "recent"
    assert "30 %" in next(e for e in explained if e["indicator"] == "completion")["text"]
