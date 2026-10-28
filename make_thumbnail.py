#!/usr/bin/env python3
"""
make_thumbnail.py - builds a 1280x720 JPEG thumbnail for an episode:
scene background, the two characters who talk most, and a big bold title.

Usage:  python make_thumbnail.py [episode_id]
"""
import json
import sys
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance

from assemble_video import BIBLE, H, INK, OUT_DIR, W, background, get_font, wrap
from rig import Rig


def build(ep_id):
    ep_dir = OUT_DIR / ep_id
    script = json.loads((ep_dir / "script.json").read_text(encoding="utf-8"))

    bg_name = next((s["background"] for s in script["scenes"] if s["segment"] == "adventure"),
                   script["scenes"][0]["background"])
    img = ImageEnhance.Color(background(bg_name).copy()).enhance(1.3)

    counts = Counter(l["speaker"] for s in script["scenes"] for l in s["lines"])
    ranked = [c for c, _ in counts.most_common()]
    main = ranked[0]
    second = ranked[1] if len(ranked) > 1 else None

    # sunburst behind the main character
    rays = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rd = ImageDraw.Draw(rays)
    cx, cy = W - 330, H - 330
    import math
    for i in range(16):
        a0, a1 = math.radians(i * 22.5), math.radians(i * 22.5 + 11)
        rd.polygon([(cx, cy), (cx + 1200 * math.cos(a0), cy + 1200 * math.sin(a0)),
                    (cx + 1200 * math.cos(a1), cy + 1200 * math.sin(a1))], fill=(255, 245, 160, 110))
    img.paste(rays, (0, 0), rays)

    big = Rig.get(main).compose({"mouth": "open", "eyes": "wide", "brows": "up", "armL": -75, "armR": 75, "head": 6}, 700)
    img.paste(big, (W - 700 + 40, H - 700 + 70), big)
    if second:
        small = Rig.get(second).compose({"mouth": "open", "brows": "up", "armL": -30, "armR": 80, "head": -6}, 380)
        img.paste(small, (10, H - 380 + 40), small)

    # title text: uppercase, auto-shrink to fit the left side
    text = script["title"].upper()
    d = ImageDraw.Draw(img)
    size = 110
    while size > 48:
        font = get_font(size)
        lines = wrap(text, font, 660)
        if len(lines) * size * 1.12 <= 340 and all(font.getlength(l) <= 660 for l in lines):
            break
        size -= 6
    y = 60
    for ln in lines:
        d.text((40, y), ln, font=font, fill=(255, 222, 89), stroke_width=10, stroke_fill=INK)
        y += int(size * 1.12)

    out = ep_dir / "thumbnail.jpg"
    img.save(out, quality=88)
    print("Thumbnail ready:", out)


if __name__ == "__main__":
    ep = sys.argv[1] if len(sys.argv) > 1 else (OUT_DIR / "latest.txt").read_text().strip()
    build(ep)
