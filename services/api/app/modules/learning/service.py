"""The training centre: queue, schedule and run the trainings (docs/learning.md §3-4).

The system administrator (or the AI administrator) launches a training from the dashboard, or turns on its schedule
(setting ``learning.schedule``: every N days). The worker runs the queued jobs one at a time; a job that needs a GPU
(fire and smoke detector) waits for the trainer, which sends its figures back. Every launch and result is audited.

    python -m app.modules.learning.service run report_category    # queues and runs one training as the system
"""

import argparse
import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import get_store
from app.modules.audit import service as audit
from app.modules.learning import samples, tasks
from app.modules.learning.models import LearnedModel, Sample, TrainingJob
from app.modules.settings import domain as settings_domain
from app.modules.settings import service as settings

log = structlog.get_logger()

ACTIVE = ("queued", "running", "waiting_trainer")
# Samples refreshed before a training, at most (each call of samples.sync is one bounded batch).
SYNC_ROUNDS = 40
MANIFEST_LINK_S = 6 * 3600


async def enqueue(session: AsyncSession, task: str, trigger: str, actor: str, actor_name: str) -> TrainingJob:
    if task not in tasks.TASKS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown_task")
    busy = await session.scalar(select(TrainingJob.id).where(TrainingJob.task == task, TrainingJob.state.in_(ACTIVE)))
    if busy is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "training_in_progress")
    job = TrainingJob(task=task, trigger=trigger, requested_by=actor, requested_by_name=actor_name)
    session.add(job)
    await session.flush()
    await audit.record(
        session,
        actor=actor,
        action="learning.launch",
        target=f"training:{job.id}",
        details={"task": task, "trigger": trigger},
    )
    return job


async def sync_samples(session: AsyncSession) -> int:
    total = 0
    for _ in range(SYNC_ROUNDS):
        added = await samples.sync(session)
        total += added
        if added < samples.BATCH:
            break
    return total


def link(key: str) -> str:
    return get_store().presign_get(key, expires_s=MANIFEST_LINK_S)


async def _work(session: AsyncSession, job: TrainingJob, task: tasks.Task) -> tuple[str, dict[str, Any], Any]:
    if task.runner == "trainer":
        prepared = await tasks.vision_dataset(session, link)
        result = {k: v for k, v in prepared.items() if k != "manifest"}
        if not prepared["images"]:
            return "skipped", {**result, "skipped": "no_images"}, None
        return "waiting_trainer", result, None
    synced = await sync_samples(session)
    if task.key == "derja_words":
        return "done", {"synced": synced, **await tasks.derja_words(session)}, None
    actor_name = "system" if job.trigger == "schedule" else job.requested_by_name
    trained, model = await tasks.train_text(session, task, actor_name)
    return ("skipped" if model is None else "done"), {"synced": synced, **trained}, model.id if model else None


async def run(session: AsyncSession, job: TrainingJob) -> None:
    """Runs one job to its end state (the caller commits)."""
    task = tasks.TASKS[job.task]
    job.state, job.started_at = "running", datetime.now(UTC)
    await session.flush()
    try:
        # A savepoint: a failed training rolls back its own writes and still records the failure on the job.
        async with session.begin_nested():
            state, result, model_id = await _work(session, job, task)
        job.state, job.result, job.model_id = state, result, model_id
    except Exception as exc:
        log.exception("learning.job_failed", task=job.task)
        job.state, job.error = "failed", type(exc).__name__
    if job.state != "waiting_trainer":
        job.finished_at = datetime.now(UTC)
    await session.flush()
    await audit.record(
        session,
        actor=audit.SYSTEM_ACTOR,
        action="learning.result",
        target=f"training:{job.id}",
        details={"task": job.task, "state": job.state, **{k: v for k, v in job.result.items() if k != "candidates"}},
    )


