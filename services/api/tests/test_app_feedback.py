"""Rating of the app (phase P5b, F-APP-143, docs/phase-p5/design-simple.md §2.2): stars and an encrypted remark from
any reporter, a summary for the system administrator and the content editor, export and erasure."""

from collections.abc import Callable

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import TokenFactory, bearer, device_headers

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/app/feedback"
STAFF_URL = "/api/v1/staff/app-feedback"


async def _clear(session: AsyncSession) -> None:
    await session.execute(text("DELETE FROM feedback.app_rating"))
    await session.commit()


async def test_rating_with_a_remark_is_encrypted(
    client: httpx.AsyncClient, citizen: dict[str, str], session: AsyncSession
) -> None:
    body = {"stars": 4, "remark": "Simple et clair", "platform": "android", "build": 16, "version": "0.17.0"}
    r = await client.post(URL, json={**body, "locale": "fr"}, headers=citizen)
    assert r.status_code == 201, r.text
    assert r.json()["stars"] == 4
    row = (
        await session.execute(
            text("SELECT stars, remark_enc, build FROM feedback.app_rating WHERE id = :id"), {"id": r.json()["id"]}
        )
    ).one()
    assert row.stars == 4 and row.build == 16
    assert b"Simple" not in bytes(row.remark_enc)


async def test_anonymous_device_may_rate(client: httpx.AsyncClient) -> None:
    r = await client.post(URL, json={"stars": 5}, headers=device_headers())
    assert r.status_code == 201, r.text


async def test_stars_are_checked(client: httpx.AsyncClient, citizen: dict[str, str]) -> None:
    for stars in (0, 6):
        r = await client.post(URL, json={"stars": stars}, headers=citizen)
        assert r.status_code == 422
    r = await client.post(URL, json={"stars": 3, "remark": "x" * 1001}, headers=citizen)
    assert r.status_code == 422


async def test_three_ratings_a_day_per_account(client: httpx.AsyncClient, make_token: TokenFactory) -> None:
    headers = bearer(make_token(roles=["citizen"]))
    for _ in range(3):
        assert (await client.post(URL, json={"stars": 3}, headers=headers)).status_code == 201
    r = await client.post(URL, json={"stars": 3}, headers=headers)
    assert r.status_code == 429


async def test_offensive_remark_is_refused(client: httpx.AsyncClient, citizen: dict[str, str]) -> None:
    from app.modules.moderation.terms import BUILT_IN

    word = sorted(BUILT_IN)[0]
    r = await client.post(URL, json={"stars": 1, "remark": f"Application {word} vraiment"}, headers=citizen)
    assert r.status_code == 422 and r.json()["detail"] == "offensive_text"


async def test_summary_for_the_system_administrator(
    client: httpx.AsyncClient, make_token: TokenFactory, staff: Staff, session: AsyncSession
) -> None:
    await _clear(session)
    for stars, build, remark in ((5, 16, "ممتاز"), (4, 16, None), (2, 15, "بطيء عند فتح الخريطة")):
        headers = bearer(make_token(roles=["citizen"]))
        body = {"stars": stars, "build": build, "version": f"0.{build + 1}.0", "remark": remark}
        assert (await client.post(URL, json=body, headers=headers)).status_code == 201
    r = await client.get(STAFF_URL, headers=staff(["sysadmin"], gouvernorat=None))
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["count"] == 3 and out["average"] == 3.67
    assert out["by_stars"] == {"1": 0, "2": 1, "3": 0, "4": 1, "5": 1}
    assert [(b["build"], b["count"], b["average"]) for b in out["by_build"]] == [(16, 2, 4.5), (15, 1, 2.0)]
    assert [x["remark"] for x in out["remarks"]] == ["بطيء عند فتح الخريطة", "ممتاز"]
    logged = await session.scalar(text("SELECT count(*) FROM audit.log WHERE action = 'app_feedback.read'"))
    assert logged and logged >= 1


async def test_summary_is_empty_without_ratings(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    await _clear(session)
    r = await client.get(STAFF_URL, headers=staff(["content_editor"], gouvernorat=None))
    assert r.status_code == 200
    assert r.json()["count"] == 0 and r.json()["average"] is None and r.json()["remarks"] == []


async def test_summary_is_for_two_roles_only(client: httpx.AsyncClient, citizen: dict[str, str], staff: Staff) -> None:
    assert (await client.get(STAFF_URL, headers=staff(["operator"]))).status_code == 403
    assert (await client.get(STAFF_URL, headers=citizen)).status_code in (401, 403)


async def test_ratings_in_export_and_erased_with_the_account(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession
) -> None:
    headers = bearer(make_token(roles=["citizen"]))
    rated = await client.post(URL, json={"stars": 4, "remark": "Merci"}, headers=headers)
    assert rated.status_code == 201
    export = await client.get("/api/v1/me/export", headers=headers)
    assert export.status_code == 200, export.text
    assert [(x["stars"], x["remark"]) for x in export.json()["app_ratings"]] == [(4, "Merci")]
    r = await client.post("/api/v1/me/delete", json={"confirm": "DELETE"}, headers=headers)
    assert r.status_code == 202, r.text
    left = await session.scalar(
        text("SELECT count(*) FROM feedback.app_rating WHERE id = :i"), {"i": rated.json()["id"]}
    )
    assert left == 0
