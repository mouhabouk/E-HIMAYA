"""The gateway beside MediaMTX (L5b): local callers only, shape checked, readings kept on disk until the API takes
them, and the same signature as the API checks (docs/sensor-gateway.md)."""

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from gateway import sim
from gateway.config import ConfigError, Settings, _networks
from gateway.forwarder import Forwarder
from gateway.queue import Queue
from gateway.server import make_server

TOKEN = "test-sensor-gateway-token-0001"
KEY = "00" * 32


class FakeApi:
    """The API's internal routes: records the reading batches and the tower events, answers with ``status``."""

    def __init__(self) -> None:
        self.batches: list[list[dict[str, str]]] = []
        self.events: list[dict[str, str]] = []
        self.tokens: list[str | None] = []
        self.status = 200
        api = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: Any) -> None:
                pass

            def do_POST(self) -> None:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                api.tokens.append(self.headers.get("X-Gateway-Token"))
                if self.path == "/internal/towers/events":
                    if api.status == 200:
                        api.events.append(body)
                    answer: dict[str, Any] = {"accepted": True, "reason": None, "suggestion": True}
                else:
                    if api.status == 200:
                        api.batches.append(body["readings"])
                    answer = {"accepted": len(body["readings"]), "rejected": {}, "suggestions": 0}
                data = json.dumps(answer).encode()
                self.send_response(api.status)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"


@pytest.fixture
def api() -> Iterator[FakeApi]:
    fake = FakeApi()
    yield fake
    fake.server.shutdown()


def _settings(api: FakeApi, tmp_path: Path, **extra: Any) -> Settings:
    return Settings(api_url=api.url, token=TOKEN, bind="127.0.0.1", port=0, queue_path=tmp_path / "q.sqlite3", **extra)


def _post(port: int, body: Any, path: str = "/readings") -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_signature_matches_the_api() -> None:
    # Computed by app.modules.sensors.domain.sign in the API: firmware, simulator and API agree.
    expected = "d4b458e4b6d2c2e5546e80548754f6231cc50af2c33c597da0bd2e41d06ab0aa"
    assert sim.sign(KEY, "GAB-R1", "2026-10-28T20:00:00+00:00", "12.5") == expected
    # And app.modules.towers.domain.sign for a tower's event without a frame.
    tower = "da3de1c6f641ec22d489b15c5bb21af095bb49ba96726ef0440bf02abb79d959"
    assert sim.sign_event(KEY, "TWR-1", "2026-10-28T20:00:00+00:00", "fire", "0.87", "3", "5", "") == tower


def test_settings_stay_on_the_local_network() -> None:
    with pytest.raises(ConfigError):
        _networks("192.168.1.0/24,8.8.8.0/24")
    with pytest.raises(ConfigError):
        Settings.from_env({"GATEWAY_API_URL": "http://api:8000", "GATEWAY_TOKEN": "short"})
    s = Settings.from_env({"GATEWAY_API_URL": "http://10.0.0.5:8000/", "GATEWAY_TOKEN": TOKEN})
    assert s.api_url == "http://10.0.0.5:8000" and s.port == 8088


def test_receives_queues_and_relays(api: FakeApi, tmp_path: Path) -> None:
    settings = _settings(api, tmp_path)
    queue = Queue(settings.queue_path, 10)
    server = make_server(settings, queue, Queue(settings.queue_path, 5, table="event"))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    try:
        one = sim.reading("GAB-R1", KEY, 12.5)
        assert _post(port, one) == (202, {"queued": 1})
        assert _post(port, {"readings": [one, one]}) == (202, {"queued": 2})
        assert _post(port, {"readings": [one | {"extra": "x"}]})[0] == 422
        assert _post(port, {"readings": [one | {"sensor": "bad code!"}]})[0] == 422
        assert _post(port, {"readings": []})[0] == 422
        assert queue.size() == 3
        forwarder = Forwarder(settings, queue)
        # The API is down: everything stays queued, and survives a restart of the gateway.
        api.status = 503
        assert forwarder.flush_once() is False and queue.size() == 3
        reopened = Queue(settings.queue_path, 10)
        assert reopened.size() == 3
        reopened.close()
        api.status = 200
        assert forwarder.flush_once() is True and queue.size() == 0
        assert len(api.batches) == 1 and len(api.batches[0]) == 3 and set(api.tokens) == {TOKEN}
        # Full queue: refused rather than lost silently.
        assert queue.push([one] * 10)
        assert _post(port, one) == (503, {"error": "queue_full"})
    finally:
        server.shutdown()
        queue.close()


def test_refuses_callers_outside_the_allowed_networks(api: FakeApi, tmp_path: Path) -> None:
    settings = _settings(api, tmp_path, allow=_networks("10.0.0.0/8"))
    queue = Queue(settings.queue_path, 10)
    server = make_server(settings, queue, Queue(settings.queue_path, 5, table="event"))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        assert _post(server.server_address[1], sim.reading("GAB-R1", KEY, 1.0))[0] == 403
        assert queue.size() == 0
    finally:
        server.shutdown()
        queue.close()


def test_scenarios_cross_the_thresholds() -> None:
    storm = sim.SCENARIOS["storm"]
    assert storm["rain_1h"](0, 12) == 0 and storm["rain_1h"](11, 12) == 60
    assert all(sim.SCENARIOS["calm"]["rain_1h"](i, 12) == 0 for i in range(12))
    with pytest.raises(ValueError):
        sim.parse_sensors("A:zz:rain_1h")
    assert sim.parse_sensors(f"GAB-R1:{KEY}:rain_1h") == [("GAB-R1", KEY, "rain_1h")]


def test_tower_events_queue_apart_and_relay_one_by_one(api: FakeApi, tmp_path: Path) -> None:
    settings = _settings(api, tmp_path)
    queue = Queue(settings.queue_path, 10)
    events = Queue(settings.queue_path, 2, table="event")
    server = make_server(settings, queue, events)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    try:
        frame = b"\xff\xd8\xff\xe0" + b"\x00" * 2000 + b"\xff\xd9"
        event = sim.tower_event("JND-TWR-1", KEY, "smoke", 0.74, frame)
        # A tower event is larger than a batch of readings may be, and has its own shape.
        assert _post(port, event, "/events") == (202, {"queued": 1})
        assert _post(port, event | {"extra": "x"}, "/events")[0] == 422
        assert _post(port, event | {"sig": "short"}, "/events")[0] == 422
        assert _post(port, event | {"tower": "bad code!"}, "/events")[0] == 422
        assert _post(port, event, "/readings")[0] == 422
        assert _post(port, sim.tower_event("JND-TWR-1", KEY, "fire", 0.9), "/events") == (202, {"queued": 1})
        assert _post(port, event, "/events") == (503, {"error": "queue_full"})
        assert events.size() == 2 and queue.size() == 0
        forwarder = Forwarder(settings, queue, events)
        api.status = 503
        assert forwarder.flush_once() is False and events.size() == 2
        api.status = 200
        assert forwarder.flush_once() is True and events.size() == 0
        assert [e["label"] for e in api.events] == ["smoke", "fire"] and api.events[0] == event
    finally:
        server.shutdown()
        queue.close()
        events.close()
