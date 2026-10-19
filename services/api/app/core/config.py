"""Runtime configuration, read from environment variables (see .env.example)."""

import base64
import binascii
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.core.secrets_policy import production_problems


class Settings(BaseSettings):
    # hide_input_in_errors: a start-up error must never print the secrets it was given.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    # production: no /docs, /redoc or /openapi.json, and start-up refuses weak or example secrets
    # (app/core/secrets_policy.py). development (default): local stacks and tests.
    app_env: Literal["development", "production"] = "development"
    database_url: str = Field(description="postgresql+asyncpg://user:pass@host:5432/db")
    valkey_url: str | None = None
    nats_url: str | None = None

    s3_endpoint_url: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: SecretStr | None = None
    s3_bucket_media: str = "ehimaya-media"
    # Endpoint used in pre-signed URLs handed to browsers (defaults to s3_endpoint_url).
    s3_public_endpoint_url: str | None = None
    s3_region: str = "us-east-1"

    # Comma-separated list of accepted token issuers (public realm, staff realm).
    oidc_issuers: Annotated[list[str], NoDecode] = Field(default_factory=list)
    # Optional internal base URL used to fetch JWKS when the public issuer host is not reachable
    # from inside the cluster (e.g. issuer http://localhost:8080, internal http://keycloak:8080).
    oidc_jwks_base_url: str | None = None
    oidc_audience: str = "ehimaya-api"

    anon_pseudonym_secret: SecretStr = Field(min_length=32)
    # AES-256-GCM key for field-level encryption (personal data at rest): base64 of 32 random bytes. It is key
    # version 1 and the root of the blind indexes (CIN, phone, report search words), so it stays configured
    # after a rotation.
    field_encryption_key: SecretStr
    # Key rotation: further key versions "2:<base64>,3:<base64>" (2..255). New values are encrypted with the
    # active version (default: the highest configured); every listed version stays readable. After adding a
    # version run `python -m app.modules.privacy.cli reencrypt`, then retire the old one.
    field_encryption_keys: SecretStr | None = None
    field_encryption_active_version: int | None = Field(default=None, ge=1, le=255)
    # Version of the privacy charter every reporter must have accepted (FR-A-001).
    charter_version: str = "2026-10"
    # Shared secret tusd sends in the Authorization header of its hook calls (HTTP Basic, user "tusd", or
    # "Bearer <secret>"); the hook endpoint is disabled when unset.
    tusd_hook_secret: SecretStr | None = Field(default=None, min_length=24)
    # Background loops (outbox relay, media verification). Disabled in tests, which drive them directly.
    background_workers: bool = True
    # api: serve HTTP only, no background loop; worker: run the background loops and serve only /health and
    # /metrics (no SOS traffic); all: both (single-container development).
    process_role: Literal["api", "worker", "all"] = "all"
    # Bearer token of the Prometheus scraper; /metrics answers 404 while unset.
    metrics_token: SecretStr | None = Field(default=None, min_length=24)

    # Abuse controls (A1). Per-client-IP limits apply to anonymous device identities only (registered
    # citizens are limited per account); windows in seconds. Beyond the global anonymous budget, reports
    # are still accepted but flagged "needs verification" with a lowered priority.
    anon_identity_per_ip: int = Field(default=60, ge=1)
    anon_identity_window_s: int = Field(default=3600, ge=1)
    anon_report_per_ip: int = Field(default=60, ge=1)
    anon_report_window_s: int = Field(default=600, ge=1)
    anon_consent_per_ip: int = Field(default=60, ge=1)
    anon_device_per_ip: int = Field(default=120, ge=1)
    anon_report_budget: int = Field(default=300, ge=1)
    anon_report_budget_window_s: int = Field(default=600, ge=1)

    # Internal AI inference service (services/ai). Without it, reports are scored and grouped by rules only.
    ai_service_url: str | None = None
    ai_service_token: SecretStr | None = Field(default=None, min_length=24)
    # Long audio on a CPU-only server can take minutes to transcribe.
    ai_request_timeout_s: float = 900.0
    ai_concurrency: int = Field(default=2, ge=1, le=32)
    # Retries with back-off when a model is unavailable, then the analysis is marked failed.
    ai_max_attempts: int = Field(default=8, ge=1, le=50)

    # Institutions portal (FR-B-*): base of invitation links and of the certificate verification page.
    portal_public_url: str = "http://localhost:5174"
    # Ed25519 private key (base64 of the 32-byte seed) signing approved safety certificates (FR-B-008).
    # Without it certificates can be generated and submitted but not approved.
    certificate_signing_key: SecretStr | None = None

    # Notification channels (phase 5). Each one is optional: without its settings the channel is recorded
    # as "skipped" and the other channels still go out.
    # Firebase Cloud Messaging (Android, and iOS through APNs): the service-account JSON, base64-encoded.
    fcm_service_account: SecretStr | None = None
    # ┏━━ SIMULATION ━━ in development compose these two point at services/notify-sim (emulated FCM HTTP v1 + OAuth)
    # ┃ PRODUCTION: set FCM_SERVICE_ACCOUNT=<base64 of the key from Firebase console > Project settings > Service
    # ┃   accounts > Generate new private key>, FCM_API_URL=https://fcm.googleapis.com (the default here).
    # ┃   FCM_SERVICE_ACCOUNT wins over FCM_SERVICE_ACCOUNT_FILE; the defaults below are the production ones.
    # ┗━━━━━━━━━━━━━━━━
    # Path of the service-account JSON file, used when FCM_SERVICE_ACCOUNT is unset.
    fcm_service_account_file: Path | None = None
    # Base URL of the FCM HTTP v1 API.
    fcm_api_url: str = "https://fcm.googleapis.com"
    # SMS gateway of a Tunisian operator or aggregator: JSON POST {"to", "text", "sender"} with a bearer token.
    sms_http_url: str | None = None
    sms_http_token: SecretStr | None = None
    sms_sender: str = "E-HIMAYA"
    # Outgoing e-mail (Mailpit in development).
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from: str = "e-Himaya <no-reply@ehimaya.tn>"
    smtp_starttls: bool = True

    # Retention and anonymisation (law 2004-63, architecture §5.3), run by the worker role. Durations in days.
    retention_enabled: bool = True
    retention_interval_s: int = Field(default=3600, ge=60)
    # Domain events already relayed to the bus (the bus itself keeps 7 days).
    retention_events_days: int = Field(default=7, ge=1)
    # Individual pushes and e-mails once sent, skipped or failed.
    retention_notify_outbox_days: int = Field(default=30, ge=1)
    # Finished fan-out jobs of notifications and alerts (their delivery counters).
    retention_notify_dispatch_days: int = Field(default=180, ge=1)
    # Push devices not refreshed by the app for this long are forgotten; their rounded position earlier.
    retention_device_days: int = Field(default=180, ge=1)
    retention_device_location_days: int = Field(default=30, ge=1)
    # Closed or rejected reports are anonymised this long after their last change (5 years).
    retention_report_days: int = Field(default=1826, ge=1)
    # Acceptances of a superseded charter, kept as proof while reports made under them are kept.
    retention_consent_days: int = Field(default=1826, ge=1)
    # Anonymous device identities that never reported and have no push device.
    retention_anon_account_days: int = Field(default=365, ge=1)
    # Erasure requests once the identity-provider account was disabled.
    retention_erasure_days: int = Field(default=30, ge=1)

    api_cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    api_log_level: str = "INFO"
    db_pool_size: int = 10
    db_max_overflow: int = 20

    @field_validator("field_encryption_key")
    @classmethod
    def _check_key(cls, value: SecretStr) -> SecretStr:
        # Fail at start-up rather than on the first encrypted write.
        try:
            raw = base64.b64decode(value.get_secret_value(), validate=True)
        except binascii.Error as exc:
            raise ValueError("FIELD_ENCRYPTION_KEY must be base64 (openssl rand -base64 32)") from exc
        if len(raw) != 32:
            raise ValueError("FIELD_ENCRYPTION_KEY must decode to 32 bytes (openssl rand -base64 32)")
        return value

    @field_validator("field_encryption_keys")
    @classmethod
    def _check_keyring(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None or not value.get_secret_value().strip():
            return None
        parse_keyring(value.get_secret_value())
        return value

    @model_validator(mode="after")
    def _check_production_secrets(self) -> "Settings":
        if self.app_env == "production":
            problems = production_problems(self)
            if problems:
                raise ValueError("APP_ENV=production refuses weak or example secrets: " + "; ".join(problems))
        return self

    @model_validator(mode="after")
    def _check_active_version(self) -> "Settings":
        if self.field_encryption_active_version is not None:
            extra = parse_keyring(self.field_encryption_keys.get_secret_value()) if self.field_encryption_keys else {}
            if self.field_encryption_active_version not in {1, *extra}:
                raise ValueError("FIELD_ENCRYPTION_ACTIVE_VERSION names a key version that is not configured")
        return self

    @field_validator("certificate_signing_key")
    @classmethod
    def _check_signing_key(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        try:
            raw = base64.b64decode(value.get_secret_value(), validate=True)
        except binascii.Error as exc:
            raise ValueError("CERTIFICATE_SIGNING_KEY must be base64 (openssl rand -base64 32)") from exc
        if len(raw) != 32:
            raise ValueError("CERTIFICATE_SIGNING_KEY must decode to 32 bytes (openssl rand -base64 32)")
        return value

    @field_validator(
        "ai_service_url",
        "ai_service_token",
        "metrics_token",
        "tusd_hook_secret",
        "certificate_signing_key",
        "field_encryption_keys",
        "field_encryption_active_version",
        "fcm_service_account",
        "fcm_service_account_file",
        "sms_http_url",
        "sms_http_token",
        "smtp_host",
        "smtp_username",
        "smtp_password",
        mode="before",
    )
    @classmethod
    def _empty_is_unset(cls, value: object) -> object:
        # Compose passes "" when the optional AI profile is not configured.
        return None if value == "" else value

    @field_validator("fcm_api_url", mode="before")
    @classmethod
    def _default_fcm_api_url(cls, value: object) -> object:
        # Compose passes "" when the variable is not set in .env.
        return "https://fcm.googleapis.com" if value == "" or value is None else value

    @field_validator("portal_public_url", "fcm_api_url")
    @classmethod
    def _strip_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("oidc_issuers", "api_cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip().rstrip("/") for item in value.split(",") if item.strip()]
        return value


def parse_keyring(value: str) -> dict[int, bytes]:
    """``"2:<base64>,3:<base64>"`` → {2: key, 3: key}; version 1 is FIELD_ENCRYPTION_KEY."""
    keys: dict[int, bytes] = {}
    for item in (part.strip() for part in value.split(",")):
        if not item:
            continue
        version_text, sep, encoded = item.partition(":")
        if not sep or not version_text.strip().isdigit():
            raise ValueError("FIELD_ENCRYPTION_KEYS entries are <version>:<base64 key>")
        version = int(version_text)
        if not 2 <= version <= 255 or version in keys:
            raise ValueError("FIELD_ENCRYPTION_KEYS versions are distinct numbers from 2 to 255")
        try:
            raw = base64.b64decode(encoded.strip(), validate=True)
        except binascii.Error as exc:
            raise ValueError("FIELD_ENCRYPTION_KEYS keys must be base64 (openssl rand -base64 32)") from exc
        if len(raw) != 32:
            raise ValueError("FIELD_ENCRYPTION_KEYS keys must decode to 32 bytes (openssl rand -base64 32)")
        keys[version] = raw
    return keys


@lru_cache
def get_settings() -> Settings:
    return Settings()
