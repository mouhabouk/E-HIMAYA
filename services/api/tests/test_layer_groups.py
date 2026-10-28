"""Map layers in groups (phase UI-3b, docs/phase-ui3/design-layer-groups.md): every layer lands in a group, the
groups listed are only those holding a layer the caller sees (the sensitive group stays unknown to everyone but its
readers), the administrator manages the groups, and a sensitive layer never leaves the sensitive group."""

import uuid
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.layers import domain

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/staff/layers"
NAMES = {"ar": "مجموعة", "fr": "Groupe", "en": "Group"}


def _admin(staff: Staff) -> dict[str, str]:
    return staff(["sysadmin"], gouvernorat=None)


@pytest.mark.parametrize(
    ("key", "icon", "sensitive", "group"),
    [
        ("osm_hospitals", "pin", False, "health"),
        ("sim_pharmacies", "pin", False, "health"),
        ("osm_police", "pin", False, "security"),
        ("prog_summer_2026", "pin", False, "seasons"),
        ("osm_barracks", "pin", True, "sensitive"),
        ("anything", "pin", True, "sensitive"),
        ("my_layer", "pharmacy", False, "health"),
        ("my_layer", "pin", False, "other"),
    ],
)
def test_default_group(key: str, icon: str, sensitive: bool, group: str) -> None:
    assert domain.default_group(key, icon, sensitive) == group


async def _create(client: httpx.AsyncClient, staff: Staff, key: str, **extra: Any) -> dict[str, Any]:
    body = {
        "key": key,
        "name": {"ar": "طبقة", "fr": "Couche", "en": "Layer"},
        "icon": "pin",
        "colour": "#2E7D32",
        "reason": "test of layer groups",
        "status": "published",
        "audiences": ["room", "command"],
        **extra,
    }
    r = await client.post(URL, json=body, headers=_admin(staff))
    assert r.status_code == 201, r.text
    return r.json()


async def _patch(client: httpx.AsyncClient, staff: Staff, layer: dict[str, Any], **changes: Any) -> httpx.Response:
    return await client.patch(
        f"{URL}/{layer['key']}",
        json={"version": layer["version"], "reason": "move to a group", **changes},
        headers=_admin(staff),
    )


def _group(listing: dict[str, Any], key: str) -> dict[str, Any] | None:
    return next((g for g in listing["groups"] if g["key"] == key), None)


async def test_groups_follow_what_the_caller_sees(client: httpx.AsyncClient, staff: Staff) -> None:
    suffix = uuid.uuid4().hex[:6]
    clinic = await _create(client, staff, f"t_clinic_{suffix}", icon="clinic")
    secret = await _create(
        client, staff, f"t_secret_{suffix}", sensitive=True, audiences=["command"], status="published"
    )
    assert clinic["group"] == "health" and secret["group"] == "sensitive"

    admin = (await client.get(URL, headers=_admin(staff))).json()
    assert [g["key"] for g in admin["groups"]][:2] == ["civil_protection", "health"]
    assert {g["key"] for g in admin["groups"]} >= {"other", "sensitive"}

    room = (await client.get(URL, headers=staff(["operator"], gouvernorat=None))).json()
    assert _group(room, "health") is not None and _group(room, "sensitive") is None
    assert all(g["layer_count"] > 0 for g in room["groups"])
    assert {g["key"] for g in room["groups"]} == {i["group"] for i in room["items"]}

    minister = (await client.get(URL, headers=staff(["central_committee"], gouvernorat=None))).json()
    assert (_group(minister, "sensitive") or {}).get("layer_count", 0) >= 1


async def test_move_a_layer_and_the_sensitive_rule(client: httpx.AsyncClient, staff: Staff) -> None:
    suffix = uuid.uuid4().hex[:6]
    layer = await _create(client, staff, f"t_move_{suffix}")
    assert layer["group"] == "other"
    r = await _patch(client, staff, layer, group_key="transport")
    assert r.status_code == 200, r.text
    moved = r.json()
    assert moved["group"] == "transport"
    assert (await _patch(client, staff, moved, group_key="nowhere")).status_code == 404
    assert (await _patch(client, staff, moved, group_key="sensitive")).json()["detail"] == "group_sensitivity_mismatch"
    # Becoming sensitive takes it out of its group into the sensitive one.
    r = await _patch(client, staff, moved, sensitive=True)
    assert r.status_code == 200, r.text
    secret = r.json()
    assert secret["group"] == "sensitive"
    assert (await _patch(client, staff, secret, group_key="health")).status_code == 422
    # Back to the start: the revision restores the settings, its group with them.
    r = await client.post(
        f"{URL}/{layer['key']}/revisions/2/restore", json={"reason": "back to transport"}, headers=_admin(staff)
    )
    assert r.status_code == 200, r.text
    assert r.json()["group"] == "transport"


async def test_manage_groups(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    admin = _admin(staff)
    key = f"g_{uuid.uuid4().hex[:8]}"
    body = {"key": key, "name": NAMES, "icon": "warning", "tone": "orange", "position": 5}
    for headers in (staff(), staff(["operator"], gouvernorat=None), staff(["central_committee"], gouvernorat=None)):
        assert (await client.post(f"{URL}/groups", json=body, headers=headers)).status_code == 403
    assert (await client.post(f"{URL}/groups", json={**body, "icon": "rocket"}, headers=admin)).status_code == 422
    assert (await client.post(f"{URL}/groups", json={**body, "tone": "gold"}, headers=admin)).status_code == 422
    r = await client.post(f"{URL}/groups", json=body, headers=admin)
    assert r.status_code == 201, r.text
    assert r.json()["layer_count"] == 0
    assert (await client.post(f"{URL}/groups", json=body, headers=admin)).status_code == 409

    # An empty group shows to the administrator only.
    assert _group((await client.get(URL, headers=admin)).json(), key) is not None
    assert _group((await client.get(URL, headers=staff(["operator"], gouvernorat=None))).json(), key) is None

    r = await client.patch(f"{URL}/groups/{key}", json={"tone": "teal", "position": 2}, headers=admin)
    assert r.status_code == 200, r.text
    assert (r.json()["tone"], r.json()["position"]) == ("teal", 2)

    layer = await _create(client, staff, f"t_in_{key}")
    moved = (await _patch(client, staff, layer, group_key=key)).json()
    assert (await client.delete(f"{URL}/groups/{key}", headers=admin)).json()["detail"] == "group_not_empty"
    assert (await _patch(client, staff, moved, group_key="other")).status_code == 200
    assert (await client.delete(f"{URL}/groups/{key}", headers=admin)).status_code == 204
    assert (await client.delete(f"{URL}/groups/{key}", headers=admin)).status_code == 404
    for kept in ("other", "sensitive"):
        assert (await client.delete(f"{URL}/groups/{kept}", headers=admin)).json()["detail"] == "group_kept"

    actions = (
        await session.scalars(
            text("SELECT action FROM audit.log WHERE target = :t ORDER BY id"), {"t": f"layer_group:{key}"}
        )
    ).all()
    assert actions == ["layer_group.create", "layer_group.update", "layer_group.delete"]
