"""OIDC bearer-token verification against the two Keycloak realms.

* ``ehimaya-public`` — citizens, volunteers and institutions (mobile app, portal).
* ``ehimaya-staff``  — operators, commanders, committees, administrators (dashboard, MFA mandatory).

A role is honoured only when it comes from the realm that owns it, so a token from the public
realm can never carry a staff role even if such a role were created there by mistake.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Annotated, Any, Protocol
from urllib.parse import urlsplit

import jwt
from anyio import to_thread
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings


class Realm(StrEnum):
    PUBLIC = "ehimaya-public"
    STAFF = "ehimaya-staff"


class Role(StrEnum):
    # public realm
    CITIZEN = "citizen"
    VOLUNTEER = "volunteer"
    ORG_ADMIN = "org_admin"
    ORG_MEMBER = "org_member"
    # staff realm
    OPERATOR = "operator"
    OPS_MANAGER = "ops_manager"
    FIELD_COMMANDER = "field_commander"
    LOCAL_COMMITTEE = "local_committee"
    CENTRAL_COMMITTEE = "central_committee"
    ORG_AUDITOR = "org_auditor"
    CONTENT_EDITOR = "content_editor"
    SYSADMIN = "sysadmin"


REALM_ROLES: dict[Realm, frozenset[Role]] = {
    Realm.PUBLIC: frozenset({Role.CITIZEN, Role.VOLUNTEER, Role.ORG_ADMIN, Role.ORG_MEMBER}),
    Realm.STAFF: frozenset(
        {
            Role.OPERATOR,
            Role.OPS_MANAGER,
            Role.FIELD_COMMANDER,
            Role.LOCAL_COMMITTEE,
            Role.CENTRAL_COMMITTEE,
            Role.ORG_AUDITOR,
            Role.CONTENT_EDITOR,
            Role.SYSADMIN,
        }
    ),
}


@dataclass(frozen=True, slots=True)
class Principal:
    subject: str
    realm: Realm
    roles: frozenset[Role]
    # Geographic scope for staff: None means national scope.
    gouvernorat_code: int | None = None
    claims: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @property
    def is_staff(self) -> bool:
        return self.realm is Realm.STAFF

    @property
    def is_national(self) -> bool:
        return self.is_staff and self.gouvernorat_code is None

    def can_access_gouvernorat(self, code: int) -> bool:
        return self.is_national or self.gouvernorat_code == code


class KeyResolver(Protocol):
    def __call__(self, token: str, issuer: str) -> Any: ...


class JwksKeyResolver:
    """Resolves the signing key from the issuer's JWKS endpoint (keys are cached by PyJWKClient)."""

    def __init__(self, jwks_base_url: str | None = None) -> None:
        self._jwks_base_url = jwks_base_url.rstrip("/") if jwks_base_url else None
        self._clients: dict[str, jwt.PyJWKClient] = {}

    def _jwks_url(self, issuer: str) -> str:
        if self._jwks_base_url:
            return f"{self._jwks_base_url}{urlsplit(issuer).path}/protocol/openid-connect/certs"
        return f"{issuer}/protocol/openid-connect/certs"

    def __call__(self, token: str, issuer: str) -> Any:
        client = self._clients.get(issuer)
        if client is None:
            client = jwt.PyJWKClient(self._jwks_url(issuer), cache_keys=True, lifespan=600, timeout=5)
            self._clients[issuer] = client
        return client.get_signing_key_from_jwt(token).key


class TokenVerifier:
    def __init__(self, issuers: list[str], audience: str, key_resolver: KeyResolver) -> None:
        self._issuers = {iss.rstrip("/"): Realm(urlsplit(iss).path.rsplit("/", 1)[-1]) for iss in issuers}
        self._audience = audience
        self._key_resolver = key_resolver

    def verify(self, token: str) -> Principal:
        try:
            unverified = jwt.decode(token, options={"verify_signature": False})
        except jwt.PyJWTError as exc:
            raise _unauthorized("invalid_token") from exc
        issuer = str(unverified.get("iss", "")).rstrip("/")
        realm = self._issuers.get(issuer)
        if realm is None:
            raise _unauthorized("invalid_token")
        try:
            key = self._key_resolver(token, issuer)
            claims: dict[str, Any] = jwt.decode(
                token,
                key=key,
                algorithms=["RS256", "ES256", "PS256"],
                audience=self._audience,
                issuer=issuer,
                options={"require": ["exp", "iat", "iss", "sub", "aud"]},
                leeway=10,
            )
        except jwt.PyJWTError as exc:
            raise _unauthorized("invalid_token") from exc
        except Exception as exc:  # JWKS unreachable, etc.
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "identity_provider_unavailable") from exc

        raw_roles = set(claims.get("realm_access", {}).get("roles", []))
        allowed = REALM_ROLES[realm]
        roles = frozenset(r for r in allowed if r.value in raw_roles)

        gouvernorat_code: int | None = None
        if realm is Realm.STAFF and claims.get("scope_level") != "national":
            try:
                gouvernorat_code = int(claims["gouvernorat_code"])
            except (KeyError, TypeError, ValueError) as exc:
                # A staff account without an explicit scope is refused rather than silently national.
                raise HTTPException(status.HTTP_403_FORBIDDEN, "staff_scope_missing") from exc

        return Principal(
            subject=str(claims["sub"]),
            realm=realm,
            roles=roles,
            gouvernorat_code=gouvernorat_code,
            claims=claims,
        )


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


_verifier: TokenVerifier | None = None


def get_token_verifier() -> TokenVerifier:
    global _verifier
    if _verifier is None:
        settings = get_settings()
        _verifier = TokenVerifier(
            settings.oidc_issuers, settings.oidc_audience, JwksKeyResolver(settings.oidc_jwks_base_url)
        )
    return _verifier


def set_token_verifier(verifier: TokenVerifier | None) -> None:
    """Used by tests to inject a verifier with a static key."""
    global _verifier
    _verifier = verifier


_bearer = HTTPBearer(auto_error=False)


async def get_optional_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal | None:
    if credentials is None:
        return None
    return await to_thread.run_sync(get_token_verifier().verify, credentials.credentials)


async def get_principal(principal: Annotated[Principal | None, Depends(get_optional_principal)]) -> Principal:
    if principal is None:
        raise _unauthorized("authentication_required")
    return principal


def require_roles(*roles: Role) -> Callable[..., Awaitable[Principal]]:
    """Dependency: the caller must hold at least one of ``roles``."""
    wanted = frozenset(roles)

    async def _dependency(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
        if not principal.roles & wanted:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient_role")
        return principal

    return _dependency


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]
OptionalPrincipal = Annotated[Principal | None, Depends(get_optional_principal)]
