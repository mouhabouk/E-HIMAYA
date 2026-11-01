"""The bridge's work: an alarm from a camera becomes a signed event on the disk queue; a thread relays the queue to
the API, another sends each camera's heartbeat, one per Dahua camera listens to its event stream, and after an alarm
the camera's video is sent to the system for a while so the room can watch it."""

import json
import logging
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime

from bridge import camera_http
from bridge.config import Camera, Settings
from bridge.queue import Queue
from bridge.signing import event_body, heartbeat_body
from bridge.vendors import Alarm, parse_dahua_line

log = logging.getLogger("bridge")
Post = Callable[[str, dict[str, str]], int]
# The API answered: 2xx done; 409 already received; 401 or 422 will never pass (wrong key, bad clock): logged and
# dropped. Anything else (no network, 5xx, 429) stays queued and is tried again.
FINAL = {401, 409, 422}


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def http_post(settings: Settings) -> Post:
    def post(path: str, body: dict[str, str]) -> int:
        request = urllib.request.Request(  # noqa: S310 (api_url is https, checked at load)
            settings.api_url + path,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "User-Agent": "ehimaya-camera-bridge/0.1"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=settings.timeout_s) as r:  # noqa: S310
                return int(r.status)
        except urllib.error.HTTPError as exc:
            return int(exc.code)

    return post


class Bridge:
    def __init__(
        self,
        settings: Settings,
        queue: Queue,
        post: Post | None = None,
        snapshot: Callable[[Camera], bytes | None] = camera_http.snapshot,
    ) -> None:
        self.settings = settings
        self.queue = queue
        self.post = post or http_post(settings)
        self.snapshot = snapshot
        self._stop = threading.Event()
        self._relays: dict[str, subprocess.Popen[bytes]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ alarms

    def on_alarm(self, cam: Camera, alarm: Alarm) -> bool:
        """Sign and queue the alarm (with the camera's picture), then start sending the video. False: queue full."""
        frame = alarm.frame or self.snapshot(cam)
        body = event_body(
            cam.key, cam.camera, now_iso(), alarm.label, "1", alarm.temperature, frame, alarm.vendor_event
        )
        queued = self.queue.push([body])
        log.warning(
            "alarm %s from %s (%s%s)%s",
            alarm.label,
            cam.label,
            alarm.vendor_event,
            f", {alarm.temperature} °C" if alarm.temperature else "",
            "" if queued else ": QUEUE FULL, dropped",
        )
        self.start_video(cam)
        return queued

    def start_video(self, cam: Camera) -> None:
        if not (cam.rtsp_url and cam.publish_url and self.settings.stream_after_alarm_s):
            return
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            log.warning("ffmpeg not installed: no video after the alarm of %s", cam.label)
            return
        with self._lock:
            running = self._relays.get(cam.camera)
            if running is not None and running.poll() is None:
                return
            # -c copy: the camera's H.264 as it is, no CPU load; stops by itself after stream_after_alarm_s.
            self._relays[cam.camera] = subprocess.Popen(  # noqa: S603 (fixed program, arguments from the config)
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "warning",
                    "-rtsp_transport",
                    "tcp",
                    "-i",
                    cam.rtsp_url,
                    "-t",
                    str(self.settings.stream_after_alarm_s),
                    "-an",
                    "-c:v",
                    "copy",
                    "-f",
                    "rtsp",
                    "-rtsp_transport",
                    "tcp",
                    cam.publish_url,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        log.info("video of %s sent for %d s", cam.label, self.settings.stream_after_alarm_s)

    # ------------------------------------------------------------------ relaying

    def flush_once(self) -> int:
        """Relay what waits, oldest first; stops at the first answer that means «try later». Returns how many left."""
        sent = 0
        for item_id, body in self.queue.peek(20):
            try:
                code = self.post("/api/v1/camera-events", body)
            except OSError as exc:
                log.info("API unreachable (%s), %d waiting", exc, self.queue.size())
                break
            if 200 <= code < 300 or code in FINAL:
                if code in (401, 422):
                    log.error(
                        "the system refused an alarm of %s (HTTP %d): check the key and the clock",
                        body.get("camera"),
                        code,
                    )
                self.queue.drop(item_id)
                sent += 1
                continue
            log.info("API answered %d, %d waiting", code, self.queue.size())
            break
        return sent

    def heartbeat_once(self) -> dict[str, int]:
        codes: dict[str, int] = {}
        for cam in self.settings.cameras:
            try:
                codes[cam.camera] = self.post(
                    "/api/v1/camera-events/heartbeat", heartbeat_body(cam.key, cam.camera, now_iso())
                )
            except OSError:
                codes[cam.camera] = 0
            if codes[cam.camera] == 401:
                log.error("heartbeat of %s refused: wrong camera id or key", cam.label)
        return codes

    def run_sender(self) -> None:
        while not self._stop.is_set():
            self.flush_once()
            self._stop.wait(1.0)

    def run_heartbeat(self) -> None:
        while not self._stop.is_set():
            self.heartbeat_once()
            self._stop.wait(self.settings.heartbeat_s)

    def run_dahua(self, cam: Camera) -> None:
        """Keep Dahua's event stream open; reconnect after a drop."""
        while not self._stop.is_set():
            try:
                for line in camera_http.dahua_events(cam):
                    alarm = parse_dahua_line(line)
                    if alarm is not None:
                        self.on_alarm(cam, alarm)
                    if self._stop.is_set():
                        return
            except OSError as exc:
                log.warning("event stream of %s lost: %s", cam.label, exc)
            self._stop.wait(5.0)

    def start(self) -> list[threading.Thread]:
        threads = [
            threading.Thread(target=self.run_sender, name="sender", daemon=True),
            threading.Thread(target=self.run_heartbeat, name="heartbeat", daemon=True),
        ]
        threads += [
            threading.Thread(target=self.run_dahua, args=(c,), name=f"dahua-{c.host}", daemon=True)
            for c in self.settings.cameras
            if c.vendor == "dahua"
        ]
        for t in threads:
            t.start()
        return threads

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            for p in self._relays.values():
                if p.poll() is None:
                    p.terminate()
        time.sleep(0)
