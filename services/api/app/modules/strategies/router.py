"""The strategies menu (phase S, docs/phase-s/design-s.md §2.2).

The platform's own pages are gathered there (SNACR, the intervention plans, the seasonal programmes, the dry runs, the
lessons learned); the system administrator adds the other items: a national strategy, a programme, a reference, with
its own page or a link, shown to every staff member or to some roles only.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import REALM_ROLES, Principal, Realm, Role, require_roles
from app.modules.audit import service as audit
from app.modules.strategies import schemas
from app.modules.strategies.models import StrategyItem

router = APIRouter(prefix="/api/v1/staff/strategies", tags=["staff", "strategies"])
Session = Annotated[AsyncSession, Depends(get_session)]
AnyStaff = Annotated[Principal, Depends(require_roles(*REALM_ROLES[Realm.STAFF]))]
Key = Annotated[str, Path(pattern=r"^[a-z][a-z0-9_]{1,39}$")]


def _manages(principal: Principal) -> bool:
    return principal.is_national and Role.SYSADMIN in principal.roles


async def _administrator(principal: AnyStaff) -> Principal:
    if not _manages(principal):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient_role")
    return principal


Admin = Annotated[Principal, Depends(_administrator)]


def _out(item: StrategyItem) -> schemas.ItemOut:
    return schemas.ItemOut.model_validate(item, from_attributes=True)


def _sees(principal: Principal, item: StrategyItem) -> bool:
    return not item.roles or any(r.value in item.roles for r in principal.roles)


@router.get("", response_model=schemas.ItemsOut)
async def list_items(principal: AnyStaff, session: Session) -> schemas.ItemsOut:
    """The items the caller sees (active, open to one of their roles); the administrator gets them all."""
    items = list(await session.scalars(select(StrategyItem).order_by(StrategyItem.position, StrategyItem.key)))
    manages = _manages(principal)
    shown = items if manages else [i for i in items if i.active and _sees(principal, i)]
    return schemas.ItemsOut(items=[_out(i) for i in shown], can_manage=manages)


@router.get("/{key}", response_model=schemas.ItemOut)
async def get_item(principal: AnyStaff, session: Session, key: Key) -> schemas.ItemOut:
    item = await session.get(StrategyItem, key)
    if item is None or not (_manages(principal) or (item.active and _sees(principal, item))):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return _out(item)


@router.put("/{key}", response_model=schemas.ItemOut)
async def put_item(principal: Admin, session: Session, key: Key, body: schemas.ItemIn) -> schemas.ItemOut:
    """Adds an item or changes it. It needs its name in the three languages, and a page text or a link."""
    if not all(body.name.get(lang) for lang in ("ar", "fr", "en")):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "name_required")
    if not body.link and not any(v.strip() for v in body.body.values()):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "body_or_link_required")
    item = await session.get(StrategyItem, key)
    created = item is None
    if item is None:
        item = StrategyItem(key=key)
        session.add(item)
    item.name = {str(k): v for k, v in body.name.items()}
    item.summary = {k: v for k, v in body.summary.items() if v}
    item.body = {k: v for k, v in body.body.items() if v.strip()}
    item.link, item.icon, item.tone = body.link, body.icon, body.tone
    item.roles, item.position, item.active = body.roles, body.position, body.active
    item.updated_by, item.updated_by_name = audit.actor_of(principal), audit.name_of(principal)
    item.updated_at = datetime.now().astimezone()
    await session.flush()
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="strategies.item_saved",
        target=f"strategy_item:{key}",
        details={"created": created, "active": body.active, "roles": body.roles, "link": body.link},
    )
    await session.commit()
    await session.refresh(item)
    return _out(item)


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(principal: Admin, session: Session, key: Key) -> Response:
    item = await session.get(StrategyItem, key)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    await session.delete(item)
    await audit.record(
        session, actor=audit.actor_of(principal), action="strategies.item_deleted", target=f"strategy_item:{key}"
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
