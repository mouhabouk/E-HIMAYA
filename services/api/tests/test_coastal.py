"""Coastal safety (phase L1b, docs/phase-l/design-l1b-coastal.md): the declared drowning-risk rules, the marine weather
provider, and the whole flow on a beaches layer: four days of risk, today's alert once, the citizen's view (colour,
reasons, visible card fields only, never the presence count), the anonymous presence, the coastal dashboard and its
regional scope, the bulletin, the rules changed by the Office, and the purge of presence rows."""

import json
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_system_sessionmaker
from app.modules.coastal import marine, risk, service
from app.modules.privacy import retention
from tests.conftest import accept_charter, device_headers, outbox_events, report_body

Staff = Callable[..., dict[str, str]]
LAYERS = "/api/v1/staff/layers"
PUBLIC = "/api/v1/coastal"
URL = "/api/v1/staff/coastal"
# 2026-07-04: a simulated northern swell (day ≡ 1 mod 4) and no eastern chop (day ≢ 3 mod 6), in the bathing season.
SWELL_DAY = date(2026, 7, 4)
NOW = datetime(2026, 7, 4, 7, 0, tzinfo=UTC)
NORTH = (37.2745, 9.8739)  # Bizerte, Corniche
SOUSSE = (35.8300, 10.6400)
HAMMAMET = (36.3950, 10.6150)


# ---------------------------------------------------------------- rules (no database)


def test_rules_give_points_and_reasons() -> None:
    rules = risk.rules_of(None)
    rough = risk.DayInputs(
        day=SWELL_DAY,
        wave_height_m=2.6,
        current_kmh=2.4,
        onshore_wind_kmh=45,
        max_temperature_c=31,
        guarded=False,
        crowd="high",
        incidents=4,
    )
    found = risk.assess(rough, rules)
    points = {f["code"]: f["points"] for f in found.factors}
    assert points == {
        "waves": 55,
        "onshore_wind": 15,
        "current": 10,
        "season": 10,
        "crowd": 5,
        "unguarded": 10,
        "past_drownings": 15,
    }
    assert (found.score, found.level) == (100, "red")

    calm = risk.assess(risk.DayInputs(day=date(2026, 1, 15), wave_height_m=0.3, guarded=False), rules)
    assert (calm.score, calm.level, calm.factors) == (0, "green", [])  # out of season: no "unguarded" points

    yellow = risk.assess(risk.DayInputs(day=SWELL_DAY, wave_height_m=1.2), rules)
    assert (yellow.score, yellow.level) == (35, "yellow")

    unknown = risk.assess(risk.DayInputs(day=date(2026, 2, 1)), rules)
    assert unknown.score == 0


def test_onshore_wind_and_rule_overrides() -> None:
    rules = risk.rules_of({"red": 50, "nonsense": 1, "yellow": None})
    assert (rules["red"], rules["yellow"]) == (50, 35) and "nonsense" not in rules
    assert risk.is_onshore(350, 10, rules)  # from the north, sea to the north
    assert not risk.is_onshore(180, 10, rules)  # from the land
    assert not risk.is_onshore(350, None, rules)  # unknown coast: never counted
    assert risk.angle_between(350, 10) == 20


# ---------------------------------------------------------------- marine provider (no database)


async def test_open_meteo_marine_request_and_failures() -> None:
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        hourly = {"time": [1783123200, 1783126800], **{v: [1.0, None] for v in marine.HOURLY_VARIABLES}}
        return httpx.Response(200, json=[{"latitude": 37.3, "longitude": 9.9, "hourly": hourly}] * 2)

    provider = marine.OpenMeteoMarine("https://marine.test/", 5, transport=httpx.MockTransport(answer))
    series = await provider.fetch([NORTH, SOUSSE], 4)
    assert len(series) == 2 and series[0][0].wave_height_m == 1.0 and series[0][1].sea_temp_c is None
    params = seen[0].url.params
    assert seen[0].url.path == "/v1/marine" and params["forecast_days"] == "4"
    assert set(params["hourly"].split(",")) == set(marine.HOURLY_VARIABLES)

    limited = marine.OpenMeteoMarine(
        "https://marine.test", 5, transport=httpx.MockTransport(lambda r: httpx.Response(429))
    )
    with pytest.raises(marine.MarineRateLimited):
        await limited.fetch([NORTH], 4)
    calls: list[int] = []

    def broken(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503)

    down = marine.OpenMeteoMarine("https://marine.test", 5, transport=httpx.MockTransport(broken), retry_pause_s=0)
    with pytest.raises(marine.MarineUnavailable):
        await down.fetch([NORTH], 4)
    assert len(calls) == marine.MAX_ATTEMPTS
    with pytest.raises(marine.MarineUnavailable):
        marine.parse({"hourly": {}}, 1)


