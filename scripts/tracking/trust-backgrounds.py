"""The animated backgrounds of the committee presentation (Yamen, 2026-11-14), in a sober line style.

    python3 scripts/tracking/trust-backgrounds.py <out-dir>

trust-network-{night,day}.gif, for the cover: Tunisia drawn by its own points (schools and delegation seats from
data/osm), twinkling, with a wave of light leaving the national room and crossing the country, the Civil Protection units in gold, and the 24 governorate seats joined to the national room in Tunis, a
pulse running along every link: one national system, from the report to the decision.
trust-ring-{night,day}.gif, for the closing slide: the emblem in thin gold circles, and round it a ring of citizens and
Civil Protection agents hand in hand, drawn as line art and turning slowly: the trust between them.
grid-{night,day}.gif, behind every other slide: the slide grid itself, a band of light sweeping across it.
Every loop is seamless; colours are the deck kit's. PowerPoint plays the GIFs in the slide show.
"""
import json
import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOGO = Image.open(HERE / 'assets' / 'civil-protection-logo.png').convert('RGBA')
W, H, SS = 1280, 720, 2          # frame size, supersampling
FRAMES, MS = 48, 80              # a loop of 3.84 s
PAL = {
    'night': dict(bg='08102A', ink='E8ECF5', gold='C9A24A', red='FF6B6B', dot='8FA8FF', disc='0E1426', grid='16224A', shade='050A1C', glow='3A4F94'),
    'day': dict(bg='F6F8FC', ink='1F3FA0', gold='9C7A22', red='D7141A', dot='1F3FA0', disc='FFFFFF', grid='E3E9F4', shade='DCE3F1', glow='A9B9E0'),
}
CELL = 40 * W / 1920             # the deck kit's grid: 40 px cells on a 1920 px slide
# the 24 governorate seats (lon, lat); Tunis first, the national room
SEATS = [(10.18, 36.80), (10.19, 36.86), (10.23, 36.75), (10.10, 36.81), (10.74, 36.45), (10.14, 36.40), (9.87, 37.27),
         (9.18, 36.73), (8.78, 36.50), (8.71, 36.17), (9.37, 36.08), (10.64, 35.83), (10.83, 35.77), (11.06, 35.50),
         (10.76, 34.74), (10.10, 35.68), (8.84, 35.17), (9.48, 35.04), (10.10, 33.88), (10.50, 33.35), (10.45, 32.93),
         (8.78, 34.42), (8.13, 33.92), (8.97, 33.70)]


def rgb(h, a=255):
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


def points(layer):
    d = json.loads((ROOT / 'data' / 'osm' / 'layers' / f'{layer}_enriched.geojson').read_text(encoding='utf-8'))
    return [f['geometry']['coordinates'][:2] for f in d['features'] if f['geometry']['type'] == 'Point']


def project(cx, top, h):
    """lon/lat to frame pixels: the country h pixels tall, centred on cx, its north at top."""
    k = h / (37.6 - 30.2)
    mid = 9.55
    return lambda lon, lat: ((cx + (lon - mid) * k * math.cos(math.radians(34))) * SS, (top + (37.6 - lat) * k) * SS)


def ease(u):
    return u * u * (3 - 2 * u)


def network(mode, out):
    c = PAL[mode]
    pj = project(W / 2, 20, 680)
    land = [pj(*p) for p in points('schools') + points('delegation_hq')]
    units = [pj(*p) for p in points('civil_protection')]
    seats = [pj(*p) for p in SEATS]
    hub = seats[0]
    r = random.Random(3)
    starts = [r.random() for _ in seats]
    land = [((x, y), math.hypot(x - hub[0], y - hub[1]), r.random()) for x, y in land]
    reach = max(dist for _, dist, _ in land)
    base = ground(c)
    lay = Image.new('RGBA', base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for x, y in seats[1:]:
        d.line([(x, y), hub], fill=rgb(c['gold'], 60), width=SS)
    for x, y in units:
        d.ellipse([x - 3.5 * SS, y - 3.5 * SS, x + 3.5 * SS, y + 3.5 * SS], outline=rgb(c['gold'], 120), width=SS)
    base.alpha_composite(lay)
    frames = []
    for f in range(FRAMES):
        t = f / FRAMES
        img = base.copy()
        lay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        front = t * reach * 1.25              # a wave of light leaves the national room and crosses the country
        for (x, y), dist, tw in land:
            glow = math.exp(-((dist - front) / (34 * SS)) ** 2)
            a = int(55 + 30 * math.sin(2 * math.pi * (t * 2 + tw)) + 170 * glow)
            rr = 3 + 3 * glow
            d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=rgb(c['dot'] if glow < 0.5 else c['gold'], a))
        for i, (x, y) in enumerate(seats[1:], 1):
            u = (t + starts[i]) % 1.0           # a report travels from the seat to the room, once a loop
            e = ease(u)
            px, py = x + (hub[0] - x) * e, y + (hub[1] - y) * e
            a = int(230 * math.sin(math.pi * u))
            d.ellipse([px - 3 * SS, py - 3 * SS, px + 3 * SS, py + 3 * SS], fill=rgb(c['gold'], a))
            d.ellipse([x - 4 * SS, y - 4 * SS, x + 4 * SS, y + 4 * SS], fill=rgb(c['gold'], 200))
        pulse = (math.sin(2 * math.pi * t) + 1) / 2
        for k in range(2):                     # the national room breathes: two rings, half a loop apart
            ph = (t + k / 2) % 1.0
            rr = (8 + 34 * ph) * SS
            d.ellipse([hub[0] - rr, hub[1] - rr, hub[0] + rr, hub[1] + rr], outline=rgb(c['gold'], int(170 * (1 - ph))), width=SS)
        rr = (6 + 1.5 * pulse) * SS
        d.ellipse([hub[0] - rr, hub[1] - rr, hub[0] + rr, hub[1] + rr], fill=rgb(c['gold']))
        img.alpha_composite(lay)
        frames.append(img.resize((W, H), Image.LANCZOS).convert('RGB'))
    save(frames, out)


