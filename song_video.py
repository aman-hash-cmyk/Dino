"""
song_video.py - draws the counting-song videos in true 1080p.

Count-up verse : ten spotted eggs drop in, crack and hatch exactly when each number is sung (1..10).
Action chant   : the babies do their species move (waddle / play / flap / munch / stomp) to a catchy chant.
Count-down     : ten babies hop in and wave goodbye one by one as the numbers go down (10..1).
Extras         : slow camera sway and punch-ins on hatches, drifting clouds, floating sparkles, glossy 3D-style
                 characters whose eyes follow the action, a friendly host caption and word-by-word lyrics.
"""
import json
import math
import os
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from rig import Rig

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
W, H, FPS = 1920, 1080, 24
K = 1.5                                                   # everything was designed for 1280x720; scale to 1080p
LINE_RGB = (106, 74, 99)
FRONT_XS = [int(x * K) for x in (160, 400, 640, 880, 1120)]
BACK_XS = [int(x * K) for x in (280, 505, 730, 955, 1180)]
FRONT = dict(ground=int(662 * K), baby=360, egg=300)
BACK = dict(ground=int(522 * K), baby=270, egg=225)
EGG_BOTTOM = 0.92
SPECIES_INFO = {
    "steg": ("Green Stegosaurus", (110, 200, 110), (255, 200, 87)),
    "tri": ("Yellow Triceratops", (242, 197, 58), (255, 184, 107)),
    "ptero": ("Purple Pterodactyl", (150, 115, 230), (143, 115, 230)),
    "bronto": ("Teal Brontosaurus", (70, 190, 180), (92, 203, 192)),
    "trex": ("Orange T. rex", (242, 127, 61), (255, 168, 102)),
}
PASTEL = [(255, 226, 90), (255, 160, 200), (150, 220, 255), (170, 255, 170), (210, 170, 255)]
FONT_PATHS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
              "/Library/Fonts/Arial Bold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"]
_fonts, _bg, _eggs, _shadow, _cloud, _leaf_img = {}, {}, {}, {}, {}, []


def get_font(size):
    size = int(size)
    if size not in _fonts:
        font = None
        for p in FONT_PATHS:
            if Path(p).exists():
                font = ImageFont.truetype(p, size)
                break
        if font is None:
            try:
                font = ImageFont.load_default(size)
            except TypeError:
                font = ImageFont.load_default()
        _fonts[size] = font
    return _fonts[size]


def ease_out_back(x):
    x = max(0.0, min(1.0, x))
    c1 = 1.70158
    return 1 + (c1 + 1) * (x - 1) ** 3 + c1 * (x - 1) ** 2


def bounce_out(p):
    p = max(0.0, min(1.0, p))
    n1, d1 = 7.5625, 2.75
    if p < 1 / d1:
        return n1 * p * p
    if p < 2 / d1:
        p -= 1.5 / d1
        return n1 * p * p + 0.75
    if p < 2.5 / d1:
        p -= 2.25 / d1
        return n1 * p * p + 0.9375
    p -= 2.625 / d1
    return n1 * p * p + 0.984375


def layout(i):
    if i < 5:
        return FRONT_XS[i], FRONT["ground"], FRONT["baby"], FRONT["egg"]
    return BACK_XS[i - 5], BACK["ground"], BACK["baby"], BACK["egg"]


DRAW_ORDER = list(range(5, 10)) + list(range(5))


def _leaf():
    if not _leaf_img:
        _leaf_img.append(Image.open(ASSETS / "props" / "leaf.png").convert("RGBA"))
    return _leaf_img[0]


# ------------------------------------------------------------------ scenery: camera, clouds, sparkles
def big_bg(n):
    if n not in _bg:
        im = Image.open(ASSETS / "song" / f"bg_{n % 5}.png").convert("RGB")
        _bg[n] = ImageEnhance.Color(im).enhance(1.12)
    return _bg[n]


def bg_crop(n, t):
    """the background is 10% larger than the screen; the 'camera' slowly sways across it."""
    im = big_bg(n)
    ox = (im.width - W) / 2 + 0.45 * (im.width - W) / 2 * math.sin(t * 0.23)
    oy = (im.height - H) / 2 + 0.45 * (im.height - H) / 2 * math.cos(t * 0.19)
    return im.crop((int(ox), int(oy), int(ox) + W, int(oy) + H))


