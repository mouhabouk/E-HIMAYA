"""Register of plans, decisions and instructions (phase L3b, docs/phase-l/design-l3b.md): recording central and
regional documents in scope, the advanced search (words, kind, level, gouvernorat, topic, issuer, period, in force on
a day) with its facets, drafts, versions and revisions, repeal and links, the attached file, key recommendations,
expiry by the worker, who reads which access level, the signed directives of a crisis axis recorded automatically,
the plan of an axis, and the library."""

import base64
import hashlib
import secrets
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_system_sessionmaker
from app.core.security import Principal, Realm
from app.modules.knowledge import indexer
from app.modules.register import domain, service
from tests.conftest import FakeStore, outbox_events

Staff = Callable[..., dict[str, str]]
URL = "/api/v1/staff/register"
CRISIS = "/api/v1/staff/crisis"
NABEUL, SOUSSE = 21, 51
TEST_KEY = base64.b64encode(hashlib.sha256(b"e-himaya register test key").digest()).decode()
AREA = {
    "type": "Polygon",
    "coordinates": [[[10.60, 36.35], [10.85, 36.35], [10.85, 36.55], [10.60, 36.55], [10.60, 36.35]]],
}
PDF = b"%PDF-1.7\n1 0 obj << >> endobj\n%%EOF\n"


@pytest.fixture(autouse=True)
def _key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "evidence_signing_key", SecretStr(TEST_KEY))


def central(staff: Staff) -> dict[str, str]:
    return staff(["central_committee"], gouvernorat=None)


def room(staff: Staff, code: int = NABEUL) -> dict[str, str]:
    return staff(["ops_manager"], gouvernorat=code)


def word() -> str:
    """A word of its own for one test, so a search on a reused database finds this test's documents only."""
    return "zq" + "".join(secrets.choice("bcdfghjklmnpqrstvwxz") for _ in range(10))


def doc_body(title: str, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "reference": "قرار اللجنة الجهوية بولاية نابل عدد 27 لسنة 2026",
        "kind": "plan",
        "level": "regional",
        "gouvernorat_code": NABEUL,
        "issuer": "اللجنة الجهوية بنابل",
        "signatory": "[SIM] اللجنة الجهوية",
        "title": title,
        "summary": "المخطط الجهوي للنجدة عند الفيضانات وتوزيع المهام على المتدخلين",
        "topics": ["floods", "civil_protection"],
        "issued_on": "2026-03-10",
        "effective_from": "2026-03-15",
    }
    body.update(overrides)
    return body


