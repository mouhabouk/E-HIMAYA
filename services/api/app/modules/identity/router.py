from fastapi import APIRouter
from pydantic import BaseModel

from app.core.security import CurrentPrincipal

router = APIRouter(prefix="/api/v1", tags=["identity"])


class MeOut(BaseModel):
    subject: str
    realm: str
    roles: list[str]
    gouvernorat_code: int | None
    is_staff: bool


@router.get("/me", response_model=MeOut)
async def me(principal: CurrentPrincipal) -> MeOut:
    """Who am I, as seen by the API (identity, roles and geographic scope)."""
    return MeOut(
        subject=principal.subject,
        realm=principal.realm.value,
        roles=sorted(r.value for r in principal.roles),
        gouvernorat_code=principal.gouvernorat_code,
        is_staff=principal.is_staff,
    )
