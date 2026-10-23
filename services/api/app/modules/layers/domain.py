"""Map data layers (phase B1, docs/phase-b/design.md §2): reading a file into checked rows, without the database.

One file = one layer, in CSV (``,`` or ``;``, UTF-8 or the Arabic Windows code page), Excel XLSX (first sheet),
JSON (an array of objects) or GeoJSON (a ``FeatureCollection`` of points). Column names are recognised in Arabic,
French or English; any other column is kept as extra information of the place. Each row becomes a :class:`Row` or
a :class:`Rejected` with a reason code (the dashboard translates the codes). Positions are checked against the
gouvernorat boundaries afterwards, in the database (``service.locate``).
"""

import csv
import hashlib
import io
import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Literal

from app.modules.telephony.domain import normalize_tn_number

Format = Literal["csv", "xlsx", "json", "geojson"]
FORMATS: tuple[Format, ...] = ("csv", "xlsx", "json", "geojson")

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_ROWS = 50_000
MAX_COLUMNS = 60
MAX_EXTRA_COLUMNS = 30
MAX_VALUE_LENGTH = 500
MAX_NAME_LENGTH = 200
MAX_REF_LENGTH = 100
# Rejected rows and warnings kept for the preview (counts are always complete).
MAX_REPORTED = 500

# Icons the dashboard and the app both draw (apps/dashboard/src/lib/layers.ts, apps/mobile/lib/features/places).
ICONS = (
    "hospital",
    "clinic",
    "pharmacy",
    "police",
    "guard",
    "civil_protection",
    "shelter",
    "school",
    "factory",
    "water",
    "fuel",
    "pin",
)
# Layer colours: white text and icons on each reach 4.5:1 (WCAG AA). Amber stays reserved for simulations.
PALETTE = (
    "#C62828",
    "#AD1457",
    "#6A1B9A",
    "#283593",
    "#1565C0",
    "#00695C",
    "#2E7D32",
    "#5D4037",
    "#37474F",
    "#BF360C",
)

# Standard columns (stored in their own field or under these keys of ``props``) and their accepted names.
STANDARD: tuple[str, ...] = (
    "id",
    "name",
    "type",
    "lat",
    "lon",
    "phone",
    "phone2",
    "address",
    "delegation",
    "manager",
    "hours",
    "email",
    "website",
    "hidden",
)
PROPS_KEYS = ("phone2", "address", "delegation", "manager", "hours", "email", "website")
# Written by the exports for reading, ignored on import (the gouvernorat is always computed from the position).
IGNORED = ("gouvernorat",)

ALIASES: dict[str, tuple[str, ...]] = {
    "id": ("id", "identifiant", "identifier", "code", "ref", "reference", "référence", "المعرف", "الرمز", "المرجع"),
    "name": ("name", "nom", "libellé", "désignation", "designation", "الاسم", "اسم", "التسمية"),
    "type": ("type", "category", "catégorie", "kind", "sous-type", "subtype", "النوع", "الصنف"),
    "lat": ("lat", "latitude", "y", "خط العرض", "العرض"),
    "lon": ("lon", "lng", "long", "longitude", "x", "خط الطول", "الطول"),
    "phone": ("phone", "téléphone", "tel", "tél", "telephone", "phone1", "الهاتف", "هاتف", "رقم الهاتف"),
    "phone2": ("phone2", "téléphone 2", "tel2", "tél 2", "fax", "الهاتف 2", "هاتف 2", "الفاكس"),
    "address": ("address", "adresse", "العنوان"),
    "delegation": ("delegation", "délégation", "المعتمدية"),
    "manager": ("manager", "responsable", "directeur", "director", "المسؤول", "المدير"),
    "hours": ("hours", "horaires", "opening hours", "opening_hours", "ساعات العمل", "التوقيت"),
    "email": ("email", "e-mail", "courriel", "mail", "البريد الإلكتروني", "البريد"),
    "website": ("website", "site web", "site", "url", "web", "الموقع الإلكتروني", "الموقع"),
    "hidden": ("hidden", "masqué", "masque", "مخفي"),
    "gouvernorat": ("gouvernorat", "governorate", "الولاية"),
}

