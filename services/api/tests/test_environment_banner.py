"""Environment strip (backlog G3): the app, the dashboard and the portal read it from one public endpoint."""

import httpx
import pytest

from app.core.config import get_settings
from app.modules.appinfo import router as appinfo


async def test_development_stack_shows_the_strip(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/app/environment")
    assert r.status_code == 200
    assert r.json() == {"banner": "development"}
    assert "max-age" in r.headers["cache-control"]


@pytest.mark.parametrize(
    ("app_env", "choice", "expected"),
    [
        ("production", "auto", None),
        ("production", "pilot", "pilot"),
        ("production", "training", "training"),
        ("development", "off", None),
        ("development", "auto", "development"),
    ],
)
def test_banner_choice(monkeypatch: pytest.MonkeyPatch, app_env: str, choice: str, expected: str | None) -> None:
    cfg = get_settings().model_copy(update={"app_env": app_env, "environment_banner": choice})
    monkeypatch.setattr(appinfo, "get_settings", lambda: cfg)
    assert appinfo.environment_banner() == expected


async def test_app_version_carries_the_environment(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/app/version")
    assert r.status_code == 200
    assert r.json()["environment"] == "development"
