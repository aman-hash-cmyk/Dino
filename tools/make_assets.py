#!/usr/bin/env python3
"""
make_assets.py - writes the Dino Pals artwork as SVG files.

  assets/characters/<id>_closed.svg   600x600, transparent, mouth closed
  assets/characters/<id>_open.svg     600x600, transparent, mouth open (talking)
  assets/backgrounds/<name>.svg       1920x1080

Run once (or whenever you tweak a colour / shape), then run render_assets.py
to turn the SVGs into PNGs. The PNGs are what the video stage uses, so you can
commit them to the repo and never need an SVG renderer in the cloud.
"""
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAR_DIR = ROOT / "assets" / "characters"
BG_DIR = ROOT / "assets" / "backgrounds"
OUT = "#3b2a2a"          # outline colour


# ------------------------------------------------------------------ helpers
def svg(w, h, body, defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'width="{w}" height="{h}"><defs>{defs}</defs>{body}</svg>')


def st(w=6):
    return f'stroke="{OUT}" stroke-width="{w}" stroke-linejoin="round" stroke-linecap="round"'


def shadow(rx=170):
    return f'<ellipse cx="300" cy="562" rx="{rx}" ry="20" fill="#000" opacity="0.18"/>'


def eye(cx, cy, r=32, look=(0, 0), pr=0.5):
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#fff" {st(5)}/>'
            f'<circle cx="{cx + look[0]}" cy="{cy + look[1]}" r="{r * pr}" fill="{OUT}"/>'
            f'<circle cx="{cx + look[0] + r * 0.18}" cy="{cy + look[1] - r * 0.2}" r="{r * 0.17}" fill="#fff"/>')


def cheek(cx, cy, rx=24, ry=15):
    return f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="#ff7f9a" opacity="0.55"/>'


def mouth(cx, y, w, open_, teeth=0):
    if not open_:
        return f'<path d="M{cx - w} {y} Q{cx} {y + w * 0.6} {cx + w} {y}" fill="none" {st(6)}/>'
    d = (f'M{cx - w} {y} Q{cx} {y - w * 0.15} {cx + w} {y} '
         f'Q{cx + w * 0.85} {y + w} {cx} {y + w} Q{cx - w * 0.85} {y + w} {cx - w} {y} Z')
    cid = f"mc{int(cx)}_{int(y)}"
    out = f'<clipPath id="{cid}"><path d="{d}"/></clipPath><path d="{d}" fill="#6b1d2a"/>'
    out += f'<g clip-path="url(#{cid})"><ellipse cx="{cx}" cy="{y + w * 0.98}" rx="{w * 0.58}" ry="{w * 0.4}" fill="#ff8a9a"/>'
    if teeth:
        tw = 2 * w / teeth
        for i in range(teeth):
            x0 = cx - w + i * tw
            out += (f'<polygon points="{x0 + 2},{y - 4} {x0 + tw - 2},{y - 4} {x0 + tw / 2},{y + w * 0.3}" '
                    f'fill="#fff"/>')
    out += '</g>'
    out += f'<path d="{d}" fill="none" {st(6)}/>'
    return out


# ------------------------------------------------------------------ characters
def rexy(o):
    B, D, L = "#E4572E", "#B83A1B", "#FFD9A0"
    s = st()
    p = [shadow()]
    p.append(f'<path d="M400 430 C475 445 545 410 568 330 C535 388 490 392 440 360 Z" fill="{B}" {s}/>')
    for x in (250, 350):
        p.append(f'<rect x="{x - 38}" y="470" width="76" height="85" rx="34" fill="{B}" {s}/>')
        p.append(f'<ellipse cx="{x}" cy="546" rx="54" ry="24" fill="{D}" {s}/>')
        for dx in (-28, 0, 28):
            p.append(f'<circle cx="{x + dx}" cy="554" r="8" fill="#fff" {st(3)}/>')
    p.append(f'<ellipse cx="300" cy="400" rx="125" ry="145" fill="{B}" {s}/>')
    p.append(f'<ellipse cx="300" cy="432" rx="80" ry="104" fill="{L}" {st(4)}/>')
    p.append(f'<g transform="rotate(28 192 405)"><ellipse cx="192" cy="405" rx="32" ry="17" fill="{B}" {s}/></g>')
    p.append(f'<g transform="rotate(-28 408 405)"><ellipse cx="408" cy="405" rx="32" ry="17" fill="{B}" {s}/></g>')
    for sx in (-1, 1):
        cx = 300 + sx * 112
        p.append(f'<circle cx="{cx - sx * 4}" cy="418" r="7" fill="#fff" {st(3)}/>')
    for x, h in ((240, 40), (300, 55), (360, 40)):
        p.append(f'<polygon points="{x - 22},140 {x},{140 - h} {x + 22},140" fill="{D}" {s}/>')
    p.append(f'<ellipse cx="300" cy="235" rx="152" ry="116" fill="{B}" {s}/>')
    p.append(f'<ellipse cx="300" cy="290" rx="102" ry="58" fill="#F27A52" stroke="none"/>')
    p.append(f'<ellipse cx="268" cy="262" rx="8" ry="6" fill="{OUT}"/><ellipse cx="332" cy="262" rx="8" ry="6" fill="{OUT}"/>')
    p.append(eye(232, 204) + eye(368, 204))
    p.append(f'<path d="M196 166 Q232 146 270 164" fill="none" {st(7)}/><path d="M404 166 Q368 146 330 164" fill="none" {st(7)}/>')
    p.append(cheek(185, 270) + cheek(415, 270))
    p.append(mouth(300, 305, 62, o, teeth=6))
    return svg(600, 600, "".join(p))


