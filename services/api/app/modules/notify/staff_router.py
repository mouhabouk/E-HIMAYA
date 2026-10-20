"""Notifications and alerts management of the dashboard (FR-C-17, FR-C-18)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.ratelimit import enforce, opaque
from app.core.security import Principal, Role, require_roles
from app.modules.audit import service as audit
from app.modules.notify import schemas, service
from app.modules.reports.staff_router import READ_ROLES

router = APIRouter(prefix="/api/v1/staff", tags=["staff-notifications"])
Session = Annotated[AsyncSession, Depends(get_session)]
Editor = Annotated[
    Principal,
    Depends(require_roles(Role.CONTENT_EDITOR, Role.OPS_MANAGER, Role.LOCAL_COMMITTEE, Role.CENTRAL_COMMITTEE)),
]
# Only roles that can send an informational message to one user may resolve an e-mail to an account.
UserLookup = Annotated[Principal, Depends(require_roles(*service.INFO_ROLES))]
AlertReader = Annotated[Principal, Depends(require_roles(*READ_ROLES, Role.CONTENT_EDITOR))]
KINDS, STATUSES = ("info", "alert"), ("draft", "published", "cancelled", "expired")
LOOKUP_LIMIT, LOOKUP_WINDOW_S = 30, 600


def _csv(raw: str | None, allowed: tuple[str, ...], code: str) -> list[str]:
    values = [v.strip() for v in (raw or "").split(",") if v.strip()]
    if any(v not in allowed for v in values):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, code)
    return values


@router.get("/notifications", response_model=schemas.MessagePage)
async def list_messages(
    principal: Editor,
    session: Session,
    kind: str | None = None,
    status_: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    cursor: str | None = None,
) -> schemas.MessagePage:
    items, next_cursor = await service.staff_list(
        session, principal, _csv(kind, KINDS, "invalid_kind"), _csv(status_, STATUSES, "invalid_status"), limit, cursor
    )
    return schemas.MessagePage(items=items, next_cursor=next_cursor)


@router.post("/notifications", response_model=schemas.MessageOut, status_code=status.HTTP_201_CREATED)
async def create_message(principal: Editor, session: Session, body: schemas.MessageIn) -> schemas.MessageOut:
    message = await service.create(session, principal, body)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="notification.create",
        target=f"notification:{message.id}",
        details={"kind": message.kind},
    )
    out = await service.message_out(session, message)
    await session.commit()
    return out


@router.post("/users/lookup", response_model=schemas.UserLookupOut)
async def lookup_user(principal: UserLookup, session: Session, body: schemas.UserLookupIn) -> schemas.UserLookupOut:
    """Resolve an exact e-mail to the account a one-user notification targets (personal data: audited)."""
    await enforce(f"user-lookup:{opaque(principal.subject)}", LOOKUP_LIMIT, LOOKUP_WINDOW_S)
    try:
        found = await service.lookup_user(session, str(body.email), principal)
    except HTTPException as exc:
        # Misses are audited too, so a series of guesses stays visible (the address itself is not kept).
        await audit.record(
            session, actor=audit.actor_of(principal), action="user.lookup", details={"result": exc.detail}
        )
        await session.commit()
        raise
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="user.lookup",
        target=f"account:{found.user_id}",
        details={"result": "found"},
    )
    await session.commit()
    return found


@router.get("/notifications/{message_id}", response_model=schemas.MessageOut)
async def get_message(principal: Editor, session: Session, message_id: uuid.UUID) -> schemas.MessageOut:
    return await service.message_out(session, await service.get_in_scope(session, principal, message_id))


@router.put("/notifications/{message_id}", response_model=schemas.MessageOut)
async def update_message(
    principal: Editor, session: Session, message_id: uuid.UUID, body: schemas.MessageIn
) -> schemas.MessageOut:
    message = await service.get_in_scope(session, principal, message_id, lock=True)
    await service.update(session, principal, message, body)
    out = await service.message_out(session, message)
    await session.commit()
    return out


@router.delete("/notifications/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(principal: Editor, session: Session, message_id: uuid.UUID) -> Response:
    message = await service.get_in_scope(session, principal, message_id, lock=True)
    await service.delete(session, principal, message)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/notifications/{message_id}/audience", response_model=schemas.AudienceOut)
async def message_audience(principal: Editor, session: Session, message_id: uuid.UUID) -> schemas.AudienceOut:
    return await service.audience(session, await service.get_in_scope(session, principal, message_id))


@router.post("/notifications/{message_id}/publish", response_model=schemas.MessageOut)
async def publish_message(principal: Editor, session: Session, message_id: uuid.UUID) -> schemas.MessageOut:
    message = await service.get_in_scope(session, principal, message_id, lock=True)
    await service.publish(session, principal, message)
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action="notification.publish",
        target=f"notification:{message_id}",
        details={"kind": message.kind, "severity": message.severity, "channels": list(message.channels)},
    )
    await service.announce(session, message)
    out = await service.message_out(session, message)
    await session.commit()
    return out


@router.post("/notifications/{message_id}/cancel", response_model=schemas.MessageOut)
async def cancel_message(principal: Editor, session: Session, message_id: uuid.UUID) -> schemas.MessageOut:
    message = await service.get_in_scope(session, principal, message_id, lock=True)
    await service.cancel(session, principal, message)
    await audit.record(
        session, actor=audit.actor_of(principal), action="notification.cancel", target=f"notification:{message_id}"
    )
    await service.announce(session, message)
    out = await service.message_out(session, message)
    await session.commit()
    return out


@router.get("/alerts/active", response_model=list[schemas.MessageOut])
async def staff_active_alerts(principal: AlertReader, session: Session) -> list[schemas.MessageOut]:
    items, _ = await service.staff_list(session, principal, ["alert"], ["published"], 100, None)
    return items
