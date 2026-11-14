"""The animated background of the presentation (Yamen, 2026-11-14): bubbles rising, some of them carrying the emblem
of the Civil Protection, and around the emblem a ring of people, citizens and Civil Protection agents hand in hand,
turning slowly: the trust built between the citizens on one side and the Civil Protection on the other.

    python3 scripts/tracking/trust-bubbles.py <out-dir>

Writes four looping GIFs (PowerPoint plays them in the slide show): trust-ring-{night,day}.gif with the ring, for the
closing slide, and trust-field-{night,day}.gif with the bubbles alone, for the cover. Colours are the deck kit's.
"""
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
LOGO = Image.open(HERE / 'assets' / 'civil-protection-logo.png').convert('RGBA')
W, H, SS = 1280, 720, 2          # frame size, supersampling
FRAMES, MS = 48, 80              # a loop of 3.84 s
PAL = {
    'night': dict(bg='08102A', ink='E8ECF5', gold='C9A24A', red='FF6B6B', bubble='8FA8FF', disc='0E1426'),
    'day': dict(bg='F6F8FC', ink='1F3FA0', gold='9C7A22', red='D7141A', bubble='1F3FA0', disc='FFFFFF'),
}


def rgb(h, a=255):
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


def bubbles(seed, n):
    r = random.Random(seed)
    out = []
    for k in range(n):
        out.append(dict(x=r.uniform(0.03, 0.97) * W, y=r.uniform(0, 1), rad=r.uniform(16, 64), laps=r.choice([1, 1, 2]),
                        sway=r.uniform(6, 22), ph=r.uniform(0, 2 * math.pi), logo=k % 3 == 0))
    return out


def draw_bubbles(img, bs, t, c):
    # translucent shapes go on a layer of their own, then onto the frame: ImageDraw alone does not blend
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    logos = []
    for b in bs:
        rad = b['rad'] * SS
        span = H * SS + 2 * rad
        y = (b['y'] * span - t * b['laps'] * span) % span - rad
        x = (b['x'] + b['sway'] * math.sin(2 * math.pi * t + b['ph'])) * SS
        d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=rgb(c['bubble'], 20), outline=rgb(c['bubble'], 80), width=SS * 2)
        d.ellipse([x - rad * 0.55, y - rad * 0.7, x - rad * 0.2, y - rad * 0.4], fill=rgb('FFFFFF', 60))  # the shine
        if b['logo']:
            logos.append((x, y, rad))
    img.alpha_composite(layer)
    for x, y, rad in logos:
        s = int(rad * 1.25)
        lg = LOGO.resize((s, s), Image.LANCZOS)
        lg.putalpha(lg.getchannel('A').point(lambda v: v * 110 // 255))
        img.alpha_composite(lg, (int(x - s / 2), int(y - s / 2)))


def person(d, x, y, s, body, head_col, helmet):
    """One standing person, feet at (x, y), height about 3.1 s."""
    d.rounded_rectangle([x - 0.55 * s, y - 2.2 * s, x + 0.55 * s, y], radius=int(0.45 * s), fill=body)
    d.ellipse([x - 0.42 * s, y - 3.1 * s, x + 0.42 * s, y - 2.26 * s], fill=head_col)
    if helmet:
        d.chord([x - 0.5 * s, y - 3.18 * s, x + 0.5 * s, y - 2.45 * s], 180, 360, fill=helmet)


def draw_ring(img, t, c, cx, cy):
    n, rx, ry = 12, 290 * SS, 72 * SS
    # the glow under the emblem, ring over ring
    for k in range(6, 0, -1):
        r = (92 + k * 10) * SS
        g = Image.new('RGBA', img.size, (0, 0, 0, 0))
        ImageDraw.Draw(g).ellipse([cx - r, cy - 150 * SS - r, cx + r, cy - 150 * SS + r], fill=rgb(c['gold'], 14))
        img.alpha_composite(g)
    d = ImageDraw.Draw(img)
    pts = []
    for i in range(n):
        a = 2 * math.pi * (i / n + t / n)  # one place per loop: seamless
        depth = math.sin(a)               # -1 at the back, +1 at the front
        pts.append((a, cx + rx * math.cos(a), cy + ry * depth, 0.75 + 0.25 * (depth + 1) / 2, i % 2 == 0))

    def link(p, q, alpha):
        s1, s2 = p[3] * 28 * SS, q[3] * 28 * SS
        d.line([(p[1], p[2] - 1.6 * s1), (q[1], q[2] - 1.6 * s2)], fill=rgb(c['gold'], alpha), width=int(3 * SS))

    order = sorted(range(n), key=lambda i: pts[i][2])
    back = [i for i in order if pts[i][2] < cy]
    front = [i for i in order if pts[i][2] >= cy]

    def people(ids):
        for i in ids:
            _, x, y, sc, citizen = pts[i]
            s = sc * 28 * SS
            if citizen:
                person(d, x, y, s, rgb(c['ink'], 235), rgb(c['ink'], 255), None)
            else:
                person(d, x, y, s, rgb(c['red'], 240), rgb(c['red'], 255), rgb(c['gold'], 255))

    for i in range(n):  # the hands: back links first
        j = (i + 1) % n
        if pts[i][2] < cy and pts[j][2] < cy:
            link(pts[i], pts[j], 150)
    people(back)
    # the emblem on its disc, in the middle of the ring
    r = 92 * SS
    d.ellipse([cx - r, cy - 150 * SS - r, cx + r, cy - 150 * SS + r], fill=rgb(c['disc']), outline=rgb(c['gold']), width=4 * SS)
    s = int(150 * SS)
    img.alpha_composite(LOGO.resize((s, s), Image.LANCZOS), (int(cx - s / 2), int(cy - 150 * SS - s / 2)))
    d = ImageDraw.Draw(img)
    for i in range(n):
        j = (i + 1) % n
        if not (pts[i][2] < cy and pts[j][2] < cy):
            link(pts[i], pts[j], 230)
    people(front)


def render(mode, ring, out):
    c = PAL[mode]
    bs = bubbles(7, 22)
    frames = []
    for f in range(FRAMES):
        t = f / FRAMES
        img = Image.new('RGBA', (W * SS, H * SS), rgb(c['bg']))
        draw_bubbles(img, bs, t, c)
        if ring:
            draw_ring(img, t, c, W * SS / 2, 300 * SS)
        frames.append(img.resize((W, H), Image.LANCZOS).convert('RGB'))
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
        render(mode, True, dst / f'trust-ring-{mode}.gif')
        render(mode, False, dst / f'trust-field-{mode}.gif')
