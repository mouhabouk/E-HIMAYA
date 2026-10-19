"""Test fixtures. Tests run against a real PostgreSQL (PostGIS + pgvector) migrated to head.

TEST_DATABASE_URL=postgresql+asyncpg://ehimaya:...@localhost:5432/ehimaya pytest
"""

import os
import time
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

PUBLIC_ISS = "http://kc.test/realms/ehimaya-public"
STAFF_ISS = "http://kc.test/realms/ehimaya-staff"

os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get("TEST_DATABASE_URL", "postgresql+asyncpg://ehimaya:ehimaya@localhost:5432/ehimaya"),
)
os.environ["OIDC_ISSUERS"] = f"{PUBLIC_ISS},{STAFF_ISS}"
os.environ["OIDC_AUDIENCE"] = "ehimaya-api"
os.environ.setdefault("ANON_PSEUDONYM_SECRET", "test-secret-test-secret-test-secret-0001")
os.environ.pop("VALKEY_URL", None)
os.environ.pop("NATS_URL", None)

import httpx  # noqa: E402
import jwt  # noqa: E402
import pytest  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core import security  # noqa: E402
from app.core.db import dispose_engine, get_sessionmaker  # noqa: E402
from app.main import app  # noqa: E402

_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="session", autouse=True)
def _static_verifier() -> None:
    security.set_token_verifier(
        security.TokenVerifier([PUBLIC_ISS, STAFF_ISS], "ehimaya-api", lambda token, issuer: _PRIVATE_KEY.public_key())
    )


@pytest.fixture(scope="session", autouse=True)
async def _engine_lifecycle() -> AsyncIterator[None]:
    yield
    await dispose_engine()


TokenFactory = Callable[..., str]


@pytest.fixture
def make_token() -> TokenFactory:
    def _make(
        *,
        issuer: str = PUBLIC_ISS,
        roles: list[str] | None = None,
        audience: str = "ehimaya-api",
        expires_in: int = 300,
        signing_key: Any = None,
        **extra: Any,
    ) -> str:
        now = int(time.time())
        claims = {
            "iss": issuer,
            "sub": str(uuid.uuid4()),
            "aud": audience,
            "iat": now,
            "exp": now + expires_in,
            "realm_access": {"roles": roles or []},
            **extra,
        }
        return jwt.encode(claims, signing_key or _PRIVATE_KEY, algorithm="RS256")

    return _make


@pytest.fixture
def other_key() -> Any:
    return _OTHER_KEY


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://api.test") as c:
        yield c


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as s:
        yield s


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
