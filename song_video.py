"""
song_video.py - draws the "10 Little Dinosaurs" counting song.

Every verse: ten spotted eggs drop in, then they crack and hatch one by one exactly when the number
is sung (1..10). Each species behaves differently: Stegosaurus waddles, Triceratops hops and plays,
Pterodactyl flaps and floats, Brontosaurus munches a leaf, T. rex stomps gently to the beat.
Everybody opens their mouth when the chorus sings and cheers on "...dinosaur babies!".
"""
import json
import math
import os
import random
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance

from assemble_video import (FPS, H, INK, W, confetti, ease_out_back, get_font, outlined, sparkles)
from rig import Rig

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
LINE_RGB = (106, 74, 99)
FRONT_XS, BACK_XS = [160, 400, 640, 880, 1120], [280, 505, 730, 955, 1180]
FRONT = dict(ground=662, baby=240, egg=200)
BACK = dict(ground=522, baby=180, egg=150)
EGG_BOTTOM = 0.92                        # egg bottom edge (fraction of the egg image height)
SPECIES_INFO = {
    "steg": ("Green Stegosaurus", (110, 200, 110), (255, 200, 87)),
    "tri": ("Yellow Triceratops", (242, 197, 58), (255, 184, 107)),
    "ptero": ("Purple Pterodactyl", (150, 115, 230), (143, 115, 230)),
    "bronto": ("Teal Brontosaurus", (70, 190, 180), (92, 203, 192)),
    "trex": ("Orange T. rex", (242, 127, 61), (255, 168, 102)),
}
_bg, _eggs, _shadow = {}, {}, {}


_leaf_img = []


def _leaf():
    if not _leaf_img:
        _leaf_img.append(Image.open(ASSETS / "props" / "leaf.png").convert("RGBA"))
    return _leaf_img[0]


def layout(i):
    if i < 5:
        return FRONT_XS[i], FRONT["ground"], FRONT["baby"], FRONT["egg"]
    return BACK_XS[i - 5], BACK["ground"], BACK["baby"], BACK["egg"]


DRAW_ORDER = list(range(5, 10)) + list(range(5))        # back row first


# ------------------------------------------------------------------ pictures
def background(n):
    if n not in _bg:
        im = Image.open(ASSETS / "song" / f"bg_{n % 5}.png").convert("RGB").resize((W, H), Image.LANCZOS)
        _bg[n] = ImageEnhance.Color(im).enhance(1.12)
    return _bg[n]


def make_egg(spot, size):
    """spotted egg as full / cracked / bottom half / top half (drawn with PIL, no files needed)."""
    key = (spot, size)
    if key in _eggs:
        return _eggs[key]
    S = size * 4
    cx, cy, rx, ry = S * 0.5, S * 0.58, S * 0.27, S * 0.34
    lw = max(3, int(S * 0.022))
    shape = Image.new("L", (S, S), 0)
    ImageDraw.Draw(shape).ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)
    egg = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(egg)
    d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=(255, 249, 234, 255))
    spots = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sd = ImageDraw.Draw(spots)
    for fx, fy, fr in ((-.45, -.35, .13), (.4, -.5, .10), (.1, .08, .14), (-.35, .45, .10), (.5, .3, .09), (-.05, -.78, .07), (.2, .62, .08)):
        x, y, r = cx + fx * rx, cy + fy * ry, fr * rx * 1.6
        sd.ellipse((x - r, y - r, x + r, y + r), fill=spot + (255,))
    spots.putalpha(ImageChops.multiply(spots.split()[3], shape))
    egg.alpha_composite(spots)
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
    top = piece([(0, 0), (S, 0)] + zig[::-1])
    bottom = piece(zig + [(S, S), (0, S)])
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
    rx, ry = max(6, int(rx)), max(3, int(ry))
    if (rx, ry) not in _shadow:
        im = Image.new("RGBA", (rx * 2, ry * 2), (0, 0, 0, 0))
        ImageDraw.Draw(im).ellipse((0, 0, rx * 2 - 1, ry * 2 - 1), fill=(90, 60, 100, 60))
        _shadow[(rx, ry)] = im
    frame.paste(_shadow[(rx, ry)], (int(cx - rx), int(ground - ry)), _shadow[(rx, ry)])


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


