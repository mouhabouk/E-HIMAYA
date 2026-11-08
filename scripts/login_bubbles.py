"""Sign-in background and name (Yamen, 2026-11-08): the e-Himaya emblem as translucent bubbles of every size.

Cuts the round emblem and the name out of the horizontal mark, then writes img/bubbles.svg and img/wordmark.png:

    python3 scripts/login_bubbles.py
"""

import base64
import io
from pathlib import Path

from PIL import Image

IMG = Path(__file__).resolve().parents[1] / "infra/keycloak/themes/ehimaya/login/resources/img"

# (cx, cy, radius, opacity of the emblem, float period in s, phase in s) on a 1600 x 1000 canvas.
BUBBLES = [
    (140, 170, 150, 0.22, 19, 0),
    (420, 90, 52, 0.30, 14, 2),
    (330, 420, 86, 0.20, 17, 5),
    (110, 640, 70, 0.26, 15, 1),
    (300, 850, 175, 0.18, 22, 3),
    (560, 960, 60, 0.28, 16, 6),
    (1460, 140, 120, 0.22, 18, 4),
    (1210, 70, 44, 0.32, 13, 1),
    (1300, 360, 76, 0.22, 16, 0),
    (1520, 560, 96, 0.20, 20, 2),
    (1240, 760, 190, 0.17, 23, 5),
    (1560, 930, 58, 0.28, 15, 3),
    (980, 980, 46, 0.30, 14, 2),
    (640, 40, 34, 0.34, 12, 4),
    (930, 30, 28, 0.34, 12, 0),
    (40, 430, 38, 0.30, 13, 7),
    (1080, 560, 30, 0.28, 12, 3),
    (520, 600, 26, 0.28, 12, 6),
]
FADE = 0.62  # all emblems are kept faint: a background, not a pattern

HEAD = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1000" preserveAspectRatio="xMidYMid slice">
<!-- e-Himaya sign-in background: the emblem as translucent bubbles (scripts/login_bubbles.py). -->
<style>
.b{animation:f var(--d) ease-in-out var(--l) infinite alternate}
@keyframes f{to{transform:translateY(-14px)}}
@media (prefers-reduced-motion:reduce){.b{animation:none}}
</style>
<defs>
<radialGradient id="glass" cx="50%" cy="50%" r="50%">
<stop offset="0" stop-color="#1f3fa0" stop-opacity=".10"/>
<stop offset=".78" stop-color="#1f3fa0" stop-opacity=".16"/>
<stop offset="1" stop-color="#e8cf8a" stop-opacity=".16"/>
</radialGradient>
<radialGradient id="shine" cx="35%" cy="28%" r="40%">
<stop offset="0" stop-color="#fff" stop-opacity=".28"/>
<stop offset="1" stop-color="#fff" stop-opacity="0"/>
</radialGradient>
"""


def main() -> None:
    mark = Image.open(IMG / "logo-horizontal.png").convert("RGBA")
    name = mark.crop((0, 0, 611, mark.height))
    name.crop(name.getbbox()).save(IMG / "wordmark.png", optimize=True)
    emblem = mark.crop((611, 0, mark.width, mark.height))
    emblem = emblem.crop(emblem.getbbox()).resize((240, 240), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    emblem.save(buf, "PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode()

    out = [HEAD, f'<image id="e" width="1" height="1" href="data:image/png;base64,{b64}"/>\n</defs>']
    for cx, cy, r, opacity, period, phase in BUBBLES:
        x, y, size = cx - r * 0.86, cy - r * 0.86, r * 1.72
        out.append(
            f'<g class="b" style="--d:{period}s;--l:-{phase}s">'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#glass)"/>'
            f'<use href="#e" transform="translate({x} {y}) scale({size})" opacity="{opacity * FADE:.3f}"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#shine)"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r - 0.75}" fill="none" '
            'stroke="#c9a24a" stroke-opacity=".30" stroke-width="1.5"/>'
            "</g>"
        )
    out.append("</svg>")
    (IMG / "bubbles.svg").write_text("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