def test_simulated_marine_is_deterministic() -> None:
    at = datetime(2026, 7, 4, 15, tzinfo=UTC)
    assert marine.simulated_values(*NORTH, at) == marine.simulated_values(*NORTH, at)
    assert (marine.simulated_values(*NORTH, at).wave_height_m or 0) > 2.5  # the northern swell
    assert (marine.simulated_values(*SOUSSE, at).wave_height_m or 9) < 0.6


# ---------------------------------------------------------------- the flow


def _admin(staff: Staff) -> dict[str, str]:
    return staff(["sysadmin"], gouvernorat=None)


def _beaches() -> bytes:
    def point(name: str, where: tuple[float, float], **props: Any) -> dict[str, Any]:
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [where[1], where[0]]},
            "properties": {"name": name, **props},
        }

    return json.dumps(
        {
            "type": "FeatureCollection",
            "features": [
                point("شاطئ الكورنيش", NORTH, guarded=False, classification="local"),
                point(
                    "شاطئ بوجعفر",
                    SOUSSE,
                    guarded=True,
                    classification="touristic",
                    crowd="medium",
                    classification_source="ONTT",
                    classification_date="2026-06-01",
                ),
                point("شاطئ الحمامات", HAMMAMET, guarded=True, classification="international", crowd="high"),
            ],
        }
    ).encode()


