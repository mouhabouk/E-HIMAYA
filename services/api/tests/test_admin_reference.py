# covers: FR-M-01, FR-M-02, FR-M-03, FR-M-04, FR-M-07
"""Administrative reference of phase M (docs/phase-m/design-m.md): the Map Tunisia boundaries of migration 0079, the
administrative address of every report, the boundaries for the maps and the reports per délégation."""

from collections.abc import Callable

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.geo import router as geo_router
from tests.conftest import SFAX, TUNIS, accept_charter, report_body

Staff = Callable[..., dict[str, str]]


async def test_the_reference_is_complete_and_nested(session: AsyncSession) -> None:
    counts = (
        await session.execute(
            text(
                "SELECT (SELECT count(*) FROM geo.gouvernorat WHERE ins_code IS NOT NULL AND population_2024 > 0),"
                " (SELECT count(*) FROM geo.delegation WHERE ins_code IS NOT NULL AND boundary IS NOT NULL),"
                " (SELECT count(*) FROM geo.sector), (SELECT count(*) FROM geo.municipality),"
                " (SELECT count(*) FROM geo.economic_region), (SELECT count(*) FROM geo.district),"
                " (SELECT count(*) FROM geo.city), (SELECT count(*) FROM geo.water_body)"
            )
        )
    ).one()
    assert tuple(counts) == (24, 279, 2083, 338, 7, 5, 284, 67)
    # The census adds up: the délégations of each gouvernorat hold its whole 2024 population.
    mismatched = await session.scalar(
        text(
            "SELECT count(*) FROM geo.gouvernorat g WHERE g.population_2024 <> "
            "(SELECT sum(d.population_2024) FROM geo.delegation d WHERE d.gouvernorat_code = g.code)"
        )
    )
    assert mismatched == 0
    # Every imada lies in its délégation's gouvernorat; our ids and names are unchanged (Sfax Ville is still 6114).
    assert (
        await session.scalar(
            text(
                "SELECT count(*) FROM geo.sector s JOIN geo.delegation d ON d.id = s.delegation_id "
                "WHERE s.gouvernorat_code <> d.gouvernorat_code"
            )
        )
        == 0
    )
    sfax = (await session.execute(text("SELECT id, ins_code FROM geo.delegation WHERE name_fr = 'Sfax Ville'"))).one()
    assert tuple(sfax) == (6114, "3451")


async def test_a_report_gets_its_delegation_imada_and_municipality(
    client: httpx.AsyncClient, citizen: dict[str, str], staff: Staff
) -> None:
    await accept_charter(client, citizen)
    r = await client.post("/api/v1/reports", json=report_body(SFAX), headers=citizen)
    assert r.status_code == 201, r.text
    detail = (await client.get(f"/api/v1/staff/reports/{r.json()['id']}", headers=staff())).json()
    assert detail["delegation_id"] == 6114
    address = detail["address"]
    assert address["delegation"]["name_fr"] == "Sfax Ville"
    assert address["sector"]["id"] == "345151"
    # The municipality of Sfax is one of the 12 OpenStreetMap does not outline yet (docs/phase-m/design-m.md §6).
    assert address["municipality"] is None
    r = await client.post("/api/v1/reports", json=report_body(TUNIS), headers=citizen)
    tunis = (await client.get(f"/api/v1/staff/reports/{r.json()['id']}", headers=staff(gouvernorat=11))).json()
    assert tunis["address"]["municipality"]["name_fr"] == "Tunis"

    # At sea there is no administrative address (the geo-verification queue decides, phase 9).
    r = await client.post(
        "/api/v1/reports", json=report_body({"lat": 34.70, "lon": 10.86, "accuracy_m": 10.0}), headers=citizen
    )
    detail = (await client.get(f"/api/v1/staff/reports/{r.json()['id']}", headers=staff(gouvernorat=None))).json()
    assert detail["delegation_id"] is None and detail["address"] is None


