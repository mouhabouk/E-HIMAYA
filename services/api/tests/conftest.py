"""Test fixtures. Tests run against a real PostgreSQL (PostGIS + pgvector) migrated to head.

TEST_DATABASE_URL=postgresql+asyncpg://ehimaya:...@localhost:5432/ehimaya pytest
"""

import os
import time
import uuid
from collections.abc import AsyncIterator, Callable, Iterator
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
os.environ.setdefault("FIELD_ENCRYPTION_KEY", "dGVzdC1rZXktdGVzdC1rZXktdGVzdC1rZXktMzJieXQ=")
os.environ["TUSD_HOOK_SECRET"] = "test-hook-secret-test-hook-secret"
os.environ["BACKGROUND_WORKERS"] = "false"
os.environ.pop("API_CORS_ORIGINS", None)
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


# ---------------------------------------------------------------- reporting helpers

SFAX = {"lat": 34.7406, "lon": 10.7603, "accuracy_m": 8.0}
TUNIS = {"lat": 36.8065, "lon": 10.1815, "accuracy_m": 15.0}


def device_headers() -> dict[str, str]:
    import base64

    return {"X-Device-Key": base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")}


def report_body(location: dict[str, float] | None = None, **overrides: Any) -> dict[str, Any]:
    from datetime import UTC, datetime

    body: dict[str, Any] = {
        "client_uuid": str(uuid.uuid4()),
        "category": "fire",
        "text": "دخان كثيف قرب المخزن",
        "lang": "ar",
        "location": location or SFAX,
        "created_at": datetime.now(UTC).isoformat(),
    }
    body.update(overrides)
    return body


async def accept_charter(client: httpx.AsyncClient, headers: dict[str, str]) -> None:
    r = await client.post(
        "/api/v1/consents", json={"charter_version": "2026-10", "locale": "ar", "platform": "android"}, headers=headers
    )
    assert r.status_code == 201, r.text


@pytest.fixture
def citizen(make_token: TokenFactory) -> dict[str, str]:
    """Headers of a fresh registered citizen."""
    return bearer(make_token(roles=["citizen"], email="citizen@example.tn", email_verified=True))


@pytest.fixture
def staff(make_token: TokenFactory) -> Callable[..., dict[str, str]]:
    def _staff(roles: list[str] | None = None, gouvernorat: int | None = 61) -> dict[str, str]:
        scope: dict[str, Any] = {"gouvernorat_code": str(gouvernorat)} if gouvernorat else {"scope_level": "national"}
        return bearer(make_token(issuer=STAFF_ISS, roles=roles or ["operator"], **scope))

    return _staff


class FakeStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.deleted: list[str] = []

    async def sha256(self, key: str) -> tuple[str, int]:
        import hashlib

        data = self.objects[key]
        return hashlib.sha256(data).hexdigest(), len(data)

    async def delete(self, *keys: str) -> None:
        self.deleted.extend(keys)
        for key in keys:
            self.objects.pop(key, None)

    def presign_get(self, key: str, *, expires_s: int = 600, content_type: str | None = None) -> str:
        return f"http://s3.test/{key}?sig=1"


@pytest.fixture(autouse=True)
def _isolated_infra() -> Iterator[FakeStore]:
    from app.core import ratelimit, storage

    store = FakeStore()
    storage.set_store(store)
    ratelimit.set_limiter(ratelimit.MemoryLimiter())
    yield store
    storage.set_store(None)
    ratelimit.set_limiter(None)


@pytest.fixture
def fake_store(_isolated_infra: FakeStore) -> FakeStore:
    return _isolated_infra
