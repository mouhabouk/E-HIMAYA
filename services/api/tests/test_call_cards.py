"""Guided call-taking cards (OS2, docs/phase-os2/design-os2.md): rules, intake with a card, writing, approving."""

from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.modules.reports import callcards as cc
from app.modules.reports import sla

Staff = Callable[..., dict[str, str]]
NABEUL = 21
IN_NABEUL = {"lat": 36.4513, "lon": 10.7357}
REPORTS = "/api/v1/staff/reports"
CARDS = "/api/v1/staff/call-cards"


async def _cards(client: httpx.AsyncClient, headers: dict[str, str], include: str = "current") -> list[dict[str, Any]]:
    r = await client.get(CARDS, headers=headers, params={"include": include})
    assert r.status_code == 200, r.text
    cards: list[dict[str, Any]] = r.json()["cards"]
    return cards


def _approved(cards: list[dict[str, Any]], category: str) -> dict[str, Any]:
    return next(c for c in cards if c["category"] == category and c["status"] == "approved")


# ---------------------------------------------------------------- the rules (pure)


def _content() -> cc.CardContent:
    return cc.CardContent.model_validate(
        {
            "title": "اختبار",
            "base_band": "normal",
            "base_means": ["إسعاف"],
            "questions": [
                {"id": "a", "text": "أ؟", "key": True, "effects": {"yes": {"why": "أ", "band": "high", "lives": True}}},
                {
                    "id": "b",
                    "text": "ب؟",
                    "key": True,
                    "when": {"question": "a", "answer": "yes"},
                    "effects": {"no": {"why": "ب", "band": "critical", "flag": "توقف", "instruction": "cpr"}},
                },
                {"id": "c", "text": "ج؟", "effects": {"yes": {"why": "ج", "band": "low"}}},
            ],
            "instructions": {"cpr": {"title": "إنعاش", "steps": ["اضغط"], "medical": True, "metronome": 110}},
        }
    )


def test_answers_raise_the_band_and_never_lower_it() -> None:
    content = _content()
    assert cc.evaluate(content, {}).band == "normal"
    # An effect asking for "low" does not lower the card's starting point.
    assert cc.evaluate(content, {"c": "yes"}).band == "normal"
    out = cc.evaluate(content, {"a": "yes", "b": "no"})
    assert out.band == "critical" and out.flags == ["توقف"] and out.instructions == ["cpr"] and out.lives
    assert out.asked == 3 and out.answered == 2


def test_a_follow_up_is_asked_only_after_its_answer() -> None:
    content = _content()
    assert [q.id for q in cc.asked(content, {})] == ["a", "c"]
    assert [q.id for q in cc.asked(content, {"a": "yes"})] == ["a", "b", "c"]
    # The answer to a follow-up no longer shown is dropped; a question the card does not have is refused.
    assert cc.clean_answers(content, {"a": "no", "b": "no"}) == {"a": "no"}
    with pytest.raises(ValueError):
        cc.clean_answers(content, {"z": "yes"})


def test_not_knowing_a_decisive_answer_keeps_the_band_high() -> None:
    out = cc.evaluate(_content(), {"a": "unknown"})
    assert out.band == "high" and any("لا يعرف" in r for r in out.reasons)


def test_content_is_checked() -> None:
    raw = _content().model_dump(mode="json")
    raw["questions"][1]["effects"]["no"]["instruction"] = "missing"
    with pytest.raises(ValueError):
        cc.CardContent.model_validate(raw)
    raw = _content().model_dump(mode="json")
    raw["questions"] = [raw["questions"][1], raw["questions"][0]]  # follow-up before its question
    with pytest.raises(ValueError):
        cc.CardContent.model_validate(raw)


def test_the_claim_band_never_goes_below_the_cards_floor() -> None:
    bands = {"critical": 85, "high": 70, "normal": 40}
    assert sla.band_of(10, "medical", bands) == "low"
    assert sla.band_of(10, "medical", bands, "critical") == "critical"
    assert sla.band_of(90, "medical", bands, "normal") == "critical"


# ---------------------------------------------------------------- the seeded cards and intake


