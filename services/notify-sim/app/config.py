# ┏━━ SIMULATION ━━ settings of the channels simulator (fake FCM project, fake SMS gateway token)
# ┃ PRODUCTION: none of these exist in production; the API's FCM_SERVICE_ACCOUNT / FCM_API_URL / SMS_HTTP_URL /
# ┃   SMS_HTTP_TOKEN take the real values instead (docs/api/notify-sim.md, "Switching to production").
# ┗━━━━━━━━━━━━━━━━
"""SIMULATION — runtime configuration (environment variables prefixed ``SIM_``)."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SIM_", extra="ignore")

    # Where the generated service account (RSA key included) is kept across restarts.
    data_dir: Path = Path("/data")
    # Project id of the fake Firebase project; the API reads it from the service account.
    fcm_project: str = "ehimaya-sim"
    # Base URL under which the API reaches this service: becomes the token_uri of the service account.
    public_url: str = "http://notify-sim:8090"
    # Bearer token the SMS gateway accepts.
    sms_token: str = Field(default="sim-sms-token", min_length=1)
    # Numbers for which the gateway answers 503 operator_unavailable (exercise the failure path).
    sms_fail_numbers: Annotated[frozenset[str], NoDecode] = Field(default_factory=frozenset)
    # Messages kept in memory for inspection.
    max_messages: int = Field(default=1000, ge=1, le=100_000)
    log_level: str = "INFO"

    @field_validator("public_url")
    @classmethod
    def _strip_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("sms_fail_numbers", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return frozenset(item.strip() for item in value.split(",") if item.strip())
        return value

    @property
    def token_uri(self) -> str:
        return f"{self.public_url}/oauth2/token"

    @property
    def service_account_file(self) -> Path:
        return self.data_dir / "fcm-service-account.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
