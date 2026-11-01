"""SNACR studies in the Office's format (methodology note, 2026-11-01): the regional file of several years merged into
the national years, the six tables (SEC_GLOB, SAP, SR, LCI, SB, DIV) per unit and délégation, the day and night
periods, the travel time, the archive of the previous study and the exports."""

import io
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

import httpx
from openpyxl import Workbook, load_workbook
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.snacr import domain

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/staff/snacr"
ARIANA, NABEUL = 12, 21
SOUKRA, KALAAT, MEDINA = 1204, 1203, 1201
HEAD = [
    "NUM_SEQUENTIEL", "DATE_D", "DATE_S", "DATE_AR_SP", "DATE_F", "12h du jours", "NOM_DIREC_REG", "DESIG_DELEG",
    "DESIGNATION", "DESIGNATION_1", "DESIGNATION_2", "NOM_BRIGADE", "ADRESSE", "INTERV_OUI_NON", "REMARQUE",
]  # fmt: skip


def _row(
    seq: int, called: str, travel: int | None, delegation: str, nature: str, unit: str, yes: str = "نعم"
) -> list[Any]:
    """An outing: departure one minute after the call, arrival ``travel`` minutes after the departure."""
    d = datetime.fromisoformat(called)
    departed = d + timedelta(minutes=1)
    arrived = None if travel is None else departed + timedelta(minutes=travel)
    return [seq, d, departed, arrived, d, "M", "أريانة", delegation, nature, "", "", unit, "نهج سري", yes, "اسم خاص"]


