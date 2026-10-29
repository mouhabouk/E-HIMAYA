"""Model cards and the drowning model in shadow (L5c, docs/phase-l/design-l5.md §4.1 and §4.2): one card per model
with its figures, small samples flagged, thresholds and the committee's decisions (AI-01); the PDF; the shadow model
trained on [SIM] days, applied by the daily computation beside the rules, shown to staff only and compared."""

import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_system_sessionmaker
from app.modules.coastal import risk, service, shadow
from app.modules.modelcards import service as cards
from tests.test_coastal import NOW, PUBLIC, SWELL_DAY, URL, beaches, sim_marine  # noqa: F401 (fixtures)

Staff = Callable[..., dict[str, str]]
MODELS = "/api/v1/staff/ai/models"
REPO = Path(__file__).resolve().parents[3]


@pytest.fixture
def quick_training(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shadow, "TRAIN_DAYS", 4000)
    monkeypatch.setattr(shadow, "TEST_DAYS", 2000)


def test_shadow_model_learns_the_declared_process(quick_training: None) -> None:
    rules = risk.DEFAULT_RULES
    assert shadow.simulate(50, 3, rules) == shadow.simulate(50, 3, rules)
    params, metrics = shadow.train(7, rules)
    assert params["features"] == list(shadow.FEATURES) and len(params["coef"]) == len(shadow.FEATURES)
    assert 0 < params["cutoffs"]["yellow"] < params["cutoffs"]["red"] < 1
    # It learns the [SIM] process at least as well as the rules rank it, and flags as many days as they do.
    assert metrics["simulated"] and metrics["auc"]["model"] >= metrics["auc"]["rules"] - 0.03
    flagged = {k: v["yellow"] + v["red"] for k, v in metrics["flagged"].items()}
    assert abs(flagged["model"] - flagged["rules"]) < 0.05
    calm = risk.DayInputs(day=SWELL_DAY, wave_height_m=0.2, current_kmh=0.2, guarded=True, crowd="low")
    storm = risk.DayInputs(day=SWELL_DAY, wave_height_m=3.0, current_kmh=2.5, guarded=False, crowd="high", incidents=3)
    assert shadow.probability(params, calm, rules) < shadow.probability(params, storm, rules)
    assert shadow.level(params, shadow.probability(params, storm, rules)) == "red"


def test_card_measures_match_the_services() -> None:
    fetch = REPO / "services/vision/models/fetch_models.py"
    if not fetch.exists():
        pytest.skip("services/vision is not next to the API (container image)")
    source = fetch.read_text()
    fire = re.search(r'"name": "(ehimaya-fire-smoke-yolox-tiny)",\s*"version": "([^"]+)"', source)
    person = re.search(r'"name": "(yolox-tiny-coco-person)",\s*"version": "([^"]+)"', source)
    assert fire and f"{fire[1]} {fire[2]}" == cards.FIRE_SMOKE_VERSION
    assert person and f"{person[1]} {person[2]}" == cards.PERSON_VERSION
    # The copies the API ships are the outputs of the evaluation scripts, unchanged.
    measured = json.loads((REPO / "services/vision/eval/conditions-results.json").read_text())
    assert json.loads((cards.MEASURES / "vision_conditions.json").read_text()) == measured
    ai_results = REPO / "services/ai/eval/reports-results.json"
    if ai_results.exists():
        assert json.loads((cards.MEASURES / "reports.json").read_text()) == json.loads(ai_results.read_text())


