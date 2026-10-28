"""Phase 8 §2: national memory (workflow, versions, access levels, pre-fill from an incident) and the events library
(PostgreSQL fallback always; OpenSearch when OPENSEARCH_URL is set), scope of every hit, the indexer and the
assistant's memory sources."""

import json
import os
import re
import secrets
import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_system_sessionmaker
from app.modules.decision import llm
from app.modules.knowledge import calendar as kcalendar
from app.modules.knowledge import documents, indexer, opensearch, search
from app.modules.knowledge import text as kt
from app.modules.knowledge.domain import Kind
from app.modules.knowledge.opensearch import OpenSearch, SearchUnavailable
from tests.aihelpers import FakeAi
from tests.conftest import accept_charter, device_headers, report_body

Staff = Callable[..., dict[str, str]]
# Gouvernorats no other test module reports in.
ZAGHOUAN, BEJA = 22, 31
ZAGHOUAN_POINT = {"lat": 36.4029, "lon": 10.1429, "accuracy_m": 10.0}
BEJA_POINT = {"lat": 36.7256, "lon": 9.1817, "accuracy_m": 10.0}


# ---------------------------------------------------------------- fixtures and helpers


@pytest.fixture(autouse=True)
def postgres_backend() -> Iterator[None]:
    """Every test here runs on the PostgreSQL backend unless it injects an engine."""
    opensearch.set_engine(None)
    yield
    opensearch.set_engine(None, override=False)


async def index_all() -> None:
    """Drive the indexer as the worker would: outbox, sweep (everything settled), prune, push/drop."""
    sessionmaker = get_system_sessionmaker()
    async with sessionmaker() as s, s.begin():
        await indexer.consume_outbox(s)
        while await indexer.sweep(s, settle=__import__("datetime").timedelta(0)):
            pass
        await indexer.prune(s)
    await indexer.cycle(sessionmaker, sweep_now=False, prune_now=False, embed=False)


