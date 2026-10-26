#!/usr/bin/env python3
"""Create a branded, high-contrast 1280x720 Dino Pals thumbnail."""
import json
import math
import sys
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from assemble_video import BIBLE, H, INK, OUT_DIR, W, background, get_font, sprite, wrap


def rounded_panel(size, radius=34, fill=(35, 34, 58, 218), outline=(255, 255, 255, 210), width=5):
    panel = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(panel)
    d.rounded_rectangle((2, 2, size[0] - 3, size[1] - 3), radius=radius,
                        fill=fill, outline=outline, width=width)
    return panel


def choose_characters(script):
    counts = Counter(
        line.get("speaker")
        for scene in script.get("scenes", [])
        for line in scene.get("lines", [])
        if line.get("speaker") in BIBLE.get("characters", {})
    )
    ranked = [cid for cid, _ in counts.most_common()]
    if not ranked:
        ranked = list(BIBLE.get("characters", {}))
    main = ranked[0]
    second = ranked[1] if len(ranked) > 1 else None
    return main, second


def fit_title(title, max_width, max_height):
    """Find a readable font size and wrapped lines that fit the title panel."""
    clean = " ".join(str(title).split()).upper() or "A DINO ADVENTURE!"
    for size in range(100, 43, -4):
        font = get_font(size)
        lines = wrap(clean, font, max_width)
        line_height = int(size * 1.08)
        if len(lines) <= 4 and all(font.getlength(line) <= max_width for line in lines):
            if len(lines) * line_height <= max_height:
                return font, lines, line_height
    size = 44
    font = get_font(size)
    lines = wrap(clean, font, max_width)[:4]
    return font, lines, int(size * 1.08)


def build(ep_id):
    ep_dir = OUT_DIR / ep_id
    script_path = ep_dir / "script.json"
    if not script_path.is_file():
        raise FileNotFoundError(f"Episode script not found: {script_path}")
    script = json.loads(script_path.read_text(encoding="utf-8"))
    scenes = script.get("scenes", [])
    if not scenes:
        raise ValueError("The episode script has no scenes.")

    adventure = next((s for s in scenes if s.get("segment") == "adventure"), scenes[0])
    bg_name = adventure.get("background") or scenes[0].get("background") or "jungle"
    img = ImageEnhance.Color(background(bg_name).copy()).enhance(1.22)
    img = ImageEnhance.Contrast(img).enhance(1.08).convert("RGBA")

    # Add a subtle darkening layer at the bottom to keep foreground details clear.
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for y in range(H // 2, H):
        alpha = int(105 * ((y - H / 2) / (H / 2)) ** 1.4)
        sd.line((0, y, W, y), fill=(18, 22, 42, alpha))
    img = Image.alpha_composite(img, shade)

    # Warm sunburst behind the main character, kept to the right of the title.
    rays = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rd = ImageDraw.Draw(rays)
    cx, cy = int(W * 0.77), int(H * 0.56)
    for i in range(18):
        a0 = math.radians(i * 20)
        a1 = math.radians(i * 20 + 9)
        rd.polygon([(cx, cy), (cx + W * 1.1 * math.cos(a0), cy + H * 1.1 * math.sin(a0)),
                    (cx + W * 1.1 * math.cos(a1), cy + H * 1.1 * math.sin(a1))],
                   fill=(255, 239, 150, 62))
    img = Image.alpha_composite(img, rays)

    main, second = choose_characters(script)
    main_size = int(H * 1.02)
    main_img = sprite(main, "open", main_size)
    # Place the main character on the right; let the lower edge crop naturally.
    img.paste(main_img, (int(W * 0.49), H - main_size + int(H * 0.12)), main_img)

    if second:
        second_size = int(H * 0.53)
        second_img = sprite(second, "open", second_size)
        img.paste(second_img, (int(W * 0.43), H - second_size + int(H * 0.02)), second_img)

    # Left-side title panel improves contrast and avoids hiding the main character.
    panel_x, panel_y = 26, 30
    panel_w, panel_h = int(W * 0.56), int(H * 0.78)
    panel = rounded_panel((panel_w, panel_h), radius=38)
    img.paste(panel, (panel_x, panel_y), panel)
    d = ImageDraw.Draw(img)

    brand_font = get_font(28)
    brand = BIBLE.get("series", {}).get("title", "DINO PALS").upper()
    brand_box = (panel_x + 24, panel_y + 22, panel_x + panel_w - 24, panel_y + 68)
    d.rounded_rectangle(brand_box, radius=22, fill=(255, 222, 89, 255), outline=(255, 255, 255, 255), width=3)
    d.text(((brand_box[0] + brand_box[2]) / 2, (brand_box[1] + brand_box[3]) / 2),
           brand, font=brand_font, fill=(55, 42, 48), anchor="mm")

    title = script.get("title", "A Dino Adventure!")
    max_title_width = panel_w - 56
    max_title_height = panel_h - 150
    font, lines, line_height = fit_title(title, max_title_width, max_title_height)
    total_text_height = len(lines) * line_height
    y = panel_y + 92 + max(0, (max_title_height - total_text_height) // 2)
    for line in lines:
        # Text stroke plus a small offset shadow helps at mobile thumbnail size.
        d.text((panel_x + 29, y + 4), line, font=font, fill=(20, 20, 35), stroke_width=5, stroke_fill=(20, 20, 35))
        d.text((panel_x + 26, y), line, font=font, fill=(255, 222, 89),
               stroke_width=5, stroke_fill=(59, 42, 42))
        y += line_height

    # Small corner accent reinforces a playful, consistent brand system.
    d.ellipse((W - 92, 24, W - 34, 82), fill=(255, 128, 171, 245), outline=(255, 255, 255, 255), width=4)
    d.text((W - 63, 53), "!", font=get_font(42), fill=(255, 255, 255), anchor="mm", stroke_width=1, stroke_fill=INK)

    out = ep_dir / "thumbnail.jpg"
    img.convert("RGB").save(out, "JPEG", quality=92, optimize=True)
    print(f"Thumbnail ready: {out} ({W}x{H})")


if __name__ == "__main__":
    episode = sys.argv[1] if len(sys.argv) > 1 else (OUT_DIR / "latest.txt").read_text(encoding="utf-8").strip()
    build(episode)