CLOUDS = [(0, 120, 14, 1.1, 100), (1, 260, 9, 0.9, 900), (2, 80, 11, 1.3, 1500), (0, 360, 7, 0.8, 1900), (1, 190, 12, 1.0, 400)]


def draw_clouds(frame, t):
    for idx, y, speed, sc, x0 in CLOUDS:
        key = (idx, sc)
        if key not in _cloud:
            im = Image.open(ASSETS / "song" / f"cloud_{idx}.png").convert("RGBA")
            _cloud[key] = im.resize((int(im.width * sc), int(im.height * sc)), Image.LANCZOS)
        c = _cloud[key]
        x = (x0 + speed * t) % (W + c.width) - c.width
        frame.paste(c, (int(x), int(y)), c)


_dust = None


def draw_dust(frame, t):
    global _dust
    if _dust is None:
        rnd = random.Random(11)
        _dust = [(rnd.random() * W, rnd.random() * H, 5 + rnd.random() * 12, 3 + rnd.random() * 4, rnd.random() * 6) for _ in range(26)]
    d = ImageDraw.Draw(frame)
    for x, y0, sp, r, ph in _dust:
        yy = (y0 - sp * t) % H
        xx = x + 22 * math.sin(t * 0.8 + ph)
        a = 0.5 + 0.5 * math.sin(t * 2 + ph)
        c = (255, int(240 + 15 * a), int(190 + 50 * a))
        d.ellipse((xx - r, yy - r, xx + r, yy + r), fill=c)


def star4(d, x, y, r, color):
    d.polygon([(x, y - r), (x + r * .3, y - r * .3), (x + r, y), (x + r * .3, y + r * .3),
               (x, y + r), (x - r * .3, y + r * .3), (x - r, y), (x - r * .3, y - r * .3)], fill=color)


def sparkles(d, cx, cy, t, n=7, rad=170):
    cols = [(255, 240, 120), (255, 255, 255), (255, 170, 210), (170, 235, 255)]
    for i in range(n):
        a = t * 2.2 + i * 2 * math.pi / n
        r = rad + 25 * K * math.sin(t * 5 + i)
        s = (11 + 8 * abs(math.sin(t * 6 + i * 1.7))) * K
        star4(d, cx + r * math.cos(a), cy - 60 * K + 0.6 * r * math.sin(a), s, cols[i % 4])


_conf = None


def confetti(d, t):
    global _conf
    if _conf is None:
        rnd = random.Random(7)
        cols = [(255, 92, 140), (255, 222, 89), (90, 200, 255), (130, 230, 120), (190, 120, 255)]
        _conf = [(rnd.random() * W, rnd.random() * H, (60 + rnd.random() * 90) * K, (6 + rnd.random() * 8) * K, cols[rnd.randrange(5)]) for _ in range(60)]
    for x, y0, sp, s, c in _conf:
        y = (y0 + t * sp) % H
        xx = x + 18 * K * math.sin(t * 2 + y0)
        d.ellipse((xx - s, y - s * .6, xx + s, y + s * .6), fill=c)


def camera(frame, zoom, cy_frac=0.62):
    if zoom <= 1.002:
        return frame
    w, h = W / zoom, H / zoom
    x0 = (W - w) / 2
    y0 = min(H - h, max(0, H * cy_frac - h / 2))
    return frame.crop((int(x0), int(y0), int(x0 + w), int(y0 + h))).resize((W, H), Image.BILINEAR)


