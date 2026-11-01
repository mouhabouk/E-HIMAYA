"""The app's QR code (Yamen, 2026-11-01): one stable address that sends the phone to the download, drawn as SVG or
PNG, and printed with a caption in the footer of every printed document."""

import httpx
import pytest

from app.core import print_footer
from app.core.config import get_settings


async def test_download_redirects_and_qr_is_drawn(client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        get_settings(), "app_download_url", "https://play.google.com/store/apps/details?id=tn.ehimaya.app"
    )
    r = await client.get("/api/v1/app/download", follow_redirects=False)
    assert r.status_code == 307 and r.headers["location"].startswith("https://play.google.com/")
    svg = await client.get("/api/v1/app/qr.svg")
    assert svg.status_code == 200 and svg.headers["content-type"].startswith("image/svg+xml") and b"<svg" in svg.content
    png = await client.get("/api/v1/app/qr.png", params={"scale": 12})
    assert png.status_code == 200 and png.content.startswith(b"\x89PNG")
    assert (await client.get("/api/v1/app/qr.gif")).status_code == 422


def test_footer_is_added_to_a_printed_page() -> None:
    page = '<!doctype html><html><head><style>p{}</style></head><body class="x"><p>نص</p></body></html>'
    out = print_footer.apply(page, ["منصة ء-حماية", "وثيقة"])
    assert out.index('class="print-footer"') > out.index('<body class="x">')
    assert print_footer.APP_CAPTION in out and "position: running(footer)" in out and "margin-bottom: 32mm" in out
    assert "data:image/svg+xml" in out
    # With a payload of its own (a mission number), the caption of the app is not added.
    own = print_footer.apply(page, ["أمر مهمة"], "e-Himaya|أمر مهمة|1")
    assert print_footer.APP_CAPTION not in own