@pytest.fixture
async def beaches(client: httpx.AsyncClient, staff: Staff, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    admin = _admin(staff)
    key = f"t_beaches_{uuid.uuid4().hex[:8]}"
    r = await client.post(
        LAYERS,
        json={
            "key": key,
            "name": {"ar": "الشواطئ", "fr": "Plages", "en": "Beaches"},
            "icon": "pin",
            "colour": "#00695C",
            "source": "OpenStreetMap",
            "licence": "ODbL",
            "status": "published",
            "audiences": ["citizen", "room", "field", "command", "support"],
            "fields": {"crowd": ["room", "command"]},
            "reason": "coastal test layer",
        },
        headers=admin,
    )
    assert r.status_code == 201, r.text
    imported = await client.post(
        f"{LAYERS}/{key}/imports",
        params={"file_name": "beaches.geojson", "mode": "merge"},
        content=_beaches(),
        headers={**admin, "Content-Type": "application/octet-stream"},
    )
    assert imported.status_code == 201, imported.text
    applied = await client.post(
        f"{LAYERS}/{key}/imports/{imported.json()['id']}/apply", json={"reason": "beaches"}, headers=admin
    )
    assert applied.status_code == 200, applied.text
    monkeypatch.setattr(get_settings(), "coastal_layer_key", key)
    features = (await client.get(f"{LAYERS}/{key}/features", headers=admin)).json()["items"]
    return {"key": key, "ids": {f["name"]: f["id"] for f in features}}


@pytest.fixture
def sim_marine() -> Iterator[None]:
    marine.set_provider(marine.SimMarine(NOW))
    yield
    marine.set_provider(None)


async def _drowning_near(client: httpx.AsyncClient, where: tuple[float, float]) -> None:
    headers = device_headers()
    await accept_charter(client, headers)
    body = report_body({"lat": where[0] + 0.001, "lon": where[1], "accuracy_m": 10.0}, category="drowning")
    r = await client.post("/api/v1/reports", json=body, headers=headers)
    assert r.status_code == 201, r.text


async def test_coastal_flow(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession, beaches: dict[str, Any], sim_marine: None
) -> None:
    north, sousse = beaches["ids"]["شاطئ الكورنيش"], beaches["ids"]["شاطئ بوجعفر"]
    await _drowning_near(client, NORTH)
    first = await service.refresh(get_system_sessionmaker(), NOW)
    assert first == {"added": 3, "fetched": 3, "days": 12}

    rows = (
        await session.execute(
            text("SELECT feature_id, day, level, factors, simulated FROM coastal.beach_day WHERE feature_id = :f"),
            {"f": north},
        )
    ).all()
    assert [r.day for r in sorted(rows, key=lambda r: r.day)] == [SWELL_DAY + timedelta(days=d) for d in range(4)]
    today = next(r for r in rows if r.day == SWELL_DAY)
    codes = {f["code"] for f in today.factors}
    assert today.level == "red" and today.simulated
    assert {"waves", "current", "season", "unguarded", "past_drownings"} <= codes

    # One alert per beach, day and level, however often the worker runs; the live event goes to its gouvernorat.
    await service.refresh(get_system_sessionmaker(), NOW + timedelta(hours=1))
    alerts = (await session.execute(text("SELECT level FROM coastal.alert WHERE feature_id = :f"), {"f": north})).all()
    assert [a.level for a in alerts] == ["red"]
    events = [e for e in await outbox_events(session, "coastal.alert") if e["feature_id"] == north]
    assert len(events) == 1 and events[0]["level"] == "red" and events[0]["gouvernorat_codes"]

    # The citizen: colours and reasons; the hidden column and the presence count never leave the server.
    public = await client.get(f"{PUBLIC}/beaches", params={"day": SWELL_DAY.isoformat()})
    assert public.status_code == 200, public.text
    by_id = {b["id"]: b for b in public.json()["items"]}
    assert by_id[north]["level"] == "red" and by_id[sousse]["level"] == "green"
    assert public.json()["simulated"] and public.json()["warn_radius_m"] == 1000
    assert all(b["present"] is None for b in by_id.values())
    detail = (await client.get(f"{PUBLIC}/beaches/{sousse}")).json()
    assert "crowd" not in detail["card"] and detail["card"]["classification"] == "touristic"
    assert detail["sources"] == {"classification": {"source": "ONTT", "date": "2026-06-01"}}
    assert (await client.get(f"{PUBLIC}/beaches/{uuid.uuid4()}")).status_code == 404

    # Presence: anonymous, counted once per phone and day.
    token = "a" * 24
    for _ in range(2):
        r = await client.post(f"{PUBLIC}/beaches/{sousse}/presence", json={"token": token})
        assert r.status_code == 204, r.text
    assert (await client.post(f"{PUBLIC}/beaches/{sousse}/presence", json={"token": "short"})).status_code == 422
    stored = (await session.execute(text("SELECT token_hash FROM coastal.presence"))).scalars().all()
    assert token.encode() not in stored

    # The national room: indicators, top 10, by gouvernorat, heat maps; the crowd column is theirs.
    room = staff(["operator"], gouvernorat=None)
    view = await client.get(f"{URL}/overview", params={"day": SWELL_DAY.isoformat()}, headers=room)
    assert view.status_code == 200, view.text
    data = view.json()
    assert data["kpis"]["beaches"] == 3 and data["kpis"]["red"] >= 1 and data["kpis"]["present"] == 1
    assert data["top_dangerous"][0]["id"] == north
    assert [b["name"] for b in data["top_touristic"]] == ["شاطئ الحمامات", "شاطئ بوجعفر"]
    assert data["heat_risk"] and data["heat_drownings"]
    assert {g["code"] for g in data["by_gouvernorat"]} == {b["gouvernorat_code"] for b in data["beaches"]}
    only_red = await client.get(f"{URL}/overview", params={"day": SWELL_DAY.isoformat(), "level": "red"}, headers=room)
    assert {b["id"] for b in only_red.json()["beaches"]} == {north}
    staff_card = (await client.get(f"{URL}/beaches/{sousse}", headers=room)).json()
    assert staff_card["card"]["crowd"] == "medium" and staff_card["beach"]["present"] == 1

    # A regional room sees its own gouvernorat only.
    sfax = staff(["operator"], gouvernorat=61)
    regional = await client.get(f"{URL}/overview", params={"day": SWELL_DAY.isoformat()}, headers=sfax)
    assert regional.json()["kpis"]["beaches"] == 0
    assert (await client.get(f"{URL}/beaches/{north}", headers=sfax)).status_code == 404
    assert north not in {a["feature_id"] for a in (await client.get(f"{URL}/alerts", headers=sfax)).json()["items"]}

    # The alerts centre: red first, acknowledged once.
    listed = await client.get(f"{URL}/alerts", params={"day": SWELL_DAY.isoformat()}, headers=room)
    mine = [a for a in listed.json()["items"] if a["feature_id"] == north]
    assert mine and mine[0]["level"] == "red" and mine[0]["acked_at"] is None
    acked = await client.post(f"{URL}/alerts/{mine[0]['id']}/ack", headers=room)
    assert acked.status_code == 200 and acked.json()["acked_at"]

    # The bulletin.
    pdf = await client.get(f"{URL}/bulletin.pdf", params={"day": SWELL_DAY.isoformat(), "lang": "fr"}, headers=room)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


async def test_rules_changed_by_the_office(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession, beaches: dict[str, Any], sim_marine: None
) -> None:
    national = staff(["ops_manager"], gouvernorat=None)
    current = await client.get(f"{URL}/settings", headers=national)
    assert current.json()["rules"]["red"] == 60
    assert (
        await client.put(f"{URL}/settings", json={"rules": {"red": 30}, "reason": "test"}, headers=national)
    ).status_code == 422  # red must stay above yellow
    assert (
        await client.put(f"{URL}/settings", json={"rules": {"bogus": 1}, "reason": "test"}, headers=national)
    ).status_code == 422
    regional = staff(["ops_manager"], gouvernorat=61)
    assert (
        await client.put(f"{URL}/settings", json={"rules": {"red": 90}, "reason": "test"}, headers=regional)
    ).status_code == 403
    try:
        changed = await client.put(
            f"{URL}/settings", json={"rules": {"red": 99, "yellow": 80}, "reason": "summer review"}, headers=national
        )
        assert changed.status_code == 200, changed.text
        assert changed.json()["rules"]["red"] == 99
        audit = (
            (await session.execute(text("SELECT reason FROM audit.log WHERE action = 'coastal.rules_update'")))
            .scalars()
            .all()
        )
        assert "summer review" in audit
        await service.refresh(get_system_sessionmaker(), NOW)
        north = beaches["ids"]["شاطئ الكورنيش"]
        level = (
            await session.execute(
                text("SELECT level FROM coastal.beach_day WHERE feature_id = :f AND day = :d"),
                {"f": north, "d": SWELL_DAY},
            )
        ).scalar_one()
        assert level == "yellow"  # 85 to 90 points: red only from 99 now
    finally:
        await client.put(f"{URL}/settings", json={"rules": {}, "reason": "back to defaults"}, headers=national)


async def test_layer_not_for_citizens(client: httpx.AsyncClient, staff: Staff, beaches: dict[str, Any]) -> None:
    admin = _admin(staff)
    layers = (await client.get(LAYERS, headers=admin)).json()["items"]
    layer = next(i for i in layers if i["key"] == beaches["key"])
    r = await client.patch(
        f"{LAYERS}/{beaches['key']}",
        json={"version": layer["version"], "audiences": ["room"], "reason": "rooms only"},
        headers=admin,
    )
    assert r.status_code == 200, r.text
    assert (await client.get(f"{PUBLIC}/beaches")).status_code == 404
    sousse = beaches["ids"]["شاطئ بوجعفر"]
    assert (await client.post(f"{PUBLIC}/beaches/{sousse}/presence", json={"token": "b" * 20})).status_code == 404
    assert (await client.get(f"{URL}/overview", headers=staff(["operator"], gouvernorat=None))).status_code == 200
    assert (
        await client.get(f"{URL}/overview", headers=staff(["local_committee"], gouvernorat=None))
    ).status_code == 404


async def test_presence_rows_are_purged(
    client: httpx.AsyncClient, session: AsyncSession, beaches: dict[str, Any], sim_marine: None
) -> None:
    await service.refresh(get_system_sessionmaker(), NOW)
    sousse = beaches["ids"]["شاطئ بوجعفر"]
    assert (await client.post(f"{PUBLIC}/beaches/{sousse}/presence", json={"token": "c" * 20})).status_code == 204
    later = datetime.now(UTC) + timedelta(hours=get_settings().retention_coastal_presence_hours + 1)
    async with get_system_sessionmaker()() as s, s.begin():
        await retention.purge_coastal_presence(s, get_settings(), later)
    left = (
        await session.execute(text("SELECT count(*) FROM coastal.presence WHERE feature_id = :f"), {"f": sousse})
    ).scalar_one()
    assert left == 0


async def test_nearest_on_the_road(client: httpx.AsyncClient, beaches: dict[str, Any]) -> None:
    """The place closest as the crow flies may be farther on the road: with ``road``, the engine's order wins."""
    from app.modules.decision import routing

    class Engine:
        name = "valhalla"

        async def route(self, *_: Any) -> Any:
            raise NotImplementedError

        async def matrix(
            self, sources: list[routing.Point], target: routing.Point, profile: str
        ) -> list[routing.Leg | None]:
            # Hammamet is reached by a short coastal road, Sousse by a long detour.
            return [
                routing.Leg(80_000, 3_600) if s.lat < 36 else routing.Leg(20_000, 900) if s.lat < 37 else None
                for s in sources
            ]

    near = f"{SOUSSE[0] + 0.2},{SOUSSE[1]}"  # nearer Sousse than Hammamet as the crow flies
    params = {"near": near, "limit": 2, "radius_km": 300}
    plain = (await client.get(f"/api/v1/layers/{beaches['key']}/features", params=params)).json()["items"]
    assert plain[0]["name"] == "شاطئ بوجعفر" and plain[0]["road_m"] is None
    routing.set_engine(Engine())  # type: ignore[arg-type]
    try:
        by_road = await client.get(f"/api/v1/layers/{beaches['key']}/features", params={**params, "road": "true"})
    finally:
        routing.set_engine(None)
    items = by_road.json()["items"]
    assert [i["name"] for i in items] == ["شاطئ الحمامات", "شاطئ بوجعفر"]
    assert items[0]["road_m"] == 20_000 and items[0]["road_engine"] == "valhalla"
