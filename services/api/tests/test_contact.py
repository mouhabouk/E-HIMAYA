"""Contact us (phase B1, docs/phase-b/design.md §2ter): numbered requests, inbox by kind and gouvernorat, history,
answers seen by the citizen, internal notes never, encrypted contact details, export and erasure."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import device_headers

Staff = Callable[..., dict[str, str]]
STAFF_URL = "/api/v1/staff/contact"


def _body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "kind": "question",
        "subject": "Formation aux premiers secours",
        "message": "Proposez-vous des formations pour les associations de quartier ?",
        "gouvernorat_code": 61,
        "phone": "22 333 444",
        "locale": "fr",
        "platform": "android",
    }
    body.update(overrides)
    return body


async def _send(client: httpx.AsyncClient, headers: dict[str, str], **overrides: Any) -> dict[str, Any]:
    r = await client.post("/api/v1/contact", json=_body(**overrides), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _act(
    client: httpx.AsyncClient, headers: dict[str, str], request: dict[str, Any], action: str, **extra: Any
) -> httpx.Response:
    return await client.post(
        f"{STAFF_URL}/{request['id']}/actions",
        json={"version": request["version"], "action": action, **extra},
        headers=headers,
    )


async def test_request_gets_a_number_and_is_encrypted(
    client: httpx.AsyncClient, citizen: dict[str, str], session: AsyncSession
) -> None:
    mine = await _send(client, citizen, name="Salma Ben Ali", email="salma@example.tn")
    year = datetime.now(UTC).astimezone().year
    assert mine["number"].startswith(f"CT-{year}-") and len(mine["number"]) == 14
    assert mine["status"] == "received" and mine["due_at"] is None
    assert [h["action"] for h in mine["history"]] == ["created"]
    row = (
        await session.execute(
            text("SELECT name_enc, phone_enc, message_enc FROM contact.request WHERE number = :n"),
            {"n": mine["number"]},
        )
    ).one()
    for raw in row:
        assert b"Salma" not in bytes(raw) and b"22333444" not in bytes(raw) and b"formations" not in bytes(raw)
    listed = (await client.get("/api/v1/me/contact", headers=citizen)).json()["items"]
    assert [m["number"] for m in listed] == [mine["number"]]


async def test_rules_of_the_form(client: httpx.AsyncClient, citizen: dict[str, str]) -> None:
    async def post(**overrides: Any) -> httpx.Response:
        return await client.post("/api/v1/contact", json=_body(**overrides), headers=citizen)

    assert (await post(kind="access_info")).status_code == 422  # name required by law 2016-22
    assert (await post(kind="hazard", gouvernorat_code=None)).status_code == 422
    assert (await post(phone="123")).json()["detail"] == "invalid_phone"
    assert (await post(email="not-an-email")).json()["detail"] == "invalid_email"
    assert (await post(gouvernorat_code=98)).json()["detail"] == "unknown_gouvernorat"
    assert (await post(message="short")).status_code == 422
    assert (await post(kind="emergency")).status_code == 422


async def test_access_to_information_has_a_legal_deadline(client: httpx.AsyncClient, citizen: dict[str, str]) -> None:
    mine = await _send(client, citizen, kind="access_info", name="Karim Trabelsi", gouvernorat_code=None)
    due = datetime.fromisoformat(mine["due_at"])
    created = datetime.fromisoformat(mine["created_at"])
    assert timedelta(days=19, hours=23) < due - created <= timedelta(days=20, minutes=1)


async def test_anonymous_device_identity_can_write(client: httpx.AsyncClient) -> None:
    headers = device_headers()
    mine = await _send(client, headers, phone=None)
    assert mine["number"]
    assert (await client.get("/api/v1/me/contact", headers=headers)).json()["items"][0]["id"] == mine["id"]


async def test_inbox_scope_and_roles(
    client: httpx.AsyncClient, citizen: dict[str, str], staff: Staff, make_token: Any
) -> None:
    sfax = await _send(client, citizen, gouvernorat_code=61, subject="Sfax question")
    national = await _send(client, citizen, gouvernorat_code=None, kind="suggestion", subject="National idea")
    regional = staff(["ops_manager"], gouvernorat=61)
    tunis = staff(["ops_manager"], gouvernorat=11)
    central = staff(["central_committee"], gouvernorat=None)

    assert (await client.get(STAFF_URL, headers=staff(["operator"]))).status_code == 403
    assert (await client.get(STAFF_URL, headers=citizen)).status_code in (401, 403)

    numbers = {i["number"] for i in (await client.get(STAFF_URL, headers=regional)).json()["items"]}
    assert sfax["number"] in numbers and national["number"] not in numbers
    numbers = {i["number"] for i in (await client.get(STAFF_URL, headers=tunis)).json()["items"]}
    assert sfax["number"] not in numbers
    assert (await client.get(f"{STAFF_URL}/{sfax['id']}", headers=tunis)).status_code == 404

    inbox = (await client.get(STAFF_URL, params={"gouvernorat": 0}, headers=central)).json()
    assert national["number"] in {i["number"] for i in inbox["items"]}
    assert sfax["number"] not in {i["number"] for i in inbox["items"]}
    assert inbox["open_by_kind"]["suggestion"] >= 1
    kinds = (await client.get(STAFF_URL, params={"kind": "suggestion"}, headers=central)).json()["items"]
    assert {i["kind"] for i in kinds} == {"suggestion"}


async def test_handling_answer_note_and_history(
    client: httpx.AsyncClient, citizen: dict[str, str], staff: Staff, session: AsyncSession
) -> None:
    mine = await _send(client, citizen, name="Salma Ben Ali")
    handler = staff(["local_committee"], gouvernorat=61)
    detail = (await client.get(f"{STAFF_URL}/{mine['id']}", headers=handler)).json()
    assert detail["name"] == "Salma Ben Ali" and detail["phone"] == "+21622333444"

    r = await _act(client, handler, detail, "take")
    assert r.status_code == 200 and r.json()["status"] == "in_progress"
    stale = await _act(client, handler, detail, "note", text="appel prévu demain")
    assert stale.status_code == 409 and stale.json()["detail"] == "version_conflict"
    detail = r.json()
    r = await _act(client, handler, detail, "note", text="appel prévu demain")
    assert r.status_code == 200
    detail = r.json()
    assert (await _act(client, handler, detail, "answer")).json()["detail"] == "text_required"
    r = await _act(client, handler, detail, "answer", text="Oui, inscrivez-vous auprès du centre régional.")
    assert r.json()["status"] == "answered"
    detail = r.json()
    assert [e["action"] for e in detail["events"]] == ["created", "status", "note", "answer"]
    assert (await _act(client, handler, detail, "reject", text="trop tard")).json()["detail"] == "invalid_transition"

    seen = (await client.get("/api/v1/me/contact", headers=citizen)).json()["items"][0]
    assert seen["status"] == "answered" and seen["answer"].startswith("Oui")
    assert [h["action"] for h in seen["history"]] == ["created", "status", "answer"]
    assert "appel" not in str(seen)

    closed = await _act(client, handler, detail, "close")
    assert closed.json()["status"] == "closed" and closed.json()["closed_at"]
    reopened = await _act(client, handler, closed.json(), "reopen")
    assert reopened.json()["status"] == "in_progress" and reopened.json()["closed_at"] is None

    actions = (
        await session.execute(
            text("SELECT action FROM audit.log WHERE target = :t ORDER BY id"), {"t": f"contact:{mine['number']}"}
        )
    ).scalars()
    assert list(actions) == [
        "contact.create",
        "contact.view",
        "contact.take",
        "contact.note",
        "contact.answer",
        "contact.close",
        "contact.reopen",
    ]


async def test_move_to_another_gouvernorat(client: httpx.AsyncClient, citizen: dict[str, str], staff: Staff) -> None:
    mine = await _send(client, citizen, gouvernorat_code=61)
    sfax, tunis = staff(["ops_manager"], gouvernorat=61), staff(["ops_manager"], gouvernorat=11)
    detail = (await client.get(f"{STAFF_URL}/{mine['id']}", headers=sfax)).json()
    r = await _act(client, sfax, detail, "move", gouvernorat_code=11)
    assert r.status_code == 200, r.text
    assert (await client.get(f"{STAFF_URL}/{mine['id']}", headers=sfax)).status_code == 404
    moved = (await client.get(f"{STAFF_URL}/{mine['id']}", headers=tunis)).json()
    assert moved["gouvernorat_code"] == 11 and moved["events"][-1]["action"] == "move"


async def test_export_and_erasure(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    headers = device_headers()
    mine = await _send(client, headers, name="Ali", email="ali@example.tn")
    exported = (await client.get("/api/v1/me/export", headers=headers)).json()
    assert exported["contact"][0]["number"] == mine["number"]
    assert exported["contact"][0]["email"] == "ali@example.tn"

    r = await client.post("/api/v1/me/delete", json={"confirm": "DELETE"}, headers=headers)
    assert r.status_code == 202, r.text
    row = (
        await session.execute(
            text("SELECT user_id, name_enc, phone_enc, email_enc, message_enc FROM contact.request WHERE id = :i"),
            {"i": mine["id"]},
        )
    ).one()
    assert row[:4] == (None, None, None, None) and row[4] is not None
    kept = (
        await client.get(f"{STAFF_URL}/{mine['id']}", headers=staff(["central_committee"], gouvernorat=None))
    ).json()
    assert kept["anonymous"] is True and kept["message"].startswith("Proposez")


async def test_respectful_language_applies(client: httpx.AsyncClient, citizen: dict[str, str], staff: Staff) -> None:
    from app.modules.moderation.terms import BUILT_IN

    word = sorted(BUILT_IN)[0]
    r = await client.post("/api/v1/contact", json=_body(message=f"Votre service est {word} vraiment"), headers=citizen)
    assert r.status_code == 422 and r.json()["detail"] == "offensive_text"
