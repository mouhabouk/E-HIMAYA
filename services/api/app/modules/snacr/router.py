"""Risk analysis and coverage plan, SNACR (docs/phase-s/design-s.md).

Staff only, aggregates only. The archive is loaded by the national level (the central room, the national committee);
the analysis of a regional account covers its own gouvernorat; a regional committee prepares and approves the plan of
its gouvernorat, the national committee the national plan (decree 93-942, articles 5 and 12).
"""

import uuid
from datetime import date, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.modules.analytics.service import resolve_scope
from app.modules.audit import service as audit
from app.modules.snacr import damage, documents, domain, schemas, service, simulate, study_export, study_findings
from app.modules.snacr import study as studies
from app.modules.snacr.models import Dataset, Plan, SpecialRisk, Study

router = APIRouter(prefix="/api/v1/staff/snacr", tags=["staff", "snacr"])
Session = Annotated[AsyncSession, Depends(get_session)]

READ_ROLES = (Role.OPS_MANAGER, Role.LOCAL_COMMITTEE, Role.CENTRAL_COMMITTEE, Role.GOVERNOR, Role.MINISTER)
NATIONAL_EDITORS = (Role.OPS_MANAGER, Role.CENTRAL_COMMITTEE)
PLANNERS = (Role.LOCAL_COMMITTEE, Role.CENTRAL_COMMITTEE, Role.GOVERNOR, Role.MINISTER)
Reader = Annotated[Principal, Depends(require_roles(*READ_ROLES))]
Editor = Annotated[Principal, Depends(require_roles(*NATIONAL_EDITORS))]
Planner = Annotated[Principal, Depends(require_roles(*PLANNERS))]


def _national(principal: Principal) -> None:
    if not principal.is_national:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "national_only")


def _codes(principal: Principal, gouvernorat: int | None) -> list[int]:
    return resolve_scope(principal, [gouvernorat] if gouvernorat is not None else None)


async def _years(session: AsyncSession, years: list[int] | None) -> list[int]:
    available = await service.years_available(session)
    if not years:
        return await service.default_years(session)
    missing = [y for y in years if y not in available]
    if missing:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "years_not_loaded")
    return sorted(set(years))


def _dataset(d: Dataset) -> schemas.DatasetOut:
    return schemas.DatasetOut.model_validate(d, from_attributes=True)


@router.get("", response_model=schemas.Overview)
async def overview(principal: Reader, session: Session) -> schemas.Overview:
    return schemas.Overview(
        datasets=[_dataset(d) for d in await service.datasets(session)],
        default_years=await service.default_years(session),
        method=schemas.Method(**await service.method(session)),
        references=[schemas.Reference(**r) for r in domain.REFERENCES],
        can_import=principal.is_national and bool(principal.roles & set(NATIONAL_EDITORS)),
        can_edit_national=principal.is_national and bool(principal.roles & {Role.CENTRAL_COMMITTEE, Role.MINISTER}),
    )


@router.get("/analysis", response_model=schemas.Analysis)
async def analysis(
    principal: Reader,
    session: Session,
    years: Annotated[str | None, Query(pattern=r"^\d{4}(,\d{4}){0,4}$", description="Comma-separated years")] = None,
    gouvernorat: Annotated[int | None, Query(ge=11, le=83)] = None,
) -> dict[str, Any]:
    """Everyday risks over three consecutive years by default: frequency per 1,000 inhabitants (census 2024), arrival
    times at the median and the 90th percentile, the share within the target of the délégation's kind, the
    completeness of the archive, the frequency × coverage matrix, seasons and hours."""
    codes = _codes(principal, gouvernorat)
    chosen = await _years(session, [int(y) for y in years.split(",")] if years else None)
    if not chosen:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no_dataset")
    return await service.analysis(session, codes, chosen)


# ---------------------------------------------------------------- archive