async def new_report(client: httpx.AsyncClient, location: dict[str, float], **overrides: Any) -> dict[str, Any]:
    headers = device_headers()
    await accept_charter(client, headers)
    r = await client.post("/api/v1/reports", json=report_body(location, **overrides), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


async def new_incident(
    client: httpx.AsyncClient, staff: Staff, location: dict[str, float], code: int, **overrides: Any
) -> tuple[str, str]:
    report = await new_report(client, location, **overrides)
    r = await client.post(
        f"/api/v1/staff/reports/{report['id']}/incident",
        json={"action": "new", "override_reason": "independent test incident"},
        headers=staff(gouvernorat=code),
    )
    assert r.status_code == 200, r.text
    return r.json()["incident_id"], report["id"]


def unique_word() -> str:
    """A random word no analyser splits or stems into something common (letters only)."""
    return "zq" + "".join(secrets.choice("bcdfghjklmnpqrstvwxz") for _ in range(10))


def random_year() -> int:
    """A past year of its own for the entries of one test, so a search can be narrowed to them on a reused DB."""
    return 1951 + secrets.randbelow(49)


def entry_body(word: str, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "title": {"ar": f"حرائق الغابات {word}", "fr": f"Feux de forêt {word}"},
        "event_type": "fire",
        "started_at": "2003-07-14T10:00:00+01:00",
        "ended_at": "2003-07-16T18:00:00+01:00",
        "gouvernorats": [ZAGHOUAN],
        "summary": {"ar": f"اندلع الحريق في الغابة {word}", "fr": f"Le feu a pris dans la forêt {word}."},
        "lessons": {"ar": "تجهيز المسالك مسبقا", "fr": "Préparer les pistes à l'avance."},
        "recommendations": {"ar": "", "fr": "Renforcer les guetteurs."},
        "sources": [{"title": "Rapport DGPC", "url": "https://www.protectioncivile.tn/rapport"}],
        "access": "gouvernorat",
    }
    body.update(overrides)
    return body


async def publish(client: httpx.AsyncClient, staff: Staff, body: dict[str, Any], code: int = ZAGHOUAN) -> str:
    author, reviewer = staff(["ops_manager"], gouvernorat=code), staff(["local_committee"], gouvernorat=code)
    if not body["gouvernorats"]:
        author, reviewer = staff(["ops_manager"], gouvernorat=None), staff(["central_committee"], gouvernorat=None)
    r = await client.post("/api/v1/staff/memory", json=body, headers=author)
    assert r.status_code == 201, r.text
    entry = r.json()
    r = await client.post(
        f"/api/v1/staff/memory/{entry['id']}/transition", json={"to": "in_review", "version": 1}, headers=author
    )
    assert r.status_code == 200, r.text
    r = await client.post(
        f"/api/v1/staff/memory/{entry['id']}/transition", json={"to": "published", "version": 2}, headers=reviewer
    )
    assert r.status_code == 200, r.text
    return entry["id"]  # type: ignore[no-any-return]


async def free_year(client: httpx.AsyncClient, headers: dict[str, str]) -> int:
    """A past year with no memory entry in Zaghouan yet: on a reused DB (the job runs this file twice) a browse of the
    year then lists this test's entries only."""
    while True:
        year = random_year()
        body = await find(
            client,
            headers,
            "",
            kinds="memory",
            gouvernorat=ZAGHOUAN,
            **{"from": f"{year}-01-01", "to": f"{year}-12-31"},
        )
        if not body["items"]:
            return year


async def find(client: httpx.AsyncClient, headers: dict[str, str], q: str, **params: Any) -> dict[str, Any]:
    r = await client.get("/api/v1/staff/library/search", params={"q": q, **params}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()  # type: ignore[no-any-return]


def ids(body: dict[str, Any]) -> set[str]:
    return {item["id"] for item in body["items"]}


# ---------------------------------------------------------------- text helpers


def test_normalisation_and_query_terms() -> None:
    assert kt.normalise("Évacuation de l'ÉCOLE — الحَرِيق في الغابة") == "evacuation de ecole الحريق في الغابه"
    assert kt.query_terms("الحرائق في الغابة") == ["الحرايق", "حرايق", "في", "الغابه", "غابه"]


def test_excerpt_escapes_everything_but_mark() -> None:
    body = 'قبل <script>alert(1)</script> & "x" ' + "كلام " * 80 + "اشتعل الحريق قرب <b>المصنع</b> ثم انتهى"
    out = kt.excerpt(body, kt.query_terms("حريق المصنع"))
    assert "<mark>الحريق</mark>" in out and "<mark>المصنع</mark>" in out
    assert re.sub(r"</?mark>", "", out).count("<") == 0 and "&lt;b&gt;" in out
    assert out.startswith("…")
    # Engine highlights become the same HTML: sentinels to <mark>, any tag text escaped.
    fragment = f"a <img src=x onerror=1> {kt.HL_OPEN}feu{kt.HL_CLOSE} b"
    assert kt.from_highlight(fragment) == "a &lt;img src=x onerror=1&gt; <mark>feu</mark> b"


def test_reciprocal_rank_fusion() -> None:
    fused = search.fuse([[("memory", "a"), ("report", "b")], [("report", "b"), ("incident", "c")]])
    assert [key for key, _ in fused] == [("report", "b"), ("memory", "a"), ("incident", "c")]
    assert fused[0][1] == pytest.approx(1 / 62 + 1 / 61)


# ---------------------------------------------------------------- national memory


async def test_memory_review_workflow_and_versions(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession
) -> None:
    word = unique_word()
    author = staff(["ops_manager"], gouvernorat=ZAGHOUAN)
    reviewer = staff(["local_committee"], gouvernorat=ZAGHOUAN)
    r = await client.post("/api/v1/staff/memory", json=entry_body(word), headers=staff(["operator"]))
    assert r.status_code == 403
    r = await client.post(
        "/api/v1/staff/memory", json=entry_body(word), headers=staff(["ops_manager"], gouvernorat=BEJA)
    )
    assert r.status_code == 403 and r.json()["detail"] == "out_of_scope"
    r = await client.post("/api/v1/staff/memory", json=entry_body(word, sources=[{"title": "x"}]), headers=author)
    assert r.status_code == 422
    r = await client.post("/api/v1/staff/memory", json=entry_body(word), headers=author)
    assert r.status_code == 201, r.text
    entry = r.json()
    eid = entry["id"]
    assert entry["status"] == "draft" and entry["version"] == 1 and entry["can_edit"] and not entry["can_review"]
    assert entry["author"]["id"].startswith("ehimaya-staff:")

    r = await client.patch(f"/api/v1/staff/memory/{eid}", json={"version": 9, "lessons": {"ar": "x"}}, headers=author)
    assert r.status_code == 409 and r.json()["detail"] == "version_conflict"
    r = await client.patch(
        f"/api/v1/staff/memory/{eid}",
        json={"version": 1, "strengths": {"ar": "سرعة التدخل", "fr": "Rapidité"}},
        headers=author,
    )
    assert r.status_code == 200 and r.json()["version"] == 2 and r.json()["strengths"]["fr"] == "Rapidité"

    async def move(to: str, version: int, headers: dict[str, str], note: str | None = None) -> httpx.Response:
        return await client.post(
            f"/api/v1/staff/memory/{eid}/transition", json={"to": to, "version": version, "note": note}, headers=headers
        )

    assert (await move("published", 2, reviewer)).json()["detail"] == "invalid_transition"
    assert (await move("in_review", 2, author)).status_code == 200
    r = await client.patch(f"/api/v1/staff/memory/{eid}", json={"version": 3}, headers=author)
    assert r.json()["detail"] == "entry_in_review"
    # The author (who is also a reviewer role) cannot approve their own entry: a second staff member reviews.
    r = await move("published", 3, author)
    assert r.status_code == 403 and r.json()["detail"] == "self_review_forbidden"
    assert (await move("published", 3, staff(["field_commander"], gouvernorat=ZAGHOUAN))).status_code == 403
    assert (await move("draft", 3, reviewer)).json()["detail"] == "note_required"
    r = await move("draft", 3, reviewer, "Compléter les chiffres")
    assert r.status_code == 200 and r.json()["reviewers"][0]["decision"] == "changes_requested"
    assert (await move("in_review", 4, author)).status_code == 200
    r = await move("published", 5, reviewer)
    assert r.status_code == 200, r.text
    published = r.json()
    assert published["status"] == "published" and published["published_version"] == 6
    assert published["reviewers"][-1]["decision"] == "approved"

    # Editing a published entry starts a new draft; readers keep the published snapshot.
    r = await client.patch(
        f"/api/v1/staff/memory/{eid}",
        json={"version": 6, "title": {"ar": "عنوان جديد للمسودة", "fr": "Nouveau titre"}},
        headers=author,
    )
    assert r.status_code == 200 and r.json()["status"] == "draft" and r.json()["published_version"] == 6
    reader = staff(["operator"], gouvernorat=ZAGHOUAN)
    seen = (await client.get(f"/api/v1/staff/memory/{eid}", headers=reader)).json()
    assert seen["status"] == "published" and seen["version"] == 6 and seen["title"]["fr"].startswith("Feux de forêt")
    assert not seen["can_edit"]
    versions = (await client.get(f"/api/v1/staff/memory/{eid}/versions", headers=author)).json()["items"]
    assert [v["change"] for v in versions] == [
        "edited",
        "published",
        "in_review",
        "changes_requested",
        "in_review",
        "edited",
        "created",
    ]
    assert [
        v["version"] for v in (await client.get(f"/api/v1/staff/memory/{eid}/versions", headers=reader)).json()["items"]
    ] == [6]
    v2 = (await client.get(f"/api/v1/staff/memory/{eid}/versions/2", headers=author)).json()
    assert v2["entry"]["strengths"]["ar"] == "سرعة التدخل"
    assert (await client.get(f"/api/v1/staff/memory/{eid}/versions/2", headers=reader)).status_code == 404

    actions = (
        (
            await session.execute(
                text("SELECT action FROM audit.log WHERE target = :t ORDER BY seq"), {"t": f"memory:{eid}"}
            )
        )
        .scalars()
        .all()
    )
    assert actions == [
        "memory.created",
        "memory.edited",
        "memory.in_review",
        "memory.changes_requested",
        "memory.in_review",
        "memory.published",
        "memory.edited",
    ]
    # Archiving needs a reason; an archived entry leaves readers' view; a draft once published cannot be deleted.
    assert (await move("archived", 7, reviewer)).json()["detail"] == "note_required"
    assert (await client.delete(f"/api/v1/staff/memory/{eid}", headers=author)).json()["detail"] == (
        "entry_published_once"
    )
    assert (await move("archived", 7, reviewer, "Doublon")).status_code == 200
    assert (await client.get(f"/api/v1/staff/memory/{eid}", headers=reader)).status_code == 404
    assert (await move("draft", 8, reviewer)).json()["status"] == "draft"


async def test_memory_delete_and_list(client: httpx.AsyncClient, staff: Staff) -> None:
    word = unique_word()
    author = staff(["content_editor"], gouvernorat=ZAGHOUAN)
    eid = (await client.post("/api/v1/staff/memory", json=entry_body(word), headers=author)).json()["id"]
    listed = (await client.get("/api/v1/staff/memory", params={"q": word, "status": "draft"}, headers=author)).json()
    assert [i["id"] for i in listed["items"]] == [eid]
    # A reader of another gouvernorat does not even see that a draft exists.
    other = staff(["operator"], gouvernorat=BEJA)
    assert (await client.get("/api/v1/staff/memory", params={"q": word}, headers=other)).json()["items"] == []
    assert (await client.get(f"/api/v1/staff/memory/{eid}", headers=other)).status_code == 404
    assert (await client.delete(f"/api/v1/staff/memory/{eid}", headers=other)).status_code == 403
    assert (await client.delete(f"/api/v1/staff/memory/{eid}", headers=author)).status_code == 204
    assert (await client.get(f"/api/v1/staff/memory/{eid}", headers=author)).status_code == 404


async def test_memory_access_levels(client: httpx.AsyncClient, staff: Staff) -> None:
    word = unique_word()
    committee = await publish(client, staff, entry_body(word, access="committee"))
    national = await publish(client, staff, entry_body(word, access="national"))
    regional = await publish(client, staff, entry_body(word))

    def visible(headers: dict[str, str]) -> set[str]:
        return {e for e in (committee, national, regional) if e in seen[id(headers)]}

    seen: dict[int, set[str]] = {}
    callers = {
        "operator_zaghouan": staff(["operator"], gouvernorat=ZAGHOUAN),
        "operator_beja": staff(["operator"], gouvernorat=BEJA),
        "local_committee_zaghouan": staff(["local_committee"], gouvernorat=ZAGHOUAN),
        "local_committee_beja": staff(["local_committee"], gouvernorat=BEJA),
        "central_committee": staff(["central_committee"], gouvernorat=None),
        "national_operator": staff(["operator"], gouvernorat=None),
    }
    for headers in callers.values():
        listed = (await client.get("/api/v1/staff/memory", params={"q": word}, headers=headers)).json()
        seen[id(headers)] = {i["id"] for i in listed["items"]}
        for eid in (committee, national, regional):
            code = (await client.get(f"/api/v1/staff/memory/{eid}", headers=headers)).status_code
            assert (code == 200) == (eid in seen[id(headers)]), (eid, code)
    assert visible(callers["operator_zaghouan"]) == {national, regional}
    assert visible(callers["operator_beja"]) == {national}
    assert visible(callers["local_committee_zaghouan"]) == {committee, national, regional}
    assert visible(callers["local_committee_beja"]) == {national}
    assert visible(callers["central_committee"]) == {committee, national, regional}
    assert visible(callers["national_operator"]) == {national, regional}


async def test_memory_from_incident_prefill(client: httpx.AsyncClient, staff: Staff, session: AsyncSession) -> None:
    secret_text = f"اسمي محمد ورقمي 98{secrets.randbelow(10**6):06d}"
    incident_id, _ = await new_incident(client, staff, ZAGHOUAN_POINT, ZAGHOUAN, category="flood", text=secret_text)
    commander = staff(["field_commander"], gouvernorat=ZAGHOUAN)
    r = await client.post(
        f"/api/v1/staff/incidents/{incident_id}/close",
        json={
            "outcome": "resolved",
            "summary": "Évacuation de 12 familles avant la montée des eaux.",
            "casualties": {"evacuated": 40, "rescued": 3},
            "lessons": "تنظيف مجاري المياه قبل الخريف",
        },
        headers=commander,
    )
    assert r.status_code == 200, r.text
    assert (
        await client.post(
            f"/api/v1/staff/memory/from-incident/{incident_id}", headers=staff(["ops_manager"], gouvernorat=BEJA)
        )
    ).status_code == 404
    r = await client.post(f"/api/v1/staff/memory/from-incident/{incident_id}", headers=commander)
    assert r.status_code == 201, r.text
    draft = r.json()
    assert draft["status"] == "draft" and draft["incident_ids"] == [incident_id]
    assert draft["event_type"] == "flood" and draft["gouvernorats"] == [ZAGHOUAN] and draft["access"] == "gouvernorat"
    assert "| Personnes évacuées | 40 |" in draft["summary"]["fr"] and "| تم إجلاؤهم | 40 |" in draft["summary"]["ar"]
    assert "Évacuation de 12 familles" in draft["summary"]["fr"]
    assert draft["lessons"]["ar"] == "تنظيف مجاري المياه قبل الخريف"
    assert "Chronologie" in draft["summary"]["fr"]
    dumped = json.dumps(draft, ensure_ascii=False)
    # Facts only: the citizen's words never reach the national memory by themselves.
    assert secret_text not in dumped and "محمد" not in dumped
    # Nothing is published automatically.
    assert draft["published_version"] is None


# ---------------------------------------------------------------- events library (PostgreSQL backend)


async def test_library_search_scope_and_highlight(client: httpx.AsyncClient, staff: Staff) -> None:
    word = unique_word()
    regional = await publish(client, staff, entry_body(word))
    hostile = f"حريق {word} <img src=x onerror=alert(1)> قرب المستودع"
    zaghouan_report = await new_report(client, ZAGHOUAN_POINT, text=hostile)
    beja_report = await new_report(client, BEJA_POINT, text=f"حريق {word} في بيت قديم")
    await index_all()

    zaghouan = staff(["operator"], gouvernorat=ZAGHOUAN)
    body = await find(client, zaghouan, word)
    assert body["backend"] == "postgres" and body["semantic"] is False
    assert ids(body) == {regional, zaghouan_report["id"]}
    report_hit = next(i for i in body["items"] if i["id"] == zaghouan_report["id"])
    assert report_hit["kind"] == "report" and report_hit["gouvernorat"] == ZAGHOUAN
    assert f"<mark>{word}</mark>" in report_hit["excerpt"] and "&lt;img" in report_hit["excerpt"]
    assert re.sub(r"</?mark>", "", report_hit["excerpt"]).count("<") == 0
    assert {f["key"]: f["count"] for f in body["facets"]["kind"]} == {"memory": 1, "report": 1}

    # Staff of another gouvernorat see their own report only; a national operator sees both; content editors never
    # see citizens' words.
    assert ids(await find(client, staff(["operator"], gouvernorat=BEJA), word)) == {beja_report["id"]}
    assert ids(await find(client, staff(["operator"], gouvernorat=None), word)) == {
        regional,
        zaghouan_report["id"],
        beja_report["id"],
    }
    assert ids(await find(client, staff(["content_editor"], gouvernorat=None), word)) == {regional}
    assert (
        await client.get("/api/v1/staff/library/search", params={"q": word}, headers=staff(["sysadmin"]))
    ).status_code == 403

    # Filters: kinds, gouvernorat, category, period.
    assert ids(await find(client, staff(gouvernorat=None), word, kinds="memory")) == {regional}
    assert ids(await find(client, staff(gouvernorat=None), word, gouvernorat=BEJA)) == {beja_report["id"]}
    assert ids(await find(client, staff(gouvernorat=None), word, **{"from": "2003-01-01", "to": "2003-12-31"})) == {
        regional
    }
    r = await client.get("/api/v1/staff/library/search", params={"q": word, "kinds": "nope"}, headers=zaghouan)
    assert r.status_code == 422 and r.json()["detail"] == "invalid_kind"

    # Encrypted at the source, encrypted in the index: no clear text, blind-index tokens only.
    async with get_system_sessionmaker()() as s:
        raw = (
            await s.execute(
                text(
                    "SELECT body, norm, body_enc, cardinality(tokens) AS n FROM knowledge.search_doc "
                    "WHERE kind = 'report' AND ref_id = :id"
                ),
                {"id": zaghouan_report["id"]},
            )
        ).one()
    assert raw.body is None and raw.norm is None and word.encode() not in bytes(raw.body_enc) and raw.n > 3


async def test_library_arabic_variants_and_pagination(client: httpx.AsyncClient, staff: Staff) -> None:
    national = staff(gouvernorat=None)
    word, year = unique_word(), await free_year(client, national)
    period = {"from": f"{year}-01-01", "to": f"{year}-12-31"}
    created = [
        await publish(
            client,
            staff,
            entry_body(
                word,
                summary={"ar": f"إخلاء المدرسة بعد الفيضانات {word} رقم {n}", "fr": f"Évacuation {word} {n}"},
                started_at=f"{year}-0{n + 1}-10T10:00:00+01:00",
                ended_at=None,
            ),
        )
        for n in range(3)
    ]
    await index_all()
    # "الفيضانات" written with its article and diacritics still matches; "ecole" without accent matches "École".
    body = await find(client, national, f"فيضانات {word}", **period)
    assert ids(body) == set(created)
    page1 = await find(client, national, word, limit=2)
    assert len(page1["items"]) == 2 and page1["next_cursor"]
    page2 = await find(client, national, word, limit=2, cursor=page1["next_cursor"])
    assert ids(page1) | ids(page2) == set(created) and page2["next_cursor"] is None
    r = await client.get("/api/v1/staff/library/search", params={"q": word, "cursor": "%%"}, headers=national)
    assert r.status_code == 422
    # Browsing (no query) lists the newest first with exact facets.
    browse = await find(client, national, "", kinds="memory", gouvernorat=ZAGHOUAN, **period)
    dates = [i["date"] for i in browse["items"]]
    assert dates == sorted(dates, reverse=True) and set(created) == ids(browse)
    assert {f["key"] for f in browse["facets"]["year"]} == {str(year)}


async def test_library_calendar_tree_and_item(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession, fake_store: Any
) -> None:
    word = unique_word()
    eid = await publish(
        client, staff, entry_body(word, started_at="2001-03-05T12:00:00+01:00", ended_at=None, event_type="landslide")
    )
    report = await new_report(client, ZAGHOUAN_POINT, text=f"انزلاق تربة {word}", category="landslide")
    await index_all()
    zaghouan = staff(["operator"], gouvernorat=ZAGHOUAN)
    cal = (
        await client.get(
            "/api/v1/staff/library/calendar",
            params={"year": 2001, "month": 3, "kinds": "memory", "gouvernorat": ZAGHOUAN, "category": "landslide"},
            headers=zaghouan,
        )
    ).json()
    assert {d["date"]: d["count"] for d in cal["days"]}.get("2001-03-05", 0) >= 1
    # The six levels (L4a): the same filters, the period of the level cut into its cells.
    grids = {}
    for level in kcalendar.LEVELS:
        r = await client.get(
            "/api/v1/staff/library/calendar/grid",
            params={"level": level, "on": "2001-03-05", "kinds": "memory", "category": "landslide"},
            headers=zaghouan,
        )
        assert r.status_code == 200, r.text
        grids[level] = r.json()
    assert len(grids["day"]["cells"]) == 24 and grids["day"]["cells"][12]["count"] >= 1
    assert sum(c["count"] for c in grids["day"]["cells"]) == grids["day"]["cells"][12]["count"]
    assert grids["week"]["start"] == "2001-03-05" and len(grids["week"]["cells"]) == 7
    assert grids["week"]["cells"][0]["count"] >= 1
    assert len(grids["month"]["cells"]) == 31 and grids["month"]["cells"][4]["count"] >= 1
    quarter = grids["quarter"]
    assert quarter["step"] == "week" and quarter["cells"][0]["start"] == "2001-01-01"
    assert quarter["cells"][-1]["end"] == "2001-03-31"
    assert next(c for c in quarter["cells"] if c["start"] == "2001-03-05")["count"] >= 1
    assert [len(grids[x]["cells"]) for x in ("half", "year")] == [6, 12]
    assert grids["year"]["cells"][2]["count"] == grids["half"]["cells"][2]["count"] >= 1
    assert all(sum(c["count"] for c in grids[x]["cells"]) >= 1 for x in grids)
    bad = await client.get(
        "/api/v1/staff/library/calendar/grid", params={"level": "decade", "on": "2001-03-05"}, headers=zaghouan
    )
    assert bad.status_code == 422
    tree = (
        await client.get("/api/v1/staff/library/tree", params={"by": "type", "category": "landslide"}, headers=zaghouan)
    ).json()
    kinds = {n["key"]: n for n in tree["nodes"]}
    assert (
        kinds["memory"]["label"]["fr"] == "Mémoire nationale" and kinds["memory"]["children"][0]["key"] == "landslide"
    )
    period = (
        await client.get("/api/v1/staff/library/tree", params={"by": "period", "kinds": "memory"}, headers=zaghouan)
    ).json()
    assert any(child["key"] == "2001-03" for node in period["nodes"] for child in node["children"])
    by_place = (await client.get("/api/v1/staff/library/tree", params={"by": "gouvernorat"}, headers=zaghouan)).json()
    assert all(n["key"] in (str(ZAGHOUAN), "0") for n in by_place["nodes"])

    item = (await client.get(f"/api/v1/staff/library/items/memory/{eid}", headers=zaghouan)).json()
    assert (
        item["kind"] == "memory" and "Préparer les pistes" in item["body"] and item["fields"]["published_version"] == 3
    )
    r = await client.get(f"/api/v1/staff/library/items/report/{report['id']}", headers=zaghouan)
    assert r.status_code == 200 and word in r.json()["body"] and r.json()["fields"]["tracking_code"]
    # Out of scope or unknown: 404, never a hint.
    beja = staff(["operator"], gouvernorat=BEJA)
    assert (await client.get(f"/api/v1/staff/library/items/report/{report['id']}", headers=beja)).status_code == 404
    assert (await client.get(f"/api/v1/staff/library/items/memory/{eid}", headers=beja)).status_code == 404
    assert (await client.get("/api/v1/staff/library/items/report/not-a-uuid", headers=zaghouan)).status_code == 404
    audited = (
        await session.execute(
            text("SELECT count(*) FROM audit.log WHERE action = 'library.item_view' AND target = :t"),
            {"t": f"report:{report['id']}"},
        )
    ).scalar_one()
    assert audited == 1


def test_calendar_levels_bounds_and_cells() -> None:
    from datetime import date

    on = date(2024, 2, 29)
    assert kcalendar.bounds("week", on) == (date(2024, 2, 26), date(2024, 3, 3))
    assert kcalendar.bounds("quarter", on) == (date(2024, 1, 1), date(2024, 3, 31))
    assert kcalendar.bounds("half", date(2024, 11, 2)) == (date(2024, 7, 1), date(2024, 12, 31))
    assert kcalendar.bounds("year", on) == (date(2024, 1, 1), date(2024, 12, 31))
    weeks = kcalendar.cells("quarter", *kcalendar.bounds("quarter", on))
    # 2024-01-01 is a Monday; the last week is cut at the end of March.
    assert weeks[0] == (date(2024, 1, 1), date(2024, 1, 7)) and weeks[-1] == (date(2024, 3, 25), date(2024, 3, 31))
    assert len(kcalendar.cells("month", *kcalendar.bounds("month", on))) == 29


async def test_calendar_figures_scope_and_roles(client: httpx.AsyncClient, staff: Staff) -> None:
    url = "/api/v1/staff/library/calendar/figures"
    period = {"from": "2001-03-01", "to": "2001-03-31"}
    zaghouan = staff(["operator"], gouvernorat=ZAGHOUAN)
    r = await client.get(url, params=period, headers=zaghouan)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["gouvernorats"] == [ZAGHOUAN] and body["min_cell"] >= 1 and "by_category" in body["figures"]
    # Another gouvernorat than one's own: refused, never widened.
    other = await client.get(url, params=period | {"gouvernorat": BEJA}, headers=zaghouan)
    assert other.status_code == 403
    editor = staff(["content_editor"])
    assert (await client.get(url, params=period, headers=editor)).status_code == 403
    long = {"from": "2001-01-01", "to": "2002-06-30"}
    assert (await client.get(url, params=long, headers=zaghouan)).status_code == 422
    national = staff(["central_committee"], gouvernorat=None)
    whole = (await client.get(url, params=period | {"category": "landslide"}, headers=national)).json()
    assert whole["gouvernorats"] == []


async def test_indexer_follows_events_and_wipes_rejected_reports(client: httpx.AsyncClient, staff: Staff) -> None:
    sessionmaker = get_system_sessionmaker()
    await index_all()  # cursor initialised, everything settled indexed
    word = unique_word()
    report = await new_report(client, ZAGHOUAN_POINT, text=f"تسرب غاز {word}")
    async with sessionmaker() as s, s.begin():
        assert await indexer.consume_outbox(s) >= 1
    zaghouan = staff(["operator"], gouvernorat=ZAGHOUAN)
    assert ids(await find(client, zaghouan, word)) == {report["id"]}
    r = await client.post(
        f"/api/v1/staff/reports/{report['id']}/status", json={"status": "rejected", "note": "faux"}, headers=zaghouan
    )
    assert r.status_code == 200, r.text
    async with sessionmaker() as s, s.begin():
        await indexer.consume_outbox(s)
        row = await documents.find_row(s, "report", report["id"])
        # Tombstone: keys only, the text is gone at once.
        assert row is not None and row.deleted and row.body_enc is None and row.tokens == []
    assert ids(await find(client, zaghouan, word)) == set()
    await indexer.cycle(sessionmaker, sweep_now=False, prune_now=False, embed=False)
    async with sessionmaker() as s:
        assert await documents.find_row(s, "report", report["id"]) is None


async def test_outbox_cursor_waits_for_gaps(session: AsyncSession) -> None:
    sessionmaker = get_system_sessionmaker()
    async with sessionmaker() as s, s.begin():
        await indexer.consume_outbox(s)
        # The cursor on a row of this test (the runtime role cannot set the sequence back).
        base = int(
            await s.scalar(
                text("INSERT INTO events.outbox (subject, payload) VALUES ('test.noop', '{}'::jsonb) RETURNING id")
            )
            or 0
        )
        await s.execute(
            text(
                "INSERT INTO knowledge.index_state (key, value) VALUES ('outbox', '{}') "
                "ON CONFLICT (key) DO UPDATE SET value = jsonb_build_object('id', CAST(:b AS int))"
            ),
            {"b": base},
        )
    # A row two ids ahead (the one in between belongs to an open or rolled-back transaction).
    async with sessionmaker() as s, s.begin():
        assert await s.scalar(text("SELECT nextval('events.outbox_id_seq')")) == base + 1
        await s.execute(text("INSERT INTO events.outbox (subject, payload) VALUES ('test.noop', '{}'::jsonb)"))
    async with sessionmaker() as s, s.begin():
        await indexer.consume_outbox(s)
        state = (await s.execute(text("SELECT value FROM knowledge.index_state WHERE key = 'outbox'"))).scalar_one()
    assert state["id"] == base and state["gap"]["at"] == base + 1
    async with sessionmaker() as s, s.begin():
        await s.execute(
            text(
                "UPDATE knowledge.index_state "
                "SET value = jsonb_set(value, '{gap,since}', '\"2000-01-01T00:00:00+00:00\"') WHERE key = 'outbox'"
            )
        )
    async with sessionmaker() as s, s.begin():
        await indexer.consume_outbox(s)
        state = (await s.execute(text("SELECT value FROM knowledge.index_state WHERE key = 'outbox'"))).scalar_one()
    assert state == {"id": base + 2}
    async with sessionmaker() as s, s.begin():
        await s.execute(text("DELETE FROM events.outbox WHERE subject = 'test.noop'"))


async def test_semantic_part_is_fused(client: httpx.AsyncClient, staff: Staff, fake_ai: FakeAi) -> None:
    word, year = unique_word(), random_year()
    eid = await publish(client, staff, entry_body(word, started_at=f"{year}-07-14T10:00:00+01:00", ended_at=None))
    await index_all()
    sessionmaker = get_system_sessionmaker()
    async with sessionmaker() as s, s.begin():
        while await indexer.embed_pending(s, fake_ai):
            pass
        row = await documents.find_row(s, "memory", eid)
        assert row is not None and row.embedding_model == "e5-test"
    # No word in common, but the same vector: found through pgvector only.
    body = await find(
        client,
        staff(["operator"], gouvernorat=ZAGHOUAN),
        "حماية الغطاء النباتي",
        kinds="memory",
        **{"from": f"{year}-01-01", "to": f"{year}-12-31"},
    )
    assert body["semantic"] is True and eid in ids(body)


async def test_engine_hits_are_rechecked_and_fallback(client: httpx.AsyncClient, staff: Staff) -> None:
    word = unique_word()
    beja_report = await new_report(client, BEJA_POINT, text=f"حريق {word}")
    zaghouan_report = await new_report(client, ZAGHOUAN_POINT, text=f"حريق {word}")
    await index_all()

    class LeakyEngine:
        """An index that 'forgets' the scope filter: the API must still drop what the caller may not see."""

        async def ensure_indices(self) -> None: ...

        async def bulk(self, upserts: list[dict[str, Any]], deletes: list[tuple[str, str]]) -> None: ...

        async def health(self) -> str | None:
            return "green"

        async def search(self, body: dict[str, Any]) -> dict[str, Any]:
            hits = [
                {
                    "_source": {"kind": "report", "ref_id": rid},
                    "highlight": {"body": [f"x {kt.HL_OPEN}{word}{kt.HL_CLOSE}"]},
                }
                for rid in (beja_report["id"], zaghouan_report["id"], str(uuid.uuid4()))
            ]
            return {"hits": {"hits": hits}}

    opensearch.set_engine(LeakyEngine())
    body = await find(client, staff(["operator"], gouvernorat=ZAGHOUAN), word)
    assert body["backend"] == "opensearch" and ids(body) == {zaghouan_report["id"]}
    assert body["items"][0]["excerpt"] == f"x <mark>{word}</mark>"

    class DownEngine(LeakyEngine):
        async def search(self, body: dict[str, Any]) -> dict[str, Any]:
            raise SearchUnavailable("ConnectError")

    opensearch.set_engine(DownEngine())
    body = await find(client, staff(["operator"], gouvernorat=ZAGHOUAN), word)
    assert body["backend"] == "postgres" and ids(body) == {zaghouan_report["id"]}


async def test_assistant_cites_published_memory(client: httpx.AsyncClient, staff: Staff) -> None:
    word = unique_word()
    eid = await publish(
        client,
        staff,
        entry_body(
            word,
            event_type="chemical_leak",
            lessons={"ar": "", "fr": f"Couper la ventilation du bâtiment {word}."},
        ),
    )
    draft = (
        await client.post(
            "/api/v1/staff/memory",
            json=entry_body(word, event_type="chemical_leak"),
            headers=staff(["ops_manager"], gouvernorat=ZAGHOUAN),
        )
    ).json()["id"]
    await index_all()
    incident_id, _ = await new_incident(client, staff, ZAGHOUAN_POINT, ZAGHOUAN, category="chemical_leak")

    class CiteMemory:
        model = "qwen3-test"
        prompts: list[str] = []

        async def chat_json(self, system: str, user: str, schema: dict[str, Any]) -> str:
            self.prompts.append(user)
            number = re.search(r"\[(\d+)\] \(national memory", user)
            assert number, user
            return json.dumps(
                {"answer": f"Couper la ventilation [{number[1]}].", "used_sources": [], "supported": True}
            )

    fake = CiteMemory()
    llm.set_llm(fake)
    try:
        r = await client.post(
            f"/api/v1/staff/incidents/{incident_id}/assistant",
            json={"question": "Que faire contre la fuite de gaz ?", "lang": "fr"},
            headers=staff(gouvernorat=ZAGHOUAN),
        )
    finally:
        llm.set_llm(None)
    assert r.status_code == 200, r.text
    (source,) = r.json()["sources"]
    assert source["kind"] == "memory" and source["id"] == eid and word in source["excerpt"]
    # Drafts are never a source.
    assert draft not in fake.prompts[-1]
    # Leave no published chemical_leak entry behind for other tests.
    reviewer = staff(["local_committee"], gouvernorat=ZAGHOUAN)
    r = await client.post(
        f"/api/v1/staff/memory/{eid}/transition",
        json={"to": "archived", "version": 3, "note": "test"},
        headers=reviewer,
    )
    assert r.status_code == 200
    await index_all()


async def test_search_ids_for_other_modules(staff: Staff, session: AsyncSession, client: httpx.AsyncClient) -> None:
    from app.core.security import Principal, Realm, Role

    word = unique_word()
    eid = await publish(client, staff, entry_body(word, access="national"))
    await index_all()
    principal = Principal(subject="x", realm=Realm.STAFF, roles=frozenset({Role.OPERATOR}), gouvernorat_code=None)
    assert await search.search_ids(session, principal, word, ["memory"]) == [uuid.UUID(eid)]
    assert await search.search_ids(session, principal, "  ") is None


async def test_backfill_command_rebuilds_rows(client: httpx.AsyncClient, staff: Staff) -> None:
    word = unique_word()
    eid = await publish(client, staff, entry_body(word))
    sessionmaker = get_system_sessionmaker()
    async with sessionmaker() as s, s.begin():
        await s.execute(text("DELETE FROM knowledge.search_doc WHERE kind = 'memory' AND ref_id = :id"), {"id": eid})
    counts = await indexer.backfill(sessionmaker, [Kind.MEMORY])
    assert counts["upserted"] >= 1
    async with sessionmaker() as s:
        assert await documents.find_row(s, "memory", eid) is not None


# ---------------------------------------------------------------- OpenSearch (only with a real server)

OPENSEARCH_URL = os.environ.get("OPENSEARCH_URL")
requires_opensearch = pytest.mark.skipif(not OPENSEARCH_URL, reason="OPENSEARCH_URL not set")


@pytest.fixture
async def real_engine() -> AsyncIterator[OpenSearch]:
    ca = os.environ.get("OPENSEARCH_CA_FILE")
    engine = OpenSearch(
        str(OPENSEARCH_URL),
        os.environ.get("OPENSEARCH_USER", "admin"),
        os.environ["OPENSEARCH_PASSWORD"],
        Path(ca) if ca else None,
        f"ehimaya-test-{secrets.token_hex(3)}",
        10.0,
    )
    await engine.ensure_indices()
    opensearch.set_engine(engine)
    yield engine
    await engine._request("DELETE", f"/{engine.prefix}-*")
    await engine.close()


async def _refresh(engine: OpenSearch) -> None:
    await engine._request("POST", f"/{engine.library}/_refresh")


@requires_opensearch
async def test_opensearch_arabic_french_scope_and_highlight(
    client: httpx.AsyncClient, staff: Staff, real_engine: OpenSearch
) -> None:
    word = unique_word()
    regional = await publish(
        client,
        staff,
        entry_body(word, summary={"ar": f"حرائق الغابات في الجبل {word}", "fr": f"Les incendies des forêts {word}"}),
    )
    beja = await new_report(client, BEJA_POINT, text=f"حريق كبير في الغابة {word}")
    hostile = await new_report(client, ZAGHOUAN_POINT, text=f"<b>حريق</b> {word}")
    await index_all()
    sessionmaker = get_system_sessionmaker()
    async with sessionmaker() as s, s.begin():
        while await indexer.push(s, real_engine):
            pass
    await _refresh(real_engine)

    zaghouan = staff(["operator"], gouvernorat=ZAGHOUAN)
    body = await find(client, zaghouan, f"الحرائق {word}")
    assert body["backend"] == "opensearch"
    # Other runs' fires may match "الحرائق" too: ours are in, and the Beja report (outside the caller's scope) is not.
    assert {regional, hostile["id"]} <= ids(body) and beja["id"] not in ids(body)
    for item in body["items"]:
        assert re.sub(r"</?mark>", "", item["excerpt"]).count("<") == 0
    # French stemming: "incendie" finds "incendies".
    assert regional in ids(await find(client, zaghouan, f"incendie forêt {word}", kinds="memory"))
    beja_body = await find(client, staff(["operator"], gouvernorat=BEJA), word)
    assert ids(beja_body) == {beja["id"]}
    # A rejected report leaves OpenSearch too.
    r = await client.post(
        f"/api/v1/staff/reports/{hostile['id']}/status", json={"status": "rejected", "note": "faux"}, headers=zaghouan
    )
    assert r.status_code == 200
    async with sessionmaker() as s, s.begin():
        await indexer.consume_outbox(s)
        await indexer.push(s, real_engine)
    await _refresh(real_engine)
    hits = await real_engine.search({"query": {"term": {"ref_id": hostile["id"]}}})
    assert hits["hits"]["hits"] == []


@requires_opensearch
async def test_opensearch_rebuild_switches_aliases(
    client: httpx.AsyncClient, staff: Staff, real_engine: OpenSearch
) -> None:
    word = unique_word()
    eid = await publish(client, staff, entry_body(word, access="national"))
    await indexer.backfill(get_system_sessionmaker(), [Kind.MEMORY], rebuild=True)
    await _refresh(real_engine)
    alias = real_engine.alias("memory")
    aliases = (await real_engine._request("GET", f"/{alias}/_alias/{alias}")).json()
    assert len(aliases) == 1 and next(iter(aliases)).startswith(f"{real_engine.prefix}-memory-v1-r")
    assert eid in ids(await find(client, staff(gouvernorat=None), word))
    assert await real_engine.health() in ("green", "yellow")