def trixie(o):
    B, D, L, H = "#2E86AB", "#1F5F7A", "#7CC2DE", "#FFF3D6"
    s = st()
    p = [shadow()]
    p.append(f'<path d="M405 445 C470 455 525 430 548 372 C515 410 470 405 430 385 Z" fill="{B}" {s}/>')
    # frill
    p.append(f'<circle cx="300" cy="222" r="158" fill="{D}" {s}/>')
    for i in range(11):
        a = math.radians(200 + i * 14)
        x, y = 300 + 158 * math.cos(a), 222 + 158 * math.sin(a)
        p.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="14" fill="#F6AE2D" {st(4)}/>')
    for x in (252, 348):
        p.append(f'<rect x="{x - 36}" y="478" width="72" height="78" rx="32" fill="{B}" {s}/>')
        p.append(f'<ellipse cx="{x}" cy="548" rx="50" ry="22" fill="{D}" {s}/>')
    p.append(f'<ellipse cx="300" cy="420" rx="118" ry="132" fill="{B}" {s}/>')
    p.append(f'<ellipse cx="300" cy="445" rx="76" ry="94" fill="{L}" {st(4)}/>')
    p.append(f'<ellipse cx="300" cy="250" rx="118" ry="100" fill="{B}" {s}/>')
    p.append(f'<ellipse cx="300" cy="298" rx="76" ry="52" fill="{L}" {st(4)}/>')
    p.append(f'<polygon points="232,170 208,78 266,150" fill="{H}" {s}/><polygon points="368,170 392,78 334,150" fill="{H}" {s}/>')
    p.append(f'<polygon points="282,262 300,200 318,262" fill="{H}" {s}/>')
    p.append(eye(248, 218, 28) + eye(352, 218, 28))
    p.append(f'<path d="M214 184 Q246 168 276 182" fill="none" {st(6)}/><path d="M386 184 Q354 168 324 182" fill="none" {st(6)}/>')
    p.append(cheek(205, 285) + cheek(395, 285))
    p.append(mouth(300, 312, 42, o))
    return svg(600, 600, "".join(p))


def sam(o):
    B, D, L, P = "#76B041", "#4F8A2A", "#D4EDA6", "#F59E0B"
    s = st()
    p = [shadow()]
    # plates behind body
    for x, y, rot, sz in ((178, 318, -62, 52), (212, 222, -42, 62), (238, 158, -20, 62),
                          (362, 158, 20, 62), (388, 222, 42, 62), (422, 318, 62, 52)):
        p.append(f'<g transform="rotate({rot} {x} {y})"><polygon points="{x},{y - sz} {x + sz * 0.62},{y} {x},{y + sz * 0.5} {x - sz * 0.62},{y}" fill="{P}" {s}/></g>')
    # tail with spikes
    p.append(f'<path d="M415 450 C490 470 545 440 572 385 C535 415 490 410 440 385 Z" fill="{B}" {s}/>')
    for x, y in ((520, 428), (546, 406)):
        p.append(f'<polygon points="{x - 10},{y} {x + 4},{y - 34} {x + 18},{y - 4}" fill="#FFF3D6" {s}/>')
    for x in (222, 378):
        p.append(f'<rect x="{x - 38}" y="480" width="76" height="76" rx="30" fill="{B}" {s}/>')
        p.append(f'<ellipse cx="{x}" cy="548" rx="50" ry="22" fill="{D}" {s}/>')
    p.append(f'<ellipse cx="300" cy="405" rx="142" ry="125" fill="{B}" {s}/>')
    p.append(f'<ellipse cx="300" cy="445" rx="92" ry="78" fill="{L}" {st(4)}/>')
    p.append(f'<ellipse cx="300" cy="268" rx="112" ry="92" fill="{B}" {s}/>')
    p.append(f'<ellipse cx="300" cy="300" rx="70" ry="42" fill="#A5D46F" stroke="none"/>')
    # sleepy eyes (lids cover the top half)
    for cx in (252, 348):
        p.append(eye(cx, 252, 28, look=(0, 6)))
        p.append(f'<path d="M{cx - 31} 252 A31 31 0 0 1 {cx + 31} 252 Z" fill="{B}" {st(5)}/>')
    p.append(cheek(212, 292) + cheek(388, 292))
    p.append(mouth(300, 304, 40, o))
    p.append(f'<g fill="#fff" opacity="0.9" font-family="Arial Black, Arial" font-weight="bold" font-size="30"><text x="395" y="150" transform="rotate(10 395 150)">z</text><text x="425" y="118" font-size="38">Z</text></g>')
    return svg(600, 600, "".join(p))


