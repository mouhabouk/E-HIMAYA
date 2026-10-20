"""AI layer 1: analysis pipeline, explained scores, rules-only fallback (FR-A-044, FR-A-045, BR-06, BR-20)."""

import uuid

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.modules.ai import lexicon, pipeline, scoring
from app.modules.ai.client import AiRejected, AiUnavailable
from app.modules.ai.settings import PrioritySettings
from app.modules.reports.domain import Category
from tests.aihelpers import FakeAi, Staff, add_audio, analyse, create, detail, spot
from tests.conftest import FakeStore, accept_charter, outbox_events

pytestmark = pytest.mark.usefixtures("isolated_window")

# ---------------------------------------------------------------- immediate scores (no model)


async def test_new_report_is_ranked_at_once_by_the_rules(
    client: httpx.AsyncClient, citizen: dict[str, str], staff: Staff
) -> None:
    await accept_charter(client, citizen)
    report = await create(client, citizen, location=spot(), text="Deux enfants coincés au premier étage, il y a du gaz")
    d = await detail(client, staff, report["id"])
    assert d["analysis_state"] == "pending" and d["lives_at_risk"] is True
    priority = d["analysis"]["priority"]
    assert d["priority_score"] == priority["score"] > 60
    components = {c["key"]: c for c in priority["components"]}
    assert components["lives"]["detail"]["source"] == "keywords"
    assert components["severity"]["detail"]["hazards"] == ["gas"]
    # Components without a data source yet are shown but do not count.
    assert components["weather"]["value"] is None and components["weather"]["points"] == 0
    assert abs(sum(c["points"] for c in priority["components"]) - priority["score"]) <= 1
    credibility = {c["key"]: c["points"] for c in d["analysis"]["credibility"]["components"]}
    assert credibility["base"] == 50 and credibility["registered"] == 15 and credibility["precise_location"] == 5
    assert d["credibility_score"] == d["analysis"]["credibility"]["score"]


async def test_priority_sort_and_pagination(client: httpx.AsyncClient, citizen: dict[str, str], staff: Staff) -> None:
    await accept_charter(client, citizen)
    marker = uuid.uuid4().hex[:10]
    low = await create(client, citizen, category="other", text=f"panneau tombé {marker}", location=spot())
    high = await create(client, citizen, category="drowning", text=f"un enfant se noie {marker}", location=spot())
    mid = await create(client, citizen, category="fire", text=f"fumée {marker}", location=spot())
    operator = staff(gouvernorat=61)
    page = (
        await client.get(
            "/api/v1/staff/reports", params={"q": marker, "sort": "priority", "limit": 2}, headers=operator
        )
    ).json()
    assert [i["id"] for i in page["items"]] == [high["id"], mid["id"]]
    assert page["items"][0]["priority_score"] >= page["items"][1]["priority_score"]
    rest = (
        await client.get(
            "/api/v1/staff/reports",
            params={"q": marker, "sort": "priority", "limit": 2, "cursor": page["next_cursor"]},
            headers=operator,
        )
    ).json()
    assert [i["id"] for i in rest["items"]] == [low["id"]]
    bad = await client.get("/api/v1/staff/reports", params={"sort": "nope"}, headers=operator)
    assert bad.status_code == 422


# ---------------------------------------------------------------- pipeline with models


