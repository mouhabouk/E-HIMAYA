"""Talking to a camera on the local network: its picture and Dahua's event stream (digest or basic authentication,
standard library only)."""

import logging
import urllib.request
from collections.abc import Iterator

from bridge.config import Camera

log = logging.getLogger("bridge")
SNAPSHOT_MAX = 2 * 1024 * 1024


def opener(cam: Camera) -> urllib.request.OpenerDirector:
    passwords = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    passwords.add_password(None, f"http://{cam.host}:{cam.port}/", cam.user, cam.password)
    return urllib.request.build_opener(
        urllib.request.HTTPDigestAuthHandler(passwords), urllib.request.HTTPBasicAuthHandler(passwords)
    )


def snapshot_url(cam: Camera) -> str | None:
    base = f"http://{cam.host}:{cam.port}"
    if cam.vendor == "hikvision":
        return f"{base}/ISAPI/Streaming/channels/{cam.snapshot_channel}/picture"
    if cam.vendor == "dahua":
        return f"{base}/cgi-bin/snapshot.cgi?channel={cam.snapshot_channel}"
    return None


def snapshot(cam: Camera, timeout_s: float = 5.0) -> bytes | None:
    """The camera's picture now (JPEG), or None: the alarm goes without it rather than late."""
    url = snapshot_url(cam)
    if url is None:
        return None
    try:
        with opener(cam).open(url, timeout=timeout_s) as r:
            data: bytes = r.read(SNAPSHOT_MAX + 1)
    except OSError as exc:
        log.warning("snapshot of %s failed: %s", cam.label, exc)
        return None
    return data if data.startswith(b"\xff\xd8\xff") and len(data) <= SNAPSHOT_MAX else None


def dahua_events(cam: Camera, timeout_s: float = 90.0) -> Iterator[str]:
    """The lines of Dahua's event stream, until the connection drops (the caller reconnects)."""
    codes = "[FireWarning,HeatImagingTemper,SmokeDetection]"
    url = f"http://{cam.host}:{cam.port}/cgi-bin/eventManager.cgi?action=attach&codes={codes}&heartbeat=30"
    with opener(cam).open(url, timeout=timeout_s) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if line.startswith("Code="):
                yield line
