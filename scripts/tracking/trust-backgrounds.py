"""The animated backgrounds of the committee presentation (Yamen, 2026-11-14), in a sober line style.

    python3 scripts/tracking/trust-backgrounds.py <out-dir>

trust-network-{night,day}.gif, for the cover: Tunisia drawn by its own points (schools and delegation seats from
data/osm), twinkling, with a wave of light leaving the national room and crossing the country, the Civil Protection units in gold, and the 24 governorate seats joined to the national room in Tunis, a
pulse running along every link: one national system, from the report to the decision.
trust-ring-{night,day}.gif, for the closing slide: the emblem in thin gold circles, and round it a ring of citizens and
Civil Protection agents hand in hand, drawn as line art and turning slowly: the trust between them.
Every loop is seamless; colours are the deck kit's. PowerPoint plays the GIFs in the slide show.
"""
import json
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOGO = Image.open(HERE / 'assets' / 'civil-protection-logo.png').convert('RGBA')
W, H, SS = 1280, 720, 2          # frame size, supersampling
FRAMES, MS = 48, 80              # a loop of 3.84 s
PAL = {
    'night': dict(bg='08102A', ink='E8ECF5', gold='C9A24A', red='FF6B6B', dot='8FA8FF', disc='0E1426'),
    'day': dict(bg='F6F8FC', ink='1F3FA0', gold='9C7A22', red='D7141A', dot='1F3FA0', disc='FFFFFF'),
}
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
    pj = project(320, 20, 680)
    land = [pj(*p) for p in points('schools') + points('delegation_hq')]
    units = [pj(*p) for p in points('civil_protection')]
    seats = [pj(*p) for p in SEATS]
    hub = seats[0]
    r = random.Random(3)
    starts = [r.random() for _ in seats]
    land = [((x, y), math.hypot(x - hub[0], y - hub[1]), r.random()) for x, y in land]
    reach = max(dist for _, dist, _ in land)
    base = Image.new('RGBA', (W * SS, H * SS), rgb(c['bg']))
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
    frames = []
    for f in range(FRAMES):
        t = f / FRAMES
        img = Image.new('RGBA', (W * SS, H * SS), rgb(c['bg']))
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


def pulse(mode, out):
    """Waves going out from the emblem, slow and even, like a signal heard across the country."""
    c = PAL[mode]
    cx, cy = W * SS / 2, 250 * SS
    frames = []
    for f in range(FRAMES):
        t = f / FRAMES
        img = Image.new('RGBA', (W * SS, H * SS), rgb(c['bg']))
        lay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        for k in range(5):                     # five waves, a fifth of a loop apart
            ph = (t + k / 5) % 1.0
            rr = (100 + 520 * ph) * SS
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=rgb(c['gold'], int(150 * (1 - ph) ** 1.5)), width=SS * 2)
        r = 88 * SS
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=rgb(c['disc']), outline=rgb(c['gold']), width=2 * SS)
        img.alpha_composite(lay)
        s = int(140 * SS)
        img.alpha_composite(LOGO.resize((s, s), Image.LANCZOS), (int(cx - s / 2), int(cy - s / 2)))
        frames.append(img.resize((W, H), Image.LANCZOS).convert('RGB'))
    save(frames, out)


def save(frames, out):
    # one palette for every frame, so the colours do not flicker
    sample = Image.new('RGB', (W, H * 4))
    for k, f in enumerate(frames[::FRAMES // 4]):
        sample.paste(f, (0, H * k))
    pal = sample.quantize(colors=128, method=Image.Quantize.MEDIANCUT)
    q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    q[0].save(out, save_all=True, append_images=q[1:], duration=MS, loop=0, optimize=True, disposal=1)
    print(f'{out} · {Path(out).stat().st_size // 1024} KiB')


if __name__ == '__main__':
    dst = Path(sys.argv[1] if len(sys.argv) > 1 else HERE / 'assets')
    dst.mkdir(parents=True, exist_ok=True)
    for mode in PAL:
        network(mode, dst / f'trust-network-{mode}.gif')
        ring(mode, dst / f'trust-ring-{mode}.gif')
