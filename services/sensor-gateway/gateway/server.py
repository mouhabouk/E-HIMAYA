"""What the sensors call, on the local network only.

* ``POST /readings``: one reading ``{"sensor", "at", "value", "sig"}`` or ``{"readings": [...]}`` (500 at most). The
  gateway checks the shape and queues; the API checks each signature with the sensor's key, which never leaves it.
* ``GET /health``: ``{"status": "ok", "queued": n}`` for the server's supervision.

A caller outside GATEWAY_ALLOW is refused before its body is read. Nothing is logged of a reading but its sensor code.
"""

import ipaddress
import json
import logging
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from gateway.config import Settings
from gateway.queue import Queue, Reading

log = logging.getLogger("gateway")
MAX_BATCH = 500
FIELDS = {"sensor": 40, "at": 40, "value": 16, "sig": 64}
_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,39}$")


class Refused(ValueError):
    pass


def readings_of(body: Any) -> list[Reading]:
    """The readings of a request body, or Refused with the reason."""
    items = body.get("readings") if isinstance(body, dict) and "readings" in body else [body]
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_BATCH:
        raise Refused("batch_size")
    out: list[Reading] = []
    for item in items:
        if not isinstance(item, dict) or set(item) != set(FIELDS):
            raise Refused("fields")
        if any(not isinstance(item[k], str) or not 1 <= len(item[k]) <= n for k, n in FIELDS.items()):
            raise Refused("fields")
        if not _CODE.match(item["sensor"]):
            raise Refused("sensor")
        out.append({k: item[k] for k in FIELDS})
    return out


def make_server(settings: Settings, queue: Queue) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        server_version = "ehimaya-sensor-gateway"
        sys_version = ""

        def log_message(self, format: str, *args: Any) -> None:
            log.debug("http %s", format % args)

        def _send(self, code: HTTPStatus, payload: dict[str, Any]) -> None:
            data = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _local(self) -> bool:
            try:
                address = ipaddress.ip_address(self.client_address[0])
            except ValueError:
                return False
            return any(address in net for net in settings.allow)

        def do_GET(self) -> None:
            if not self._local():
                self._send(HTTPStatus.FORBIDDEN, {"error": "outside_local_network"})
            elif self.path == "/health":
                self._send(HTTPStatus.OK, {"status": "ok", "queued": queue.size()})
            else:
                self._send(HTTPStatus.NOT_FOUND, {"error": "not_found"})

        def do_POST(self) -> None:
            if not self._local():
                log.warning("refused a caller outside the local network")
                self._send(HTTPStatus.FORBIDDEN, {"error": "outside_local_network"})
                return
            if self.path != "/readings":
                self._send(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = -1
            if not 0 < length <= settings.max_body:
                self._send(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "body_size"})
                return
            try:
                readings = readings_of(json.loads(self.rfile.read(length)))
            except (ValueError, Refused) as exc:
                reason = str(exc) if isinstance(exc, Refused) else "json"
                self._send(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": reason})
                return
            if not queue.push(readings):
                log.error("queue full: the API has not taken readings for a while")
                self._send(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "queue_full"})
                return
            self._send(HTTPStatus.ACCEPTED, {"queued": len(readings)})

    return ThreadingHTTPServer((settings.bind, settings.port), Handler)
