"""Follow-ups of the guided call-taking cards (docs/phase-os2b/design-os2b.md): the statistics (OS2-3) and the review
of the [SIM] cards (OS2-4)."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reports import callcard_stats as stats

Staff = Callable[..., dict[str, str]]
NABEUL = 21
IN_NABEUL = {"lat": 36.4513, "lon": 10.7357}
REPORTS = "/api/v1/staff/reports"
CARDS = "/api/v1/staff/call-cards"


async def _cards(client: httpx.AsyncClient, headers: dict[str, str]) -> list[dict[str, Any]]:
    r = await client.get(CARDS, headers=headers)
    assert r.status_code == 200, r.text
    cards: list[dict[str, Any]] = r.json()["cards"]
    return cards


def _approved(cards: list[dict[str, Any]], category: str) -> dict[str, Any]:
    return next(c for c in cards if c["category"] == category and c["status"] == "approved")


def _ago(seconds: int) -> str:
    return (datetime.now(UTC) - timedelta(seconds=seconds)).isoformat()


# ---------------------------------------------------------------- statistics (OS2-3)


def test_the_call_time_is_the_phones_then_the_forms() -> None:
    assert stats.duration(95.0, 400.0) == 95.0
    assert stats.duration(None, 120.0) == 120.0
    # Outside 0 s – 2 h it says nothing of the call.
    assert stats.duration(None, -3.0) is None and stats.duration(9000.0, 60.0) is None
    assert stats.duration(None, None) is None
    assert stats._p90([]) is None and stats._p90([40.0]) == 40
    assert stats._p90([float(x) for x in range(1, 11)]) == 9


async def _stats(client: httpx.AsyncClient, headers: dict[str, str], **params: Any) -> dict[str, Any]:
    r = await client.get(f"{CARDS}/stats", headers=headers, params={"channel": "radio", **params})
    assert r.status_code == 200, r.text
    out: dict[str, Any] = r.json()
    return out


def _row(out: dict[str, Any], room: str) -> dict[str, Any]:
    return next((r for r in out["rooms"] if r["room"] == room), {"entered": 0, "with_card": 0})


def _question(out: dict[str, Any], category: str, qid: str) -> dict[str, Any]:
    card = next(c for c in out["cards"] if c["category"] == category)
    return next(q for q in card["questions"] if q["id"] == qid)


async def test_card_use_and_call_time_per_room(client: httpx.AsyncClient, staff: Staff) -> None:
    agent = staff(["operator"], gouvernorat=NABEUL, name="عون القاعة")
    before = await _stats(client, agent)
    assert before["room"] == f"g:{NABEUL}" and all(r["room"] == f"g:{NABEUL}" for r in before["rooms"])
    card = _approved(await _cards(client, agent), "medical")
    base = {"category": "medical", "location": IN_NABEUL, "channel": "radio"}
    with_card = {
        **base,
        "started_at": _ago(90),
        "call_card": {"card_id": card["id"], "version": card["version"], "answers": {"chest": "unknown"}},
    }
    for body in (with_card, {**base, "started_at": _ago(150)}, {**base, "started_at": _ago(5 * 3600)}):
        r = await client.post(REPORTS, json=body, headers=agent)
        assert r.status_code == 201, r.text

    after = await _stats(client, agent)
    room, was = _row(after, f"g:{NABEUL}"), _row(before, f"g:{NABEUL}")
    assert room["entered"] - was["entered"] == 3 and room["with_card"] - was["with_card"] == 1
    assert room["median_with_s"] is not None and room["median_without_s"] is not None
    chest, chest_was = _question(after, "medical", "chest"), _question(before, "medical", "chest")
    assert chest["unknown"] - chest_was["unknown"] == 1 and chest["key"] is True
    medical = next(c for c in after["cards"] if c["category"] == "medical")
    assert set(medical["checks"]) == set(stats.CHECKS) and "cpr" in medical["read"]
    # The national figures stand beside the room's; a regional room cannot ask for another room.
    assert after["national"]["entered"] >= room["entered"]
    other = await _stats(client, agent, room="central")
    assert other["room"] == f"g:{NABEUL}"
    # The national scope sees every room, or one; the cards' readers outside the rooms do not.
    national = await _stats(client, staff(["ops_manager"], gouvernorat=None), room=f"g:{NABEUL}")
    assert national["room"] == f"g:{NABEUL}" and _row(national, f"g:{NABEUL}")["entered"] == room["entered"]
    assert (await client.get(f"{CARDS}/stats", headers=staff(["governor"], gouvernorat=NABEUL))).status_code == 403
    bad = await client.get(f"{CARDS}/stats", headers=agent, params={"room": "everywhere"})
    assert bad.status_code == 422


# ---------------------------------------------------------------- the review of the [SIM] cards (OS2-4)


def _item(review: dict[str, Any], category: str) -> dict[str, Any]:
    return next(i for i in review["items"] if i["category"] == category)


async def _review(client: httpx.AsyncClient, headers: dict[str, str]) -> dict[str, Any]:
    r = await client.get(f"{CARDS}/review", headers=headers)
    assert r.status_code == 200, r.text
    out: dict[str, Any] = r.json()
    return out


async def _reset(client: httpx.AsyncClient, session: AsyncSession, editor: dict[str, str], category: str) -> None:
    """Back to the [SIM] text with no draft, whatever an earlier run of these tests left."""
    for c in await _cards(client, editor):
        if c["category"] == category and c["status"] == "draft":
            await client.delete(f"{CARDS}/{c['id']}", headers=editor)
    await session.execute(
        text("UPDATE reports.call_card SET sim = true WHERE category = :c AND status = 'approved'"), {"c": category}
    )
    await session.commit()


async def test_the_office_reviews_a_card_and_the_manager_approves(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession
) -> None:
    editor = staff(["content_editor"], gouvernorat=None, name="مكتب الوقاية")
    manager = staff(["ops_manager"], gouvernorat=None, name="رئيس العمليات")
    await _reset(client, session, editor, "landslide")
    review = await _review(client, editor)
    assert review["total"] == 9 and _item(review, "landslide")["stage"] == "not_started"

    # Who reviews: named by the Office, never by a regional account.
    who = {"office": "مكتب الوقاية", "doctor": None, "reason": "تعيين المراجع"}
    r = await client.put(
        f"{CARDS}/landslide/reviewers", json=who, headers=staff(["content_editor"], gouvernorat=NABEUL)
    )
    assert r.status_code == 403
    r = await client.put(f"{CARDS}/landslide/reviewers", json=who, headers=editor)
    assert r.status_code == 200 and r.json()["office"] == "مكتب الوقاية"

    # A draft with the Office's notes: only on questions the card has.
    current = _approved(await _cards(client, editor), "landslide")
    content = current["content"]
    content["questions"][0]["help"] = "هل تسمع أصواتا تحت الأنقاض؟"
    qid = content["questions"][0]["id"]
    odd = {"content": content, "reason": "مراجعة", "notes": {"nope": "؟"}}
    r = await client.post(f"{CARDS}/landslide/draft", json=odd, headers=editor)
    assert r.status_code == 422 and r.json()["detail"] == "call_card_note"
    body = {"content": content, "reason": "مراجعة المكتب", "notes": {qid: "توضيح للمتصل", "_card": "مراجعة أولى"}}
    r = await client.post(f"{CARDS}/landslide/draft", json=body, headers=editor)
    assert r.status_code == 201, r.text
    draft = r.json()
    assert draft["notes"][qid] == "توضيح للمتصل" and draft["submitted_at"] is None
    assert _item(await _review(client, editor), "landslide")["stage"] == "office"

    # Sending back what was not handed over is refused; handed over, the manager sends it back with a note.
    back = {"reason": "أضيفوا سؤالا عن الغاز", "updated_at": draft["updated_at"]}
    r = await client.post(f"{CARDS}/{draft['id']}/return", json=back, headers=manager)
    assert r.status_code == 409 and r.json()["detail"] == "call_card_not_submitted"
    r = await client.post(
        f"{CARDS}/{draft['id']}/submit", json={"reason": "للاعتماد", "updated_at": draft["updated_at"]}, headers=editor
    )
    assert r.status_code == 200 and r.json()["submitted_by_name"] == "مكتب الوقاية"
    submitted = r.json()
    assert _item(await _review(client, editor), "landslide")["stage"] == "approval"
    r = await client.post(
        f"{CARDS}/{draft['id']}/return", json={**back, "updated_at": submitted["updated_at"]}, headers=editor
    )
    assert r.status_code == 403
    r = await client.post(
        f"{CARDS}/{draft['id']}/return", json={**back, "updated_at": submitted["updated_at"]}, headers=manager
    )
    assert r.status_code == 200, r.text
    returned = r.json()
    assert returned["returned_reason"] == "أضيفوا سؤالا عن الغاز" and returned["submitted_at"] is None
    assert _item(await _review(client, editor), "landslide")["stage"] == "office"

    # The Office edits and hands it over again: the note it got back is cleared on handing over.
    r = await client.put(
        f"{CARDS}/{draft['id']}",
        json={**body, "reason": "بعد الملاحظة", "updated_at": returned["updated_at"]},
        headers=editor,
    )
    assert r.status_code == 200, r.text
    r = await client.post(
        f"{CARDS}/{draft['id']}/submit",
        json={"reason": "للاعتماد", "updated_at": r.json()["updated_at"]},
        headers=editor,
    )
    assert r.status_code == 200 and r.json()["returned_reason"] is None
    r = await client.post(
        f"{CARDS}/{draft['id']}/approve",
        json={"reason": "اعتماد", "updated_at": r.json()["updated_at"]},
        headers=manager,
    )
    assert r.status_code == 200 and r.json()["sim"] is False
    item = _item(await _review(client, editor), "landslide")
    assert item["stage"] == "done" and item["approved"]["version"] == draft["version"]


async def test_the_office_confirms_a_medical_card_unchanged(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession
) -> None:
    editor = staff(["content_editor"], gouvernorat=None, name="مكتب الوقاية")
    doctor = staff(["medical_coordinator"], gouvernorat=None, name="الطبيب المنسق")
    manager = staff(["ops_manager"], gouvernorat=None, name="رئيس العمليات")
    await _reset(client, session, editor, "medical")
    current = _approved(await _cards(client, editor), "medical")
    r = await client.post(f"{CARDS}/medical/confirm", json={"reason": "النص مطابق"}, headers=editor)
    assert r.status_code == 201, r.text
    draft = r.json()
    assert draft["unchanged"] and draft["sim"] is False and draft["submitted_at"] is not None
    assert draft["content"] == current["content"] and draft["version"] == current["version"] + 1
    again = await client.post(f"{CARDS}/medical/confirm", json={"reason": "النص مطابق"}, headers=editor)
    assert again.status_code == 409 and again.json()["detail"] == "draft_exists"
    # A medical card waits for the doctor, who may send it back; the validation is then withdrawn.
    assert _item(await _review(client, editor), "medical")["stage"] == "doctor"
    r = await client.post(
        f"{CARDS}/{draft['id']}/medical-validation",
        json={"reason": "مطابق للبروتوكول", "updated_at": draft["updated_at"]},
        headers=doctor,
    )
    assert r.status_code == 200
    assert _item(await _review(client, editor), "medical")["stage"] == "approval"
    r = await client.post(
        f"{CARDS}/{draft['id']}/return",
        json={"reason": "راجعوا وضعية الأمان", "updated_at": r.json()["updated_at"]},
        headers=doctor,
    )
    assert r.status_code == 200 and r.json()["medical_validated_at"] is None
    # Cleaning up: the [SIM] card stays the approved one for the other tests.
    assert (await client.delete(f"{CARDS}/{draft['id']}", headers=editor)).status_code == 204
    assert _item(await _review(client, manager), "medical")["stage"] == "not_started"
    # Confirming applies only to the [SIM] text.
    await session.execute(
        text("UPDATE reports.call_card SET sim = false WHERE category = 'medical' AND status = 'approved'")
    )
    await session.commit()
    r = await client.post(f"{CARDS}/medical/confirm", json={"reason": "النص مطابق"}, headers=editor)
    assert r.status_code == 409 and r.json()["detail"] == "call_card_not_sim"
    await _reset(client, session, editor, "medical")
