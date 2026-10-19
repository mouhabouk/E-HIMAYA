"""Runtime configuration, read from environment variables (see .env.example)."""

from functools import lru_cache
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

    # Comma-separated list of accepted token issuers (public realm, staff realm).
    oidc_issuers: Annotated[list[str], NoDecode] = Field(default_factory=list)
    # Optional internal base URL used to fetch JWKS when the public issuer host is not reachable
    # from inside the cluster (e.g. issuer http://localhost:8080, internal http://keycloak:8080).
    oidc_jwks_base_url: str | None = None
    oidc_audience: str = "ehimaya-api"

    anon_pseudonym_secret: SecretStr = Field(min_length=32)

    api_cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    api_log_level: str = "INFO"
    db_pool_size: int = 10
    db_max_overflow: int = 20

    @field_validator("oidc_issuers", "api_cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip().rstrip("/") for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
