"""Emergency hub topics and items (phase B1, docs/phase-b/design.md §2bis): add, change, hide, reorder, validate."""

import uuid
from collections.abc import Callable
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/staff/emergency-guide"


def _editor(staff: Staff) -> dict[str, str]:
    return staff(["content_editor"], gouvernorat=None)


def _text(title: str) -> dict[str, Any]:
    return {"title": title, "call": ["Si inconscient"], "steps": ["Étape 1", "Étape 2"], "dont": ["Ne pas paniquer"]}


def _content(title: str = "Électrocution") -> dict[str, Any]:
    return {"ar": _text("صعق كهربائي"), "fr": _text(title), "en": _text("Electric shock")}


async def _topic(client: httpx.AsyncClient, staff: Staff) -> dict[str, Any]:
    key = f"t_{uuid.uuid4().hex[:8]}"
    r = await client.post(
        f"{URL}/topics",
        json={
            "key": key,
            "title": {"ar": "الكهرباء", "fr": "Électricité", "en": "Electricity"},
            "icon": "electric",
            "colour": "#283593",
            "reason": "new topic asked by the Office",
        },
        headers=_editor(staff),
    )
    assert r.status_code == 201, r.text
    return next(t for t in r.json()["topics"] if t["key"] == key)


async def test_first_load_is_public_and_awaits_validation(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/emergency-guide")
    assert r.status_code == 200
    topics = {t["key"]: t for t in r.json()["topics"]}
    assert {"fire", "fracture", "first_aid", "breathing", "burns", "bleeding"} <= set(topics)
    keys = [t["key"] for t in r.json()["topics"]]
    assert keys.index("fire") < keys.index("fracture") < keys.index("first_aid") < keys.index("breathing")
    cpr = topics["first_aid"]["items"][0]
    assert cpr["call_198"] is True and cpr["content"]["fr"]["steps"]
    assert topics["fire"]["title"]["ar"] == "الحرائق"
    assert all(not i["validated"] for t in topics.values() if t["key"] == "fire" for i in t["items"])
    # Migration 0036: "other emergencies" after the first six, more items, in three languages, awaiting validation.
    assert keys.index("bleeding") < keys.index("other")
    other = [i["content"]["fr"]["title"] for i in topics["other"]["items"]]
    assert "Piqûre de scorpion" in other and "Noyade" in other
    assert len(topics["first_aid"]["items"]) >= 7 and len(topics["fire"]["items"]) >= 5
    for item in topics["other"]["items"]:
        assert not item["validated"]
        assert all(item["content"][lang]["steps"] for lang in ("ar", "fr", "en"))
    again = await client.get("/api/v1/emergency-guide", headers={"If-None-Match": r.headers["etag"]})
    assert again.status_code == 304


async def test_only_content_editors(client: httpx.AsyncClient, staff: Staff, citizen: dict[str, str]) -> None:
    assert (await client.get(URL)).status_code == 401
    assert (await client.get(URL, headers=citizen)).status_code == 403
    assert (await client.get(URL, headers=staff(["operator"]))).status_code == 403
    r = await client.get(URL, headers=_editor(staff))
    assert r.status_code == 200 and "fire" in r.json()["icons"]


async def test_add_change_hide_and_validate(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    editor = _editor(staff)
    topic = await _topic(client, staff)
    r = await client.post(
        f"{URL}/topics/{topic['id']}/items",
        json={"content": _content(), "call_198": True, "reason": "first item"},
        headers=editor,
    )
    assert r.status_code == 201, r.text
    item = next(t for t in r.json()["topics"] if t["id"] == topic["id"])["items"][0]
    public = (await client.get("/api/v1/emergency-guide")).json()
    shown = next(t for t in public["topics"] if t["id"] == topic["id"])
    assert shown["items"][0]["content"]["fr"]["title"] == "Électrocution" and shown["items"][0]["validated"] is False

    # Validate, then a new text withdraws the validation.
    r = await client.post(
        f"{URL}/items/{item['id']}/validate",
        json={"version": item["version"], "reason": "checked by Dr X"},
        headers=editor,
    )
    item = next(t for t in r.json()["topics"] if t["id"] == topic["id"])["items"][0]
    assert item["validated"] is True and item["validated_by"]
    r = await client.patch(
        f"{URL}/items/{item['id']}",
        json={"version": item["version"], "content": _content("Électrisation"), "reason": "better wording"},
        headers=editor,
    )
    item = next(t for t in r.json()["topics"] if t["id"] == topic["id"])["items"][0]
    assert item["validated"] is False and item["content"]["fr"]["title"] == "Électrisation"
    stale = await client.patch(
        f"{URL}/items/{item['id']}", json={"version": 1, "hidden": True, "reason": "stale edit"}, headers=editor
    )
    assert (stale.status_code, stale.json()["detail"]) == (409, "version_conflict")

    # Hide the item, then the whole topic: the app no longer shows them; the dashboard still does.
    r = await client.patch(
        f"{URL}/items/{item['id']}",
        json={"version": item["version"], "hidden": True, "reason": "under review"},
        headers=editor,
    )
    assert r.status_code == 200
    public = (await client.get("/api/v1/emergency-guide")).json()
    assert next(t for t in public["topics"] if t["id"] == topic["id"])["items"] == []
    r = await client.patch(
        f"{URL}/topics/{topic['id']}",
        json={"version": topic["version"], "hidden": True, "reason": "not ready"},
        headers=editor,
    )
    assert r.status_code == 200
    public = (await client.get("/api/v1/emergency-guide")).json()
    assert topic["id"] not in {t["id"] for t in public["topics"]}
    staff_view = (await client.get(URL, headers=editor)).json()
    assert next(t for t in staff_view["topics"] if t["id"] == topic["id"])["hidden"] is True

    actions = (
        await session.scalars(
            text("SELECT action FROM audit.log WHERE target IN (:t, :i) ORDER BY seq"),
            {"t": f"guide_topic:{topic['key']}", "i": f"guide_item:{item['id']}"},
        )
    ).all()
    assert actions == [
        "guide.topic_create",
        "guide.item_create",
        "guide.item_validate",
        "guide.item_update",
        "guide.item_update",
        "guide.topic_update",
    ]


async def test_reorder_and_move_between_topics(client: httpx.AsyncClient, staff: Staff) -> None:
    editor = _editor(staff)
    first, second = await _topic(client, staff), await _topic(client, staff)
    r = await client.post(f"{URL}/topics/{second['id']}/move", json={"direction": "up"}, headers=editor)
    keys = [t["key"] for t in r.json()["topics"]]
    assert keys.index(second["key"]) < keys.index(first["key"])
    last = keys[-1]
    last_id = next(t["id"] for t in r.json()["topics"] if t["key"] == last)
    r = await client.post(f"{URL}/topics/{last_id}/move", json={"direction": "down"}, headers=editor)
    assert (r.status_code, r.json()["detail"]) == (409, "cannot_move")

    for title in ("A", "B"):
        r = await client.post(
            f"{URL}/topics/{first['id']}/items", json={"content": _content(title), "reason": "add item"}, headers=editor
        )
    items = next(t for t in r.json()["topics"] if t["id"] == first["id"])["items"]
    assert [i["content"]["fr"]["title"] for i in items] == ["A", "B"]
    r = await client.post(f"{URL}/items/{items[1]['id']}/move", json={"direction": "up"}, headers=editor)
    items = next(t for t in r.json()["topics"] if t["id"] == first["id"])["items"]
    assert [i["content"]["fr"]["title"] for i in items] == ["B", "A"]
    r = await client.patch(
        f"{URL}/items/{items[0]['id']}",
        json={"version": items[0]["version"], "topic_id": second["id"], "reason": "belongs to the other topic"},
        headers=editor,
    )
    moved = next(t for t in r.json()["topics"] if t["id"] == second["id"])["items"]
    assert [i["content"]["fr"]["title"] for i in moved] == ["B"]


async def test_checks(client: httpx.AsyncClient, staff: Staff) -> None:
    editor = _editor(staff)
    body = {
        "key": "fire",
        "title": {"ar": "x", "fr": "x", "en": "x"},
        "icon": "fire",
        "colour": "#BF360C",
        "reason": "duplicate key",
    }
    r = await client.post(f"{URL}/topics", json=body, headers=editor)
    assert (r.status_code, r.json()["detail"]) == (409, "key_taken")
    r = await client.post(f"{URL}/topics", json={**body, "key": "t_icon", "icon": "rocket"}, headers=editor)
    assert r.status_code == 422
    r = await client.post(f"{URL}/topics", json={**body, "key": "t_colour", "colour": "#FFB300"}, headers=editor)
    assert r.status_code == 422
    topic = await _topic(client, staff)
    empty = _content()
    empty["en"]["steps"] = []
    r = await client.post(
        f"{URL}/topics/{topic['id']}/items", json={"content": empty, "reason": "no steps"}, headers=editor
    )
    assert r.status_code == 422