async def test_full_analysis_with_models(
    client: httpx.AsyncClient,
    citizen: dict[str, str],
    staff: Staff,
    fake_ai: FakeAi,
    fake_store: FakeStore,
    session: AsyncSession,
) -> None:
    await accept_charter(client, citizen)
    report = await create(
        client, citizen, text="Incendie dans un immeuble, deux enfants bloqués", lang="fr", location=spot()
    )
    media_id = await add_audio(session, fake_store, report["id"])
    assert await analyse(report["id"], fake_ai, fake_store)

    d = await detail(client, staff, report["id"])
    analysis = d["analysis"]
    assert d["analysis_state"] == analysis["state"] == "done"
    assert analysis["steps"] == {"transcribe": "done", "extract": "done", "translate": "done", "embed": "done"}
    # The AI service reads media through an internal pre-signed link, never with storage credentials.
    assert fake_ai.calls[0][0] == "transcribe" and fake_ai.calls[0][1].startswith("http://s3-internal.test/")
    # FR-A-045: French is translated, the original is kept.
    assert d["text"] == "Incendie dans un immeuble, deux enfants bloqués"
    assert d["text_ar"] == "ترجمة: Incendie dans un immeuble, deux enfants bloqués"
    [transcript] = analysis["transcripts"]
    assert transcript["media_id"] == media_id and transcript["text"] == "Il y a le feu au deuxième étage."
    assert transcript["language"] == "fr" and transcript["translation_ar"].startswith("ترجمة:")
    assert analysis["extraction"]["injured_count"] == 2 and d["suggested_category"] == "fire"
    assert analysis["models"]["extract"] == "qwen3-test" and analysis["models"]["translate_fr"] == "opus-mt-fr-ar"
    components = {c["key"]: c for c in analysis["priority"]["components"]}
    assert components["lives"]["detail"]["source"] == "model"
    assert components["casualties"]["value"] == 0.4
    stored = await session.scalar(
        text("SELECT embedding IS NOT NULL FROM reports.report WHERE id = :id"), {"id": report["id"]}
    )
    assert stored
    events = [e for e in await outbox_events(session, "report.enriched") if e["report"]["id"] == report["id"]]
    assert len(events) >= 1

    # Nothing left to do: a second pass does not call the models again.
    fake_ai.calls.clear()
    assert not await analyse(report["id"], fake_ai, fake_store)
    assert fake_ai.calls == []


async def test_unavailable_model_is_retried_with_backoff_then_given_up(
    client: httpx.AsyncClient,
    citizen: dict[str, str],
    staff: Staff,
    fake_ai: FakeAi,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "ai_max_attempts", 2)
    await accept_charter(client, citizen)
    report = await create(client, citizen, location=spot())
    fake_ai.fail["extract"] = AiUnavailable("HTTP 503")
    assert await analyse(report["id"], fake_ai)

    row = (
        await session.execute(
            text(
                "SELECT state, attempts, next_attempt_at > now() AS later, steps FROM ai.analysis WHERE report_id = :id"
            ),
            {"id": report["id"]},
        )
    ).one()
    assert (row.state, row.attempts, row.later) == ("pending", 1, True)
    assert row.steps["extract"] == "unavailable" and row.steps["embed"] == "done"
    # BR-06: the report stays visible and ranked while it waits.
    d = await detail(client, staff, report["id"])
    assert d["status"] == "received" and d["priority_score"] is not None

    assert not await analyse(report["id"], fake_ai)  # not due yet
    await session.execute(
        text("UPDATE ai.analysis SET next_attempt_at = now() WHERE report_id = :id"), {"id": report["id"]}
    )
    await session.commit()
    assert await analyse(report["id"], fake_ai)
    d = await detail(client, staff, report["id"])
    assert d["analysis_state"] == "failed" and d["analysis"]["attempts"] == 2


async def test_undecodable_media_is_not_retried(
    client: httpx.AsyncClient,
    citizen: dict[str, str],
    staff: Staff,
    fake_ai: FakeAi,
    fake_store: FakeStore,
    session: AsyncSession,
) -> None:
    await accept_charter(client, citizen)
    report = await create(client, citizen, location=spot())
    await add_audio(session, fake_store, report["id"], kind="video")
    fake_ai.fail["transcribe"] = AiRejected("media_undecodable")
    assert await analyse(report["id"], fake_ai, fake_store)
    d = await detail(client, staff, report["id"])
    assert d["analysis_state"] == "done" and d["analysis"]["steps"]["transcribe"] == "failed"
    assert d["analysis"]["transcripts"][0]["error"] == "media_undecodable"

    await pipeline.enqueue(session, uuid.UUID(report["id"]))
    await session.commit()
    fake_ai.calls.clear()
    assert await analyse(report["id"], fake_ai, fake_store)
    assert "transcribe" not in [name for name, _ in fake_ai.calls]