async def _read_body(request: Request) -> bytes:
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > domain.MAX_BYTES:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "file_too_large")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/datasets", response_model=schemas.ImportOut, status_code=status.HTTP_201_CREATED)
async def import_dataset(
    principal: Editor,
    session: Session,
    request: Request,
    file_name: Annotated[str, Query(min_length=1, max_length=200)],
    year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
    merge: bool = False,
) -> schemas.ImportOut:
    """The Office's export (xlsx or CSV) is the request body. Only the times, the place, the nature, the intervention
    number, the unit and INTERV_OUI_NON are read; the address, the free texts, the crew and the vehicles never are.

    ``year``: that year only, replacing the year already loaded. Without it, every year the file covers is loaded
    (a regional file of 2022–2025). ``merge``: only the gouvernorats of the file are replaced in each year, the others
    stay (the files of the 24 regional directorates loaded one after the other)."""
    _national(principal)
    data = await _read_body(request)
    try:
        records = list(domain.read(file_name, data))
        years = [year] if year is not None else service.years_in(records)
        if not years:
            raise domain.FileError("file_empty")
        loaded = [
            await service.load(
                session, y, records, "office", file_name, audit.actor_of(principal), audit.name_of(principal), merge
            )
            for y in years
        ]
    except domain.FileError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, exc.code) from exc
    for dataset in loaded:
        await audit.record(
            session,
            actor=audit.actor_of(principal),
            action="snacr.dataset_imported",
            target=f"snacr_dataset:{dataset.year}",
            details={
                "rows": dataset.rows,
                "file_name": file_name,
                "merge": merge,
                "skipped": dataset.quality.get("skipped"),
            },
        )
    await session.commit()
    for dataset in loaded:
        await session.refresh(dataset)
    return schemas.ImportOut(dataset=_dataset(loaded[0]), datasets=[_dataset(d) for d in loaded])


@router.post("/damages", response_model=schemas.DamageImportOut, status_code=status.HTTP_201_CREATED)
async def import_damages(
    principal: Editor,
    session: Session,
    request: Request,
    file_name: Annotated[str, Query(min_length=1, max_length=200)],
) -> schemas.DamageImportOut:
    """A damage table of the Office (degat_forestieres or degat_Agriculteur, CSV or xlsx), recognised by its headings;
    it replaces the lines of its kind. Each line is tied to its intervention by NUM_SEQUENTIEL."""
    _national(principal)
    data = await _read_body(request)
    try:
        report, lines = damage.read(file_name, data, await service.crop_reference(session))
    except domain.FileError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, exc.code) from exc
    await service.load_damages(session, lines, report.kind, file_name, audit.actor_of(principal))
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="snacr.damages_imported",
        target=f"snacr_damage:{report.kind}",
        details={"file_name": file_name, "read": report.read, "kept": report.kept, "rejected": report.rejected},
    )
    await session.commit()
    return schemas.DamageImportOut(
        kind=report.kind,
        read=report.read,
        kept=report.kept,
        rejected=report.rejected,
        status=[schemas.DamageStatus(**s) for s in await service.damage_status(session)],
    )


@router.get("/damages", response_model=list[schemas.DamageStatus])
async def damages_status(principal: Reader, session: Session) -> list[dict[str, Any]]:
    """The damage tables loaded, and how many of their lines find their intervention in the archive."""
    return await service.damage_status(session)


@router.post("/datasets/simulate", response_model=schemas.ImportOut, status_code=status.HTTP_201_CREATED)
async def simulate_dataset(
    principal: Editor,
    session: Session,
    year: Annotated[int, Query(ge=2000, le=2100)],
    rows: Annotated[int | None, Query(ge=100, le=250_000)] = None,
) -> schemas.ImportOut:
    """[SIM] A year generated on the distributions of the real 2022 archive, until the Office's file of that year
    arrives (it then replaces the simulated year by the same import)."""
    _national(principal)
    dataset = await service.load(
        session,
        year,
        simulate.generate(year, rows),
        "simulated",
        None,
        audit.actor_of(principal),
        audit.name_of(principal),
    )
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="snacr.dataset_simulated",
        target=f"snacr_dataset:{year}",
        details={"rows": dataset.rows},
    )
    await session.commit()
    await session.refresh(dataset)
    return schemas.ImportOut(dataset=_dataset(dataset))


