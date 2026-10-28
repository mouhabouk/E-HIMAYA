"""Seasonal programmes (phase L2, docs/phase-l/design-l2.md §2): reading the three formats and their problems, the
import preview and apply, the life cycle (draft, approved, updated, ended, cancelled) with versions, differences and
going back, the layer each approved programme owns (published between its dates, columns per audience: the
supervisor for the rooms only), the daily follow-up by a regional room, "copy last year's programme", and the beach
guarded by a programme point in the coastal risk (L1b)."""

import json
import uuid
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_system_sessionmaker
from app.modules.coastal import service as coastal
from app.modules.programmes import domain, service
from tests import test_coastal as coastal_test
from tests.test_coastal import beaches, sim_marine  # noqa: F401 (fixtures)

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/staff/programmes"
DATA = Path(__file__).resolve().parents[3] / "data" / "programmes" / "2026"
TODAY = service.today()
ALL = {"bbox": "7.4,30,11.7,37.6", "limit": 50}


def _admin(staff: Staff) -> dict[str, str]:
    return staff(["sysadmin"], gouvernorat=None)


def _code(prefix: str = "TEST") -> str:
    return f"{prefix}-{2000 + uuid.uuid4().int % 999}-{uuid.uuid4().hex[:5].upper()}"


def _file(
    code: str, *, valid_from: date | None = None, valid_to: date | None = None, shift: float = 0.0, **extra: Any
) -> bytes:
    """A beach programme: Bizerte (located, with a supervisor), Nabeul (no position), Sousse (closed)."""
    points = [
        {
            "point_id": f"{code}-01",
            "governorate": "بنزرت",
            "place_name": "شاطئ الكورنيش",
            "latitude": 37.2745,
            "longitude": 9.8739 + shift,
            "geo_confidence": "مرتفعة: شاطئ مسمّى في OSM",
            "supervisors": 1,
            "lifeguards_planned": 8,
            "lifeguards_deployed": 3,
            "hours": "10:00 - 18:00",
            "point_status": "مفتوحة",
            "supervisor_name": "الملازم س. م.",
            "supervisor_phone": "71000000",
        },
        {
            "point_id": f"{code}-02",
            "governorate": "نابل",
            "place_name": "الحمامات الكرنيش",
            "geo_confidence": "غير محدد: يحدده المدير على الخريطة",
            "lifeguards_planned": 7,
            "lifeguards_deployed": 9,
        },
        {
            "point_id": f"{code}-03",
            "governorate": "سوسة",
            "place_name": "بوجعفر",
            "latitude": 35.83,
            "longitude": 10.64,
            "geo_confidence": "تقريبية: مركز مدينة (البلدة لا النقطة)",
            "lifeguards_planned": 5,
            "point_status": "مغلقة",
        },
    ]
    return json.dumps(
        {
            "programmes": [
                {
                    "program_id": code,
                    "program_type": "التركز بالشواطئ",
                    "title": "التركيز بالشواطئ (اختبار)",
                    "season": "صائفة",
                    "valid_from": (valid_from or TODAY - timedelta(days=5)).isoformat(),
                    "valid_to": (valid_to or TODAY + timedelta(days=30)).isoformat(),
                    "version": 1,
                    "status": "معتمد",
                    "declared_lifeguards_planned": 21,
                    "points": points,
                    **extra,
                }
            ]
        },
        ensure_ascii=False,
    ).encode()


async def _import(client: httpx.AsyncClient, headers: dict[str, str], data: bytes, **params: Any) -> httpx.Response:
    return await client.post(
        f"{URL}/imports",
        params={"file_name": "p.json", **params},
        content=data,
        headers={**headers, "Content-Type": "application/octet-stream"},
    )


async def _create(client: httpx.AsyncClient, staff: Staff, code: str, **kw: Any) -> dict[str, Any]:
    r = await _import(client, _admin(staff), _file(code, **kw), apply="true", reason="first load of the programme")
    assert r.status_code == 200, r.text
    found = [p for p in (await client.get(URL, headers=_admin(staff))).json()["items"] if p["code"] == code]
    return found[0]


# ---------------------------------------------------------------- files (no database)