async def run_next(session: AsyncSession) -> TrainingJob | None:
    """Claims and runs the oldest queued job, if any."""
    job = await session.scalar(
        select(TrainingJob)
        .where(TrainingJob.state == "queued")
        .order_by(TrainingJob.requested_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if job is None:
        return None
    await run(session, job)
    return job


async def due(session: AsyncSession, now: datetime) -> list[str]:
    """Scheduled tasks whose last launch is older than their period: queued as the system."""
    schedule = await settings.get(session, settings_domain.LEARNING_SCHEDULE)
    queued = []
    for key, entry in (schedule or {}).items():
        if key not in tasks.TASKS or not entry.get("enabled"):
            continue
        last = await session.scalar(select(func.max(TrainingJob.requested_at)).where(TrainingJob.task == key))
        if last is not None and last > now - timedelta(days=int(entry.get("every_days", 7))):
            continue
        busy = await session.scalar(
            select(TrainingJob.id).where(TrainingJob.task == key, TrainingJob.state.in_(ACTIVE))
        )
        if busy is None:
            await enqueue(session, key, "schedule", audit.SYSTEM_ACTOR, "system")
            queued.append(key)
    return queued


async def trainer_result(
    session: AsyncSession, job: TrainingJob, metrics: dict[str, Any], model_name: str, actor: str, actor_name: str
) -> TrainingJob:
    """The GPU trainer's figures for a fire and smoke job. The detector itself is installed by an administrator
    after the committee's review (services/vision/README.md); nothing is swapped here."""
    if job.state != "waiting_trainer":
        raise HTTPException(status.HTTP_409_CONFLICT, "not_waiting_trainer")
    job.result = {**job.result, "trainer": {"model": model_name, "metrics": metrics, "by": actor_name}}
    job.state, job.finished_at = "done", datetime.now(UTC)
    await session.flush()
    await audit.record(
        session,
        actor=actor,
        action="learning.trainer_result",
        target=f"training:{job.id}",
        details={"model": model_name, "metrics": metrics},
    )
    return job


def _job(job: TrainingJob) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "task": job.task,
        "trigger": job.trigger,
        "state": job.state,
        "requested_by_name": job.requested_by_name,
        "requested_at": job.requested_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "result": job.result,
        "error": job.error,
    }


def _model(model: LearnedModel | None) -> dict[str, Any] | None:
    if model is None:
        return None
    return {
        "version": model.version,
        "algorithm": model.algorithm,
        "metrics": model.metrics,
        "primary_metric": model.primary_metric,
        "train_samples": model.train_samples,
        "heldout_samples": model.heldout_samples,
        "trained_by_name": model.trained_by_name,
        "trained_at": model.trained_at,
    }


async def jobs(session: AsyncSession, task: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    query = select(TrainingJob).order_by(TrainingJob.requested_at.desc()).limit(limit)
    if task:
        query = query.where(TrainingJob.task == task)
    return [_job(j) for j in await session.scalars(query)]


async def overview(session: AsyncSession) -> dict[str, Any]:
    schedule = await settings.get(session, settings_domain.LEARNING_SCHEDULE) or {}
    by_origin = dict(
        (await session.execute(select(Sample.label_origin, func.count()).group_by(Sample.label_origin))).all()
    )
    by_split = dict((await session.execute(select(Sample.split, func.count()).group_by(Sample.split))).all())
    items = []
    for key, task in tasks.TASKS.items():
        last = await session.scalar(
            select(TrainingJob).where(TrainingJob.task == key).order_by(TrainingJob.requested_at.desc()).limit(1)
        )
        items.append(
            {
                "task": key,
                "runner": task.runner,
                "primary_metric": task.primary_metric,
                "schedule": schedule.get(key, {"enabled": False, "every_days": 7}),
                "last_job": _job(last) if last is not None else None,
                "current": _model(await tasks.current_model(session, key)),
            }
        )
    return {
        "samples": {
            "total": sum(by_origin.values()),
            "by_origin": by_origin,
            "by_split": by_split,
        },
        "tasks": items,
    }


async def dataset_rows(session: AsyncSession) -> list[dict[str, Any]]:
    """The anonymised report samples, for a training outside the platform (export, audited by the caller)."""
    out = []
    for s in await session.scalars(
        select(Sample).where(Sample.source == samples.SOURCE_REPORT).order_by(Sample.created_at)
    ):
        out.append(
            {
                "id": str(s.id),
                "text": s.text,
                "category": s.label.get("category"),
                "lives_at_risk": s.label.get("lives_at_risk"),
                "rejected": s.label.get("rejected"),
                "confirmed": ",".join(s.label.get("confirmed") or []),
                "origin": s.label_origin,
                "split": s.split,
            }
        )
    return out


async def _main(task: str) -> None:
    from app.core.db import dispose_engine, get_system_sessionmaker

    try:
        async with get_system_sessionmaker()() as session:
            job = await enqueue(session, task, "manual", audit.SYSTEM_ACTOR, "system")
            await run(session, job)
            await session.commit()
            print({"state": job.state, **{k: v for k, v in job.result.items() if k != "candidates"}})
    finally:
        await dispose_engine()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["run"])
    parser.add_argument("task", choices=sorted(tasks.TASKS))
    args = parser.parse_args()
    asyncio.run(_main(args.task))
