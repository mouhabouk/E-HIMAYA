"""The training centre (docs/learning.md): samples from final reports, the operator's confirmation, the trainings and
their schedule, and the samples' retention."""

import random
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_system_sessionmaker
from app.modules.learning import samples, service, tasks, textmodel
from app.modules.learning.anonymize import anonymize
from app.modules.learning.models import LearnedModel, Sample, TrainingJob
from app.modules.privacy import retention
from app.modules.reports.models import Report
from app.modules.settings import domain as settings_domain
from app.modules.settings import service as settings_service
from tests.conftest import accept_charter, report_body

Staff = Callable[..., dict[str, str]]

# ---------------------------------------------------------------- pure functions


def test_anonymize_keeps_what_the_model_needs() -> None:
    text = (
        "اسمي Sami، حريق في الطابق 2 و3 عالقين. اتصلوا 98 123 456 او +216 22.333.444، "
        "sami.benali@mail.tn https://x.tn/a الكرهبة 123 تونس 4567 بطاقة 08123456 Ben Ali"
    )
    out = anonymize(text, ["Sami", "Ben Ali"])
    for gone in ("Sami", "98 123 456", "22.333.444", "sami.benali", "https://", "4567", "08123456", "Ali"):
        assert gone not in out, gone
    for tag in ("<NAME>", "<PHONE>", "<EMAIL>", "<URL>", "<PLATE>", "<NUMBER>"):
        assert tag in out, tag
    # Small numbers carry the meaning: they stay.
    assert "الطابق 2" in out and "3 عالقين" in out
    # Short name parts are left alone (they would eat ordinary words).
    assert anonymize("wa9t el 7ri9", ["El"]) == "wa9t el 7ri9"


def test_split_is_fixed_and_one_in_five() -> None:
    keys = [str(uuid.UUID(int=i)) for i in range(2000)]
    assert [samples.split_of(k) for k in keys] == [samples.split_of(k) for k in keys]
    heldout = sum(samples.split_of(k) == "heldout" for k in keys)
    assert 300 < heldout < 500


def test_confirmed_labels_survive_weak_ones() -> None:
    current = {"category": "flood", "lives_at_risk": True, "rejected": False, "confirmed": ["category"]}
    weak = {"category": "fire", "lives_at_risk": False, "rejected": True}
    assert samples.merged(current, weak) == {
        "category": "flood",
        "lives_at_risk": False,
        "rejected": True,
        "confirmed": ["category"],
    }
    assert samples.merged(None, weak)["confirmed"] == []


def test_weak_labels_prefer_the_language_model() -> None:
    report = Report(category="other", status="rejected")
    assert samples.weak_labels(report, None) == {"category": "other", "lives_at_risk": None, "rejected": True}
    read = samples.weak_labels(report, {"category": "flood", "lives_at_risk": True})
    assert read == {"category": "flood", "lives_at_risk": True, "rejected": True}
    # An unknown category from the model is ignored.
    assert samples.weak_labels(report, {"category": "volcano"})["category"] == "other"


def test_text_model_learns_and_scores() -> None:
    fire = ["حريق كبير في الغابة", "7ri9 9rib dar", "دخان كثيف و نار", "incendie forêt fumée", "النار شعلت فالكوجينة"]
    flood = ["فيضان في الوادي", "el ma tla3 fi dar", "مياه غمرت الطريق", "inondation route coupée", "الواد فاض"]
    texts, labels = fire * 4 + flood * 4, ["fire"] * 20 + ["flood"] * 20
    params = textmodel.fit(texts, labels, [1.0] * 40)
    model = textmodel.Classifier(params)
    assert model.predict("حريق و دخان قرب الدار") == "fire"
    assert model.predict("فيضان الواد غمر الطريق") == "flood"
    assert abs(sum(model.probabilities("نار").values()) - 1.0) < 1e-6
    scores = textmodel.scores(["fire", "flood", "fire"], ["fire", "flood", "flood"])
    assert scores["accuracy"] == pytest.approx(2 / 3, abs=1e-3)
    assert 0 < scores["macro_f1"] < 1


def test_tasks_match_the_schedule_setting() -> None:
    assert tuple(tasks.TASKS) == settings_domain.LEARNING_TASKS
    validate = settings_domain.VALIDATORS[settings_domain.LEARNING_SCHEDULE]
    out = validate({"fire_smoke": {"enabled": True, "every_days": 14}})
    assert out["fire_smoke"] == {"enabled": True, "every_days": 14}
    assert out["report_category"] == {"enabled": False, "every_days": 7}
    bad: object
    for bad in ({"unknown": {"enabled": True}}, {"derja_words": {"enabled": True, "every_days": 0}}, []):
        with pytest.raises(ValueError):
            validate(bad)


# ---------------------------------------------------------------- with the database