def test_the_2026_files_read_alike() -> None:
    counts = {}
    for name in ("programmes_2026.json", "e-himaya_programmes_template_2026.xlsx", "programme_points_2026.csv"):
        parsed = domain.parse(name, (DATA / name).read_bytes())
        assert parsed.errors == []
        counts[name] = {p.code: len(p.points) for p in parsed.programmes}
        beach = next(p for p in parsed.programmes if p.code == "BEACH-2026")
        assert sum(1 for p in beach.points if p["lat"] is None) == 36
        assert domain.totals(beach.points)["lifeguards_planned"] == 2293
        # The repository keeps no supervisor's name or phone (they stay outside it, design §5).
        assert not any(p.get("supervisor_name") or p.get("supervisor_phone") for p in beach.points)
    assert len({json.dumps(c, sort_keys=True) for c in counts.values()}) == 1
    assert counts["programmes_2026.json"] == {"ROAD-2026": 10, "SEAS-2026": 18, "BEACH-2026": 185}


def test_problems_are_reported() -> None:
    parsed = domain.check(
        "csv",
        [],
        [
            {
                "program_id": "X-2026",
                "point_id": "A",
                "governorate": "تونس",
                "place_name": "p",
                "latitude": "40",
                "longitude": "10",
            },
            {"program_id": "X-2026", "point_id": "B", "governorate": "تونس", "place_name": "p", "latitude": "36.8"},
            {"program_id": "X-2026", "point_id": "C", "governorate": "تونس", "place_name": "p", "staff_count": "-1"},
            {"program_id": "X-2026", "point_id": "D", "governorate": "تونس", "place_name": "p"},
            {"program_id": "X-2026", "point_id": "D", "governorate": "تونس", "place_name": "p"},
            {"program_id": "", "point_id": "E", "place_name": "p"},
        ],
    )
    assert [e.code for e in parsed.errors] == [
        "outside_tunisia",
        "bad_coordinates",
        "bad_number",
        "duplicate_point",
        "programme_missing",
    ]
    assert [w.code for w in parsed.warnings] == ["no_position"]
    assert domain.confidence_of("تقريبية: مركز قرية (البلدة لا النقطة)", True) == "approximate"
    assert domain.normalize("أريانة") == domain.normalize("اريانه")


def test_diff_between_versions() -> None:
    before = {"programme": {"title": "a"}, "points": {"1": {"status": "open"}, "2": {"status": "open"}}}
    after = {"programme": {"title": "b"}, "points": {"1": {"status": "closed"}, "3": {"status": "open"}}}
    assert domain.diff(before, after) == {
        "programme": {"title": ["a", "b"]},
        "added": ["3"],
        "removed": ["2"],
        "changed": {"1": {"status": ["open", "closed"]}},
    }


# ---------------------------------------------------------------- the flow


async def test_import_preview_then_apply(client: httpx.AsyncClient, staff: Staff) -> None:
    code = _code()
    admin = _admin(staff)
    preview = await _import(client, admin, _file(code))
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["applied"] is False
    found = body["programmes"][0]
    assert found == {
        **found,
        "code": code,
        "exists": False,
        "points": 3,
        "unlocated": 1,
        "computed": {"staff": 0, "lifeguards_planned": 20, "lifeguards_deployed": 12},
        "declared": {"lifeguards_planned": 21},
    }
    assert {w["code"] for w in body["warnings"]} == {
        "no_position",
        "deployed_above_planned",
        "total_lifeguards_planned",
    }
    assert not [p for p in (await client.get(URL, headers=admin)).json()["items"] if p["code"] == code]
    # Applying needs a reason; a regional room may not import.
    assert (await _import(client, admin, _file(code), apply="true")).status_code == 422
    regional = staff(["ops_manager"], gouvernorat=23)
    assert (await _import(client, regional, _file(code), apply="true", reason="x" * 6)).status_code == 403
    programme = await _create(client, staff, code)
    assert programme["status"] == "draft"
    assert programme["figures"] == {
        "points": 3,
        "unlocated": 1,
        "open": 2,
        "gouvernorats": 3,
        "staff": 0,
        "lifeguards_planned": 20,
        "lifeguards_deployed": 12,
    }
    assert programme["layer_key"] is None
    # Importing the same file again shows no difference.
    again = (await _import(client, admin, _file(code))).json()["programmes"][0]
    assert again["exists"] is True
    assert again["diff"] == {**again["diff"], "programme": {}, "added": [], "removed": [], "changed": {}}
    bad = await _import(client, admin, b"\x00\x01", file_name="x.bin")
    assert bad.status_code == 422 and bad.json()["detail"] == "file_format"