def paste_rot(frame, img, anchor_xy, pivot_xy, angle=0.0, scale=1.0):
    """paste img so that its pivot lands on anchor; optional rotation/scale around the pivot."""
    if scale != 1.0:
        img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.BILINEAR)
        pivot_xy = (pivot_xy[0] * scale, pivot_xy[1] * scale)
    if angle:
        img = img.rotate(angle, resample=Image.BILINEAR, center=pivot_xy)
    frame.paste(img, (int(anchor_xy[0] - pivot_xy[0]), int(anchor_xy[1] - pivot_xy[1])), img)


# ------------------------------------------------------------------ baby behaviour
def blink(i, t):
    return ((t + i * 0.77) % 3.4) < 0.15


def baby_motion(sp, i, tt, ts, bl, singing, in_final):
    """pose + body motion of one baby. tt: seconds since it hatched, ts: seconds since the verse began singing."""
    s, pi = math.sin, math.pi
    ph = ts / bl
    pose = {"tail": 16 * s(ts * 7 + i), "head": 3 * s(ts * 1.5 + i), "head_dy": 0,
            "mouth": "open" if singing else "closed", "eyes": "blink" if blink(i, ts) else "open",
            "armL": -(8 + 5 * s(ts * 2 + i)), "armR": 8 + 5 * s(ts * 2.2 + i)}
    dx = dy = ang = 0.0
    sx = sy = 1.0
    if sp == "steg":                                  # waddle
        w = s(pi * ph + i * 0.7)
        ang, dx, dy = 7 * w, 8 * w, -4 * abs(w)
    elif sp == "tri":                                 # play: happy hops
        h = abs(s(pi * ph + i * 0.5))
        dy = -24 * h
        sy = 1 + 0.06 * h - 0.08 * max(0.0, 1 - h * 5)
        sx = 1 / sy
        pose["head"] = 9 * s(pi * ph + i)
        pose["armL"], pose["armR"] = -(20 + 18 * h), 20 + 18 * h
    elif sp == "ptero":                               # flap and float
        a = 24 + 24 * s(ts * 11 + i)
        pose["armL"], pose["armR"] = -a, a
        dy, dx = -34 + 8 * s(ts * 2.5 + i), 14 * s(ts * 1.1 + i)
    elif sp == "bronto":                              # munch a leaf
        m = s(ts * 5.5 + i)
        pose["head"], pose["head_dy"] = 10 * m, 9 * abs(m)
        pose["mouth"] = "open" if (m > 0.15 or singing) else "closed"
    elif sp == "trex":                                # soft stomps on the beat
        sq = max(0.0, 1 - (ph % 1.0) * 4.5)
        sy = 1 - 0.09 * sq
        sx = 1 / sy
        pose["armL"], pose["armR"] = -(12 + 14 * sq), 12 + 14 * sq
    if tt < 0.55:                                     # little hop when it hatches
        h = s(pi * tt / 0.55)
        dy -= 46 * h
        sy *= 1 + 0.10 * h
        sx = sx / (1 + 0.10 * h)
    if in_final is not None:                          # "...dinosaur babies!" everybody cheers
        h = abs(s(pi * in_final / bl))
        dy -= 40 * h
        a = 62 + 20 * s(in_final * 12 + i)
        pose["armL"], pose["armR"] = -a, a
        pose["mouth"] = "open"
        pose["brows"] = "up"
        sy *= 1 + 0.06 * h
        sx = sx / (1 + 0.06 * h)
    return pose, dx, dy, sx, sy, ang


