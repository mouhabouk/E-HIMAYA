"""Image decoding (uploads) and encoding (frames attached to the callbacks)."""

import base64
import io
import warnings

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageOps

# Content types accepted by POST /v1/detect and the magic bytes each must start with.
SIGNATURES: dict[str, tuple[bytes, ...]] = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/webp": (b"RIFF",),
}
PIL_FORMATS = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}


class ImageRejected(Exception):
    """The upload is not an acceptable image; the message is a stable error code."""


def sniff(payload: bytes) -> str | None:
    """Content type from the magic bytes, or None."""
    for content_type, prefixes in SIGNATURES.items():
        if any(payload.startswith(prefix) for prefix in prefixes):
            if content_type == "image/webp" and payload[8:12] != b"WEBP":
                continue
            return content_type
    return None


def decode(payload: bytes, declared: str | None, max_pixels: int) -> NDArray[np.uint8]:
    """Bytes → RGB array, after checking the magic bytes match the declared type and the size is bounded."""
    actual = sniff(payload)
    if actual is None:
        raise ImageRejected("unsupported_media_type")
    if declared and declared.split(";")[0].strip().lower() not in (actual, "application/octet-stream"):
        raise ImageRejected("content_type_mismatch")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(payload), formats=[PIL_FORMATS[actual]]) as image:
                width, height = image.size
                if width * height > max_pixels:
                    raise ImageRejected("image_too_large")
                if width < 16 or height < 16:
                    raise ImageRejected("image_too_small")
                image.draft("RGB", (4096, 4096))  # JPEG: decode at a reduced scale when very large
                rgb = ImageOps.exif_transpose(image).convert("RGB")
                return np.asarray(rgb, dtype=np.uint8)
    except ImageRejected:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ImageRejected("image_too_large") from exc
    except Exception as exc:  # truncated or corrupted file
        raise ImageRejected("image_undecodable") from exc


def jpeg_b64(frame: NDArray[np.uint8], max_side: int, quality: int) -> str:
    """Downscaled JPEG of a frame, base64 (``frame_jpeg_b64`` of the callback)."""
    image = Image.fromarray(frame)
    image.thumbnail((max_side, max_side), Image.Resampling.BILINEAR)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True)
    return base64.b64encode(buffer.getvalue()).decode("ascii")