async def create(client: httpx.AsyncClient, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
    r = await client.post(f"{URL}/documents", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["document"]  # type: ignore[no-any-return]


async def find(client: httpx.AsyncClient, headers: dict[str, str], **params: Any) -> dict[str, Any]:
    r = await client.get(f"{URL}/documents", params=params, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()  # type: ignore[no-any-return]


def numbers(body: dict[str, Any]) -> set[str]:
    return {d["number"] for d in body["items"]}


# --- Pure rules -----------------------------------------------------------------------------------------------------


def test_rules() -> None:
    def p(roles: set[str], code: int | None) -> Principal:
        return Principal(subject="s", realm=Realm.STAFF, roles=frozenset(roles), gouvernorat_code=code, claims={})  # type: ignore[arg-type]

    national, regional = p({"central_committee"}, None), p({"ops_manager"}, NABEUL)
    assert domain.can_write(national, "central", None) and domain.can_write(national, "regional", SOUSSE)
    assert domain.can_write(regional, "regional", NABEUL)
    assert not domain.can_write(regional, "central", None) and not domain.can_write(regional, "regional", SOUSSE)
    assert not domain.can_write(p({"governor"}, NABEUL), "regional", NABEUL)
    assert not domain.writes(p({"operator"}, NABEUL)) and domain.reads(p({"operator"}, NABEUL))

    def reads(pr: Principal, access: str, code: int | None = NABEUL, status: str = "in_force") -> bool:
        return domain.can_read(pr, access=access, gouvernorat_code=code, status=status, created_by="x", actor="y")

    operator, gov, minister = p({"operator"}, NABEUL), p({"governor"}, NABEUL), p({"minister"}, None)
    assert reads(operator, "all") and reads(operator, "gouvernorat") and not reads(operator, "command")
    assert not reads(operator, "all", SOUSSE) and reads(operator, "all", None)
    assert reads(gov, "command") and not reads(gov, "restricted") and reads(minister, "restricted", SOUSSE)
    assert not reads(operator, "all", status="draft") and reads(regional, "all", status="draft")

    d = date(2026, 6, 1)
    assert domain.status_on("in_force", date(2026, 5, 31), d) == "expired"
    assert domain.status_on("in_force", d, d) == "in_force" and domain.status_on("repealed", None, d) == "repealed"
    assert domain.in_force_on(None, None, date(2026, 1, 1), d) and not domain.in_force_on(date(2026, 7, 1), None, d, d)
    assert domain.file_type(PDF, None) == "application/pdf"
    assert domain.file_type(b"\xff\xd8\xff\xe0", "image/jpeg") == "image/jpeg"
    assert domain.file_type(b"MZ\x90\x00", "application/pdf") is None


# --- Recording and scope --------------------------------------------------------------------------------------------


async def test_create_in_scope_and_validation(client: httpx.AsyncClient, staff: Staff) -> None:
    w = word()
    regional = await create(client, room(staff), doc_body(f"مخطط النجدة {w}"))
    assert regional["number"].startswith("REG-2026-") and regional["status"] == "in_force"
    assert regional["gouvernorat_name"] and regional["can_edit"] and regional["level"] == "regional"

    # A regional room records neither central documents nor those of another gouvernorat.
    r = await client.post(
        f"{URL}/documents", json=doc_body(w, level="central", gouvernorat_code=None), headers=room(staff)
    )
    assert r.status_code == 403 and r.json()["detail"] == "out_of_scope"
    r = await client.post(f"{URL}/documents", json=doc_body(w, gouvernorat_code=SOUSSE), headers=room(staff))
    assert r.status_code == 403
    # Operators, governors and the minister read but do not record.
    for headers in (staff(["operator"], gouvernorat=NABEUL), staff(["governor"], gouvernorat=NABEUL)):
        assert (await client.post(f"{URL}/documents", json=doc_body(w), headers=headers)).status_code == 403

    # Level and gouvernorat agree; a temporary instruction has an end; the end is not before the start.
    cases = {
        "central_without_gouvernorat": doc_body(w, level="central"),
        "gouvernorat_required": doc_body(w, gouvernorat_code=None),
        "end_date_required": doc_body(w, kind="temporary_instruction"),
        "dates_out_of_order": doc_body(w, effective_to="2026-03-01"),
    }
    for detail, body in cases.items():
        r = await client.post(f"{URL}/documents", json=body, headers=central(staff))
        assert r.status_code == 422 and r.json()["detail"] == detail, (detail, r.text)

    # The central committee records central documents; a temporary instruction already past its end is expired.
    temp = await create(
        client,
        central(staff),
        doc_body(
            f"تعليمات وقتية {w}",
            kind="temporary_instruction",
            level="central",
            gouvernorat_code=None,
            issuer="وزارة الداخلية",
            effective_to="2026-04-30",
        ),
    )
    assert temp["status"] == "expired" and temp["level"] == "central"

    # The room of Sousse does not see the Nabeul document (404, not 403); a governor of Nabeul does.
    other = room(staff, SOUSSE)
    assert (await client.get(f"{URL}/documents/{regional['id']}", headers=other)).status_code == 404
    assert (await client.get(f"{URL}/documents/{temp['id']}", headers=other)).status_code == 200
    seen = await client.get(f"{URL}/documents/{regional['id']}", headers=staff(["governor"], gouvernorat=NABEUL))
    assert seen.status_code == 200 and not seen.json()["document"]["can_edit"]
    assert numbers(await find(client, other, q=w)) == {temp["number"]}


async def test_advanced_search_filters_and_facets(client: httpx.AsyncClient, staff: Staff) -> None:
    w = word()
    h = central(staff)
    plan = await create(client, h, doc_body(f"مخطط الفيضانات {w}", summary=f"توزيع المهام عند فيضان {w}"))
    memo = await create(
        client,
        h,
        doc_body(
            f"مذكرة الشواطئ {w}",
            kind="memo",
            level="central",
            gouvernorat_code=None,
            issuer="الإدارة العامة للحماية المدنية",
            topics=["beaches"],
            issued_on="2025-06-01",
            effective_from=None,
            effective_to="2025-09-30",
        ),
    )
    sousse = await create(
        client, h, doc_body(f"تعليمات دائمة {w}", kind="standing_instruction", gouvernorat_code=SOUSSE, topics=[])
    )
    draft = await create(client, h, doc_body(f"مسودة {w}", publish=False))
    assert draft["status"] == "draft" and memo["status"] == "expired"

    everything = await find(client, h, q=w)
    assert numbers(everything) == {plan["number"], memo["number"], sousse["number"], draft["number"]}
    assert everything["can_create"] and everything["can_create_central"]
    excerpts = {d["number"]: d["excerpt"] or "" for d in everything["items"]}
    assert f"<mark>{w}</mark>" in excerpts[plan["number"]]
    # Words are matched by their start, across the reference and the summary too.
    assert plan["number"] in numbers(await find(client, h, q=f"{w[:8]} نابل"))

    assert numbers(await find(client, h, q=w, kind="memo")) == {memo["number"]}
    assert numbers(await find(client, h, q=w, kind="memo,standing_instruction")) == {memo["number"], sousse["number"]}
    bad = await client.get(f"{URL}/documents", params={"kind": "plan,poem"}, headers=h)
    assert bad.status_code == 422 and bad.json()["detail"] == "invalid_kind"
    assert numbers(await find(client, h, q=w, level="regional", gouvernorat=SOUSSE)) == {sousse["number"]}
    assert numbers(await find(client, h, q=w, topic="beaches")) == {memo["number"]}
    assert numbers(await find(client, h, q=w, issuer="الإدارة العامة")) == {memo["number"]}
    assert numbers(await find(client, h, q=w, status="in_force,draft")) == {
        plan["number"],
        sousse["number"],
        draft["number"],
    }
    # Period: issued in 2025; effective from 15 March 2026 onwards.
    assert numbers(await find(client, h, q=w, **{"from": "2025-01-01", "to": "2025-12-31"})) == {memo["number"]}
    effective = await find(client, h, q=w, date_field="effective", **{"from": "2026-03-12"})
    assert memo["number"] not in numbers(effective) and plan["number"] in numbers(effective)
    # In force on a day: the beach memo was in force in summer 2025, the plan was not yet.
    assert numbers(await find(client, h, q=w, in_force_on="2025-07-01")) == {memo["number"]}
    assert numbers(await find(client, h, q=w, in_force_on="2026-04-01")) == {plan["number"], sousse["number"]}
    assert numbers(await find(client, h, q=w, has_file="true")) == set()
    oldest = await find(client, h, q=w, sort="oldest")
    assert oldest["items"][0]["number"] == memo["number"]

    # Facets count every value of a field under the other filters.
    faceted = await find(client, h, q=w, kind="memo")
    kinds = {f["key"]: f["count"] for f in faceted["facets"]["kind"]}
    assert kinds == {"plan": 2, "memo": 1, "standing_instruction": 1} and faceted["total"] == 1
    assert {f["key"]: f["count"] for f in faceted["facets"]["status"]} == {"expired": 1}

    # Drafts stay with those who may write them; a regional room sees no central draft of another scope.
    assert draft["number"] not in numbers(await find(client, staff(["operator"], gouvernorat=NABEUL), q=w))
    assert draft["number"] in numbers(await find(client, room(staff), q=w))
    assert sousse["number"] not in numbers(await find(client, room(staff), q=w))
    operator = await find(client, staff(["operator"], gouvernorat=NABEUL), q=w)
    assert not operator["can_create"] and not operator["can_create_central"]


async def test_access_levels(client: httpx.AsyncClient, staff: Staff) -> None:
    w = word()
    h = central(staff)
    made = {
        access: await create(
            client, h, doc_body(f"{access} {w}", level="central", gouvernorat_code=None, access=access)
        )
        for access in ("all", "command", "restricted")
    }
    expected = {
        "operator": {"all"},
        "governor": {"all", "command"},
        "minister": {"all", "command", "restricted"},
        "central_committee": {"all", "command", "restricted"},  # its own restricted document
    }
    heads = {
        "operator": staff(["operator"], gouvernorat=NABEUL),
        "governor": staff(["governor"], gouvernorat=NABEUL),
        "minister": staff(["minister"], gouvernorat=None),
        "central_committee": h,
    }
    for who, levels in expected.items():
        assert numbers(await find(client, heads[who], q=w)) == {made[a]["number"] for a in levels}, who
    restricted = made["restricted"]["id"]
    assert (await client.get(f"{URL}/documents/{restricted}", headers=heads["governor"])).status_code == 404
    other = staff(["central_committee"], gouvernorat=None)
    assert (await client.get(f"{URL}/documents/{restricted}", headers=other)).status_code == 404


# --- Life of a document ---------------------------------------------------------------------------------------------


async def test_draft_versions_links_and_repeal(client: httpx.AsyncClient, staff: Staff) -> None:
    w = word()
    h = room(staff)
    old = await create(client, h, doc_body(f"المخطط القديم {w}"))
    draft = await create(client, h, doc_body(f"المخطط الجديد {w}", publish=False))
    patch = {**doc_body(f"المخطط الجديد المنقح {w}"), "version": 1, "reason": "إدراج ملاحظات اللجنة", "publish": True}
    r = await client.patch(f"{URL}/documents/{draft['id']}", json=patch, headers=h)
    assert r.status_code == 200, r.text
    new = r.json()["document"]
    assert new["status"] == "in_force" and new["version"] == 2 and new["title"].endswith("المنقح " + w)
    stale = await client.patch(f"{URL}/documents/{draft['id']}", json=patch, headers=h)
    assert stale.status_code == 409 and stale.json()["detail"] == "version_conflict"
    # Another gouvernorat's room cannot edit, nor can the governor.
    assert (
        await client.patch(f"{URL}/documents/{draft['id']}", json={**patch, "version": 2}, headers=room(staff, SOUSSE))
    ).status_code == 404
    assert (
        await client.patch(
            f"{URL}/documents/{draft['id']}",
            json={**patch, "version": 2},
            headers=staff(["governor"], gouvernorat=NABEUL),
        )
    ).status_code == 403

    # A complement link shows on both sides; the new plan repeals the old one, and that cannot be undone by unlinking.
    other = await create(client, h, doc_body(f"ملحق {w}", kind="other"))
    r = await client.post(
        f"{URL}/documents/{new['id']}/links", json={"to_id": other["id"], "relation": "complements"}, headers=h
    )
    assert r.status_code == 200 and r.json()["links"][0]["direction"] == "out"
    back = (await client.get(f"{URL}/documents/{other['id']}", headers=h)).json()
    assert back["links"][0]["direction"] == "in" and back["links"][0]["relation"] == "complements"
    r = await client.post(
        f"{URL}/documents/{new['id']}/links", json={"to_id": old["id"], "relation": "repeals"}, headers=h
    )
    assert r.status_code == 200, r.text
    repealed = (await client.get(f"{URL}/documents/{old['id']}", headers=h)).json()["document"]
    assert repealed["status"] == "repealed" and repealed["repealed_by"] == new["id"] and not repealed["can_edit"]
    assert new["number"] in (repealed["repeal_reason"] or "")
    r = await client.delete(f"{URL}/documents/{new['id']}/links/{old['id']}", headers=h)
    assert r.status_code == 409 and r.json()["detail"] == "repeal_is_final"
    assert (await client.delete(f"{URL}/documents/{new['id']}/links/{other['id']}", headers=h)).status_code == 204
    r = await client.post(f"{URL}/documents/{old['id']}/repeal", json={"reason": "مرة ثانية للتجربة"}, headers=h)
    assert r.status_code == 409 and r.json()["detail"] == "document_repealed"

    # Repealing directly, with a reason; deleting is for drafts only.
    r = await client.post(f"{URL}/documents/{other['id']}/repeal", json={"reason": "انتهى العمل بالملحق"}, headers=h)
    assert r.status_code == 200 and r.json()["document"]["status"] == "repealed"
    assert (await client.delete(f"{URL}/documents/{new['id']}", headers=h)).status_code == 409
    scrap = await create(client, h, doc_body(f"مسودة للحذف {w}", publish=False))
    assert (await client.delete(f"{URL}/documents/{scrap['id']}", headers=h)).status_code == 204
    assert (await client.get(f"{URL}/documents/{scrap['id']}", headers=h)).status_code == 404

    revisions = (await client.get(f"{URL}/documents/{old['id']}/revisions", headers=h)).json()
    assert [r["change"] for r in revisions] == ["repealed", "created"]
    revisions = (await client.get(f"{URL}/documents/{draft['id']}/revisions", headers=h)).json()
    assert revisions[0]["reason"] == "إدراج ملاحظات اللجنة" and revisions[0]["snapshot"]["status"] == "in_force"
    # The repealed plan is still found, and "in force today" leaves it out.
    found = await find(client, h, q=w, in_force_on=date.today().isoformat())
    assert old["number"] not in numbers(found) and new["number"] in numbers(found)


async def test_file_and_recommendations(client: httpx.AsyncClient, staff: Staff, fake_store: FakeStore) -> None:
    w = word()
    h = room(staff)
    doc = await create(client, h, doc_body(f"مذكرة {w}", kind="memo"))
    url = f"{URL}/documents/{doc['id']}/file"
    r = await client.put(url, params={"file_name": "x.exe"}, content=b"MZ\x90\x00", headers=h)
    assert r.status_code == 415 and r.json()["detail"] == "file_type_not_allowed"
    assert (await client.put(url, params={"file_name": "e.pdf"}, content=b"", headers=h)).status_code == 422
    assert (
        await client.put(url, params={"file_name": "m.pdf"}, content=PDF, headers=room(staff, SOUSSE))
    ).status_code == 404
    r = await client.put(url, params={"file_name": "مذكرة.pdf"}, content=PDF, headers=h)
    assert r.status_code == 200, r.text
    first = r.json()["document"]
    assert first["file_type"] == "application/pdf" and first["file_sha256"] == hashlib.sha256(PDF).hexdigest()
    first_key = next(k for k in fake_store.objects if k.startswith(f"register/{doc['id']}/"))
    # A new file replaces the old one in the store.
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 16
    r = await client.put(url, params={"file_name": "map.png"}, content=png, headers=h, timeout=10)
    assert r.json()["document"]["file_type"] == "image/png" and first_key in fake_store.deleted
    reader = staff(["operator"], gouvernorat=NABEUL)
    r = await client.get(url, headers=reader)
    assert r.status_code == 200 and r.json()["url"].startswith("http://s3.test/register/")
    assert numbers(await find(client, reader, q=w, has_file="true")) == {doc["number"]}

    # Key recommendations, numbered; dropping one needs a reason; overdue ones are flagged.
    past = (date.today() - timedelta(days=2)).isoformat()
    rec_url = f"{URL}/documents/{doc['id']}/recommendations"
    r = await client.post(
        rec_url, json={"body": "تجهيز مراكز الإيواء", "responsible": "المعتمد", "due_on": past}, headers=h
    )
    assert r.status_code == 200, r.text
    r = await client.post(rec_url, json={"body": "تنظيف مجاري الأودية"}, headers=h)
    recs = r.json()["recommendations"]
    assert [x["number"] for x in recs] == [1, 2] and recs[0]["overdue"] and not recs[1]["overdue"]
    assert r.json()["document"]["recommendations_open"] == 2
    assert (await client.post(rec_url, json={"body": "توصية من القارئ"}, headers=reader)).status_code == 403
    status_url = f"{URL}/recommendations/{recs[1]['id']}/status"
    r = await client.post(status_url, json={"status": "dropped"}, headers=h)
    assert r.status_code == 422 and r.json()["detail"] == "reason_required"
    r = await client.post(status_url, json={"status": "dropped", "reason": "أنجزتها البلدية"}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "dropped"
    r = await client.post(f"{URL}/recommendations/{recs[0]['id']}/status", json={"status": "done"}, headers=h)
    assert not r.json()["overdue"]
    detail = (await client.get(f"{URL}/documents/{doc['id']}", headers=reader)).json()
    assert detail["document"]["recommendations"] == 2 and detail["document"]["recommendations_open"] == 0


async def test_worker_expires_documents(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    w = word()
    end = (date.today() + timedelta(days=3)).isoformat()
    doc = await create(
        client, room(staff), doc_body(f"منع السباحة {w}", kind="temporary_instruction", effective_to=end)
    )
    assert doc["status"] == "in_force"
    await session.execute(
        text("UPDATE register.document SET effective_from = NULL, effective_to = current_date - 1 WHERE id = :id"),
        {"id": doc["id"]},
    )
    await session.commit()
    async with get_system_sessionmaker()() as s, s.begin():
        assert await service.tick(s) >= 1
    after = (await client.get(f"{URL}/documents/{doc['id']}", headers=room(staff))).json()["document"]
    assert after["status"] == "expired"
    action = await session.scalar(
        text("SELECT action FROM audit.log WHERE target = :t ORDER BY id DESC LIMIT 1"), {"t": doc["id"]}
    )
    assert action == "register.document_expired"


# --- Crisis axes and the library ------------------------------------------------------------------------------------


async def test_axis_directives_recorded_and_plan(client: httpx.AsyncClient, staff: Staff) -> None:
    w = word()
    axis = (
        await client.post(
            f"{CRISIS}/axes",
            json={"name": f"فيضانات نابل {w}", "kind": "flood", "level": 3, "gouvernorat_code": NABEUL, "area": AREA},
            headers=staff(["ops_manager"], gouvernorat=None),
        )
    ).json()
    body = {"kind": "decision", "category": "evacuation", "body": f"إخلاء حي الوفاء فورا {w}", "executor": "regional"}
    first = await client.post(
        f"{CRISIS}/axes/{axis['id']}/directives", json=body, headers=staff(["governor"], gouvernorat=NABEUL)
    )
    assert first.status_code == 201, first.text
    second = await client.post(
        f"{CRISIS}/axes/{axis['id']}/directives",
        json={**body, "body": f"إخلاء الأحياء المنخفضة كلها {w}"},
        headers=staff(["minister"], gouvernorat=None),
    )
    assert second.status_code == 201, second.text

    # Both are in the register, signed and for the command; the governor's is repealed by the minister's.
    minister = staff(["minister"], gouvernorat=None)
    found = await find(client, minister, axis=axis["id"])
    by_level = {d["level"]: d for d in found["items"]}
    gov_doc, min_doc = by_level["regional"], by_level["central"]
    assert gov_doc["source"] == min_doc["source"] == "axis" and gov_doc["signed"] and min_doc["signed"]
    assert gov_doc["access"] == "command" and gov_doc["kind"] == "decision" and "floods" in gov_doc["topics"]
    assert gov_doc["status"] == "repealed" and gov_doc["repealed_by"] == min_doc["id"]
    assert min_doc["issuer"] == "اللجنة الوطنية" and min_doc["status"] == "in_force" and not min_doc["can_edit"]
    # An operator does not see the command's documents; documents of an axis are not edited in the register.
    assert numbers(await find(client, staff(["operator"], gouvernorat=NABEUL), axis=axis["id"])) == set()
    commander = staff(["central_committee"], gouvernorat=None)
    r = await client.post(
        f"{URL}/documents/{min_doc['id']}/repeal", json={"reason": "تجربة الإلغاء"}, headers=commander
    )
    assert r.status_code == 403

    # The axis lists them; its plan is a plan of the register in force.
    h = room(staff)
    detail = (await client.get(f"{CRISIS}/axes/{axis['id']}", headers=h)).json()
    assert {d["id"] for d in detail["documents"]} == {gov_doc["id"], min_doc["id"]}
    memo = await create(client, h, doc_body(f"مذكرة {w}", kind="memo"))
    plan = await create(client, h, doc_body(f"المخطط الجهوي للنجدة {w}"))
    version = detail["axis"]["version"]
    r = await client.patch(
        f"{CRISIS}/axes/{axis['id']}", json={"version": version, "plan_document_id": memo["id"]}, headers=h
    )
    assert r.status_code == 409 and r.json()["detail"] == "not_a_plan_in_force"
    r = await client.patch(
        f"{CRISIS}/axes/{axis['id']}", json={"version": version, "plan_document_id": plan["id"]}, headers=h
    )
    assert r.status_code == 200, r.text
    assert r.json()["plan_document"]["number"] == plan["number"]
    r = await client.patch(
        f"{CRISIS}/axes/{axis['id']}", json={"version": r.json()["version"], "clear_plan_document": True}, headers=h
    )
    assert r.status_code == 200 and r.json()["plan_document"] is None
    # A plan of another gouvernorat is not disclosed.
    sousse = await create(client, central(staff), doc_body(f"مخطط سوسة {w}", gouvernorat_code=SOUSSE))
    r = await client.patch(
        f"{CRISIS}/axes/{axis['id']}",
        json={"version": r.json()["version"], "plan_document_id": sousse["id"]},
        headers=h,
    )
    assert r.status_code == 404


async def test_library_lists_open_documents(client: httpx.AsyncClient, staff: Staff) -> None:
    w = word()
    h = room(staff)
    shared = await create(client, h, doc_body(f"مخطط مفتوح {w}"))
    await create(client, h, doc_body(f"مخطط للقيادة {w}", access="command"))
    await create(client, h, doc_body(f"مسودة مخطط {w}", publish=False))
    sessionmaker = get_system_sessionmaker()
    async with sessionmaker() as s, s.begin():
        while await indexer.sweep(s, settle=timedelta(0)):
            pass
    await indexer.cycle(sessionmaker, sweep_now=False, prune_now=False, embed=False)

    def search(headers: dict[str, str]) -> Any:
        return client.get("/api/v1/staff/library/search", params={"q": w, "kinds": "register"}, headers=headers)

    hits = (await search(staff(["operator"], gouvernorat=NABEUL))).json()["items"]
    assert [x["id"] for x in hits] == [shared["id"]] and hits[0]["kind"] == "register"
    assert hits[0]["category"] in ("plan", "floods", "civil_protection")
    assert (await search(staff(["operator"], gouvernorat=SOUSSE))).json()["items"] == []
    item = await client.get(f"/api/v1/staff/library/items/register/{shared['id']}", headers=h)
    assert item.status_code == 200, item.text
    assert item.json()["fields"]["document_id"] == shared["id"]


# --- Directives and notices between the centre and the gouvernorats (design §8) -----------------------------------

DOCX = b"PK\x03\x04" + b"\x14\x00" * 20
XLS = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 32


def test_attachment_types() -> None:
    assert domain.attachment_type(PDF, "x.bin") == ("application/pdf", ".pdf")
    assert domain.attachment_type(DOCX, "تقرير.docx")[0].endswith("wordprocessingml.document")  # type: ignore[index]
    assert domain.attachment_type(DOCX, "جدول.XLSX")[0].endswith("spreadsheetml.sheet")  # type: ignore[index]
    assert domain.attachment_type(XLS, "old.xls") == ("application/vnd.ms-excel", ".xls")
    assert domain.attachment_type("ولاية,عدد\nنابل,3\n".encode(), "a.csv") == ("text/csv", ".csv")
    # An archive or a program renamed is refused.
    assert domain.attachment_type(DOCX, "x.zip") is None
    assert domain.attachment_type(b"MZ\x90\x00", "x.docx") is None
    assert domain.attachment_type(b"\xff\xfe\x00bad", "x.txt") is None


async def test_directive_to_one_gouvernorat_and_threads(
    client: httpx.AsyncClient, staff: Staff, fake_store: FakeStore
) -> None:
    w = word()
    centre = staff(["ops_manager"], gouvernorat=None)
    nabeul, sousse = room(staff), room(staff, SOUSSE)
    D = f"{URL}/dispatches"
    # Only the centre directs; a regional room cannot.
    body = {"kind": "directive", "audience": "targeted", "gouvernorats": [NABEUL], "subject": f"تأمين السدود {w}"}
    assert (await client.post(D, json=body, headers=nabeul)).status_code == 403
    assert (await client.post(D, json={**body, "gouvernorats": []}, headers=centre)).status_code == 422
    r = await client.post(
        D, json={**body, "body": "تقرير عن منسوب السدود قبل الساعة 18", "urgency": "urgent"}, headers=centre
    )
    assert r.status_code == 201, r.text
    directive = r.json()["dispatch"]
    assert directive["number"].startswith("DIR-") and directive["targets"] == 1 and not directive["unread"]
    did = directive["id"]
    # The author attaches a Word file; a CSV renamed .exe is refused.
    r = await client.put(f"{D}/{did}/attachments", params={"file_name": "تعليمات.docx"}, content=DOCX, headers=centre)
    assert r.status_code == 200, r.text
    r = await client.put(f"{D}/{did}/attachments", params={"file_name": "x.exe"}, content=b"MZ\x90", headers=centre)
    assert r.status_code == 415

    # A private directive: Sousse neither lists nor opens it.
    assert w not in str((await client.get(D, params={"q": w}, headers=sousse)).json())
    assert (await client.get(f"{D}/{did}", headers=sousse)).status_code == 404
    inbox = (await client.get(D, params={"box": "inbox", "q": w}, headers=nabeul)).json()
    assert [x["id"] for x in inbox["items"]] == [did] and inbox["items"][0]["unread"] and inbox["can_notify"]
    # Opening marks it seen; Nabeul replies with an Excel file.
    opened = (await client.get(f"{D}/{did}", headers=nabeul)).json()
    assert opened["dispatch"]["seen"] == 1 and len(opened["attachments"]) == 1 and opened["can_reply"]
    r = await client.post(f"{D}/{did}/replies", json={"body": "منسوب سد المصري 82%"}, headers=nabeul)
    assert r.status_code == 200, r.text
    rid = r.json()["reply_id"]
    r = await client.put(
        f"{D}/{did}/attachments", params={"file_name": "منسوب.xls", "reply_id": rid}, content=XLS, headers=nabeul
    )
    assert r.status_code == 200, r.text
    # The centre sees the thread of Nabeul, replied, and answers in it.
    seen = (await client.get(f"{D}/{did}", headers=centre)).json()
    assert seen["targets"][0]["replied_at"] and seen["targets"][0]["seen_at"]
    thread = seen["threads"][0]
    assert thread["gouvernorat_code"] == NABEUL and thread["replies"][0]["attachments"][0]["file_name"] == "منسوب.xls"
    assert (await client.post(f"{D}/{did}/replies", json={"body": "شكرا"}, headers=centre)).status_code == 422
    r = await client.post(
        f"{D}/{did}/replies", json={"body": "واصلوا المتابعة", "gouvernorat_code": NABEUL}, headers=centre
    )
    assert r.status_code == 200
    # The governor of Nabeul reads, does not reply; another room's attachment cannot be fetched by Sousse.
    gov = (await client.get(f"{D}/{did}", headers=staff(["governor"], gouvernorat=NABEUL))).json()
    assert len(gov["threads"][0]["replies"]) == 2 and not gov["can_reply"]
    file_id = thread["replies"][0]["attachments"][0]["id"]
    assert (await client.get(f"{URL}/attachments/{file_id}", headers=sousse)).status_code == 404
    url = (await client.get(f"{URL}/attachments/{file_id}", headers=nabeul)).json()["url"]
    assert url.startswith("http://s3.test/register/dispatch/")
    # Closing stops replies.
    assert (await client.post(f"{D}/{did}/close", headers=nabeul)).status_code == 403
    assert (await client.post(f"{D}/{did}/close", headers=centre)).json()["dispatch"]["status"] == "closed"
    assert (await client.post(f"{D}/{did}/replies", json={"body": "رد متأخر"}, headers=nabeul)).status_code == 409


async def test_general_directive_keeps_each_thread_private(client: httpx.AsyncClient, staff: Staff) -> None:
    w = word()
    centre = staff(["central_committee"], gouvernorat=None)
    D = f"{URL}/dispatches"
    due = "2099-01-01T12:00:00+01:00"
    r = await client.post(
        D, json={"kind": "directive", "subject": f"جرد وسائل الضخ {w}", "reply_due_at": due}, headers=centre
    )
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["dispatch"]["audience"] == "all" and d["dispatch"]["targets"] == 24
    did = d["dispatch"]["id"]
    for code, text_ in ((NABEUL, "نابل: 12 مضخة"), (SOUSSE, "سوسة: 7 مضخات")):
        r = await client.post(f"{D}/{did}/replies", json={"body": text_}, headers=room(staff, code))
        assert r.status_code == 200, r.text
    # Each gouvernorat sees the directive and only its own thread; the centre sees both, replied 2 of 24.
    nabeul = (await client.get(f"{D}/{did}", headers=room(staff))).json()
    assert [t["gouvernorat_code"] for t in nabeul["threads"]] == [NABEUL]
    assert "سوسة" not in str(nabeul["threads"]) and nabeul["dispatch"]["targets"] == 1
    whole = (await client.get(f"{D}/{did}", headers=centre)).json()
    assert {t["gouvernorat_code"] for t in whole["threads"]} == {NABEUL, SOUSSE}
    assert whole["dispatch"]["replied"] == 2 and len(whole["targets"]) == 24
    listed = (await client.get(D, params={"q": w, "box": "sent"}, headers=centre)).json()
    assert listed["items"][0]["replied"] == 2 and listed["can_direct"]


async def test_notice_from_a_room_to_the_centre(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    w = word()
    D = f"{URL}/dispatches"
    centre = staff(["ops_manager"], gouvernorat=None)
    body = {"kind": "notice", "urgency": "flash", "subject": f"انهيار جزئي لجسر {w}", "body": "الطريق 27 مقطوعة"}
    assert (await client.post(D, json=body, headers=centre)).status_code == 403
    assert (await client.post(D, json=body, headers=staff(["governor"], gouvernorat=NABEUL))).status_code == 403
    r = await client.post(D, json=body, headers=staff(["operator"], gouvernorat=NABEUL))
    assert r.status_code == 201, r.text
    notice = r.json()["dispatch"]
    assert notice["number"].startswith("NOT-") and notice["origin_gouvernorat"] == NABEUL
    # Sousse does not see it; the centre has it unread in its inbox, then answers.
    assert (await client.get(f"{D}/{notice['id']}", headers=room(staff, SOUSSE))).status_code == 404
    inbox = (await client.get(D, params={"box": "inbox", "q": w}, headers=centre)).json()
    assert inbox["items"][0]["unread"] and inbox["unread"] >= 1
    r = await client.post(
        f"{D}/{notice['id']}/replies", json={"body": "أُرسلت وحدة هندسة", "gouvernorat_code": NABEUL}, headers=centre
    )
    assert r.status_code == 200
    back = (await client.get(f"{D}/{notice['id']}", headers=room(staff))).json()
    assert back["threads"][0]["replies"][0]["side"] == "centre" and back["targets"][0]["replied_at"]
    events = await outbox_events(session, "register.notice_sent")
    assert any(e["id"] == notice["id"] and e["urgency"] == "flash" for e in events)
