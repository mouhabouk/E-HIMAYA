"""SNACR rules (docs/phase-s/design-s.md): reading the Office's archive, cleaning it, and grading délégations.

The archive comes as the Office exports it today (one sheet a year, columns ``DATE_D`` … ``DESC_FINALE``). Only the
times, the place and the nature are kept; the address, the free texts, the crew and the vehicles are never read, so no
name, telephone or identity number can reach the database.
"""

import csv
import io
import re
import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

TUNIS = ZoneInfo("Africa/Tunis")
MAX_BYTES = 120 * 1024 * 1024
MAX_ROWS = 400_000
# A recorded arrival later than this after the call is kept but not counted in the arrival indicators.
ARRIVAL_CEILING_MIN = 180.0

Family = Literal["medical", "road", "fire", "rescue"]
FAMILIES: tuple[Family, ...] = ("medical", "road", "fire", "rescue")
Zone = Literal["urban", "periurban", "rural"]
ZONES: tuple[Zone, ...] = ("urban", "periurban", "rural")
Hazard = Literal[
    "flood", "forest_fire", "industrial", "hazmat_transport", "coastal", "earthquake", "storm", "drought", "epidemic"
]
HAZARDS: tuple[Hazard, ...] = (
    "flood",
    "forest_fire",
    "industrial",
    "hazmat_transport",
    "coastal",
    "earthquake",
    "storm",
    "drought",
    "epidemic",
)
FLAGS = (
    "arrival_missing",
    "arrival_negative",
    "arrival_outlier",
    "delegation_unmatched",
    "delegation_reassigned",
)

# The columns read, under the names the Office's export gives them; every other column is ignored.
COLUMNS = {
    "called": "DATE_D",
    "departed": "DATE_S",
    "arrived": "DATE_AR_SP",
    "ended": "DATE_F",
    "gouvernorat": "NOM_DIREC_REG",
    "delegation": "DESIG_DELEG",
    "nature": "DESIGNATION",
    "subtype": "DESIGNATION_1",
}
REQUIRED = ("called", "gouvernorat", "delegation", "nature")


class FileError(Exception):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------- names

_DIACRITICS = re.compile("[ً-ْـ]")
_SPACES = re.compile(r"[\s\-_.،,/]+")


def normalize(name: str) -> str:
    """The comparable form of an Arabic place name: no diacritics, one alif, ة→ه, ى→ي, ئ→ي, single spaces."""
    s = _DIACRITICS.sub("", str(name or ""))
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ة", "ه"), ("ى", "ي"), ("ئ", "ي"), ("ؤ", "و")):
        s = s.replace(a, b)
    s = _SPACES.sub(" ", s).strip()
    return re.sub(r"^معتمديه ", "", s)


def compact(name: str) -> str:
    """A looser form for the second try: no spaces and no article, so "غارالدماء" meets "غار الدماء"."""
    return normalize(name).replace(" ", "").replace("ال", "")


# ---------------------------------------------------------------- natures and subtypes

# The natures (DESIGNATION) of the 2022 archive and their family.
NATURES: dict[str, Family] = {
    "الإسعاف في غير حوادث المرور": "medical",
    "مرض فجئي": "medical",
    "سقوط فجئي": "medical",
    "اعتداء": "medical",
    "تسمم": "medical",
    "النجدة والإسعاف على الطرقات": "road",
    "حوادث وسائل النقل": "road",
    "مجابهة الحرائق": "fire",
    "حريق": "fire",
    "الإنقاذ": "rescue",
    "مختلفة": "rescue",
}
_NATURES = {normalize(k): v for k, v in NATURES.items()}
_KEYWORDS: tuple[tuple[str, Family], ...] = (
    ("في غير حوادث", "medical"),
    ("طرقات", "road"),
    ("وسايل النقل", "road"),
    ("حري", "fire"),
    ("حرايق", "fire"),
    ("انقاذ", "rescue"),
    ("غرق", "rescue"),
    ("فيضان", "rescue"),
    ("اسعاف", "medical"),
    ("مرض", "medical"),
    ("سقوط", "medical"),
    ("تسمم", "medical"),
)
# Spelling variants of the subtypes (DESIGNATION_1) seen in the archive.
SUBTYPE_FIXES = {
    "محتلفة": "مختلفة",
    "غرقا": "غرق",
    "السقوط من علو": "سقوط من علو",
    "محروقات": "بمحروقات",
    "ببناية": "بالبنايات",
}


def family_of(nature: str) -> Family | None:
    n = normalize(nature)
    if n in _NATURES:
        return _NATURES[n]
    for key, fam in _KEYWORDS:
        if key in n:
            return fam
    return None


