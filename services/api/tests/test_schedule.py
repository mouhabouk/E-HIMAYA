"""Daily, weekly and monthly programmes (phase PL2, docs/phase-pl/design-plans.md §3): the calendar rules, the approval
path each gouvernorat chooses, the activities and their checks, the follow-up and its progress, the copy of the previous
period, and who sees what (a room its own gouvernorat, the governor the progress only)."""

import secrets
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import httpx

from app.modules.schedule import domain

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/staff/schedule"
GABES, BIZERTE = 61, 23


def monday() -> date:
    """A Monday of a past year of its own, so a reused database does not mix the programmes of two runs."""
    day = date(secrets.choice(range(1200, 1999)), secrets.choice(range(1, 13)), 10)
    return day - timedelta(days=day.weekday())


def item(on: date, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "activity": "patrol",
        "title": "[SIM] دورية الشواطئ",
        "on_date": on.isoformat(),
        "starts_at": "08:00",
        "ends_at": "12:00",
        "responsible": "رئيس الوحدة",
        "staff_count": 4,
    }
    body.update(overrides)
    return body


async def setting(client: httpx.AsyncClient, staff: Staff, code: int, approval: str) -> None:
    r = await client.put(
        f"{URL}/settings/{code}", json={"approval": approval}, headers=staff(["ops_manager"], gouvernorat=code)
    )
    assert r.status_code == 200, r.text


