"""The signatures the API checks (``app.modules.streams.camera_events``): HMAC-SHA256 in lower-case hex over the
strings as sent, joined by ``|``."""

import hashlib
import hmac


def sign(key: str, *parts: str) -> str:
    return hmac.new(bytes.fromhex(key), "|".join(parts).encode(), hashlib.sha256).hexdigest()


def event_body(
    key: str,
    camera: str,
    at: str,
    label: str,
    confidence: str,
    temperature: str,
    frame: bytes | None,
    vendor_event: str | None,
) -> dict[str, str]:
    import base64

    sha = hashlib.sha256(frame).hexdigest() if frame else ""
    body = {
        "camera": camera,
        "at": at,
        "label": label,
        "confidence": confidence,
        "temperature": temperature,
        "sig": sign(key, camera, at, label, confidence, temperature, sha),
    }
    if vendor_event:
        body["vendor_event"] = vendor_event
    if frame:
        body["frame_jpeg_b64"] = base64.b64encode(frame).decode()
    return body


def heartbeat_body(key: str, camera: str, at: str) -> dict[str, str]:
    return {"camera": camera, "at": at, "sig": sign(key, camera, at, "heartbeat")}
