"""Staff accounts in Keycloak (phase 9 §6.2), through the admin REST API of the staff realm.

The API authenticates as the confidential client ``ehimaya-account-admin`` (client credentials; its service account
holds ``realm-management: manage-users, view-users``). The account administration rules (own gouvernorat, grantable
roles, no self-edit) are enforced by ``accounts`` before any call here; this module only speaks Keycloak.
Tests replace the directory with a fake through ``set_directory``.
"""

import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx
import structlog

from app.core.config import get_settings
from app.core.security import REALM_ROLES, Realm

log = structlog.get_logger()

STAFF_ROLES = frozenset(r.value for r in REALM_ROLES[Realm.STAFF])
REQUIRED_ACTIONS = ["CONFIGURE_TOTP", "UPDATE_PASSWORD", "VERIFY_EMAIL"]
TIMEOUT_S = 10.0


class DirectoryError(Exception):
    """Keycloak answered with an error or could not be reached (502 identity_provider_error)."""


class UsernameTaken(DirectoryError):
    """Keycloak refused a duplicate username or e-mail (409 username_taken)."""


@dataclass(slots=True)
class StaffAccount:
    id: str
    username: str
    email: str | None
    first_name: str | None
    last_name: str | None
    enabled: bool
    roles: set[str] = field(default_factory=set)
    scope_level: str | None = None
    gouvernorat_code: int | None = None
    mfa_configured: bool = False


class Directory(Protocol):
    async def list_accounts(
        self, *, gouvernorat_code: int | None, q: str | None, first: int, max_results: int
    ) -> list[StaffAccount]: ...

    async def get_account(self, account_id: str) -> StaffAccount | None: ...

    async def create_account(self, account: StaffAccount, required_actions: list[str]) -> str: ...

    async def set_roles(self, account_id: str, add: set[str], remove: set[str]) -> None: ...

    async def set_enabled(self, account_id: str, enabled: bool) -> None: ...

    async def reset_credentials(self, account_id: str) -> None: ...

    async def sign_out(self, account_id: str) -> None: ...


def _attribute(user: dict[str, Any], name: str) -> str | None:
    values = (user.get("attributes") or {}).get(name) or []
    return str(values[0]) if values else None


def _code(raw: str | None) -> int | None:
    try:
        return int(raw) if raw else None
    except ValueError:
        return None


