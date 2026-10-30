"""SNACR (docs/phase-s/design-s.md): cleaning the Office's archive, the [SIM] years, the analysis, the specific risks
and the plans with their committees."""

from collections.abc import Callable
from datetime import datetime

import httpx
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog
from app.modules.snacr import domain, simulate
from app.modules.snacr.models import Intervention

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/staff/snacr"
NABEUL, SIDI_BOUZID, MONASTIR = 21, 43, 52


def _places() -> domain.Places:
    return domain.places_from(
        [(52, "المنستير"), (22, "زغوان"), (13, "بن عروس"), (32, "جندوبة")],
        [(52, 5208, "المنستير"), (22, 2205, "زغوان"), (32, 3205, "غار الدماء"), (13, 1301, "بن عروس")],
        [(52, "المنستير المدينة", 5208)],
    )


def test_names_are_compared_loosely_and_through_aliases() -> None:
    assert domain.normalize("  أريانة   المدينة ") == "اريانه المدينه"
    assert domain.compact("غارالدماء") == domain.compact("غار الدماء")
    places = _places()
    assert places.gouvernorat("المنستير") == 52
    assert places.delegation(52, "المنستير المدينة") == (5208, None)
    assert places.delegation(32, "غارالدماء") == (3205, None)
    # Filed under the wrong gouvernorat but known elsewhere once: reassigned, and said so.
    assert places.delegation(13, "زغوان") == (2205, "delegation_reassigned")
    assert places.delegation(52, "مكان لا وجود له") == (None, "delegation_unmatched")


def test_natures_and_subtypes() -> None:
    assert domain.family_of("الإسعاف في غير حوادث المرور") == "medical"
    assert domain.family_of("النجدة والإسعاف على الطرقات") == "road"
    assert domain.family_of("مجابهة الحرائق") == "fire"
    assert domain.family_of("الإنقاذ") == "rescue"
    assert domain.family_of("طلب معلومات") is None
    assert domain.clean_subtype("محتلفة") == "مختلفة"
    assert domain.clean_subtype(" ") is None


def test_cleaning_flags_without_dropping() -> None:
    quality = domain.Quality()
    base = {
        "called": "2023-05-01 10:00:00",
        "gouvernorat": "المنستير",
        "delegation": "المنستير المدينة",
        "nature": "الإنقاذ",
    }
    ok = domain.clean({**base, "arrived": "2023-05-01 10:12:00"}, _places(), quality)
    assert ok is not None and ok.arrival_min == 12 and ok.flags == [] and ok.delegation_id == 5208
    early = domain.clean({**base, "arrived": "2023-05-01 09:00:00"}, _places(), quality)
    assert early is not None and "arrival_negative" in early.flags
    missing = domain.clean(base, _places(), quality)
    assert missing is not None and missing.flags == ["arrival_missing"]
    assert domain.clean({**base, "nature": "؟"}, _places(), quality) is None
    assert domain.clean({**base, "called": ""}, _places(), quality) is None
    out = quality.out()
    assert out["kept"] == 3 and out["skipped"] == {"nature_unknown": 1, "called_missing": 1}
    assert out["by_gouvernorat"]["52"]["arrival_complete_pct"] == 33.3


def test_grades() -> None:
    assert domain.zone_of(10_000, 5.0, 1000, 150) == "urban"
    assert domain.zone_of(10_000, 50.0, 1000, 150) == "periurban"
    assert domain.zone_of(None, 50.0, 1000, 150) == "rural"
    breaks = domain.quintile_breaks([float(x) for x in range(1, 11)])
    assert domain.frequency_level(1.0, breaks) == 1 and domain.frequency_level(10.0, breaks) == 5
    assert (
        domain.coverage_level(95, 90) == 1
        and domain.coverage_level(75, 90) == 3
        and domain.coverage_level(None, 90) is None
    )
    assert (
        domain.priority_of(5, 3) == "high"
        and domain.priority_of(2, 4) == "medium"
        and domain.priority_of(1, 1) == "low"
    )
    assert domain.special_level(4, 5) == "high"


def test_simulation_follows_the_2022_profile() -> None:
    rows = list(simulate.generate(2031, 2_000))
    assert len(rows) == 2_000 and rows == list(simulate.generate(2031, 2_000))
    assert all(r["called"].year == 2031 for r in rows)
    families = {domain.family_of(r["nature"]) for r in rows}
    assert families == {"medical", "road", "fire", "rescue"}
    # The archive's defects are kept: missing and impossible arrivals.
    assert any(r["arrived"] is None for r in rows)
    assert any(r["arrived"] is not None and r["arrived"] < r["called"] for r in rows)
    # Aggregates only in the profile: no address, free text or person.
    profile = simulate.profile()
    assert set(profile) >= {"cells", "month", "weekday_hour", "arrival"} and "rows_data" not in profile
    assert all(set(c) == {"gouvernorat", "delegation", "family", "count"} for c in profile["cells"])


