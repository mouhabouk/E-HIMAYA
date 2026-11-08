# covers: NFR-13
"""The system logs window (docs/phase-h/design-h5.md §1): Loki behind the API, for the technical administrators."""

import json
from typing import Any

import httpx
import pytest

from app.core.config import get_settings
from app.modules.syslogs import router as syslogs
from tests.conftest import STAFF_ISS, TokenFactory, bearer


def sysadmin(make_token: TokenFactory, **claims: Any) -> dict[str, str]:
    claims.setdefault("scope_level", "national")
    return bearer(make_token(issuer=STAFF_ISS, roles=["sysadmin"], **claims))


@pytest.fixture
def loki(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    calls: list[tuple[str, dict[str, Any]]] = []
    line = {"event": "http.request", "level": "error", "request_id": "abcd1234abcd", "status": 500}

    async def fake_get(path: str, params: dict[str, Any]) -> dict[str, Any]:
        calls.append((path, params))
        if path.endswith("/query_range"):
            return {
                "data": {
                    "result": [
                        {
                            "stream": {"service": "api", "level": "error"},
                            "values": [["1762620000000000000", json.dumps(line)]],
                        },
                        {"stream": {"service": "caddy"}, "values": [["1762620001000000000", "plain text line"]]},
                    ]
                }
            }
        if path.endswith("/query"):
            level = "errors" if "error" in params["query"] else "warnings"
            return {
                "data": {"result": [{"metric": {"service": "api"}, "value": [0, "3" if level == "errors" else "5"]}]}
            }
        return {"data": ["api", "caddy", "worker"]}

    monkeypatch.setattr(get_settings(), "loki_url", "http://loki:3100")
    monkeypatch.setattr(syslogs, "_get", fake_get)
    return calls


def test_query_is_built_from_checked_parameters_only() -> None:
    assert syslogs.build_query(None, None, None, None) == '{service=~".+"}'
    assert (
        syslogs.build_query("api", "warning", "abcd1234abcd", 'say "hi"')
        == '{service="api", level=~"warning|error|critical"} |= "abcd1234abcd" |= "say \\"hi\\""'
    )


async def test_sysadmin_reads_lines_and_summary(
    client: httpx.AsyncClient, make_token: TokenFactory, loki: list[tuple[str, dict[str, Any]]]
) -> None:
    headers = sysadmin(make_token)
    r = await client.get(
        "/api/v1/admin/logs", params={"service": "api", "level": "error", "minutes": 30}, headers=headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["query"] == '{service="api", level=~"error|critical"}'
    first, second = body["items"]
    assert second["service"] == "api" and second["event"] == "http.request" and second["fields"]["status"] == 500
    assert first["service"] == "caddy" and first["text"] == "plain text line" and first["fields"] is None
    path, params = loki[0]
    assert path == "/loki/api/v1/query_range" and params["direction"] == "backward"
    r = await client.get("/api/v1/admin/logs/summary", headers=headers)
    assert r.status_code == 200
    services = {s["service"]: s for s in r.json()["services"]}
    assert services["api"] == {"service": "api", "errors": 3, "warnings": 5}
    assert services["worker"]["errors"] == 0


async def test_window_is_national_technical_and_checks_input(
    client: httpx.AsyncClient, make_token: TokenFactory, loki: list[tuple[str, dict[str, Any]]]
) -> None:
    regional = bearer(make_token(issuer=STAFF_ISS, roles=["sysadmin"], gouvernorat_code="61"))
    assert (await client.get("/api/v1/admin/logs", headers=regional)).status_code == 403
    operator = bearer(make_token(issuer=STAFF_ISS, roles=["ops_manager"], scope_level="national"))
    assert (await client.get("/api/v1/admin/logs", headers=operator)).status_code == 403
    headers = sysadmin(make_token)
    bad = await client.get("/api/v1/admin/logs", params={"service": 'api"} or {x=~".+'}, headers=headers)
    assert bad.status_code == 422
    assert (await client.get("/api/v1/admin/logs", params={"request_id": "x"}, headers=headers)).status_code == 422
    assert loki == []


async def test_not_configured(
    client: httpx.AsyncClient, make_token: TokenFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "loki_url", None)
    r = await client.get("/api/v1/admin/logs", headers=sysadmin(make_token))
    assert r.status_code == 503 and r.json()["detail"] == "logs_not_configured"


async def test_each_request_leaves_one_line_with_its_route(
    client: httpx.AsyncClient, capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()
    r = await client.get("/api/v1/public/org-kinds", headers={"X-Request-ID": "trace-test-0001"})
    await client.get("/health/live")
    assert r.headers["X-Request-ID"] == "trace-test-0001"
    out = capsys.readouterr().out
    entries = [json.loads(line) for line in out.splitlines() if line.startswith("{")]
    lines = [entry for entry in entries if entry.get("event") == "http.request"]
    assert len(lines) == 1, out
    line = lines[0]
    assert line["route"] == "/api/v1/public/org-kinds" and line["status"] == 200
    assert line["level"] == "info" and line["duration_ms"] >= 0 and line["request_id"] == "trace-test-0001"