class KeycloakDirectory:
    def __init__(self, base_url: str, realm: str, client_id: str, client_secret: str) -> None:
        self._base = base_url.rstrip("/")
        self._realm = realm
        self._client_id = client_id
        self._client_secret = client_secret
        self._token: tuple[str, float] | None = None

    @property
    def _admin(self) -> str:
        return f"{self._base}/admin/realms/{self._realm}"

    async def _access_token(self, client: httpx.AsyncClient) -> str:
        if self._token is not None and self._token[1] > time.monotonic():
            return self._token[0]
        response = await client.post(
            f"{self._base}/realms/{self._realm}/protocol/openid-connect/token",
            data={"grant_type": "client_credentials"},
            auth=(self._client_id, self._client_secret),
        )
        if response.status_code != 200:
            raise DirectoryError(f"token_{response.status_code}")
        body = response.json()
        self._token = (str(body["access_token"]), time.monotonic() + max(int(body.get("expires_in", 60)) - 30, 5))
        return self._token[0]

    async def _call(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
                token = await self._access_token(client)
                response = await client.request(
                    method, f"{self._admin}{path}", headers={"Authorization": f"Bearer {token}"}, **kwargs
                )
        except httpx.HTTPError as exc:
            raise DirectoryError(type(exc).__name__) from exc
        if response.status_code == 409:
            raise UsernameTaken("conflict")
        if response.status_code >= 400 and response.status_code != 404:
            log.warning("keycloak.admin_error", path=path.split("?")[0], status=response.status_code)
            raise DirectoryError(f"http_{response.status_code}")
        return response

    async def _account(self, user: dict[str, Any]) -> StaffAccount:
        uid = str(user["id"])
        roles = await self._call("GET", f"/users/{uid}/role-mappings/realm")
        credentials = await self._call("GET", f"/users/{uid}/credentials")
        return StaffAccount(
            id=uid,
            username=str(user.get("username") or ""),
            email=user.get("email"),
            first_name=user.get("firstName"),
            last_name=user.get("lastName"),
            enabled=bool(user.get("enabled")),
            roles={str(r["name"]) for r in roles.json()} & STAFF_ROLES if roles.status_code == 200 else set(),
            scope_level=_attribute(user, "scope_level"),
            gouvernorat_code=_code(_attribute(user, "gouvernorat_code")),
            mfa_configured=credentials.status_code == 200 and any(c.get("type") == "otp" for c in credentials.json()),
        )

    async def list_accounts(
        self, *, gouvernorat_code: int | None, q: str | None, first: int, max_results: int
    ) -> list[StaffAccount]:
        # One page of the realm's users; the caller filters roles (listing a role's members needs ``view-realm``,
        # which the service account does not hold).
        params: dict[str, Any] = {"first": first, "max": max_results, "briefRepresentation": "false"}
        if gouvernorat_code is not None:
            params["q"] = f"gouvernorat_code:{gouvernorat_code}"
        if q:
            params["search"] = q
        response = await self._call("GET", "/users", params=params)
        users = response.json() if response.status_code == 200 else []
        return [await self._account(u) for u in users]

    async def get_account(self, account_id: str) -> StaffAccount | None:
        response = await self._call("GET", f"/users/{account_id}")
        if response.status_code == 404:
            return None
        return await self._account(response.json())

    async def create_account(self, account: StaffAccount, required_actions: list[str]) -> str:
        attributes: dict[str, list[str]] = {"scope_level": [account.scope_level or "gouvernorat"]}
        if account.gouvernorat_code is not None:
            attributes["gouvernorat_code"] = [str(account.gouvernorat_code)]
        response = await self._call(
            "POST",
            "/users",
            json={
                "username": account.username,
                "email": account.email,
                "firstName": account.first_name,
                "lastName": account.last_name,
                "enabled": True,
                "emailVerified": False,
                "attributes": attributes,
                "requiredActions": required_actions,
            },
        )
        location = str(response.headers.get("Location", ""))
        account_id = location.rstrip("/").rsplit("/", 1)[-1]
        if response.status_code != 201 or not account_id:
            raise DirectoryError(f"create_{response.status_code}")
        await self.set_roles(account_id, set(account.roles), set())
        return account_id

    async def _role_representations(self, account_id: str, names: set[str], mapped: bool) -> list[dict[str, Any]]:
        """Representations of realm roles, read from the user's mappings (``view-users`` is enough, unlike
        ``/roles``): the available ones to add, the current ones to remove."""
        path = f"/users/{account_id}/role-mappings/realm" + ("" if mapped else "/available")
        response = await self._call("GET", path)
        found = {str(r["name"]): r for r in response.json()} if response.status_code == 200 else {}
        missing = names - set(found)
        if missing and not mapped:
            raise DirectoryError("role_unavailable")
        return [found[n] for n in sorted(names) if n in found]

    async def set_roles(self, account_id: str, add: set[str], remove: set[str]) -> None:
        if add:
            reps = await self._role_representations(account_id, add, mapped=False)
            await self._call("POST", f"/users/{account_id}/role-mappings/realm", json=reps)
        if remove:
            reps = await self._role_representations(account_id, remove, mapped=True)
            if reps:
                await self._call("DELETE", f"/users/{account_id}/role-mappings/realm", json=reps)

    async def _update(self, account_id: str, changes: dict[str, Any]) -> None:
        """A user update: Keycloak replaces the attributes with what the PUT carries, so the whole representation is
        read and sent back with the changes."""
        response = await self._call("GET", f"/users/{account_id}")
        if response.status_code != 200:
            raise DirectoryError(f"user_{response.status_code}")
        await self._call("PUT", f"/users/{account_id}", json={**response.json(), **changes})

    async def set_enabled(self, account_id: str, enabled: bool) -> None:
        await self._update(account_id, {"enabled": enabled})

    async def reset_credentials(self, account_id: str) -> None:
        # No e-mail is sent: the password must be changed and the second factor set up again at the next sign-in,
        # and every open session ends now.
        credentials = await self._call("GET", f"/users/{account_id}/credentials")
        for credential in credentials.json() if credentials.status_code == 200 else []:
            if credential.get("type") == "otp":
                await self._call("DELETE", f"/users/{account_id}/credentials/{credential['id']}")
        await self._update(account_id, {"requiredActions": ["UPDATE_PASSWORD", "CONFIGURE_TOTP"]})
        await self.sign_out(account_id)

    async def sign_out(self, account_id: str) -> None:
        """End every Keycloak session of the account (its refresh tokens stop working)."""
        response = await self._call("POST", f"/users/{account_id}/logout")
        if response.status_code not in (200, 204):
            raise DirectoryError(f"logout_{response.status_code}")


_directory: Directory | None = None


def get_directory() -> Directory | None:
    """The configured directory, or None when KEYCLOAK_ADMIN_URL / the client secret are not set."""
    global _directory
    if _directory is None:
        settings = get_settings()
        if settings.keycloak_admin_url and settings.keycloak_admin_client_secret is not None:
            _directory = KeycloakDirectory(
                settings.keycloak_admin_url,
                settings.keycloak_staff_realm,
                settings.keycloak_admin_client_id,
                settings.keycloak_admin_client_secret.get_secret_value(),
            )
    return _directory


def set_directory(directory: Directory | None) -> None:
    """Used by tests to inject a fake directory."""
    global _directory
    _directory = directory
