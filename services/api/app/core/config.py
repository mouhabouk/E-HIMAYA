"""Runtime configuration, read from environment variables (see .env.example)."""

import base64
import binascii
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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
    # AES-256-GCM key for field-level encryption (CIN, medical data): base64 of 32 random bytes.
    field_encryption_key: SecretStr
    # Version of the privacy charter every reporter must have accepted (FR-A-001).
    charter_version: str = "2026-10"
    # Shared secret in the tusd hook URL path; the hook endpoint is disabled when unset.
    tusd_hook_secret: SecretStr | None = Field(default=None, min_length=24)
    # Background loops (outbox relay, media verification). Disabled in tests, which drive them directly.
    background_workers: bool = True

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
        "certificate_signing_key",
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