def draw_baby(frame, sp, i, pose, cx, ground, Sb, dx, dy, sx, sy, ang, sc):
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
    d.text((cx, cy + 1), str(num), font=get_font(max(12, int(rr * 1.15))), fill=(255, 255, 255),
           stroke_width=max(2, rr // 12), stroke_fill=LINE_RGB, anchor="mm")


# ------------------------------------------------------------------ one verse
def singing_now(V, t):
    return any(p["start"] <= t < p["end"] for tk in V["tokens"] for p in tk["parts"])


def draw_verse(frame, V, t, exiting=False):
    sp, bl = V["species"], V["beat"]
    name, color, spot = SPECIES_INFO[sp]
    rel = t - V["t_sing"]
    singing = (not exiting) and singing_now(V, t)
    ex = t - V["t_end"] if exiting else 0.0
    exit_sc = max(0.0, 1 - ex / 0.45) if exiting else 1.0
    if exit_sc <= 0:
        return
    in_final = rel - 28 * bl if (not exiting and rel >= 28 * bl) else None
    for i in DRAW_ORDER:
        cx, ground, Sb, Se = layout(i)
        hatch = V["hatch"][i]
        drop_t = V["t_pre"] + 0.15 + 0.035 * i
        if t < drop_t:
            continue
        eggs = make_egg(spot, Se)
        yoff = -(1 - bounce_out((t - drop_t) / 0.55)) * (ground + 120)
        if t < hatch:                                                         # ---- still an egg
            left = hatch - t
            ang = 2.0 * math.sin(t * 3 + i) if left > 0.8 else 11 * (1 - left / 0.8) * math.sin(t * 38)
            img = eggs["cracked"] if left < 0.42 else eggs["full"]
            shadow(frame, cx, ground, Se * 0.27, Se * 0.04)
            paste_rot(frame, img, (cx, ground + yoff), (Se / 2, EGG_BOTTOM * Se), ang, exit_sc)
            continue
        tt = t - hatch                                                        # ---- hatched
        em = (0.4 + 0.6 * ease_out_back(tt / 0.4)) if tt < 0.4 else 1.0
        sc = em * exit_sc
        pose, dx, dy, sx, sy, ang = baby_motion(sp, i, tt, rel, bl, singing, in_final)
        shadow(frame, cx + dx, ground, Sb * 0.27 * sc * (1 - 0.35 * min(1.0, max(0.0, -dy) / 40)), Sb * 0.04 * sc)
        draw_baby(frame, sp, i, pose, cx, ground, Sb, dx, dy, sx, sy, ang, sc)
        if sp == "bronto":                                                    # the leaf it is munching
            leaf = _leaf()
            bite = 1 - 0.1 * ((rel * 1.2) % 4)
            ls = int(Sb * 0.36 * bite * sc)
            if ls > 8:
                mouth_y = ground + dy - Sb * 562 / 600 * sc + Sb * 0.34 * sc + pose["head_dy"] * 0.4
                leaf = leaf.resize((ls, ls), Image.BILINEAR).rotate(25 + 8 * math.sin(rel * 5.5), resample=Image.BILINEAR)
                frame.paste(leaf, (int(cx + Sb * 0.08 * sc), int(mouth_y)), leaf)
        eggs_b = eggs["bottom"]                                               # bottom half of the shell stays
        paste_rot(frame, eggs_b, (cx, ground), (Se / 2, EGG_BOTTOM * Se), 0, exit_sc)
        if tt < 1.1:                                                          # top half flies away
            fly = 0.0 if i % 2 else 1.0
            vx, vy, g = (140 if i % 2 else -140), -560, 1700
            px = cx + vx * tt
            py = ground + vy * tt + 0.5 * g * tt * tt
            top = eggs["top"]
            if tt < 0.9:
                paste_rot(frame, top, (px, py), (Se / 2, EGG_BOTTOM * Se), (260 if i % 2 else -260) * tt, 1.0)
        d = ImageDraw.Draw(frame)
        if tt < 0.5:
            sparkles(d, cx, ground - Sb * 0.35, tt * 3, n=5, rad=int(Sb * 0.3))
        bscale = ease_out_back((tt - 0.05) / 0.3) * exit_sc
        bob = 4 * math.sin(rel * 3 + i)
        draw_badge(frame, cx, int(ground - Sb * 1.0 - 30 + bob), i + 1, color, 34 if i < 5 else 28, bscale)


def draw_lyrics(frame, V, t):
    d = ImageDraw.Draw(frame)
    name, color, _ = SPECIES_INFO[V["species"]]
    if t < V["t_sing"] + 0.3:                                                  # species name banner
        p = ease_out_back((t - V["t_pre"]) / 0.4)
        if p > 0.02:
            f = get_font(max(14, int(50 * p)))
            wtxt = f.getlength(name) + 80
            d.rounded_rectangle((W / 2 - wtxt / 2, 28, W / 2 + wtxt / 2, 108), radius=40, fill=color, outline=(255, 255, 255), width=6)
            d.text((W / 2, 70), name, font=f, fill=(255, 255, 255), stroke_width=4, stroke_fill=LINE_RGB, anchor="mm")
        return
    cur = 0
    for tk in V["tokens"]:
        if tk["start"] - 0.05 <= t:
            cur = tk["line"]
    words = [tk for tk in V["tokens"] if tk["line"] == cur]
    size = 56
    while True:                                                                # shrink until the line fits the screen
        font = get_font(size)
        space = font.getlength(" ")
        total = sum(font.getlength(w["display"]) for w in words) + space * (len(words) - 1)
        if total <= W - 90 or size <= 30:
            break
        size -= 2
    x = (W - total) / 2
    for w in words:
        wl = font.getlength(w["display"])
        if w["start"] <= t < w["end"] + 0.05:
            fill, lift = (255, 226, 90), -5
        elif t >= w["end"]:
            fill, lift = (255, 214, 238), 0
        else:
            fill, lift = (255, 255, 255), 0
        d.text((x + wl / 2, 70 + lift), w["display"], font=font, fill=fill, stroke_width=9, stroke_fill=LINE_RGB, anchor="mm")
        x += wl + space


# ------------------------------------------------------------------ title / outro
def teaser(frame, t, wave=False):
    d = ImageDraw.Draw(frame)
    for k, sp in enumerate(("steg", "tri", "ptero", "bronto", "trex")):
        cx = FRONT_XS[k]
        h = abs(math.sin(t * 4 + k))
        pose = {"tail": 18 * math.sin(t * 7 + k), "head": 6 * math.sin(t * 3 + k), "mouth": "open" if int(t * 3 + k) % 2 else "closed",
                "eyes": "blink" if blink(k, t) else "open"}
        a = (50 + 25 * math.sin(t * 9 + k)) if wave else 25 + 15 * h
        pose["armL"], pose["armR"] = -a, a
        dy = -26 * h - (30 if sp == "ptero" else 0)
        shadow(frame, cx, 668, 70, 10)
        draw_baby(frame, sp, k, pose, cx, 668, 240, 0, dy, 1, 1 + 0.05 * h, 0, 1.0)


def title_text(frame, text, y, size, t, colors):
    d = ImageDraw.Draw(frame)
    font = get_font(size)
    widths = [font.getlength(c) for c in text]
    x = (W - sum(widths)) / 2
    for k, ch in enumerate(text):
        yy = y - 12 * abs(math.sin(t * 4 + k * 0.6))
        d.text((x + widths[k] / 2, yy), ch, font=font, fill=colors[k % len(colors)], stroke_width=10, stroke_fill=LINE_RGB, anchor="mm")
        x += widths[k]


PASTEL = [(255, 226, 90), (255, 160, 200), (150, 220, 255), (170, 255, 170), (210, 170, 255)]


def intro_frame(tl, t):
    frame = background(0).copy()
    d = ImageDraw.Draw(frame)
    confetti(d, t)
    title_text(frame, "10 Little", 140, 120, t, PASTEL)
    title_text(frame, "Dinosaurs", 262, 128, t + 1, PASTEL[::-1])
    d.rounded_rectangle((W / 2 - 190, 340, W / 2 + 190, 410), radius=35, fill=(255, 140, 190), outline=(255, 255, 255), width=6)
    d.text((W / 2, 376), "A Counting Song", font=get_font(40), fill=(255, 255, 255), stroke_width=4, stroke_fill=LINE_RGB, anchor="mm")
    teaser(frame, t)
    sparkles(d, W // 2, 330, t, n=9, rad=420)
    return frame


def outro_frame(tl, t):
    frame = background(4).copy()
    d = ImageDraw.Draw(frame)
    confetti(d, t)
    title_text(frame, "Bye bye!", 140, 120, t, PASTEL)
    outlined(d, (W // 2, 260), "Thanks for counting with us!", get_font(52), (255, 255, 255), 8)
    outlined(d, (W // 2, 340), "Subscribe for more dino songs!", get_font(38), (255, 240, 170), 6)
    teaser(frame, t, wave=True)
    return frame


# ------------------------------------------------------------------ build
def find_verse(tl, t):
    for k, V in enumerate(tl["verses"]):
        if V["t_pre"] <= t < V["t_end"]:
            return k
    return None


def build(ep_dir):
    ep_dir = Path(ep_dir)
    tl = json.loads((ep_dir / "song_timeline.json").read_text())
    total = tl["total"] + 0.5
    nframes = int(total * FPS)
    nframes = min(nframes, int(os.environ.get("DINO_MAX_FRAMES", nframes)))
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", str(ep_dir / "final_audio.wav"), "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", f"{total:.3f}", str(ep_dir / "video.mp4")]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(nframes):
        t = f / FPS
        if t < tl["intro"]["t1"]:
            frame = intro_frame(tl, t)
        elif t >= tl["outro"]["t0"]:
            frame = outro_frame(tl, t - tl["outro"]["t0"])
        else:
            k = find_verse(tl, t)
            V = tl["verses"][k]
            bgn = V.get("bg", V["index"])
            frame = background(bgn).copy()
            if k > 0 and t < V["t_pre"] + 0.8:                                # soft crossfade between scenes
                a = (t - V["t_pre"]) / 0.8
                frame = Image.blend(background(tl["verses"][k - 1].get("bg", k - 1)), frame, a)
                draw_verse(frame, tl["verses"][k - 1], t, exiting=True)
            draw_verse(frame, V, t)
            d = ImageDraw.Draw(frame)
            if t >= V["t_sing"] + 28 * V["beat"]:
                confetti(d, t)
                sparkles(d, W // 2, 330, t, n=9, rad=430)
            draw_lyrics(frame, V, t)
        proc.stdin.write(frame.convert("RGB").tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        sys.exit("ffmpeg failed")
    segs = [{"segment": "intro", "start": 0.0, "end": round(tl["intro"]["t1"] / total, 4)}]
    names = {"steg": "stegosaurus", "tri": "triceratops", "ptero": "pterodactyl", "bronto": "brontosaurus", "trex": "trex"}
    for V in tl["verses"]:
        segs.append({"segment": names[V["species"]], "start": round(V["t_pre"] / total, 4), "end": round(V["t_end"] / total, 4)})
    segs.append({"segment": "outro", "start": round(tl["outro"]["t0"] / total, 4), "end": 1.0})
    (ep_dir / "segments.json").write_text(json.dumps({"duration": round(total, 2), "segments": segs}, indent=2))
    print(f"Video ready: {ep_dir / 'video.mp4'} ({total / 60:.1f} min)")


# ------------------------------------------------------------------ thumbnail
def thumbnail(ep_dir, tl):
    ep_dir = Path(ep_dir)
    img = ImageEnhance.Color(background(tl["verses"][0].get("bg", 0)).copy()).enhance(1.15)
    rays = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rd = ImageDraw.Draw(rays)
    for k in range(16):
        a0, a1 = math.radians(k * 22.5), math.radians(k * 22.5 + 11)
        rd.polygon([(W / 2, H * 0.62), (W / 2 + 1500 * math.cos(a0), H * 0.62 + 1500 * math.sin(a0)),
                    (W / 2 + 1500 * math.cos(a1), H * 0.62 + 1500 * math.sin(a1))], fill=(255, 250, 190, 90))
    img.paste(rays, (0, 0), rays)
    for k, sp in enumerate(("steg", "tri", "ptero", "bronto", "trex")):
        pose = {"mouth": "open", "armL": -62, "armR": 62, "head": 5 * (-1) ** k, "eyes": "open"}
        comp = Rig.get("baby_" + sp).compose(pose, 320)
        x = int(60 + k * 235 - 80)
        img.paste(comp, (x, H - 330 - (30 if sp == "ptero" else 0)), comp)
    d = ImageDraw.Draw(img)
    for text, y, size, cols in (("10 LITTLE", 105, 135, PASTEL), ("DINOSAURS", 235, 140, PASTEL[::-1])):
        font = get_font(size)
        widths = [font.getlength(c) for c in text]
        x = (W - sum(widths)) / 2
        for k, ch in enumerate(text):
            d.text((x + widths[k] / 2, y), ch, font=font, fill=cols[k % 5], stroke_width=11, stroke_fill=LINE_RGB, anchor="mm")
            x += widths[k]
    d.rounded_rectangle((W / 2 - 230, 305, W / 2 + 230, 380), radius=38, fill=(255, 120, 175), outline=(255, 255, 255), width=6)
    d.text((W / 2, 343), "COUNT 1 TO 10!", font=get_font(44), fill=(255, 255, 255), stroke_width=4, stroke_fill=LINE_RGB, anchor="mm")
    img.convert("RGB").save(ep_dir / "thumbnail.jpg", quality=88)
    print("Thumbnail ready:", ep_dir / "thumbnail.jpg")
