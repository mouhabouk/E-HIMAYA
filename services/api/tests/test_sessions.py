"""Phase 10 §1: MFA proven in the staff token, and session revocation."""

import time
import uuid
from collections.abc import Callable, Iterator

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import metrics, security, sessions
from app.modules.access import keycloak
from tests.conftest import _PRIVATE_KEY, PUBLIC_ISS, STAFF_ISS, TokenFactory, bearer
from tests.test_accounts import URL, FakeDirectory

Staff = Callable[..., dict[str, str]]
SFAX = 61


async def test_staff_token_without_second_factor_is_refused(
    client: httpx.AsyncClient, make_token: TokenFactory
) -> None:
    scope = {"gouvernorat_code": "61"}
    # make_token gives staff tokens a second factor unless amr is passed.
    for amr in (None, [], ["pwd"], "otp"):
        token = make_token(issuer=STAFF_ISS, roles=["operator"], amr=amr, **scope)
        r = await client.get("/api/v1/me", headers=bearer(token))
        assert (r.status_code, r.json()["detail"]) == (401, "mfa_required"), amr
        assert r.headers["www-authenticate"] == 'Bearer error="insufficient_user_authentication"'
    for amr in (["pwd", "otp"], ["hwk"], ["mfa"]):
        token = make_token(issuer=STAFF_ISS, roles=["operator"], amr=amr, **scope)
        assert (await client.get("/api/v1/me", headers=bearer(token))).status_code == 200, amr


async def test_public_tokens_need_no_second_factor(client: httpx.AsyncClient, make_token: TokenFactory) -> None:
    r = await client.get("/api/v1/me", headers=bearer(make_token(issuer=PUBLIC_ISS, roles=["citizen"])))
    assert r.status_code == 200, r.text


async def test_mfa_check_can_be_turned_off(client: httpx.AsyncClient, make_token: TokenFactory) -> None:
    previous = security.get_token_verifier()
    security.set_token_verifier(
        security.TokenVerifier(
            [PUBLIC_ISS, STAFF_ISS],
            "ehimaya-api",
            lambda token, issuer: _PRIVATE_KEY.public_key(),
            staff_mfa_required=False,
        )
    )
    try:
        token = make_token(issuer=STAFF_ISS, roles=["operator"], amr=["pwd"], gouvernorat_code="61")
        assert (await client.get("/api/v1/me", headers=bearer(token))).status_code == 200
    finally:
        security.set_token_verifier(previous)


async def test_sign_out_everywhere(client: httpx.AsyncClient, make_token: TokenFactory) -> None:
    subject = str(uuid.uuid4())
    old = bearer(make_token(roles=["citizen"], sub=subject, iat=int(time.time()) - 60))
    assert (await client.get("/api/v1/me", headers=old)).status_code == 200
    r = await client.post("/api/v1/me/sign-out-everywhere", headers=old)
    assert r.status_code == 204, r.text
    r = await client.get("/api/v1/me", headers=old)
    assert (r.status_code, r.json()["detail"]) == (401, "session_revoked")
    # A token issued after the revocation (a new sign-in) is accepted.
    new = bearer(make_token(roles=["citizen"], sub=subject, iat=int(time.time()) + 1))
    assert (await client.get("/api/v1/me", headers=new)).status_code == 200
    # Other subjects are untouched.
    assert (await client.get("/api/v1/me", headers=bearer(make_token(roles=["citizen"])))).status_code == 200


@pytest.fixture
def directory() -> Iterator[FakeDirectory]:
    fake = FakeDirectory()
    keycloak.set_directory(fake)
    yield fake
    keycloak.set_directory(None)


def _token_of(make_token: TokenFactory, subject: str) -> dict[str, str]:
    return bearer(
        make_token(issuer=STAFF_ISS, roles=["operator"], sub=subject, gouvernorat_code="61", iat=int(time.time()) - 60)
    )


async def test_admin_actions_revoke_sessions(
    client: httpx.AsyncClient, make_token: TokenFactory, staff: Staff, directory: FakeDirectory, session: AsyncSession
) -> None:
    admin = staff(["regional_account_admin"], gouvernorat=SFAX)
    signed_out = directory.add("sfax.so", SFAX, {"operator"})
    disabled = directory.add("sfax.off", SFAX, {"operator"})
    regranted = directory.add("sfax.role", SFAX, {"operator"})
    reset = directory.add("sfax.reset", SFAX, {"operator"})
    untouched = directory.add("sfax.keep", SFAX, {"operator"})
    holders = {a: _token_of(make_token, a) for a in (signed_out, disabled, regranted, reset, untouched)}

    r = await client.post(f"{URL}/{signed_out}/sign-out", headers=admin)
    assert r.status_code == 204, r.text
    assert directory.sign_outs == [signed_out]
    assert (await client.patch(f"{URL}/{disabled}", json={"enabled": False}, headers=admin)).status_code == 200
    r = await client.patch(f"{URL}/{regranted}", json={"roles": ["operator", "ops_manager"]}, headers=admin)
    assert r.status_code == 200
    assert (await client.post(f"{URL}/{reset}/reset-credentials", headers=admin)).status_code == 204

    for account in (signed_out, disabled, regranted, reset):
        r = await client.get("/api/v1/me", headers=holders[account])
        assert (r.status_code, r.json()["detail"]) == (401, "session_revoked"), account
    assert (await client.get("/api/v1/me", headers=holders[untouched])).status_code == 200
    assert await session.scalar(
        text("SELECT count(*) FROM audit.log WHERE action = 'account.sign_out' AND target = :t"),
        {"t": f"account:{signed_out}"},
    )


async def test_sign_out_scope(client: httpx.AsyncClient, staff: Staff, directory: FakeDirectory) -> None:
    gabes_op = directory.add("gabes.so", 72, {"operator"})
    admin = staff(["regional_account_admin"], gouvernorat=SFAX)
    assert (await client.post(f"{URL}/{gabes_op}/sign-out", headers=admin)).status_code == 404
    assert (await client.post(f"{URL}/{gabes_op}/sign-out", headers=staff(["operator"]))).status_code == 403
    assert directory.sign_outs == []
    directory.down = True
    sfax_op = directory.add("sfax.so2", SFAX, {"operator"})
    assert (await client.post(f"{URL}/{sfax_op}/sign-out", headers=admin)).status_code == 502


class _BrokenStore:
    async def set(self, subject: str, not_before: int) -> None:
        raise ConnectionError("valkey down")

    async def get(self, subject: str) -> int | None:
        raise ConnectionError("valkey down")


async def test_valkey_outage_skips_the_check(client: httpx.AsyncClient, staff: Staff) -> None:
    sessions.set_store(_BrokenStore())
    before = metrics.SESSION_CHECK_DEGRADED._value.get()
    assert (await client.get("/api/v1/me", headers=staff())).status_code == 200
    assert metrics.SESSION_CHECK_DEGRADED._value.get() == before + 1
