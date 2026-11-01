"""The Office's reference lists (Yamen, 2026-11-01): the vehicle types with their CEE code, the agent's status and post,
the vehicle's state and situation, the parties of a road accident, the nature of a fire, the crops lost and their
units, the places of the damages and of the preventive programmes, the fields of intervention.

Every staff member reads them (the forms and the imports take their values from them); the central room adds an item,
renames it or retires it. An item is never deleted: a retired item stays readable for the records that carry it."""

import csv
import io
import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import REALM_ROLES, Principal, Realm, Role, require_roles
from app.modules.audit import service as audit
from app.modules.references import schemas
from app.modules.references.models import RefItem, RefList

router = APIRouter(prefix="/api/v1/staff/references", tags=["staff", "references"])
Session = Annotated[AsyncSession, Depends(get_session)]
AnyStaff = Annotated[Principal, Depends(require_roles(*REALM_ROLES[Realm.STAFF]))]
Key = Annotated[str, Path(pattern=r"^[a-z][a-z0-9_]{1,40}$")]
MANAGERS = (Role.SYSADMIN, Role.CENTRAL_COMMITTEE)


def _manages(principal: Principal) -> bool:
    return principal.is_national and any(r in principal.roles for r in MANAGERS)


async def _manager(principal: Annotated[Principal, Depends(require_roles(*MANAGERS))]) -> Principal:
    if not _manages(principal):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient_role")
    return principal


Manager = Annotated[Principal, Depends(_manager)]


def _item(i: RefItem) -> schemas.ItemOut:
    return schemas.ItemOut.model_validate(i, from_attributes=True)


async def _lists(session: AsyncSession, key: str | None = None) -> list[schemas.ListOut]:
    stmt = select(RefList).order_by(RefList.sort, RefList.key)
    if key is not None:
        stmt = stmt.where(RefList.key == key)
    lists = list(await session.scalars(stmt))
    items = list(await session.scalars(select(RefItem).order_by(RefItem.list_key, RefItem.sort, RefItem.label_ar)))
    return [
        schemas.ListOut(
            key=rl.key,
            name_ar=rl.name_ar,
            name_fr=rl.name_fr,
            name_en=rl.name_en,
            items=[_item(i) for i in items if i.list_key == rl.key],
        )
        for rl in lists
    ]


@router.get("", response_model=schemas.ListsOut)
async def list_references(principal: AnyStaff, session: Session) -> schemas.ListsOut:
    """Every list with its items, the retired ones included (marked)."""
    return schemas.ListsOut(lists=await _lists(session), can_manage=_manages(principal))


_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/export", response_class=Response, responses={200: {"content": {"text/csv": {}, _XLSX: {}}}})
async def export_references(
    principal: AnyStaff,
    session: Session,
    format: Annotated[Literal["xlsx", "csv"], Query()] = "xlsx",
    key: Annotated[str | None, Query(pattern=r"^[a-z][a-z0-9_]{1,40}$")] = None,
) -> Response:
    """The lists as a workbook (one sheet per list) or one list as CSV (UTF-8 with BOM, for Excel)."""
    lists = await _lists(session, key)
    if key is not None and not lists:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    head = ["code", "label_ar", "label_fr", "unit", "active"]
    if format == "csv":
        buf = io.StringIO()
        out = csv.writer(buf)
        out.writerow(["list", *head])
        for rl in lists:
            for i in rl.items:
                out.writerow([rl.key, i.code or "", i.label_ar, i.label_fr or "", i.unit or "", int(i.active)])
        name = f"references-{key or 'all'}-{stamp}.csv"
        return Response(
            ("﻿" + buf.getvalue()).encode(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    wb.remove(wb.active)
    for rl in lists:
        ws = wb.create_sheet(rl.key[:31])
        ws.sheet_view.rightToLeft = True
        ws.append([rl.name_ar])
        ws["A1"].font = Font(bold=True, size=12)
        ws.append(head)
        for c in range(1, len(head) + 1):
            ws.cell(2, c).font = Font(bold=True)
        for i in rl.items:
            ws.append([i.code, i.label_ar, i.label_fr, i.unit, "نعم" if i.active else "لا"])
        ws.column_dimensions["B"].width = 40
    data = io.BytesIO()
    wb.save(data)
    return Response(
        data.getvalue(),
        media_type=_XLSX,
        headers={"Content-Disposition": f'attachment; filename="references-{key or "all"}-{stamp}.xlsx"'},
    )


@router.post("/{key}/items", response_model=schemas.ItemOut, status_code=status.HTTP_201_CREATED)
async def add_item(principal: Manager, session: Session, key: Key, body: schemas.ItemIn) -> schemas.ItemOut:
    if await session.get(RefList, key) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    sort = body.sort
    if sort is None:
        last = await session.scalar(select(func.max(RefItem.sort)).where(RefItem.list_key == key))
        sort = (last or 0) + 10
    item = RefItem(
        list_key=key,
        code=(body.code or "").strip() or None,
        label_ar=body.label_ar.strip(),
        label_fr=(body.label_fr or "").strip() or None,
        unit=body.unit,
        sort=sort,
        active=True,
        updated_by=audit.actor_of(principal),
        updated_by_name=audit.name_of(principal),
    )
    session.add(item)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "reference_exists") from exc
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="references.item_added",
        target=f"ref_item:{item.id}",
        details={"list": key, "label": item.label_ar, "code": item.code},
    )
    await session.commit()
    await session.refresh(item)
    return _item(item)


@router.patch("/items/{item_id}", response_model=schemas.ItemOut)
async def change_item(
    principal: Manager, session: Session, item_id: uuid.UUID, body: schemas.ItemPatch
) -> schemas.ItemOut:
    """Rename an item, give it a code, a unit or a place, retire it or bring it back."""
    item = await session.get(RefItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    changes = body.model_dump(exclude_unset=True)
    before = {k: getattr(item, k) for k in changes}
    for k, v in changes.items():
        if k == "label_ar":
            if v:
                item.label_ar = v.strip()
        else:
            setattr(item, k, (v.strip() or None) if isinstance(v, str) else v)
    item.updated_by, item.updated_by_name = audit.actor_of(principal), audit.name_of(principal)
    item.updated_at = datetime.now(UTC)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "reference_exists") from exc
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="references.item_changed",
        target=f"ref_item:{item.id}",
        details={"list": item.list_key, "before": before, "after": changes},
    )
    await session.commit()
    await session.refresh(item)
    return _item(item)