def figure(d, x, y, s, col, w, helmet):
    """One standing person in line art, feet at (x, y), about 3.1 s tall."""
    d.ellipse([x - 0.4 * s, y - 3.1 * s, x + 0.4 * s, y - 2.3 * s], outline=col, width=w)
    d.line([(x, y - 2.25 * s), (x, y - 0.95 * s)], fill=col, width=w)
    d.line([(x, y - 0.95 * s), (x - 0.45 * s, y)], fill=col, width=w)
    d.line([(x, y - 0.95 * s), (x + 0.45 * s, y)], fill=col, width=w)
    if helmet:
        d.arc([x - 0.52 * s, y - 3.22 * s, x + 0.52 * s, y - 2.5 * s], 180, 360, fill=helmet, width=w + SS)


def ring(mode, out):
    c = PAL[mode]
    cx, cy, n, rx, ry, ey = W * SS / 2, 300 * SS, 14, 300 * SS, 64 * SS, 150 * SS
    under = ground(c)
    frames = []
    for f in range(FRAMES):
        t = f / FRAMES
        img = under.copy()
        lay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], outline=rgb(c['gold'], 70), width=SS)  # the ground of the ring
        pts = []
        for i in range(n):
            a = 2 * math.pi * (i + t) / n      # one place per loop: seamless
            dep = math.sin(a)                  # -1 at the back, +1 at the front
            sc = (0.72 + 0.28 * (dep + 1) / 2) * 26 * SS
            pts.append((cx + rx * math.cos(a), cy + ry * dep, sc, dep, i % 2 == 0))

        def hands(p, q, alpha):
            d.line([(p[0], p[1] - 1.75 * p[2]), (q[0], q[1] - 1.75 * q[2])], fill=rgb(c['gold'], alpha), width=SS * 2)

        def people(ids, alpha):
            for i in ids:
                x, y, s, dep, citizen = pts[i]
                al = int(alpha * (0.55 + 0.45 * (dep + 1) / 2))
                if citizen:
                    figure(d, x, y, s, rgb(c['ink'], al), SS * 2, None)
                else:
                    figure(d, x, y, s, rgb(c['red'], al), SS * 2, rgb(c['gold'], al))

        back = [i for i in range(n) if pts[i][3] < 0]
        front = [i for i in range(n) if pts[i][3] >= 0]
        for i in range(n):
            j = (i + 1) % n
            if pts[i][3] < 0 and pts[j][3] < 0:
                hands(pts[i], pts[j], 110)
        people(back, 255)
        img.alpha_composite(lay)
        # the emblem in thin gold circles, one ring breathing out of it
        lay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        r = 88 * SS
        d.ellipse([cx - r, ey - r, cx + r, ey + r], fill=rgb(c['disc']), outline=rgb(c['gold']), width=2 * SS)
        r2 = 100 * SS
        d.ellipse([cx - r2, ey - r2, cx + r2, ey + r2], outline=rgb(c['gold'], 110), width=SS)
        rr = (100 + 40 * t) * SS
        d.ellipse([cx - rr, ey - rr, cx + rr, ey + rr], outline=rgb(c['gold'], int(120 * (1 - t))), width=SS)
        img.alpha_composite(lay)
        s = int(140 * SS)
        img.alpha_composite(LOGO.resize((s, s), Image.LANCZOS), (int(cx - s / 2), int(ey - s / 2)))
        lay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        for i in range(n):
            j = (i + 1) % n
            if not (pts[i][3] < 0 and pts[j][3] < 0):
                hands(pts[i], pts[j], 220)
        people(front, 255)
        img.alpha_composite(lay)
        frames.append(img.resize((W, H), Image.LANCZOS).convert('RGB'))
    save(frames, out)


def hexa(h):
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=float)


