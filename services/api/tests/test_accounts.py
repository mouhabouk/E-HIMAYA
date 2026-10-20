"""Regional account administration (phase 9, docs/api/phase-9-contract.md §6.2) against a fake Keycloak directory:
a regional administrator manages the accounts of its own gouvernorat only (IDOR on the path and the body), grants the
operational roles only, never edits its own account; everything is logged and audited."""

import uuid
from collections.abc import Iterator
from dataclasses import replace

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.access import keycloak
from app.modules.access.keycloak import DirectoryError, StaffAccount, UsernameTaken
from tests.scopehelpers import Staff

URL = "/api/v1/staff/accounts"
SFAX, GABES = 61, 81


class FakeDirectory:
    def __init__(self) -> None:
        self.accounts: dict[str, StaffAccount] = {}
        self.required_actions: dict[str, list[str]] = {}
        self.resets: list[str] = []
        self.down = False

    def add(self, username: str, gouvernorat: int | None, roles: set[str], account_id: str | None = None) -> str:
        account_id = account_id or str(uuid.uuid4())
        self.accounts[account_id] = StaffAccount(
            id=account_id,
            username=username,
            email=f"{username}@ehimaya.tn",
            first_name=username.title(),
            last_name="Test",
            enabled=True,
            roles=set(roles),
            scope_level="national" if gouvernorat is None else "gouvernorat",
            gouvernorat_code=gouvernorat,
        )
        return account_id

    def _check(self) -> None:
        if self.down:
            raise DirectoryError("down")

    async def list_accounts(
        self, *, gouvernorat_code: int | None, q: str | None, first: int, max_results: int
    ) -> list[StaffAccount]:
        self._check()
        # Deliberately ignores the gouvernorat filter: the API must filter again.
        return [replace(a, roles=set(a.roles)) for a in list(self.accounts.values())[first : first + max_results]]

    async def get_account(self, account_id: str) -> StaffAccount | None:
        self._check()
        found = self.accounts.get(account_id)
        return replace(found, roles=set(found.roles)) if found else None

    async def create_account(self, account: StaffAccount, required_actions: list[str]) -> str:
        self._check()
        if any(a.username == account.username for a in self.accounts.values()):
            raise UsernameTaken(account.username)
        account_id = self.add(account.username, account.gouvernorat_code, set(account.roles))
        self.required_actions[account_id] = required_actions
        return account_id

    async def set_roles(self, account_id: str, add: set[str], remove: set[str]) -> None:
        self._check()
        self.accounts[account_id].roles = (self.accounts[account_id].roles | add) - remove

    async def set_enabled(self, account_id: str, enabled: bool) -> None:
        self._check()
        self.accounts[account_id].enabled = enabled

    async def reset_credentials(self, account_id: str) -> None:
        self._check()
        self.resets.append(account_id)


@pytest.fixture
def directory() -> Iterator[FakeDirectory]:
    fake = FakeDirectory()
    keycloak.set_directory(fake)
    yield fake
    keycloak.set_directory(None)


def new_account(gouvernorat: int | None, roles: list[str], **overrides: object) -> dict[str, object]:
    return {
        "username": f"agent.{uuid.uuid4().hex[:8]}",
        "email": f"{uuid.uuid4().hex[:8]}@ehimaya.tn",
        "first_name": "Ines",
        "last_name": "Ben Salah",
        "roles": roles,
        "scope_level": "national" if gouvernorat is None else "gouvernorat",
        "gouvernorat_code": gouvernorat,
        **overrides,
    }


async def test_regional_admin_lists_and_creates_own_gouvernorat(
    client: httpx.AsyncClient, staff: Staff, directory: FakeDirectory, session: AsyncSession
) -> None:
    sfax_op = directory.add("sfax.op", SFAX, {"operator"})
    directory.add("gabes.op", GABES, {"operator"})
    admin = staff(["regional_account_admin"], gouvernorat=SFAX, name="Nadia Comptes")
    r = await client.get(URL, headers=admin)
    assert r.status_code == 200, r.text
    assert {a["username"] for a in r.json()["items"]} == {"sfax.op"}
    # Asking for another gouvernorat is refused, not answered.
    assert (await client.get(URL, params={"gouvernorat": GABES}, headers=admin)).status_code == 403
    r = await client.post(URL, json=new_account(None, ["operator"]), headers=admin)
    assert (r.status_code, r.json()["detail"]) == (403, "out_of_scope")
    r = await client.post(URL, json=new_account(SFAX, ["operator", "field_commander"]), headers=admin)
    assert r.status_code == 201, r.text
    created = r.json()
    assert (created["gouvernorat_code"], created["scope_level"]) == (SFAX, "gouvernorat")
    assert directory.required_actions[created["id"]] == ["CONFIGURE_TOTP", "UPDATE_PASSWORD", "VERIFY_EMAIL"]
    r = await client.post(URL, json=new_account(SFAX, ["operator"], username=created["username"]), headers=admin)
    assert (r.status_code, r.json()["detail"]) == (409, "username_taken")
    logged = (
        await session.execute(
            text(
                "SELECT details->'gouvernorats' AS g, details->>'actor_name' AS name FROM audit.log "
                "WHERE action = 'account.create' AND target = :t"
            ),
            {"t": f"account:{created['id']}"},
        )
    ).one()
    assert (logged.g, logged.name) == ([SFAX], "Nadia Comptes")
    assert await session.scalar(
        text("SELECT count(*) FROM access.account_admin_log WHERE account_id = :a"), {"a": created["id"]}
    )
    assert sfax_op in directory.accounts


