"""Media type detection from the first bytes of a file (magic numbers), for the verification worker (A7).

The type declared by the device is never trusted for serving: a file is served only with a type its bytes
confirm. Containers are matched by family, since one container carries several declared types (an ISO
BMFF file may be ``video/mp4``, ``video/quicktime``, ``video/3gpp`` or ``audio/mp4``); anything that is
not a known image, audio or video format (HTML, SVG, scripts, archives…) matches nothing.
"""

from dataclasses import dataclass

HEAD_BYTES = 64

_HEIF_BRANDS = frozenset({b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"mif1", b"msf1"})
_ISO_MEDIA = frozenset({"video/mp4", "video/quicktime", "video/3gpp", "audio/mp4"})


@dataclass(frozen=True, slots=True)
class Detected:
    # Short name of the format found, for staff and the audit log.
    format: str
    # Declared types these bytes are compatible with.
    types: frozenset[str]


def detect(head: bytes) -> Detected | None:
    """The format of a file from its first ``HEAD_BYTES`` bytes, or None when it is not a media format."""
    if head.startswith(b"\xff\xd8\xff"):
        return Detected("jpeg", frozenset({"image/jpeg"}))
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return Detected("png", frozenset({"image/png"}))
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return Detected("webp", frozenset({"image/webp"}))
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return Detected("wav", frozenset({"audio/wav", "audio/x-wav"}))
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in _HEIF_BRANDS:
            return Detected("heif", frozenset({"image/heic", "image/heif"}))
        if brand.startswith(b"avif"):
            return None
        return Detected("iso-bmff", _ISO_MEDIA)
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return Detected("webm", frozenset({"video/webm", "audio/webm"}))
    if head.startswith(b"OggS"):
        return Detected("ogg", frozenset({"audio/ogg"}))
    if head.startswith(b"ID3"):
        return Detected("mp3", frozenset({"audio/mpeg"}))
    if len(head) >= 2 and head[0] == 0xFF:
        if head[1] & 0xF6 == 0xF0:  # ADTS: sync word, layer 00
            return Detected("aac", frozenset({"audio/aac"}))
        if head[1] & 0xE0 == 0xE0 and head[1] & 0x06:  # MPEG audio frame sync, layer I-III
            return Detected("mp3", frozenset({"audio/mpeg"}))
    return None


@dataclass(frozen=True, slots=True)
class Verification:
    verified_type: str | None
    # None when the file may be served; else why it is quarantined.
    reason: str | None
    detected: str | None


def verify(declared: str | None, head: bytes) -> Verification:
    found = detect(head)
    if found is None:
        return Verification(None, "disallowed_type", None)
    if declared is None or declared not in found.types:
        return Verification(None, "type_mismatch", found.format)
    return Verification(declared, None, found.format)


EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/heif": ".heif",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/3gpp": ".3gp",
    "video/webm": ".webm",
    "audio/mp4": ".m4a",
    "audio/aac": ".aac",
    "audio/mpeg": ".mp3",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/webm": ".weba",
}