def clean_subtype(raw: Any) -> str | None:
    s = _SPACES.sub(" ", str(raw or "")).strip()
    if not s or s.lower() in ("none", "nan"):
        return None
    return SUBTYPE_FIXES.get(s, s)


# ---------------------------------------------------------------- reading the file

_DATE_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d-%m-%Y %H:%M", "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S")


def moment(value: Any) -> datetime | None:
    """A time of the archive (local time in Tunis) as an aware datetime, or None when absent or unreadable."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        naive = value
    else:
        text = str(value).strip()
        if not text:
            return None
        for fmt in _DATE_FORMATS:
            try:
                naive = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        else:
            return None
    return naive if naive.tzinfo is not None else naive.replace(tzinfo=TUNIS)


def detect_format(file_name: str, data: bytes) -> Literal["xlsx", "csv"]:
    if data[:2] == b"PK" or file_name.lower().endswith(".xlsx"):
        return "xlsx"
    return "csv"


def _heading_map(headings: list[str]) -> dict[str, int]:
    index = {str(h or "").strip().upper(): i for i, h in enumerate(headings)}
    out = {}
    for key, column in COLUMNS.items():
        if column in index:
            out[key] = index[column]
    missing = [COLUMNS[k] for k in REQUIRED if k not in out]
    if missing:
        raise FileError("file_columns_missing", ", ".join(missing))
    return out


def _records(rows: Iterator[tuple[Any, ...] | list[Any]]) -> Iterator[dict[str, Any]]:
    try:
        headings = [str(h or "") for h in next(rows)]
    except StopIteration:
        return
    where = _heading_map(headings)
    for values in rows:
        if values is None or all(v in (None, "") for v in values):
            continue
        yield {key: (values[i] if i < len(values) else None) for key, i in where.items()}


def read(file_name: str, data: bytes) -> Iterator[dict[str, Any]]:
    """The rows of the archive file (the first sheet of an xlsx, or a CSV with the same headings)."""
    if len(data) > MAX_BYTES:
        raise FileError("file_too_large")
    if detect_format(file_name, data) == "xlsx":
        from openpyxl import load_workbook

        try:
            workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        except (zipfile.BadZipFile, KeyError, ValueError, OSError) as exc:
            raise FileError("file_unreadable") from exc
        try:
            sheet = workbook[workbook.sheetnames[0]]
            yield from _records(sheet.iter_rows(values_only=True))
        finally:
            workbook.close()
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise FileError("file_unreadable") from exc
        yield from _records(iter(csv.reader(io.StringIO(text))))


# ---------------------------------------------------------------- cleaning


@dataclass(slots=True)
class Places:
    """The reference délégations and the alternative names, by gouvernorat."""

    gouvernorats: dict[str, int]
    exact: dict[int, dict[str, int]]
    loose: dict[int, dict[str, int]]
    aliases: dict[int, dict[str, int]]
    national: dict[str, list[tuple[int, int]]] = field(default_factory=dict)

    def gouvernorat(self, raw: Any) -> int | None:
        return self.gouvernorats.get(normalize(raw))

    def delegation(self, gouvernorat: int, raw: Any) -> tuple[int | None, str | None]:
        """The délégation id and, when found elsewhere than in its gouvernorat, the flag saying so."""
        n = normalize(raw)
        for table in (self.aliases, self.exact):
            hit = table.get(gouvernorat, {}).get(n)
            if hit is not None:
                return hit, None
        hit = self.loose.get(gouvernorat, {}).get(compact(raw))
        if hit is not None:
            return hit, None
        elsewhere = self.national.get(n, [])
        if len(elsewhere) == 1:
            return elsewhere[0][1], "delegation_reassigned"
        return None, "delegation_unmatched"


def places_from(
    gouvernorats: Iterable[tuple[int, str]],
    delegations: Iterable[tuple[int, int, str]],
    aliases: Iterable[tuple[int, str, int]],
) -> Places:
    """``gouvernorats``: (code, name_ar); ``delegations``: (gouvernorat, id, name_ar); ``aliases``: (gouvernorat,
    raw, délégation)."""
    out = Places({normalize(n): c for c, n in gouvernorats}, {}, {}, {})
    for g, d, name in delegations:
        out.exact.setdefault(g, {})[normalize(name)] = d
        out.loose.setdefault(g, {})[compact(name)] = d
        out.national.setdefault(normalize(name), []).append((g, d))
    for g, raw, d in aliases:
        out.aliases.setdefault(g, {})[normalize(raw)] = d
    return out


@dataclass(slots=True)
class Row:
    family: Family
    nature: str
    subtype: str | None
    gouvernorat_code: int
    delegation_id: int | None
    delegation_raw: str
    called_at: datetime
    departed_at: datetime | None
    arrived_at: datetime | None
    ended_at: datetime | None
    arrival_min: float | None
    flags: list[str]


@dataclass(slots=True)
class Quality:
    """What the cleaning found, kept with the dataset and shown to the committee (data completeness report)."""

    read: int = 0
    kept: int = 0
    skipped: dict[str, int] = field(default_factory=dict)
    flags: dict[str, int] = field(default_factory=dict)
    by_gouvernorat: dict[int, dict[str, int]] = field(default_factory=dict)
    unmatched: dict[tuple[int, str], int] = field(default_factory=dict)
    years: dict[int, int] = field(default_factory=dict)

    def skip(self, why: str) -> None:
        self.skipped[why] = self.skipped.get(why, 0) + 1

    def out(self) -> dict[str, Any]:
        return {
            "read": self.read,
            "kept": self.kept,
            "skipped": self.skipped,
            "flags": self.flags,
            "by_gouvernorat": {
                str(g): {**v, "arrival_complete_pct": round(100 * v["arrival_ok"] / v["rows"], 1) if v["rows"] else 0}
                for g, v in sorted(self.by_gouvernorat.items())
            },
            "unmatched": [
                {"gouvernorat_code": g, "raw": raw, "rows": n}
                for (g, raw), n in sorted(self.unmatched.items(), key=lambda kv: -kv[1])
            ],
        }


def clean(record: dict[str, Any], places: Places, quality: Quality) -> Row | None:
    quality.read += 1
    called = moment(record.get("called"))
    if called is None:
        quality.skip("called_missing")
        return None
    nature = _SPACES.sub(" ", str(record.get("nature") or "")).strip()
    family = family_of(nature)
    if family is None:
        quality.skip("nature_unknown")
        return None
    gouvernorat = places.gouvernorat(record.get("gouvernorat"))
    if gouvernorat is None:
        quality.skip("gouvernorat_unknown")
        return None
    raw = _SPACES.sub(" ", str(record.get("delegation") or "")).strip()
    flags: list[str] = []
    delegation, flag = places.delegation(gouvernorat, raw)
    if flag:
        flags.append(flag)
        if flag == "delegation_unmatched":
            key = (gouvernorat, raw)
            quality.unmatched[key] = quality.unmatched.get(key, 0) + 1
    departed, arrived, ended = (moment(record.get(k)) for k in ("departed", "arrived", "ended"))
    arrival: float | None = None
    if arrived is None:
        flags.append("arrival_missing")
    else:
        arrival = (arrived - called).total_seconds() / 60
        if arrival < 0:
            flags.append("arrival_negative")
        elif arrival > ARRIVAL_CEILING_MIN:
            flags.append("arrival_outlier")
    for f in flags:
        quality.flags[f] = quality.flags.get(f, 0) + 1
    g = quality.by_gouvernorat.setdefault(gouvernorat, {"rows": 0, "arrival_ok": 0, "unmatched": 0})
    g["rows"] += 1
    g["arrival_ok"] += int(arrival is not None and 0 <= arrival <= ARRIVAL_CEILING_MIN)
    g["unmatched"] += int("delegation_unmatched" in flags)
    quality.years[called.year] = quality.years.get(called.year, 0) + 1
    quality.kept += 1
    return Row(
        family=family,
        nature=nature,
        subtype=clean_subtype(record.get("subtype")),
        gouvernorat_code=gouvernorat,
        delegation_id=delegation,
        delegation_raw=raw,
        called_at=called,
        departed_at=departed,
        arrived_at=arrived,
        ended_at=ended,
        arrival_min=round(arrival, 2) if arrival is not None else None,
        flags=flags,
    )


# ---------------------------------------------------------------- grading


def zone_of(population: int | None, area_km2: float | None, urban: int, periurban: int) -> Zone:
    """Urban, periurban or rural from the 2024 density; a délégation without census counts as rural."""
    if not population or not area_km2 or area_km2 <= 0:
        return "rural"
    density = population / area_km2
    if density >= urban:
        return "urban"
    return "periurban" if density >= periurban else "rural"


def quintile_breaks(values: list[float]) -> list[float]:
    """The four values that cut ``values`` into five groups of equal size."""
    if not values:
        return []
    ordered = sorted(values)
    return [ordered[min(len(ordered) - 1, int(len(ordered) * q / 5))] for q in (1, 2, 3, 4)]


def frequency_level(rate: float | None, breaks: list[float]) -> int | None:
    """1 (rarest fifth of the country) to 5 (most frequent fifth)."""
    if rate is None or not breaks:
        return None
    return 1 + sum(rate >= b for b in breaks)


def coverage_level(compliance: float | None, goal: float) -> int | None:
    """1 (the goal is met) to 5 (40 points or more below it); None without a recorded arrival."""
    if compliance is None:
        return None
    gap = goal - compliance
    if gap <= 0:
        return 1
    if gap <= 10:
        return 2
    if gap <= 25:
        return 3
    return 4 if gap <= 40 else 5


Priority = Literal["high", "medium", "low"]


def priority_of(frequency: int | None, coverage: int | None) -> Priority | None:
    """Everyday risk: how often (1-5) times how badly covered (1-5)."""
    if frequency is None or coverage is None:
        return None
    score = frequency * coverage
    if score >= 15:
        return "high"
    return "medium" if score >= 8 else "low"


def special_level(probability: int, gravity: int) -> Priority:
    score = probability * gravity
    if score >= 15:
        return "high"
    return "medium" if score >= 8 else "low"


# ---------------------------------------------------------------- method and references

# Where each concept and indicator comes from (docs/phase-s/design-s.md §2); the plan prints this list.
REFERENCES: tuple[dict[str, str], ...] = (
    {
        "code": "TN-91-39",
        "title": "Loi n° 91-39 du 8 juin 1991 relative à la lutte contre les calamités, à leur prévention et à "
        "l'organisation des secours",
        "use": "legal_basis",
    },
    {
        "code": "TN-93-942",
        "title": "Décret n° 93-942 du 26 avril 1993 (modifié par le décret n° 2004-2723): plan national et plans "
        "régionaux, commission nationale présidée par le ministre de l'Intérieur, commissions régionales présidées "
        "par le gouverneur, réunies au moins une fois par an",
        "use": "committees_and_review",
        "url": "https://onpc.nat.tn/pdfs/20251216145353_221_Dcret_n93-942-.pdf",
    },
    {
        "code": "TN-93-121",
        "title": "Loi n° 93-121 du 27 décembre 1993 portant création de l'Office national de la protection civile",
        "use": "legal_basis",
        "url": "https://legislation-securite.tn/wp-content/uploads/sites/5/2023/11/Loi-n°-93-121-du-27-Decembre-1993-Fr-1.pdf",
    },
    {
        "code": "TN-SNRRC-2030",
        "title": "Stratégie nationale de réduction des risques de catastrophe à l'horizon 2030 et plan d'action (2021)",
        "use": "special_risks",
        "url": "https://www.environnement.gov.tn/fileadmin/Bibliotheque/Environnement_en_Tunisie/strategie_nationale_de_reduction_Finalise.pdf",
    },
    {
        "code": "FR-SDACR",
        "title": "Schéma départemental d'analyse et de couverture des risques (CGCT art. L1424-7) et son guide "
        "méthodologique actualisé (2020): risques courants et risques complexes, objectifs de couverture, révision "
        "au moins tous les cinq ans",
        "use": "structure_everyday_special_coverage",
        "url": "https://www.banquedesterritoires.fr/services-dincendie-et-de-secours-des-sdacr-nouvelle-formule",
    },
    {
        "code": "UK-NFCC-CRMP",
        "title": "NFCC Community Risk Management Planning Strategic Framework: périmètre, identification des "
        "dangers, analyse des risques, décision, évaluation",
        "use": "plan_cycle",
        "url": "https://nfcc.org.uk/our-services/community-risk-programme/community-risk-management-planning-strategic-framework/",
    },
    {
        "code": "US-NFPA-1710",
        "title": "NFPA 1710: objectifs de délai mesurés au 90e centile (traitement de l'appel, départ, trajet)",
        "use": "percentile_indicators",
        "url": "https://emergent.tech/blog/nfpa-1710-response-times",
    },
    {
        "code": "UN-SENDAI",
        "title": "Cadre de Sendai pour la réduction des risques de catastrophe 2015-2030, cibles A à G et indicateurs",
        "use": "special_risks",
        "url": "https://www.preventionweb.net/sendai-framework/sendai-framework-indicators",
    },
    {
        "code": "ISO-31000",
        "title": "ISO 31000:2018, management du risque: le niveau d'un risque combine sa vraisemblance et ses "
        "conséquences",
        "use": "matrix",
    },
)
