"""The bridge's listener on the institution's network: the cameras post their alarms here.

* ``POST /hikvision``: Hikvision «Alarm Server / HTTP Listening» (XML, JSON or multipart with the picture);
* ``POST /generic``: any device, JSON ``{"label": "fire"|"smoke", "temperature": "…"}``;
* ``GET /health``: ``{"ok": true, "queued": n}``.

A post is taken only from the address of a camera in the configuration, and only for that camera: another computer of
the network cannot raise an alarm in its name.
"""

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from bridge.core import Bridge
from bridge.vendors import parse_generic, parse_hikvision

log = logging.getLogger("bridge")
MAX_BODY = 4 * 1024 * 1024


def make_server(bridge: Bridge) -> ThreadingHTTPServer:
    settings = bridge.settings

    class Handler(BaseHTTPRequestHandler):
        server_version = "ehimaya-camera-bridge"
        sys_version = ""

        def log_message(self, fmt: str, *args: object) -> None:
            log.debug("%s " + fmt, self.client_address[0], *args)

        def _answer(self, code: int, body: dict[str, object]) -> None:
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            if self.path == "/health":
                self._answer(200, {"ok": True, "queued": bridge.queue.size()})
            else:
                self._answer(404, {"error": "not_found"})

        def do_POST(self) -> None:
            cam = settings.by_host.get(self.client_address[0])
            if cam is None:
                log.warning("post from %s refused: not a configured camera", self.client_address[0])
                self._answer(403, {"error": "unknown_camera"})
                return
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > MAX_BODY:
                self._answer(413 if length > MAX_BODY else 400, {"error": "body"})
                return
            body = self.rfile.read(length)
            if self.path.startswith("/hikvision"):
                alarm = parse_hikvision(body, self.headers.get("Content-Type", ""))
            elif self.path.startswith("/generic"):
                alarm = parse_generic(body)
            else:
                self._answer(404, {"error": "not_found"})
                return
            if alarm is None:
                # A heartbeat, a motion event or an alarm ending: nothing to relay.
                self._answer(200, {"alarm": False})
                return
            queued = bridge.on_alarm(cam, alarm)
            self._answer(200 if queued else 503, {"alarm": True, "queued": queued})

    return ThreadingHTTPServer((settings.listen, settings.port), Handler)
