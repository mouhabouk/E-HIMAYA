# ┏━━ SIMULATION ━━ FcmPush and HttpSms talk to the emulated FCM HTTP v1 + OAuth and SMS gateway, no network
# ┃ PRODUCTION: the same provider code talks to fcm.googleapis.com / oauth2.googleapis.com and the SMS provider once
# ┃   FCM_SERVICE_ACCOUNT, FCM_API_URL, SMS_HTTP_URL, SMS_HTTP_TOKEN are set (docs/api/notify-sim.md).
# ┗━━━━━━━━━━━━━━━━
"""The API's real delivery providers against the channels simulator (services/notify-sim), in-process.

Both services have a top-level package named ``app``, so the simulator is loaded under the name ``notify_sim``
(its modules only use relative imports). Requests go through ``httpx.ASGITransport``: the providers build the
same absolute URLs as in compose (http://notify-sim:8090/...), nothing listens on a port.
"""

import base64
import importlib
import importlib.util
import json
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import pytest

from app.core.config import get_settings
from app.modules.notify import providers
from app.modules.notify.providers import FcmPush, HttpSms, Push, Result

SIM_ROOT = Path(__file__).resolve().parents[2] / "notify-sim"
SIM_URL = "http://notify-sim:8090"
SMS_TOKEN = "sim-sms-token"
FAIL_NUMBER = "+21698000000"


def _load_sim() -> ModuleType:
    if "notify_sim.main" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "notify_sim", SIM_ROOT / "app" / "__init__.py", submodule_search_locations=[str(SIM_ROOT / "app")]
        )
        assert spec and spec.loader, f"notify-sim not found under {SIM_ROOT}"
        package = importlib.util.module_from_spec(spec)
        sys.modules["notify_sim"] = package
        spec.loader.exec_module(package)
    return importlib.import_module("notify_sim.main")


class Sim:
    """The simulator app plus a client that records every request the providers make."""

    def __init__(self, data_dir: Path) -> None:
        sim = _load_sim()
        config = importlib.import_module("notify_sim.config")
        settings = config.Settings(
            data_dir=data_dir, public_url=SIM_URL, sms_token=SMS_TOKEN, sms_fail_numbers=FAIL_NUMBER
        )
        self.app = sim.create_app(settings)
        self.account_file: Path = settings.service_account_file
        self.requests: list[httpx.Request] = []

        async def record(request: httpx.Request) -> None:
            self.requests.append(request)

        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), event_hooks={"request": [record]})

    def paths(self) -> list[str]:
        return [r.url.path for r in self.requests]

    async def messages(self, **params: Any) -> list[dict[str, Any]]:
        response = await self.client.get(f"{SIM_URL}/api/messages", params=params)
        assert response.status_code == 200, response.text
        items: list[dict[str, Any]] = response.json()["items"]
        return items


@pytest.fixture
async def sim(tmp_path: Path) -> AsyncIterator[Sim]:
    s = Sim(tmp_path)
    try:
        yield s
    finally:
        await s.client.aclose()


@pytest.fixture
def account(sim: Sim) -> dict[str, Any]:
    info: dict[str, Any] = json.loads(sim.account_file.read_text())
    return info


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> Iterator[pytest.MonkeyPatch]:
    """Change provider settings for one test, then rebuild the defaults."""
    get_settings.cache_clear()
    yield monkeypatch
    monkeypatch.undo()
    get_settings.cache_clear()


def alert(token: str) -> Push:
    return Push(token, "android", "إنذار فيضان", "ابتعدوا عن الأودية", {"type": "alert", "id": "42"}, alert=True)


async def test_fcm_token_flow_and_alert_payload(sim: Sim, account: dict[str, Any]) -> None:
    push = FcmPush(account, client=sim.client, api_url=SIM_URL)

    assert await push.send(alert("sim-device-1")) == Result(ok=True)
    info = Push("sim-device-2", "ios", "Info", "Exercice demain", {"type": "info", "id": "43"})
    assert await push.send(info) == Result(ok=True)

    # One OAuth exchange (signed assertion verified by the simulator), then the cached access token.
    assert sim.paths() == [
        "/oauth2/token",
        "/v1/projects/ehimaya-sim/messages:send",
        "/v1/projects/ehimaya-sim/messages:send",
    ]
    sent = json.loads(sim.requests[1].content)
    assert sent == push.message(alert("sim-device-1"))
    assert sent["message"]["apns"] == {
        "headers": {"apns-priority": "10", "apns-collapse-id": "alert:42"},
        "payload": {"aps": {"sound": "alert.caf", "interruption-level": "time-sensitive"}},
    }
    assert sim.requests[1].headers["authorization"] == sim.requests[2].headers["authorization"]

    first, second = await sim.messages(channel="push")
    assert first["token"] == "sim-device-1"
    assert (first["title"], first["body"]) == ("إنذار فيضان", "ابتعدوا عن الأودية")
    assert first["data"] == {"type": "alert", "id": "42"}
    assert (first["android_channel"], first["priority"]) == ("ehimaya_alerts_v2", "high")
    assert second["android_channel"] == "ehimaya_default"
    assert sent["message"]["android"]["notification"]["tag"] == "alert:42"

    critical = Push(
        "sim-device-3", "android", "إنذار", "إخلاء", {"type": "alert", "id": "44"}, alert=True, critical=True
    )
    assert await push.send(critical) == Result(ok=True)
    [third] = await sim.messages(token="sim-device-3")
    assert third["android_channel"] == "ehimaya_critical_v2"

    # Personal pushes carry no "id": the collapse key falls back to the call-out or report id (same key as the app).
    callout = Push("sim-device-4", "android", "t", "b", {"type": "callout", "callout_id": "c-7", "redacted": "1"})
    assert push.message(callout)["message"]["android"]["notification"]["tag"] == "callout:c-7"
    assert [m["token"] for m in await sim.messages(token="sim-device-2")] == ["sim-device-2"]