async def _rejected_report(client: httpx.AsyncClient, citizen: dict[str, str], staff: Staff, text: str) -> str:
    await accept_charter(client, citizen)
    r = await client.post("/api/v1/reports", json=report_body(text=text), headers=citizen)
    assert r.status_code == 201, r.text
    report_id = r.json()["id"]
    r = await client.post(
        f"/api/v1/staff/reports/{report_id}/status", json={"status": "rejected", "note": "faux"}, headers=staff()
    )
    assert r.status_code == 200, r.text
    return str(report_id)


async def test_operator_confirms_the_reading_of_a_final_report(
    client: httpx.AsyncClient, citizen: dict[str, str], staff: Staff, session: AsyncSession
) -> None:
    await accept_charter(client, citizen)
    r = await client.post("/api/v1/reports", json=report_body(text="دخان قرب المخزن 98123456"), headers=citizen)
    open_id = r.json()["id"]
    assert (await client.get(f"/api/v1/staff/reports/{open_id}/learning-label", headers=staff())).status_code == 409

    report_id = await _rejected_report(client, citizen, staff, "حريق صغير، اتصلوا 98123456")
    url = f"/api/v1/staff/reports/{report_id}/learning-label"
    read = await client.get(url, headers=staff())
    assert read.status_code == 200, read.text
    assert read.json() | {"lives_at_risk": None} == {
        "category": "fire",
        "lives_at_risk": None,
        "rejected": True,
        "confirmed": [],
    }
    put = await client.put(url, json={"category": "other", "lives_at_risk": False}, headers=staff())
    assert put.status_code == 200, put.text
    assert put.json() == {
        "category": "other",
        "lives_at_risk": False,
        "rejected": True,
        "confirmed": ["category", "lives_at_risk"],
    }

    sample = await session.scalar(select(Sample).where(Sample.source_id == report_id))
    assert sample is not None and sample.label_origin == "operator"
    assert "98123456" not in sample.text and "<PHONE>" in sample.text
    # A later refresh keeps the operator's labels.
    report = await session.get(Report, uuid.UUID(report_id))
    assert report is not None
    refreshed = await samples.upsert(session, report)
    assert refreshed is not None and refreshed.label["category"] == "other"
    await session.rollback()

    # A citizen, an analyst or another region cannot label.
    assert (await client.put(url, json={"rejected": False}, headers=citizen)).status_code in (401, 403)
    assert (await client.put(url, json={"rejected": False}, headers=staff(gouvernorat=11))).status_code in (403, 404)


async def test_only_the_administrators_launch_trainings(client: httpx.AsyncClient, staff: Staff) -> None:
    body = {"task": "derja_words"}
    assert (await client.post("/api/v1/staff/learning/jobs", json=body, headers=staff())).status_code == 403
    regional = staff(["sysadmin"], gouvernorat=61)
    assert (await client.post("/api/v1/staff/learning/jobs", json=body, headers=regional)).status_code == 403
    committee = staff(["central_committee"], gouvernorat=None)
    assert (await client.get("/api/v1/staff/learning", headers=committee)).status_code == 200
    assert (await client.post("/api/v1/staff/learning/jobs", json=body, headers=committee)).status_code == 403

    sysadmin = staff(["sysadmin"], gouvernorat=None)
    first = await client.post("/api/v1/staff/learning/jobs", json=body, headers=sysadmin)
    assert first.status_code == 202, first.text
    again = await client.post("/api/v1/staff/learning/jobs", json=body, headers=sysadmin)
    assert again.status_code == 409 and again.json()["detail"] == "training_in_progress"

    async with get_system_sessionmaker()() as s, s.begin():
        job = await s.get(TrainingJob, uuid.UUID(first.json()["id"]))
        assert job is not None
        await service.run(s, job)
        assert job.state == "done" and "candidates" in job.result
    jobs = (await client.get("/api/v1/staff/learning/jobs?task=derja_words", headers=sysadmin)).json()
    assert jobs[0]["id"] == first.json()["id"] and jobs[0]["state"] == "done"
    overview = (await client.get("/api/v1/staff/learning", headers=sysadmin)).json()
    assert [t["task"] for t in overview["tasks"]] == list(tasks.TASKS)


_FIRE = ["حريق", "دخان", "نار", "7ri9", "dokhan", "incendie", "شعلت", "fumée"]
_FLOOD = ["فيضان", "مياه", "الواد", "fidhan", "el ma", "inondation", "غمرت", "سيول"]
_FILLER = ["قرب", "الدار", "fi", "el houma", "route", "الطريق", "برشا", "توا", "près", "kbir"]


