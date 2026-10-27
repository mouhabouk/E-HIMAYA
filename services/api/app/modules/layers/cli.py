"""Load the enriched OpenStreetMap layers as drafts (phase L1a, docs/phase-l/design-layers.md §3.7), for development
and trials. Run in the API image with the API's environment:

python -m app.modules.layers.cli load-osm /data/osm [--only hospitals,beaches] [--dry-run]

Each ``layers/<name>_enriched.geojson`` file (and ``beaches/beaches_enriched.geojson``) becomes the layer
``osm_<name>``, created as a draft with the suggested settings below when it does not exist, then filled by a normal
import in ``replace`` mode: a preview, applied at once, recorded in the import history and the audit log as
``system``, and undoable from the layers page. A layer the administrator already has keeps its settings (only its
places are imported again); a deleted one is skipped. Nothing is published: the administrator reviews the names and
publishes each layer from the dashboard. The two sensitive layers are not in the repository and are never loaded here.
"""

import argparse
import asyncio
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from app.core.db import dispose_engine, get_system_sessionmaker
from app.modules.audit import service as audit
from app.modules.geo.models import Layer, LayerImport, LayerRevision
from app.modules.layers import access, domain, service
from app.modules.layers.router import REVISED

ACTOR = audit.SYSTEM_ACTOR
REASON = "chargement initial des couches OpenStreetMap enrichies (brouillon)"
SOURCE = "OpenStreetMap"
LICENCE = "ODbL 1.0 (© OpenStreetMap contributors)"
OPERATIONAL: tuple[access.Audience, ...] = ("room", "field", "command")
EVERYONE = access.AUDIENCES
STAFF = access.STAFF_AUDIENCES


@dataclass(frozen=True)
class Preset:
    ar: str
    fr: str
    en: str
    icon: str
    colour: str
    # The audiences suggested when the administrator publishes it (the layer starts as a draft).
    audiences: tuple[access.Audience, ...]


PRESETS: dict[str, Preset] = {
    "hospitals": Preset("المستشفيات", "Hôpitaux", "Hospitals", "hospital", "#C62828", EVERYONE),
    "clinics": Preset("المصحات", "Cliniques", "Clinics", "clinic", "#AD1457", EVERYONE),
    "pharmacies": Preset("الصيدليات", "Pharmacies", "Pharmacies", "pharmacy", "#2E7D32", EVERYONE),
    "civil_protection": Preset(
        "الحماية المدنية (OSM)",
        "Protection civile (OSM)",
        "Civil protection (OSM)",
        "civil_protection",
        "#BF360C",
        STAFF,
    ),
    "forests": Preset("الغابات", "Forêts", "Forests", "pin", "#2E7D32", OPERATIONAL),
    "rivers": Preset("الأودية", "Oueds", "Rivers", "water", "#1565C0", OPERATIONAL),
    "lakes": Preset("البحيرات والسدود", "Lacs et barrages", "Lakes and dams", "water", "#283593", OPERATIONAL),
    "railways": Preset("السكك الحديدية", "Voies ferrées", "Railways", "pin", "#37474F", OPERATIONAL),
    "beaches": Preset("الشواطئ", "Plages", "Beaches", "pin", "#00695C", OPERATIONAL),
    "schools": Preset("المدارس", "Écoles", "Schools", "school", "#283593", OPERATIONAL),
    "institutes": Preset("المعاهد", "Lycées", "Secondary schools", "school", "#1565C0", OPERATIONAL),
    "faculties": Preset("الكليات", "Facultés", "Faculties", "school", "#6A1B9A", OPERATIONAL),
    "universities": Preset("الجامعات", "Universités", "Universities", "school", "#6A1B9A", OPERATIONAL),
    "elderly_homes": Preset("دور المسنين", "Maisons de retraite", "Elderly homes", "shelter", "#AD1457", OPERATIONAL),
    "worship": Preset("دور العبادة", "Lieux de culte", "Places of worship", "pin", "#5D4037", OPERATIONAL),
    "sports": Preset("الملاعب", "Stades et terrains", "Sports grounds", "pin", "#00695C", OPERATIONAL),
    "supermarkets": Preset("المغازات الكبرى", "Supermarchés", "Supermarkets", "pin", "#5D4037", OPERATIONAL),
    "hotels": Preset("النزل", "Hôtels", "Hotels", "shelter", "#283593", OPERATIONAL),
    "factories": Preset("المصانع", "Usines", "Factories", "factory", "#37474F", OPERATIONAL),
    "companies": Preset("الشركات", "Entreprises", "Companies", "factory", "#5D4037", OPERATIONAL),
    "fuel_stations": Preset("محطات الوقود", "Stations-service", "Fuel stations", "fuel", "#BF360C", OPERATIONAL),
    "police": Preset("الشرطة", "Police", "Police", "police", "#283593", OPERATIONAL),
    "national_guard": Preset("الحرس الوطني", "Garde nationale", "National guard", "guard", "#2E7D32", OPERATIONAL),
    "ministries": Preset("الوزارات", "Ministères", "Ministries", "pin", "#37474F", OPERATIONAL),
    "airports": Preset("المطارات", "Aéroports", "Airports", "pin", "#1565C0", OPERATIONAL),
    "train_stations": Preset("محطات القطار", "Gares", "Train stations", "pin", "#37474F", OPERATIONAL),
    "bus_stations": Preset("محطات الحافلات", "Gares routières", "Bus stations", "pin", "#5D4037", OPERATIONAL),
    "bus_stops": Preset("مواقف الحافلات", "Arrêts de bus", "Bus stops", "pin", "#5D4037", OPERATIONAL),
    # Not reliable as a reference (quality report): they stay drafts, seen by nobody but the administrator.
    "governorate_hq": Preset("مقرات الولايات", "Sièges des gouvernorats", "Governorate seats", "pin", "#6A1B9A", ()),
    "delegation_hq": Preset("مقرات المعتمديات", "Sièges des délégations", "Delegation seats", "pin", "#6A1B9A", ()),
    "fire_hydrants": Preset("أعمدة الماء", "Bouches d'incendie", "Fire hydrants", "water", "#C62828", ()),
}
# Never loaded, even when a copy is found next to the others (Yamen's decision: the minister alone, uploaded by hand).
SENSITIVE = ("barracks", "oil_gas")