def pip(o):
    Y, W, M, BK = "#F6AE2D", "#F08A24", "#F8CE6E", "#F59E0B"
    s = st()
    p = [shadow(120)]
    # wings
    left = "M215 375 L22 250 L48 405 Q95 372 120 440 Q150 400 188 455 Q205 420 222 455 Z"
    right = "M385 375 L578 250 L552 405 Q505 372 480 440 Q450 400 412 455 Q395 420 378 455 Z"
    p.append(f'<path d="{left}" fill="{M}" {s}/><path d="{right}" fill="{M}" {s}/>')
    p.append(f'<path d="M215 375 L48 405 M215 375 L120 440 M385 375 L552 405 M385 375 L480 440" fill="none" stroke="{W}" stroke-width="6" stroke-linecap="round"/>')
    for x in (262, 338):
        p.append(f'<ellipse cx="{x}" cy="545" rx="40" ry="16" fill="{BK}" {s}/>')
        p.append(f'<rect x="{x - 10}" y="490" width="20" height="55" rx="9" fill="{BK}" {s}/>')
    p.append(f'<ellipse cx="300" cy="405" rx="88" ry="116" fill="{Y}" {s}/>')
    p.append(f'<ellipse cx="300" cy="430" rx="54" ry="80" fill="#FFF0B8" {st(4)}/>')
    # crest
    p.append(f'<path d="M285 134 Q340 40 440 70 Q380 90 350 140 Z" fill="{W}" {s}/>')
    p.append(f'<circle cx="300" cy="232" r="106" fill="{Y}" {s}/>')
    p.append(eye(252, 212, 31, look=(0, -3), pr=0.55) + eye(348, 212, 31, look=(0, -3), pr=0.55))
    p.append(f'<path d="M218 172 Q250 156 280 170" fill="none" {st(6)}/><path d="M382 172 Q350 156 320 170" fill="none" {st(6)}/>')
    drop = 46 if o else 0
    if o:
        p.append(f'<ellipse cx="300" cy="306" rx="54" ry="44" fill="#6b1d2a" {st(5)}/>')
        p.append(f'<ellipse cx="300" cy="334" rx="32" ry="15" fill="#ff8a9a"/>')
    p.append(f'<path d="M248 292 Q300 {330 + drop} 352 292 Q330 {318 + drop} 300 {322 + drop} Q270 {318 + drop} 248 292 Z" fill="{BK}" {s}/>')
    p.append(f'<path d="M232 258 Q300 232 368 258 Q342 310 300 322 Q258 310 232 258 Z" fill="{BK}" {s}/>')
    p.append(f'<ellipse cx="282" cy="270" rx="6" ry="5" fill="{OUT}"/><ellipse cx="318" cy="270" rx="6" ry="5" fill="{OUT}"/>')
    p.append(cheek(205, 262) + cheek(395, 262))
    return svg(600, 600, "".join(p))


