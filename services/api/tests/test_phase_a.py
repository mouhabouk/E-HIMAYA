"""Phase A (docs/phase-a/design.md): app version, SMS sign-in code, phone claims, respectful-language filter."""

import json
import time
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_system_sessionmaker
from app.modules.identity import internal
from app.modules.identity.models import phone_index
from app.modules.moderation.normalize import tokens
from app.modules.moderation.service import is_offensive
from app.modules.notify.providers import Providers, Result, set_providers
from app.modules.settings import domain
from app.modules.settings import service as settings_service
from tests.conftest import FakeChannel, TokenFactory, bearer
from tests.test_profile import _profile

Staff = Callable[..., dict[str, str]]
OTP_SECRET = "test-otp-sms-secret-0000000001"


@pytest.fixture
async def restore_settings() -> AsyncIterator[None]:
    async with get_system_sessionmaker()() as s:
        saved = (await s.execute(text("SELECT key, value::text, version FROM platform.setting"))).all()
    yield
    async with get_system_sessionmaker()() as s, s.begin():
        for key, value, version in saved:
            await s.execute(
                text("UPDATE platform.setting SET value = CAST(:v AS jsonb), version = :n WHERE key = :k"),
                {"k": key, "v": value, "n": version},
            )
    settings_service.invalidate()


