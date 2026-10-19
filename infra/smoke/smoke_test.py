"""Smoke test of a running stack (docker compose): anonymous report + resumable upload + integrity check.

Standard library only, so it runs anywhere:  python3 infra/smoke/smoke_test.py
Environment: API_URL (default http://localhost:8000), TUS_URL (default http://localhost:1080/api/v1/uploads/).
"""

import base64
import hashlib
import json
import os
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
DEVICE = {"X-Device-Key": base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")}


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


def main() -> None:
    wait_ready()
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

    data = os.urandom(3 * 1024 * 1024 + 7)
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
    print("smoke test passed")


if __name__ == "__main__":
    main()
