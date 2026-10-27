"""The nearest hospitals of an incident (phase L1b): only the places of hospital layers the reader may see, timed on
the road, and the one the room adds goes on the incident's timeline."""

import json
import uuid
from collections.abc import Callable
from typing import Any

import httpx

from tests.scopehelpers import group, incident, new_report

Staff = Callable[..., dict[str, str]]
LAYERS = "/api/v1/staff/layers"
# Tozeur: far from the places that other tests put in their layers.
HERE = (33.9200, 8.1300)


async def _layer(client: httpx.AsyncClient, admin: dict[str, str], audiences: list[str], places: list[Any]) -> None:
    key = f"t_hosp_{uuid.uuid4().hex[:8]}"
    r = await client.post(
        LAYERS,
        json={
            "key": key,
            "name": {"ar": "مستشفيات", "fr": "Hôpitaux", "en": "Hospitals"},
            "icon": "hospital",
            "colour": "#C62828",
            "source": "test",
            "licence": "ODbL",
            "status": "published",
            "audiences": audiences,
            "reason": "hospital test layer",
        },
        headers=admin,
    )
    assert r.status_code == 201, r.text
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"name": name, "phone": "76000000"},
        }
        for name, lat, lon in places
    ]
    imported = await client.post(
        f"{LAYERS}/{key}/imports",
        params={"file_name": "h.geojson", "mode": "merge"},
        content=json.dumps({"type": "FeatureCollection", "features": features}).encode(),
        headers={**admin, "Content-Type": "application/octet-stream"},
    )
    assert imported.status_code == 201, imported.text
    applied = await client.post(
        f"{LAYERS}/{key}/imports/{imported.json()['id']}/apply", json={"reason": "hospitals"}, headers=admin
    )
    assert applied.status_code == 200, applied.text


async def test_nearest_hospitals_and_the_one_added(client: httpx.AsyncClient, staff: Staff) -> None:
    admin = staff(["sysadmin"], gouvernorat=None)
    operator = staff(["operator"], gouvernorat=72)
    tag = uuid.uuid4().hex[:6]
    seen, far, hidden = f"مستشفى توزر {tag}", f"مصحة دقاش {tag}", f"مستشفى مخفي {tag}"
    await _layer(client, admin, ["room", "command"], [(seen, HERE[0] + 0.01, HERE[1]), (far, 33.98, 8.04)])
    # The nearest of all, in a layer for the citizens only: never offered to the room.
    await _layer(client, admin, ["citizen"], [(hidden, HERE[0] + 0.001, HERE[1])])

    report = await new_report(client, {"lat": HERE[0], "lon": HERE[1], "accuracy_m": 10.0})
    r = await group(client, operator, report["id"], action="new")
    assert r.status_code == 200, r.text
    incident_id = r.json()["incident_id"]
    url = f"/api/v1/staff/incidents/{incident_id}/hospitals"

    r = await client.get(url, headers=operator)
    assert r.status_code == 200, r.text
    names = [h["name"] for h in r.json()]
    assert names[:2] == [seen, far] and hidden not in names
    first = r.json()[0]
    assert first["road_m"] > 0 and first["phone"] == "+21676000000"

    assert (await client.post(url, json={"feature_id": str(uuid.uuid4())}, headers=operator)).status_code == 422
    r = await client.post(url, json={"feature_id": first["id"]}, headers=operator)
    assert r.status_code == 200, r.text
    timeline = (await incident(client, operator, incident_id))["timeline"]
    assert timeline[-1]["kind"] == "hospital_chosen"
    # Reading is not writing: a read-only role cannot add it.
    viewer = staff(["local_committee"], gouvernorat=72)
    assert (await client.post(url, json={"feature_id": first["id"]}, headers=viewer)).status_code == 403
