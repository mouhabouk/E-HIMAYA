"""Satellite background of the maps (docs/phase-r/design-basemap.md): the open source by default, the paid provider
the national system administrator sets and tests, its key kept by the API (never returned, never in the audit), and
the tile address that serves the provider's tiles or falls back to the open source."""

from collections.abc import Callable

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.modules.audit.models import AuditLog
from app.modules.basemap import domain
from app.modules.basemap import router as basemap_router

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/staff/basemap"
KEY = "secret-licence-key-1234"
SETTINGS = {
    "provider": "esri",
    "url_template": "https://imagery.example.test/tile/{z}/{y}/{x}?token={key}",
    "api_key": KEY,
    "attribution": "Esri, Maxar",
    "max_zoom": 19,
    "enabled": False,
}


def test_templates_and_tokens() -> None:
    domain.check_template(SETTINGS["url_template"], True, None)  # type: ignore[arg-type]
    for template, has_key, header, code in (
        ("http://x.test/{z}/{x}/{y}", False, None, "basemap_url_https"),
        ("https://x.test/{z}/{x}", False, None, "basemap_url_placeholders"),
        ("https://x.test/{z}/{x}/{y}", True, None, "basemap_key_unused"),
        ("https://x.test/{z}/{x}/{y}?k={key}", False, None, "basemap_key_missing"),
    ):
        with pytest.raises(ValueError, match=code):
            domain.check_template(template, has_key, header)
    domain.check_template("https://x.test/{z}/{x}/{y}", True, "X-Api-Key")
    assert domain.tile_url("https://x.test/{z}/{x}/{y}?k={key}", 6, 33, 25, "a b") == "https://x.test/6/33/25?k=a%20b"
    token = domain.tile_token(now=1_800_000_000)
    assert domain.tile_token_valid(token, now=1_800_000_000)
    assert not domain.tile_token_valid(token, now=1_800_000_000 + domain.TOKEN_SECONDS + 1)
    assert not domain.tile_token_valid(token[:-2] + "xx", now=1_800_000_000)
    assert domain.key_hint(KEY) == "••••1234"


def test_the_office_map_server_replaces_the_public_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without internet (docs/offline-maps.md) the imagery and the place names come from the Office's map server."""
    assert domain.open_source() == ([domain.OPEN_TILES], domain.OPEN_ATTRIBUTION, domain.OPEN_MAX_ZOOM)
    local = "https://api.example.test/maps/data/satellite/{z}/{x}/{y}.jpg"
    labels = "https://api.example.test/maps/styles/ehimaya-labels/{z}/{x}/{y}.png"
    settings = get_settings()
    monkeypatch.setattr(settings, "basemap_open_tiles", local)
    monkeypatch.setattr(settings, "basemap_open_attribution", "Sentinel-2 – office mirror")
    monkeypatch.setattr(settings, "basemap_open_max_zoom", 16)
    monkeypatch.setattr(settings, "basemap_label_tiles", labels)
    assert domain.open_source() == ([local], "Sentinel-2 – office mirror", 16)
    assert domain.label_source() == ([labels], domain.LABEL_ATTRIBUTION, domain.LABEL_MAX_ZOOM)
    assert domain.open_tile(6, 33, 25) == "https://api.example.test/maps/data/satellite/6/33/25.jpg"
    with pytest.raises(ValidationError, match="tile address"):
        Settings(basemap_open_tiles="https://api.example.test/maps/satellite.jpg")


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch) -> list[httpx.Request]:
    """A fake imagery provider: answers a PNG when the key is right."""
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.params.get("token") == KEY:
            return httpx.Response(200, content=b"\x89PNG tile", headers={"content-type": "image/png"})
        return httpx.Response(401, json={"error": "bad key"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(answer))
    monkeypatch.setattr(basemap_router, "_client", lambda: client)
    basemap_router.forget()
    return seen


async def test_the_administrator_sets_tests_and_enables_a_paid_provider(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession, provider: list[httpx.Request]
) -> None:
    admin = staff(["sysadmin"], gouvernorat=None)
    # Only the national system administrator sees or changes the settings.
    for other in (staff(["sysadmin"], gouvernorat=21), staff(["ops_manager"], gouvernorat=None)):
        assert (await client.get(f"{URL}/settings", headers=other)).status_code == 403
    r = await client.put(f"{URL}/settings", json=SETTINGS, headers=admin)
    assert r.status_code == 200, r.text
    saved = r.json()
    assert saved["key_hint"] == "••••1234" and KEY not in r.text and saved["last_test_ok"] is None

    # Off: every map uses the open source.
    room = staff(["operator"], gouvernorat=21)
    view = (await client.get(URL, headers=room)).json()
    assert view["source"] == "open" and view["satellite"]["tiles"] == [domain.OPEN_TILES]

    # The test asks for one tile with the stored key (None keeps it) and records the result.
    test = (await client.post(f"{URL}/settings/test", json={**SETTINGS, "api_key": None}, headers=admin)).json()
    assert test["ok"] is True and test["status"] == 200 and test["content_type"] == "image/png"
    assert (await client.get(f"{URL}/settings", headers=admin)).json()["last_test_ok"] is True
    wrong = (await client.post(f"{URL}/settings/test", json={**SETTINGS, "api_key": "wrong"}, headers=admin)).json()
    assert wrong["ok"] is False and wrong["status"] == 401
    bad = await client.put(f"{URL}/settings", json={**SETTINGS, "url_template": "https://x.test/{z}"}, headers=admin)
    assert bad.json()["detail"] == "basemap_url_placeholders"

    await client.put(f"{URL}/settings", json={**SETTINGS, "api_key": None, "enabled": True}, headers=admin)
    view = (await client.get(URL, headers=room)).json()
    assert view["source"] == "paid" and KEY not in str(view)
    address = view["satellite"]["tiles"][0]
    assert address.startswith("/api/v1/basemap/tiles/{z}/{x}/{y}?t=")
    tile = await client.get(address.replace("{z}/{x}/{y}", "6/33/25"))
    assert tile.status_code == 200 and tile.content == b"\x89PNG tile"
    assert provider[-1].url.params["token"] == KEY
    # No token, no tile; beyond the provider's zoom, the open source.
    assert (await client.get("/api/v1/basemap/tiles/6/33/25")).status_code == 403
    deep = await client.get(address.replace("{z}/{x}/{y}", "20/1/1"))
    assert deep.status_code == 307 and deep.headers["location"] == domain.open_tile(20, 1, 1)

    # A key that stops working: the tile comes from the open source, the map never goes blank.
    await client.put(f"{URL}/settings", json={**SETTINGS, "api_key": "expired", "enabled": True}, headers=admin)
    fallback = await client.get(address.replace("{z}/{x}/{y}", "6/33/25"))
    assert fallback.status_code == 307 and fallback.headers["location"] == domain.open_tile(6, 33, 25)

    entries = (
        await session.scalars(select(AuditLog).where(AuditLog.action.in_(["basemap.update", "basemap.test"])))
    ).all()
    assert entries and all(KEY not in str(e.details) and "expired" not in str(e.details) for e in entries)
    await client.put(f"{URL}/settings", json={**SETTINGS, "enabled": False}, headers=admin)
