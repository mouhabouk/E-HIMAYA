"""OIDC bearer-token verification against the two Keycloak realms.

* ``ehimaya-public`` — citizens, volunteers and institutions (mobile app, portal).
* ``ehimaya-staff``  — operators, commanders, committees, administrators (dashboard, MFA mandatory).

A role is honoured only when it comes from the realm that owns it, so a token from the public
realm can never carry a staff role even if such a role were created there by mistake.
"""

from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Annotated, Any, Literal, Protocol
from urllib.parse import urlsplit

import jwt
from anyio import to_thread
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.sessions import is_revoked


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
    # Technical administration split in phase 9 (docs/api/phase-9-contract.md §1.1): none grants operational rights.
    SECURITY_ADMIN = "security_admin"
    AI_ADMIN = "ai_admin"
    REGIONAL_ACCOUNT_ADMIN = "regional_account_admin"
    # Phase C1-a: checks the doctors' registrations of a gouvernorat (no operational rights).
    MEDICAL_COORDINATOR = "medical_coordinator"
    # Phase P4a: the leader of an intervention team, on the staff app (shift, mission steps, field reports only).
    TEAM_LEADER = "team_leader"


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
            Role.SECURITY_ADMIN,
            Role.AI_ADMIN,
            Role.REGIONAL_ACCOUNT_ADMIN,
            Role.MEDICAL_COORDINATOR,
            Role.TEAM_LEADER,
        }
    ),
}


class Function(StrEnum):
    """Families of staff roles (phase 9 §1.1). Derived from the roles, never read from a token claim."""

    COMMAND = "command"
    OPERATIONS = "operations"
    TECHNICAL = "technical"
    SUPPORT = "support"
    FIELD = "field"


FUNCTION_ROLES: dict[Function, frozenset[Role]] = {
    Function.COMMAND: frozenset({Role.CENTRAL_COMMITTEE, Role.LOCAL_COMMITTEE, Role.FIELD_COMMANDER}),
    Function.OPERATIONS: frozenset({Role.OPERATOR, Role.OPS_MANAGER}),
    Function.TECHNICAL: frozenset({Role.SYSADMIN, Role.SECURITY_ADMIN, Role.AI_ADMIN, Role.REGIONAL_ACCOUNT_ADMIN}),
    Function.SUPPORT: frozenset({Role.CONTENT_EDITOR, Role.ORG_AUDITOR, Role.MEDICAL_COORDINATOR}),
    Function.FIELD: frozenset({Role.TEAM_LEADER}),
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

    @property
    def functions(self) -> frozenset[str]:
        """Role families of a staff member (a token may carry roles of several families)."""
        if not self.is_staff:
            return frozenset()
        return frozenset(f.value for f, members in FUNCTION_ROLES.items() if self.roles & members)

    @property
    def room(self) -> Literal["central", "regional"]:
        """Operations room the staff member works in: central (national scope) or regional."""
        return "central" if self.is_national else "regional"


#: The signed-in principal of the current request (set by ``get_principal``); the audit log reads the actor's display
#: name from it so the regional audit view can show who acted without exposing the account id (phase 9 §7.3).
current_principal: ContextVar[Principal | None] = ContextVar("ehimaya_principal", default=None)


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


#: Authentication methods (RFC 8176 ``amr`` values) that prove a second factor.
SECOND_FACTORS = frozenset({"otp", "hwk", "mfa"})


class TokenVerifier:
    def __init__(
        self, issuers: list[str], audience: str, key_resolver: KeyResolver, *, staff_mfa_required: bool = True
    ) -> None:
        self._issuers = {iss.rstrip("/"): Realm(urlsplit(iss).path.rsplit("/", 1)[-1]) for iss in issuers}
        self._audience = audience
        self._key_resolver = key_resolver
        self._staff_mfa_required = staff_mfa_required

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

        if realm is Realm.STAFF and self._staff_mfa_required:
            amr = claims.get("amr")
            if not isinstance(amr, list) or not SECOND_FACTORS & {str(m) for m in amr}:
                # RFC 9470: the client signs in again with a stronger method.
                raise HTTPException(
                    status.HTTP_401_UNAUTHORIZED,
                    "mfa_required",
                    headers={"WWW-Authenticate": 'Bearer error="insufficient_user_authentication"'},
                )

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
            settings.oidc_issuers,
            settings.oidc_audience,
            JwksKeyResolver(settings.oidc_jwks_base_url),
            staff_mfa_required=settings.staff_mfa_required,
        )
    return _verifier


def set_token_verifier(verifier: TokenVerifier | None) -> None:
    """Used by tests to inject a verifier with a static key."""
    global _verifier
    _verifier = verifier


_bearer = HTTPBearer(auto_error=False)


async def authenticate(token: str) -> Principal:
    """Verify a bearer token and refuse it when its session was revoked (phase 10 §1.2)."""
    principal = await to_thread.run_sync(get_token_verifier().verify, token)
    if await is_revoked(principal.subject, int(principal.claims["iat"])):
        raise _unauthorized("session_revoked")
    return principal


async def get_optional_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal | None:
    if credentials is None:
        return None
    return await authenticate(credentials.credentials)


async def get_principal(principal: Annotated[Principal | None, Depends(get_optional_principal)]) -> Principal:
    if principal is None:
        raise _unauthorized("authentication_required")
    # Database scope of this request (row-level security, phase 9 §9.1); reporters refine it in get_reporter.
    from app.core.access import scope_of_principal, set_db_scope

    set_db_scope(scope_of_principal(principal))
    current_principal.set(principal)
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
