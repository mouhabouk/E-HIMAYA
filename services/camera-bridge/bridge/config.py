"""The bridge's settings: one JSON file (``BRIDGE_CONFIG``, default ``/etc/ehimaya-bridge/bridge.json``).

```json
{
  "api_url": "https://api.ehimaya.tn",
  "listen": "0.0.0.0", "port": 8099,
  "queue": "/var/lib/ehimaya-bridge/queue.sqlite3",
  "cameras": [
    {"camera": "<id from the dashboard>", "key": "<64 hex, shown once>", "vendor": "hikvision",
     "host": "192.168.1.64", "user": "bridge", "password": "...", "snapshot_channel": "201",
     "rtsp_url": "rtsp://bridge:...@192.168.1.64:554/Streaming/Channels/201",
     "publish_url": "rtsp://media.ehimaya.tn:8554/<path>?token=<publish token>"}
  ]
}
```

The camera keys and passwords stay on this computer (file mode 600); the system never learns the passwords.
"""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

VENDORS = ("hikvision", "dahua", "generic")
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_KEY = re.compile(r"^[0-9a-f]{64}$")


class ConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Camera:
    camera: str
    key: str
    vendor: str
    host: str
    user: str = ""
    password: str = ""
    port: int = 80
    snapshot_channel: str = "1"
    rtsp_url: str = ""
    publish_url: str = ""

    @property
    def label(self) -> str:
        return f"{self.vendor}@{self.host}"


@dataclass(frozen=True, slots=True)
class Settings:
    api_url: str
    cameras: tuple[Camera, ...]
    listen: str = "0.0.0.0"  # noqa: S104 (the institution's network; see the guide's firewall step)
    port: int = 8099
    queue: Path = Path("/var/lib/ehimaya-bridge/queue.sqlite3")
    queue_max: int = 5000
    heartbeat_s: int = 300
    # Video sent to the system after an alarm, so the room can watch: this many seconds (0: never).
    stream_after_alarm_s: int = 600
    timeout_s: float = 15.0
    by_host: dict[str, Camera] = field(default_factory=dict)

    @staticmethod
    def load(path: Path | None = None) -> "Settings":
        path = path or Path(os.environ.get("BRIDGE_CONFIG", "/etc/ehimaya-bridge/bridge.json"))
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ConfigError(f"cannot read {path}: {exc}") from None
        return Settings.parse(raw)

    @staticmethod
    def parse(raw: object) -> "Settings":
        if not isinstance(raw, dict):
            raise ConfigError("the file must hold a JSON object")
        api = str(raw.get("api_url", "")).rstrip("/")
        parsed = urlparse(api)
        if parsed.scheme not in ("https", "http") or not parsed.netloc:
            raise ConfigError("api_url: https://… expected")
        cameras = []
        for i, c in enumerate(raw.get("cameras") or []):
            if not isinstance(c, dict):
                raise ConfigError(f"cameras[{i}]: object expected")
            cam = Camera(
                camera=str(c.get("camera", "")).lower(),
                key=str(c.get("key", "")).lower(),
                vendor=str(c.get("vendor", "")),
                host=str(c.get("host", "")),
                user=str(c.get("user", "")),
                password=str(c.get("password", "")),
                port=int(c.get("port", 80)),
                snapshot_channel=str(c.get("snapshot_channel", "1")),
                rtsp_url=str(c.get("rtsp_url", "")),
                publish_url=str(c.get("publish_url", "")),
            )
            if not _UUID.match(cam.camera):
                raise ConfigError(f"cameras[{i}].camera: the camera id shown in the dashboard")
            if not _KEY.match(cam.key):
                raise ConfigError(f"cameras[{i}].key: 64 hexadecimal characters")
            if cam.vendor not in VENDORS:
                raise ConfigError(f"cameras[{i}].vendor: one of {', '.join(VENDORS)}")
            if not cam.host:
                raise ConfigError(f"cameras[{i}].host: the camera's address on the local network")
            if cam.publish_url and "token=" not in cam.publish_url:
                raise ConfigError(f"cameras[{i}].publish_url: must carry ?token=")
            cameras.append(cam)
        if not cameras:
            raise ConfigError("cameras: at least one camera")
        hosts = [c.host for c in cameras]
        if len(set(hosts)) != len(hosts):
            raise ConfigError("cameras: one entry per camera address")
        return Settings(
            api_url=api,
            cameras=tuple(cameras),
            listen=str(raw.get("listen", "0.0.0.0")),  # noqa: S104
            port=int(raw.get("port", 8099)),
            queue=Path(str(raw.get("queue", "/var/lib/ehimaya-bridge/queue.sqlite3"))),
            queue_max=int(raw.get("queue_max", 5000)),
            heartbeat_s=max(30, int(raw.get("heartbeat_s", 300))),
            stream_after_alarm_s=max(0, int(raw.get("stream_after_alarm_s", 600))),
            timeout_s=float(raw.get("timeout_s", 15.0)),
            by_host={c.host: c for c in cameras},
        )
