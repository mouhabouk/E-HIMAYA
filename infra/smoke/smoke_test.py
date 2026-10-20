"""Smoke test of a running stack (docker compose): anonymous report + resumable upload + integrity check, and the
live-streaming chain (citizen stream, MediaMTX auth, hooks, recording → SHA-256 → S3 → reports.media).

Standard library only, so it runs anywhere:  python3 infra/smoke/smoke_test.py   (from the repository root)
Environment: API_URL (default http://localhost:8000), TUS_URL (default http://localhost:1080/api/v1/uploads/),
NOTIFY_SIM_URL (default http://localhost:8090; empty to skip, e.g. when real FCM/SMS providers are configured),
MEDIAMTX_HLS_URL (default http://localhost:8888; empty to skip the streaming checks), STREAM_SIM_TOKEN (default: read
from ./.env; empty to skip the recorded sim stream), SMOKE_COMPOSE (default
"docker compose --env-file .env -f infra/compose.yml", used to run ffmpeg inside the mediamtx container).
"""

import base64
import hashlib
import json
import os
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin

API = os.environ.get("API_URL", "http://localhost:8000")
TUS = os.environ.get("TUS_URL", "http://localhost:1080/api/v1/uploads/")
NOTIFY_SIM = os.environ.get("NOTIFY_SIM_URL", "http://localhost:8090")
MEDIAMTX_HLS = os.environ.get("MEDIAMTX_HLS_URL", "http://localhost:8888")
COMPOSE = shlex.split(os.environ.get("SMOKE_COMPOSE", "docker compose --env-file .env -f infra/compose.yml"))
DEVICE = {"X-Device-Key": base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")}


def env_file_value(name: str, path: str = ".env") -> str:
    if name in os.environ:
        return os.environ[name]
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                key, sep, value = line.strip().partition("=")
                if sep and key == name:
                    return value.strip()
    except OSError:
        pass
    return ""


def call(method: str, url: str, body: bytes | None = None, headers: dict[str, str] | None = None) -> tuple[int, dict[str, str], bytes]:
    request = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 (fixed local URLs)
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read()


def api(method: str, path: str, payload: Any = None) -> tuple[int, Any]:
    body = json.dumps(payload).encode() if payload is not None else None
    status, _, raw = call(method, f"{API}{path}", body, {"Content-Type": "application/json", **DEVICE})
    return status, json.loads(raw) if raw else None


def wait_ready() -> None:
    for _ in range(90):
        try:
            status, _, raw = call("GET", f"{API}/health/ready")
            if status == 200:
                print("api ready:", raw.decode())
                return
        except OSError:
            pass
        time.sleep(2)
    sys.exit("api never became ready")


def check_notify_sim() -> None:
    # SIMULATION: development channels simulator (docs/api/notify-sim.md). PRODUCTION: run with NOTIFY_SIM_URL="".
    if not NOTIFY_SIM:
        return
    status, _, raw = call("GET", f"{NOTIFY_SIM}/healthz")
    assert status == 200 and json.loads(raw) == {"status": "ok"}, (status, raw)
    status, _, raw = call("GET", f"{NOTIFY_SIM}/api/messages?limit=1")
    assert status == 200 and "last_seq" in json.loads(raw), (status, raw)
    print("notify-sim ready")


def check_streams(report_id: str) -> None:
    """Citizen stream lifecycle, then (with STREAM_SIM_TOKEN) a recorded RTSP stream through MediaMTX."""
    if not MEDIAMTX_HLS:
        return
    # MediaMTX answers (any HTTP status: its root page needs a token).
    status, _, _ = call("GET", f"{MEDIAMTX_HLS}/")
    assert 200 <= status < 500, status
    status, stream = api("POST", f"/api/v1/reports/{report_id}/streams", {})
    assert status == 201, (status, stream)
    assert stream["path"] == f"live/{stream['stream_id']}" and stream["publish_token"], stream
    status, again = api("POST", f"/api/v1/reports/{report_id}/streams", {})
    assert status == 409, (status, again)
    status, summary = api("POST", f"/api/v1/streams/{stream['stream_id']}/stop", {})
    assert status == 200 and summary["status"] in ("ended", "expired"), (status, summary)
    print("citizen stream created and stopped:", stream["stream_id"])

    token = env_file_value("STREAM_SIM_TOKEN")
    if not token:
        print("STREAM_SIM_TOKEN not set: recorded stream check skipped")
        return
    # SIMULATION: a source=sim stream published for 8 s by ffmpeg inside the mediamtx container (no host port).
    sim_headers = {"Content-Type": "application/json", "X-Sim-Token": token}
    body = json.dumps({"label": f"smoke {uuid.uuid4().hex[:8]}"}).encode()
    status, _, raw = call("POST", f"{API}/internal/sim/streams", body, sim_headers)
    assert status == 201, (status, raw)
    sim = json.loads(raw)
    url = f"rtsp://sim:{sim['publish_token']}@127.0.0.1:8554/{sim['path']}"
    ffmpeg = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-re"]
    ffmpeg += ["-f", "lavfi", "-i", "testsrc2=size=640x360:rate=15"]
    ffmpeg += ["-t", "8", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-g", "15"]
    ffmpeg += ["-f", "rtsp", "-rtsp_transport", "tcp", url]
    command = [*COMPOSE, "exec", "-T", "mediamtx", *ffmpeg]
    result = subprocess.run(command, capture_output=True, timeout=120, check=False)  # noqa: S603 (fixed command)
    errors = result.stderr.decode(errors="replace").replace(sim["publish_token"], "<token>")
    assert result.returncode == 0, errors
    for _ in range(60):
        status, _, raw = call("GET", f"{API}/internal/sim/streams/{sim['id']}", None, sim_headers)
        state = json.loads(raw)
        if status == 200 and state["recordings_count"] >= 1:
            print("sim stream recorded:", state)
            return
        time.sleep(2)
    sys.exit(f"sim stream recording never stored: {state}")


def main() -> None:
    wait_ready()
    check_notify_sim()
    status, _ = api("POST", "/api/v1/consents", {"charter_version": "2026-10", "locale": "ar", "platform": "android"})
    assert status == 201, status
    body = {
        "client_uuid": str(uuid.uuid4()),
        "category": "flood",
        "text": "smoke test",
        "lang": "en",
        "location": {"lat": 36.8065, "lon": 10.1815, "accuracy_m": 10},
        "created_at": datetime.now(UTC).isoformat(),
    }
    status, report = api("POST", "/api/v1/reports", body)
    assert status == 201, (status, report)
    print("report:", report["tracking_code"], "gouvernorat", report["gouvernorat_code"])
    assert report["gouvernorat_code"] == 11

    # A JPEG signature: the API checks the magic bytes against the declared type (A7) and quarantines a mismatch.
    data = b"\xff\xd8\xff\xe0" + os.urandom(3 * 1024 * 1024 + 3)
    meta = {
        "report_id": report["id"],
        "kind": "image",
        "filetype": "image/jpeg",
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    tus = {"Tus-Resumable": "1.0.0", **DEVICE}
    encoded = ",".join(f"{k} {base64.b64encode(v.encode()).decode()}" for k, v in meta.items())
    status, headers, raw = call("POST", TUS, None, {**tus, "Upload-Length": str(len(data)), "Upload-Metadata": encoded})
    assert status == 201, (status, raw)
    location = urljoin(TUS, headers["Location"])
    offset = 0
    while offset < len(data):
        status, headers, raw = call(
            "PATCH",
            location,
            data[offset : offset + 1024 * 1024],
            {**tus, "Upload-Offset": str(offset), "Content-Type": "application/offset+octet-stream"},
        )
        assert status == 204, (status, raw)
        offset = int(headers["Upload-Offset"])
    print("uploaded", offset, "bytes")

    for _ in range(30):
        status, mine = api("GET", "/api/v1/reports/mine")
        media = mine["items"][0]["media"]
        if media and media[0]["status"] == "stored":
            print("media stored and verified:", media[0]["sha256"])
            break
        time.sleep(1)
    else:
        sys.exit(f"media not verified: {media}")

    status, track = api("GET", f"/api/v1/reports/track/{report['tracking_code']}")
    assert status == 200 and track["status"] == "received"
    check_streams(report["id"])
    print("smoke test passed")


if __name__ == "__main__":
    main()