@router.post("/datasets/live", response_model=schemas.ImportOut, status_code=status.HTTP_201_CREATED)
async def live_dataset(
    principal: Editor, session: Session, year: Annotated[int, Query(ge=2000, le=2100)]
) -> schemas.ImportOut:
    """The year drawn from the records of the operations rooms (phase S2): the times the teams and the rooms gave,
    the crews. Built again on each call; it never replaces the Office's file or a [SIM] year."""
    _national(principal)
    dataset = await service.build_live(session, year, audit.actor_of(principal), audit.name_of(principal))
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="snacr.dataset_live",
        target=f"snacr_dataset:{year}",
        details={"rows": dataset.rows},
    )
    await session.commit()
    await session.refresh(dataset)
    return schemas.ImportOut(dataset=_dataset(dataset))


@router.delete("/datasets/{year}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(principal: Editor, session: Session, year: int) -> Response:
    _national(principal)
    dataset = await session.scalar(select(Dataset).where(Dataset.year == year))
    if dataset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    await session.delete(dataset)
    await audit.record(
        session, actor=audit.actor_of(principal), action="snacr.dataset_deleted", target=f"snacr_dataset:{year}"
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/unmatched", response_model=list[schemas.UnmatchedName])
async def unmatched(
    principal: Reader, session: Session, gouvernorat: Annotated[int | None, Query(ge=11, le=83)] = None
) -> list[dict[str, Any]]:
    """The names of the archive tied to no délégation yet, the most frequent first."""
    return await service.unmatched(session, _codes(principal, gouvernorat))


@router.get("/aliases", response_model=list[schemas.AliasOut])
async def list_aliases(
    principal: Reader, session: Session, gouvernorat: Annotated[int | None, Query(ge=11, le=83)] = None
) -> list[schemas.AliasOut]:
    return [
        schemas.AliasOut.model_validate(a, from_attributes=True)
        for a in await service.aliases(session, _codes(principal, gouvernorat))
    ]


@router.post("/aliases", response_model=schemas.AliasCreated, status_code=status.HTTP_201_CREATED)
async def create_alias(principal: Editor, session: Session, body: schemas.AliasIn) -> schemas.AliasCreated:
    """Tie a name of the archive to its délégation; the rows already loaded with that name follow."""
    _national(principal)
    alias, fixed = await service.add_alias(
        session,
        body.gouvernorat_code,
        body.raw,
        body.delegation_id,
        audit.actor_of(principal),
        audit.name_of(principal),
    )
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="snacr.alias_created",
        target=f"snacr_alias:{alias.id}",
        details={"raw": alias.raw, "delegation_id": alias.delegation_id, "rows_fixed": fixed},
        gouvernorats=[alias.gouvernorat_code],
    )
    await session.commit()
    await session.refresh(alias)
    return schemas.AliasCreated(alias=schemas.AliasOut.model_validate(alias, from_attributes=True), rows_fixed=fixed)


# ---------------------------------------------------------------- specific risks


@router.get("/special-risks", response_model=list[schemas.SpecialRiskOut])
async def list_special_risks(
    principal: Reader, session: Session, gouvernorat: Annotated[int | None, Query(ge=11, le=83)] = None
) -> list[dict[str, Any]]:
    return [service.special_out(r) for r in await service.special_risks(session, _codes(principal, gouvernorat))]


def _may_edit(principal: Principal, gouvernorat: int) -> None:
    if not principal.roles & {
        Role.CENTRAL_COMMITTEE,
        Role.LOCAL_COMMITTEE,
        Role.GOVERNOR,
        Role.MINISTER,
        Role.OPS_MANAGER,
    }:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient_role")
    if not principal.can_access_gouvernorat(gouvernorat):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "out_of_scope")