def _xlsx(rows: list[list[Any]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(HEAD)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_class_and_period_rules() -> None:
    assert domain.snacr_class("medical", True) == "SAP" and domain.snacr_class("road", None) == "SR"
    assert domain.snacr_class("fire", True) == "LCI" and domain.snacr_class("rescue", True) == "DIV"
    assert domain.snacr_class("medical", False) == "SB"
    assert domain.intervened_of("لا") is False and domain.intervened_of("نعم") is True
    assert domain.intervened_of(None) is None
    at = lambda h, m: datetime(2041, 1, 1, h, m, tzinfo=domain.TUNIS)  # noqa: E731
    assert [domain.period_of(at(h, m)) for h, m in ((6, 0), (18, 0), (18, 1), (5, 59))] == ["J", "J", "S", "S"]
    assert domain.unit_key("أريانة المدينة") == domain.unit_key("اريانة المدينة")


def _cell(table: dict[str, Any], delegation: str, unit: str | None = None) -> dict[str, Any]:
    for block in table["gouvernorats"]:
        for u in block["units"]:
            if unit is not None and domain.unit_key(u["unit"]) != domain.unit_key(unit):
                continue
            for r in u["rows"]:
                if r["delegation"] == delegation:
                    return dict(r)
    raise AssertionError(f"{delegation} under {unit}")


async def test_study_tables_archive_and_exports(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    central = staff(["central_committee"], gouvernorat=None)
    await session.execute(text("DELETE FROM snacr.study WHERE gouvernorat_code = :g"), {"g": ARIANA})
    await session.execute(text("DELETE FROM snacr.dataset WHERE year IN (2041, 2042)"))
    await session.commit()

    # The national year first (one Nabeul row), then the regional file of two years merged into it.
    national = ("DATE_D,NOM_DIREC_REG,DESIG_DELEG,DESIGNATION\n2041-03-01 10:00:00,نابل,الحمامات,الإنقاذ\n").encode()
    r = await client.post(f"{URL}/datasets", params={"year": 2041, "file_name": "2041.csv"}, content=national,
                          headers=central)  # fmt: skip
    assert r.status_code == 201, r.text
    rows = [
        _row(1, "2041-02-01T10:00", 4, "سكرة", "الإسعاف في غير حوادث المرور", "سكرة"),
        _row(2, "2041-02-01T18:01", 6, "سكرة", "النجدة والإسعاف على الطرقات", "سكرة"),
        _row(3, "2041-02-02T18:00", 3, "سكرة", "الإسعاف في غير حوادث المرور", "سكرة", yes="لا"),
        _row(4, "2041-02-03T05:59", -1, "سكرة", "مجابهة الحرائق", "سكرة"),
        _row(5, "2041-02-03T06:00", 90, "سكرة", "مجابهة الحرائق", "سكرة"),
        _row(6, "2041-05-01T12:00", 10, "قلعة الأندلس", "الإنقاذ", "الغزالة"),
        _row(7, "2042-05-01T12:00", 8, "قلعة الأندلس", "الإنقاذ", "قلعة الأندلس"),
        _row(8, "2042-05-02T12:00", None, "قلعة الأندلس", "الإسعاف في غير حوادث المرور", "قلعة الأندلس"),
        _row(9, "2042-06-01T09:00", 5, "اريانة مدينة", "الإسعاف في غير حوادث المرور", "أريانة المدينة"),
        _row(10, "2042-06-01T21:00", 7, "اريانة مدينة", "الإسعاف في غير حوادث المرور", "اريانة المدينة"),
    ]
    r = await client.post(f"{URL}/datasets", params={"file_name": "ariana.xlsx", "merge": "true"},
                          content=_xlsx(rows), headers=central)  # fmt: skip
    assert r.status_code == 201, r.text
    assert sorted(d["year"] for d in r.json()["datasets"]) == [2041, 2042]
    stored = (
        await session.execute(
            text(
                "SELECT gouvernorat_code, seq_num, unit_raw, intervened FROM snacr.intervention "
                "WHERE year = 2041 ORDER BY seq_num NULLS FIRST"
            )
        )
    ).all()
    assert stored[0][0] == NABEUL  # the national row stayed
    assert [s[1] for s in stored[1:]] == [1, 2, 3, 4, 5, 6] and stored[3][3] is False and stored[1][2] == "سكرة"
    leaked = (
        await session.execute(text("SELECT count(*) FROM snacr.intervention WHERE delegation_raw LIKE '%سري%'"))
    ).scalar()
    assert leaked == 0

    # A study of Ariana, day and night.
    r = await client.post(f"{URL}/studies", json={"gouvernorat_code": ARIANA, "years": [2041, 2042]}, headers=central)
    assert r.status_code == 201, r.text
    first = r.json()
    assert first["status"] == "current" and first["split"] is True and first["travel_max"] == 60
    t = {tb["key"]: tb for tb in first["tables"]["tables"]}
    assert list(t) == ["SEC_GLOB", "SAP", "SR", "LCI", "SB", "DIV"]
    soukra = _cell(t["SEC_GLOB"], "سكرة")
    # 10:00 and 06:00 by day; 18:00 is still day (J), 18:01 and 05:59 night.
    assert soukra["counts"]["2041"] == {"J": 3, "S": 2} and soukra["counts"]["2042"] == {"J": 0, "S": 0}
    assert soukra["area_km2"] == 50.92 and soukra["population"] == 159862
    assert _cell(t["SB"], "سكرة")["counts"]["2041"] == {"J": 1, "S": 0}
    assert _cell(t["LCI"], "سكرة")["counts"]["2041"] == {"J": 1, "S": 1}
    # Travel: the negative one and the one over 60 minutes are left out of the mean, and counted.
    assert _cell(t["LCI"], "سكرة")["travel"] == {"J": None, "S": None}
    assert _cell(t["SAP"], "سكرة")["travel"]["J"] == 4
    assert first["quality"]["travel_negative"] == 1 and first["quality"]["travel_over"] == 1
    assert first["quality"]["white"] == 1 and first["quality"]["rows"] == 10
    # Kalaat El Andalous under El Ghazala in 2041, under its own unit in 2042 ("*" for the other year).
    early = _cell(t["SEC_GLOB"], "قلعة الأندلس", "الغزالة")
    late = _cell(t["SEC_GLOB"], "قلعة الأندلس", "قلعة الأندلس")
    assert early["counts"]["2042"] is None and early["mean"]["J"] == 1
    assert late["counts"]["2041"] is None and late["counts"]["2042"] == {"J": 2, "S": 0}
    # Two spellings of one unit make one unit.
    units = [u["unit"] for b in t["SEC_GLOB"]["gouvernorats"] for u in b["units"]]
    assert sum(1 for u in units if domain.unit_key(u) == domain.unit_key("أريانة المدينة")) == 1
    assert t["SEC_GLOB"]["total"]["total"] == 10
    # The statistical board and the technical notes, read from the study's own tables.
    f = first["findings"]
    classes = {c["key"]: c for c in f["classes"]}
    assert classes["SEC_GLOB"]["per_year"] == {"2041": 6, "2042": 4} and classes["SEC_GLOB"]["change_pct"] == -33.3
    assert classes["SB"]["share_pct"] == 10.0 and classes["SEC_GLOB"]["night_pct"] == 30.0
    kalaat = next(d for d in f["delegations"] if d["delegation"] == "قلعة الأندلس")
    assert kalaat["per_year"] == {"2041": 1, "2042": 2} and len(kalaat["units"]) == 2
    soukra_d = next(d for d in f["delegations"] if d["delegation"] == "سكرة")
    assert soukra_d["rate_per_1000"] == round(2.5 / 159862 * 1000, 2)
    texts = [n["text_ar"] for n in f["notes"]]
    assert texts[0].startswith("بلغ مجموع الخرجات 10 خلال الفترة 2041–2042")
    assert any("انخفض عدد الخرجات من 6 سنة 2041 إلى 4 سنة 2042" in x for x in texts)
    assert any(n["tone"] == "warn" and "الخرجات البيضاء" in n["text_ar"] for n in f["notes"])
    assert any("تغيرت الوحدة المغطية" in x and "قلعة الأندلس" in x for x in texts)

    # A second study, whole day: the first is archived as it was.
    r = await client.post(f"{URL}/studies", json={"gouvernorat_code": ARIANA, "years": [2042], "split": False},
                          headers=central)  # fmt: skip
    assert r.status_code == 201, r.text
    second = r.json()
    assert second["number"] == first["number"] + 1 and second["tables"]["periods"] == ["T"]
    listed = (await client.get(f"{URL}/studies", params={"gouvernorat": ARIANA}, headers=central)).json()
    assert [s["status"] for s in listed[:2]] == ["current", "archived"] and listed[1]["id"] == first["id"]
    again = (await client.get(f"{URL}/studies/{first['id']}", headers=central)).json()
    assert again["tables"] == first["tables"]

    # Exports, of the archived study too.
    pdf = await client.get(f"{URL}/studies/{first['id']}/export", headers=central)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    xlsx = await client.get(f"{URL}/studies/{first['id']}/export", params={"format": "xlsx"}, headers=central)
    assert xlsx.status_code == 200
    wb = load_workbook(io.BytesIO(xlsx.content))
    assert wb.sheetnames == ["ETUDE", "ANALYSE", "DEGATS", "SEC_GLOB", "SAP", "SR", "LCI", "SB", "DIV"]
    assert wb["SEC_GLOB"]["A1"].value == "Unité d’intervention" and wb["SEC_GLOB"]["F2"].value == 2041
    page = (await client.get(f"{URL}/studies/{first['id']}/export", params={"format": "html"}, headers=central)).text
    assert "مؤرشفة" in page and "سري" not in page and "اسم خاص" not in page
    assert "لوحة إحصائية وملاحظات تقنية" in page and "انخفض عدد الخرجات" in page
    assert wb["ANALYSE"]["A1"].value == "لوحة إحصائية وملاحظات تقنية"

    # Scope: another gouvernorat's committee sees nothing; Ariana's launches its own, never the national one.
    nabeul = staff(["local_committee"], gouvernorat=NABEUL)
    assert (await client.get(f"{URL}/studies/{first['id']}", headers=nabeul)).status_code == 404
    ariana = staff(["local_committee"], gouvernorat=ARIANA)
    assert (await client.get(f"{URL}/studies", headers=ariana)).json()[0]["id"] == second["id"]
    r = await client.post(f"{URL}/studies", json={"years": [2042]}, headers=ariana)
    assert r.status_code == 403
    assert (await client.post(f"{URL}/studies", json={"gouvernorat_code": ARIANA, "years": [1999]},
                              headers=ariana)).status_code == 422  # fmt: skip
    assert (await client.post(f"{URL}/studies", json={"gouvernorat_code": ARIANA, "years": [2042]},
                              headers=staff(["operator"], gouvernorat=ARIANA))).status_code == 403  # fmt: skip

    # The years of this test leave the archive (the other SNACR tests read the last years loaded).
    await session.execute(text("DELETE FROM snacr.study WHERE gouvernorat_code = :g"), {"g": ARIANA})
    await session.execute(text("DELETE FROM snacr.dataset WHERE year IN (2041, 2042)"))
    await session.commit()