def dina(o):
    SK, HR, PU, TAN = "#E0A878", "#5A3A28", "#9B5DE5", "#D9A94B"
    s = st()
    p = [shadow(120)]
    # ponytail behind head
    p.append(f'<ellipse cx="412" cy="262" rx="34" ry="62" fill="{HR}" {s}/>')
    # legs + boots
    for x in (268, 332):
        p.append(f'<rect x="{x - 20}" y="470" width="40" height="70" rx="14" fill="{SK}" {s}/>')
        p.append(f'<path d="M{x - 30} 545 Q{x - 32} 520 {x - 20} 520 L{x + 20} 520 Q{x + 34} 522 {x + 36} 548 Z" fill="#7A4A2A" {s}/>')
    p.append(f'<rect x="232" y="430" width="136" height="60" rx="24" fill="#C9B27A" {s}/>')
    # torso
    p.append(f'<rect x="222" y="352" width="156" height="132" rx="44" fill="#fff" {s}/>')
    p.append(f'<path d="M222 400 Q222 352 262 352 L282 352 L282 484 L262 484 Q222 484 222 440 Z" fill="{PU}" {s}/>')
    p.append(f'<path d="M378 400 Q378 352 338 352 L318 352 L318 484 L338 484 Q378 484 378 440 Z" fill="{PU}" {s}/>')
    p.append(f'<circle cx="262" cy="410" r="8" fill="#F6AE2D" {st(3)}/><circle cx="338" cy="410" r="8" fill="#F6AE2D" {st(3)}/>')
    # left arm down, right arm up holding a brush
    p.append(f'<path d="M226 380 Q190 420 200 462" fill="none" stroke="{OUT}" stroke-width="40" stroke-linecap="round"/>'
             f'<path d="M226 380 Q190 420 200 462" fill="none" stroke="{SK}" stroke-width="28" stroke-linecap="round"/>')
    p.append(f'<path d="M376 378 Q430 372 446 322" fill="none" stroke="{OUT}" stroke-width="40" stroke-linecap="round"/>'
             f'<path d="M376 378 Q430 372 446 322" fill="none" stroke="{SK}" stroke-width="28" stroke-linecap="round"/>')
    p.append(f'<line x1="446" y1="326" x2="486" y2="236" stroke="#7A4A2A" stroke-width="10" stroke-linecap="round"/>')
    p.append(f'<ellipse cx="490" cy="222" rx="16" ry="28" transform="rotate(22 490 222)" fill="#E4572E" {st(4)}/>')
    p.append(f'<circle cx="446" cy="326" r="19" fill="{SK}" {s}/>')
    p.append(f'<circle cx="200" cy="466" r="19" fill="{SK}" {s}/>')
    p.append(f'<polygon points="520,170 527,190 548,192 531,204 537,225 520,213 503,225 509,204 492,192 513,190" fill="#FFE066" {st(3)}/>')
    # head
    p.append(f'<circle cx="300" cy="245" r="106" fill="{SK}" {s}/>')
    p.append(f'<path d="M194 240 Q196 140 300 134 Q404 140 406 240 Q362 190 300 196 Q238 190 194 240 Z" fill="{HR}" {s}/>')
    # hat
    p.append(f'<path d="M212 152 Q216 62 300 58 Q384 62 388 152 Z" fill="{TAN}" {s}/>')
    p.append(f'<path d="M213 138 Q300 156 387 138 L388 152 Q300 172 212 152 Z" fill="{PU}" {st(4)}/>')
    p.append(f'<ellipse cx="300" cy="156" rx="146" ry="30" fill="{TAN}" {s}/>')
    p.append(f'<path d="M222 140 Q300 168 378 140 L382 154 Q300 182 218 154 Z" fill="{PU}" stroke="none"/>')
    # glasses + eyes
    for cx in (254, 346):
        p.append(f'<circle cx="{cx}" cy="238" r="35" fill="#fff" fill-opacity="0.55" {st(5)}/>')
        p.append(f'<circle cx="{cx}" cy="238" r="15" fill="{OUT}"/><circle cx="{cx + 5}" cy="233" r="5" fill="#fff"/>')
    p.append(f'<path d="M289 236 Q300 228 311 236" fill="none" {st(5)}/>')
    p.append(cheek(222, 288, 20, 13) + cheek(378, 288, 20, 13))
    p.append(mouth(300, 292, 30, o))
    return svg(600, 600, "".join(p))


CHARACTERS = {"rexy": rexy, "trixie": trixie, "sam": sam, "pip": pip, "dina": dina}


# ------------------------------------------------------------------ backgrounds
W, H = 1920, 1080


def grad(gid, stops, x2=0, y2=1):
    s = "".join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in stops)
    return f'<linearGradient id="{gid}" x1="0" y1="0" x2="{x2}" y2="{y2}">{s}</linearGradient>'


def cloud(x, y, sc=1.0, c="#fff", op=0.95):
    return (f'<g transform="translate({x} {y}) scale({sc})" fill="{c}" opacity="{op}">'
            '<ellipse cx="0" cy="0" rx="110" ry="42"/><ellipse cx="-70" cy="10" rx="70" ry="34"/>'
            '<ellipse cx="75" cy="8" rx="80" ry="36"/><ellipse cx="10" cy="-30" rx="62" ry="38"/></g>')


def fern(x, y, sc=1.0, c="#2f8f3a", rot=0):
    leaves = ""
    for i in range(-5, 6):
        a = i * 11
        leaves += (f'<path d="M0 0 Q{40 + abs(i) * 4} -90 0 -230" fill="{c}" transform="rotate({a})" opacity="0.95"/>')
    return f'<g transform="translate({x} {y}) scale({sc}) rotate({rot})">{leaves}</g>'