async def test_fcm_unregistered_token(sim: Sim, account: dict[str, Any]) -> None:
    push = FcmPush(account, client=sim.client, api_url=SIM_URL)
    result = await push.send(alert("sim-unregistered-0001"))
    assert result == Result(ok=False, unregistered=True, error="http_404")
    assert await sim.messages() == []


async def test_fcm_refused_key(sim: Sim, account: dict[str, Any]) -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = other.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    push = FcmPush({**account, "private_key": pem}, client=sim.client, api_url=SIM_URL)
    result = await push.send(alert("sim-device-1"))
    assert result.ok is False and result.unregistered is False
    assert result.error == "HTTPStatusError"  # invalid_grant from the token endpoint
    assert sim.paths() == ["/oauth2/token"]


async def test_sms_gateway(sim: Sim) -> None:
    sms = HttpSms(f"{SIM_URL}/sms/send", SMS_TOKEN, "E-HIMAYA", client=sim.client)
    assert await sms.send("+21655123456", "تحذير: فيضان في وادي مجردة") == Result(ok=True)
    assert await sms.send(FAIL_NUMBER, "Alerte") == Result(ok=False, error="http_503")
    assert await sms.send("+33612345678", "Alerte") == Result(ok=False, error="http_400")
    wrong_token = HttpSms(f"{SIM_URL}/sms/send", "wrong", "E-HIMAYA", client=sim.client)
    assert await wrong_token.send("+21655123456", "Alerte") == Result(ok=False, error="http_401")

    [item] = await sim.messages(channel="sms")
    assert item["to"] == "+21655123456"
    assert item["text"] == "تحذير: فيضان في وادي مجردة"
    assert (item["segments"], item["encoding"]) == (1, "UCS-2")


async def test_build_uses_service_account_file(env: pytest.MonkeyPatch, sim: Sim) -> None:
    env.delenv("FCM_SERVICE_ACCOUNT", raising=False)
    env.setenv("FCM_SERVICE_ACCOUNT_FILE", str(sim.account_file))
    env.setenv("FCM_API_URL", SIM_URL + "/")
    env.setenv("SMS_HTTP_URL", f"{SIM_URL}/sms/send")
    env.setenv("SMS_HTTP_TOKEN", SMS_TOKEN)
    built = providers._build()
    assert isinstance(built.push, FcmPush)
    assert built.push._url == f"{SIM_URL}/v1/projects/ehimaya-sim/messages:send"
    assert isinstance(built.sms, HttpSms)


async def test_build_prefers_inline_service_account(env: pytest.MonkeyPatch, account: dict[str, Any]) -> None:
    real = {**account, "project_id": "ehimaya-prod"}
    env.setenv("FCM_SERVICE_ACCOUNT", base64.b64encode(json.dumps(real).encode()).decode())
    env.setenv("FCM_SERVICE_ACCOUNT_FILE", "/nonexistent/fcm-service-account.json")
    env.setenv("FCM_API_URL", "")  # compose passes "" when .env leaves it empty
    built = providers._build()
    assert isinstance(built.push, FcmPush)
    assert built.push._url == "https://fcm.googleapis.com/v1/projects/ehimaya-prod/messages:send"


@pytest.mark.parametrize("path", ["", "/nonexistent/fcm-service-account.json"])
async def test_build_without_usable_file_is_unconfigured(env: pytest.MonkeyPatch, path: str) -> None:
    env.delenv("FCM_SERVICE_ACCOUNT", raising=False)
    env.setenv("FCM_SERVICE_ACCOUNT_FILE", path)
    assert providers._build().push.configured is False


async def test_google_account_ignores_simulator_url(env: pytest.MonkeyPatch, account: dict[str, Any]) -> None:
    # A real key left with the development FCM_API_URL must still reach Google, not the simulator.
    real = {**account, "project_id": "ehimaya-prod", "token_uri": "https://oauth2.googleapis.com/token"}
    env.setenv("FCM_SERVICE_ACCOUNT", base64.b64encode(json.dumps(real).encode()).decode())
    env.setenv("FCM_API_URL", SIM_URL)
    built = providers._build()
    assert isinstance(built.push, FcmPush)
    assert built.push._url == "https://fcm.googleapis.com/v1/projects/ehimaya-prod/messages:send"


async def test_fcm_wrong_project_keeps_devices(sim: Sim, account: dict[str, Any]) -> None:
    # A bare 404 (wrong project) is a configuration error, not an uninstalled app.
    push = FcmPush({**account, "project_id": "other-project"}, client=sim.client, api_url=SIM_URL)
    result = await push.send(alert("sim-device-1"))
    assert result == Result(ok=False, unregistered=False, error="http_404")
