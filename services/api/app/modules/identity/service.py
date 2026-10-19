"""Reporter identity: registered citizens (Keycloak public realm) and anonymous devices (BR-01, BR-02).

Every reporter has exactly one ``identity.account`` row, the unified USERID (FR-A-004), created on the
first authenticated call. Anonymous devices are known only by ``HMAC(server secret, device key)``.
"""

import base64
import binascii
import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import pseudonym
from app.core.db import get_session
from app.core.security import OptionalPrincipal, Principal, Realm, Role
from app.modules.identity.models import Account, AccountKind, AccountStatus, Consent

DEVICE_KEY_BYTES = 32
_ORG_ROLES = frozenset({Role.ORG_ADMIN, Role.ORG_MEMBER})


@dataclass(frozen=True, slots=True)
class Reporter:
    user_id: uuid.UUID
    kind: AccountKind
    principal: Principal | None

    @property
    def is_anonymous(self) -> bool:
        return self.kind is AccountKind.ANONYMOUS

    @property
    def actor(self) -> str:
        """Audit actor string; anonymous reporters are referenced by account id only."""
        if self.principal is not None:
            return f"{self.principal.realm.value}:{self.principal.subject}"
        return f"anonymous:{self.user_id}"


def parse_device_key(raw: str) -> bytes:
    try:
        key = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_device_key") from exc
    if len(key) != DEVICE_KEY_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_device_key")
    return key


async def _upsert_account(session: AsyncSession, kind: AccountKind, *, sub: str | None, anon: bytes | None) -> Account:
    column = Account.keycloak_sub if sub is not None else Account.anon_pseudonym
    value: str | bytes = sub if sub is not None else anon  # type: ignore[assignment]
    await session.execute(
        insert(Account)
        .values(kind=kind, keycloak_sub=sub, anon_pseudonym=anon)
        .on_conflict_do_nothing(index_elements=[column])
    )
    account = await session.scalar(select(Account).where(column == value))
    assert account is not None
    return account


async def resolve_reporter(
    session: AsyncSession, principal: Principal | None, device_key_header: str | None
) -> Reporter:
    if principal is not None:
        if principal.realm is not Realm.PUBLIC:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "reporter_realm_required")
        kind = AccountKind.ORGANIZATION if principal.roles & _ORG_ROLES else AccountKind.CITIZEN
        account = await _upsert_account(session, kind, sub=principal.subject, anon=None)
    elif device_key_header:
        account = await _upsert_account(
            session, AccountKind.ANONYMOUS, sub=None, anon=pseudonym(parse_device_key(device_key_header))
        )
    else:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "authentication_required", headers={"WWW-Authenticate": "Bearer"}
        )

    if account.status is not AccountStatus.ACTIVE:
        if account.kind is AccountKind.ANONYMOUS:
            # BR-04: a quarantined pseudonym may only report again after registering.
            raise HTTPException(status.HTTP_403_FORBIDDEN, "anon_blocked")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "account_suspended")
    await session.commit()
    return Reporter(user_id=account.user_id, kind=account.kind, principal=principal)


async def get_reporter(
    principal: OptionalPrincipal,
    session: Annotated[AsyncSession, Depends(get_session)],
    x_device_key: Annotated[str | None, Header(max_length=64)] = None,
) -> Reporter:
    return await resolve_reporter(session, principal, x_device_key)


CurrentReporter = Annotated[Reporter, Depends(get_reporter)]


async def has_consented(session: AsyncSession, user_id: uuid.UUID, version: str) -> bool:
    found = await session.scalar(
        select(Consent.id).where(Consent.user_id == user_id, Consent.charter_version == version).limit(1)
    )
    return found is not None