def _csv(rows: list[list[str]]) -> bytes:
    head = [
        "NUM_SEQUENTIEL", "DATE_D", "DATE_S", "DATE_AR_SP", "DATE_F", "NOM_DIREC_REG", "DESIG_DELEG", "DESIGNATION",
        "DESIGNATION_1", "ADRESSE", "DESC_FINALE", "VEHICULES",
    ]  # fmt: skip
    lines = [",".join(head), *(",".join(r) for r in rows)]
    return ("\n".join(lines) + "\n").encode()


async def test_archive_analysis_and_plan(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    central = staff(["central_committee"], gouvernorat=None)
    room = staff(["ops_manager"], gouvernorat=None)
    # What an earlier run on the same database left: the alias this test adds, the [SIM] entry it edits.
    await session.execute(text("DELETE FROM snacr.alias WHERE raw = 'سيدي بوزيد المدينة'"))
    await session.execute(
        text("UPDATE snacr.special_risk SET simulated = true WHERE gouvernorat_code = 21 AND hazard = 'flood'")
    )
    await session.commit()
    # Only the national level loads the archive.
    r = await client.post(
        f"{URL}/datasets/simulate", params={"year": 2031, "rows": 100}, headers=staff(["ops_manager"])
    )
    assert r.status_code == 403
    for year in (2031, 2032):
        r = await client.post(f"{URL}/datasets/simulate", params={"year": year, "rows": 1500}, headers=room)
        assert r.status_code == 201, r.text
        assert r.json()["dataset"]["simulated"] is True
    # The Office's file: the address, the description and the vehicles are never stored.
    body = _csv(
        [
            ["1", "2033-07-02 14:00:00", "2033-07-02 14:02:00", "2033-07-02 14:11:00", "2033-07-02 15:00:00",
             "نابل", "الحمامات", "مجابهة الحرائق", "بمواد غابية و أعشاب", "نهج الياسمين", "فلان الفلاني 40 سنة",
             "51428"],
            ["2", "2033-07-03 09:00:00", "", "", "2033-07-03 10:00:00",
             "سيدي بوزيد", "سيدي بوزيد المدينة", "الإسعاف في غير حوادث المرور", "توعك صحي", "", "", ""],
            ["3", "2033-07-03 09:00:00", "", "", "", "نابل", "قليبية", "طلب معلومات", "", "", "", ""],
        ]
    )  # fmt: skip
    r = await client.post(
        f"{URL}/datasets", params={"year": 2033, "file_name": "2033.csv"}, content=body, headers=central
    )
    assert r.status_code == 201, r.text
    quality = r.json()["dataset"]["quality"]
    assert r.json()["dataset"]["rows"] == 2 and quality["skipped"] == {"nature_unknown": 1}
    assert quality["unmatched"] == [{"gouvernorat_code": SIDI_BOUZID, "raw": "سيدي بوزيد المدينة", "rows": 1}]
    stored = (await session.execute(text("SELECT * FROM snacr.intervention WHERE year = 2033"))).mappings().all()
    assert all("فلان" not in str(dict(row)) and "الياسمين" not in str(dict(row)) for row in stored)
    assert not {"adresse", "address", "description", "vehicles"} & set(stored[0].keys())
    bad = await client.post(f"{URL}/datasets", params={"year": 2034, "file_name": "x.csv"}, content=b"A,B\n1,2\n",
                            headers=central)  # fmt: skip
    assert bad.status_code == 422 and bad.json()["detail"] == "file_columns_missing"

    # An alias ties the unmatched name, and the stored row follows.
    sidi = (await client.get("/api/v1/geo/gouvernorats/43/delegations")).json()
    west = next(d["id"] for d in sidi if "الغربية" in d["name_ar"])
    r = await client.post(
        f"{URL}/aliases",
        json={"gouvernorat_code": SIDI_BOUZID, "raw": "سيدي بوزيد المدينة", "delegation_id": west},
        headers=central,
    )
    assert r.status_code == 201, r.text
    assert r.json()["rows_fixed"] >= 1
    r = await client.post(
        f"{URL}/aliases",
        json={"gouvernorat_code": SIDI_BOUZID, "raw": "سيدي  بوزيد المدينة", "delegation_id": west},
        headers=central,
    )
    assert r.status_code == 409
    unmatched = (await client.get(f"{URL}/unmatched", headers=central)).json()
    assert all(u["raw"] != "سيدي بوزيد المدينة" for u in unmatched)

    # The analysis: national for the central room, own gouvernorat for a regional account.
    overview = (await client.get(URL, headers=central)).json()
    assert overview["default_years"][-3:] == [2031, 2032, 2033] and overview["method"]["goal"] == 90
    assert any(ref["code"] == "TN-93-942" for ref in overview["references"])
    a = (await client.get(f"{URL}/analysis", params={"years": "2031,2032"}, headers=central)).json()
    assert a["simulated"] is True and a["totals"]["rows"] == 3000
    assert sum(sum(row) for row in a["matrix"]) == sum(1 for d in a["delegations"] if d["priority"])
    assert {d["zone"] for d in a["delegations"]} <= {"urban", "periurban", "rural"}
    regional = staff(["local_committee"], gouvernorat=NABEUL)
    mine = (await client.get(f"{URL}/analysis", params={"years": "2031,2032"}, headers=regional)).json()
    assert {g["code"] for g in mine["gouvernorats"]} == {NABEUL}
    assert (await client.get(f"{URL}/analysis", params={"gouvernorat": MONASTIR}, headers=regional)).status_code == 403
    assert (await client.get(f"{URL}/analysis", params={"years": "1999"}, headers=central)).status_code == 422
    assert (await client.get(URL, headers=staff(["operator"]))).status_code == 403

    # Specific risks: a regional committee edits its own gouvernorat; an edited [SIM] entry becomes real.
    risks = (await client.get(f"{URL}/special-risks", headers=regional)).json()
    assert risks and all(x["gouvernorat_code"] == NABEUL for x in risks)
    flood = next(x for x in risks if x["hazard"] == "flood")
    assert flood["simulated"] is True
    r = await client.post(
        f"{URL}/special-risks",
        json={"gouvernorat_code": NABEUL, "hazard": "flood", "probability": 5, "gravity": 4, "note": "أودية الحمامات"},
        headers=regional,
    )
    assert r.status_code == 200 and r.json()["simulated"] is False and r.json()["level"] == "high"
    r = await client.post(
        f"{URL}/special-risks",
        json={"gouvernorat_code": MONASTIR, "hazard": "flood", "probability": 2, "gravity": 2},
        headers=regional,
    )
    assert r.status_code == 403

    # Plans: the regional committee drafts and approves its own; the national plan is the national level's.
    r = await client.post(f"{URL}/plans", json={"gouvernorat_code": NABEUL, "years": [2031, 2032]}, headers=regional)
    assert r.status_code == 201, r.text
    plan = r.json()
    assert plan["status"] == "draft" and plan["simulated"] is True and plan["can_approve"] is True
    assert any(o["kind"] == "special" and o["hazard"] == "flood" for o in plan["objective_list"])
    assert (await client.post(f"{URL}/plans", json={}, headers=regional)).status_code == 403
    other = staff(["local_committee"], gouvernorat=MONASTIR)
    assert (await client.get(f"{URL}/plans/{plan['id']}", headers=other)).status_code == 404
    r = await client.post(f"{URL}/plans/{plan['id']}/approve", headers=regional)
    assert r.status_code == 200 and r.json()["status"] == "approved"
    assert r.json()["review_due"] and r.json()["valid_until"]
    assert (await client.post(f"{URL}/plans/{plan['id']}/approve", headers=regional)).status_code == 409
    second = (await client.post(f"{URL}/plans", json={"gouvernorat_code": NABEUL}, headers=regional)).json()
    assert second["version"] == plan["version"] + 1
    await client.post(f"{URL}/plans/{second['id']}/approve", headers=regional)
    first = (await client.get(f"{URL}/plans/{plan['id']}", headers=regional)).json()
    assert first["status"] == "superseded"

    national = (await client.post(f"{URL}/plans", json={"years": [2031, 2032, 2033]}, headers=central)).json()
    assert national["gouvernorat_code"] is None
    assert (await client.post(f"{URL}/plans/{national['id']}/approve", headers=room)).status_code == 403
    page = await client.get(f"{URL}/plans/{national['id']}/document", params={"format": "html"}, headers=central)
    assert page.status_code == 200 and "المخطط الوطني لتحليل المخاطر وتغطيتها" in page.text and "[SIM]" in page.text
    assert "اللجنة الوطنية برئاسة السيد وزير الداخلية" in page.text
    pdf = await client.get(f"{URL}/plans/{national['id']}/document", headers=central)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

    actions = set((await session.scalars(select(AuditLog.action).where(AuditLog.action.like("snacr.%")))).all())
    assert {"snacr.dataset_imported", "snacr.dataset_simulated", "snacr.alias_created", "snacr.special_risk_saved",
            "snacr.plan_drafted", "snacr.plan_approved"} <= actions  # fmt: skip

    # Replacing a year replaces its rows.
    r = await client.post(f"{URL}/datasets/simulate", params={"year": 2031, "rows": 200}, headers=room)
    assert r.status_code == 201
    count = await session.scalar(select(func.count()).select_from(Intervention).where(Intervention.year == 2031))
    assert count == 200
    for year in (2031, 2032, 2033):  # the test years never stay among the last three of a shared database
        assert (await client.delete(f"{URL}/datasets/{year}", headers=room)).status_code == 204
    assert datetime.now().year < 2031  # the test years stay clear of real ones