def tree(x, base, h, trunk="#7a4a2a", leaf="#2f9a46", leaf2="#3fb558"):
    w = h * 0.1
    out = f'<rect x="{x - w / 2}" y="{base - h}" width="{w}" height="{h}" rx="{w / 3}" fill="{trunk}"/>'
    top = base - h
    for dx, dy, r, c in ((-h * .22, 10, h * .24, leaf), (h * .22, 10, h * .24, leaf), (0, -h * .1, h * .3, leaf2),
                         (-h * .1, h * .1, h * .22, leaf2), (h * .12, h * .08, h * .22, leaf)):
        out += f'<circle cx="{x + dx}" cy="{top + dy}" r="{r}" fill="{c}"/>'
    return out


def palm(x, base, h, lean=60):
    cx, cy = x + lean, base - h
    out = (f'<path d="M{x - 14} {base} Q{x + lean * 0.2} {base - h * 0.6} {cx - 8} {cy} L{cx + 8} {cy} '
           f'Q{x + lean * 0.2 + 28} {base - h * 0.6} {x + 14} {base} Z" fill="#8a5a33"/>')
    for a in (-160, -125, -90, -55, -20, 15):
        out += f'<path d="M{cx} {cy} Q{cx + 90} {cy - 70} {cx + 190} {cy + 20} Q{cx + 90} {cy - 20} {cx} {cy} Z" fill="#2fa04a" transform="rotate({a} {cx} {cy})"/>'
    return out


def hills(y, c, amp=80, seed=0, n=5):
    pts = f"M0 {H} L0 {y}"
    for i in range(n):
        x0, x1 = i * W / n, (i + 1) * W / n
        peak = y - amp * (0.5 + 0.5 * math.sin(i * 1.7 + seed))
        pts += f" Q{(x0 + x1) / 2} {peak} {x1} {y + 20 * math.sin(i + seed)}"
    pts += f" L{W} {H} Z"
    return f'<path d="{pts}" fill="{c}"/>'


def bg_jungle():
    d = grad("sky", [(0, "#7fd4ff"), (1, "#eafcff")]) + grad("gr", [(0, "#58b947"), (1, "#2e7d3a")])
    b = f'<rect width="{W}" height="{H}" fill="url(#sky)"/><circle cx="1600" cy="170" r="90" fill="#fff6b0"/>'
    b += cloud(420, 160, 1.1) + cloud(1150, 110, 0.8)
    b += hills(640, "#6bbf7a", 90, 1) + hills(720, "#3f9d52", 70, 3)
    for x, h in ((120, 520), (420, 440), (1500, 540), (1780, 460)):
        b += tree(x, 830, h)
    b += f'<path d="M0 800 Q480 760 960 800 T1920 790 L1920 {H} L0 {H} Z" fill="url(#gr)"/>'
    b += fern(60, 900, 1.2) + fern(1850, 920, 1.3, rot=10) + fern(1650, 1000, 0.8, "#3aa84a")
    for i in range(26):
        x = (i * 211) % W
        y = 880 + (i * 53) % 190
        b += f'<path d="M{x} {y} l6 -26 l6 26 M{x + 14} {y} l6 -20 l6 20" stroke="#2a7a34" stroke-width="5" fill="none" stroke-linecap="round"/>'
    for x, y, c in ((300, 960, "#ff7aa8"), (700, 1020, "#ffd23f"), (1250, 975, "#ff7aa8"), (1580, 1030, "#fff")):
        b += f'<circle cx="{x}" cy="{y}" r="11" fill="{c}"/><circle cx="{x}" cy="{y}" r="4" fill="#f6a800"/>'
    return svg(W, H, b, d)


def bg_volcano():
    d = grad("sky", [(0, "#ff9a5a"), (0.6, "#ffcf8a"), (1, "#ffe9b8")]) + grad("gr", [(0, "#7a4a35"), (1, "#3d2418")])
    d += '<radialGradient id="glow"><stop offset="0" stop-color="#ffb347" stop-opacity="0.9"/><stop offset="1" stop-color="#ffb347" stop-opacity="0"/></radialGradient>'
    b = f'<rect width="{W}" height="{H}" fill="url(#sky)"/>'
    b += cloud(300, 180, 1.2, "#e8b8a0", 0.8) + cloud(1500, 240, 1.0, "#e8b8a0", 0.8)
    b += '<circle cx="960" cy="330" r="330" fill="url(#glow)"/>'
    b += '<polygon points="520,820 800,360 1120,360 1400,820" fill="#5b3a2c"/><polygon points="800,360 960,330 1120,360 1030,400 880,400" fill="#3d2418"/>'
    b += '<path d="M900 380 Q940 480 900 580 Q880 660 930 760 L990 760 Q960 650 990 560 Q1010 470 1000 380 Z" fill="#ff6a2a"/>'
    b += '<path d="M1010 385 Q1060 470 1040 560 Q1030 640 1080 720" stroke="#ffa03a" stroke-width="16" fill="none" stroke-linecap="round"/>'
    for x, y, r in ((930, 300, 70), (990, 230, 80), (1070, 160, 92), (900, 210, 60)):
        b += f'<circle cx="{x}" cy="{y}" r="{r}" fill="#8a7a78" opacity="0.8"/>'
    b += hills(760, "#6a4331", 60, 2)
    b += f'<path d="M0 820 Q480 790 960 830 T1920 810 L1920 {H} L0 {H} Z" fill="url(#gr)"/>'
    b += '<path d="M0 990 Q300 960 520 1000 T1000 1000" stroke="#ff7a30" stroke-width="12" fill="none" stroke-linecap="round" opacity="0.9"/>'
    b += fern(90, 930, 1.1, "#4a6b2a") + fern(1830, 940, 1.2, "#4a6b2a", 8)
    for x, y, r in ((300, 900, 40), (1500, 930, 55), (1650, 880, 34)):
        b += f'<ellipse cx="{x}" cy="{y}" rx="{r * 1.4}" ry="{r}" fill="#5a3a2a"/><ellipse cx="{x - 8}" cy="{y - 8}" rx="{r}" ry="{r * 0.6}" fill="#7a5340"/>'
    return svg(W, H, b, d)