# ------------------------------------------------------------------ eggs (drawn with PIL, 3D-style shading)
def make_egg(spot, size):
    key = (spot, size)
    if key in _eggs:
        return _eggs[key]
    S = size * 3
    cx, cy, rx, ry = S * 0.5, S * 0.58, S * 0.27, S * 0.34
    lw = max(3, int(S * 0.02))
    shape = Image.new("L", (S, S), 0)
    ImageDraw.Draw(shape).ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)
    egg = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(egg).ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=(255, 249, 234, 255))
    spots = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sd = ImageDraw.Draw(spots)
    for fx, fy, fr in ((-.45, -.35, .13), (.4, -.5, .10), (.1, .08, .14), (-.35, .45, .10), (.5, .3, .09), (-.05, -.78, .07), (.2, .62, .08)):
        x, y, r = cx + fx * rx, cy + fy * ry, fr * rx * 1.6
        sd.ellipse((x - r, y - r, x + r, y + r), fill=spot + (255,))
    spots.putalpha(ImageChops.multiply(spots.split()[3], shape))
    egg.alpha_composite(spots)
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)                            # soft shading: light from the top-left
    nx, ny = (xx - cx) / rx, (yy - cy) / ry
    dark = np.clip(np.hypot(nx + 0.38, ny + 0.45) / 1.9, 0, 1) ** 1.6
    shade = Image.new("RGBA", (S, S), (70, 40, 110, 0))
    shade.putalpha(ImageChops.multiply(Image.fromarray((dark * 120).astype(np.uint8)), shape))
    egg.alpha_composite(shade)
    hl = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(hl).ellipse((cx - rx * 0.68, cy - ry * 0.82, cx - rx * 0.12, cy - ry * 0.3), fill=(255, 255, 255, 170))
    hl = hl.filter(ImageFilter.GaussianBlur(S * 0.018))
    hl.putalpha(ImageChops.multiply(hl.split()[3], shape))
    egg.alpha_composite(hl)
    ImageDraw.Draw(egg).ellipse((cx - rx, cy - ry, cx + rx, cy + ry), outline=LINE_RGB + (255,), width=lw)
    alpha = egg.split()[3]
    n, zz = 8, S * 0.035
    zig = [(S * k / n, cy + (zz if k % 2 else -zz)) for k in range(n + 1)]

    def piece(poly):
        m = Image.new("L", (S, S), 0)
        ImageDraw.Draw(m).polygon(poly, fill=255)
        p = egg.copy()
        p.putalpha(ImageChops.multiply(alpha, m))
        line = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        ImageDraw.Draw(line).line(zig, fill=LINE_RGB + (255,), width=lw)
        line.putalpha(ImageChops.multiply(line.split()[3], alpha))
        p.alpha_composite(line)
        return p
    top, bottom = piece([(0, 0), (S, 0)] + zig[::-1]), piece(zig + [(S, S), (0, S)])
    crack = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    cd = ImageDraw.Draw(crack)
    cd.line(zig, fill=LINE_RGB + (255,), width=lw)
    cd.line([(cx - rx * 0.15, cy), (cx - rx * 0.3, cy - ry * 0.45), (cx - rx * 0.1, cy - ry * 0.7)], fill=LINE_RGB + (255,), width=lw)
    cd.line([(cx + rx * 0.3, cy), (cx + rx * 0.2, cy + ry * 0.4)], fill=LINE_RGB + (255,), width=lw)
    crack.putalpha(ImageChops.multiply(crack.split()[3], alpha))
    cracked = egg.copy()
    cracked.alpha_composite(crack)
    out = {k: v.resize((size, size), Image.LANCZOS) for k, v in (("full", egg), ("cracked", cracked), ("top", top), ("bottom", bottom))}
    _eggs[key] = out
    return out


def shadow(frame, cx, ground, rx, ry):
    rx, ry = max(8, int(rx)), max(4, int(ry))
    if (rx, ry) not in _shadow:
        im = Image.new("RGBA", (rx * 2, ry * 2), (0, 0, 0, 0))
        ImageDraw.Draw(im).ellipse((0, 0, rx * 2 - 1, ry * 2 - 1), fill=(90, 60, 100, 70))
        _shadow[(rx, ry)] = im.filter(ImageFilter.GaussianBlur(ry * 0.25))
    frame.paste(_shadow[(rx, ry)], (int(cx - rx), int(ground - ry)), _shadow[(rx, ry)])


def paste_rot(frame, img, anchor_xy, pivot_xy, angle=0.0, scale=1.0):
    if scale != 1.0:
        img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.BILINEAR)
        pivot_xy = (pivot_xy[0] * scale, pivot_xy[1] * scale)
    if angle:
        img = img.rotate(angle, resample=Image.BICUBIC, center=pivot_xy)
    frame.paste(img, (int(anchor_xy[0] - pivot_xy[0]), int(anchor_xy[1] - pivot_xy[1])), img)


# ------------------------------------------------------------------ baby behaviour
def blink(i, t):
    return ((t + i * 0.77) % 3.4) < 0.15


