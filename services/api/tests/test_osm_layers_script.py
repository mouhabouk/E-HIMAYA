"""OpenStreetMap first load (phase B1, design §2.8): the script's files pass the layer import as they are."""

import importlib.util
import json
from pathlib import Path
from types import ModuleType

from app.modules.layers import domain

SCRIPT = Path(__file__).resolve().parents[3] / "scripts/osm_layers.py"


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("osm_layers", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ANSWER = {
    "osm3s": {"timestamp_osm_base": "2026-10-23T08:00:00Z"},
    "elements": [
        {
            "type": "node",
            "id": 1,
            "lat": 34.7406,
            "lon": 10.7603,
            "tags": {
                "amenity": "hospital",
                "name": "مستشفى الحبيب بورقيبة",
                "name:fr": "Hôpital Habib Bourguiba",
                "emergency": "yes",
                "phone": "+216 74 241 511",
                "beds": "420",
            },
        },
        {
            "type": "way",
            "id": 2,
            "center": {"lat": 36.8065, "lon": 10.1815},
            "tags": {"amenity": "pharmacy", "name": "Pharmacie de nuit", "opening_hours": "24/7"},
        },
        {
            "type": "node",
            "id": 3,
            "lat": 36.4,
            "lon": 10.6,
            "tags": {"amenity": "police", "name": "Poste de la Garde nationale", "operator": "Garde nationale"},
        },
        {"type": "node", "id": 4, "lat": 36.5, "lon": 10.1, "tags": {"amenity": "police", "name": "Poste de police"}},
        {"type": "node", "id": 5, "lat": 36.5, "lon": 10.1, "tags": {"amenity": "pharmacy"}},
        {"type": "node", "id": 6, "lat": 36.5, "lon": 10.1, "tags": {"amenity": "school", "name": "École"}},
        {"type": "relation", "id": 7, "tags": {"amenity": "clinic", "name": "Clinique sans centre"}},
    ],
}


def test_layers_and_left_out() -> None:
    script = _script()
    by_layer, left_out = script.convert(ANSWER)
    names = {layer: [f["properties"]["name"] for f in feats] for layer, feats in by_layer.items()}
    assert names["hospitals"] == ["مستشفى الحبيب بورقيبة"]
    assert names["pharmacies"] == ["Pharmacie de nuit"]
    assert names["national_guard"] == ["Poste de la Garde nationale"]
    assert names["police"] == ["Poste de police"]
    assert names["clinics"] == []
    assert left_out == {"pharmacies:no_name": 1, "clinics:no_position": 1}
    hospital = by_layer["hospitals"][0]["properties"]
    assert hospital["id"] == "osm-node-1" and hospital["type"] == "emergency" and hospital["beds"] == "420"
    assert "osm_name_fr" not in hospital and hospital["name_fr"] == "Hôpital Habib Bourguiba"
    assert "nwr" in script.query() and '"ISO3166-1"="TN"' in script.query()


def test_files_pass_the_layer_import(tmp_path: Path) -> None:
    script = _script()
    by_layer, _ = script.convert(ANSWER)
    paths = script.write(by_layer, tmp_path, "2026-10-23T08:00:00Z")
    hospitals = next(p for p in paths if p.name == "osm-hospitals.geojson")
    doc = json.loads(hospitals.read_text(encoding="utf-8"))
    assert doc["attribution"].startswith("© OpenStreetMap contributors")
    parsed = domain.parse(hospitals.name, hospitals.read_bytes())
    assert not parsed.rejected
    row = parsed.rows[0]
    assert row.ref == "osm-node-1" and row.phone == "+21674241511" and row.kind == "emergency"
    assert row.props["beds"] == "420" and row.props["name_fr"] == "Hôpital Habib Bourguiba"
