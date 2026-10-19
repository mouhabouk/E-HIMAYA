"""AI settings (BR-10 thresholds, BR-20 weights) and the status of the models, for the dashboard."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import Principal, Role, require_roles
from app.modules.ai import settings as ai_settings
from app.modules.ai.client import get_ai_client
from app.modules.audit import service as audit
from app.modules.audit.service import actor_of
from app.modules.reports.staff_router import READ_ROLES

router = APIRouter(prefix="/api/v1/staff/ai", tags=["ai"])

StaffReader = Annotated[Principal, Depends(require_roles(*READ_ROLES))]
# National decision: the central committee (and system administrators) tune the weights.
SettingsEditor = Annotated[Principal, Depends(require_roles(Role.CENTRAL_COMMITTEE, Role.SYSADMIN))]
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/settings", response_model=ai_settings.AiSettings)
async def get_settings(_: StaffReader, session: Session) -> ai_settings.AiSettings:
    return await ai_settings.load(session)


@router.put("/settings", response_model=ai_settings.AiSettings)
async def put_settings(
    principal: SettingsEditor, session: Session, body: ai_settings.AiSettings
) -> ai_settings.AiSettings:
    if not principal.is_national:
        raise HTTPException(status_code=403, detail="national_scope_required")
    before = (await ai_settings.load(session)).model_dump(mode="json")
    actor = actor_of(principal)
    after = await ai_settings.save(session, body, actor)
    await audit.record(
        session, actor=actor, action="ai.settings", target="ai:settings", details={"before": before, "after": after}
    )
    await session.commit()
    # New weights apply to reports scored from now on (each new analysis or regrouping).
    return body


@router.get("/status")
async def status(_: StaffReader) -> dict[str, Any]:
    client = get_ai_client()
    if client is None:
        return {"configured": False, "capabilities": {}}
    return {"configured": True, "capabilities": await client.health()}