def bg_beach():
    d = grad("sky", [(0, "#5ec8ff"), (1, "#c9f1ff")]) + grad("sea", [(0, "#2ec4c4"), (1, "#1aa0b8")]) + grad("sand", [(0, "#f6e0a4"), (1, "#e8c77a")])
    b = f'<rect width="{W}" height="{H}" fill="url(#sky)"/><circle cx="300" cy="170" r="100" fill="#fff3a0"/>'
    b += cloud(900, 150, 1.0) + cloud(1500, 230, 0.8)
    b += f'<rect y="560" width="{W}" height="260" fill="url(#sea)"/>'
    for i in range(7):
        y = 600 + i * 34
        b += f'<path d="M0 {y} q60 -22 120 0 t120 0 t120 0 t120 0 t120 0 t120 0 t120 0 t120 0 t120 0 t120 0 t120 0 t120 0 t120 0 t120 0 t120 0 t120 0" stroke="#fff" stroke-opacity="0.55" stroke-width="5" fill="none"/>'
    b += f'<path d="M0 800 Q500 770 1000 800 T1920 790 L1920 {H} L0 {H} Z" fill="url(#sand)"/>'
    b += '<path d="M0 800 Q500 770 1000 800 T1920 790" stroke="#fff" stroke-width="10" fill="none" opacity="0.8"/>'
    b += palm(140, 900, 420, 70) + palm(1780, 920, 460, -80)
    for x, y in ((520, 980), (1300, 1010), (1560, 960)):
        b += f'<path d="M{x} {y} q20 -34 40 0 q-20 14 -40 0 Z" fill="#ffb3c1" stroke="#e58aa0" stroke-width="3"/>'
    b += '<polygon points="760,1000 790,950 820,1000" fill="#ff7a59"/><circle cx="790" cy="1002" r="4" fill="#fff"/>'
    return svg(W, H, b, d)


def bg_nest():
    d = grad("sky", [(0, "#ffb88c"), (0.55, "#ffe3b3"), (1, "#fff6dc")]) + grad("gr", [(0, "#88c46a"), (1, "#4f9a4a")])
    b = f'<rect width="{W}" height="{H}" fill="url(#sky)"/><circle cx="1500" cy="380" r="120" fill="#fff0a8" opacity="0.9"/>'
    b += cloud(350, 200, 1.0, "#fff", 0.8) + cloud(1050, 140, 0.8, "#fff", 0.8)
    b += hills(700, "#a8d68a", 90, 0.5) + hills(790, "#6cb55a", 60, 2)
    b += f'<path d="M0 840 Q500 800 1000 840 T1920 820 L1920 {H} L0 {H} Z" fill="url(#gr)"/>'
    b += '<ellipse cx="1500" cy="880" rx="330" ry="86" fill="#8a5a33"/>'
    for i in range(34):
        a = i * 0.57
        x = 1500 + 300 * math.cos(a) * (0.55 + 0.45 * ((i * 7) % 5) / 4)
        y = 880 + 70 * math.sin(a)
        b += f'<path d="M{x - 55} {y - 8} L{x + 55} {y + 8}" stroke="{"#5a3a1c" if i % 2 else "#a8723d"}" stroke-width="12" stroke-linecap="round" transform="rotate({i * 23} {x} {y})"/>'
    for x, c in ((1400, "#f1ead7"), (1520, "#e6f1d7"), (1630, "#f1ead7")):
        b += f'<ellipse cx="{x}" cy="835" rx="52" ry="70" fill="{c}" stroke="#c9b98a" stroke-width="4"/>'
        b += f'<circle cx="{x - 14}" cy="815" r="9" fill="#9ccf7f"/><circle cx="{x + 18}" cy="845" r="7" fill="#9ccf7f"/><circle cx="{x - 4}" cy="862" r="6" fill="#9ccf7f"/>'
    b += fern(100, 930, 1.1) + fern(560, 1010, 0.7, "#3aa84a")
    return svg(W, H, b, d)


