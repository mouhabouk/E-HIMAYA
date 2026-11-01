"""The camera bridge: reading each make's alarm, signing as the API checks, the listener and the disk queue."""

import hashlib
import hmac
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from bridge.config import ConfigError, Settings
from bridge.core import Bridge
from bridge.queue import Queue
from bridge.server import make_server
from bridge.signing import event_body, heartbeat_body
from bridge.vendors import parse_dahua_line, parse_generic, parse_hikvision

CAM = "0b7c1d2e-3f40-4a5b-8c6d-7e8f90a1b2c3"
KEY = "ab" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"1" * 100

HIK_TMA = b"""<?xml version="1.0" encoding="UTF-8"?>
<EventNotificationAlert version="2.0" xmlns="http://www.isapi.org/ver20/XMLSchema">
<ipAddress>192.168.1.64</ipAddress><channelID>2</channelID><dateTime>2026-11-01T14:00:00+01:00</dateTime>
<eventType>TMA</eventType><eventState>active</eventState>
<eventDescription>Temperature Measurement Alarm</eventDescription>
<ThermometryAlarm><ruleID>1</ruleID><alarmLevel>1</alarmLevel><currTemperature>87.5</currTemperature></ThermometryAlarm>
</EventNotificationAlert>"""


def settings(tmp_path: Path, host: str = "127.0.0.1", **extra: object) -> Settings:
    raw = {
        "api_url": "https://api.example.tn",
        "port": 0,
        "queue": str(tmp_path / "q.sqlite3"),
        "cameras": [{"camera": CAM, "key": KEY, "vendor": "hikvision", "host": host}],
        **extra,
    }
    return Settings.parse(raw)


def test_the_signature_is_the_one_the_api_checks() -> None:
    body = event_body(KEY, CAM, "2026-11-01T13:00:00+00:00", "fire", "1", "87.5", JPEG, "TMA")
    sha = hashlib.sha256(JPEG).hexdigest()
    msg = f"{CAM}|2026-11-01T13:00:00+00:00|fire|1|87.5|{sha}".encode()
    assert body["sig"] == hmac.new(bytes.fromhex(KEY), msg, hashlib.sha256).hexdigest()
    beat = heartbeat_body(KEY, CAM, "2026-11-01T13:00:00+00:00")
    msg = f"{CAM}|2026-11-01T13:00:00+00:00|heartbeat".encode()
    assert beat["sig"] == hmac.new(bytes.fromhex(KEY), msg, hashlib.sha256).hexdigest()


def test_hikvision_xml_json_and_multipart() -> None:
    alarm = parse_hikvision(HIK_TMA, "application/xml")
    assert alarm is not None and (alarm.label, alarm.vendor_event, alarm.temperature) == ("fire", "TMA", "87.5")
    assert alarm.address == "192.168.1.64"
    assert parse_hikvision(HIK_TMA.replace(b"active", b"inactive")) is None
    assert parse_hikvision(HIK_TMA.replace(b"<eventType>TMA", b"<eventType>VMD")) is None
    data = json.dumps({"ipAddress": "192.168.1.64", "eventType": "smokeDetection", "eventState": "active"})
    smoke = parse_hikvision(data.encode(), "application/json")
    assert smoke is not None and smoke.label == "smoke"
    multipart = (
        b"--MIME_boundary\r\nContent-Type: application/xml\r\n\r\n"
        + HIK_TMA.replace(b"TMA", b"fireDetection")
        + b"\r\n--MIME_boundary\r\nContent-Type: image/jpeg\r\n\r\n"
        + JPEG
        + b"\r\n--MIME_boundary--\r\n"
    )
    fire = parse_hikvision(multipart, "multipart/form-data; boundary=MIME_boundary")
    assert fire is not None and fire.label == "fire" and fire.frame == JPEG


def test_dahua_and_generic() -> None:
    alarm = parse_dahua_line('Code=FireWarning;action=Start;index=0;data={"Temperature" : 92.3}')
    assert alarm is not None and (alarm.label, alarm.temperature) == ("fire", "92.3")
    assert parse_dahua_line("Code=FireWarning;action=Stop;index=0") is None
    assert parse_dahua_line("Code=VideoMotion;action=Start;index=0") is None
    smoke = parse_generic(b'{"label": "smoke"}')
    assert smoke is not None and smoke.label == "smoke"
    assert parse_generic(b'{"label": "flood"}') is None


def test_configuration_is_checked(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="key"):
        Settings.parse(
            {"api_url": "https://a.tn", "cameras": [{"camera": CAM, "key": "x", "vendor": "dahua", "host": "h"}]}
        )
    with pytest.raises(ConfigError, match="api_url"):
        Settings.parse({"api_url": "ftp://a", "cameras": []})
    with pytest.raises(ConfigError, match="token"):
        settings(
            tmp_path,
            cameras=[{"camera": CAM, "key": KEY, "vendor": "hikvision", "host": "h", "publish_url": "rtsp://x"}],
        )


def test_the_listener_takes_alarms_from_its_cameras_only(tmp_path: Path) -> None:
    s = settings(tmp_path)
    queue = Queue(s.queue, s.queue_max)
    bridge = Bridge(s, queue, post=lambda _p, _b: 202, snapshot=lambda _c: JPEG)
    server = make_server(bridge)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/hikvision",
            data=HIK_TMA,
            method="POST",
            headers={"Content-Type": "application/xml"},
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            assert json.loads(r.read()) == {"alarm": True, "queued": True}
        ((_, body),) = queue.peek(5)
        assert body["camera"] == CAM and body["label"] == "fire" and body["temperature"] == "87.5"
        assert body["frame_jpeg_b64"]  # the camera's picture, fetched since the XML had none
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as r:
            assert json.loads(r.read()) == {"ok": True, "queued": 1}
    finally:
        server.shutdown()
    # Another address of the network is refused.
    s2 = settings(tmp_path / "b", host="192.168.1.64")
    other = make_server(Bridge(s2, Queue(s2.queue, 10), post=lambda _p, _b: 202, snapshot=lambda _c: None))
    threading.Thread(target=other.serve_forever, daemon=True).start()
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{other.server_address[1]}/hikvision", data=HIK_TMA, method="POST"
        )
        with pytest.raises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(req, timeout=5)
        assert err.value.code == 403
    finally:
        other.shutdown()


def test_the_queue_keeps_alarms_until_the_api_takes_them(tmp_path: Path) -> None:
    s = settings(tmp_path)
    queue = Queue(s.queue, s.queue_max)
    answers = [503]
    bridge = Bridge(s, queue, post=lambda _p, _b: answers[0], snapshot=lambda _c: None)
    alarm = parse_hikvision(HIK_TMA)
    assert alarm is not None
    bridge.on_alarm(s.cameras[0], alarm)
    assert bridge.flush_once() == 0 and queue.size() == 1  # the API is down: kept
    answers[0] = 202
    assert bridge.flush_once() == 1 and queue.size() == 0
    bridge.on_alarm(s.cameras[0], alarm)
    answers[0] = 409  # already received: dropped
    assert bridge.flush_once() == 1 and queue.size() == 0
    assert bridge.heartbeat_once() == {CAM: 409}
