"""Sign-in background and name (Yamen, 2026-11-08): the e-Himaya emblem as translucent bubbles of every size.

Cuts the round emblem and the name out of the horizontal mark, then writes img/wordmark.png, img/bubbles.svg (royal
blue) and img/bubbles-red.svg (royal red, Yamen's second colour; loaded only when a visitor picks it):

    python3 scripts/login_bubbles.py
"""

import base64
import io
from pathlib import Path

from PIL import Image

IMG = (
    Path(__file__).resolve().parents[1]
    / "infra/keycloak/themes/ehimaya/login/resources/img"
)

# (cx, cy, radius, opacity of the emblem, float period in s, phase in s) on a 1600 x 1000 canvas.
BUBBLES = [
    # Left side, mirrored on the right: a few bubbles framing the card, none under it.
    (170, 200, 132, 0.20, 21, 0),
    (380, 640, 64, 0.26, 16, 4),
    (120, 870, 92, 0.22, 19, 2),
    (480, 120, 34, 0.30, 13, 6),
    (1430, 800, 140, 0.20, 22, 3),
    (1225, 360, 68, 0.26, 17, 1),
    (1490, 160, 88, 0.22, 18, 5),
    (1120, 905, 36, 0.30, 14, 2),
    (800, 960, 26, 0.30, 12, 7),
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
<stop offset="0" stop-color="GLASS" stop-opacity=".10"/>
<stop offset=".78" stop-color="GLASS" stop-opacity=".16"/>
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
    name = name.crop(name.getbbox())
    # The name and E-HIMAYA only: the line under them is set as text by the theme, in the page's language.
    name = name.crop((0, 0, name.width, 206))
    solid = name.getchannel("A").point(
        lambda a: 255 if a > 60 else 0
    )  # faint glow pixels do not count
    name.crop(solid.getbbox()).save(IMG / "wordmark.png", optimize=True)
    emblem = mark.crop((611, 0, mark.width, mark.height))
    emblem = emblem.crop(emblem.getbbox()).resize((240, 240), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    emblem.save(buf, "PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode()

    for file, glass in (("bubbles.svg", "#1f3fa0"), ("bubbles-red.svg", "#a3182c")):
        write(file, glass, b64)


def write(file: str, glass: str, b64: str) -> None:
    out = [
        HEAD.replace("GLASS", glass),
        f'<image id="e" width="1" height="1" href="data:image/png;base64,{b64}"/>\n</defs>',
    ]
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
    (IMG / file).write_text("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
