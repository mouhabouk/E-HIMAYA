"""The Office's damage tables (Yamen, 2026-11-01), tied to the archive of interventions by NUM_SEQUENTIEL.

* ``degat_forestieres`` (DGF_*): the place burnt (dry grass, Aleppo pine forest, broadleaf forest, waste land) and its
  surface in hectares;
* ``degat_Agriculteur`` (DGA_*): the place (fodder, farm, estate, farming area), the crop or fodder lost (wheat, barley,
  other crops, stubble, hay, straw), its unit (hectare, bale, bag) and the quantity.

The files are read whole (semicolon CSV with a BOM, or an xlsx sheet with the same headings), the decimal comma is
accepted, a label without its code takes the code of the reference list, and each import replaces the lines of its
kind. Nothing else of the file is kept."""

import csv
import io
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Literal

from app.modules.snacr import domain

Kind = Literal["forest", "agri"]
MAX_ROWS = 200_000
UNIT_OF_CODE = {"1": "ha", "2": "bag", "3": "bale"}
UNIT_OF_LABEL = {"هكتار": "ha", "اكياس": "bag", "حزم(بالات)": "bale", "حزم (بالات)": "bale", "بالات": "bale"}
UNIT_AR = {"ha": "هكتار", "bag": "كيس", "bale": "بالة"}
PREFIX: dict[Kind, str] = {"forest": "DGF_", "agri": "DGA_"}


@dataclass(slots=True)
class Line:
    kind: Kind
    source_key: int | None
    seq_num: int
    place_code: str | None
    place_label: str | None
    crop_code: str | None
    crop_label: str | None
    unit: str
    value: float


@dataclass(slots=True)
class Report:
    kind: Kind
    read: int = 0
    kept: int = 0
    rejected: dict[str, int] = field(default_factory=dict)

    def reject(self, why: str) -> None:
        self.rejected[why] = self.rejected.get(why, 0) + 1


def _rows(file_name: str, data: bytes) -> Iterator[list[Any]]:
    if len(data) > domain.MAX_BYTES:
        raise domain.FileError("file_too_large")
    if domain.detect_format(file_name, data) == "xlsx":
        from openpyxl import load_workbook

        try:
            workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        except (zipfile.BadZipFile, KeyError, ValueError, OSError) as exc:
            raise domain.FileError("file_unreadable") from exc
        try:
            yield from (list(r) for r in workbook[workbook.sheetnames[0]].iter_rows(values_only=True))
        finally:
            workbook.close()
        return
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise domain.FileError("file_unreadable") from exc
    first = text.split("\n", 1)[0]
    yield from csv.reader(io.StringIO(text), delimiter=";" if first.count(";") >= first.count(",") else ",")


def _text(value: Any) -> str | None:
    s = str(value).strip() if value is not None else ""
    return s if s and s != "0" else None


def _code(value: Any) -> str | None:
    s = _text(value)
    if s is None:
        return None
    try:
        return str(int(float(s.replace(",", "."))))
    except ValueError:
        return None


def _number(value: Any) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    s = _text(value)
    if s is None:
        return 0.0 if str(value).strip() == "0" else None
    try:
        return float(s.replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def read(file_name: str, data: bytes, crops: dict[str, tuple[str, str | None]]) -> tuple[Report, list[Line]]:
    """The lines of a damage file; ``crops`` is the reference list of crops, normalized label → (code, unit)."""
    rows = _rows(file_name, data)
    head = [str(h or "").strip().upper() for h in next(rows, [])]
    kind: Kind
    if any(h.startswith("DGF_") for h in head):
        kind = "forest"
    elif any(h.startswith("DGA_") for h in head):
        kind = "agri"
    else:
        raise domain.FileError("damage_file_unknown")
    p = PREFIX[kind]
    col = {h: i for i, h in enumerate(head)}
    if f"{p}CO_NUM_SEQUENTIEL" not in col:
        raise domain.FileError("damage_file_unknown")

    def get(row: list[Any], name: str) -> Any:
        i = col.get(name)
        return row[i] if i is not None and i < len(row) else None

    report, lines = Report(kind), []
    for row in rows:
        if not any(v not in (None, "") for v in row):
            continue
        report.read += 1
        if report.read > MAX_ROWS:
            raise domain.FileError("file_too_many_rows")
        seq = _code(get(row, f"{p}CO_NUM_SEQUENTIEL"))
        if seq is None:
            report.reject("no_number")
            continue
        place_code, place_label = _code(get(row, f"{p}TYPE_LIEU")), _text(get(row, f"{p}LIBE_LIEU"))
        crop_code = crop_label = None
        if kind == "forest":
            unit, value = "ha", _number(get(row, "SURFACE"))
        else:
            crop_code, crop_label = _code(get(row, "DGA_CODE_DEGAT")), _text(get(row, "DGA_LIBE_DEGAT"))
            known = crops.get(domain.normalize(crop_label or ""))
            if crop_code is None and known is not None:
                crop_code = known[0]
            unit_code, unit_label = _code(get(row, "DGA_CODE_UNITE")), _text(get(row, "DGA_LIBE_UNITE"))
            unit = UNIT_OF_CODE.get(unit_code or "") or UNIT_OF_LABEL.get(domain.normalize(unit_label or "")) or ""
            if not unit and known is not None and known[1]:
                unit = known[1]
            value = _number(get(row, "DGA_VALEUR"))
        if not unit:
            report.reject("no_unit")
            continue
        if value is None or value < 0:
            report.reject("bad_value")
            continue
        lines.append(
            Line(kind, int(_code(get(row, f"{p}CLE")) or 0) or None, int(seq), place_code, place_label, crop_code,
                 crop_label, unit, value)
        )  # fmt: skip
        report.kept += 1
    return report, lines
