"""Intervention plans by hazard (phase PL1, docs/phase-pl/design-plans.md §2): the hazards and their colours kept by
the central room, a plan recorded once with its PDF and read on the screen (audited), the plan in force for each
hazard nationally and in each gouvernorat the reader sees, a new version repealing the previous one, and the plans
offered to a crisis axis of the same hazard."""

import secrets
from collections.abc import Callable
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import FakeStore

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/staff/register"
NABEUL, SOUSSE = 21, 51
PDF = b"%PDF-1.7\n1 0 obj << >> endobj\n%%EOF\n"
AREA = {
    "type": "Polygon",
    "coordinates": [[[10.60, 36.35], [10.85, 36.35], [10.85, 36.55], [10.60, 36.55], [10.60, 36.35]]],
}


def key() -> str:
    """A hazard of its own for one test, so a reused database does not mix the plans of two runs."""
    return "zz_" + "".join(secrets.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(10))


def hazard(colour: str = "#1976D2", **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "name": {"ar": "خطر تجريبي", "fr": "Risque d'essai", "en": "Test hazard"},
        "colour": colour,
        "icon": "water",
        "position": 90,
    }
    body.update(overrides)
    return body


def plan(hazard_key: str, title: str, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "kind": "plan",
        "hazard_key": hazard_key,
        "level": "central",
        "issuer": "اللجنة الوطنية للحماية المدنية",
        "title": title,
        "summary": "[SIM] المخطط الوطني للتدخل",
        "topics": ["civil_protection"],
        "issued_on": "2026-01-15",
    }
    body.update(overrides)
    return body


