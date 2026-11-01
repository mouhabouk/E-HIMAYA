"""Getting the app from a QR code (Yamen, 2026-11-01): the committee members scan, the phone opens the download.

``/api/v1/app/download`` is the one stable address printed in every QR code (documents' footers, slides, posters):
it sends the phone to ``APP_DOWNLOAD_URL`` (the store page or the Office's own hosting of the APK), so the place of
the files can change without reprinting anything. ``/api/v1/app/qr.svg`` and ``qr.png`` draw that address.
"""

from typing import Annotated, Literal

import segno
from fastapi import APIRouter, Query, Response
from fastapi.responses import RedirectResponse

from app.core.config import get_settings

router = APIRouter(prefix="/api/v1/app", tags=["app"])


def download_address() -> str:
    """What the QR codes carry: the API's stable download address."""
    return f"{get_settings().api_public_url.rstrip('/')}/api/v1/app/download"


@router.get("/download", response_class=RedirectResponse, status_code=307)
async def download() -> RedirectResponse:
    return RedirectResponse(get_settings().app_download_url, status_code=307)


@router.get("/qr.{fmt}", response_class=Response, responses={200: {"content": {"image/svg+xml": {}, "image/png": {}}}})
async def qr(fmt: Literal["svg", "png"], scale: Annotated[int, Query(ge=2, le=40)] = 10) -> Response:
    import io

    code = segno.make(download_address(), error="m")
    out = io.BytesIO()
    code.save(out, kind=fmt, scale=scale, border=2)
    media = "image/svg+xml" if fmt == "svg" else "image/png"
    return Response(out.getvalue(), media_type=media, headers={"Cache-Control": "public, max-age=3600"})
