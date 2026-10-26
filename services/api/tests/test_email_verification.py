"""A work e-mail confirmed by code (phase P5b, F-APP-12 and FR-A-002, docs/phase-p5/design-simple.md §2.4): an
account signed in with a phone number confirms an address with a 6-digit code and may then register an institution."""

import re
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import TokenFactory, bearer
from tests.test_orgs import card

URL = "/api/v1/me/email"


def _phone_user(make_token: TokenFactory) -> dict[str, str]:
    """Signed in with a phone number and an SMS code (phase A): no e-mail in the token."""
    return bearer(make_token(roles=["citizen"], phone_number="+21698123456", phone_number_verified=True))


async def _code_sent(session: AsyncSession, address: str) -> str:
    row = (
        await session.execute(
            text("SELECT payload FROM notify.outbox WHERE channel = 'email' AND address = :a ORDER BY id DESC"),
            {"a": address},
        )
    ).first()
    assert row is not None
    payload: dict[str, Any] = row.payload
    found = re.search(r"\b(\d{6})\b", payload["text"])
    assert found is not None
    return found.group(1)


async def test_phone_account_has_no_proven_email(client: httpx.AsyncClient, make_token: TokenFactory) -> None:
    r = await client.get(URL, headers=_phone_user(make_token))
    assert r.status_code == 200
    assert r.json() == {"email": None, "verified": False, "source": None}


async def test_identity_provider_email_counts(client: httpx.AsyncClient, citizen: dict[str, str]) -> None:
    r = await client.get(URL, headers=citizen)
    assert r.json() == {"email": "citizen@example.tn", "verified": True, "source": "account"}


async def test_code_confirms_the_address_and_opens_registration(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession
) -> None:
    headers = _phone_user(make_token)
    r = await client.post("/api/v1/orgs", json=card(), headers=headers)
    assert r.status_code == 403 and r.json()["detail"] == "email_not_verified"

    r = await client.post(f"{URL}/code", json={"email": "Direction@Hotel-Sud.tn", "locale": "fr"}, headers=headers)
    assert r.status_code == 200, r.text
    code = await _code_sent(session, "direction@hotel-sud.tn")
    stored = (await session.execute(text("SELECT email_enc, code_hmac FROM identity.email_code"))).all()
    assert all(b"hotel-sud" not in bytes(row.email_enc) for row in stored)

    r = await client.post(f"{URL}/verify", json={"code": code}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"email": "direction@hotel-sud.tn", "verified": True, "source": "code"}
    assert (await client.get(URL, headers=headers)).json()["source"] == "code"

    r = await client.post("/api/v1/orgs", json=card(), headers=headers)
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "pending_review"


async def test_wrong_code_spends_an_attempt(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession
) -> None:
    headers = _phone_user(make_token)
    await client.post(f"{URL}/code", json={"email": "a@example.tn"}, headers=headers)
    code = await _code_sent(session, "a@example.tn")
    wrong = f"{(int(code) + 1) % 1_000_000:06d}"
    for _ in range(5):
        r = await client.post(f"{URL}/verify", json={"code": wrong}, headers=headers)
        assert r.status_code == 422 and r.json()["detail"] == "invalid_code"
    # Attempts spent: even the right code is refused until a new one is sent.
    r = await client.post(f"{URL}/verify", json={"code": code}, headers=headers)
    assert r.status_code == 409 and r.json()["detail"] == "code_expired"


async def test_expired_code_is_refused(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession
) -> None:
    headers = _phone_user(make_token)
    await client.post(f"{URL}/code", json={"email": "b@example.tn"}, headers=headers)
    code = await _code_sent(session, "b@example.tn")
    await session.execute(text("UPDATE identity.email_code SET expires_at = now() - interval '1 minute'"))
    await session.commit()
    r = await client.post(f"{URL}/verify", json={"code": code}, headers=headers)
    assert r.status_code == 409 and r.json()["detail"] == "code_expired"


async def test_codes_are_limited_per_hour(client: httpx.AsyncClient, make_token: TokenFactory) -> None:
    headers = _phone_user(make_token)
    for _ in range(5):
        assert (await client.post(f"{URL}/code", json={"email": "c@example.tn"}, headers=headers)).status_code == 200
    r = await client.post(f"{URL}/code", json={"email": "c@example.tn"}, headers=headers)
    assert r.status_code == 429


async def test_anonymous_device_cannot_confirm(client: httpx.AsyncClient) -> None:
    from tests.conftest import device_headers

    r = await client.post(f"{URL}/code", json={"email": "d@example.tn"}, headers=device_headers())
    assert r.status_code == 403 and r.json()["detail"] == "registration_required"


async def test_bad_input(client: httpx.AsyncClient, make_token: TokenFactory) -> None:
    headers = _phone_user(make_token)
    assert (await client.post(f"{URL}/code", json={"email": "not-an-email"}, headers=headers)).status_code == 422
    assert (await client.post(f"{URL}/verify", json={"code": "12ab56"}, headers=headers)).status_code == 422
