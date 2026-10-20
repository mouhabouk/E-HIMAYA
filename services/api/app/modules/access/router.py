"""Break-glass endpoints (phase 9 §6.1): request a time-boxed read-only grant, list, revoke, review."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Ctx, authorize, require
from app.core.db import get_session
from app.core.security import REALM_ROLES, Principal, Realm, Role, require_roles
from app.modules.access import grants, schemas

router = APIRouter(prefix="/api/v1/staff/break-glass", tags=["break-glass"])

Session = Annotated[AsyncSession, Depends(get_session)]
Requester = Annotated[
    Principal,
    Depends(
        require_roles(
            Role.OPERATOR, Role.OPS_MANAGER, Role.FIELD_COMMANDER, Role.LOCAL_COMMITTEE, Role.CENTRAL_COMMITTEE
        )
    ),
]
AnyStaff = Annotated[Principal, Depends(require_roles(*REALM_ROLES[Realm.STAFF]))]
SecurityAdmin = Annotated[Principal, Depends(require_roles(Role.SECURITY_ADMIN))]
OBJECTLESS = Ctx(lead=None)


@router.post("", response_model=schemas.GrantOut, status_code=status.HTTP_201_CREATED)
async def request_grant(principal: Requester, session: Session, body: schemas.GrantIn) -> schemas.GrantOut:
    require(await authorize(session, principal, Action.BREAKGLASS_REQUEST, OBJECTLESS))
    row = await grants.request(session, principal, body)
    out = grants.grant_out(row)
    await session.commit()
    return out


@router.get("", response_model=schemas.GrantPage)
async def list_grants(
    principal: AnyStaff,
    session: Session,
    status_: Annotated[str | None, Query(alias="status", pattern="^(active|expired|pending_review|reviewed)$")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
) -> schemas.GrantPage:
    items, next_cursor = await grants.list_grants(session, principal, status_, limit, cursor)
    return schemas.GrantPage(items=items, next_cursor=next_cursor)


@router.post("/{grant_id}/revoke", response_model=schemas.GrantOut)
async def revoke_grant(principal: AnyStaff, session: Session, grant_id: uuid.UUID) -> schemas.GrantOut:
    row = await grants.revoke(session, principal, grant_id)
    out = grants.grant_out(row)
    await session.commit()
    return out


@router.post("/{grant_id}/review", response_model=schemas.GrantOut)
async def review_grant(
    principal: SecurityAdmin, session: Session, grant_id: uuid.UUID, body: schemas.ReviewIn
) -> schemas.GrantOut:
    require(await authorize(session, principal, Action.BREAKGLASS_REVIEW, OBJECTLESS))
    row = await grants.review(session, principal, grant_id, body)
    out = grants.grant_out(row)
    await session.commit()
    return out
