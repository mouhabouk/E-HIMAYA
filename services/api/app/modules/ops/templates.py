"""Detailed reports built from templates (phase P4b, F-STF-05, docs/phase-p4/design-staff.md §5.7).

A template is a list of questions answered with a tap: chips (one or several), yes or no, or a number with + and −.
The Office keeps one approved version per category (and optionally classification); approving a draft retires the
version before it, and every report keeps the version it answered. The first versions are a model [SIM].
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal
from app.modules.audit import service as audit
from app.modules.ops import schemas
from app.modules.ops.domain import classification_allowed
from app.modules.ops.models import ReportTemplate
from app.modules.reports.domain import Category


def _now() -> datetime:
    return datetime.now(UTC)


def template_out(t: ReportTemplate) -> schemas.TemplateOut:
    return schemas.TemplateOut(
        id=t.id,
        category=Category(t.category),
        classification=t.classification,
        version=t.version,
        status=t.status,
        fields=[schemas.TemplateField.model_validate(f) for f in t.fields],
        simulated=t.simulated,
        created_by_name=t.created_by_name,
        created_at=t.created_at,
        updated_at=t.updated_at,
        approved_by_name=t.approved_by_name,
        approved_at=t.approved_at,
    )


async def approved_for(session: AsyncSession, category: str, classification: str | None) -> ReportTemplate | None:
    """The approved template of a classification, else the one of its category."""
    rows = await session.scalars(
        select(ReportTemplate).where(
            ReportTemplate.status == "approved",
            ReportTemplate.category == category,
            (ReportTemplate.classification.is_(None)) | (ReportTemplate.classification == classification),
        )
    )
    found = list(rows)
    return next((t for t in found if t.classification is not None), None) or next(iter(found), None)


# ---------------------------------------------------------------- answers


def check_answers(fields: list[dict[str, Any]], answers: dict[str, Any]) -> dict[str, Any]:
    """The answers kept: only known keys, each of the field's shape; a required field must be answered."""
    by_key = {f["key"]: f for f in fields}
    unknown = set(answers) - set(by_key)
    if unknown:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown_field")
    kept: dict[str, Any] = {}
    for key, field in by_key.items():
        value = answers.get(key)
        if value is None:
            if field.get("required"):
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "answer_required")
            continue
        options = {o["key"] for o in field.get("options", [])}
        kind = field["type"]
        ok = False
        if kind == "single":
            ok = isinstance(value, str) and value in options
        elif kind == "multi":
            ok = isinstance(value, list) and len(value) == len(set(value)) and all(v in options for v in value)
        elif kind == "yesno":
            ok = isinstance(value, bool)
        elif kind == "count":
            ok = (
                isinstance(value, int)
                and not isinstance(value, bool)
                and 0 <= value <= int(field.get("max") or 1_000_000)
            )
        if not ok:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_answer")
        kept[key] = value
    return kept


# ---------------------------------------------------------------- the Office's editor


def _check_fields(fields: list[schemas.TemplateField]) -> list[dict[str, Any]]:
    keys = [f.key for f in fields]
    if len(keys) != len(set(keys)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "duplicate_field")
    for f in fields:
        options = [o.key for o in f.options]
        if f.type in ("single", "multi") and len(options) < 2:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "options_required")
        if len(options) != len(set(options)):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "duplicate_option")
        if f.type not in ("single", "multi") and options:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "options_not_allowed")
    return [f.model_dump(exclude_none=True) for f in fields]


async def list_templates(session: AsyncSession, include_retired: bool) -> list[ReportTemplate]:
    query = select(ReportTemplate).order_by(
        ReportTemplate.category, ReportTemplate.classification.nulls_first(), ReportTemplate.version.desc()
    )
    if not include_retired:
        query = query.where(ReportTemplate.status != "retired")
    return list(await session.scalars(query))


async def get(session: AsyncSession, template_id: uuid.UUID, *, lock: bool = False) -> ReportTemplate:
    t = await session.get(ReportTemplate, template_id, with_for_update=lock)
    if t is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return t


async def create_draft(session: AsyncSession, principal: Principal, body: schemas.TemplateIn) -> ReportTemplate:
    if body.classification is not None and not classification_allowed(body.category, body.classification):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_classification")
    fields = _check_fields(body.fields)
    same = (ReportTemplate.category == body.category.value) & (
        ReportTemplate.classification.is_(None)
        if body.classification is None
        else ReportTemplate.classification == body.classification
    )
    if await session.scalar(select(ReportTemplate.id).where(same, ReportTemplate.status == "draft")):
        raise HTTPException(status.HTTP_409_CONFLICT, "draft_exists")
    version = (await session.scalar(select(func.max(ReportTemplate.version)).where(same)) or 0) + 1
    t = ReportTemplate(
        category=body.category.value,
        classification=body.classification,
        version=version,
        status="draft",
        fields=fields,
        simulated=False,
        created_by=audit.actor_of(principal),
        created_by_name=audit.name_of(principal),
    )
    session.add(t)
    await session.flush()
    await session.refresh(t)
    return t


async def edit_draft(session: AsyncSession, t: ReportTemplate, body: schemas.TemplatePatch) -> ReportTemplate:
    if t.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "not_a_draft")
    t.fields = _check_fields(body.fields)
    t.updated_at = _now()
    await session.flush()
    return t


async def approve(session: AsyncSession, principal: Principal, t: ReportTemplate) -> ReportTemplate:
    if t.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "not_a_draft")
    current = await approved_for(session, t.category, t.classification)
    now = _now()
    if current is not None and current.classification == t.classification:
        current.status, current.retired_at = "retired", now
        await session.flush()
    t.status = "approved"
    t.approved_by, t.approved_by_name, t.approved_at = audit.actor_of(principal), audit.name_of(principal), now
    t.updated_at = now
    await session.flush()
    return t


async def discard_draft(session: AsyncSession, t: ReportTemplate) -> None:
    if t.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "not_a_draft")
    await session.delete(t)
    await session.flush()


async def retire(session: AsyncSession, t: ReportTemplate) -> ReportTemplate:
    if t.status != "approved":
        raise HTTPException(status.HTTP_409_CONFLICT, "not_approved")
    t.status, t.retired_at, t.updated_at = "retired", _now(), _now()
    await session.flush()
    return t
