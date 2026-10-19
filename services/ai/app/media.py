"""Download a media object through the pre-signed link the API built (no storage credentials here)."""

import os
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx

from app.config import get_settings


class MediaError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@asynccontextmanager
async def downloaded(url: str, client: httpx.AsyncClient) -> AsyncIterator[str]:
    settings = get_settings()
    # Only the object store's internal address is fetched (no request forgery towards other hosts).
    if not url.startswith(settings.media_url_prefix):
        raise MediaError("media_url_not_allowed")
    fd, path = tempfile.mkstemp(prefix="ehimaya-media-")
    try:
        size = 0
        with os.fdopen(fd, "wb") as out:
            async with client.stream("GET", url, timeout=httpx.Timeout(30, read=120)) as response:
                if response.status_code != 200:
                    raise MediaError("media_fetch_failed")
                async for chunk in response.aiter_bytes(1024 * 1024):
                    size += len(chunk)
                    if size > settings.max_media_bytes:
                        raise MediaError("media_too_large")
                    out.write(chunk)
        yield path
    except httpx.HTTPError as exc:
        raise MediaError("media_fetch_failed") from exc
    finally:
        os.unlink(path)
