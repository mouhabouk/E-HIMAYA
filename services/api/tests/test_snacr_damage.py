"""The Office's damage tables (degat_forestieres, degat_Agriculteur) tied to the archive by NUM_SEQUENTIEL, and read
in a SNACR study: the surfaces burnt, the crops and fodder lost, their notes and their sheet (Yamen, 2026-11-01)."""

import io
from collections.abc import Callable

import httpx
from openpyxl import load_workbook
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.test_snacr_study import _row, _xlsx

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/staff/snacr"
ARIANA = 12

FOREST = (
    "﻿DGF_CLE;DGF_CO_NUM_SEQUENTIEL;DGF_TYPE_LIEU;DGF_LIBE_LIEU;SURFACE\r\n"
    '1;9101;4;"أعشاب جافة";0,5\r\n'
    '2;9102;95;"غابة شعراء";2\r\n'
    '3;9104;4;"أعشاب جافة";1,5\r\n'
    '4;;4;"أعشاب جافة";1\r\n'  # no intervention number: rejected
    '5;9999;1;"غابة مورقة";3\r\n'  # an intervention not in the archive: kept, not matched
)
AGRI = (
    "﻿DGA_CLE;DGA_CO_NUM_SEQUENTIEL;DGA_TYPE_LIEU;DGA_LIBE_LIEU;DGA_CODE_DEGAT;DGA_LIBE_DEGAT;DGA_CODE_UNITE;"
    "DGA_LIBE_UNITE;DGA_VALEUR\r\n"
    '1;9102;2;"مواد علفية و فلاحية";6;"تبن";3;"حزم(بالات)";100\r\n'
    '2;9104;83;"ضيعة فلاحية";;"حصيدة";1;"هكتار";0,25\r\n'  # the code of the crop taken from the reference list
    '3;9104;3;"مزرعة";1;"قمح";;"";2\r\n'  # the unit of the crop taken from the reference list
    '4;9104;3;"مزرعة";2;"شعير";1;"هكتار";abc\r\n'  # unreadable quantity: rejected
)


async def test_damages_tied_to_the_archive_and_read_in_a_study(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession
) -> None:
    central = staff(["central_committee"], gouvernorat=None)
    await session.execute(text("DELETE FROM snacr.study WHERE gouvernorat_code = :g"), {"g": ARIANA})
    await session.execute(text("DELETE FROM snacr.dataset WHERE year IN (2041, 2042)"))
    await session.commit()
    rows = [
        _row(9101, "2041-07-01T13:00", 9, "سكرة", "مجابهة الحرائق", "سكرة"),
        _row(9102, "2041-07-02T15:00", 12, "سكرة", "مجابهة الحرائق", "سكرة"),
        _row(9103, "2041-07-02T16:00", 5, "سكرة", "الإسعاف في غير حوادث المرور", "سكرة"),
        _row(9104, "2042-07-03T14:00", 11, "سكرة", "مجابهة الحرائق", "سكرة"),
    ]
    r = await client.post(f"{URL}/datasets", params={"file_name": "ariana.xlsx"}, content=_xlsx(rows),
                          headers=central)  # fmt: skip
    assert r.status_code == 201, r.text

    r = await client.post(f"{URL}/damages", params={"file_name": "degat_forestieres.csv"},
                          content=FOREST.encode(), headers=central)  # fmt: skip
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["kind"] == "forest" and out["read"] == 5 and out["kept"] == 4 and out["rejected"] == {"no_number": 1}
    r = await client.post(f"{URL}/damages", params={"file_name": "degat_Agriculteur.csv"},
                          content=AGRI.encode(), headers=central)  # fmt: skip
    out = r.json()
    assert out["kind"] == "agri" and out["kept"] == 3 and out["rejected"] == {"bad_value": 1}
    status = {s["kind"]: s for s in out["status"]}
    assert status["forest"]["lines"] == 4 and status["forest"]["matched"] == 3
    assert status["agri"]["matched"] == 3 and status["agri"]["years"] == [2041, 2042]
    stored = (
        await session.execute(
            text("SELECT crop_code, unit, value FROM snacr.damage WHERE kind = 'agri' ORDER BY source_key")
        )
    ).all()
    assert [tuple(s) for s in stored] == [("6", "bale", 100.0), ("4", "ha", 0.25), ("1", "ha", 2.0)]

    # A second import of the same kind replaces the first.
    r = await client.post(f"{URL}/damages", params={"file_name": "f.csv"}, content=FOREST.encode(), headers=central)
    assert (await client.get(f"{URL}/damages", headers=central)).json()[1]["lines"] == 4
    # Another file is refused, and the import is the central room's.
    r = await client.post(f"{URL}/damages", params={"file_name": "x.csv"}, content=b"A;B\n1;2\n", headers=central)
    assert r.status_code == 422 and r.json()["detail"] == "damage_file_unknown"
    local = staff(["local_committee"], gouvernorat=ARIANA)
    r = await client.post(f"{URL}/damages", params={"file_name": "f.csv"}, content=FOREST.encode(), headers=local)
    assert r.status_code == 403

    # The study reads the damages of its interventions, per year.
    r = await client.post(f"{URL}/studies", json={"gouvernorat_code": ARIANA, "years": [2041, 2042]}, headers=central)
    assert r.status_code == 201, r.text
    study = r.json()
    forest = {x["label"]: x for x in study["tables"]["damages"]["forest"]}
    assert forest["أعشاب جافة"]["per_year"] == {"2041": 0.5, "2042": 1.5} and forest["أعشاب جافة"]["outings"] == 2
    assert "غابة مورقة" not in forest  # its intervention is not in the archive
    assert study["findings"]["damages"]["forest_ha"] == {"2041": 2.5, "2042": 1.5}
    agri = {x["label"]: x for x in study["tables"]["damages"]["agri"]}
    assert agri["تبن"]["unit"] == "bale" and agri["تبن"]["total"] == 100
    texts = [n["text_ar"] for n in study["findings"]["notes"]]
    assert any(t.startswith("احترق 4 هكتار من الغابات والأعشاب والأراضي في 3 تدخلا") for t in texts)
    assert any(t.startswith("الخسائر الفلاحية: 2.25 هكتار") and "100 بالة (تبن)" in t for t in texts)
    xlsx = await client.get(f"{URL}/studies/{study['id']}/export", params={"format": "xlsx"}, headers=central)
    sheet = load_workbook(io.BytesIO(xlsx.content))["DEGATS"]
    assert sheet["A1"].value == "Nature" and sheet.max_row == 1 + len(forest) + len(agri)
    page = (await client.get(f"{URL}/studies/{study['id']}/export", params={"format": "html"}, headers=central)).text
    assert "المساحات المحترقة (هكتار)" in page and "الخسائر الفلاحية" in page

    await session.execute(text("DELETE FROM snacr.study WHERE gouvernorat_code = :g"), {"g": ARIANA})
    await session.execute(text("DELETE FROM snacr.dataset WHERE year IN (2041, 2042)"))
    await session.execute(text("DELETE FROM snacr.damage"))
    await session.commit()