@router.post("/special-risks", response_model=schemas.SpecialRiskOut)
async def put_special_risk(principal: Reader, session: Session, body: schemas.SpecialRiskIn) -> dict[str, Any]:
    """Add or update the risk of a gouvernorat (one per hazard); an edited [SIM] entry becomes a real one."""
    _may_edit(principal, body.gouvernorat_code)
    risk = await session.scalar(
        select(SpecialRisk).where(
            SpecialRisk.gouvernorat_code == body.gouvernorat_code, SpecialRisk.hazard == body.hazard
        )
    )
    if risk is None:
        risk = SpecialRisk(gouvernorat_code=body.gouvernorat_code, hazard=body.hazard)
        session.add(risk)
    risk.probability, risk.gravity, risk.note = body.probability, body.gravity, body.note
    risk.simulated = False
    risk.updated_by, risk.updated_by_name = audit.actor_of(principal), audit.name_of(principal)
    risk.updated_at = datetime.now().astimezone()
    await session.flush()
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="snacr.special_risk_saved",
        target=f"snacr_special_risk:{risk.id}",
        details={"hazard": risk.hazard, "probability": risk.probability, "gravity": risk.gravity},
        gouvernorats=[risk.gouvernorat_code],
    )
    await session.commit()
    await session.refresh(risk)
    return service.special_out(risk)


@router.delete("/special-risks/{risk_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_special_risk(principal: Reader, session: Session, risk_id: uuid.UUID) -> Response:
    risk = await session.get(SpecialRisk, risk_id)
    if risk is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    _may_edit(principal, risk.gouvernorat_code)
    await session.delete(risk)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="snacr.special_risk_deleted",
        target=f"snacr_special_risk:{risk_id}",
        gouvernorats=[risk.gouvernorat_code],
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- plans


def _can_approve(principal: Principal, plan: Plan) -> bool:
    if plan.status != "draft":
        return False
    if plan.gouvernorat_code is None:
        return principal.is_national and bool(principal.roles & {Role.CENTRAL_COMMITTEE, Role.MINISTER})
    return bool(principal.roles & set(PLANNERS)) and principal.can_access_gouvernorat(plan.gouvernorat_code)


def _months(start: datetime, months: int) -> datetime:
    return start + timedelta(days=round(months * 30.44))


async def _summary(session: AsyncSession, principal: Principal, plan: Plan) -> dict[str, Any]:
    m = await service.method(session)
    approved = plan.approved_at
    return {
        "id": plan.id,
        "gouvernorat_code": plan.gouvernorat_code,
        "version": plan.version,
        "years": plan.years,
        "status": plan.status,
        "simulated": plan.simulated,
        "created_by_name": plan.created_by_name,
        "created_at": plan.created_at,
        "approved_by_name": plan.approved_by_name,
        "approved_at": approved,
        "review_due": _months(approved, m["review_months"]) if approved else None,
        "valid_until": _months(approved, 12 * m["validity_years"]) if approved else None,
        "objectives": len(plan.content.get("objectives", [])),
        "can_approve": _can_approve(principal, plan),
    }


@router.get("/plans", response_model=list[schemas.PlanSummary])
async def list_plans(
    principal: Reader, session: Session, gouvernorat: Annotated[int | None, Query(ge=11, le=83)] = None
) -> list[dict[str, Any]]:
    stmt = select(Plan).order_by(Plan.gouvernorat_code.nulls_first(), Plan.version.desc())
    if gouvernorat is not None:
        _codes(principal, gouvernorat)
        stmt = stmt.where(Plan.gouvernorat_code == gouvernorat)
    return [await _summary(session, principal, p) for p in (await session.scalars(stmt)).all()]


@router.post("/plans", response_model=schemas.PlanOut, status_code=status.HTTP_201_CREATED)
async def create_plan(principal: Planner, session: Session, body: schemas.PlanIn) -> dict[str, Any]:
    """A draft: the analysis of the chosen years frozen with the register of specific risks and the objectives drawn
    from them. The national plan is prepared by the national level only."""
    if body.gouvernorat_code is None:
        _national(principal)
    else:
        _codes(principal, body.gouvernorat_code)
    years = await _years(session, body.years)
    if not years:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no_dataset")
    plan = await service.build_plan(
        session, body.gouvernorat_code, years, audit.actor_of(principal), audit.name_of(principal)
    )
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="snacr.plan_drafted",
        target=f"snacr_plan:{plan.id}",
        details={"version": plan.version, "years": years},
        gouvernorats=[plan.gouvernorat_code] if plan.gouvernorat_code else None,
    )
    await session.commit()
    await session.refresh(plan)
    return await _plan_out(session, principal, plan)


