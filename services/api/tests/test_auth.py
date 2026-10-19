from typing import Any

import httpx

from tests.conftest import PUBLIC_ISS, STAFF_ISS, TokenFactory, bearer


async def test_me_requires_token(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/me")
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"] == "Bearer"


async def test_citizen_token(client: httpx.AsyncClient, make_token: TokenFactory) -> None:
    r = await client.get("/api/v1/me", headers=bearer(make_token(roles=["citizen", "offline_access"])))
    assert r.status_code == 200
    body = r.json()
    assert body["realm"] == "ehimaya-public"
    assert body["roles"] == ["citizen"]
    assert body["is_staff"] is False


async def test_public_realm_cannot_claim_staff_roles(client: httpx.AsyncClient, make_token: TokenFactory) -> None:
    token = make_token(roles=["citizen", "sysadmin", "operator"])
    r = await client.get("/api/v1/me", headers=bearer(token))
    assert r.json()["roles"] == ["citizen"]
    r = await client.get("/api/v1/admin/audit/verify", headers=bearer(token))
    assert r.status_code == 403


async def test_staff_with_gouvernorat_scope(client: httpx.AsyncClient, make_token: TokenFactory) -> None:
    token = make_token(issuer=STAFF_ISS, roles=["operator"], gouvernorat_code="61")
    body = (await client.get("/api/v1/me", headers=bearer(token))).json()
    assert body["is_staff"] is True
    assert body["gouvernorat_code"] == 61


async def test_staff_national_scope(client: httpx.AsyncClient, make_token: TokenFactory) -> None:
    token = make_token(issuer=STAFF_ISS, roles=["central_committee"], scope_level="national")
    body = (await client.get("/api/v1/me", headers=bearer(token))).json()
    assert body["gouvernorat_code"] is None


async def test_staff_without_scope_is_refused(client: httpx.AsyncClient, make_token: TokenFactory) -> None:
    token = make_token(issuer=STAFF_ISS, roles=["operator"])
    r = await client.get("/api/v1/me", headers=bearer(token))
    assert r.status_code == 403


async def test_rejected_tokens(client: httpx.AsyncClient, make_token: TokenFactory, other_key: Any) -> None:
    cases = {
        "wrong audience": make_token(audience="another-client"),
        "expired": make_token(expires_in=-120),
        "unknown issuer": make_token(issuer="http://evil.test/realms/ehimaya-public"),
        "bad signature": make_token(signing_key=other_key),
        "garbage": "not-a-jwt",
    }
    for label, token in cases.items():
        r = await client.get("/api/v1/me", headers=bearer(token))
        assert r.status_code == 401, label


async def test_issuer_must_match_exactly(client: httpx.AsyncClient, make_token: TokenFactory) -> None:
    r = await client.get("/api/v1/me", headers=bearer(make_token(issuer=PUBLIC_ISS + "/")))
    # PyJWT compares the issuer exactly; a trailing slash variant must not be accepted silently.
    assert r.status_code == 401