async def test_cards_decisions_and_pdf(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession, quick_training: None
) -> None:
    assert (await client.get(MODELS, headers=staff(["operator"], gouvernorat=None))).status_code == 403
    regional = await client.get(MODELS, headers=staff(["ai_admin"], gouvernorat=61))
    assert (regional.status_code, regional.json()["detail"]) == (403, "national_scope_required")

    ai_admin = staff(["ai_admin"], gouvernorat=None)
    listed = await client.get(MODELS, headers=ai_admin)
    assert listed.status_code == 200, listed.text
    items = {c["id"]: c for c in listed.json()["items"]}
    assert list(items) == list(cards.ORDER)
    fire = items["fire_smoke"]
    assert fire["name"] == "كاشف النار والدخان" and fire["use"] and fire["limits"] and fire["data"]
    tables = {t["key"]: t for t in fire["measures"]}
    assert {"overall", "conditions_fire", "conditions_smoke", "hard_negatives"} <= set(tables)
    # Every condition under 30 images is flagged, and the note says so.
    conditions = tables["conditions_fire"]
    assert conditions["measured_on"] and conditions["small_rows"] and conditions["note"]
    assert [t["key"] for t in fire["thresholds"]] == ["vision_min_confidence", "vision_alert_confidence"]
    assert items["plan_reading"]["thresholds"][0]["value"] is True
    assert not fire["can_decide"] and not items["drowning"]["can_decide"] and items["drowning"]["can_train"]

    # French words for a French reader.
    fr = (await client.get(MODELS, params={"lang": "fr"}, headers=ai_admin)).json()["items"][0]
    assert fr["name"] == "Détecteur de feu et de fumée"

    # The shadow model: trained by the AI administrator, audited, measured against the rules on other [SIM] days.
    trained = await client.post(f"{MODELS}/drowning/train", json={"seed": 11}, headers=ai_admin)
    assert trained.status_code == 201, trained.text
    drowning = trained.json()
    assert drowning["version"].startswith("v") and drowning["simulated"] and drowning["status"] == "shadow"
    assert next(t for t in drowning["measures"] if t["key"] == "drowning")["simulated"]
    assert await session.scalar(text("SELECT count(*) FROM audit.log WHERE action = 'ai.model_trained'"))

    # The committee approves the card as it saw it; the AI administrator cannot.
    committee = staff(["central_committee"], gouvernorat=None)
    body = {"decision": "approved", "version": items["report_reading"]["version"], "reference": "PV 2026/07"}
    assert (await client.post(f"{MODELS}/report_reading/decisions", json=body, headers=ai_admin)).status_code == 403
    stale = await client.post(f"{MODELS}/report_reading/decisions", json={**body, "version": "old"}, headers=committee)
    assert (stale.status_code, stale.json()["detail"]) == (409, "model_changed")
    unknown = await client.post(f"{MODELS}/nope/decisions", json=body, headers=committee)
    assert unknown.status_code == 404
    approved = await client.post(f"{MODELS}/report_reading/decisions", json=body, headers=committee)
    assert approved.status_code == 201, approved.text
    card = approved.json()
    assert card["status"] == "approved" and card["decisions"][0]["reference"] == "PV 2026/07"
    assert card["decisions"][0]["thresholds"] == {"suggestion_min_confidence": 0.7}
    logged = await session.scalar(
        text("SELECT reason FROM audit.log WHERE action = 'ai.model_decision' ORDER BY id DESC LIMIT 1")
    )
    assert logged == "PV 2026/07"

    # A threshold changed after the approval: the card says it waits for a new one.
    settings = (await client.get("/api/v1/staff/ai/settings", headers=committee)).json()
    changed = {**settings, "priority": {**settings["priority"], "suggestion_min_confidence": 0.8}}
    try:
        assert (await client.put("/api/v1/staff/ai/settings", json=changed, headers=committee)).status_code == 200
        now = {c["id"]: c for c in (await client.get(MODELS, headers=ai_admin)).json()["items"]}
        assert now["report_reading"]["status"] == "changed"
    finally:
        await client.put("/api/v1/staff/ai/settings", json=settings, headers=committee)
    withdrawn = await client.post(
        f"{MODELS}/report_reading/decisions", json={**body, "decision": "withdrawn"}, headers=committee
    )
    assert withdrawn.json()["status"] == "withdrawn"

    pdf = await client.get(f"{MODELS}/fire_smoke/card.pdf", headers=ai_admin)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert (await client.get(f"{MODELS}/nope/card.pdf", headers=ai_admin)).status_code == 404
    assert await session.scalar(text("SELECT count(*) FROM audit.log WHERE action = 'ai.model_card_exported'"))


async def test_shadow_beside_the_rules_for_staff_only(
    client: httpx.AsyncClient,
    staff: Staff,
    session: AsyncSession,
    beaches: dict[str, Any],  # noqa: F811
    sim_marine: None,  # noqa: F811
    quick_training: None,
) -> None:
    north = beaches["ids"]["شاطئ الكورنيش"]
    async with get_system_sessionmaker()() as system:
        params, metrics = shadow.train(5, risk.DEFAULT_RULES)
        model = await shadow.store(system, 5, params, metrics, "test")
        await system.commit()
    await service.refresh(get_system_sessionmaker(), NOW)
    # The beach card lists today and the next days: compute today too (no marine hours today: calm defaults).
    await service.refresh(get_system_sessionmaker(), datetime.now(UTC))
    row = (
        await session.execute(
            text(
                "SELECT level, shadow_level, shadow_p, shadow_version FROM coastal.beach_day "
                "WHERE feature_id = :f AND day = :d"
            ),
            {"f": north, "d": SWELL_DAY},
        )
    ).one()
    assert row.shadow_version == model.version and row.shadow_level in risk.LEVELS and 0 <= row.shadow_p <= 1

    room = staff(["operator"], gouvernorat=None)
    staff_days = (await client.get(f"{URL}/beaches/{north}", headers=room)).json()["days"]
    assert staff_days[0]["shadow"]["version"] == model.version
    # The citizen never sees the shadow.
    public_days = (await client.get(f"{PUBLIC}/beaches/{north}")).json()["days"]
    assert all(d["shadow"] is None for d in public_days)

    async with get_system_sessionmaker()() as system:
        compared = await shadow.comparison(system, SWELL_DAY)
    assert compared["total"]["beaches"] >= 3
    total = compared["total"]
    assert total["same"] + total["model_higher"] + total["model_lower"] == total["beaches"]
