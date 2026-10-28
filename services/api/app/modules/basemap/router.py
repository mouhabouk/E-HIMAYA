"""Satellite background of the maps (docs/phase-r/design-basemap.md).

``GET /api/v1/staff/basemap`` tells a map where its satellite and hybrid tiles come from. The national system
administrator chooses a paid provider in ``/settings`` (address, licence key, attribution) and tests the connection
before switching it on; every change is audited, without the key. The tiles of a paid provider go through
``/api/v1/basemap/tiles``, opened by a signed address, so the key never leaves the API; a failing provider falls back
to the open source tile by tile.
"""

import time
from datetime import UTC, datetime
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session, get_system_sessionmaker
from app.core.security import Principal, Role, get_principal, require_roles
from app.modules.audit import service as audit
from app.modules.basemap import domain, schemas
from app.modules.basemap.models import Basemap

router = APIRouter(prefix="/api/v1/staff/basemap", tags=["staff", "basemap"])
tiles_router = APIRouter(prefix="/api/v1/basemap", tags=["basemap"])
Session = Annotated[AsyncSession, Depends(get_session)]
Admin = Annotated[Principal, Depends(require_roles(Role.SYSADMIN))]
KEY = "satellite"
CACHE_SECONDS = 60
TILE_TIMEOUT = httpx.Timeout(8)

# The provider as the tile address needs it, read again at most once a minute (and at once after a change).
_cached: tuple[float, Basemap | None] | None = None
_http: httpx.AsyncClient | None = None


def _client() -> httpx.AsyncClient:
    global _http
    if _http is None:
        _http = httpx.AsyncClient(timeout=TILE_TIMEOUT, follow_redirects=True)
    return _http


def forget() -> None:
    global _cached
    _cached = None


async def _provider() -> Basemap | None:
    global _cached
    if _cached is not None and time.monotonic() - _cached[0] < CACHE_SECONDS:
        return _cached[1]
    async with get_system_sessionmaker()() as session:
        row = await session.get(Basemap, KEY)
        if row is not None:
            session.expunge(row)
    _cached = (time.monotonic(), row)
    return row


def _staff(principal: Principal) -> Principal:
    if not principal.is_staff:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient_role")
    return principal


def _national(principal: Principal) -> None:
    if not principal.is_national:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "out_of_scope")


def _open() -> schemas.TileSource:
    return schemas.TileSource(
        tiles=[domain.OPEN_TILES], attribution=domain.OPEN_ATTRIBUTION, max_zoom=domain.OPEN_MAX_ZOOM
    )


@router.get("", response_model=schemas.BasemapOut)
async def basemap(principal: Annotated[Principal, Depends(get_principal)], session: Session) -> schemas.BasemapOut:
    _staff(principal)
    row = await session.get(Basemap, KEY)
    labels = schemas.TileSource(
        tiles=domain.LABEL_TILES, attribution=domain.LABEL_ATTRIBUTION, max_zoom=domain.LABEL_MAX_ZOOM
    )
    if row is None or not row.enabled:
        return schemas.BasemapOut(source="open", satellite=_open(), labels=labels, open=_open())
    paid = schemas.TileSource(
        tiles=[f"/api/v1/basemap/tiles/{{z}}/{{x}}/{{y}}?t={domain.tile_token()}"],
        attribution=row.attribution,
        max_zoom=row.max_zoom,
    )
    return schemas.BasemapOut(source="paid", satellite=paid, labels=labels, open=_open())


def _settings_out(row: Basemap | None) -> schemas.SettingsOut:
    if row is None:
        return schemas.SettingsOut(
            configured=False,
            provider=None,
            url_template=None,
            key_hint=None,
            key_header=None,
            attribution=None,
            max_zoom=19,
            enabled=False,
            last_test_ok=None,
            last_test_at=None,
            updated_by_name=None,
            updated_at=None,
        )
    return schemas.SettingsOut(
        configured=True,
        provider=row.provider,
        url_template=row.url_template,
        key_hint=domain.key_hint(row.api_key),
        key_header=row.key_header,
        attribution=row.attribution,
        max_zoom=row.max_zoom,
        enabled=row.enabled,
        last_test_ok=row.last_test_ok,
        last_test_at=row.last_test_at,
        updated_by_name=row.updated_by_name,
        updated_at=row.updated_at,
    )


