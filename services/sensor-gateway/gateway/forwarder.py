"""Relays what is queued to the API and drops it once taken.

* Readings, in batches, to ``POST /internal/sensors/readings``; the API answers per reading (accepted, or refused with
  a reason).
* Tower events, one at a time (each carries a frame), to ``POST /internal/towers/events``; the API answers whether
  it accepted the event or why not.

Something refused is not sent again. While the API is unreachable or refuses the gateway (401, 403, 404, 5xx),
everything stays queued and the gateway waits longer between tries, up to a minute.
"""

import json
import logging
import threading
import urllib.error
import urllib.request
from typing import Any

from gateway.config import Settings
from gateway.queue import Queue

log = logging.getLogger("gateway")
MAX_WAIT_S = 60.0
EVENTS_PER_ROUND = 10


class Forwarder:
    def __init__(self, settings: Settings, queue: Queue, events: Queue | None = None) -> None:
        self._settings = settings
        self._queue = queue
        self._events = events
        self._stop = threading.Event()
        self._wait = settings.flush_every_s

    def _post(self, path: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        request = urllib.request.Request(  # noqa: S310 (GATEWAY_API_URL is checked to be http or https)
            f"{self._settings.api_url}{path}",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "X-Gateway-Token": self._settings.token},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._settings.timeout_s) as response:  # noqa: S310
                return int(response.status), json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as exc:
            return int(exc.code), {}

    def send(self, readings: list[dict[str, str]]) -> tuple[int, dict[str, Any]]:
        return self._post("/internal/sensors/readings", {"readings": readings})

    def flush_once(self) -> bool:
        """Relay one batch of readings, then some events; True when the API took them (or nothing was waiting)."""
        return self._flush_readings() and self._flush_events()

    def _flush_readings(self) -> bool:
        rows = self._queue.peek(self._settings.batch)
        if not rows:
            return True
        try:
            code, body = self.send([r for _, r in rows])
        except (OSError, ValueError) as exc:
            log.warning("API unreachable (%s); %d readings kept", type(exc).__name__, len(rows))
            return False
        if code == 422:
            # Malformed for the API (should not happen after the gateway's own check): not retried forever.
            log.error("API refused a batch as malformed; %d readings dropped", len(rows))
            self._queue.drop(rows[-1][0])
            return True
        if code != 200:
            log.warning("API answered %d; %d readings kept", code, len(rows))
            return False
        self._queue.drop(rows[-1][0])
        if body.get("rejected"):
            log.warning("API refused readings: %s", body["rejected"])
        return True

    def _flush_events(self) -> bool:
        if self._events is None:
            return True
        for row_id, event in self._events.peek(EVENTS_PER_ROUND):
            try:
                code, body = self._post("/internal/towers/events", event)
            except (OSError, ValueError) as exc:
                log.warning("API unreachable (%s); tower events kept", type(exc).__name__)
                return False
            if code not in (200, 422):
                log.warning("API answered %d; tower events kept", code)
                return False
            self._events.drop(row_id)
            if code == 422 or not body.get("accepted"):
                log.warning("API refused an event of tower %s: %s", event.get("tower"), body.get("reason", code))
        return True

    def run(self) -> None:
        while not self._stop.is_set():
            ok = self.flush_once()
            self._wait = self._settings.flush_every_s if ok else min(self._wait * 2, MAX_WAIT_S)
            self._stop.wait(self._wait)

    def stop(self) -> None:
        self._stop.set()
