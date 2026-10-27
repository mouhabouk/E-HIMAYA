"""Approximate, invented map places for trials ([SIM], phase B1, Yamen 2026-10-23).

┏━━ SIMULATION ━━ approximate places while the Office's lists and the OpenStreetMap load are missing
┃ Every place is invented: one regional hospital, one basic health centre, two pharmacies, one police station and one
┃ National Guard post near the centre of each of the 24 gouvernorats, a few hundred metres apart. Names start with
┃ "[SIM]" in Arabic, French and English, and no place has a phone number (a citizen must never dial an invented
┃ number: the app offers 198). Import each file in a layer created with "simulated" and "to be verified" ticked.
┃ PRODUCTION: the Office's official lists (or scripts/osm_layers.py) replace these files with the *replace* mode,
┃ and the "simulated" mark is then removed from the layer.
┗━━━━━━━━━━━━━━━━

Usage (from the repository root)::

    python3 scripts/sim_layers.py --out build/sim     # one sim-<layer>.geojson per layer and layers.json

Standard library only; the output is the same at every run (no randomness).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SOURCE = "[SIM] Données approximatives d'essai / بيانات تقريبية للتجربة / approximate trial data"

# code, Arabic, French, English, approximate centre of the gouvernorat's main town (lat, lon), and the direction
# the places are spread in (lat, lon steps in degrees) so that coastal towns stay on land.
GOUVERNORATS: list[tuple[int, str, str, str, float, float, float, float]] = [
    (11, "تونس", "Tunis", "Tunis", 36.8065, 10.1815, 0.0, -0.004),
    (12, "أريانة", "Ariana", "Ariana", 36.8625, 10.1956, 0.002, -0.003),
    (13, "بن عروس", "Ben Arous", "Ben Arous", 36.7531, 10.2189, -0.003, -0.002),
    (14, "منوبة", "Manouba", "Manouba", 36.8101, 10.0863, 0.0, -0.004),
    (21, "نابل", "Nabeul", "Nabeul", 36.4561, 10.7376, 0.003, -0.004),
    (22, "زغوان", "Zaghouan", "Zaghouan", 36.4029, 10.1429, 0.003, -0.003),
    (23, "بنزرت", "Bizerte", "Bizerte", 37.2744, 9.8739, 0.0, -0.004),
    (31, "باجة", "Béja", "Beja", 36.7256, 9.1817, 0.0, -0.004),
    (32, "جندوبة", "Jendouba", "Jendouba", 36.5011, 8.7802, 0.0, 0.004),
    (33, "الكاف", "Le Kef", "Kef", 36.1742, 8.7049, -0.003, 0.003),
    (34, "سليانة", "Siliana", "Siliana", 36.0849, 9.3708, 0.0, 0.004),
    (41, "القيروان", "Kairouan", "Kairouan", 35.6781, 10.0963, 0.0, -0.004),
    (42, "القصرين", "Kasserine", "Kasserine", 35.1676, 8.8365, 0.0, 0.004),
    (43, "سيدي بوزيد", "Sidi Bouzid", "Sidi Bouzid", 35.0382, 9.4849, 0.0, 0.004),
    (51, "سوسة", "Sousse", "Sousse", 35.8256, 10.6084, -0.002, -0.004),
    (52, "المنستير", "Monastir", "Monastir", 35.7643, 10.8113, -0.003, -0.003),
    (53, "المهدية", "Mahdia", "Mahdia", 35.5047, 11.0622, -0.002, -0.004),
    (61, "صفاقس", "Sfax", "Sfax", 34.7406, 10.7603, 0.003, -0.004),
    (71, "قفصة", "Gafsa", "Gafsa", 34.4250, 8.7842, 0.0, 0.004),
    (72, "توزر", "Tozeur", "Tozeur", 33.9197, 8.1335, 0.0, 0.004),
    (73, "قبلي", "Kébili", "Kebili", 33.7044, 8.9690, 0.0, 0.004),
    (81, "قابس", "Gabès", "Gabes", 33.8815, 10.0982, -0.002, -0.004),
    (82, "مدنين", "Médenine", "Medenine", 33.3549, 10.5055, 0.0, -0.004),
    (83, "تطاوين", "Tataouine", "Tataouine", 32.9297, 10.4518, 0.0, -0.004),
]

# layer key → names, icon, colour, places: (id suffix, type, hours, name ar / fr / en; {ar} {fr} {en}: the town)
LAYERS: dict[str, dict[str, Any]] = {
    "hospitals": {
        "names": {"ar": "المستشفيات وأقسام الاستعجالي", "fr": "Hôpitaux et urgences", "en": "Hospitals and A&E"},
        "icon": "hospital",
        "colour": "#C62828",
        "places": [
            ("h", "emergency", "24/7", "المستشفى الجهوي بـ{ar}", "Hôpital régional de {fr}", "{en} Regional Hospital"),
        ],
    },
    "clinics": {
        "names": {"ar": "مراكز الصحة الأساسية", "fr": "Centres de santé de base", "en": "Primary health centres"},
        "icon": "clinic",
        "colour": "#AD1457",
        "places": [
            (
                "c",
                None,
                "08:00-17:00",
                "مركز الصحة الأساسية بـ{ar}",
                "Centre de santé de base de {fr}",
                "{en} Primary Health Centre",
            ),
        ],
    },
    "pharmacies": {
        "names": {"ar": "الصيدليات", "fr": "Pharmacies", "en": "Pharmacies"},
        "icon": "pharmacy",
        "colour": "#2E7D32",
        "places": [
            ("p1", "night", "24/7", "صيدلية الليل بـ{ar}", "Pharmacie de nuit de {fr}", "{en} Night Pharmacy"),
            ("p2", None, "08:00-20:00", "صيدلية وسط {ar}", "Pharmacie du centre de {fr}", "{en} Central Pharmacy"),
        ],
    },
    "police": {
        "names": {"ar": "مراكز الأمن", "fr": "Postes de police", "en": "Police stations"},
        "icon": "police",
        "colour": "#283593",
        "places": [("s", None, "24/7", "مركز الأمن بـ{ar}", "Poste de police de {fr}", "{en} Police Station")],
    },
    "national_guard": {
        "names": {"ar": "مراكز الحرس الوطني", "fr": "Postes de la Garde nationale", "en": "National Guard posts"},
        "icon": "guard",
        "colour": "#37474F",
        "places": [
            (
                "g",
                None,
                "24/7",
                "مركز الحرس الوطني بـ{ar}",
                "Poste de la Garde nationale de {fr}",
                "{en} National Guard Post",
            ),
        ],
    },
}

SIM = "[SIM] "
NOTE = {
    "ar": "مكان وهمي تقريبي للتجربة، ليس مكانا حقيقيا",
    "fr": "Lieu fictif approximatif d'essai, pas un lieu réel",
    "en": "Approximate invented place for trials, not a real place",
}


def _order() -> list[tuple[str, tuple[Any, ...]]]:
    """Every place of every layer, in the order they are spread from the town centre."""
    return [(layer, place) for layer, spec in LAYERS.items() for place in spec["places"]]


def features(layer: str) -> list[dict[str, Any]]:
    order = _order()
    out = []
    for code, ar, fr, en, lat, lon, dlat, dlon in GOUVERNORATS:
        for index, (key, place) in enumerate(order):
            if key != layer:
                continue
            suffix, kind, hours, name_ar, name_fr, name_en = place
            # Places a few hundred metres apart, from the centre towards the inland side.
            step = index + 1
            plat, plon = round(lat + dlat * step, 6), round(lon + dlon * step, 6)
            names = {
                "ar": SIM + name_ar.format(ar=ar),
                "fr": SIM + name_fr.format(fr=fr),
                "en": SIM + name_en.format(en=en),
            }
            props: dict[str, Any] = {
                "id": f"sim-{code}-{suffix}",
                "name": names["fr"],
                "name_ar": names["ar"],
                "name_fr": names["fr"],
                "name_en": names["en"],
                "type": kind,
                "hours": hours,
                "address": f"{ar} / {fr}",
                "simulated": "yes",
                "note_ar": NOTE["ar"],
                "note_fr": NOTE["fr"],
                "note_en": NOTE["en"],
            }
            props = {k: v for k, v in props.items() if v is not None}
            geometry = {"type": "Point", "coordinates": [plon, plat]}
            out.append({"type": "Feature", "id": props["id"], "geometry": geometry, "properties": props})
    return out


def layer_settings(layer: str) -> dict[str, Any]:
    """What to enter in the dashboard when creating the layer (the import does not create layers)."""
    spec = LAYERS[layer]
    return {
        "key": layer,
        "name": spec["names"],
        "icon": spec["icon"],
        "colour": spec["colour"],
        "audience": "public",
        "source": SOURCE,
        "licence": "",
        "to_verify": True,
        "simulated": True,
        "staff_only": ["manager"],
        # Since phase L1a a new layer starts as a draft; the [SIM] layers are for trials and are published at once.
        "status": "published",
    }


def write(out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for layer in LAYERS:
        doc = {"type": "FeatureCollection", "simulated": True, "source": SOURCE, "features": features(layer)}
        path = out / f"sim-{layer}.geojson"
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        written.append(path)
    settings = out / "layers.json"
    settings.write_text(
        json.dumps([layer_settings(layer) for layer in LAYERS], ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    written.append(settings)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=Path("build/sim"), help="folder of the GeoJSON files")
    args = parser.parse_args(argv)
    for path in write(args.out):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
