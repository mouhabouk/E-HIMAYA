# ┏━━ SIMULATION ━━ tests of the emulated service account and Google OAuth token endpoint
# ┃ PRODUCTION: not shipped; see docs/api/notify-sim.md "Switching to production".
# ┗━━━━━━━━━━━━━━━━
import json
import stat
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.account import CLIENT_EMAIL, load_or_create
from app.config import Settings
from tests.conftest import PUBLIC_URL, Clock, assertion, bearer, token_request


def test_service_account_has_google_shape(settings: Settings, account: dict[str, Any]) -> None:
    assert account["type"] == "service_account"
    assert account["project_id"] == "ehimaya-sim"
    assert account["client_email"] == CLIENT_EMAIL
    assert account["token_uri"] == f"{PUBLIC_URL}/oauth2/token"
    assert account["private_key"].startswith("-----BEGIN PRIVATE KEY-----")
    assert account["private_key_id"] and account["client_id"]
    assert stat.S_IMODE(settings.service_account_file.stat().st_mode) == 0o600


def test_key_is_kept_across_restarts_and_follows_settings(settings: Settings, account: dict[str, Any]) -> None:
    moved = settings.model_copy(update={"fcm_project": "other-project", "public_url": "http://elsewhere:8090"})
    reloaded = load_or_create(moved)
    assert reloaded.info["private_key"] == account["private_key"]
    assert reloaded.info["private_key_id"] == account["private_key_id"]
    assert reloaded.project_id == "other-project"
    assert reloaded.token_uri == "http://elsewhere:8090/oauth2/token"
    assert json.loads(settings.service_account_file.read_text())["project_id"] == "other-project"


def test_token_issued_for_valid_assertion(client: TestClient, account: dict[str, Any], clock: Clock) -> None:
    response = token_request(client, assertion(account, clock.now))
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"].startswith("sim-at-")
    assert body["expires_in"] == 3600
    assert body["token_type"] == "Bearer"


def test_scope_may_list_several_scopes(client: TestClient, account: dict[str, Any], clock: Clock) -> None:
    scope = "https://www.googleapis.com/auth/cloud-platform https://www.googleapis.com/auth/firebase.messaging"
    assert token_request(client, assertion(account, clock.now, scope=scope)).status_code == 200


@pytest.mark.parametrize(
    ("overrides", "fragment"),
    [
        ({"aud": "https://oauth2.googleapis.com/token"}, "aud"),
        ({"iss": "someone@else.iam.gserviceaccount.com"}, "iss"),
        ({"scope": "https://www.googleapis.com/auth/cloud-platform"}, "scope"),
        ({"scope": None}, "scope"),
        ({"exp": None}, "exp"),
    ],
)
def test_bad_claims_are_invalid_grant(
    client: TestClient, account: dict[str, Any], clock: Clock, overrides: dict[str, Any], fragment: str
) -> None:
    response = token_request(client, assertion(account, clock.now, **overrides))
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "invalid_grant"
    assert fragment in body["error_description"]


def test_bad_signature_is_invalid_grant(client: TestClient, account: dict[str, Any], clock: Clock) -> None:
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    response = token_request(client, assertion(account, clock.now, key=other))
    assert response.status_code == 400
    assert response.json() == {"error": "invalid_grant", "error_description": "Invalid JWT Signature."}


def test_malformed_assertion_is_invalid_grant(client: TestClient) -> None:
    response = token_request(client, "not-a-jwt")
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_grant"


@pytest.mark.parametrize(
    "times",
    [
        {"iat": -7200, "exp": -3600},  # expired
        {"iat": 0, "exp": 3601},  # longer than an hour
        {"iat": 600, "exp": 3000},  # issued in the future
    ],
)
def test_lifetime_is_checked(client: TestClient, account: dict[str, Any], clock: Clock, times: dict[str, int]) -> None:
    now = int(clock.now)
    response = token_request(client, assertion(account, now, iat=now + times["iat"], exp=now + times["exp"]))
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_grant"


def test_other_grant_type_is_refused(client: TestClient, account: dict[str, Any], clock: Clock) -> None:
    response = token_request(client, assertion(account, clock.now), grant_type="client_credentials")
    assert response.status_code == 400
    assert response.json()["error"] == "unsupported_grant_type"


def test_access_token_expires(client: TestClient, access_token: str, clock: Clock) -> None:
    message = {"message": {"token": "device-1", "notification": {"title": "t", "body": "b"}}}
    url = "/v1/projects/ehimaya-sim/messages:send"
    assert client.post(url, json=message, headers=bearer(access_token)).status_code == 200
    clock.now += 3601
    response = client.post(url, json=message, headers=bearer(access_token))
    assert response.status_code == 401
    assert response.json()["error"]["status"] == "UNAUTHENTICATED"