async def _plan_out(session: AsyncSession, principal: Principal, plan: Plan) -> dict[str, Any]:
    return {
        **await _summary(session, principal, plan),
        "objective_list": plan.content.get("objectives", []),
        "special_risks": plan.content.get("special_risks", []),
        "references": plan.content.get("references", []),
    }


async def _plan(session: AsyncSession, principal: Principal, plan_id: uuid.UUID) -> Plan:
    plan = await session.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if plan.gouvernorat_code is not None and not principal.can_access_gouvernorat(plan.gouvernorat_code):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return plan


@router.get("/plans/{plan_id}", response_model=schemas.PlanOut)
async def get_plan(principal: Reader, session: Session, plan_id: uuid.UUID) -> dict[str, Any]:
    return await _plan_out(session, principal, await _plan(session, principal, plan_id))


@router.post("/plans/{plan_id}/approve", response_model=schemas.PlanOut)
async def approve_plan(principal: Planner, session: Session, plan_id: uuid.UUID) -> dict[str, Any]:
    """The committee of the plan's level approves it (decree 93-942: the governor for the regional plan, the
    national commission for the national one); the plan it replaces is superseded."""
    plan = await _plan(session, principal, plan_id)
    if not _can_approve(principal, plan):
        raise HTTPException(
            status.HTTP_409_CONFLICT if plan.status != "draft" else status.HTTP_403_FORBIDDEN,
            "plan_not_draft" if plan.status != "draft" else "insufficient_role",
        )
    await service.approve(session, plan, audit.actor_of(principal), audit.name_of(principal))
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="snacr.plan_approved",
        target=f"snacr_plan:{plan.id}",
        details={"version": plan.version},
        gouvernorats=[plan.gouvernorat_code] if plan.gouvernorat_code else None,
    )
    await session.commit()
    await session.refresh(plan)
    return await _plan_out(session, principal, plan)


@router.get(
    "/plans/{plan_id}/document",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}, "text/html": {}}}},
)
async def plan_document(
    principal: Reader,
    session: Session,
    plan_id: uuid.UUID,
    format: Annotated[str, Query(pattern="^(pdf|html)$")] = "pdf",
) -> Response:
    """The plan as a document (Arabic): framework and references, territory, everyday risks, coverage and gaps,
    specific risks, objectives, review, and the completeness of the archive."""
    plan = await _plan(session, principal, plan_id)
    names = await documents.names(session)
    summary = await _summary(session, principal, plan)
    page = documents.render_html(plan, summary, names)
    stamp = date.today().isoformat()
    scope = "national" if plan.gouvernorat_code is None else f"g{plan.gouvernorat_code}"
    if format == "html":
        return Response(page, media_type="text/html; charset=utf-8")
    return Response(
        documents.render_pdf(page),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="snacr-{scope}-v{plan.version}-{stamp}.pdf"'},
    )


# ---------------------------------------------------------------- studies (the Office's six tables)

STUDY_ROLES = (Role.OPS_MANAGER, Role.LOCAL_COMMITTEE, Role.CENTRAL_COMMITTEE)
Launcher = Annotated[Principal, Depends(require_roles(*STUDY_ROLES))]


def _study_summary(s: Study) -> dict[str, Any]:
    return {
        "id": s.id,
        "number": s.number,
        "gouvernorat_code": s.gouvernorat_code,
        "years": s.years,
        "split": s.split,
        "travel_max": s.travel_max,
        "status": s.status,
        "simulated": s.simulated,
        "quality": s.quality,
        "created_by_name": s.created_by_name,
        "created_at": s.created_at,
        "archived_at": s.archived_at,
    }


