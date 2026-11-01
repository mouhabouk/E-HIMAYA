"""What each kind of camera sends when it detects a fire, read into one shape (``Alarm``).

* **Hikvision** (thermal DS-2TD…, bi-spectrum): «Alarm Server / HTTP Listening» posts an ``EventNotificationAlert``,
  as XML, JSON, or multipart with the XML and a picture. Fire: ``fireDetection``, ``TMA`` (temperature measurement
  alarm), ``smokeAndFireDetection``; smoke: ``smokeDetection``. Only ``eventState`` active counts.
* **Dahua** (thermal TPC-…): the bridge keeps ``/cgi-bin/eventManager.cgi?action=attach`` open; a line
  ``Code=FireWarning;action=Start;…`` is a fire, ``HeatImagingTemper`` a temperature alarm, ``SmokeDetection`` smoke.
* **Generic**: any device or controller (a fire panel's relay through an ESP32, a camera of another make) posts JSON
  ``{"label": "fire"|"smoke", "temperature": "87.5"}`` to ``/generic``.
"""

import json
import re
from dataclasses import dataclass

HIK_LABELS = {
    "fireDetection": "fire",
    "TMA": "fire",
    "smokeAndFireDetection": "fire",
    "smokeDetection": "smoke",
}
DAHUA_LABELS = {"FireWarning": "fire", "HeatImagingTemper": "fire", "SmokeDetection": "smoke"}
_TAG = r"<{0}>\s*([^<]*?)\s*</{0}>"
_TEMP = re.compile(r"<(?:currTemperature|maxTemperature|highestTemperature|alarmTemperature)>\s*(-?\d{1,4}(?:\.\d+)?)")
_JSON_TEMP = re.compile(r'"(?:Temperature|currTemperature|maxTemperature|temperature)"\s*:\s*"?(-?\d{1,4}(?:\.\d+)?)')
_NUMBER = re.compile(r"^-?\d{1,4}(\.\d{1,4})?$")


@dataclass(frozen=True, slots=True)
class Alarm:
    label: str
    vendor_event: str
    temperature: str = ""
    address: str = ""
    frame: bytes | None = None


def _tag(text: str, name: str) -> str:
    m = re.search(_TAG.format(name), text)
    return m.group(1) if m else ""


def _temperature(raw: str) -> str:
    raw = raw.strip()
    if not _NUMBER.match(raw):
        try:
            raw = f"{float(raw):.1f}"
        except ValueError:
            return ""
        if not _NUMBER.match(raw):
            return ""
    return raw


def _parts(body: bytes, content_type: str) -> tuple[str, bytes | None]:
    """The text of the event and the picture, if the camera sent one (multipart)."""
    m = re.search(r"boundary=\"?([^\";]+)\"?", content_type)
    if not m:
        return body.decode("utf-8", "replace"), None
    text, frame = "", None
    for part in body.split(b"--" + m.group(1).encode()):
        _head, _, payload = part.partition(b"\r\n\r\n")
        payload = payload.rstrip(b"\r\n-")
        if payload.startswith(b"\xff\xd8\xff"):
            frame = frame or payload
        elif b"EventNotificationAlert" in payload or payload.lstrip().startswith(b"{"):
            text = payload.decode("utf-8", "replace")
    return text, frame


def parse_hikvision(body: bytes, content_type: str = "") -> Alarm | None:
    text, frame = _parts(body, content_type)
    if text.lstrip().startswith("{"):
        try:
            data = json.loads(text)
        except ValueError:
            return None
        event = str(data.get("eventType", ""))
        state = str(data.get("eventState", "active"))
        address = str(data.get("ipAddress", ""))
        m = _JSON_TEMP.search(text)
        temperature = m.group(1) if m else ""
    else:
        event, state, address = _tag(text, "eventType"), _tag(text, "eventState") or "active", _tag(text, "ipAddress")
        m = _TEMP.search(text)
        temperature = m.group(1) if m else ""
    label = HIK_LABELS.get(event)
    if label is None or state.lower() != "active":
        return None
    return Alarm(label, event, _temperature(temperature), address, frame)


def parse_dahua_line(line: str) -> Alarm | None:
    fields = dict(p.split("=", 1) for p in line.strip().split(";") if "=" in p)
    code, action = fields.get("Code", ""), fields.get("action", "")
    label = DAHUA_LABELS.get(code)
    if label is None or action != "Start":
        return None
    m = _JSON_TEMP.search(fields.get("data", ""))
    return Alarm(label, code, _temperature(m.group(1)) if m else "")


def parse_generic(body: bytes) -> Alarm | None:
    try:
        data = json.loads(body)
    except ValueError:
        return None
    if not isinstance(data, dict) or data.get("label") not in ("fire", "smoke"):
        return None
    return Alarm(str(data["label"]), "generic", _temperature(str(data.get("temperature", ""))))
