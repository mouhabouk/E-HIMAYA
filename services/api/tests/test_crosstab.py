"""Statistical cross-tabulations and their findings (Yamen, 2026-11-01): counts across two dimensions beside the same
period a year earlier, and the sentence "ارتفاع في عدد حرائق المحاصيل الزراعية بنسبة 15%"."""

import uuid
from collections.abc import Callable

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

Staff = Callable[..., dict[str, str]]
KEBILI = 73
URL = "/api/v1/staff/analytics"


async def _incidents(session: AsyncSession, year: int, count: int, classification: str, month: int = 7) -> None:
    for i in range(count):
        await session.execute(
            text(
                "INSERT INTO ops.incident "
                "(id, category, classification, centroid, gouvernorat_code, status, opened_at) "
                "VALUES (:id, 'fire', :c, ST_SetSRID(ST_MakePoint(8.97, 33.70), 4326)::geography, :g, 'closed', "
                "make_timestamptz(:y, :m, 1 + :d, 14, 0, 0, 'Africa/Tunis'))"
            ),
            {"id": uuid.uuid4(), "c": classification, "g": KEBILI, "y": year, "m": month, "d": i % 27},
        )
    await session.commit()


async def test_crop_fires_rise_fifteen_percent(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    await session.execute(
        text("DELETE FROM ops.incident WHERE gouvernorat_code = :g AND opened_at < '2020-01-01'"), {"g": KEBILI}
    )
    await _incidents(session, 2018, 20, "crop_fire")
    await _incidents(session, 2019, 23, "crop_fire")
    await _incidents(session, 2018, 10, "forest_fire", month=8)
    await _incidents(session, 2019, 6, "forest_fire", month=8)
    period = {"from": "2019-01-01", "to": "2019-12-31", "gouvernorat": KEBILI}

    room = staff(["local_committee"], KEBILI)
    r = await client.get(f"{URL}/crosstab", params={**period, "rows": "classification", "cols": "month"}, headers=room)
    assert r.status_code == 200, r.text
    table = r.json()
    assert table["previous_from"] == "2018-01-01" and table["col_keys"] == ["7", "8"]
    crops = table["row_keys"].index("crop_fire")
    assert table["cells"][crops][0] == {"count": 23, "previous": 20, "change_pct": 15.0}
    assert table["row_totals"][table["row_keys"].index("forest_fire")]["change_pct"] == -40.0

    found = (await client.get(f"{URL}/findings", params=period, headers=room)).json()
    texts = [f["text_ar"] for f in found]
    assert "ارتفاع في عدد حرائق المحاصيل الزراعية بنسبة 15% مقارنة بالسنة الفارطة (23 مقابل 20)" in texts
    assert any(t.startswith("انخفاض في عدد حرائق الغابات بنسبة 40%") for t in texts)

    # Scope and validation, as the other analytics.
    other = await client.get(f"{URL}/crosstab", params=period, headers=staff(["local_committee"], 61))
    assert other.status_code == 403
    same = await client.get(f"{URL}/crosstab", params={**period, "rows": "month", "cols": "month"}, headers=room)
    assert same.status_code == 422
    resources = await client.get(
        f"{URL}/crosstab", params={**period, "rows": "category", "cols": "resource"}, headers=room
    )
    assert resources.status_code == 200 and resources.json()["col_keys"] == ["none"]