def bg_sky():
    d = grad("sky", [(0, "#2a7de1"), (0.6, "#6cc3ff"), (1, "#d6f3ff")])
    b = f'<rect width="{W}" height="{H}" fill="url(#sky)"/><circle cx="1620" cy="190" r="110" fill="#fff6b0"/><circle cx="1620" cy="190" r="150" fill="#fff6b0" opacity="0.25"/>'
    for x, y, s in ((280, 240, 1.4), (900, 160, 1.0), (1300, 420, 1.3), (480, 600, 1.2), (1650, 650, 1.5), (1000, 760, 1.7), (150, 880, 1.6), (1800, 940, 1.4)):
        b += cloud(x, y, s)
    for x, y in ((700, 330), (780, 300), (1120, 250), (1400, 180)):
        b += f'<path d="M{x - 24} {y} q24 -26 24 0 q0 -26 24 0" stroke="#3b2a2a" stroke-width="5" fill="none" stroke-linecap="round"/>'
    return svg(W, H, b, d)


def bg_cave():
    d = grad("wall", [(0, "#2d1f45"), (1, "#4a3566")]) + grad("fl", [(0, "#5a4a6a"), (1, "#2d2238")])
    d += '<radialGradient id="torch"><stop offset="0" stop-color="#ffb347" stop-opacity="0.75"/><stop offset="1" stop-color="#ffb347" stop-opacity="0"/></radialGradient>'
    b = f'<rect width="{W}" height="{H}" fill="url(#wall)"/>'
    b += '<circle cx="320" cy="520" r="420" fill="url(#torch)"/><circle cx="1640" cy="520" r="420" fill="url(#torch)"/>'
    for x in range(-60, W + 100, 150):
        h = 120 + (x * 37) % 160
        b += f'<polygon points="{x},0 {x + 150},0 {x + 75},{h}" fill="#241936"/>'
    for x, y, c in ((520, 760, "#52e0e0"), (600, 790, "#9be8e8"), (1260, 740, "#ff7ad9"), (1340, 790, "#ffb3ec"), (1600, 800, "#52e0e0")):
        b += f'<polygon points="{x},{y} {x + 24},{y - 140} {x + 52},{y - 10} {x + 80},{y}" fill="{c}" opacity="0.9"/>'
    for tx in (320, 1640):
        b += f'<rect x="{tx - 10}" y="520" width="20" height="150" fill="#6a4a2a"/><ellipse cx="{tx}" cy="505" rx="34" ry="52" fill="#ff9a2a"/><ellipse cx="{tx}" cy="515" rx="18" ry="30" fill="#ffe27a"/>'
    b += f'<path d="M0 820 Q500 790 960 830 T1920 810 L1920 {H} L0 {H} Z" fill="url(#fl)"/>'
    for x, y, r in ((200, 960, 50), (900, 1010, 38), (1500, 980, 60)):
        b += f'<ellipse cx="{x}" cy="{y}" rx="{r * 1.4}" ry="{r}" fill="#3a2d4a"/><ellipse cx="{x - 8}" cy="{y - 10}" rx="{r}" ry="{r * 0.55}" fill="#54446a"/>'
    return svg(W, H, b, d)