# Column headings of the template and the exports, per language.
HEADINGS: dict[str, dict[str, str]] = {
    "ar": {
        "id": "المعرف",
        "name": "الاسم",
        "type": "النوع",
        "lat": "خط العرض",
        "lon": "خط الطول",
        "phone": "الهاتف",
        "phone2": "الهاتف 2",
        "address": "العنوان",
        "delegation": "المعتمدية",
        "manager": "المسؤول",
        "hours": "ساعات العمل",
        "email": "البريد الإلكتروني",
        "website": "الموقع الإلكتروني",
        "hidden": "مخفي",
        "gouvernorat": "الولاية",
    },
    "fr": {
        "id": "identifiant",
        "name": "nom",
        "type": "type",
        "lat": "latitude",
        "lon": "longitude",
        "phone": "téléphone",
        "phone2": "téléphone 2",
        "address": "adresse",
        "delegation": "délégation",
        "manager": "responsable",
        "hours": "horaires",
        "email": "e-mail",
        "website": "site web",
        "hidden": "masqué",
        "gouvernorat": "gouvernorat",
    },
    "en": {k: k for k in (*STANDARD, "gouvernorat")},
}

# Rough box around Tunisia, before the boundary check: catches swapped or garbage coordinates early.
LAT_RANGE = (30.0, 37.6)
LON_RANGE = (7.4, 11.7)

_SPACES = re.compile(r"[\s_\-]+")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DOMAIN = re.compile(r"^[a-z0-9.-]+\.[a-z]{2,}(/\S*)?$", re.IGNORECASE)
_SHORT_NUMBER = re.compile(r"^1\d{2}$")
_PHONE_SPLIT = re.compile(r"\s*[/;|,]\s*|\s+(?:ou|or|أو|و)\s+")
_TRUE = {"1", "true", "yes", "oui", "نعم", "x", "vrai"}


def normalize_heading(value: str) -> str:
    """Lower case, accents and Arabic diacritics removed, ``_``/``-``/spaces collapsed.

    "Téléphone_2" → "telephone 2"; the same normalisation is applied to the known names, so it only has to agree
    with itself."""
    decomposed = unicodedata.normalize("NFKD", value.strip().lower())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c)).replace("ـ", "")
    return _SPACES.sub(" ", stripped).strip()


_LOOKUP = {normalize_heading(alias): key for key, aliases in ALIASES.items() for alias in aliases}
_LOOKUP.update({normalize_heading(h): key for lang in HEADINGS.values() for key, h in lang.items()})


def column_key(heading: str) -> str | None:
    """The standard column a heading names, else None (an extra column)."""
    return _LOOKUP.get(normalize_heading(heading))


@dataclass(slots=True)
class Row:
    line: int
    ref: str
    name: str
    lat: float
    lon: float
    kind: str | None = None
    phone: str | None = None
    # None: the file has no "hidden" column, a place hidden by hand stays hidden.
    hidden: bool | None = None
    props: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "line": self.line,
            "ref": self.ref,
            "name": self.name,
            "lat": self.lat,
            "lon": self.lon,
            "kind": self.kind,
            "phone": self.phone,
            "hidden": self.hidden,
            "props": self.props,
        }


@dataclass(frozen=True, slots=True)
class Rejected:
    line: int
    reason: str
    name: str | None = None


@dataclass(frozen=True, slots=True)
class Warning:
    line: int
    column: str
    reason: str


@dataclass(slots=True)
class Parsed:
    format: Format
    rows: list[Row]
    rejected: list[Rejected]
    warnings: list[Warning]
    columns: list[str]


