"""AI5c: the commander's assistant learns — each decision linked to what followed, the learned ranking in shadow
compared with the rules' order on incidents it never saw, the decided orders as learning samples, and the targets of
design-ai5 §6 in the commander's model card."""

import random
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import httpx
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_system_sessionmaker
from app.modules.decision import outcomes, ranker
from app.modules.decision.models import CommandDecision
from app.modules.learning import service
from app.modules.learning.models import LearnedModel, Sample
from app.modules.ops.models import OpLevel
from tests import test_decision
from tests.test_command import fire_incident, fleet
from tests.test_decision import TATAOUINE, FakeEngine, FakeEnvironment

Staff = Callable[..., dict[str, str]]
NOW = datetime(2026, 7, 1, 12, tzinfo=UTC)
# The routing engine, weather and procedures library fixtures of the decision-support tests.
engine = test_decision.engine
environment = test_decision.environment
library = test_decision.library
KEYS = ["resources:fire_engine", "resources:ambulance", "alert:flood", "volunteers:first_aid", "escalation:crisis"]


def simulated(rng: random.Random, incident: uuid.UUID) -> list[CommandDecision]:
    """[SIM] One incident's decided proposals from a declared process: what the commander adopts depends on the
    situation, while the rules' order is shuffled (it knows nothing of it)."""
    category = rng.choice(["fire", "flood", "road"])
    injured, lives = rng.randint(0, 3), rng.random() < 0.4
    adopt = {
        "resources:fire_engine": category == "fire",
        "resources:ambulance": injured > 0,
        "alert:flood": category == "flood" and lives,
        "volunteers:first_aid": rng.random() < 0.15,
        "escalation:crisis": lives and injured >= 2,
    }
    ranks = list(range(len(KEYS)))
    rng.shuffle(ranks)
    rows = []
    for key, rank in zip(KEYS, ranks, strict=True):
        rows.append(
            CommandDecision(
                id=uuid.uuid4(),
                incident_id=incident,
                origin="rules",
                kind=key.split(":")[0],
                key=key,
                title={"ar": key, "fr": key},
                rationale={"ar": "-", "fr": "-"},
                confidence=rng.choice(["high", "medium", "low"]),
                proposal={"inputs": {}, "actions": []},
                features={
                    "category": category,
                    "injured": injured,
                    "lives_at_risk": lives,
                    "op_level": "normal",
                    "reports": rng.randint(1, 6),
                    "engaged": {"fire_engine": rng.randint(0, 2)},
                    "hazards": ["smoke"] if category == "fire" else [],
                    "hour": rng.randint(0, 23),
                    "rule_rank": rank,
                },
                simulated=True,
                status="adopted" if adopt[key] else "rejected",
                reason_code=None if adopt[key] else "not_needed",
                created_by="test",
                created_at=NOW,
                decided_by="test",
                decided_at=NOW + timedelta(minutes=5),
            )
        )
    return rows


# ---------------------------------------------------------------- pure functions


def test_label_learns_from_the_outcome() -> None:
    def row(status: str, reason: str | None = None, outcome: dict[str, Any] | None = None) -> CommandDecision:
        return CommandDecision(status=status, reason_code=reason, outcome=outcome)

    assert ranker.label_of(row("adopted")) == 1 and ranker.label_of(row("modified")) == 1
    assert ranker.label_of(row("rejected", "not_needed")) == 0
    # Rejected, yet the same resources were sent later: the proposal was needed.
    assert ranker.label_of(row("rejected", "not_needed", {"needed_later": True})) == 1
    # "Already done" says nothing about the rank; undecided rows neither.
    assert ranker.label_of(row("rejected", "already_done")) is None
    assert ranker.label_of(row("expired")) is None and ranker.label_of(row("proposed")) is None


def test_features_are_named_numbers_without_identifiers() -> None:
    (first, *_) = simulated(random.Random(1), uuid.uuid4())
    first.features["gouvernorat_code"] = 32
    x = ranker.features_of(first)
    assert x[f"key={first.key}"] == 1.0 and f"key={first.key}|category={first.features['category']}" in x
    assert not any(name.startswith("gouvernorat_code") or name == "hour" for name in x)
    assert any(name.startswith("day=") for name in x) and "engaged.fire_engine" in x