async def test_text_training_is_promoted_only_when_better(session: AsyncSession) -> None:
    rng = random.Random(7)
    async with get_system_sessionmaker()() as s, s.begin():
        for i in range(120):
            category = "fire" if i % 2 else "flood"
            words = rng.sample(_FIRE if category == "fire" else _FLOOD, 2) + rng.sample(_FILLER, 3)
            rng.shuffle(words)
            source_id = f"t-{uuid.uuid4()}"
            s.add(
                Sample(
                    source=samples.SOURCE_REPORT,
                    source_id=source_id,
                    text=" ".join(words),
                    label={"category": category, "lives_at_risk": None, "rejected": False, "confirmed": []},
                    label_origin="weak",
                    split=samples.split_of(source_id),
                )
            )

    async with get_system_sessionmaker()() as s, s.begin():
        job = await service.enqueue(s, "report_category", "manual", "test", "Test")
        await service.run(s, job)
        assert job.state == "done", job.result
        assert job.result["promoted"] is True and job.result["primary"] > 0.8
        first = job.result["version"]
    async with get_system_sessionmaker()() as s, s.begin():
        # The same data again cannot beat itself: the new version is kept as rejected, the current one stays.
        job = await service.enqueue(s, "report_category", "manual", "test", "Test")
        await service.run(s, job)
        assert job.result["promoted"] is False
        current = await tasks.current_model(s, "report_category")
        assert current is not None and current.version == first
        rejected = await s.scalar(
            select(LearnedModel).where(LearnedModel.task == "report_category", LearnedModel.version == first + 1)
        )
        assert rejected is not None and rejected.state == "rejected"
        assert rejected.metrics["current_version"] == first


async def test_too_few_samples_skips(session: AsyncSession) -> None:
    async with get_system_sessionmaker()() as s, s.begin():
        job = await service.enqueue(s, "report_lives", "manual", "test", "Test")
        await service.run(s, job)
        assert job.state in ("skipped", "done")
        if job.state == "skipped":
            assert job.result["skipped"] == "too_few_samples" and job.model_id is None


async def test_fire_smoke_waits_for_the_trainer(client: httpx.AsyncClient, staff: Staff) -> None:
    sysadmin = staff(["sysadmin"], gouvernorat=None)
    async with get_system_sessionmaker()() as s, s.begin():
        await s.execute(update(TrainingJob).where(TrainingJob.task == "fire_smoke").values(state="done"))
        job = await service.enqueue(s, "fire_smoke", "manual", "test", "Test")
        await service.run(s, job)
        job_id, state = job.id, job.state
    assert state in ("skipped", "waiting_trainer")
    url = f"/api/v1/staff/learning/jobs/{job_id}/trainer-result"
    body = {"model": "yolo-fire-v2", "metrics": {"map50": 0.71}}
    r = await client.post(url, json=body, headers=sysadmin)
    if state == "skipped":
        assert r.status_code == 409
        return
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "done"
    assert (await client.post(url, json=body, headers=sysadmin)).status_code == 409


async def _set_schedule(client: httpx.AsyncClient, headers: dict[str, str], value: dict[str, object]) -> None:
    items = (await client.get("/api/v1/staff/settings", headers=headers)).json()["items"]
    version = next(i["version"] for i in items if i["key"] == settings_domain.LEARNING_SCHEDULE)
    r = await client.put(
        f"/api/v1/staff/settings/{settings_domain.LEARNING_SCHEDULE}",
        json={"value": value, "version": version, "reason": "test du calendrier"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    settings_service.invalidate(settings_domain.LEARNING_SCHEDULE)


async def test_schedule_queues_due_trainings(client: httpx.AsyncClient, staff: Staff) -> None:
    ai_admin = staff(["ai_admin"], gouvernorat=None)
    now = datetime.now(UTC)
    async with get_system_sessionmaker()() as s, s.begin():
        await s.execute(
            update(TrainingJob)
            .where(TrainingJob.task == "derja_words")
            .values(state="done", requested_at=now - timedelta(days=30))
        )
    await _set_schedule(client, ai_admin, {"derja_words": {"enabled": True, "every_days": 7}})
    try:
        async with get_system_sessionmaker()() as s, s.begin():
            assert await service.due(s, now) == ["derja_words"]
            # Queued now: not due again until its period has passed.
            assert await service.due(s, now) == []
            await s.execute(delete(TrainingJob).where(TrainingJob.task == "derja_words", TrainingJob.state == "queued"))
    finally:
        await _set_schedule(client, ai_admin, {})


async def test_samples_go_with_the_report(
    client: httpx.AsyncClient, citizen: dict[str, str], staff: Staff, session: AsyncSession
) -> None:
    report_id = await _rejected_report(client, citizen, staff, "نار في الغابة")
    async with get_system_sessionmaker()() as s, s.begin():
        assert await service.sync_samples(s) >= 1
        orphan = f"gone-{uuid.uuid4()}"
        s.add(Sample(source=samples.SOURCE_REPORT, source_id=orphan, text="x", label={}, split="train"))
    async with get_system_sessionmaker()() as s, s.begin():
        await retention.purge_learning_samples(s, get_settings(), datetime.now(UTC))
        assert await s.scalar(select(Sample).where(Sample.source_id == report_id)) is not None
        assert await s.scalar(select(Sample).where(Sample.source_id == orphan)) is None
        await s.execute(update(Report).where(Report.id == uuid.UUID(report_id)).values(anonymised_at=datetime.now(UTC)))
        await retention.purge_learning_samples(s, get_settings(), datetime.now(UTC))
        assert await s.scalar(select(Sample).where(Sample.source_id == report_id)) is None