def bg_museum():
    d = grad("wall", [(0, "#fff1d6"), (1, "#f6dcae")]) + grad("fl", [(0, "#c89a64"), (1, "#8a5f38")])
    b = f'<rect width="{W}" height="{H}" fill="url(#wall)"/><rect y="640" width="{W}" height="120" fill="#b5835a"/>'
    b += f'<rect y="760" width="{W}" height="{H - 760}" fill="url(#fl)"/>'
    for i in range(0, W + 200, 220):
        b += f'<line x1="{i}" y1="760" x2="{(i - 960) * 1.7 + 960}" y2="{H}" stroke="#7a5230" stroke-width="3" opacity="0.5"/>'
    for y in (830, 910, 1000):
        b += f'<line x1="0" y1="{y}" x2="{W}" y2="{y}" stroke="#7a5230" stroke-width="3" opacity="0.4"/>'
    for x in (120, 1500):
        b += f'<rect x="{x}" y="120" width="300" height="400" rx="150" fill="#bfe8ff" stroke="#8a5f38" stroke-width="14"/><line x1="{x + 150}" y1="120" x2="{x + 150}" y2="520" stroke="#8a5f38" stroke-width="8"/><line x1="{x}" y1="330" x2="{x + 300}" y2="330" stroke="#8a5f38" stroke-width="8"/>'
    b += '<rect x="700" y="170" width="190" height="150" fill="#fff" stroke="#8a5f38" stroke-width="12"/><polygon points="740,290 790,210 830,260 855,235 860,290" fill="#76B041"/>'
    b += '<rect x="1020" y="170" width="190" height="150" fill="#fff" stroke="#8a5f38" stroke-width="12"/><circle cx="1115" cy="245" r="42" fill="#E4572E"/>'
    # skeleton on pedestal
    b += '<rect x="760" y="700" width="400" height="60" rx="10" fill="#8a8a92"/>'
    b += '<g stroke="#f4ecd8" stroke-width="14" fill="none" stroke-linecap="round"><path d="M820 690 Q960 520 1100 690"/>'
    for x in range(850, 1081, 36):
        b += f'<path d="M{x} {690 - 80 * math.sin((x - 820) / 280 * math.pi) - 10} L{x} 690"/>'
    b += '<path d="M1100 690 Q1190 650 1240 600 M820 690 L760 640 Q720 600 740 560"/></g>'
    b += '<circle cx="740" cy="560" r="34" fill="#f4ecd8"/><circle cx="728" cy="552" r="8" fill="#3b2a2a"/>'
    return svg(W, H, b, d)


def bg_river():
    d = grad("sky", [(0, "#88d3ff"), (1, "#eafcff")]) + grad("rv", [(0, "#4cb8e8"), (1, "#2a8fc6")]) + grad("gr", [(0, "#62bd4f"), (1, "#2e7d3a")])
    b = f'<rect width="{W}" height="{H}" fill="url(#sky)"/>'
    b += '<polygon points="0,560 260,260 520,560" fill="#8aa6c2"/><polygon points="380,560 740,200 1100,560" fill="#7c98b6"/><polygon points="1000,560 1360,300 1720,560" fill="#8aa6c2"/><polygon points="1480,560 1720,340 1920,560" fill="#7c98b6"/>'
    b += '<polygon points="740,200 690,262 740,250 790,270" fill="#fff"/><polygon points="260,260 225,305 262,295 296,310" fill="#fff"/>'
    b += cloud(1100, 130, 0.9) + cloud(300, 120, 0.8)
    b += hills(650, "#6bbf7a", 70, 4)
    b += tree(150, 800, 460) + tree(1800, 790, 430)
    b += f'<path d="M0 760 Q480 730 960 770 T1920 750 L1920 {H} L0 {H} Z" fill="url(#gr)"/>'
    b += f'<path d="M0 860 Q400 830 800 870 T1920 850 L1920 1010 Q1500 1040 1100 1000 T0 1020 Z" fill="url(#rv)"/>'
    for i in range(6):
        x = 120 + i * 300
        y = 900 + (i % 2) * 60
        b += f'<path d="M{x} {y} q40 -18 80 0 t80 0" stroke="#fff" stroke-opacity="0.7" stroke-width="5" fill="none" stroke-linecap="round"/>'
    for x, y, r in ((220, 1040, 46), (980, 1050, 38), (1620, 1030, 52)):
        b += f'<ellipse cx="{x}" cy="{y}" rx="{r * 1.4}" ry="{r}" fill="#8b8f98"/><ellipse cx="{x - 8}" cy="{y - 10}" rx="{r}" ry="{r * 0.55}" fill="#adb2bb"/>'
    for x in (80, 200, 1700, 1840):
        b += f'<path d="M{x} 1010 l-8 -120 M{x} 1010 l10 -150 M{x} 1010 l26 -110" stroke="#4a8a3a" stroke-width="8" fill="none" stroke-linecap="round"/><ellipse cx="{x + 10}" cy="860" rx="9" ry="26" fill="#7a4a2a"/>'
    return svg(W, H, b, d)


BACKGROUNDS = {"jungle": bg_jungle, "volcano": bg_volcano, "beach": bg_beach, "nest": bg_nest,
               "sky": bg_sky, "cave": bg_cave, "museum": bg_museum, "river": bg_river}


def main():
    CHAR_DIR.mkdir(parents=True, exist_ok=True)
    BG_DIR.mkdir(parents=True, exist_ok=True)
    for cid, fn in CHARACTERS.items():
        (CHAR_DIR / f"{cid}_closed.svg").write_text(fn(False), encoding="utf-8")
        (CHAR_DIR / f"{cid}_open.svg").write_text(fn(True), encoding="utf-8")
    for name, fn in BACKGROUNDS.items():
        (BG_DIR / f"{name}.svg").write_text(fn(), encoding="utf-8")
    print(f"Wrote {len(CHARACTERS) * 2} character SVGs and {len(BACKGROUNDS)} background SVGs to {ROOT / 'assets'}")


if __name__ == "__main__":
    main()
