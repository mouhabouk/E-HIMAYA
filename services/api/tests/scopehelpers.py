"""Shared helpers of the phase 9 scope tests: reports on either side of a gouvernorat border, incidents, units and
resources of a given gouvernorat."""

import secrets
from collections.abc import Callable
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import accept_charter, device_headers, report_body

Staff = Callable[..., dict[str, str]]
KASSERINE, SIDI_BOUZID = 42, 43
REASON = "coordination de la frontière"


async def border_points(
    session: AsyncSession, a: int = KASSERINE, b: int = SIDI_BOUZID
) -> tuple[dict[str, float], ...]:
    """Two points about 150 m apart on either side of the border between gouvernorats ``a`` and ``b``, each more
    than 30 m inside its own gouvernorat (trusted with a 10 m accuracy). A random place along the border keeps
    repeated runs on the same database apart (duplicate guard)."""
    for _ in range(200):
        fraction = 0.02 + secrets.randbelow(9600) / 10_000
        rows = (
            await session.execute(
                text(
                    """
                    WITH line AS (
                        SELECT ST_GeometryN(ST_LineMerge(ST_Intersection(ST_Boundary(x.boundary),
                                                                         ST_Boundary(y.boundary))), 1) AS l
                        FROM geo.gouvernorat x, geo.gouvernorat y WHERE x.code = :a AND y.code = :b
                    ), o AS (SELECT ST_LineInterpolatePoint(l, :f) AS p FROM line),
                    c AS (
                        SELECT ST_SetSRID(ST_MakePoint(ST_X(o.p) + dx, ST_Y(o.p) + dy), 4326) AS g
                        FROM o, (VALUES (-0.0007), (0.0), (0.0007)) AS u(dx),
                             (VALUES (-0.0007), (0.0), (0.0007)) AS v(dy)
                    )
                    SELECT ST_Y(c.g) AS lat, ST_X(c.g) AS lon, gv.code
                    FROM c JOIN geo.gouvernorat gv ON ST_Contains(gv.boundary, c.g)
                    WHERE gv.code IN (:a, :b) AND ST_Distance(ST_Boundary(gv.boundary)::geography, c.g::geography) > 30
                      -- Away from the reports of earlier runs still inside the grouping window.
                      AND NOT EXISTS (
                          SELECT 1 FROM reports.report r
                          WHERE r.received_at > now() - interval '2 hours'
                            AND ST_DWithin(r.location, c.g::geography, 1000)
                      )
                    """
                ),
                {"a": a, "b": b, "f": fraction},
            )
        ).all()
        side_a = [r for r in rows if r.code == a]
        side_b = [r for r in rows if r.code == b]
        if side_a and side_b:
            pa, pb = side_a[0], side_b[0]
            return (
                {"lat": float(pa.lat), "lon": float(pa.lon), "accuracy_m": 10.0},
                {"lat": float(pb.lat), "lon": float(pb.lon), "accuracy_m": 10.0},
            )
    raise AssertionError("no border points found")


async def new_report(client: httpx.AsyncClient, location: dict[str, float], **overrides: Any) -> dict[str, Any]:
    headers = device_headers()
    await accept_charter(client, headers)
    r = await client.post("/api/v1/reports", json=report_body(location, **overrides), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


async def group(client: httpx.AsyncClient, headers: dict[str, str], report_id: str, **body: Any) -> httpx.Response:
    return await client.post(f"/api/v1/staff/reports/{report_id}/incident", json=body, headers=headers)


async def incident(client: httpx.AsyncClient, headers: dict[str, str], incident_id: str) -> dict[str, Any]:
    r = await client.get(f"/api/v1/staff/incidents/{incident_id}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()  # type: ignore[no-any-return]


async def unit_with_resource(
    client: httpx.AsyncClient, staff: Staff, gouvernorat: int, location: dict[str, float], kind: str = "fire_engine"
) -> dict[str, Any]:
    """A unit of ``gouvernorat`` with one resource; returns the resource."""
    manager = staff(["ops_manager"], gouvernorat=gouvernorat)
    r = await client.post(
        "/api/v1/staff/units",
        json={
            "name_ar": "وحدة الحدود",
            "name_fr": f"Unité frontière {gouvernorat}",
            "kind": "unit",
            "gouvernorat_code": gouvernorat,
            "location": {"lat": location["lat"], "lon": location["lon"]},
            "phone": "77 000 000",
        },
        headers=manager,
    )
    assert r.status_code == 201, r.text
    r = await client.post(
        "/api/v1/staff/resources",
        json={"unit_id": r.json()["id"], "kind": kind, "label": f"FPT-{secrets.token_hex(3)}"},
        headers=manager,
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]