def _study_out(s: Study) -> dict[str, Any]:
    """The study with its statistical board and technical notes, read from its own tables."""
    return {**_study_summary(s), "tables": s.tables, "findings": study_findings.read(s.tables, s.quality, s.travel_max)}


async def _study(session: AsyncSession, principal: Principal, study_id: uuid.UUID) -> Study:
    found = await session.get(Study, study_id)
    if found is None or (
        found.gouvernorat_code is not None and not principal.can_access_gouvernorat(found.gouvernorat_code)
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return found


@router.get("/studies", response_model=list[schemas.StudySummary])
async def list_studies(
    principal: Reader, session: Session, gouvernorat: Annotated[int | None, Query(ge=11, le=83)] = None
) -> list[dict[str, Any]]:
    """The studies of a scope, the current one first then the archive (the national studies without a
    gouvernorat; a regional account sees its own gouvernorat's)."""
    if gouvernorat is None and not principal.is_national:
        gouvernorat = _codes(principal, None)[0]
    elif gouvernorat is not None:
        _codes(principal, gouvernorat)
    stmt = select(Study).where(
        Study.gouvernorat_code.is_(None) if gouvernorat is None else Study.gouvernorat_code == gouvernorat
    )
    rows = (await session.scalars(stmt.order_by(Study.number.desc()))).all()
    return [_study_summary(s) for s in rows]


@router.post("/studies", response_model=schemas.StudyOut, status_code=status.HTTP_201_CREATED)
async def launch_study(principal: Launcher, session: Session, body: schemas.StudyIn) -> dict[str, Any]:
    """A new study with its settings (years, day split, travel-time ceiling); the current study of the same scope is
    archived as it was, never rewritten."""
    if body.gouvernorat_code is None:
        _national(principal)
    else:
        _codes(principal, body.gouvernorat_code)
    years = await _years(session, body.years)
    study = await studies.launch(
        session,
        body.gouvernorat_code,
        years,
        body.split,
        body.travel_max,
        audit.actor_of(principal),
        audit.name_of(principal),
    )
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="snacr.study_launched",
        target=f"snacr_study:{study.id}",
        details={"number": study.number, "years": years, "split": body.split, "travel_max": body.travel_max},
        gouvernorats=[study.gouvernorat_code] if study.gouvernorat_code else None,
    )
    await session.commit()
    await session.refresh(study)
    return _study_out(study)


@router.get("/studies/{study_id}", response_model=schemas.StudyOut)
async def get_study(principal: Reader, session: Session, study_id: uuid.UUID) -> dict[str, Any]:
    found = await _study(session, principal, study_id)
    return _study_out(found)


@router.get(
    "/studies/{study_id}/export",
    response_class=Response,
    responses={
        200: {
            "content": {
                "application/pdf": {},
                "text/html": {},
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {},
            }
        }
    },
)
async def export_study(
    principal: Reader,
    session: Session,
    study_id: uuid.UUID,
    format: Annotated[str, Query(pattern="^(pdf|xlsx|html)$")] = "pdf",
) -> Response:
    """The study as the Office's file: PDF (A4 landscape) or Excel (one sheet per table, the layout of "ariana"),
    for the current study as for any archived one."""
    found = await _study(session, principal, study_id)
    names = await documents.names(session)
    g_name = names["gouvernorats"].get(found.gouvernorat_code) if found.gouvernorat_code else None
    scope = "national" if found.gouvernorat_code is None else f"g{found.gouvernorat_code}"
    stem = f"snacr-study-{scope}-{found.number}-{found.created_at:%Y%m%d}"
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="snacr.study_exported",
        target=f"snacr_study:{found.id}",
        details={"format": format},
        gouvernorats=[found.gouvernorat_code] if found.gouvernorat_code else None,
    )
    await session.commit()
    if format == "html":
        return Response(study_export.render_html(found, g_name), media_type="text/html; charset=utf-8")
    if format == "xlsx":
        return Response(
            study_export.render_xlsx(found, g_name),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{stem}.xlsx"'},
        )
    return Response(
        study_export.render_pdf(found, g_name),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{stem}.pdf"'},
    )