def test_outcome_of_a_decision() -> None:
    decided = NOW
    row = CommandDecision(key="resources:ambulance", decided_at=decided, features={"op_level": "normal"})
    incident = SimpleNamespace(
        closed_at=decided + timedelta(minutes=90),
        evaluation={"outcome": "resolved"},
        op_level=OpLevel.CRISIS,
    )
    orders = [
        (decided - timedelta(minutes=10), decided, None, "fire_engine"),  # before the decision: not counted
        (decided + timedelta(minutes=5), decided + timedelta(minutes=17), None, "ambulance"),
        (decided + timedelta(minutes=6), None, decided + timedelta(minutes=8), "water_tanker"),  # cancelled
    ]
    out = outcomes.outcome_of(row, incident, orders)  # type: ignore[arg-type]
    assert out["closed_after_min"] == 90.0 and out["result"] == "resolved"
    assert out["assignments_after"] == 1 and out["first_on_scene_min"] == 17.0
    assert out["escalated"] is True and out["needed_later"] is True
    assert outcomes.resource_kind("order:dispatch:boat") == "boat"
    assert outcomes.resource_kind("resources:location") is None and outcomes.resource_kind("alert:flood") is None
    other = CommandDecision(key="alert:flood", decided_at=decided, features={})
    assert outcomes.outcome_of(other, incident, orders)["needed_later"] is None  # type: ignore[arg-type]


def test_ranker_learns_what_the_rules_order_misses() -> None:
    rng = random.Random(5)
    examples = []
    for _ in range(300):
        for row in simulated(rng, uuid.UUID(int=rng.getrandbits(128))):
            e = ranker.example(row)
            assert e is not None
            examples.append(e)
    train = [e for e in examples if e.split == "train"]
    heldout = [e for e in examples if e.split == "heldout"]
    model = ranker.Ranker(ranker.fit(train))
    got = ranker.first_proposal(heldout, model)
    assert got["incidents"] >= 30
    assert got["model"] / got["incidents"] > 0.85
    assert got["model"] > got["rules"] + got["incidents"] // 5


# ---------------------------------------------------------------- with the database


async def _seed(count: int, seed: int) -> list[uuid.UUID]:
    rng = random.Random(seed)
    incidents = []
    async with get_system_sessionmaker()() as s, s.begin():
        for _ in range(count):
            iid = uuid.UUID(int=rng.getrandbits(128))
            await s.execute(
                text(
                    "INSERT INTO ops.incident (id, category, gouvernorat_code, opened_at, status, closed_at) "
                    "VALUES (:id, 'fire', :g, :at, 'closed', :closed)"
                ),
                {"id": iid, "g": TATAOUINE, "at": NOW, "closed": NOW + timedelta(hours=2)},
            )
            s.add_all(simulated(rng, iid))
            incidents.append(iid)
    return incidents


async def _clean(incidents: list[uuid.UUID]) -> None:
    async with get_system_sessionmaker()() as s, s.begin():
        await s.execute(text("DELETE FROM decision.command_decision"))
        await s.execute(delete(LearnedModel).where(LearnedModel.task == ranker.TASK))
        await s.execute(text("DELETE FROM ai.training_job WHERE task = :t"), {"t": ranker.TASK})
        if incidents:
            await s.execute(text("DELETE FROM ops.incident WHERE id = ANY(:ids)"), {"ids": incidents})