async def test_media_arriving_during_analysis_triggers_another_pass(
    client: httpx.AsyncClient, citizen: dict[str, str], fake_ai: FakeAi, session: AsyncSession
) -> None:
    await accept_charter(client, citizen)
    report = await create(client, citizen, location=spot())

    async def new_media() -> None:
        async with get_sessionmaker()() as other, other.begin():
            await pipeline.enqueue(other, uuid.UUID(report["id"]))

    fake_ai.on_extract = new_media
    assert await analyse(report["id"], fake_ai)
    state = await session.scalar(text("SELECT state FROM ai.analysis WHERE report_id = :id"), {"id": report["id"]})
    assert state == "pending"
    fake_ai.on_extract = None
    assert await analyse(report["id"], fake_ai)
    state = await session.scalar(text("SELECT state FROM ai.analysis WHERE report_id = :id"), {"id": report["id"]})
    assert state == "done"


async def test_without_ai_service_rules_still_run(
    client: httpx.AsyncClient, citizen: dict[str, str], staff: Staff
) -> None:
    await accept_charter(client, citizen)
    report = await create(client, citizen, category="sos", text=None, location=spot())
    assert await analyse(report["id"], None)
    d = await detail(client, staff, report["id"])
    assert d["analysis_state"] == "done"
    assert set(d["analysis"]["steps"].values()) == {"disabled"}
    components = {c["key"]: c for c in d["analysis"]["priority"]["components"]}
    # A one-touch SOS without any detail is presumed to involve a life.
    assert components["lives"]["value"] == 0.7 and components["lives"]["detail"]["source"] == "category"
    status = (await client.get("/api/v1/staff/ai/status", headers=staff())).json()
    assert status == {"configured": False, "capabilities": {}}


async def test_ai_status_when_configured(client: httpx.AsyncClient, staff: Staff, fake_ai: FakeAi) -> None:
    status = (await client.get("/api/v1/staff/ai/status", headers=staff())).json()
    assert status["configured"] is True and status["capabilities"]["extract"]["ready"] is True


async def test_kpis_count_high_priority_and_pending(
    client: httpx.AsyncClient, citizen: dict[str, str], staff: Staff
) -> None:
    await accept_charter(client, citizen)
    operator = staff(gouvernorat=61)
    before = (await client.get("/api/v1/staff/kpis", headers=operator)).json()
    await create(client, citizen, category="drowning", text="un enfant se noie", location=spot())
    after = (await client.get("/api/v1/staff/kpis", headers=operator)).json()
    assert after["high_priority"] == before["high_priority"] + 1
    assert after["analysis_pending"] == before["analysis_pending"] + 1


# ---------------------------------------------------------------- settings (BR-20 weights are tunable)