@pytest.fixture
def otp_secret(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("OTP_SMS_SECRET", OTP_SECRET)
    yield OTP_SECRET
    get_settings.cache_clear()


def _signed(body: dict[str, object], secret: str = OTP_SECRET, at: int | None = None) -> tuple[bytes, dict[str, str]]:
    raw = json.dumps(body).encode()
    timestamp = str(at or int(time.time()))
    return raw, {
        "X-Timestamp": timestamp,
        "X-Signature": internal.signature(secret, timestamp, raw),
        "Content-Type": "application/json",
    }


async def _setting_version(client: httpx.AsyncClient, staff: Staff, key: str) -> int:
    items = (await client.get("/api/v1/staff/settings", headers=staff(["sysadmin"], gouvernorat=None))).json()
    return next(item["version"] for item in items["items"] if item["key"] == key)


# ---------------------------------------------------------------- app version (addition 3)


async def test_app_version_defaults(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/app/version")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["latest_build"] >= 1 and body["min_build"] >= 1
    assert body["channel"] in ("server", "play")
    assert body["update_available"] is None and body["mandatory"] is None
    assert "max-age=600" in r.headers["cache-control"]
    # Tests have no SMS gateway URL: not the simulator.
    assert body["sms_simulated"] is False


async def test_app_version_update_and_mandatory(
    client: httpx.AsyncClient, staff: Staff, restore_settings: None
) -> None:
    admin = staff(["sysadmin"], gouvernorat=None)
    release = {
        "latest_version": "0.3.0",
        "latest_build": 5,
        "min_build": 3,
        "notes": {"ar": "جديد", "fr": "Nouveau", "en": "New"},
        "channel": "server",
        "download_url": "https://downloads.ehimaya.tn/ehimaya-0.3.0.apk",
    }
    version = await _setting_version(client, staff, domain.APP_RELEASE)
    r = await client.put(
        f"/api/v1/staff/settings/{domain.APP_RELEASE}",
        json={"value": release, "version": version, "reason": "release 0.3.0"},
        headers=admin,
    )
    assert r.status_code == 200, r.text
    settings_service.invalidate()

    current = (await client.get("/api/v1/app/version", params={"build": 5})).json()
    assert current["update_available"] is False and current["mandatory"] is False
    optional = (await client.get("/api/v1/app/version", params={"build": 4})).json()
    assert optional["update_available"] is True and optional["mandatory"] is False
    assert optional["notes"]["ar"] == "جديد" and optional["download_url"].endswith(".apk")
    mandatory = (await client.get("/api/v1/app/version", params={"build": 2, "platform": "android"})).json()
    assert mandatory["update_available"] is True and mandatory["mandatory"] is True


async def test_app_release_validation_and_editors(
    client: httpx.AsyncClient, staff: Staff, restore_settings: None
) -> None:
    version = await _setting_version(client, staff, domain.APP_RELEASE)
    bad = [
        {"latest_version": "0.3", "latest_build": 2, "min_build": 1},
        {"latest_version": "0.3.0", "latest_build": 2, "min_build": 3},
        {"latest_version": "0.3.0", "latest_build": 2, "min_build": 1, "channel": "server"},
        {"latest_version": "0.3.0", "latest_build": 2, "min_build": 1, "download_url": "http://insecure.tn/a.apk"},
    ]
    for value in bad:
        r = await client.put(
            f"/api/v1/staff/settings/{domain.APP_RELEASE}",
            json={"value": value, "version": version, "reason": "bad release"},
            headers=staff(["sysadmin"], gouvernorat=None),
        )
        assert r.status_code == 422, (value, r.text)
    # Only the national system administrator publishes a release.
    for headers in (staff(["central_committee"], gouvernorat=None), staff(["sysadmin"], gouvernorat=11)):
        r = await client.put(
            f"/api/v1/staff/settings/{domain.APP_RELEASE}",
            json={"value": domain.DEFAULTS[domain.APP_RELEASE], "version": version, "reason": "not mine"},
            headers=headers,
        )
        assert r.status_code == 403


async def test_app_version_bad_query(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/v1/app/version", params={"platform": "windows"})).status_code == 422
    assert (await client.get("/api/v1/app/version", params={"build": 0})).status_code == 422


# ---------------------------------------------------------------- SMS sign-in code (addition 6)


async def test_otp_sms_404_without_secret(client: httpx.AsyncClient) -> None:
    raw, headers = _signed({"phone": "+21622333444", "code": "123456", "locale": "ar"})
    assert (await client.post("/internal/auth/otp-sms", content=raw, headers=headers)).status_code == 404


async def test_otp_sms_sends_in_user_language(client: httpx.AsyncClient, otp_secret: str) -> None:
    sms = FakeChannel()
    set_providers(Providers(push=FakeChannel(), sms=sms, email=FakeChannel()))
    for locale, word in (("ar", "رمز"), ("fr", "Code"), ("en", "code")):
        raw, headers = _signed({"phone": "+21650111222", "code": "482913", "locale": locale})
        r = await client.post("/internal/auth/otp-sms", content=raw, headers=headers)
        assert r.status_code == 200, r.text
        assert r.json() == {"sent": True, "simulated": False}
        to, message = sms.sent[-1]
        assert to == "+21650111222" and "482913" in message and word in message


async def test_otp_sms_signature(client: httpx.AsyncClient, otp_secret: str) -> None:
    body = {"phone": "+21622333444", "code": "123456", "locale": "fr"}
    raw, headers = _signed(body, secret="another-secret-another-secret-01")
    assert (await client.post("/internal/auth/otp-sms", content=raw, headers=headers)).status_code == 401
    raw, headers = _signed(body, at=int(time.time()) - 600)
    assert (await client.post("/internal/auth/otp-sms", content=raw, headers=headers)).status_code == 401
    raw, headers = _signed(body)
    headers.pop("X-Signature")
    assert (await client.post("/internal/auth/otp-sms", content=raw, headers=headers)).status_code == 401
    # Signed, but the body is changed after signing.
    raw, headers = _signed(body)
    tampered = raw.replace(b"123456", b"654321")
    assert (await client.post("/internal/auth/otp-sms", content=tampered, headers=headers)).status_code == 401


async def test_otp_sms_validation(client: httpx.AsyncClient, otp_secret: str) -> None:
    for body in (
        {"phone": "+21612345678", "code": "123456"},  # 1 is not a mobile prefix
        {"phone": "+33612345678", "code": "123456"},
        {"phone": "+21622333444", "code": "12345"},
        {"phone": "+21622333444", "code": "123456", "locale": "de"},
    ):
        raw, headers = _signed(body)
        r = await client.post("/internal/auth/otp-sms", content=raw, headers=headers)
        assert r.status_code == 422 and r.json()["detail"] == "invalid_body", body


async def test_otp_sms_rate_limit_per_number(client: httpx.AsyncClient, otp_secret: str) -> None:
    for i in range(internal.CODES_PER_NUMBER_PER_HOUR):
        raw, headers = _signed({"phone": "+21698765432", "code": f"{i:06d}"})
        assert (await client.post("/internal/auth/otp-sms", content=raw, headers=headers)).status_code == 200
    raw, headers = _signed({"phone": "+21698765432", "code": "999999"})
    r = await client.post("/internal/auth/otp-sms", content=raw, headers=headers)
    assert r.status_code == 429
    # Another number is not affected.
    raw, headers = _signed({"phone": "+21698765433", "code": "999999"})
    assert (await client.post("/internal/auth/otp-sms", content=raw, headers=headers)).status_code == 200


async def test_otp_sms_provider_down(client: httpx.AsyncClient, otp_secret: str) -> None:
    class Refusing(FakeChannel):
        async def send(self, *args: object) -> Result:
            return Result(ok=False, error="http_500")

    set_providers(Providers(push=FakeChannel(), sms=Refusing(), email=FakeChannel()))
    raw, headers = _signed({"phone": "+21622000111", "code": "123456"})
    assert (await client.post("/internal/auth/otp-sms", content=raw, headers=headers)).status_code == 502
    set_providers(Providers(push=FakeChannel(), sms=FakeChannel(configured=False), email=FakeChannel()))
    raw, headers = _signed({"phone": "+21622000112", "code": "123456"})
    assert (await client.post("/internal/auth/otp-sms", content=raw, headers=headers)).status_code == 503


async def test_otp_sms_simulated_flag(
    client: httpx.AsyncClient, otp_secret: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import get_settings

    # SIMULATION: SMS go to notify-sim in development; the flag lets the app show its [SIM] strip.
    monkeypatch.setenv("SMS_HTTP_URL", "http://notify-sim:8090/sms/send")
    get_settings.cache_clear()
    raw, headers = _signed({"phone": "+21622000113", "code": "123456"})
    r = await client.post("/internal/auth/otp-sms", content=raw, headers=headers)
    assert r.json()["simulated"] is True
    assert (await client.get("/api/v1/app/version")).json()["sms_simulated"] is True


# ---------------------------------------------------------------- phone claims → profile


async def test_verified_phone_claim_fills_and_verifies_profile(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession
) -> None:
    phone = "+21655123987"
    headers = bearer(make_token(roles=["citizen"], phone_number=phone, phone_number_verified=True))
    assert (await client.get("/api/v1/me/profile", headers=headers)).json()["phone"] == phone

    r = await client.put("/api/v1/me/profile", json=_profile(phone=phone), headers=headers)
    assert r.status_code == 200, r.text
    verified = await session.scalar(
        text("SELECT phone_verified_at FROM identity.profile WHERE phone_hash = :p"), {"p": phone_index(phone)}
    )
    assert verified is not None


async def test_unverified_or_other_phone_stays_unverified(
    client: httpx.AsyncClient, make_token: TokenFactory, session: AsyncSession
) -> None:
    unverified = bearer(make_token(roles=["citizen"], phone_number="+21655123988", phone_number_verified=False))
    assert (await client.get("/api/v1/me/profile", headers=unverified)).json()["phone"] is None
    r = await client.put("/api/v1/me/profile", json=_profile(phone="+21655123988"), headers=unverified)
    assert r.status_code == 200

    other = bearer(make_token(roles=["citizen"], phone_number="+21655123989", phone_number_verified=True))
    r = await client.put("/api/v1/me/profile", json=_profile(phone="+21655123990"), headers=other)
    assert r.status_code == 200
    for phone in ("+21655123988", "+21655123990"):
        verified = await session.scalar(
            text("SELECT phone_verified_at FROM identity.profile WHERE phone_hash = :p"), {"p": phone_index(phone)}
        )
        assert verified is None, phone


# ---------------------------------------------------------------- respectful language (rule 4)


def test_normaliser() -> None:
    assert tokens("F.U.C.K") == ["fuck"]
    assert tokens("f u c k you") == ["fuck", "you"]
    assert tokens("NIIIQUE") == ["nique"]
    assert tokens("القَحْبَـــة") == tokens("القحبه")
    assert tokens("أحمد إبراهيم") == tokens("احمد ابراهيم")
    assert tokens("Liberté") == ["liberte"]


@pytest.mark.parametrize(
    "text_",
    ["F.U.C.K you", "يا كلب", "والقحبة", "nik omek", "Nique ta mère", "s@lope", "يلعن دينك", "ya 9a7ba"],
)
def test_offensive(text_: str) -> None:
    assert is_offensive(text_)


@pytest.mark.parametrize(
    "text_",
    [
        "Mohamed Ben Ali",
        "شارع الحبيب بورقيبة",
        "Rue de la Liberté, Sfax",
        "Dickens",
        "Scunthorpe",
        "Shiitake",
        "زامل",
        "Isis Ben Salah",
        "retard du bus",
        "كلبة",
    ],
)
def test_ordinary_text_passes(text_: str) -> None:
    assert not is_offensive(text_)


def test_extra_terms() -> None:
    assert not is_offensive("bonjour monstre")
    assert is_offensive("bonjour monstre", ["monstre"])
    assert is_offensive("vous êtes des Mon-stres", ["monstres"])


async def test_profile_refuses_offensive_names(client: httpx.AsyncClient, citizen: dict[str, str]) -> None:
    for field, value in (("first_name", "Salope"), ("last_name", "ولد القحبة"), ("address", "nahj zebi")):
        r = await client.put("/api/v1/me/profile", json=_profile(**{field: value}), headers=citizen)
        assert r.status_code == 422 and r.json()["detail"] == "offensive_text", field


async def test_extra_terms_setting_applies(
    client: httpx.AsyncClient, citizen: dict[str, str], staff: Staff, restore_settings: None
) -> None:
    version = await _setting_version(client, staff, domain.MODERATION_EXTRA_TERMS)
    r = await client.put(
        f"/api/v1/staff/settings/{domain.MODERATION_EXTRA_TERMS}",
        json={"value": ["Bouzebbal", " bouzebbal "], "version": version, "reason": "new insult reported"},
        headers=staff(["sysadmin"], gouvernorat=None),
    )
    assert r.status_code == 200 and r.json()["value"] == ["Bouzebbal", "bouzebbal"]
    settings_service.invalidate()
    r = await client.put("/api/v1/me/profile", json=_profile(last_name="Bouzebbal"), headers=citizen)
    assert r.status_code == 422 and r.json()["detail"] == "offensive_text"


async def test_reports_are_never_filtered(client: httpx.AsyncClient, citizen: dict[str, str]) -> None:
    """A frightened citizen is never refused help because of the words used (rule 4 exception)."""
    from tests.conftest import accept_charter, report_body

    await accept_charter(client, citizen)
    r = await client.post(
        "/api/v1/reports",
        json=report_body(text="Au secours, ce fils de pute a mis le feu, putain vite !", lang="fr"),
        headers=citizen,
    )
    assert r.status_code in (200, 201, 202), r.text


# Rule 4: no advertising. The build fails if an advertising or tracking package is locked by the API or the web apps.
ADVERTISING_PACKAGES = (
    "google-ads",
    "googleads",
    "admob",
    "facebook-business",
    "facebook-sdk",
    "mixpanel",
    "segment-analytics",
    "analytics-python",
    "amplitude",
    "@google-analytics",
    "react-ga",
    "react-gtm",
    "@segment/",
    "@amplitude/",
    "mixpanel-browser",
    "posthog",
    "hotjar",
    "@fullstory/",
    "appsflyer",
    "adjust-sdk",
)


def test_no_advertising_or_tracking_package() -> None:
    root = Path(__file__).resolve().parents[3]
    locks = [
        root / "services/api/uv.lock",
        root / "apps/dashboard/package-lock.json",
        root / "apps/portal/package-lock.json",
    ]
    for lock in locks:
        assert lock.is_file(), lock
        content = lock.read_text(encoding="utf-8").lower()
        found = [
            p for p in ADVERTISING_PACKAGES if f'"{p}' in content or f'name = "{p}' in content or f"/{p}" in content
        ]
        assert found == [], f"{lock.relative_to(root)}: {found}"