def files(root: Path) -> dict[str, Path]:
    found = {p.name.removesuffix("_enriched.geojson"): p for p in sorted((root / "layers").glob("*_enriched.geojson"))}
    beaches = root / "beaches" / "beaches_enriched.geojson"
    if beaches.is_file():
        found["beaches"] = beaches
    return {name: path for name, path in found.items() if name not in SENSITIVE}


async def _layer(session: Any, name: str, preset: Preset) -> Layer | None:
    key = f"osm_{name}"
    layer = await session.scalar(select(Layer).where(Layer.key == key).with_for_update())
    if layer is not None:
        return None if layer.deleted_at is not None else layer
    layer = Layer(
        key=key,
        name={"ar": preset.ar, "fr": preset.fr, "en": preset.en},
        icon=preset.icon,
        colour=preset.colour,
        audience="public" if "citizen" in preset.audiences else "staff",
        source=SOURCE,
        licence=LICENCE,
        to_verify=True,
        simulated=False,
        staff_only=[],
        editors_allowed=False,
        enabled=False,
        created_by=ACTOR,
        updated_by=ACTOR,
        status="draft",
        audiences=list(preset.audiences),
        scope=[],
        default_on=False,
        sensitive=False,
        fields={},
        actions={"call": True, "directions": True},
    )
    session.add(layer)
    await session.flush()
    await audit.record(session, actor=ACTOR, action="layer.create", target=f"layer:{key}", reason=REASON)
    session.add(
        LayerRevision(
            layer_id=layer.id,
            number=1,
            action="create",
            snapshot={k: getattr(layer, k) for k in REVISED},
            reason=REASON,
            created_by=ACTOR,
        )
    )
    return layer


async def load(root: Path, only: set[str] | None, dry_run: bool) -> dict[str, Any]:
    report: dict[str, Any] = {}
    try:
        for name, path in files(root).items():
            if only and name not in only:
                continue
            preset = PRESETS.get(name)
            if preset is None:
                report[name] = {"skipped": "no_preset"}
                continue
            data = path.read_bytes()
            try:
                parsed = domain.parse(path.name, data)
            except domain.FileError as e:
                report[name] = {"skipped": e.code}
                continue
            async with get_system_sessionmaker()() as session:
                layer = await _layer(session, name, preset)
                if layer is None:
                    report[name] = {"skipped": "layer_deleted"}
                    continue
                preview = await service.build_preview(session, layer, parsed, "replace")
                job = LayerImport(
                    layer_id=layer.id,
                    file_name=path.name,
                    sha256=hashlib.sha256(data).hexdigest(),
                    format=parsed.format,
                    mode="replace",
                    status="preview",
                    counts=preview.counts,
                    rejected=preview.rejected,
                    warnings=preview.warnings,
                    rows=preview.rows,
                    base_version=layer.data_version,
                    created_by=ACTOR,
                )
                session.add(job)
                await session.flush()
                report[name] = {"layer": layer.key, **preview.counts}
                if dry_run:
                    await session.rollback()
                    continue
                await service.apply(session, layer, job, ACTOR)
                job.reason = REASON
                await audit.record(
                    session,
                    actor=ACTOR,
                    action="layer.import_apply",
                    target=f"layer:{layer.key}",
                    reason=REASON,
                    details={"import": str(job.id), "file": job.file_name, "sha256": job.sha256, **job.counts},
                )
                await session.commit()
        async with get_system_sessionmaker()() as session:
            report["_layers"] = await session.scalar(select(func.count()).select_from(Layer))
        return report
    finally:
        await dispose_engine()


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.modules.layers.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    osm = commands.add_parser("load-osm", help="load the enriched OpenStreetMap layers as drafts")
    osm.add_argument("root", type=Path, help="the data/osm folder")
    osm.add_argument("--only", help="comma-separated names (default: all), e.g. hospitals,beaches")
    osm.add_argument("--dry-run", action="store_true", help="count what would change, write nothing")
    args = parser.parse_args()
    only = {n.strip() for n in args.only.split(",") if n.strip()} if args.only else None
    result = asyncio.run(load(args.root, only, args.dry_run))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