async def test_the_rooms_read_the_nine_seeded_cards(client: httpx.AsyncClient, staff: Staff) -> None:
    cards = await _cards(client, staff(["operator"], gouvernorat=NABEUL))
    approved = {c["category"] for c in cards if c["status"] == "approved"}
    assert approved == {
        "sos",
        "fire",
        "flood",
        "traffic_accident",
        "drowning",
        "landslide",
        "chemical_leak",
        "medical",
        "other",
    }
    medical = _approved(cards, "medical")
    assert medical["medical"] is True and medical["content"]["instructions"]["cpr"]["metronome"] == 110
    # Outside the rooms and the Office the cards are not offered.
    assert (await client.get(CARDS, headers=staff(["governor"], gouvernorat=NABEUL))).status_code == 403


async def test_a_room_enters_a_call_with_its_card(client: httpx.AsyncClient, staff: Staff) -> None:
    agent = staff(["operator"], gouvernorat=NABEUL, name="عون القاعة")
    card = _approved(await _cards(client, agent), "medical")
    body = {
        "category": "medical",
        "location": IN_NABEUL,
        "channel": "phone",
        "text": "الجار يطرق الباب",
        "call_card": {
            "card_id": card["id"],
            "version": card["version"],
            "answers": {"conscious": "yes", "breathing": "no", "child": "no"},
            "read": ["cpr", "bleeding"],
        },
    }
    r = await client.post(REPORTS, json=body, headers=agent)
    assert r.status_code == 201, r.text
    report = r.json()
    # The answers called for "critical": the claim band follows even before the priority does.
    assert report["sla_band"] == "critical"
    lives = next(c for c in report["analysis"]["priority"]["components"] if c["key"] == "lives")
    assert lives["value"] == 1.0 and lives["detail"]["source"] == "call_card"
    answered = await client.get(f"{REPORTS}/{report['id']}/call-card", headers=agent)
    assert answered.status_code == 200, answered.text
    out = answered.json()
    assert out["card_version"] == card["version"] and out["outcome"]["band"] == "critical"
    assert "توقف قلبي محتمل" in out["outcome"]["flags"]
    # Only the instructions the answers offered count as read.
    assert list(out["instructions"]) == ["cpr"]
    text = report["text"] or ""
    assert "بطاقة الاستقبال" in text and "الجار يطرق الباب" in text


async def test_a_report_without_a_card_is_as_before(client: httpx.AsyncClient, staff: Staff) -> None:
    agent = staff(["operator"], gouvernorat=NABEUL)
    r = await client.post(REPORTS, json={"category": "other", "location": IN_NABEUL, "channel": "radio"}, headers=agent)
    assert r.status_code == 201
    assert (await client.get(f"{REPORTS}/{r.json()['id']}/call-card", headers=agent)).status_code == 404


async def test_intake_refuses_a_card_that_does_not_fit(client: httpx.AsyncClient, staff: Staff) -> None:
    agent = staff(["operator"], gouvernorat=NABEUL)
    cards = await _cards(client, agent)
    fire = _approved(cards, "fire")
    base = {"category": "medical", "location": IN_NABEUL, "channel": "phone"}
    wrong = {**base, "call_card": {"card_id": fire["id"], "version": fire["version"], "answers": {}}}
    assert (await client.post(REPORTS, json=wrong, headers=agent)).json()["detail"] == "call_card_category"
    medical = _approved(cards, "medical")
    stale = {**base, "call_card": {"card_id": medical["id"], "version": medical["version"] + 9, "answers": {}}}
    r = await client.post(REPORTS, json=stale, headers=agent)
    assert r.status_code == 409 and r.json()["detail"] == "call_card_changed"
    odd = {**base, "call_card": {"card_id": medical["id"], "version": medical["version"], "answers": {"zz": "yes"}}}
    assert (await client.post(REPORTS, json=odd, headers=agent)).json()["detail"] == "call_card_question"


# ---------------------------------------------------------------- writing and approving


