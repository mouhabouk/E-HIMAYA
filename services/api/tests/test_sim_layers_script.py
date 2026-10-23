"""Approximate trial places ([SIM], phase B1, Yamen 2026-10-23): the script's files pass the layer import, every
place lands in its own gouvernorat, the layer carries the "simulated" mark and the app gets each place's name in its
language."""

import importlib.util
import json
import uuid
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx

from app.modules.layers import domain
from app.modules.layers.schemas import LayerIn

SCRIPT = Path(__file__).resolve().parents[3] / "scripts/sim_layers.py"
URL = "/api/v1/staff/layers"
Staff = Callable[..., dict[str, str]]


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("sim_layers", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_files_are_marked_and_pass_the_import(tmp_path: Path) -> None:
    script = _script()
    paths = script.write(tmp_path)
    total = 0
    for path in paths:
        if path.name == "layers.json":
            for settings in json.loads(path.read_text(encoding="utf-8")):
                body = LayerIn.model_validate({**settings, "reason": "approximate trial data"})
                assert body.simulated and body.to_verify and body.source.startswith("[SIM]")
            continue
        parsed = domain.parse(path.name, path.read_bytes())
        assert not parsed.rejected, parsed.rejected
        for row in parsed.rows:
            # Invented places are named as such in every language and never carry a number to dial.
            assert row.name.startswith("[SIM] ") and row.phone is None
            assert all(row.props[f"name_{lang}"].startswith("[SIM] ") for lang in ("ar", "fr", "en"))
            assert row.ref.startswith("sim-")
        total += len(parsed.rows)
    assert total == 24 * 6
    # Same output at every run.
    again = script.features("pharmacies")
    assert again == script.features("pharmacies") and len(again) == 48


async def _sim_layer(client: httpx.AsyncClient, staff: Staff, tmp_path: Path, layer: str) -> dict[str, Any]:
    script = _script()
    script.write(tmp_path)
    admin = staff(["sysadmin"], gouvernorat=None)
    settings = {
        **script.layer_settings(layer),
        "key": f"sim_{uuid.uuid4().hex[:8]}_{layer}"[:40],
        "reason": "approximate trial data",
    }
    r = await client.post(URL, json=settings, headers=admin)
    assert r.status_code == 201, r.text
    assert r.json()["simulated"] is True
    data = (tmp_path / f"sim-{layer}.geojson").read_bytes()
    preview = await client.post(
        f"{URL}/{settings['key']}/imports",
        params={"file_name": f"sim-{layer}.geojson", "mode": "replace"},
        content=data,
        headers={**admin, "Content-Type": "application/octet-stream"},
    )
    assert preview.status_code == 201, preview.text
    assert preview.json()["counts"]["rejected"] == 0
    applied = await client.post(
        f"{URL}/{settings['key']}/imports/{preview.json()['id']}/apply", json={"reason": "trial data"}, headers=admin
    )
    assert applied.status_code == 200, applied.text
    return settings


async def test_every_place_in_its_gouvernorat_and_named_in_the_app_language(
    client: httpx.AsyncClient, staff: Staff, tmp_path: Path
) -> None:
    settings = await _sim_layer(client, staff, tmp_path, "hospitals")
    key = settings["key"]
    layers = {i["key"]: i for i in (await client.get("/api/v1/layers", params={"lang": "en"})).json()["items"]}
    assert layers[key]["simulated"] is True and layers["civil_protection"]["simulated"] is False

    for code in (11, 23, 53, 61, 83):
        for lang, start in (("ar", "[SIM] المستشفى الجهوي"), ("fr", "[SIM] Hôpital régional"), ("en", "[SIM] ")):
            r = await client.get(f"/api/v1/layers/{key}/package", params={"gouvernorat": code, "lang": lang})
            items = r.json()["items"]
            assert len(items) == 1, (code, items)
            assert items[0]["name"].startswith(start) and items[0]["phone"] is None
            assert items[0]["gouvernorat_code"] == code
    # Nearest place to Sfax, in French.
    r = await client.get(f"/api/v1/layers/{key}/features", params={"near": "34.74,10.76", "lang": "fr", "limit": 1})
    assert r.json()["items"][0]["name"] == "[SIM] Hôpital régional de Sfax"


async def test_the_mark_can_be_removed_and_changes_the_package(
    client: httpx.AsyncClient, staff: Staff, tmp_path: Path
) -> None:
    settings = await _sim_layer(client, staff, tmp_path, "police")
    admin = staff(["sysadmin"], gouvernorat=None)
    current = next(i for i in (await client.get(URL, headers=admin)).json()["items"] if i["key"] == settings["key"])
    r = await client.patch(
        f"{URL}/{settings['key']}",
        json={"version": current["version"], "simulated": False, "reason": "official list imported"},
        headers=admin,
    )
    assert r.status_code == 200 and r.json()["simulated"] is False
    assert r.json()["data_version"] == current["data_version"] + 1


def test_committed_files_match_the_script(tmp_path: Path) -> None:
    committed = Path(__file__).resolve().parents[3] / "data/sim-layers"
    for path in _script().write(tmp_path):
        assert (committed / path.name).read_bytes() == path.read_bytes(), f"run scripts/sim_layers.py: {path.name}"