class FileError(ValueError):
    """The whole file is refused (code for the dashboard)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


# ---------------------------------------------------------------- reading the file


def detect_format(file_name: str, data: bytes) -> Format:
    name = file_name.lower()
    if name.endswith(".xlsx") or data[:2] == b"PK":
        return "xlsx"
    if name.endswith((".geojson", ".json")) or data.lstrip()[:1] in (b"[", b"{"):
        head = data[:4096].decode("utf-8", "ignore")
        return "geojson" if name.endswith(".geojson") or '"FeatureCollection"' in head else "json"
    if name.endswith((".csv", ".txt")) or name == "":
        return "csv"
    raise FileError("format_unknown")


def _decode(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        # Excel's "CSV" on an Arabic Windows saves in Windows-1256.
        return data.decode("cp1256", errors="replace")


def _records_csv(data: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    text = _decode(data)
    first = text.split("\n", 1)[0]
    delimiter = max((";", ",", "\t"), key=first.count)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        header = next(reader)
    except StopIteration:
        raise FileError("empty_file") from None
    records: list[dict[str, Any]] = []
    for values in reader:
        if not any(v.strip() for v in values):
            records.append({})
            continue
        records.append({h: v for h, v in zip(header, values, strict=False)})
    return header, records


def _records_xlsx(data: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    from openpyxl import load_workbook

    try:
        # Read-only, cached values: formulas are never evaluated, macros never loaded.
        book = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception:  # openpyxl raises many kinds on a damaged file
        raise FileError("xlsx_unreadable") from None
    try:
        sheet = book.worksheets[0]
        rows = sheet.iter_rows(values_only=True)
        header_row = next(rows, None)
        if header_row is None:
            raise FileError("empty_file")
        header = ["" if h is None else str(h) for h in header_row]
        records: list[dict[str, Any]] = []
        for values in rows:
            if len(records) > MAX_ROWS:
                break
            if values is None or all(v is None or str(v).strip() == "" for v in values):
                records.append({})
                continue
            records.append({h: v for h, v in zip(header, values, strict=False) if h})
        return header, records
    finally:
        book.close()


def _load_json(data: bytes) -> Any:
    try:
        return json.loads(_decode(data))
    except ValueError:
        raise FileError("json_invalid") from None


def _records_json(data: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    doc = _load_json(data)
    if not isinstance(doc, list):
        raise FileError("json_not_array")
    header: list[str] = []
    records: list[dict[str, Any]] = []
    for item in doc:
        record = item if isinstance(item, dict) else {}
        for k in record:
            if k not in header:
                header.append(str(k))
        records.append(record)
    return header, records


def _records_geojson(data: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    doc = _load_json(data)
    if not isinstance(doc, dict) or doc.get("type") != "FeatureCollection" or not isinstance(doc.get("features"), list):
        raise FileError("geojson_not_collection")
    header: list[str] = []
    records: list[dict[str, Any]] = []
    for feature in doc["features"]:
        props = dict(feature.get("properties") or {}) if isinstance(feature, dict) else {}
        geometry = feature.get("geometry") if isinstance(feature, dict) else None
        for k in props:
            if k not in header:
                header.append(str(k))
        # The geometry comes first, so it wins over "lat"/"lon" properties.
        record: dict[str, Any] = {}
        if isinstance(geometry, dict) and geometry.get("type") == "Point":
            coordinates = geometry.get("coordinates") or []
            if len(coordinates) >= 2:
                record["lon"], record["lat"] = coordinates[0], coordinates[1]
        else:
            record["\0geometry"] = "not_a_point"
        has_id = any(column_key(k) == "id" for k in props)
        if isinstance(feature, dict) and feature.get("id") is not None and not has_id:
            record["id"] = feature["id"]
        record.update({k: v for k, v in props.items() if k not in record})
        records.append(record)
    for k in ("id", "lat", "lon"):
        if k not in header:
            header.append(k)
    return header, records


_READERS = {"csv": _records_csv, "xlsx": _records_xlsx, "json": _records_json, "geojson": _records_geojson}


# ---------------------------------------------------------------- checking each row


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        # Excel stores phone numbers and identifiers typed as numbers as floats.
        return str(int(value))
    if isinstance(value, dict | list):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def _coordinate(value: Any) -> float | None:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    raw = _text(value).replace(" ", "")
    if raw.count(",") == 1 and "." not in raw:
        raw = raw.replace(",", ".")  # decimal comma
    try:
        return float(raw)
    except ValueError:
        return None


def _in(value: float, bounds: tuple[float, float]) -> bool:
    return bounds[0] <= value <= bounds[1]


def normalize_phone(raw: str) -> str | None:
    """A Tunisian number as ``+216XXXXXXXX``, or a 3-digit service number (190, 197…); None otherwise."""
    compact = re.sub(r"[\s().-]", "", raw)
    if _SHORT_NUMBER.match(compact):
        return compact
    return normalize_tn_number(compact)


def _website(raw: str) -> str | None:
    if raw.lower().startswith(("https://", "http://")):
        return raw if len(raw) <= MAX_VALUE_LENGTH and " " not in raw else None
    return f"https://{raw}" if _DOMAIN.match(raw) else None


def auto_ref(name: str, lat: float, lon: float) -> str:
    """Identifier of a row without one: same name and position (to about 1 m) → same place in the next file."""
    digest = hashlib.sha256(f"{normalize_heading(name)}|{lat:.5f}|{lon:.5f}".encode()).hexdigest()
    return f"auto-{digest[:16]}"


def check_row(line: int, record: dict[str, Any], keys: dict[str, str | None]) -> tuple[Row | Rejected, list[Warning]]:
    """One record (heading → value) into a checked row. ``keys`` maps each heading to its standard column."""
    warnings: list[Warning] = []
    values: dict[str, Any] = {}
    extra: dict[str, str] = {}
    for heading, value in record.items():
        if heading == "\0geometry":
            continue
        key = keys.get(heading)
        if key is None:
            text = _text(value)
            if text and len(extra) < MAX_EXTRA_COLUMNS:
                extra[heading.strip()[:64]] = text[:MAX_VALUE_LENGTH]
        elif key not in IGNORED and key not in values:
            values[key] = value
    name = _text(values.get("name"))[:MAX_NAME_LENGTH]
    if record.get("\0geometry"):
        return Rejected(line, "not_a_point", name or None), warnings
    if not name:
        return Rejected(line, "name_missing"), warnings
    lat, lon = _coordinate(values.get("lat")), _coordinate(values.get("lon"))
    if lat is None or lon is None:
        return Rejected(line, "coordinates_missing", name), warnings
    if not (_in(lat, LAT_RANGE) and _in(lon, LON_RANGE)):
        swapped = _in(lon, LAT_RANGE) and _in(lat, LON_RANGE)
        return Rejected(line, "coordinates_swapped" if swapped else "outside_tunisia", name), warnings

    props: dict[str, Any] = {}
    phones = [p for p in _PHONE_SPLIT.split(_text(values.get("phone"))) if p]
    phones += [p for p in _PHONE_SPLIT.split(_text(values.get("phone2"))) if p]
    normalized = []
    for raw in phones:
        number = normalize_phone(raw)
        if number is None:
            warnings.append(Warning(line, "phone", "phone_invalid"))
        elif number not in normalized:
            normalized.append(number)
    if len(normalized) > 1:
        props["phone2"] = normalized[1]
    for key in ("address", "delegation", "manager", "hours"):
        text = _text(values.get(key))[:MAX_VALUE_LENGTH]
        if text:
            props[key] = text
    email = _text(values.get("email"))
    if email:
        if _EMAIL.match(email) and len(email) <= 200:
            props["email"] = email
        else:
            warnings.append(Warning(line, "email", "email_invalid"))
    website = _text(values.get("website"))
    if website:
        url = _website(website)
        if url:
            props["website"] = url
        else:
            warnings.append(Warning(line, "website", "website_invalid"))
    props.update({k: v for k, v in extra.items() if k not in props})

    ref = _text(values.get("id"))[:MAX_REF_LENGTH] or auto_ref(name, lat, lon)
    kind = _text(values.get("type"))[:64] or None
    hidden = _text(values.get("hidden")).lower() in _TRUE if "hidden" in values else None
    row = Row(line, ref, name, round(lat, 7), round(lon, 7), kind, normalized[0] if normalized else None, hidden, props)
    return row, warnings


def parse(file_name: str, data: bytes) -> Parsed:
    """Read and check a whole file. Raises :class:`FileError` when the file itself is refused."""
    if len(data) > MAX_FILE_BYTES:
        raise FileError("file_too_large")
    if not data.strip():
        raise FileError("empty_file")
    fmt = detect_format(file_name, data)
    header, records = _READERS[fmt](data)
    if len(header) > MAX_COLUMNS:
        raise FileError("too_many_columns")
    if len(records) > MAX_ROWS:
        raise FileError("too_many_rows")
    keys = {h: column_key(h) for h in header}
    keys.update({"lat": "lat", "lon": "lon", "id": "id"} if fmt == "geojson" else {})
    found = set(keys.values())
    if "name" not in found or ("lat" not in found and fmt != "geojson") or ("lon" not in found and fmt != "geojson"):
        raise FileError("required_columns_missing")

    rows: list[Row] = []
    rejected: list[Rejected] = []
    warnings: list[Warning] = []
    seen: set[str] = set()
    # Line numbers as the user sees them: the heading is line 1 of a spreadsheet; JSON items count from 1.
    offset = 2 if fmt in ("csv", "xlsx") else 1
    for index, record in enumerate(records):
        if not record:
            continue
        line = index + offset
        result, row_warnings = check_row(line, record, keys)
        warnings += row_warnings
        if isinstance(result, Rejected):
            rejected.append(result)
        elif result.ref in seen:
            rejected.append(Rejected(line, "duplicate_id", result.name))
        else:
            seen.add(result.ref)
            rows.append(result)
    return Parsed(fmt, rows, rejected, warnings, [h for h in header if h])


# ---------------------------------------------------------------- export


def neutralize(value: str) -> str:
    """Spreadsheet formula injection (OWASP): a text cell starting with = + - @ is written with a leading quote."""
    return f"'{value}" if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value