async def test_the_office_writes_validates_and_approves_a_version(client: httpx.AsyncClient, staff: Staff) -> None:
    editor = staff(["content_editor"], gouvernorat=None, name="محرر المحتوى")
    manager = staff(["ops_manager"], gouvernorat=None, name="رئيس القاعة المركزية")
    doctor = staff(["medical_coordinator"], gouvernorat=None, name="الطبيب المنسق")
    # A draft left by an earlier run of this test is discarded first.
    for c in await _cards(client, editor):
        if c["category"] == "drowning" and c["status"] == "draft":
            await client.delete(f"{CARDS}/{c['id']}", headers=editor)
    current = _approved(await _cards(client, editor), "drowning")
    content = current["content"]
    content["questions"][2]["text"] = "هل الشاطئ محروس الآن؟"

    # Regional accounts and the rooms' agents do not write cards.
    for who in (staff(["content_editor"], gouvernorat=NABEUL), staff(["operator"], gouvernorat=None)):
        r = await client.post(f"{CARDS}/drowning/draft", json={"content": content, "reason": "تعديل"}, headers=who)
        assert r.status_code == 403
    r = await client.post(
        f"{CARDS}/drowning/draft", json={"content": content, "reason": "تعديل السؤال 3"}, headers=editor
    )
    assert r.status_code == 201, r.text
    draft = r.json()
    assert draft["status"] == "draft" and draft["version"] == current["version"] + 1 and draft["sim"] is False
    again = await client.post(
        f"{CARDS}/drowning/draft", json={"content": content, "reason": "مرة ثانية"}, headers=editor
    )
    assert again.status_code == 409 and again.json()["detail"] == "draft_exists"

    # A medical card needs its medical validation first.
    approve = {"reason": "اعتماد بعد الاجتماع", "updated_at": draft["updated_at"]}
    r = await client.post(f"{CARDS}/{draft['id']}/approve", json=approve, headers=manager)
    assert r.status_code == 409 and r.json()["detail"] == "medical_validation_required"
    r = await client.post(
        f"{CARDS}/{draft['id']}/medical-validation",
        json={"reason": "صادق عليها د. فلان", "updated_at": draft["updated_at"]},
        headers=doctor,
    )
    assert r.status_code == 200 and r.json()["medical_validated_by"] == "الطبيب المنسق"
    validated = r.json()
    # Editing the draft withdraws the validation: the text changed.
    content["questions"][2]["help"] = "اسأل عن العلم"
    r = await client.put(
        f"{CARDS}/{draft['id']}",
        json={"content": content, "reason": "إضافة توضيح", "updated_at": validated["updated_at"]},
        headers=editor,
    )
    assert r.status_code == 200 and r.json()["medical_validated_at"] is None
    edited = r.json()
    r = await client.post(
        f"{CARDS}/{draft['id']}/medical-validation",
        json={"reason": "صادق عليها د. فلان", "updated_at": edited["updated_at"]},
        headers=doctor,
    )
    validated = r.json()
    # Only a national room manager approves.
    stale = {"reason": "اعتماد", "updated_at": edited["updated_at"]}
    assert (await client.post(f"{CARDS}/{draft['id']}/approve", json=stale, headers=manager)).status_code == 409
    ok = {"reason": "اعتماد بعد الاجتماع", "updated_at": validated["updated_at"]}
    assert (await client.post(f"{CARDS}/{draft['id']}/approve", json=ok, headers=editor)).status_code == 403
    r = await client.post(f"{CARDS}/{draft['id']}/approve", json=ok, headers=manager)
    assert r.status_code == 200 and r.json()["status"] == "approved"

    history = [c for c in await _cards(client, editor, include="all") if c["category"] == "drowning"]
    by_version = {c["version"]: c["status"] for c in history}
    assert by_version[current["version"]] == "retired" and by_version[draft["version"]] == "approved"
    # A call taken on the retired version is refused: the room reloads the card.
    agent = staff(["operator"], gouvernorat=NABEUL)
    old = {"card_id": current["id"], "version": current["version"], "answers": {}}
    r = await client.post(
        REPORTS,
        json={"category": "drowning", "location": IN_NABEUL, "channel": "phone", "call_card": old},
        headers=agent,
    )
    assert r.status_code == 409 and r.json()["detail"] == "call_card_changed"
