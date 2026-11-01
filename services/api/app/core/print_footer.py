"""The footer of every printed document: who issued it, what it is, and a medium QR code (Yamen, 2026-11-01).

The QR code sits at the bottom of each page, about 2 cm wide, beside two or three lines of text. It carries the
document's reference (a mission number, a plan version, a bulletin date) or a link (the app download page, the
public check of a certificate), so a printed page can be traced back or opened on a phone.

Use: put ``CSS`` in the page's style and ``html(lines, payload)`` first in its body; the page's ``@page`` rule sets
``@bottom-center { content: element(footer); }`` and a bottom margin of at least 30 mm.
"""

import html as _html
import re

import segno

CSS = """
.print-footer { position: running(footer); width: 100%; border-top: 1px solid #9e9e9e; padding-top: 2mm;
  font-size: 7.5pt; color: #555; }
.print-footer table { width: 100%; border-collapse: collapse; border: 0; }
.print-footer td { border: 0; padding: 0; vertical-align: middle; background: none; }
.print-footer td.qr { width: 24mm; text-align: left; }
.print-footer img { width: 22mm; height: 22mm; }
.print-footer .page:after { content: counter(page) " / " counter(pages); }
"""

PAGE_RULE = "@bottom-center { content: element(footer); width: 100%; }"


def qr_uri(payload: str) -> str:
    return str(segno.make(payload, error="m").svg_data_uri(scale=4, border=1))


def html(lines: list[str], payload: str) -> str:
    """The running footer: the lines (escaped here), the page number and the QR code of the payload."""
    text = "<br>".join(_html.escape(line) for line in lines)
    return (
        f'<div class="print-footer"><table><tr><td>{text}<br><span class="page"></span></td>'
        f'<td class="qr"><img src="{qr_uri(payload)}" alt="QR"></td></tr></table></div>'
    )


APP_CAPTION = "امسح الرمز لتنزيل تطبيق ء-حماية"


def apply(page: str, lines: list[str], payload: str | None = None) -> str:
    """Adds the footer to a finished page: its style, a bottom margin wide enough, and the footer itself. Without a
    payload the QR code opens the app download (the committee members scan it from any printed page)."""
    if payload is None:
        from app.modules.appdownload.router import download_address

        payload = download_address()
        lines = [*lines, APP_CAPTION]
    style = f"{CSS}\n@page {{ margin-bottom: 32mm; {PAGE_RULE} }}"
    page = page.replace("</style>", style + "</style>", 1)
    return re.sub(r"(<body[^>]*>)", lambda m: m.group(1) + html(lines, payload), page, count=1)