async def test_training_links_outcomes_and_keeps_the_ranker_in_shadow(
    client: httpx.AsyncClient, staff: Staff, session: AsyncSession
) -> None:
    await _clean([])
    async with get_system_sessionmaker()() as s, s.begin():
        job = await service.enqueue(s, ranker.TASK, "manual", "test", "Test")
        await service.run(s, job)
        assert job.state == "skipped" and job.result["skipped"] == "too_few_samples"

    incidents = await _seed(150, 3)
    try:
        async with get_system_sessionmaker()() as s, s.begin():
            job = await service.enqueue(s, ranker.TASK, "manual", "test", "Test")
            await service.run(s, job)
            assert job.state == "done", (job.result, job.error)
            result = job.result
        assert result["outcomes_linked"] == 150 * len(KEYS)
        assert result["promoted"] is True and result["primary"] > result["rules_top1"]
        async with get_system_sessionmaker()() as s:
            linked = await s.scalar(select(CommandDecision).where(CommandDecision.incident_id == incidents[0]).limit(1))
            assert linked is not None and linked.outcome is not None
            assert linked.outcome["closed_after_min"] == 115.0 and linked.outcome["assignments_after"] == 0
            # Linked once: nothing left to link until an incident is closed again.
            assert await outcomes.link(s) == 0
            model = await ranker.current(s)
            assert model is not None and model.primary_metric == "top1"
            ranking = model.metrics["ranking"]
            assert ranking["model"] > ranking["rules"] and model.metrics["model"]["accuracy"] > 0.8

        # Trained again on the same data, it does not beat itself: the current version stays.
        async with get_system_sessionmaker()() as s, s.begin():
            job = await service.enqueue(s, ranker.TASK, "manual", "test", "Test")
            await service.run(s, job)
            assert job.result["promoted"] is False and job.result["outcomes_linked"] == 0

        # The training centre lists it; the commander's card shows the ranking and the targets.
        overview = (await client.get("/api/v1/staff/learning", headers=staff(["sysadmin"], gouvernorat=None))).json()
        task = next(t for t in overview["tasks"] if t["task"] == ranker.TASK)
        assert task["current"]["metrics"]["ranking"]["incidents"] == ranking["incidents"]
        cards = await client.get("/api/v1/staff/ai/models", headers=staff(["ai_admin"], gouvernorat=None))
        assert cards.status_code == 200, cards.text
        commander = next(c for c in cards.json()["items"] if c["id"] == "commander")
        tables = {t["key"]: t for t in commander["measures"]}
        assert [r[1] for r in tables["commander_ranker"]["rows"]] == [str(ranking["incidents"]), "0"]
        targets = tables["commander_targets"]
        assert len(targets["rows"]) == 5 and targets["columns"][3] == "الحكم"
        assert targets["rows"][4][3] == "لم يُقَس بعد"  # nothing decided since the training yet
    finally:
        await _clean(incidents)


async def test_a_decided_order_becomes_a_learning_sample(
    client: httpx.AsyncClient,
    staff: Staff,
    session: AsyncSession,
    engine: FakeEngine,
    environment: FakeEnvironment,
) -> None:
    await fleet(client, staff, engine)
    incident_id = await fire_incident(client, staff)
    commander = staff(["ops_manager"], gouvernorat=TATAOUINE)
    said = "ابعثوا زوز صهاريج ماء، الرقم 98 123 456"
    r = await client.post(
        f"/api/v1/staff/incidents/{incident_id}/command", json={"text": said, "lang": "ar"}, headers=commander
    )
    assert r.status_code == 200, r.text
    card = r.json()["card"]
    r = await client.post(
        f"/api/v1/staff/command/decisions/{card['id']}",
        json={"verdict": "reject", "reason_code": "wrong_reading"},
        headers=commander,
    )
    assert r.status_code == 200, r.text
    async with get_system_sessionmaker()() as s:
        sample = await s.scalar(select(Sample).where(Sample.source == "order", Sample.source_id == card["id"]))
        assert sample is not None
        assert "98 123 456" not in sample.text and "<PHONE>" in sample.text
        assert sample.label["wrong_reading"] is True and sample.label["reading_confirmed"] is False
        assert sample.label["reading"]["resource_kind"] == "water_tanker"
        assert sample.label_origin == "commander" and sample.group_key == incident_id
        await s.execute(delete(Sample).where(Sample.source == "order"))
        await s.commit()
    # A rules proposal is not an order: no sample.
    board = (await client.get(f"/api/v1/staff/incidents/{incident_id}/command", headers=commander)).json()
    rules = next(c for c in board["proposals"] if c["origin"] == "rules")
    decide = f"/api/v1/staff/command/decisions/{rules['id']}"
    r = await client.post(decide, json={"verdict": "adopt"}, headers=commander)
    assert r.status_code == 200
    assert await session.scalar(text("SELECT count(*) FROM ai.learning_sample WHERE source = 'order'")) == 0
