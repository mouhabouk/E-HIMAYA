"""A3: APP_ENV=production refuses weak or example secrets and hides the API documentation."""

import base64
import os
import secrets
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.secrets_policy import weak_reason

STRONG: dict[str, Any] = {
    "database_url": f"postgresql+asyncpg://ehimaya_app:{secrets.token_hex(24)}@postgres:5432/ehimaya",
    "valkey_url": f"redis://:{secrets.token_urlsafe(24)}@valkey:6379/0",
    "anon_pseudonym_secret": secrets.token_hex(32),
    "field_encryption_key": base64.b64encode(os.urandom(32)).decode(),
    "tusd_hook_secret": secrets.token_hex(24),
    "certificate_signing_key": base64.b64encode(os.urandom(32)).decode(),
    "s3_secret_key": secrets.token_urlsafe(30),
    # Phase 6 (live streaming): the test environment sets example values of these, replaced here.
    "mediamtx_api_password": secrets.token_urlsafe(24),
    "mediamtx_hook_token": secrets.token_urlsafe(24),
    "vision_callback_token": secrets.token_urlsafe(24),
    "vision_read_password": secrets.token_urlsafe(24),
    "stream_sim_token": None,
    # Phase 7 (telephony, SMS gateway): same.
    "telephony_ari_password": secrets.token_urlsafe(24),
    "sms_inbound_secret": secrets.token_urlsafe(32),
    "telephony_sim_token": None,
}


def production(**overrides: Any) -> Settings:
    return Settings(_env_file=None, app_env="production", **{**STRONG, **overrides})  # type: ignore[call-arg]


def test_strong_secrets_start() -> None:
    assert production().app_env == "production"


@pytest.mark.parametrize(
    ("setting", "value", "reason"),
    [
        ("anon_pseudonym_secret", "change-me-generate-with-openssl-rand-hex-32", "change-me"),
        ("anon_pseudonym_secret", "test-secret-test-secret-test-secret-0001", "test-secret"),
        ("anon_pseudonym_secret", "aaaaaaaaaaaaaaaabbbbbbbbbbbbbbbbbbbbbbbb", "variety"),
        ("field_encryption_key", "dGVzdC1rZXktdGVzdC1rZXktdGVzdC1rZXktMzJieXQ=", "randomness"),
        ("field_encryption_key", base64.b64encode(bytes(32)).decode(), "randomness"),
        ("tusd_hook_secret", "change-me-generate-with-openssl-rand-hex-24", "change-me"),
        ("s3_secret_key", "change-me-s3-secret", "change-me"),
        ("s3_secret_key", "short-Secret1", "shorter"),
        ("database_url", "postgresql+asyncpg://ehimaya:change-me-app@postgres:5432/ehimaya", "DATABASE_URL"),
        ("valkey_url", "redis://:change-me-valkey@valkey:6379/0", "VALKEY_URL"),
        ("mediamtx_hook_token", "change-me-generate-with-openssl-rand-hex-24", "change-me"),
        ("mediamtx_api_password", "change-me-generate-with-openssl-rand-hex-24", "change-me"),
        ("vision_callback_token", "change-me-generate-with-openssl-rand-hex-24", "change-me"),
        ("vision_api_token", "change-me-generate-with-openssl-rand-hex-24", "change-me"),
        ("telephony_ari_password", "change-me-generate-with-openssl-rand-hex-24", "change-me"),
        ("sms_inbound_secret", "change-me-generate-with-openssl-rand-hex-32", "change-me"),
        ("telephony_sim_token", secrets.token_urlsafe(24), "TELEPHONY_SIM_TOKEN"),
        ("sms_phone_signing_key", secrets.token_urlsafe(12), "SMS_PHONE_SIGNING_KEY"),
    ],
)
def test_weak_secret_is_refused(setting: str, value: str, reason: str) -> None:
    with pytest.raises(ValidationError, match=reason) as error:
        production(**{setting: value})
    assert setting.upper() in str(error.value)
    # The secret itself never appears in the error.
    assert value not in str(error.value).replace(setting.upper(), "")


def test_development_accepts_example_values() -> None:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        database_url="postgresql+asyncpg://ehimaya:ehimaya@localhost/ehimaya",
        anon_pseudonym_secret="test-secret-test-secret-test-secret-0001",
        field_encryption_key="dGVzdC1rZXktdGVzdC1rZXktdGVzdC1rZXktMzJieXQ=",
    )
    assert settings.app_env == "development"


def test_random_values_pass_the_policy() -> None:
    for _ in range(50):
        assert weak_reason(secrets.token_hex(32)) is None
        assert weak_reason(secrets.token_hex(24)) is None
        assert weak_reason(base64.b64encode(os.urandom(32)).decode()) is None
        assert weak_reason(f"2:{base64.b64encode(os.urandom(32)).decode()}") is None


async def test_production_app_hides_docs_and_sets_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.main as main

    monkeypatch.setattr(main, "get_settings", lambda: production(background_workers=False))
    prod_app = main.create_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=prod_app), base_url="http://api.test") as c:
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert (await c.get(path)).status_code == 404, path
        r = await c.get("/health/live")
    assert r.status_code == 200
    assert r.headers["Strict-Transport-Security"].startswith("max-age=")
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
    assert r.headers["X-Frame-Options"] == "DENY"


async def test_development_app_serves_docs(client: httpx.AsyncClient) -> None:
    assert (await client.get("/openapi.json")).status_code == 200
    r = await client.get("/health/live")
    assert "Strict-Transport-Security" not in r.headers
    assert r.headers["Content-Security-Policy"].startswith("default-src 'none'")


def test_settings_errors_never_echo_secrets() -> None:
    secret = "change-me-but-this-must-not-be-printed-0001"
    with pytest.raises(ValidationError) as error:
        production(anon_pseudonym_secret=secret)
    assert secret not in str(error.value)


def test_stream_simulator_is_refused_in_production() -> None:
    with pytest.raises(ValidationError, match="STREAM_SIM_TOKEN"):
        production(stream_sim_token=secrets.token_urlsafe(24))


def test_staff_second_factor_is_required_in_production() -> None:
    with pytest.raises(ValidationError, match="STAFF_MFA_REQUIRED"):
        production(staff_mfa_required=False)


def test_evidence_signing_key_is_checked() -> None:
    with pytest.raises(ValidationError, match="EVIDENCE_SIGNING_KEY must decode to 32 bytes"):
        production(evidence_signing_key="c2hvcnQ=")
