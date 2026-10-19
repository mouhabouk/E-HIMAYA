# ┏━━ SIMULATION ━━ test fixtures of the channels simulator
# ┃ PRODUCTION: not shipped; see docs/api/notify-sim.md "Switching to production".
# ┗━━━━━━━━━━━━━━━━
import json
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.fcm import FCM_SCOPE, JWT_BEARER
from app.main import create_app

PUBLIC_URL = "http://notify-sim.test"
SMS_TOKEN = "test-sms-token"
FAIL_NUMBER = "+21698000000"


class Clock:
    def __init__(self) -> None:
        self.now = time.time()

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path,
        public_url=PUBLIC_URL + "/",
        sms_token=SMS_TOKEN,
        sms_fail_numbers=f" {FAIL_NUMBER} ,+21622000000",  # type: ignore[arg-type]
        max_messages=1000,
    )


@pytest.fixture
def client(settings: Settings, clock: Clock) -> Iterator[TestClient]:
    with TestClient(create_app(settings, clock=clock), base_url=PUBLIC_URL) as test_client:
        yield test_client


@pytest.fixture
def account(settings: Settings, client: TestClient) -> dict[str, Any]:
    info: dict[str, Any] = json.loads(settings.service_account_file.read_text())
    return info


def assertion(account: dict[str, Any], now: float, *, key: Any = None, **overrides: Any) -> str:
    claims: dict[str, Any] = {
        "iss": account["client_email"],
        "scope": FCM_SCOPE,
        "aud": account["token_uri"],
        "iat": int(now),
        "exp": int(now) + 3600,
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key or account["private_key"], algorithm="RS256")


def token_request(client: TestClient, value: str, grant_type: str = JWT_BEARER) -> Any:
    return client.post("/oauth2/token", data={"grant_type": grant_type, "assertion": value})


@pytest.fixture
def access_token(client: TestClient, account: dict[str, Any], clock: Clock) -> str:
    response = token_request(client, assertion(account, clock.now))
    assert response.status_code == 200, response.text
    token: str = response.json()["access_token"]
    return token


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
