"""The training centre (docs/learning.md): trainings, their schedule and results, the anonymised data set, and the
operator's confirmation of a report's reading."""

import csv
import io
import json
import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service as audit
from app.modules.audit.service import actor_of
from app.modules.learning import samples, service, tasks
from app.modules.learning.models import TrainingJob
from app.modules.reports import jurisdiction
from app.modules.reports.domain import Category, Status
from app.modules.reports.staff_router import WRITE_ROLES

router = APIRouter(prefix="/api/v1/staff", tags=["learning"])

# The system administrator chooses and launches the trainings (Yamen, 2026-10-29); the AI administrator too.
LAUNCH_ROLES = (Role.SYSADMIN, Role.AI_ADMIN)
Reader = Annotated[Principal, Depends(require_roles(*LAUNCH_ROLES, Role.CENTRAL_COMMITTEE))]
Launcher = Annotated[Principal, Depends(require_roles(*LAUNCH_ROLES))]
Labeller = Annotated[Principal, Depends(require_roles(*WRITE_ROLES))]
Session = Annotated[AsyncSession, Depends(get_session)]


def _national(principal: Principal) -> None:
    if not principal.is_national:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "national_scope_required")


class LaunchIn(BaseModel):
    task: Literal["report_category", "report_lives", "report_rejected", "derja_words", "fire_smoke"]


class TrainerResultIn(BaseModel):
    model: str = Field(min_length=1, max_length=120)
    metrics: dict[str, Any]


class LabelIn(BaseModel):
    """What the operator confirms or corrects when a report ends; a field left out stays as read by the system."""

    category: Category | None = None
    lives_at_risk: bool | None = None
    rejected: bool | None = None


class LabelOut(BaseModel):
    category: str | None = None
    lives_at_risk: bool | None = None
    rejected: bool | None = None
    confirmed: list[str] = Field(default_factory=list)


@router.get("/learning")
async def overview(principal: Reader, session: Session) -> dict[str, Any]:
    _national(principal)
    return await service.overview(session)


@router.get("/learning/jobs")
async def list_jobs(principal: Reader, session: Session, task: str | None = None) -> list[dict[str, Any]]:
    _national(principal)
    return await service.jobs(session, task)


@router.post("/learning/jobs", status_code=status.HTTP_202_ACCEPTED)
async def launch(principal: Launcher, session: Session, body: LaunchIn) -> dict[str, Any]:
    """Queues a training; the worker runs it within LEARNING_INTERVAL_S."""
    _national(principal)
    job = await service.enqueue(
        session, body.task, "manual", actor_of(principal), audit.name_of(principal) or actor_of(principal)
    )
    await session.commit()
    return {"id": str(job.id), "task": job.task, "state": job.state}


@router.post("/learning/jobs/{job_id}/trainer-result")
async def trainer_result(
    principal: Launcher, session: Session, job_id: uuid.UUID, body: TrainerResultIn
) -> dict[str, Any]:
    """The figures of the GPU trainer for a fire and smoke training (services/vision/training/from_manifest.py)."""
    _national(principal)
    job = await session.get(TrainingJob, job_id, with_for_update=True)
    if job is None or tasks.TASKS[job.task].runner != "trainer":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    await service.trainer_result(
        session, job, body.metrics, body.model, actor_of(principal), audit.name_of(principal) or actor_of(principal)
    )
    await session.commit()
    return {"id": str(job.id), "state": job.state}


@router.get("/learning/datasets/{task}")
async def dataset(principal: Launcher, session: Session, task: Literal["reports", "fire_smoke"]) -> Response:
    """The anonymised data set, to train outside the platform: the report texts (CSV) or the image manifest of the
    fire and smoke detector (JSON, links valid six hours). Every export is audited."""
    _national(principal)
    actor = actor_of(principal)
    if task == "fire_smoke":
        prepared = await tasks.vision_dataset(session, service.link)
        await audit.record(
            session,
            actor=actor,
            action="learning.export",
            target="dataset:fire_smoke",
            details={"images": prepared["images"]},
        )
        await session.commit()
        return Response(
            content=json.dumps(prepared, ensure_ascii=False),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="fire-smoke-manifest.json"'},
        )
    rows = await service.dataset_rows(session)
    out = io.StringIO()
    writer = csv.DictWriter(
        out,
        fieldnames=["id", "text", "category", "lives_at_risk", "rejected", "confirmed", "origin", "split"],
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    await audit.record(
        session, actor=actor, action="learning.export", target="dataset:reports", details={"rows": len(rows)}
    )
    await session.commit()
    return Response(
        content="﻿" + out.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="e-himaya-report-texts.csv"'},
    )


# ---------------------------------------------------------------- the operator's confirmation


async def _final_report(session: AsyncSession, principal: Principal, report_id: uuid.UUID) -> Any:
    report, _ = await jurisdiction.load(session, principal, report_id)
    if report.status not in (Status.CLOSED.value, Status.REJECTED.value):
        raise HTTPException(status.HTTP_409_CONFLICT, "report_not_final")
    return report


@router.get("/reports/{report_id}/learning-label", response_model=LabelOut)
async def get_label(principal: Labeller, session: Session, report_id: uuid.UUID) -> LabelOut:
    report = await _final_report(session, principal, report_id)
    label = await samples.labels_of(session, report.id)
    if label is None:
        sample = await samples.upsert(session, report)
        await session.commit()
        label = dict(sample.label) if sample is not None else {}
    return LabelOut.model_validate(label)


@router.put("/reports/{report_id}/learning-label", response_model=LabelOut)
async def put_label(principal: Labeller, session: Session, report_id: uuid.UUID, body: LabelIn) -> LabelOut:
    """The operator confirms or corrects the reading; it weighs more than the system's own labels in training."""
    report = await _final_report(session, principal, report_id)
    actor = actor_of(principal)
    labels = body.model_dump(mode="json", exclude_none=True)
    sample = await samples.confirm(session, report, labels, actor)
    if sample is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "report_without_text")
    await audit.record(session, actor=actor, action="learning.label", target=f"report:{report_id}", details=labels)
    await session.commit()
    return LabelOut.model_validate(sample.label)
