# covers: FR-A-005, FR-A-006, FR-A-001
import secrets

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.models import phone_index
from tests.conftest import TokenFactory, bearer, device_headers


def random_cin() -> str:
    return f"{secrets.randbelow(100_000_000):08d}"


def _profile(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "first_name": "Sami",
        "last_name": "Trabelsi",
        "cin": random_cin(),
        "phone": "+21622333444",
        "gouvernorat_code": 11,
        "delegation_id": 1101,
        "address": "Rue de Marseille",
        "locale": "ar",
    }
    body.update(overrides)
    return body


async def test_profile_roundtrip_encrypts_cin(
    client: httpx.AsyncClient, citizen: dict[str, str], session: AsyncSession
) -> None:
    empty = (await client.get("/api/v1/me/profile", headers=citizen)).json()
    assert empty["first_name"] is None and empty["email"] == "citizen@example.tn"

    body = _profile()
    r = await client.put("/api/v1/me/profile", json=body, headers=citizen)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["cin_last4"] == str(body["cin"])[-4:]
    assert "cin" not in out
    assert out["email"] == "citizen@example.tn"
    assert (await client.get("/api/v1/me/profile", headers=citizen)).json() == out

    row = (
        await session.execute(
            text(
                "SELECT cin_enc, cin_hash, email_verified_at FROM identity.profile "
                "WHERE phone_hash = :p ORDER BY updated_at DESC"
            ),
            {"p": phone_index("+21622333444")},
        )
    ).first()
    assert row is not None
    assert str(body["cin"]).encode() not in row.cin_enc
    assert len(row.cin_hash) == 32
    assert row.email_verified_at is not None


async def test_cin_is_unique(client: httpx.AsyncClient, make_token: TokenFactory) -> None:
    body = _profile()
    first, second = bearer(make_token(roles=["citizen"])), bearer(make_token(roles=["citizen"]))
    assert (await client.put("/api/v1/me/profile", json=body, headers=first)).status_code == 200
    r = await client.put("/api/v1/me/profile", json=body, headers=second)
    assert r.status_code == 409 and r.json()["detail"] == "cin_already_registered"


async def test_profile_validation(client: httpx.AsyncClient, citizen: dict[str, str]) -> None:
    r = await client.put("/api/v1/me/profile", json=_profile(delegation_id=6101), headers=citizen)
    assert r.status_code == 422 and r.json()["detail"] == "delegation_mismatch"
    r = await client.put("/api/v1/me/profile", json=_profile(gouvernorat_code=99), headers=citizen)
    assert r.status_code == 422 and r.json()["detail"] == "unknown_gouvernorat"
    for bad in ({"cin": "1234"}, {"phone": "98123456"}, {"locale": "de"}):
        assert (await client.put("/api/v1/me/profile", json=_profile(**bad), headers=citizen)).status_code == 422


async def test_anonymous_has_no_profile(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/me/profile", headers=device_headers())
    assert r.status_code == 403 and r.json()["detail"] == "registration_required"


async def test_charter_and_consent(client: httpx.AsyncClient, citizen: dict[str, str]) -> None:
    assert (await client.get("/api/v1/charter")).json() == {"version": "2026-10"}
    body = {"charter_version": "2026-10", "locale": "fr", "platform": "ios"}
    first = await client.post("/api/v1/consents", json=body, headers=citizen)
    again = await client.post("/api/v1/consents", json=body, headers=citizen)
    assert first.status_code == again.status_code == 201
    assert first.json() == again.json()
    r = await client.post("/api/v1/consents", json={**body, "charter_version": "2019-01"}, headers=citizen)
    assert r.status_code == 422 and r.json()["detail"] == "unknown_charter_version"