async def test_idor_path_and_body(client: httpx.AsyncClient, staff: Staff, directory: FakeDirectory) -> None:
    gabes_op = directory.add("gabes.op2", GABES, {"operator"})
    admin = staff(["regional_account_admin"], gouvernorat=SFAX)
    # Another gouvernorat's account by id: not disclosed, untouched.
    for method, path, body in (
        ("PATCH", f"{URL}/{gabes_op}", {"enabled": False}),
        ("PATCH", f"{URL}/{gabes_op}", {"roles": ["operator", "ops_manager"]}),
        ("POST", f"{URL}/{gabes_op}/reset-credentials", None),
    ):
        r = await client.request(method, path, json=body, headers=admin)
        assert r.status_code == 404, (method, path, r.text)
    assert directory.accounts[gabes_op].enabled and directory.accounts[gabes_op].roles == {"operator"}
    assert directory.resets == []
    # Editing the gouvernorat in the body does not help.
    r = await client.post(URL, json=new_account(GABES, ["operator"]), headers=admin)
    assert (r.status_code, r.json()["detail"]) == (403, "out_of_scope")
    assert not any(a.gouvernorat_code == GABES and a.username.startswith("agent.") for a in directory.accounts.values())
    # An unknown id is a 404 as well.
    assert (await client.patch(f"{URL}/{uuid.uuid4()}", json={"enabled": False}, headers=admin)).status_code == 404


async def test_role_grant_limits(client: httpx.AsyncClient, staff: Staff, directory: FakeDirectory) -> None:
    account = directory.add("sfax.op3", SFAX, {"operator"})
    admin = staff(["regional_account_admin"], gouvernorat=SFAX)
    for role in ("central_committee", "org_auditor", "sysadmin", "security_admin", "regional_account_admin"):
        r = await client.patch(f"{URL}/{account}", json={"roles": ["operator", role]}, headers=admin)
        assert (r.status_code, r.json()["detail"]) == (403, "role_not_grantable"), role
        r = await client.post(URL, json=new_account(SFAX, [role]), headers=admin)
        assert (r.status_code, r.json()["detail"]) == (403, "role_not_grantable"), role
    r = await client.patch(f"{URL}/{account}", json={"roles": ["ops_manager", "local_committee"]}, headers=admin)
    assert r.status_code == 200, r.text
    assert directory.accounts[account].roles == {"ops_manager", "local_committee"}
    # A technical role already on the account cannot be removed by a regional administrator either.
    technical = directory.add("sfax.tech", SFAX, {"operator", "ai_admin"})
    r = await client.patch(f"{URL}/{technical}", json={"roles": ["operator"]}, headers=admin)
    assert (r.status_code, r.json()["detail"]) == (403, "role_not_grantable")


async def test_national_admin_limits(client: httpx.AsyncClient, staff: Staff, directory: FakeDirectory) -> None:
    gabes_op = directory.add("gabes.op4", GABES, {"operator"})
    national = staff(["regional_account_admin"], gouvernorat=None)
    r = await client.patch(f"{URL}/{gabes_op}", json={"roles": ["operator", "central_committee"]}, headers=national)
    assert r.status_code == 200, r.text
    r = await client.post(URL, json=new_account(None, ["org_auditor"]), headers=national)
    assert r.status_code == 201, r.text
    # Technical roles: only the national security administrator.
    r = await client.post(URL, json=new_account(None, ["security_admin"]), headers=national)
    assert (r.status_code, r.json()["detail"]) == (403, "role_not_grantable")
    security = staff(["security_admin"], gouvernorat=None)
    r = await client.post(URL, json=new_account(None, ["ai_admin"]), headers=security)
    assert r.status_code == 201, r.text
    # Other roles cannot reach the proxy at all.
    for role in ("operator", "ops_manager", "sysadmin", "central_committee"):
        assert (await client.get(URL, headers=staff([role], gouvernorat=None))).status_code == 403, role


async def test_self_edit_and_provider_errors(client: httpx.AsyncClient, staff: Staff, directory: FakeDirectory) -> None:
    me = str(uuid.uuid4())
    directory.add("sfax.admin", SFAX, {"regional_account_admin"}, account_id=me)
    admin = staff(["regional_account_admin"], gouvernorat=SFAX, sub=me)
    r = await client.patch(f"{URL}/{me}", json={"enabled": False}, headers=admin)
    assert (r.status_code, r.json()["detail"]) == (403, "self_edit")
    directory.down = True
    r = await client.get(URL, headers=admin)
    assert (r.status_code, r.json()["detail"]) == (502, "identity_provider_error")


async def test_without_directory(client: httpx.AsyncClient, staff: Staff) -> None:
    keycloak.set_directory(None)
    r = await client.get(URL, headers=staff(["regional_account_admin"], gouvernorat=SFAX))
    assert (r.status_code, r.json()["detail"]) == (502, "identity_provider_error")