def baby_motion(sp, i, tt, ts, bl, singing, cheer, chorus, look):
    """pose + body motion. tt: secs since hatched/arrived, ts: secs since singing began, cheer/chorus: phase times or None."""
    s, pi = math.sin, math.pi
    ph = ts / bl
    pose = {"tail": 16 * s(ts * 7 + i), "head": 3 * s(ts * 1.5 + i), "head_dy": 0,
            "mouth": "open" if singing else "closed", "eyes": "blink" if blink(i, ts) else "open",
            "armL": -(8 + 5 * s(ts * 2 + i)), "armR": 8 + 5 * s(ts * 2.2 + i), "look_x": look, "look_y": 2}
    dx = dy = ang = 0.0
    sx = sy = 1.0
    big = 1.7 if chorus is not None else 1.0
    if chorus is not None:
        ph = chorus / bl * 1.0
    if sp == "steg":
        w = s(pi * ph * (1.0 if chorus is None else 2.0) + i * 0.7)
        ang, dx, dy = 7 * big * w, 8 * K * big * w, -4 * K * abs(w) * big
    elif sp == "tri":
        h = abs(s(pi * ph + i * 0.5))
        dy = -24 * K * big * h
        sy = 1 + 0.06 * big * h - 0.08 * max(0.0, 1 - h * 5)
        sx = 1 / sy
        pose["head"] = 9 * big * s(pi * ph + i)
        pose["armL"], pose["armR"] = -(20 + 18 * big * h), 20 + 18 * big * h
    elif sp == "ptero":
        a = (24 + 24 * s(ts * 11 + i)) * (1.25 if chorus is not None else 1.0)
        pose["armL"], pose["armR"] = -a, a
        dy, dx = (-34 - (14 if chorus is not None else 0) + 8 * s(ts * 2.5 + i)) * K, 14 * K * s(ts * 1.1 + i)
    elif sp == "bronto":
        m = s(ts * (5.5 if chorus is None else 8) + i)
        pose["head"], pose["head_dy"] = 10 * big * m, 9 * big * abs(m)
        pose["mouth"] = "open" if (m > 0.15 or singing) else "closed"
    elif sp == "trex":
        sq = max(0.0, 1 - (ph % 1.0) * 4.5)
        sy = 1 - (0.09 if chorus is None else 0.15) * sq
        sx = 1 / sy
        pose["armL"], pose["armR"] = -(12 + 14 * sq), 12 + 14 * sq
    if tt < 0.55:
        h = s(pi * tt / 0.55)
        dy -= 46 * K * h
        sy *= 1 + 0.10 * h
        sx = sx / (1 + 0.10 * h)
    if cheer is not None:
        h = abs(s(pi * cheer / bl))
        dy -= 40 * K * h
        a = 62 + 20 * s(cheer * 12 + i)
        pose["armL"], pose["armR"] = -a, a
        pose["mouth"] = "open" if (singing or cheer < 1.2) else "closed"
        sy *= 1 + 0.06 * h
        sx = sx / (1 + 0.06 * h)
        pose["look_x"] = 0
    return pose, dx, dy, sx, sy, ang


def draw_baby(frame, sp, pose, cx, ground, Sb, dx, dy, sx, sy, ang, sc):
    comp = Rig.get("baby_" + sp).compose(pose, Sb)
    if ang:
        comp = comp.rotate(ang, resample=Image.BILINEAR, center=(Sb / 2, Sb * 562 / 600))
    w, h = max(1, int(Sb * sc * sx)), max(1, int(Sb * sc * sy))
    if (w, h) != (Sb, Sb):
        comp = comp.resize((w, h), Image.BILINEAR)
    ax, ay = Sb / 2 * sc * sx, Sb * 562 / 600 * sc * sy
    frame.paste(comp, (int(cx + dx - ax), int(ground + dy - ay)), comp)