async def week(client: httpx.AsyncClient, headers: dict[str, str], on: date, **extra: Any) -> dict[str, Any]:
    r = await client.post(f"{URL}/periods", json={"span": "week", "on": on.isoformat(), **extra}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


async def add(
    client: httpx.AsyncClient, headers: dict[str, str], period: dict[str, Any], body: dict[str, Any]
) -> dict[str, Any]:
    r = await client.post(f"{URL}/periods/{period['period']['id']}/items", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


async def step(
    client: httpx.AsyncClient, headers: dict[str, str], detail: dict[str, Any], action: str, **extra: Any
) -> httpx.Response:
    p = detail["period"]
    return await client.post(
        f"{URL}/periods/{p['id']}/{action}", json={"version": p["version"], **extra}, headers=headers
    )


def test_calendar_rules() -> None:
    assert domain.bounds("week", date(2026, 10, 28)) == (date(2026, 10, 26), date(2026, 11, 1))
    assert domain.bounds("month", date(2026, 2, 14)) == (date(2026, 2, 1), date(2026, 2, 28))
    assert domain.previous_start("month", date(2026, 3, 1)) == date(2026, 2, 1)
    assert domain.previous_start("week", date(2026, 10, 26)) == date(2026, 10, 19)
    assert domain.expand("weekdays", date(2026, 10, 28), date(2026, 11, 1)) == [
        date(2026, 10, 28),
        date(2026, 10, 29),
        date(2026, 10, 30),
    ]
    assert domain.expand("weekly", date(2026, 10, 1), date(2026, 10, 31)) == [
        date(2026, 10, d) for d in (1, 8, 15, 22, 29)
    ]
    # The 31st of a month has no place in a shorter one.
    assert domain.place(30, date(2026, 2, 1), date(2026, 2, 28)) is None
    assert domain.place(2, date(2026, 10, 26), date(2026, 11, 1)) == date(2026, 10, 28)


async def test_each_gouvernorat_approves_its_own_way(client: httpx.AsyncClient, staff: Staff) -> None:
    gabes_room, gabes_head = staff(["operator"], gouvernorat=GABES), staff(["ops_manager"], gouvernorat=GABES)
    # A gouvernorat chooses for itself only.
    r = await client.put(f"{URL}/settings/{BIZERTE}", json={"approval": "direct"}, headers=gabes_head)
    assert r.status_code == 403
    assert (
        await client.put(f"{URL}/settings/{GABES}", json={"approval": "head"}, headers=gabes_room)
    ).status_code == 403

    await setting(client, staff, GABES, "head")
    on = monday()
    p = await week(client, gabes_room, on)
    assert (await step(client, gabes_room, p, "submit")).json()["detail"] == "no_items"
    # Every working day of the week, one series.
    p = await add(client, gabes_room, p, item(on, repeat="weekdays"))
    assert [i["on_date"] for i in p["items"]] == [(on + timedelta(days=d)).isoformat() for d in range(5)]
    assert len({i["series_id"] for i in p["items"]}) == 1
    r = await step(client, gabes_room, p, "submit")
    assert r.status_code == 200 and r.json()["period"]["status"] == "submitted"
    p = r.json()
    # Locked while it waits; the room does not approve it, the head of the room does.
    r = await client.put(f"{URL}/items/{p['items'][0]['id']}", json=item(on, title="تعديل"), headers=gabes_room)
    assert r.status_code == 409 and r.json()["detail"] == "period_locked"
    assert (await step(client, gabes_room, p, "approve")).status_code == 403
    r = await step(client, gabes_head, p, "approve")
    assert r.json()["period"]["status"] == "approved" and r.json()["period"]["approved_at"]

    # Bizerte wants the central room too; the path is kept when the programme is sent.
    await setting(client, staff, BIZERTE, "head_and_centre")
    bizerte_room = staff(["operator"], gouvernorat=BIZERTE)
    p = await add(client, bizerte_room, await week(client, bizerte_room, on), item(on, activity="exercise"))
    p = (await step(client, bizerte_room, p, "submit")).json()
    await setting(client, staff, BIZERTE, "direct")
    p = (await step(client, staff(["ops_manager"], gouvernorat=BIZERTE), p, "approve")).json()
    assert p["period"]["status"] == "awaiting_centre" and p["period"]["approval"] == "head_and_centre"
    assert (await step(client, staff(["ops_manager"], gouvernorat=BIZERTE), p, "approve")).status_code == 403
    r = await step(client, staff(["central_committee"], gouvernorat=None), p, "return", reason="أضيفوا تمرين الإخلاء")
    assert r.json()["period"]["status"] == "returned"
    p = (await step(client, bizerte_room, r.json(), "submit")).json()
    # Now published as soon as it is sent.
    assert p["period"]["status"] == "approved" and p["period"]["approval"] == "direct"


async def test_activities_are_checked(client: httpx.AsyncClient, staff: Staff) -> None:
    room = staff(["operator"], gouvernorat=GABES)
    on = monday()
    p = await week(client, room, on)
    pid = p["period"]["id"]
    bad = [
        (item(on + timedelta(days=7)), "date_outside_period"),
        (item(on, starts_at="12:00", ends_at="08:00"), "hours_reversed"),
        (item(on, resources=[{"category_key": "zz_unknown", "qty": 1}]), "category_unknown"),
        (item(on, unit_id="00000000-0000-0000-0000-000000000000"), "unit_not_found"),
    ]
    for body, code in bad:
        r = await client.post(f"{URL}/periods/{pid}/items", json=body, headers=room)
        assert r.status_code == 422 and r.json()["detail"] == code, (code, r.text)
    p = await add(client, room, p, item(on, activity="maintenance", resources=[{"category_key": "pump", "qty": 2}]))
    assert p["items"][0]["resources"][0]["name"]["ar"] == "مضخة"
    # Another gouvernorat's room does not see it; the central room does.
    assert (
        await client.get(f"{URL}/periods/{pid}", headers=staff(["operator"], gouvernorat=BIZERTE))
    ).status_code == 404
    assert (await client.get(f"{URL}/periods/{pid}", headers=staff(["operator"], gouvernorat=None))).status_code == 200
    # A series is removed at once.
    p = await add(client, room, p, item(on, repeat="daily"))
    sid = next(i["id"] for i in p["items"] if i["series_id"])
    r = await client.delete(f"{URL}/items/{sid}", params={"series": "true"}, headers=room)
    assert len(r.json()["items"]) == 1


async def test_follow_up_progress_and_copy(client: httpx.AsyncClient, staff: Staff) -> None:
    await setting(client, staff, GABES, "direct")
    room = staff(["operator"], gouvernorat=GABES)
    on = monday()
    p = await add(client, room, await week(client, room, on), item(on, repeat="daily"))
    p = (await step(client, room, p, "submit")).json()
    assert p["period"]["status"] == "approved" and p["can_follow_up"]
    first, second, third = p["items"][:3]
    await client.post(f"{URL}/items/{first['id']}/status", json={"status": "done"}, headers=room)
    r = await client.post(f"{URL}/items/{second['id']}/status", json={"status": "postponed"}, headers=room)
    assert r.status_code == 422 and r.json()["detail"] == "reason_required"
    await client.post(
        f"{URL}/items/{second['id']}/status", json={"status": "postponed", "reason": "عطب في الآلية"}, headers=room
    )
    r = await client.post(
        f"{URL}/items/{third['id']}/status", json={"status": "cancelled", "reason": "رياح قوية"}, headers=room
    )
    counts = r.json()["period"]["counts"]
    assert counts == {"items": 7, "due": 6, "done": 1, "postponed": 1, "cancelled": 1, "rate": 0.167}

    # The central room sees the progress of every gouvernorat; the governor of Gabes its own, without the list.
    progress = (
        await client.get(
            f"{URL}/progress",
            params={"span": "week", "on": on.isoformat()},
            headers=staff(["central_committee"], gouvernorat=None),
        )
    ).json()
    gabes = next(row for row in progress["rows"] if row["gouvernorat_code"] == GABES)
    assert gabes["status"] == "approved" and gabes["counts"]["done"] == 1 and len(progress["rows"]) == 24
    governor = staff(["governor"], gouvernorat=GABES)
    mine = (await client.get(f"{URL}/progress", params={"span": "week", "on": on.isoformat()}, headers=governor)).json()
    assert [row["gouvernorat_code"] for row in mine["rows"]] == [GABES] and not mine["lists"]
    assert (await client.get(f"{URL}/periods/{p['period']['id']}", headers=governor)).status_code == 403

    # The next week starts from this one: same days of the week, the follow-up starts again.
    nxt = await week(client, room, on + timedelta(days=7))
    assert nxt["previous_id"] == p["period"]["id"]
    copied = (await step(client, room, nxt, "copy-previous")).json()
    assert [i["on_date"] for i in copied["items"]] == [(on + timedelta(days=7 + d)).isoformat() for d in range(7)]
    assert {i["status"] for i in copied["items"]} == {"planned"}
    slot = (
        await client.get(
            f"{URL}/slot", params={"span": "week", "on": (on + timedelta(days=9)).isoformat()}, headers=room
        )
    ).json()
    assert slot["period"]["period"]["id"] == nxt["period"]["id"] and not slot["can_create"]


async def test_a_programme_kept_as_a_template(client: httpx.AsyncClient, staff: Staff) -> None:
    """A programme repeats (Yamen, 2026-10-28): it is kept once under a name and applied to the next periods."""
    room = staff(["operator"], gouvernorat=GABES)
    on = monday()
    p = await add(client, room, await week(client, room, on), item(on, activity="duty", repeat="daily"))
    p = await add(client, room, p, item(on + timedelta(days=2), activity="exercise", title="تمرين الإخلاء"))
    name = f"الأسبوع العادي {secrets.token_hex(3)}"
    r = await client.post(f"{URL}/periods/{p['period']['id']}/template", json={"name": name}, headers=room)
    assert r.status_code == 201, r.text
    template = r.json()
    assert template["items"] == 8 and template["activities"] == {"duty": 7, "exercise": 1}
    # Saved again under the same name, it is replaced; another gouvernorat does not see it.
    r = await client.post(f"{URL}/periods/{p['period']['id']}/template", json={"name": name}, headers=room)
    assert r.json()["id"] == template["id"]
    listed = (await client.get(f"{URL}/templates", params={"span": "week"}, headers=room)).json()
    assert template["id"] in {t["id"] for t in listed}
    other = (await client.get(f"{URL}/templates", headers=staff(["operator"], gouvernorat=BIZERTE))).json()
    assert template["id"] not in {t["id"] for t in other}

    # Three weeks later, the template fills the new week, each activity on its day.
    later = await week(client, room, on + timedelta(days=21))
    r = await step(client, room, later, "apply-template", template_id=template["id"])
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 8 and {i["status"] for i in items} == {"planned"}
    exercise = next(i for i in items if i["activity"] == "exercise")
    assert exercise["on_date"] == (on + timedelta(days=23)).isoformat()
    assert len({i["series_id"] for i in items if i["activity"] == "duty"}) == 1
    # A day's template does not fit a week.
    day = (await client.post(f"{URL}/periods", json={"span": "day", "on": on.isoformat()}, headers=room)).json()
    r = await step(client, room, day, "apply-template", template_id=template["id"])
    assert r.status_code == 422 and r.json()["detail"] == "template_mismatch"
    assert (await client.delete(f"{URL}/templates/{template['id']}", headers=room)).status_code == 204
