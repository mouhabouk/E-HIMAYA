"""The screens the menu of 20 systems lacked (Yamen 2026-11-13): the image and video analysis centre, the forecast,
the citizens and the administrator's mother board. Each answers in the caller's scope; the mother board is the
national system administrator's alone; the danger estimate of a detection never alerts by itself."""

from collections.abc import Callable

import httpx

from app.modules.boards.router import danger

Staff = Callable[..., dict[str, str]]
GABES = 61


def test_the_danger_estimate_of_a_detection() -> None:
    assert danger("fire", 0.9, True, 0.6) == "high"
    assert danger("smoke", 0.7, False, 0.6) == "medium"
    assert danger("fire", 0.5, False, 0.6) == "low"
    assert danger("person", 0.99, True, 0.6) == "low"


async def test_the_vision_centre(client: httpx.AsyncClient, staff: Staff) -> None:
    r = await client.get("/api/v1/staff/vision/overview?hours=24", headers=staff(["operator"]))
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body["counts"]) == {"fire", "smoke", "person"}
    assert set(body["danger"]) == {"high", "medium", "low"}
    assert all(i["gouvernorat_code"] in (GABES, None) for i in body["items"])
    assert (
        await client.get("/api/v1/staff/vision/overview", headers=staff(["sysadmin"], gouvernorat=None))
    ).status_code == 403


async def test_the_forecast(client: httpx.AsyncClient, staff: Staff) -> None:
    r = await client.get("/api/v1/staff/forecast/overview", headers=staff(["ops_manager"]))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["hours"] == 48
    assert all(g["gouvernorat_code"] == GABES for g in body["gouvernorats"])
    assert all(run["gouvernorat_code"] == GABES for run in body["runs"])


async def test_the_citizens_without_identity(client: httpx.AsyncClient, staff: Staff) -> None:
    regional = (await client.get("/api/v1/staff/citizens/overview", headers=staff(["operator"]))).json()
    assert regional["national"] == {}
    assert all(g["gouvernorat_code"] == GABES for g in regional["gouvernorats"])
    national = await client.get(
        "/api/v1/staff/citizens/overview", headers=staff(["central_committee"], gouvernorat=None)
    )
    assert national.status_code == 200, national.text
    assert {"citizens", "anonymous", "organizations", "rating", "ratings"} <= set(national.json()["national"])
    # Figures only: no account, name or phone in the answer.
    text = national.text
    assert "user_id" not in text and "phone" not in text


async def test_the_mother_board_is_the_national_administrators(client: httpx.AsyncClient, staff: Staff) -> None:
    url = "/api/v1/staff/admin-board/overview"
    assert (await client.get(url, headers=staff(["sysadmin"], gouvernorat=GABES))).status_code == 403
    assert (await client.get(url, headers=staff(["central_committee"], gouvernorat=None))).status_code == 403
    r = await client.get(url, headers=staff(["sysadmin"], gouvernorat=None))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["services"]["database"] == "ok"
    assert body["services"]["notifications"] in ("real", "simulated")
    assert {"grants", "hidden", "assignments"} <= set(body["rules"])
