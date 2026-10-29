"""Test fixtures. Tests run against a real PostgreSQL (PostGIS + pgvector) migrated to head.

TEST_DATABASE_URL=postgresql+asyncpg://ehimaya:...@localhost:5432/ehimaya pytest
"""

import json
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
# Live streaming (phase 6): MediaMTX hooks and API user, vision callback and read credentials, stream simulator.
os.environ["MEDIAMTX_HOOK_TOKEN"] = "test-mediamtx-hook-token-0001"
os.environ["MEDIAMTX_API_PASSWORD"] = "test-mediamtx-api-password-0001"
os.environ["VISION_CALLBACK_TOKEN"] = "test-vision-callback-token-0001"
os.environ["VISION_READ_PASSWORD"] = "test-vision-read-password-0001"
# Sensors of the local network (L5b): the gateway beside MediaMTX.
os.environ["SENSOR_GATEWAY_TOKEN"] = "test-sensor-gateway-token-0001"
os.environ["STREAM_SIM_TOKEN"] = "test-stream-sim-token-0000001"
# Telephony (phase 7): ARI is replaced by a fake (tests/test_telephony.py), SMS gateway secret, call simulator.
os.environ["TELEPHONY_ARI_PASSWORD"] = "test-ari-password-0001"
os.environ["SMS_INBOUND_SECRET"] = "test-sms-inbound-secret-000001"
os.environ["TELEPHONY_SIM_TOKEN"] = "test-telephony-sim-token-0001"
os.environ.pop("TELEPHONY_ARI_URL", None)
os.environ.pop("MEDIAMTX_API_URL", None)
os.environ.pop("VISION_SERVICE_URL", None)
os.environ["BACKGROUND_WORKERS"] = "false"
os.environ.pop("API_CORS_ORIGINS", None)
os.environ.pop("VALKEY_URL", None)
os.environ.pop("NATS_URL", None)

import httpx  # noqa: E402
import jwt  # noqa: E402
import pytest  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core import security  # noqa: E402
from app.core.db import dispose_engine, get_system_sessionmaker  # noqa: E402
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
        if issuer == STAFF_ISS:
            # Staff sign in with a second factor (phase 10 §1.1); tests of the MFA check pass amr themselves.
            extra.setdefault("amr", ["pwd", "otp"])
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
async def isolated_window() -> None:
    """Move earlier tests' reports out of every grouping window, so suggestions only see this test's reports."""
    async with get_system_sessionmaker()() as s, s.begin():
        await s.execute(text("UPDATE reports.report SET received_at = received_at - interval '30 days'"))


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_system_sessionmaker()() as s:
        yield s


# tusd authenticates its hook calls with HTTP Basic (user "tusd", password TUSD_HOOK_SECRET).
HOOK_AUTH = {"Authorization": "Basic dHVzZDp0ZXN0LWhvb2stc2VjcmV0LXRlc3QtaG9vay1zZWNyZXQ="}


async def outbox_events(session: AsyncSession, subject: str) -> list[dict[str, Any]]:
    """Clear payloads of the queued domain events of a subject (they are sealed at rest)."""
    from app.core.events import open_payload

    rows = await session.scalars(text("SELECT payload FROM events.outbox WHERE subject = :s"), {"s": subject})
    return [open_payload(json.loads(p) if isinstance(p, str) else p) for p in rows]


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
        "/api/v1/consents", json={"charter_version": "2026-11", "locale": "ar", "platform": "android"}, headers=headers
    )
    assert r.status_code == 201, r.text


@pytest.fixture
def citizen(make_token: TokenFactory) -> dict[str, str]:
    """Headers of a fresh registered citizen."""
    return bearer(make_token(roles=["citizen"], email="citizen@example.tn", email_verified=True))


@pytest.fixture
def staff(make_token: TokenFactory) -> Callable[..., dict[str, str]]:
    def _staff(roles: list[str] | None = None, gouvernorat: int | None = 61, **claims: Any) -> dict[str, str]:
        scope: dict[str, Any] = {"gouvernorat_code": str(gouvernorat)} if gouvernorat else {"scope_level": "national"}
        return bearer(make_token(issuer=STAFF_ISS, roles=roles or ["operator"], **scope, **claims))

    return _staff


class FakeStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.deleted: list[str] = []
        self.presigned: list[tuple[str, str | None, str | None]] = []

    async def sha256(self, key: str) -> tuple[str, int]:
        import hashlib

        data = self.objects[key]
        return hashlib.sha256(data).hexdigest(), len(data)

    async def head(self, key: str, size: int) -> bytes:
        return self.objects[key][:size]

    async def delete(self, *keys: str) -> None:
        self.deleted.extend(keys)
        for key in keys:
            self.objects.pop(key, None)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data

    def presign_get(
        self,
        key: str,
        *,
        expires_s: int = 600,
        content_type: str | None = None,
        internal: bool = False,
        disposition: str | None = None,
    ) -> str:
        self.presigned.append((key, content_type, disposition))
        return f"http://{'s3-internal' if internal else 's3'}.test/{key}?sig=1"


class FakeChannel:
    """Records what a delivery channel was asked to send."""

    def __init__(self, configured: bool = True) -> None:
        self.configured = configured
        self.sent: list[tuple[Any, ...]] = []
        self.unregistered: set[str] = set()

    async def send(self, *args: Any) -> Any:
        from app.modules.notify.providers import Result

        self.sent.append(args)
        token = getattr(args[0], "token", None)
        if token in self.unregistered:
            return Result(ok=False, unregistered=True, error="http_404")
        return Result(ok=True)


class FakeMediamtx:
    """Records the paths whose publisher the API asked MediaMTX to kick."""

    def __init__(self) -> None:
        self.kicked: list[str] = []

    async def kick(self, path: str) -> bool:
        self.kicked.append(path)
        return True


@pytest.fixture(autouse=True)
def _isolated_infra() -> Iterator[FakeStore]:
    from app.core import ratelimit, sessions, storage
    from app.modules.notify import providers
    from app.modules.streams import mediamtx, vision
    from app.modules.volunteers import presence

    store = FakeStore()
    storage.set_store(store)
    ratelimit.set_limiter(ratelimit.MemoryLimiter())
    sessions.set_store(sessions.MemoryRevocations())
    presence.set_presence(presence.MemoryPresence())
    providers.set_providers(providers.Providers(push=FakeChannel(), sms=FakeChannel(), email=FakeChannel()))
    mediamtx.set_mediamtx(FakeMediamtx())
    vision.set_vision_client(None)
    yield store
    storage.set_store(None)
    ratelimit.set_limiter(None)
    sessions.set_store(None)
    presence.set_presence(None)
    providers.set_providers(None)
    mediamtx.set_mediamtx(None)
    vision.set_vision_client(None)


@pytest.fixture
def fake_mediamtx() -> FakeMediamtx:
    from app.modules.streams.mediamtx import get_mediamtx

    client = get_mediamtx()
    assert isinstance(client, FakeMediamtx)
    return client


@pytest.fixture
def channels() -> Any:
    from app.modules.notify.providers import get_providers

    return get_providers()


@pytest.fixture
def fake_store(_isolated_infra: FakeStore) -> FakeStore:
    return _isolated_infra


@pytest.fixture
def fake_ai() -> Iterator[Any]:
    """An in-process stand-in for the AI inference service (tests/aihelpers.py)."""
    from app.modules.ai.client import set_ai_client
    from tests.aihelpers import FakeAi

    ai = FakeAi()
    set_ai_client(ai)
    yield ai
    set_ai_client(None)