async def create(client: httpx.AsyncClient, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
    r = await client.post(f"{URL}/documents", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["document"]  # type: ignore[no-any-return]


def of(overview: dict[str, Any], hazard_key: str) -> dict[str, Any]:
    return next(h for h in overview["hazards"] if h["hazard"]["key"] == hazard_key)


async def test_hazards_are_kept_by_the_central_room(client: httpx.AsyncClient, staff: Staff) -> None:
    centre = staff(["central_committee"], gouvernorat=None)
    seeded = (await client.get(f"{URL}/hazards", headers=staff(["operator"], gouvernorat=NABEUL))).json()
    floods = next(h for h in seeded if h["key"] == "floods")
    assert floods["colour"] == "#1976D2" and floods["name"]["ar"] == "الفيضانات"

    k = key()
    regional = staff(["ops_manager"], gouvernorat=NABEUL)
    assert (await client.put(f"{URL}/hazards/{k}", json=hazard(), headers=regional)).status_code == 403
    bad = await client.put(f"{URL}/hazards/{k}", json=hazard("blue"), headers=centre)
    assert bad.status_code == 422
    assert (await client.put(f"{URL}/hazards/{k}", json=hazard(), headers=centre)).status_code == 200
    r = await client.put(f"{URL}/hazards/{k}", json=hazard("#188038", active=False), headers=centre)
    assert r.status_code == 200 and r.json()["colour"] == "#188038" and not r.json()["active"]
    # A switched-off hazard is not offered to a new plan, nor listed on the plans page.
    r = await client.post(f"{URL}/documents", json=plan(k, "مخطط"), headers=centre)
    assert r.status_code == 422 and r.json()["detail"] == "hazard_unknown"
    assert k not in {h["hazard"]["key"] for h in (await client.get(f"{URL}/plans", headers=centre)).json()["hazards"]}
    # Only a plan has a hazard.
    await client.put(f"{URL}/hazards/{k}", json=hazard(), headers=centre)
    r = await client.post(f"{URL}/documents", json=plan(k, "مذكرة", kind="memo"), headers=centre)
    assert r.status_code == 422 and r.json()["detail"] == "hazard_only_for_plans"


async def test_plan_in_force_by_hazard_versions_and_viewer(
    client: httpx.AsyncClient, staff: Staff, fake_store: FakeStore, session: AsyncSession
) -> None:
    centre = staff(["central_committee"], gouvernorat=None)
    k = key()
    await client.put(f"{URL}/hazards/{k}", json=hazard(), headers=centre)
    first = await create(client, centre, plan(k, "المخطط الأزرق 2025", issued_on="2025-01-10"))
    second = await create(client, centre, plan(k, "المخطط الأزرق 2026"))
    r = await client.post(
        f"{URL}/documents/{first['id']}/repeal",
        json={"reason": "النسخة الجديدة المعتمدة", "by_document_id": second["id"]},
        headers=centre,
    )
    assert r.status_code == 200, r.text
    nabeul_plan = await create(
        client,
        staff(["ops_manager"], gouvernorat=NABEUL),
        plan(k, "ملحق نابل", level="regional", gouvernorat_code=NABEUL, issuer="اللجنة الجهوية بنابل"),
    )
    await create(
        client,
        staff(["ops_manager"], gouvernorat=SOUSSE),
        plan(k, "ملحق سوسة", level="regional", gouvernorat_code=SOUSSE, issuer="اللجنة الجهوية بسوسة"),
    )
    # A draft is not a plan yet.
    await create(client, centre, plan(k, "مسودة", publish=False))

    overview = of((await client.get(f"{URL}/plans", headers=centre)).json(), k)
    assert overview["national"]["document"]["id"] == second["id"] and overview["national"]["versions"] == 2
    assert [p["document"]["gouvernorat_code"] for p in overview["regional"]] == [NABEUL, SOUSSE]
    # A regional room sees the national plan and its own gouvernorat's only.
    room = staff(["operator"], gouvernorat=NABEUL)
    mine = of((await client.get(f"{URL}/plans", headers=room)).json(), k)
    assert mine["national"]["document"]["id"] == second["id"]
    assert [p["document"]["id"] for p in mine["regional"]] == [nabeul_plan["id"]]

    # The PDF is recorded once and read on the screen; every opening is audited.
    url = f"{URL}/documents/{second['id']}/file"
    assert (await client.put(url, params={"file_name": "bleu.pdf"}, content=PDF, headers=centre)).status_code == 200
    r = await client.get(f"{url}/content", headers=room)
    assert r.status_code == 200 and r.content == PDF
    assert r.headers["content-type"] == "application/pdf" and "no-store" in r.headers["cache-control"]
    assert (await client.get(f"{URL}/documents/{first['id']}/file/content", headers=room)).status_code == 404
    count = await session.scalar(
        text("SELECT count(*) FROM audit.log WHERE action = 'register.file_read' AND target = :t"),
        {"t": second["id"]},
    )
    assert count == 1
    # Only a PDF is shown on the screen; an image stays behind its signed link.
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    url = f"{URL}/documents/{nabeul_plan['id']}/file"
    regional = staff(["ops_manager"], gouvernorat=NABEUL)
    assert (await client.put(url, params={"file_name": "carte.png"}, content=png, headers=regional)).status_code == 200
    r = await client.get(f"{url}/content", headers=room)
    assert r.status_code == 415 and r.json()["detail"] == "viewer_pdf_only"


async def test_a_crisis_axis_is_offered_the_plans_of_its_hazard(client: httpx.AsyncClient, staff: Staff) -> None:
    centre = staff(["central_committee"], gouvernorat=None)
    floods = await create(client, centre, plan("floods", "المخطط الأزرق للفيضانات [SIM]"))
    annex = await create(
        client,
        staff(["ops_manager"], gouvernorat=NABEUL),
        plan("floods", "ملحق نابل للفيضانات", level="regional", gouvernorat_code=NABEUL, issuer="اللجنة الجهوية بنابل"),
    )
    other = await create(
        client,
        staff(["ops_manager"], gouvernorat=SOUSSE),
        plan("floods", "ملحق سوسة للفيضانات", level="regional", gouvernorat_code=SOUSSE, issuer="اللجنة الجهوية بسوسة"),
    )
    r = await client.post(
        "/api/v1/staff/crisis/axes",
        json={"name": "فيضانات نابل [SIM]", "kind": "flood", "level": 3, "gouvernorat_code": NABEUL, "area": AREA},
        headers=staff(["ops_manager"], gouvernorat=None),
    )
    assert r.status_code == 201, r.text
    # The national flood plan in force comes first, then Nabeul's; not Sousse's.
    assert [d["id"] for d in r.json()["hazard_plans"]] == [floods["id"], annex["id"]]
    assert other["id"] not in {d["id"] for d in r.json()["hazard_plans"]}