async def test_boundaries_of_each_level(client: httpx.AsyncClient) -> None:
    geo_router._boundaries.clear()
    r = await client.get("/api/v1/geo/boundaries/gouvernorats", params={"detail": "low"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/geo+json")
    body = r.json()
    assert len(body["features"]) == 24 and "Map Tunisia" in body["attribution"]
    sfax = next(f for f in body["features"] if f["id"] == 61)
    assert sfax["properties"]["name_ar"] == "صفاقس" and sfax["properties"]["region"] == "centre-est"
    assert sfax["geometry"]["type"] == "MultiPolygon"

    delegations = (await client.get("/api/v1/geo/boundaries/delegations", params={"gouvernorat": 61})).json()
    assert len(delegations["features"]) == 16
    assert all(f["properties"]["population_2024"] > 0 for f in delegations["features"])

    regions = (await client.get("/api/v1/geo/boundaries/regions", params={"detail": "low"})).json()
    assert len(regions["features"]) == 7
    assert sum(f["properties"]["population_2024"] for f in regions["features"]) == 11_972_169

    cities = (await client.get("/api/v1/geo/boundaries/cities")).json()
    assert len(cities["features"]) == 284 and cities["features"][0]["geometry"]["type"] == "Point"
    assert (await client.get("/api/v1/geo/boundaries/streets")).status_code == 422


async def test_locate_needs_a_signed_in_user(client: httpx.AsyncClient, staff: Staff) -> None:
    params = {"lat": TUNIS["lat"], "lon": TUNIS["lon"]}
    assert (await client.get("/api/v1/geo/locate", params=params)).status_code == 401
    r = await client.get("/api/v1/geo/locate", params=params, headers=staff())
    assert r.status_code == 200
    assert r.json()["delegation"]["name_fr"] and r.json()["municipality"]["name_fr"] == "Tunis"


async def test_reports_per_delegation_follow_the_scope(
    client: httpx.AsyncClient, citizen: dict[str, str], staff: Staff
) -> None:
    await accept_charter(client, citizen)
    for place in (SFAX, SFAX, TUNIS):
        assert (await client.post("/api/v1/reports", json=report_body(place), headers=citizen)).status_code == 201
    national = {
        c["delegation_id"]: c["count"]
        for c in (await client.get("/api/v1/staff/kpis/delegations", headers=staff(gouvernorat=None))).json()
    }
    assert national[6114] >= 2 and any(d // 100 == 11 for d in national)
    regional = (await client.get("/api/v1/staff/kpis/delegations", headers=staff(gouvernorat=61))).json()
    assert regional and all(c["delegation_id"] // 100 == 61 for c in regional)


async def test_an_alert_to_some_delegations(client: httpx.AsyncClient, staff: Staff) -> None:
    from tests.test_notifications import active_ids, alert_body, drain

    central = staff(["central_committee"], gouvernorat=None)
    post = lambda body, headers=central: client.post("/api/v1/staff/notifications", json=body, headers=headers)  # noqa: E731
    for area, code in (
        ({"delegation_ids": [9999]}, "invalid_delegation"),
        ({"delegation_ids": [6114], "gouvernorat_codes": [61]}, "invalid_area"),
    ):
        r = await post(alert_body(area=area))
        assert (r.status_code, r.json()["detail"]) == (422, code)

    # Sfax Ville and the Kerkennah islands: their union has several parts.
    sfax_committee = staff(["local_committee"], gouvernorat=61)
    r = await post(alert_body(area={"delegation_ids": [6114, 6107]}, severity="medium"), sfax_committee)
    assert r.status_code == 201, r.text
    alert = r.json()
    assert alert["area"]["delegation_ids"] == [6107, 6114] and alert["area"]["gouvernorat_codes"] == []
    assert alert["area"]["polygon"]["type"] == "MultiPolygon"
    # Another member publishes it (four eyes).
    r = await client.post(f"/api/v1/staff/notifications/{alert['id']}/publish", headers=central)
    assert r.status_code == 200, r.text
    await drain()  # its pushes go now, not during another test's delivery

    assert alert["id"] in await active_ids(client, lat=34.7406, lon=10.7603)  # Sfax medina
    assert alert["id"] in await active_ids(client, lat=34.70, lon=11.17)  # Remla, Kerkennah
    assert alert["id"] not in await active_ids(client, lat=34.52, lon=10.50)  # Mahrès
    # A regional committee picks the délégations of its own gouvernorat only.
    r = await post(alert_body(area={"delegation_ids": [1101]}), sfax_committee)
    assert (r.status_code, r.json()["detail"]) == (403, "out_of_scope")
    r = await client.post(f"/api/v1/staff/notifications/{alert['id']}/cancel", headers=central)
    assert r.status_code == 200, r.text
    await drain()
