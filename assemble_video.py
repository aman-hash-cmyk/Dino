#!/usr/bin/env python3
"""Assemble a 1280x720 dinosaur counting video from episode.json and Piper audio.

Creates a clean pastel vector-inspired scene, five baby-dino silhouettes, captions,
a count badge, and simple frame-by-frame motion. Pillow renders frames to ffmpeg;
ffmpeg muxes the audio.

Install:
  pip install pillow
System requirement: ffmpeg available on PATH.
Run:
  python assemble_video.py --episode-dir output --output output/10_little_dinosaurs.mp4
Optional licensed background track:
  --music path/to/royalty_free_music.wav
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1280, 720, 24
PALETTE = {
    "Stegosaurus": (93, 180, 112),
    "Triceratops": (245, 204, 83),
    "Pterodactyl": (166, 133, 213),
    "Brontosaurus": (69, 181, 174),
    "Tyrannosaurus Rex": (242, 151, 83),
    "All": (115, 184, 130),
}
DINOS = ["Stegosaurus", "Triceratops", "Pterodactyl", "Brontosaurus", "Tyrannosaurus Rex"]


def args_parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--episode-dir", type=Path, default=Path("output"))
    p.add_argument("--output", type=Path, default=Path("output/10_little_dinosaurs.mp4"))
    p.add_argument("--music", type=Path, help="Optional licensed/royalty-free background audio.")
    p.add_argument("--ffmpeg", default="ffmpeg")
    p.add_argument("--fps", type=int, default=FPS)
    p.add_argument("--width", type=int, default=W)
    p.add_argument("--height", type=int, default=H)
    p.add_argument("--music-volume", type=float, default=0.12)
    return p.parse_args()


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def rounded(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], radius: int,
            fill: tuple[int, ...], outline: tuple[int, ...] | None = None, width: int = 1) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def draw_cloud(draw: ImageDraw.ImageDraw, x: int, y: int, scale: float = 1.0) -> None:
    white = (255, 255, 255, 225)
    draw.ellipse((x, y + 15*scale, x + 70*scale, y + 52*scale), fill=white)
    draw.ellipse((x + 18*scale, y, x + 52*scale, y + 45*scale), fill=white)
    draw.ellipse((x + 42*scale, y + 12*scale, x + 87*scale, y + 52*scale), fill=white)


def draw_palm(draw: ImageDraw.ImageDraw, x: int, y: int, scale: float = 1.0) -> None:
    trunk = (164, 130, 91)
    green = (88, 160, 112)
    draw.line((x, y, x + 4*scale, y - 95*scale), fill=trunk, width=max(3, int(10*scale)))
    for angle in [-150, -115, -80, -45, -15]:
        rad = math.radians(angle)
        ex = x + 4*scale + math.cos(rad)*55*scale
        ey = y - 95*scale + math.sin(rad)*35*scale
        draw.line((x + 4*scale, y - 95*scale, ex, ey), fill=green, width=max(3, int(8*scale)))


def draw_dino(draw: ImageDraw.ImageDraw, cx: int, ground: int, color: tuple[int, int, int],
              species: str, scale: float, t: float, index: int) -> None:
    # Tiny bounce and tail wiggle keep the simple vector characters lively.
    bounce = int(math.sin(t * 4.2 + index * 0.8) * 5)
    cx = int(cx)
    y = ground + bounce
    dark = tuple(max(0, c - 35) for c in color)
    outline = (70, 92, 79)
    # Tail and body
    tail_dx = int(math.sin(t * 5 + index) * 8)
    draw.polygon([(cx-35*scale, y-42*scale), (cx-75*scale+tail_dx, y-55*scale),
                  (cx-55*scale, y-25*scale)], fill=color, outline=outline)
    draw.ellipse((cx-58*scale, y-62*scale, cx+35*scale, y-5*scale),
                 fill=color, outline=outline, width=max(1, int(2*scale)))
    # Species-specific features
    if species == "Stegosaurus":
        for dx in [-35, -15, 5, 22]:
            draw.polygon([(cx+dx*scale, y-53*scale), (cx+(dx+10)*scale, y-70*scale),
                          (cx+(dx+20)*scale, y-48*scale)], fill=dark, outline=outline)
    elif species == "Triceratops":
        draw.ellipse((cx+5*scale, y-78*scale, cx+50*scale, y-35*scale),
                     fill=color, outline=outline, width=max(1, int(2*scale)))
        draw.polygon([(cx+18*scale, y-68*scale), (cx+3*scale, y-83*scale),
                      (cx+26*scale, y-70*scale)], fill=(255, 248, 210), outline=outline)
        draw.polygon([(cx+42*scale, y-67*scale), (cx+57*scale, y-82*scale),
                      (cx+49*scale, y-62*scale)], fill=(255, 248, 210), outline=outline)
    elif species == "Pterodactyl":
        wing = int(math.sin(t * 5 + index) * 9)
        draw.polygon([(cx-25*scale, y-40*scale), (cx-70*scale, y-82*scale-wing),
                      (cx-48*scale, y-30*scale)], fill=dark, outline=outline)
        draw.polygon([(cx+5*scale, y-42*scale), (cx+52*scale, y-82*scale+wing),
                      (cx+34*scale, y-24*scale)], fill=dark, outline=outline)
    elif species == "Brontosaurus":
        draw.rounded_rectangle((cx+3*scale, y-115*scale, cx+23*scale, y-38*scale),
                               radius=max(2, int(8*scale)), fill=color, outline=outline,
                               width=max(1, int(2*scale)))
        draw.ellipse((cx-2*scale, y-132*scale, cx+35*scale, y-105*scale),
                     fill=color, outline=outline, width=max(1, int(2*scale)))
        draw.ellipse((cx+22*scale, y-123*scale, cx+27*scale, y-118*scale), fill=(45, 55, 50))
    elif species == "Tyrannosaurus Rex":
        draw.ellipse((cx+5*scale, y-82*scale, cx+47*scale, y-42*scale),
                     fill=color, outline=outline, width=max(1, int(2*scale)))
        draw.ellipse((cx+25*scale, y-67*scale, cx+30*scale, y-62*scale), fill=(40, 50, 45))
        draw.arc((cx+22*scale, y-61*scale, cx+42*scale, y-47*scale),
                 start=0, end=140, fill=(70, 55, 45), width=max(1, int(2*scale)))
    # Feet
    draw.ellipse((cx-38*scale, y-13*scale, cx-12*scale, y+2*scale), fill=dark, outline=outline)
    draw.ellipse((cx+7*scale, y-13*scale, cx+31*scale, y+2*scale), fill=dark, outline=outline)
    # Friendly head and eyes for all species
    if species not in ("Triceratops", "Brontosaurus", "Tyrannosaurus Rex"):
        draw.ellipse((cx+13*scale, y-77*scale, cx+53*scale, y-39*scale),
                     fill=color, outline=outline, width=max(1, int(2*scale)))
    eye_x = cx + 35*scale
    eye_y = y - 62*scale if species != "Brontosaurus" else y - 119*scale
    draw.ellipse((eye_x-3*scale, eye_y-3*scale, eye_x+3*scale, eye_y+3*scale), fill=(35, 48, 42))
    draw.arc((cx+24*scale, y-55*scale, cx+43*scale, y-43*scale),
             start=5, end=150, fill=(75, 55, 45), width=max(1, int(2*scale)))


def draw_scene(t: float, segment: dict[str, Any], segment_index: int,
               width: int, height: int, total_segments: int) -> Image.Image:
    # Pastel vertical gradient.
    top = (181, 229, 250)
    bottom = (255, 242, 202)
    im = Image.new("RGB", (width, height))
    px = im.load()
    for y in range(height):
        r = y / max(1, height - 1)
        c = tuple(int(top[i] * (1-r) + bottom[i] * r) for i in range(3))
        for x in range(width):
            px[x, y] = c
    draw = ImageDraw.Draw(im, "RGBA")
    draw_cloud(draw, 110, 90, 1.0)
    draw_cloud(draw, 930, 120, 0.8)
    draw_palm(draw, 90, 520, 0.8)
    draw_palm(draw, 1170, 535, 0.7)
    # Layered rolling hills.
    draw.ellipse((-180, 420, 650, 790), fill=(174, 220, 151))
    draw.ellipse((420, 440, 1450, 820), fill=(133, 202, 139))
    draw.rectangle((0, 570, width, height), fill=(133, 202, 139))
    # Simple flowers.
    for x, y, col in [(180, 615, (255, 154, 190)), (300, 650, (255, 219, 90)),
                      (1000, 630, (255, 154, 190)), (1100, 660, (255, 219, 90))]:
        draw.line((x, y, x, y+20), fill=(74, 145, 84), width=3)
        for a in range(5):
            ang = a * math.tau / 5
            draw.ellipse((x+math.cos(ang)*7-5, y+math.sin(ang)*7-5,
                          x+math.cos(ang)*7+5, y+math.sin(ang)*7+5), fill=col)
        draw.ellipse((x-4, y-4, x+4, y+4), fill=(255, 225, 126))

    active = segment.get("dinosaur", "All")
    if active not in DINOS:
        active = DINOS[(segment_index // 6) % len(DINOS)]
    color = PALETTE.get(active, PALETTE["All"])
    # Main title
    title_font = load_font(max(28, int(width * 0.043)), True)
    draw.text((width//2, 28), "10 LITTLE DINOSAURS", font=title_font,
              anchor="mt", fill=(55, 91, 91), stroke_width=1, stroke_fill=(255,255,255))
    # Eggs along a row, with the current count highlighted.
    badge_font = load_font(max(20, int(width * 0.028)), True)
    count = segment.get("count")
    if not isinstance(count, int):
        count = min(10, max(1, (segment_index % 10) + 1))
    count = max(1, min(10, count))
    badge_x, badge_y = width - 130, 120
    draw.ellipse((badge_x-62, badge_y-62, badge_x+62, badge_y+62),
                 fill=(255, 255, 255, 225), outline=(255, 255, 255, 255), width=4)
    draw.text((badge_x, badge_y-8), str(count), font=load_font(62, True),
              anchor="mm", fill=color)
    draw.text((badge_x, badge_y+38), "DINOS", font=load_font(16, True),
              anchor="mm", fill=(73, 96, 91))
    # Draw ten tiny spotted eggs, filled when counted.
    egg_start = width//2 - 5*42
    for i in range(10):
        x = egg_start + i*42
        y = 185 + int(math.sin(t*2 + i*0.4)*3)
        egg_color = color if i < count else (238, 238, 223)
        draw.ellipse((x-15, y-22, x+15, y+22), fill=egg_color,
                     outline=(255,255,255,255), width=3)
        draw.ellipse((x-6, y-11, x-1, y-6), fill=(255,255,255,200))
        draw.ellipse((x+4, y+2, x+9, y+7), fill=(255,255,255,200))

    # Row of five baby dinosaurs, current species is prominent.
    xs = [width*0.18, width*0.34, width*0.50, width*0.66, width*0.82]
    for i, species in enumerate(DINOS):
        c = PALETTE[species]
        scale = 0.78 if species == active else 0.54
        ground = 545 if species == active else 560
        draw_dino(draw, int(xs[i]), ground, c, species, scale, t, i)
    # Species label
    label_font = load_font(max(24, int(width * 0.03)), True)
    draw.text((width//2, 470), active.upper(), font=label_font, anchor="mm",
              fill=(59, 90, 77), stroke_width=2, stroke_fill=(255,255,255))
    # Caption card: legible and high contrast.
    text = str(segment.get("text", "Let's count our dinosaur friends!"))
    caption_font = load_font(max(25, int(width * 0.027)), True)
    max_width = width - 150
    words = text.split()
    lines: list[str] = []
    current = ""
    temp_draw = ImageDraw.Draw(im)
    for word in words:
        candidate = f"{current} {word}".strip()
        if temp_draw.textbbox((0, 0), candidate, font=caption_font)[2] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    lines = lines[:2]
    caption_height = 52 + len(lines)*38
    top_y = height - caption_height - 18
    rounded(draw, (42, top_y, width-42, height-18), 24, (255,255,255,235),
            outline=(255,255,255,255), width=2)
    for i, line in enumerate(lines):
        draw.text((width//2, top_y+26+i*38), line, font=caption_font,
                  anchor="mt", fill=(51, 78, 81))
    return im


def run() -> int:
    args = args_parse()
    if not shutil.which(args.ffmpeg):
        print("ffmpeg was not found on PATH. Install ffmpeg and retry.", file=sys.stderr)
        return 2
    manifest_path = args.episode_dir / "episode.json"
    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}. Run make_episode.py first.", file=sys.stderr)
        return 2
    episode = json.loads(manifest_path.read_text(encoding="utf-8"))
    segments = episode.get("segments", [])
    if not segments:
        print("episode.json contains no segments.", file=sys.stderr)
        return 2
    voice = args.episode_dir / episode.get("voice_file", "audio/vocals.wav")
    if not voice.exists():
        print(f"Voice audio not found: {voice}", file=sys.stderr)
        return 2

    duration = float(episode.get("total_duration", 0))
    if duration <= 0:
        duration = sum(float(s.get("duration", 0)) for s in segments)
    if duration <= 0:
        print("Invalid or missing episode duration in episode.json.", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    width, height, fps = args.width, args.height, args.fps
    frame_count = math.ceil(duration * fps)
    starts = [float(s.get("start", 0)) for s in segments]
    durations = [float(s.get("duration", 0)) for s in segments]
    # Raw RGB frames streamed directly to ffmpeg; avoids creating thousands of PNGs.
    cmd = [
        args.ffmpeg, "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}",
        "-r", str(fps), "-i", "-", "-i", str(voice),
    ]
    has_music = bool(args.music and args.music.exists())
    if has_music:
        cmd += ["-stream_loop", "-1", "-i", str(args.music)]
    if has_music:
        vol = max(0.0, min(1.0, args.music_volume))
        cmd += ["-filter_complex",
                f"[1:a]volume=1.0[v];[2:a]volume={vol}[m];[v][m]amix=inputs=2:duration=first:dropout_transition=2[a]"]
        audio_map = "[a]"
    else:
        audio_map = "1:a:0"
    cmd += [
        "-map", "0:v:0", "-map", audio_map, "-c:v", "libx264",
        "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
        str(args.output),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for frame_no in range(frame_count):
            t = frame_no / fps
            idx = 0
            for j, start in enumerate(starts):
                if start <= t:
                    idx = j
                else:
                    break
            segment = segments[idx]
            frame = draw_scene(t, segment, idx, width, height, len(segments))
            assert proc.stdin is not None
            proc.stdin.write(frame.convert("RGB").tobytes())
    except BrokenPipeError:
        pass
    finally:
        if proc.stdin:
            proc.stdin.close()
    return_code = proc.wait()
    if return_code:
        print(f"ffmpeg failed with exit code {return_code}", file=sys.stderr)
        return return_code
    print(f"Created video: {args.output}")
    print(f"Resolution: {width}x{height} | FPS: {fps} | Duration: {duration:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