def draw_badge(frame, cx, cy, num, color, r, scale):
    if scale <= 0.02:
        return
    rr = int(r * scale)
    d = ImageDraw.Draw(frame)
    d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=color, outline=(255, 255, 255), width=max(3, rr // 7))
    d.ellipse((cx - rr * 0.62, cy - rr * 0.78, cx - rr * 0.05, cy - rr * 0.35), fill=tuple(min(255, c + 60) for c in color))
    d.text((cx, cy + 1), str(num), font=get_font(max(12, int(rr * 1.15))), fill=(255, 255, 255),
           stroke_width=max(2, rr // 12), stroke_fill=LINE_RGB, anchor="mm")


# ------------------------------------------------------------------ one verse
def singing_now(V, t):
    return any(p["start"] <= t < p["end"] for tk in V["tokens"] + V["chorus_tokens"] for p in tk["parts"])


def draw_verse(frame, V, t, exiting=False):
    sp, bl, kind = V["species"], V["beat"], V["kind"]
    name, color, spot = SPECIES_INFO[sp]
    rel = t - V["t_sing"]
    ex = (t - V["t_done"]) if exiting else 0.0
    exit_sc = max(0.0, 1 - ex / 0.45) if exiting else 1.0
    if exit_sc <= 0:
        return
    singing = (not exiting) and singing_now(V, t)
    cheer = chorus = None
    if not exiting:
        if kind == "up":
            if 28 * bl <= rel < 32 * bl:
                cheer = rel - 28 * bl
            elif t >= V["t_chorus_end"]:
                cheer = t - V["t_chorus_end"]
            elif V["t_end"] <= t:
                chorus = t - V["t_end"]
        elif rel >= 28 * bl:
            cheer = rel - 28 * bl
    nxt = next((j for j in range(10) if V["hatch"][j] > t), None) if kind == "up" else None
    for i in DRAW_ORDER:
        cx, ground, Sb, Se = layout(i)
        look = 0.0
        if nxt is not None and cheer is None and chorus is None:
            look = max(-1.0, min(1.0, (layout(nxt)[0] - cx) / 380.0)) * 8
        if kind == "up":
            hatch = V["hatch"][i]
            drop_t = V["t_pre"] + 0.15 + 0.035 * i
            if t < drop_t:
                continue
            eggs = make_egg(spot, Se)
            yoff = -(1 - bounce_out((t - drop_t) / 0.55)) * (ground + 160)
            if t < hatch:
                left = hatch - t
                ang = 2.0 * math.sin(t * 3 + i) if left > 0.8 else 11 * (1 - left / 0.8) * math.sin(t * 38)
                shadow(frame, cx, ground, Se * 0.27, Se * 0.045)
                paste_rot(frame, eggs["cracked"] if left < 0.42 else eggs["full"], (cx, ground + yoff), (Se / 2, EGG_BOTTOM * Se), ang, exit_sc)
                continue
            tt = t - hatch
            em = (0.4 + 0.6 * ease_out_back(tt / 0.4)) if tt < 0.4 else 1.0
            sc, hop = em * exit_sc, 0.0
        else:
            arrive = V["arrive"][i]
            if t < arrive:
                continue
            tt = 10.0
            hop = -(1 - bounce_out((t - arrive) / 0.6)) * (ground + 200)
            sc = exit_sc
            leave = V["leave"][i]
            if leave and t >= leave and not exiting:
                lt = t - leave
                if lt > 0.85:
                    continue
                hop += -50 * K * math.sin(math.pi * min(lt, 0.45) / 0.45)
                sc *= 1.0 if lt < 0.45 else max(0.0, 1 - (lt - 0.45) / 0.4)
                look = 0.0
            eggs = None
        c_i = cheer
        if kind == "down":
            c_i = None
            if V["leave"][i] and t >= V["leave"][i] and not exiting:
                c_i = t - V["leave"][i]                                   # waves goodbye
            elif not exiting and rel >= 28 * bl:
                c_i = rel - 28 * bl
        pose, dx, dy, sx, sy, ang = baby_motion(sp, i, tt, max(rel, 0.0), bl, singing, c_i, chorus, look)
        dy += hop
        shadow(frame, cx + dx, ground, Sb * 0.27 * sc * (1 - 0.35 * min(1.0, max(0.0, -dy) / (40 * K))), Sb * 0.045 * sc)
        draw_baby(frame, sp, pose, cx, ground, Sb, dx, dy, sx, sy, ang, sc)
        if sp == "bronto":
            bite = 1 - 0.1 * (((max(rel, 0)) * 1.2) % 4)
            ls = int(Sb * 0.36 * bite * sc)
            if ls > 10:
                leaf = _leaf().resize((ls, ls), Image.BILINEAR).rotate(25 + 8 * math.sin(rel * 5.5), resample=Image.BILINEAR)
                my = ground + dy - Sb * 562 / 600 * sc + Sb * 0.34 * sc + pose["head_dy"] * 0.4
                frame.paste(leaf, (int(cx + Sb * 0.08 * sc), int(my)), leaf)
        if kind == "up":
            paste_rot(frame, eggs["bottom"], (cx, ground), (Se / 2, EGG_BOTTOM * Se), 0, exit_sc)
            if tt < 0.9:
                vx = 190 if i % 2 else -190
                paste_rot(frame, eggs["top"], (cx + vx * tt, ground - 840 * tt + 0.5 * 2500 * tt * tt), (Se / 2, EGG_BOTTOM * Se),
                          (260 if i % 2 else -260) * tt, 1.0)
            if tt < 0.5:
                sparkles(ImageDraw.Draw(frame), cx, ground - Sb * 0.35, tt * 3, n=5, rad=int(Sb * 0.3))
            draw_badge(frame, cx, int(ground - Sb * 1.0 - 45 + 6 * math.sin(rel * 3 + i)), i + 1, color, 51 if i < 5 else 42,
                       ease_out_back((tt - 0.05) / 0.3) * exit_sc)
    if kind == "down" and not exiting:                                         # big counter: how many are left
        gone = [lv for lv in V["leave"] if lv and t >= lv]
        last = max(gone) if gone else V["arrive"][9] + 0.5
        draw_badge(frame, W // 2, int(250 * K * 0.78), 10 - len(gone), color, 82, ease_out_back((t - last) / 0.3))


# ------------------------------------------------------------------ text overlays (drawn after the camera move)
def pill(frame, text, y, color, size=58, scale=1.0):
    d = ImageDraw.Draw(frame)
    f = get_font(max(16, int(size * scale)))
    w = f.getlength(text) + 110
    d.rounded_rectangle((W / 2 - w / 2, y - 52 * scale, W / 2 + w / 2, y + 52 * scale), radius=int(52 * scale), fill=color, outline=(255, 255, 255), width=7)
    d.text((W / 2, y), text, font=f, fill=(255, 255, 255), stroke_width=5, stroke_fill=LINE_RGB, anchor="mm")


def host_caption(frame, tl, t, y, color=(255, 140, 190)):
    for h in tl["host"]:
        if h["t0"] <= t < h["t0"] + h["dur"] + 0.25:
            pill(frame, h["text"], y, color, 56, max(0.05, ease_out_back((t - h["t0"]) / 0.3)))
            return True
    return False


def draw_lyrics(frame, V, t):
    toks = V["tokens"] + V["chorus_tokens"]
    d = ImageDraw.Draw(frame)
    cur = 0
    for tk in toks:
        if tk["start"] - 0.05 <= t:
            cur = tk["line"]
    words = [tk for tk in toks if tk["line"] == cur]
    size = 84
    while True:
        font = get_font(size)
        space = font.getlength(" ")
        total = sum(font.getlength(w["display"]) for w in words) + space * (len(words) - 1)
        if total <= W - 130 or size <= 44:
            break
        size -= 3
    x = (W - total) / 2
    for w in words:
        wl = font.getlength(w["display"])
        if w["start"] <= t < w["end"] + 0.05:
            fill, lift = (255, 226, 90), -8
        elif t >= w["end"]:
            fill, lift = (255, 214, 238), 0
        else:
            fill, lift = (255, 255, 255), 0
        d.text((x + wl / 2, 105 + lift), w["display"], font=font, fill=fill, stroke_width=12, stroke_fill=LINE_RGB, anchor="mm")
        x += wl + space


def title_text(frame, text, y, size, t, colors):
    d = ImageDraw.Draw(frame)
    font = get_font(size)
    widths = [font.getlength(c) for c in text]
    x = (W - sum(widths)) / 2
    for k, ch in enumerate(text):
        d.text((x + widths[k] / 2, y - 18 * abs(math.sin(t * 4 + k * 0.6))), ch, font=font, fill=colors[k % len(colors)],
               stroke_width=14, stroke_fill=LINE_RGB, anchor="mm")
        x += widths[k]


def teaser(frame, t, wave=False):
    for k, sp in enumerate(("steg", "tri", "ptero", "bronto", "trex")):
        cx, h = FRONT_XS[k], abs(math.sin(t * 4 + k))
        a = (50 + 25 * math.sin(t * 9 + k)) if wave else 25 + 15 * h
        pose = {"tail": 18 * math.sin(t * 7 + k), "head": 6 * math.sin(t * 3 + k), "mouth": "open" if int(t * 3 + k) % 2 else "closed",
                "eyes": "blink" if blink(k, t) else "open", "armL": -a, "armR": a, "look_x": 0, "look_y": 3}
        dy = (-26 * h - (30 if sp == "ptero" else 0)) * K
        shadow(frame, cx, 1002, 105, 15)
        draw_baby(frame, sp, pose, cx, 1002, 360, 0, dy, 1, 1 + 0.05 * h, 0, 1.0)


def intro_frame(tl, t):
    frame = bg_crop(0, t)
    draw_clouds(frame, t)
    d = ImageDraw.Draw(frame)
    confetti(d, t)
    title_text(frame, "10 Little", 200, 170, t, PASTEL)
    title_text(frame, "Dinosaurs", 390, 180, t + 1, PASTEL[::-1])
    teaser(frame, t)
    sparkles(d, W // 2, 500, t, n=9, rad=620)
    return frame


def outro_frame(tl, t):
    frame = bg_crop(4, t)
    draw_clouds(frame, t)
    d = ImageDraw.Draw(frame)
    confetti(d, t)
    title_text(frame, "Bye bye!", 210, 170, t, PASTEL)
    d.text((W // 2, 400), "Thanks for counting with us!", font=get_font(78), fill=(255, 255, 255), stroke_width=11, stroke_fill=LINE_RGB, anchor="mm")
    teaser(frame, t, wave=True)
    return frame


# ------------------------------------------------------------------ frame + build
def find_verse(tl, t):
    for k, V in enumerate(tl["verses"]):
        if V["t_pre"] <= t < V["t_done"]:
            return k
    return None


def zoom_for(V, t):
    z = 1.0 + 0.03 * (t - V["t_pre"]) / max(0.1, V["t_done"] - V["t_pre"])
    bl = V["beat"]
    pulses = [(th, 0.022) for th in V["hatch"]] if V["kind"] == "up" else [(lv, 0.016) for lv in V["leave"] if lv]
    pulses += [(V["t_sing"] + 28 * bl, 0.04), (V["t_end"], 0.03), (V["t_chorus_end"], 0.03)]
    for p, a in pulses:
        if 0 <= t - p < 0.8:
            z += a * math.exp(-6 * (t - p))
    return z


def render_frame(tl, t):
    if t < tl["intro"]["t1"]:
        frame = intro_frame(tl, t)
        host_caption(frame, tl, t, 640)
        return frame
    if t >= tl["outro"]["t0"]:
        frame = outro_frame(tl, t - tl["outro"]["t0"])
        host_caption(frame, tl, t, 560)
        return frame
    k = find_verse(tl, t)
    V = tl["verses"][k]
    frame = bg_crop(V["bg"], t)
    if k > 0 and t < V["t_pre"] + 0.8:
        frame = Image.blend(bg_crop(tl["verses"][k - 1]["bg"], t), frame, (t - V["t_pre"]) / 0.8)
    draw_clouds(frame, t)
    draw_dust(frame, t)
    if k > 0 and t < V["t_pre"] + 0.5:
        draw_verse(frame, tl["verses"][k - 1], t, exiting=True)
    draw_verse(frame, V, t)
    d = ImageDraw.Draw(frame)
    rel = t - V["t_sing"]
    if 28 * V["beat"] <= rel < 32 * V["beat"] or V["t_end"] <= t < V["t_chorus_end"]:
        confetti(d, t)
        sparkles(d, W // 2, 500, t, n=9, rad=640)
    frame = camera(frame, zoom_for(V, t))
    if not host_caption(frame, tl, t, 105):
        if V["t_sing"] - 0.1 <= t < V["t_chorus_end"] or (V["kind"] == "down" and t < V["t_done"] and t >= V["t_sing"]):
            draw_lyrics(frame, V, t)
    return frame


def build(ep_dir):
    ep_dir = Path(ep_dir)
    tl = json.loads((ep_dir / "song_timeline.json").read_text())
    if os.environ.get("DINO_SAMPLE_TIMES"):                                    # testing aid: save a few still frames
        out = ep_dir / "samples"
        out.mkdir(exist_ok=True)
        for s in os.environ["DINO_SAMPLE_TIMES"].split(","):
            render_frame(tl, float(s)).save(out / f"t{float(s):07.2f}.png")
        return
    total = tl["total"] + 0.5
    nframes = min(int(total * FPS), int(os.environ.get("DINO_MAX_FRAMES", 10 ** 9)))
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", str(ep_dir / "final_audio.wav"), "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-tune", "animation", "-pix_fmt", "yuv420p",
           "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", f"{total:.3f}", str(ep_dir / "video.mp4")]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(nframes):
        proc.stdin.write(render_frame(tl, f / FPS).convert("RGB").tobytes())
        if f % 480 == 0:
            print(f"  rendered {f}/{int(total * FPS)} frames", flush=True)
    proc.stdin.close()
    if proc.wait() != 0:
        sys.exit("ffmpeg failed")
    names = {"steg": "stegosaurus", "tri": "triceratops", "ptero": "pterodactyl", "bronto": "brontosaurus", "trex": "trex"}
    segs = [{"segment": "intro", "start": 0.0, "end": round(tl["intro"]["t1"] / total, 4)}]
    for V in tl["verses"]:
        segs.append({"segment": ("" if V["kind"] == "up" else "down_") + names[V["species"]],
                     "start": round(V["t_pre"] / total, 4), "end": round(V["t_done"] / total, 4)})
    segs.append({"segment": "outro", "start": round(tl["outro"]["t0"] / total, 4), "end": 1.0})
    (ep_dir / "segments.json").write_text(json.dumps({"duration": round(total, 2), "segments": segs}, indent=2))
    print(f"Video ready: {ep_dir / 'video.mp4'} ({total / 60:.1f} min, {W}x{H})")


# ------------------------------------------------------------------ thumbnail (1080p)
def thumbnail(ep_dir, tl):
    ep_dir = Path(ep_dir)
    img = ImageEnhance.Color(bg_crop(tl["verses"][0]["bg"], 0.0)).enhance(1.15)
    rays = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rd = ImageDraw.Draw(rays)
    for k in range(16):
        a0, a1 = math.radians(k * 22.5), math.radians(k * 22.5 + 11)
        rd.polygon([(W / 2, H * 0.62), (W / 2 + 2200 * math.cos(a0), H * 0.62 + 2200 * math.sin(a0)),
                    (W / 2 + 2200 * math.cos(a1), H * 0.62 + 2200 * math.sin(a1))], fill=(255, 250, 190, 90))
    img.paste(rays, (0, 0), rays)
    for k, sp in enumerate(("steg", "tri", "ptero", "bronto", "trex")):
        pose = {"mouth": "open", "armL": -62, "armR": 62, "head": 5 * (-1) ** k, "eyes": "open"}
        comp = Rig.get("baby_" + sp).compose(pose, 480)
        img.paste(comp, (int(90 + k * 352 - 120), H - 500 - (45 if sp == "ptero" else 0)), comp)
    d = ImageDraw.Draw(img)
    for text, y, size, cols in (("10 LITTLE", 158, 200, PASTEL), ("DINOSAURS", 352, 210, PASTEL[::-1])):
        font = get_font(size)
        widths = [font.getlength(c) for c in text]
        x = (W - sum(widths)) / 2
        for k, ch in enumerate(text):
            d.text((x + widths[k] / 2, y), ch, font=font, fill=cols[k % 5], stroke_width=16, stroke_fill=LINE_RGB, anchor="mm")
            x += widths[k]
    d.rounded_rectangle((W / 2 - 345, 458, W / 2 + 345, 570), radius=56, fill=(255, 120, 175), outline=(255, 255, 255), width=8)
    d.text((W / 2, 514), "COUNT 1 TO 10!", font=get_font(66), fill=(255, 255, 255), stroke_width=6, stroke_fill=LINE_RGB, anchor="mm")
    img.convert("RGB").save(ep_dir / "thumbnail.jpg", quality=88)
    print("Thumbnail ready:", ep_dir / "thumbnail.jpg")