async def test_life_cycle_and_the_layer(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    code = _code()
    admin = _admin(staff)
    programme = await _create(client, staff, code)
    pid = programme["id"]
    approved = await client.post(f"{URL}/{pid}/approve", json={}, headers=admin)
    assert approved.status_code == 200, approved.text
    detail = approved.json()
    assert detail["programme"]["status"] == "approved"
    assert detail["programme"]["live"] is True
    key = detail["programme"]["layer_key"]
    assert key == service.layer_key(code)

    # The layer: the citizen sees the open, located points, without counts or supervisor.
    public = (await client.get(f"/api/v1/layers/{key}/features", params=ALL)).json()["items"]
    assert [f["name"] for f in public] == ["شاطئ الكورنيش"]
    assert "supervisor_phone" not in public[0]["props"] and "lifeguards_planned" not in public[0]["props"]
    assert public[0]["props"]["hours"] == "10:00 - 18:00"
    room = staff(["operator"], gouvernorat=23)
    rows = (await client.get(f"/api/v1/staff/layers/{key}/features", headers=room)).json()["items"]
    corniche = next(r for r in rows if r["name"] == "شاطئ الكورنيش")
    assert corniche["props"]["supervisor_phone"] == "71000000"
    assert next(r for r in rows if r["name"] == "بوجعفر")["hidden"] is True  # closed
    field = staff(["field_commander"], gouvernorat=23)
    rows = (await client.get(f"/api/v1/staff/layers/{key}/features", headers=field)).json()["items"]
    corniche = next(r for r in rows if r["name"] == "شاطئ الكورنيش")
    assert "supervisor_phone" not in corniche["props"] and corniche["props"]["lifeguards_planned"] == 8

    # The programme page: the supervisor for the rooms only; a regional room sees its own gouvernorat.
    seen = (await client.get(f"{URL}/{pid}", headers=room)).json()
    assert [p["ref"] for p in seen["points"]] == [f"{code}-01"]
    assert seen["points"][0]["supervisor_phone"] == "71000000" and seen["points"][0]["can_follow_up"] is True
    commander = (await client.get(f"{URL}/{pid}", headers=staff(["local_committee"], gouvernorat=23))).json()
    assert commander["points"][0]["supervisor_phone"] is None

    # The daily follow-up by the Bizerte room: deployed lifeguards and status only, its own points only.
    first, nabeul = seen["points"][0]["id"], None
    full = (await client.get(f"{URL}/{pid}", headers=admin)).json()
    nabeul = next(p["id"] for p in full["points"] if p["ref"] == f"{code}-02")
    r = await client.patch(f"{URL}/{pid}/points/{first}", json={"lifeguards_deployed": 8}, headers=room)
    assert r.status_code == 200, r.text
    assert r.json()["programme"]["status"] == "updated"
    assert (await client.patch(f"{URL}/{pid}/points/{first}", json={"place_name": "x" * 5}, headers=room)).json()[
        "detail"
    ] == "follow_up_only"
    assert (
        await client.patch(f"{URL}/{pid}/points/{nabeul}", json={"status": "closed"}, headers=room)
    ).status_code == 403

    # The manager places the point without a position on the map: it appears on the layer.
    r = await client.patch(
        f"{URL}/{pid}/points/{nabeul}",
        json={"lat": 36.395, "lon": 10.615, "reason": "placed on the map"},
        headers=admin,
    )
    assert r.status_code == 200, r.text
    placed = next(p for p in r.json()["points"] if p["id"] == nabeul)
    assert placed["geo_confidence"] == "confirmed"
    public = (await client.get(f"/api/v1/layers/{key}/features", params=ALL)).json()["items"]
    assert sorted(f["name"] for f in public) == ["الحمامات الكرنيش", "شاطئ الكورنيش"]

    # Versions: what each change did, and going back.
    revisions = (await client.get(f"{URL}/{pid}/revisions", headers=admin)).json()["items"]
    assert [r["action"] for r in revisions] == ["point_update", "follow_up", "approve", "import"]
    diff = (await client.get(f"{URL}/{pid}/revisions/{revisions[1]['number']}/diff", headers=admin)).json()
    assert diff["changed"] == {f"{code}-01": {"lifeguards_deployed": [3, 8]}}
    back = await client.post(
        f"{URL}/{pid}/revisions/{revisions[2]['number']}/restore", json={"reason": "wrong count"}, headers=admin
    )
    assert back.status_code == 200, back.text
    restored = {p["ref"]: p for p in back.json()["points"]}
    assert restored[f"{code}-01"]["lifeguards_deployed"] == 3
    assert restored[f"{code}-02"]["lat"] is None
    assert back.json()["programme"]["status"] == "updated"

    # Deleting: a point of an approved programme is closed instead; the programme is cancelled, not deleted.
    assert (await client.delete(f"{URL}/{pid}/points/{first}", headers=admin)).json()["detail"] == "close_instead"
    assert (await client.delete(f"{URL}/{pid}", headers=admin)).json()["detail"] == "cancel_instead"
    assert (await client.post(f"{URL}/{pid}/cancel", json={"reason": ""}, headers=admin)).status_code == 422
    cancelled = await client.post(f"{URL}/{pid}/cancel", json={"reason": "programme replaced"}, headers=admin)
    assert cancelled.json()["programme"]["status"] == "cancelled"
    assert (await client.get(f"/api/v1/layers/{key}/features", params=ALL)).status_code == 404


async def test_dates_publish_and_end(client: httpx.AsyncClient, staff: Staff) -> None:
    code = _code()
    admin = _admin(staff)
    programme = await _create(
        client, staff, code, valid_from=TODAY + timedelta(days=3), valid_to=TODAY + timedelta(days=10)
    )
    detail = (await client.post(f"{URL}/{programme['id']}/approve", json={}, headers=admin)).json()
    key = detail["programme"]["layer_key"]
    assert detail["programme"]["live"] is False
    assert (await client.get(f"/api/v1/layers/{key}/features", params=ALL)).status_code == 404
    async with get_system_sessionmaker()() as session:
        await service.lifecycle(session, TODAY + timedelta(days=3))
        await session.commit()
    assert (await client.get(f"/api/v1/layers/{key}/features", params=ALL)).status_code == 200
    async with get_system_sessionmaker()() as session:
        result = await service.lifecycle(session, TODAY + timedelta(days=11))
        await session.commit()
    assert result["ended"] >= 1
    after = (await client.get(f"{URL}/{programme['id']}", headers=admin)).json()["programme"]
    assert after["status"] == "ended" and after["can_edit"] is False
    assert (await client.get(f"/api/v1/layers/{key}/features", params=ALL)).status_code == 404


async def test_draft_points_and_copy(client: httpx.AsyncClient, staff: Staff) -> None:
    admin = _admin(staff)
    code = _code("ROAD")
    r = await client.post(
        URL,
        json={
            "code": code,
            "kind": "road",
            "title": "نقاط النجدة (اختبار)",
            "valid_from": TODAY.isoformat(),
            "valid_to": (TODAY + timedelta(days=60)).isoformat(),
        },
        headers=admin,
    )
    assert r.status_code == 201, r.text
    pid = r.json()["programme"]["id"]
    assert (await client.post(f"{URL}/{pid}/approve", json={}, headers=admin)).json()["detail"] == "no_points"
    added = await client.post(
        f"{URL}/{pid}/points",
        json={
            "ref": f"{code}-01",
            "place_name": "الطريق السيارة أ1 كم 31",
            "gouvernorat_code": 51,
            "lat": 36.57,
            "lon": 10.51,
        },
        headers=admin,
    )
    assert added.status_code == 201, added.text
    point = added.json()["points"][0]
    assert point["geo_confidence"] == "confirmed"
    assert (
        await client.post(f"{URL}/{pid}/points", json={"ref": f"{code}-01", "place_name": "xx"}, headers=admin)
    ).status_code == 409
    new_code = _code("ROAD")
    copy = await client.post(
        f"{URL}/{pid}/copy",
        json={"code": new_code, "valid_from": TODAY.isoformat(), "valid_to": (TODAY + timedelta(days=9)).isoformat()},
        headers=admin,
    )
    assert copy.status_code == 201, copy.text
    assert [p["ref"] for p in copy.json()["points"]] == [f"{new_code}-01"]
    # A draft and its points are deleted outright.
    assert (await client.delete(f"{URL}/{pid}/points/{point['id']}", headers=admin)).status_code == 200
    assert (await client.delete(f"{URL}/{pid}", headers=admin)).status_code == 204
    assert (await client.get(f"{URL}/{pid}", headers=admin)).status_code == 404
    assert (
        await client.post(
            URL,
            json={"code": "bad", "kind": "road", "title": "abc", "valid_from": "2026-01-01", "valid_to": "2026-01-02"},
            headers=admin,
        )
    ).status_code == 422
    assert (await client.get(URL, headers=staff(["operator"], gouvernorat=11))).json()["can_create"] is False


async def test_a_programme_point_guards_the_beach(client: httpx.AsyncClient, staff: Staff) -> None:
    code = _code()
    programme = await _create(client, staff, code, shift=-0.5)
    async with get_system_sessionmaker()() as session:
        assert await service.guarded_near(session, 37.2750, 9.3740, TODAY) is None
    await client.post(f"{URL}/{programme['id']}/approve", json={}, headers=_admin(staff))
    async with get_system_sessionmaker()() as session:
        assert await service.guarded_near(session, 37.2750, 9.3740, TODAY) == f"{code} v2"
        # The closed point in Sousse guards nothing; far from any point, nothing either.
        assert await service.guarded_near(session, 35.83, 10.64, TODAY) is None
        assert await service.guarded_near(session, 37.2745, 9.3739, TODAY + timedelta(days=40)) is None


@pytest.mark.parametrize("name", ["programmes_2026.json"])
async def test_the_2026_programmes_import(client: httpx.AsyncClient, staff: Staff, name: str) -> None:
    preview = await _import(client, _admin(staff), (DATA / name).read_bytes(), file_name=name)
    assert preview.status_code == 200, preview.text
    found = {p["code"]: p for p in preview.json()["programmes"]}
    assert found["BEACH-2026"]["points"] == 185 and found["BEACH-2026"]["unlocated"] == 36
    assert found["SEAS-2026"]["kind"] == "seasonal"
    assert not [e for e in preview.json()["errors"] if e["code"] == "unknown_gouvernorat"]


async def test_the_coastal_risk_follows_the_programme(
    client: httpx.AsyncClient,
    staff: Staff,
    session: AsyncSession,
    beaches: dict[str, Any],  # noqa: F811
    sim_marine: None,  # noqa: F811
) -> None:
    """A beach of the coastal layer marked unguarded gets no "unguarded" points once an open programme point is near."""
    north = beaches["ids"]["شاطئ الكورنيش"]

    async def factors() -> set[str]:
        await coastal.refresh(get_system_sessionmaker(), coastal_test.NOW)
        row = (
            await session.execute(
                text("SELECT factors, inputs FROM coastal.beach_day WHERE feature_id = :f AND day = :d"),
                {"f": north, "d": coastal_test.SWELL_DAY},
            )
        ).one()
        return {f["code"] for f in row.factors} | (
            {"by:" + row.inputs["guarded_by"]} if row.inputs.get("guarded_by") else set()
        )

    assert "unguarded" in await factors()
    code = _code()
    programme = await _create(client, staff, code, valid_from=date(2026, 6, 1), valid_to=date(2026, 9, 30))
    await client.post(f"{URL}/{programme['id']}/approve", json={}, headers=_admin(staff))
    found = await factors()
    assert "unguarded" not in found and f"by:{code} v2" in found
    # Cancelled, the programme guards nothing: the coastal tests that follow see the beach as it was.
    await client.post(f"{URL}/{programme['id']}/cancel", json={"reason": "fin du test"}, headers=_admin(staff))
    assert "unguarded" in await factors()