@router.get("/settings", response_model=schemas.SettingsOut)
async def get_settings(principal: Admin, session: Session) -> schemas.SettingsOut:
    _national(principal)
    return _settings_out(await session.get(Basemap, KEY))


def _key_of(body: schemas.SettingsIn, row: Basemap | None) -> str | None:
    if body.api_key is None:
        return row.api_key if row else None
    return body.api_key.strip() or None


def _check(body: schemas.SettingsIn, key: str | None) -> None:
    try:
        domain.check_template(body.url_template.strip(), key is not None, body.key_header)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


async def _fetch(url_template: str, key: str | None, key_header: str | None, z: int, x: int, y: int) -> httpx.Response:
    headers = {key_header: key} if key_header and key else {}
    return await _client().get(domain.tile_url(url_template, z, x, y, key), headers=headers)


@router.post("/settings/test", response_model=schemas.TestOut)
async def test_settings(principal: Admin, session: Session, body: schemas.SettingsIn) -> schemas.TestOut:
    """Asks the provider for one tile of Tunisia with these settings (the stored key unless a new one is given)."""
    _national(principal)
    row = await session.get(Basemap, KEY)
    key = _key_of(body, row)
    _check(body, key)
    started = time.monotonic()
    try:
        r = await _fetch(body.url_template.strip(), key, body.key_header, *domain.TEST_TILE)
        kind = r.headers.get("content-type", "").split(";")[0] or None
        ok = r.status_code == 200 and bool(kind and kind.startswith("image/"))
        result = schemas.TestOut(ok=ok, status=r.status_code, content_type=kind, ms=0, error=None)
    except httpx.HTTPError as exc:
        result = schemas.TestOut(ok=False, status=None, content_type=None, ms=0, error=type(exc).__name__)
    result.ms = int((time.monotonic() - started) * 1000)
    if row is not None and row.url_template == body.url_template.strip() and body.api_key is None:
        row.last_test_ok, row.last_test_at = result.ok, datetime.now(UTC)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="basemap.test",
        target=f"basemap:{KEY}",
        details={"provider": body.provider, "ok": result.ok, "status": result.status},
    )
    await session.commit()
    return result


@router.put("/settings", response_model=schemas.SettingsOut)
async def save_settings(principal: Admin, session: Session, body: schemas.SettingsIn) -> schemas.SettingsOut:
    _national(principal)
    row = await session.get(Basemap, KEY, with_for_update=True)
    key = _key_of(body, row)
    _check(body, key)
    if row is None:
        row = Basemap(key=KEY)
        session.add(row)
    changed_address = row.url_template != body.url_template.strip() or body.api_key is not None
    row.provider = body.provider
    row.url_template = body.url_template.strip()
    row.api_key = key
    row.key_header = body.key_header
    row.attribution = body.attribution.strip()
    row.max_zoom = body.max_zoom
    row.enabled = body.enabled
    if changed_address:
        row.last_test_ok, row.last_test_at = None, None
    row.updated_by = audit.actor_of(principal)
    row.updated_by_name = audit.name_of(principal)
    row.updated_at = datetime.now(UTC)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="basemap.update",
        target=f"basemap:{KEY}",
        # Never the key itself: whether one is kept, and whether it changed.
        details={
            "provider": body.provider,
            "enabled": body.enabled,
            "has_key": key is not None,
            "key_changed": body.api_key is not None,
        },
    )
    await session.commit()
    forget()
    return _settings_out(row)


@tiles_router.get("/tiles/{z}/{x}/{y}", response_model=None)
async def tile(z: int, x: int, y: int, t: Annotated[str, Query(max_length=80)] = "") -> Response | RedirectResponse:
    """A tile of the paid provider, or of the open source when the provider is off or fails."""
    if not domain.tile_token_valid(t):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "tile_token_invalid")
    if not (0 <= z <= 22 and 0 <= x < 2**z and 0 <= y < 2**z):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "tile_out_of_range")
    row = await _provider()
    if row is not None and row.enabled and z <= row.max_zoom:
        try:
            r = await _fetch(row.url_template, row.api_key, row.key_header, z, x, y)
            kind = r.headers.get("content-type", "")
            if r.status_code == 200 and kind.startswith("image/"):
                return Response(r.content, media_type=kind, headers={"Cache-Control": "private, max-age=86400"})
        except httpx.HTTPError:
            pass
    return RedirectResponse(domain.open_tile(z, x, y), status.HTTP_307_TEMPORARY_REDIRECT)
