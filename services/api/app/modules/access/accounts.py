"""Regional account administration (phase 9 §6.2): a proxy in front of the Keycloak admin API of the staff realm.

A ``regional_account_admin`` with gouvernorat g sees and edits only the accounts of g (others answer 404), creates
accounts of g only (403 ``out_of_scope``) and grants the operational roles only (403 ``role_not_grantable``). A
national one manages every gouvernorat and may also grant central_committee and org_auditor; the technical roles are
granted only by a national ``security_admin``. Nobody edits their own account. Every change is written to
``access.account_admin_log`` and to the audit log with the account's gouvernorat.

Disabling an account, changing its roles, resetting its credentials or signing it out also revokes the access tokens
it already holds (phase 10 §1.2): they stop at the next request instead of when they expire.
"""

import uuid
from collections.abc import Awaitable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import sessions
from app.core.access import Action, Ctx, authorize, require
from app.core.db import get_session
from app.core.security import REALM_ROLES, Principal, Realm, Role, require_roles
from app.modules.access import schemas
from app.modules.access.keycloak import REQUIRED_ACTIONS, Directory, DirectoryError, StaffAccount, UsernameTaken
from app.modules.access.keycloak import get_directory as _get_directory
from app.modules.access.models import AccountAdminLog
from app.modules.audit import service as audit

router = APIRouter(prefix="/api/v1/staff/accounts", tags=["accounts"])

Session = Annotated[AsyncSession, Depends(get_session)]
Admin = Annotated[Principal, Depends(require_roles(Role.REGIONAL_ACCOUNT_ADMIN, Role.SECURITY_ADMIN))]

REGIONAL_GRANTABLE = frozenset(
    {
        Role.OPERATOR,
        Role.OPS_MANAGER,
        Role.FIELD_COMMANDER,
        Role.LOCAL_COMMITTEE,
        Role.CONTENT_EDITOR,
        Role.MEDICAL_COORDINATOR,
    }
)
NATIONAL_GRANTABLE = REGIONAL_GRANTABLE | {Role.CENTRAL_COMMITTEE, Role.ORG_AUDITOR}
ALL_STAFF_ROLES = REALM_ROLES[Realm.STAFF]
PAGE = 50


def _forbidden(code: str) -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, code)


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "not_found")


def _provider_error() -> HTTPException:
    return HTTPException(status.HTTP_502_BAD_GATEWAY, "identity_provider_error")


def _is_security_admin(principal: Principal) -> bool:
    return Role.SECURITY_ADMIN in principal.roles and principal.is_national


def _is_account_admin(principal: Principal) -> bool:
    return Role.REGIONAL_ACCOUNT_ADMIN in principal.roles


def grantable(principal: Principal) -> frozenset[Role]:
    """Roles the caller may add to or remove from an account."""
    if _is_security_admin(principal):
        return ALL_STAFF_ROLES
    if _is_account_admin(principal):
        return NATIONAL_GRANTABLE if principal.is_national else REGIONAL_GRANTABLE
    return frozenset()


def _admin_gouvernorat(principal: Principal) -> int | None:
    """The gouvernorat the caller administers (None: every gouvernorat); 403 for a regional security admin alone."""
    if _is_security_admin(principal):
        return None
    if not _is_account_admin(principal):
        raise _forbidden("action_not_allowed")
    return principal.gouvernorat_code


def directory() -> Directory:
    found = _get_directory()
    if found is None:
        raise _provider_error()
    return found


async def _check_manage(session: AsyncSession, principal: Principal, code: int | None) -> None:
    """``account.manage`` on an account of gouvernorat ``code`` (404 outside the caller's gouvernorat)."""
    admin_code = _admin_gouvernorat(principal)
    if admin_code is None and _is_security_admin(principal):
        return
    if admin_code is not None and code != admin_code:
        raise _not_found()
    require(await authorize(session, principal, Action.ACCOUNT_MANAGE, Ctx(lead=code)))


def account_out(account: StaffAccount) -> schemas.AccountOut:
    return schemas.AccountOut(
        id=account.id,
        username=account.username,
        email=account.email,
        first_name=account.first_name,
        last_name=account.last_name,
        enabled=account.enabled,
        roles=sorted(Role(r) for r in account.roles if r in {x.value for x in ALL_STAFF_ROLES}),
        scope_level="national" if account.scope_level == "national" else "gouvernorat" if account.scope_level else None,
        gouvernorat_code=account.gouvernorat_code,
        mfa_configured=account.mfa_configured,
    )


async def _log(
    session: AsyncSession,
    principal: Principal,
    action: str,
    account: StaffAccount,
    details: dict[str, Any],
) -> None:
    session.add(
        AccountAdminLog(
            actor=audit.actor_of(principal),
            actor_name=audit.name_of(principal),
            action=action,
            account_id=account.id,
            username=account.username,
            gouvernorat_code=account.gouvernorat_code,
            details=details,
        )
    )
    await session.flush()
    await audit.record(
        session,
        actor=audit.actor_of(principal),
        action=action,
        target=f"account:{account.id}",
        details={"account_id": account.id, "username": account.username, **details},
        gouvernorats=[account.gouvernorat_code] if account.gouvernorat_code is not None else None,
    )


async def _visible_account(session: AsyncSession, principal: Principal, account_id: str) -> StaffAccount:
    account: StaffAccount | None = await _call(directory().get_account(account_id))
    if account is None:
        raise _not_found()
    await _check_manage(session, principal, account.gouvernorat_code)
    if account.id == principal.subject:
        raise _forbidden("self_edit")
    return account