async def test_settings_are_tunable_by_the_central_committee_only(
    client: httpx.AsyncClient, citizen: dict[str, str], staff: Staff, session: AsyncSession
) -> None:
    settings = (await client.get("/api/v1/staff/ai/settings", headers=staff())).json()
    assert settings["priority"]["weights"]["severity"] == 35 and settings["grouping"]["radius_m"]["fire"] == 500

    changed = {
        **settings,
        "priority": {
            **settings["priority"],
            "category_severity": {**settings["priority"]["category_severity"], "other": 1.0},
        },
    }
    assert (await client.put("/api/v1/staff/ai/settings", json=changed, headers=staff())).status_code == 403
    local = staff(roles=["central_committee"], gouvernorat=61)
    r = await client.put("/api/v1/staff/ai/settings", json=changed, headers=local)
    assert (r.status_code, r.json()["detail"]) == (403, "national_scope_required")
    central = staff(roles=["central_committee"], gouvernorat=None)
    # Phase 9 §2: the AI administrator (national) may tune them too; sysadmin no longer may.
    sysadmin = staff(roles=["sysadmin"], gouvernorat=None)
    assert (await client.put("/api/v1/staff/ai/settings", json=settings, headers=sysadmin)).status_code == 403
    regional_ai_admin = staff(roles=["ai_admin"], gouvernorat=61)
    r = await client.put("/api/v1/staff/ai/settings", json=settings, headers=regional_ai_admin)
    assert (r.status_code, r.json()["detail"]) == (403, "national_scope_required")
    ai_admin = staff(roles=["ai_admin"], gouvernorat=None)
    assert (await client.get("/api/v1/staff/ai/settings", headers=ai_admin)).status_code == 200
    r = await client.put("/api/v1/staff/ai/settings", json=settings, headers=ai_admin)
    assert r.status_code == 200, r.text
    broken = {**settings, "priority": {**settings["priority"], "weights": {"severity": 10}}}
    assert (await client.put("/api/v1/staff/ai/settings", json=broken, headers=central)).status_code == 422
    try:
        r = await client.put("/api/v1/staff/ai/settings", json=changed, headers=central)
        assert r.status_code == 200, r.text
        audited = await session.scalar(text("SELECT count(*) FROM audit.log WHERE action = 'ai.settings'"))
        assert audited >= 1
        await accept_charter(client, citizen)
        report = await create(client, citizen, category="other", text="x", location=spot())
        d = await detail(client, staff, report["id"])
        severity = next(c for c in d["analysis"]["priority"]["components"] if c["key"] == "severity")
        assert severity["value"] == 1.0
    finally:
        await client.put("/api/v1/staff/ai/settings", json=settings, headers=central)


# ---------------------------------------------------------------- pure rules


@pytest.mark.parametrize(
    ("sample", "language"),
    [
        ("حريق كبير قرب الغابة", "ar"),
        ("فما حريق برشا في الغابة", "ar"),
        ("famma 7ari9 kbir 9rib el ghaba", "ar_latn"),
        ("Il y a un incendie dans la forêt", "fr"),
        ("There is a fire near the road", "en"),
        ("123 !!", "other"),
    ],
)
def test_language_detection(sample: str, language: str) -> None:
    assert lexicon.detect_language(sample) == language


def test_keyword_signals() -> None:
    signals = lexicon.signals("فما زوز مجروحين و طفل عالق، ريحة قاز")
    assert signals["lives_at_risk"] and signals["injured"] and signals["hazards"] == ["gas"]
    assert lexicon.signals("Deux blessés, une personne décédée")["deaths"]
    assert not lexicon.signals("Un arbre est tombé sur la route")["lives_at_risk"]


def test_model_can_raise_but_never_lower_severity() -> None:
    settings = PrioritySettings()
    raised = scoring.Facts(
        category=Category.OTHER, reporter_kind="citizen", extraction={"category": "fire", "confidence": 0.9}
    )
    lowered = scoring.Facts(
        category=Category.FIRE, reporter_kind="citizen", extraction={"category": "other", "confidence": 0.9}
    )
    unsure = scoring.Facts(
        category=Category.OTHER, reporter_kind="citizen", extraction={"category": "fire", "confidence": 0.3}
    )

    def severity(facts: scoring.Facts) -> float:
        return next(c for c in scoring.priority(facts, 50, settings)["components"] if c["key"] == "severity")["value"]

    assert severity(raised) == 0.8 and severity(lowered) == 0.8 and severity(unsure) == 0.3


def test_credibility_bounds() -> None:
    worst = scoring.credibility(
        scoring.Facts(category=Category.FIRE, reporter_kind="anonymous", false_reports=9, accuracy_m=5000)
    )
    best = scoring.credibility(
        scoring.Facts(
            category=Category.FIRE,
            reporter_kind="citizen",
            useful_reports=9,
            stored_media=3,
            accuracy_m=5,
            corroborating_reporters=9,
        )
    )
    assert worst["score"] == 0 and best["score"] == 100
