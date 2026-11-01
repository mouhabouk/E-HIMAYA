"""``python -m bridge serve`` runs the bridge; ``python -m bridge check`` tests the configuration, the API (one
heartbeat per camera) and each camera's picture, then stops."""

import argparse
import logging
import os
import signal
import sys
import threading
from types import FrameType

from bridge import camera_http
from bridge.config import ConfigError, Settings
from bridge.core import Bridge
from bridge.queue import Queue
from bridge.server import make_server


def _settings() -> Settings | None:
    try:
        return Settings.load()
    except ConfigError as exc:
        print(f"configuration: {exc}", file=sys.stderr)
        return None


def serve() -> int:
    settings = _settings()
    if settings is None:
        return 2
    queue = Queue(settings.queue, settings.queue_max)
    bridge = Bridge(settings, queue)
    server = make_server(bridge)
    bridge.start()

    def stop(_signum: int, _frame: FrameType | None) -> None:
        bridge.stop()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    logging.getLogger("bridge").info(
        "listening on %s:%d for %d camera(s), relaying to %s",
        settings.listen,
        settings.port,
        len(settings.cameras),
        settings.api_url,
    )
    server.serve_forever()
    bridge.flush_once()
    queue.close()
    return 0


def check() -> int:
    settings = _settings()
    if settings is None:
        return 2
    print(f"configuration: {len(settings.cameras)} camera(s), API {settings.api_url}")
    queue = Queue(settings.queue, settings.queue_max)
    codes = Bridge(settings, queue).heartbeat_once()
    ok = True
    for cam in settings.cameras:
        code = codes[cam.camera]
        api = {204: "OK", 401: "REFUSED (camera id or key)", 422: "REFUSED (clock)", 0: "UNREACHABLE"}.get(
            code, f"HTTP {code}"
        )
        picture = camera_http.snapshot(cam) if cam.vendor != "generic" else None
        shot = "n/a" if cam.vendor == "generic" else ("OK" if picture else "FAILED (address, user, password)")
        print(f"- {cam.label}: system {api}; picture {shot}")
        ok = ok and code == 204 and (cam.vendor == "generic" or picture is not None)
    print(f"queued alarms: {queue.size()}")
    queue.close()
    return 0 if ok else 1


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("BRIDGE_LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s"
    )
    parser = argparse.ArgumentParser(prog="bridge")
    parser.add_argument("command", choices=("serve", "check"))
    args = parser.parse_args()
    return serve() if args.command == "serve" else check()


if __name__ == "__main__":
    sys.exit(main())