def grid_mask():
    """1 on the lines of the slide grid, 0 between them; and 1 on the crossings."""
    x, y = np.arange(W)[None, :], np.arange(H)[:, None]
    lx = (np.abs(((x + 0.5) % CELL) - CELL + 0.5) < 1.0) | ((x + 0.5) % CELL < 0.5)
    ly = (np.abs(((y + 0.5) % CELL) - CELL + 0.5) < 1.0) | ((y + 0.5) % CELL < 0.5)
    lines = (lx | ly).astype(float)
    cx, cy = np.minimum(x % CELL, CELL - x % CELL), np.minimum(y % CELL, CELL - y % CELL)
    cross = np.clip(1 - np.hypot(cx, cy) / 2.6, 0, 1)
    return np.broadcast_to(lines, (H, W)), cross


def ground_array(c):
    """The deck kit's ground: the colour, the grid and the vignette, as a float H×W×3 array."""
    lines, _ = grid_mask()
    img = hexa(c['bg'])[None, None, :] * (1 - lines[..., None]) + hexa(c['grid'])[None, None, :] * lines[..., None]
    x, y = np.arange(W)[None, :] / W - 0.5, np.arange(H)[:, None] / H - 0.4
    v = (np.clip(np.hypot(x, y) / 0.75, 0, 1) * 0.85)[..., None]   # the SVG's radial gradient, r = 75 % of each side
    return img * (1 - v) + hexa(c['shade'])[None, None, :] * v


def ground(c):
    """The same ground as a supersampled RGBA image, under the cover and closing GIFs."""
    a = ground_array(c)
    return Image.fromarray(a.clip(0, 255).astype('uint8'), 'RGB').resize((W * SS, H * SS), Image.LANCZOS).convert('RGBA')


def grid(mode, out):
    """The slide grid, alive: a soft band of light sweeps across it on the diagonal, lighting the lines it crosses and
    making the crossings glint gold, while gold dots run along the lines like reports crossing the country; behind every slide of the deck."""
    c = PAL[mode]
    # a fixed grain, the same in every frame: it hides the steps of the palette in the vignette without flicker
    base = ground_array(c) + np.random.default_rng(5).uniform(-2.5, 2.5, (H, W, 1))
    lines, cross = grid_mask()
    x, y = np.arange(W)[None, :], np.arange(H)[:, None]
    diag = (x * 0.8 + y * 0.6)                       # the band runs from the top left corner to the bottom right
    span = diag.max() + 600
    r = random.Random(11)
    flows = [dict(h=k % 2 == 0, at=r.random(), dir=r.choice([-1, 1]),
                  line=(r.randrange(1, int(H / CELL)) if k % 2 == 0 else r.randrange(1, int(W / CELL))) * CELL)
             for k in range(16)]
    frames = []
    n = 60
    for f in range(n):
        front = -300 + span * f / n
        band = np.exp(-((diag - front) / 90.0) ** 2)
        k = (band * lines)[..., None] * 0.9
        img = base * (1 - k) + hexa(c['glow'])[None, None, :] * k
        g = (band * cross)[..., None] * 0.95
        img = img * (1 - g) + hexa(c['gold'])[None, None, :] * g
        frame = Image.fromarray(img.clip(0, 255).astype('uint8'), 'RGB').convert('RGBA')
        lay = Image.new('RGBA', frame.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        for flow in flows:                           # gold reports running along the grid lines, end to end
            span = W if flow['h'] else H
            for k in range(14):                      # the dot, then its trail, 3 px a step
                u = (flow['at'] + flow['dir'] * (f / n - k * 3 / span)) % 1.0
                rr, a = (2.6 if k == 0 else 1.5), int(230 * (1 - k / 14))
                if flow['h']:
                    x0, y0 = u * W, flow['line']
                else:
                    x0, y0 = flow['line'], u * H
                d.ellipse([x0 - rr, y0 - rr, x0 + rr, y0 + rr], fill=rgb(c['gold'], a))
        frame.alpha_composite(lay)
        frames.append(frame.convert('RGB'))
    save(frames, out, ms=100, colors=256)


def save(frames, out, ms=MS, colors=128):
    # one palette for every frame, so the colours do not flicker
    sample = Image.new('RGB', (W, H * 4))
    for k, f in enumerate(frames[::len(frames) // 4]):
        sample.paste(f, (0, H * k))
    pal = sample.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    q[0].save(out, save_all=True, append_images=q[1:], duration=ms, loop=0, optimize=True, disposal=1)
    print(f'{out} · {Path(out).stat().st_size // 1024} KiB')


if __name__ == '__main__':
    dst = Path(sys.argv[1] if len(sys.argv) > 1 else HERE / 'assets')
    dst.mkdir(parents=True, exist_ok=True)
    for mode in PAL:
        grid(mode, dst / f'grid-{mode}.gif')
        network(mode, dst / f'trust-network-{mode}.gif')
        ring(mode, dst / f'trust-ring-{mode}.gif')
