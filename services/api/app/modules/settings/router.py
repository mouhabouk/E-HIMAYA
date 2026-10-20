"""National settings (phase 9 §2): read by every staff member, changed by the central room only, per key."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import CurrentPrincipal, Principal
from app.modules.settings import service
from app.modules.settings.models import PlatformSetting

router = APIRouter(prefix="/api/v1/staff/settings", tags=["staff", "settings"])
Session = Annotated[AsyncSession, Depends(get_session)]


async def _staff(principal: CurrentPrincipal) -> Principal:
    if not principal.is_staff or not principal.roles:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient_role")
    return principal


Staff = Annotated[Principal, Depends(_staff)]


class SettingOut(BaseModel):
    key: str
    value: Any
    version: int
    updated_by_name: str | None
    updated_at: datetime | None
    editable: bool


class SettingsOut(BaseModel):
    items: list[SettingOut]


class SettingIn(BaseModel):
    value: Any
    version: int = Field(ge=0)
    reason: str = Field(min_length=5, max_length=500)


def _out(row: PlatformSetting, principal: Principal) -> SettingOut:
    return SettingOut(
        key=row.key,
        value=row.value,
        version=row.version,
        updated_by_name=row.updated_by_name,
        updated_at=row.updated_at,
        editable=service.editable(principal, row.key),
    )


@router.get("", response_model=SettingsOut)
async def list_settings(principal: Staff, session: Session) -> SettingsOut:
    return SettingsOut(items=[_out(row, principal) for row in await service.rows(session)])


@router.put("/{key}", response_model=SettingOut)
async def put_setting(
    principal: Staff,
    session: Session,
    body: SettingIn,
    key: Annotated[str, Path(max_length=100)],
) -> SettingOut:
    row = await service.update(session, principal, key, body.value, body.version, body.reason.strip())
    await session.commit()
    service.invalidate(key)
    return _out(row, principal)