async def _call[T](awaitable: Awaitable[T]) -> T:
    try:
        return await awaitable
    except UsernameTaken as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "username_taken") from exc
    except DirectoryError as exc:
        raise _provider_error() from exc


def _encode(offset: int) -> str:
    return str(offset)


def _decode(cursor: str | None) -> int:
    if not cursor:
        return 0
    if not cursor.isdigit() or int(cursor) > 100_000:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_cursor")
    return int(cursor)


# ---------------------------------------------------------------- routes


@router.get("", response_model=schemas.AccountPage)
async def list_accounts(
    principal: Admin,
    session: Session,
    gouvernorat: Annotated[int | None, Query(ge=1, le=99)] = None,
    role: Role | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    cursor: str | None = None,
) -> schemas.AccountPage:
    admin_code = _admin_gouvernorat(principal)
    if admin_code is not None:
        if gouvernorat is not None and gouvernorat != admin_code:
            raise _forbidden("out_of_scope")
        gouvernorat = admin_code
        require(await authorize(session, principal, Action.ACCOUNT_MANAGE, Ctx(lead=admin_code)))
    if role is not None and role not in ALL_STAFF_ROLES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_role")
    first = _decode(cursor)
    found: list[StaffAccount] = await _call(
        directory().list_accounts(gouvernorat_code=gouvernorat, q=q, first=first, max_results=PAGE)
    )
    # The gouvernorat, role and search of every account are checked again whatever the directory answered.
    items = [
        account_out(a)
        for a in found
        if (gouvernorat is None or a.gouvernorat_code == gouvernorat)
        and (role is None or role.value in a.roles)
        and (q is None or q.lower() in f"{a.username} {a.email or ''} {a.first_name or ''} {a.last_name or ''}".lower())
    ]
    return schemas.AccountPage(items=items, next_cursor=_encode(first + PAGE) if len(found) == PAGE else None)


@router.post("", response_model=schemas.AccountOut, status_code=status.HTTP_201_CREATED)
async def create_account(principal: Admin, session: Session, body: schemas.AccountIn) -> schemas.AccountOut:
    admin_code = _admin_gouvernorat(principal)
    if admin_code is not None:
        if body.scope_level != "gouvernorat" or body.gouvernorat_code not in (None, admin_code):
            raise _forbidden("out_of_scope")
        code: int | None = admin_code
    elif body.scope_level == "national":
        if body.gouvernorat_code is not None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_gouvernorat")
        code = None
    else:
        if body.gouvernorat_code is None or not await session.scalar(
            text("SELECT count(*) FROM geo.gouvernorat WHERE code = :c"), {"c": body.gouvernorat_code}
        ):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_gouvernorat")
        code = body.gouvernorat_code
    await _check_manage(session, principal, code)
    roles = set(body.roles)
    if not roles <= grantable(principal):
        raise _forbidden("role_not_grantable")
    account = StaffAccount(
        id="",
        username=body.username,
        email=body.email,
        first_name=body.first_name,
        last_name=body.last_name,
        enabled=True,
        roles={r.value for r in roles},
        scope_level=body.scope_level,
        gouvernorat_code=code,
    )
    account.id = await _call(directory().create_account(account, list(REQUIRED_ACTIONS)))
    await _log(
        session,
        principal,
        "account.create",
        account,
        {"roles": sorted(account.roles), "scope_level": body.scope_level},
    )
    await session.commit()
    return account_out(account)


@router.patch("/{account_id}", response_model=schemas.AccountOut)
async def update_account(
    principal: Admin, session: Session, account_id: uuid.UUID, body: schemas.AccountPatch
) -> schemas.AccountOut:
    account = await _visible_account(session, principal, str(account_id))
    details: dict[str, Any] = {}
    if body.roles is not None:
        wanted = {r.value for r in body.roles}
        add, remove = wanted - account.roles, account.roles - wanted
        allowed = {r.value for r in grantable(principal)}
        if not (add | remove) <= allowed:
            raise _forbidden("role_not_grantable")
        if add or remove:
            await _call(directory().set_roles(account.id, add, remove))
            account.roles = wanted
            details.update(added=sorted(add), removed=sorted(remove))
    if body.enabled is not None and body.enabled != account.enabled:
        await _call(directory().set_enabled(account.id, body.enabled))
        account.enabled = body.enabled
        details["enabled"] = body.enabled
    if details:
        await _log(session, principal, "account.update", account, details)
        await session.commit()
        if "enabled" in details or "added" in details:
            await sessions.revoke(account.id)
    return account_out(account)


@router.post("/{account_id}/reset-credentials", status_code=status.HTTP_204_NO_CONTENT)
async def reset_credentials(principal: Admin, session: Session, account_id: uuid.UUID) -> None:
    account = await _visible_account(session, principal, str(account_id))
    await _call(directory().reset_credentials(account.id))
    await _log(session, principal, "account.reset", account, {})
    await session.commit()
    await sessions.revoke(account.id)


@router.post("/{account_id}/sign-out", status_code=status.HTTP_204_NO_CONTENT)
async def sign_out(principal: Admin, session: Session, account_id: uuid.UUID) -> None:
    """End every session of the account now: Keycloak sessions and the access tokens already issued."""
    account = await _visible_account(session, principal, str(account_id))
    await _call(directory().sign_out(account.id))
    await _log(session, principal, "account.sign_out", account, {})
    await session.commit()
    await sessions.revoke(account.id)
