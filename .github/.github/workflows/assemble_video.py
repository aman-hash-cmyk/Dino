#!/usr/bin/env python3
"""
assemble_video.py - Stage 2: turn script + timeline + audio into an MP4.

  * 1280x720, 24 fps, H.264 + AAC (ffmpeg must be installed)
  * 2.5 s title card -> episode -> 4 s end card
  * the speaking character bounces and opens/closes its mouth in time with the
    real audio loudness (simple lip-sync); the others breathe gently
  * a caption box with the speaker's name is shown while they talk
  * writes segments.json: where intro/adventure/fact/song/outro sit in the video
    (used by analytics.py to learn which part viewers stay for)

Usage:  python assemble_video.py [episode_id]     (default: output/latest.txt)
"""
import json
import math
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
OUT_DIR = ROOT / "output"
BIBLE = json.loads((ROOT / "characters.json").read_text(encoding="utf-8"))
W, H, FPS = 1280, 720, 24
LEAD, TAIL = 2.5, 4.0           # seconds of title card / end card
INK = (59, 42, 42)

FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]
_fonts, _sprites, _bgs = {}, {}, {}


def get_font(size):
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


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def sprite(cid, state, size):
    key = (cid, state, size)
    if key not in _sprites:
        im = Image.open(ASSETS / "characters" / f"{cid}_{state}.png").convert("RGBA")
        _sprites[key] = im.resize((size, size), Image.LANCZOS)
    return _sprites[key]


def background(name):
    if name not in _bgs:
        _bgs[name] = Image.open(ASSETS / "backgrounds" / f"{name}.png").convert("RGB").resize((W, H), Image.LANCZOS)
    return _bgs[name]


def wrap(text, font, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if font.getlength(trial) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def outlined(d, xy, text, font, fill=(255, 255, 255), stroke=8):
    d.text(xy, text, font=font, fill=fill, stroke_width=stroke, stroke_fill=INK, anchor="mm")


def caption_layer(speaker, text):
    c = BIBLE["characters"][speaker]
    col = hex_rgb(c["color"])
    size = 42
    while True:
        font = get_font(size)
        lines = wrap(text, font, W - 240)
        if len(lines) <= 3 or size <= 30:
            break
        size -= 4
    lh = int(size * 1.3)
    h = 62 + len(lines) * lh + 14
    layer = Image.new("RGBA", (W - 120, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((0, 18, W - 121, h - 1), radius=28, fill=(255, 255, 255, 235), outline=col, width=6)
    tag_font = get_font(30)
    tw = int(tag_font.getlength(c["name"])) + 36
    d.rounded_rectangle((24, 0, 24 + tw, 44), radius=20, fill=col)
    d.text((24 + tw / 2, 22), c["name"], font=tag_font, fill=(255, 255, 255), anchor="mm")
    y = 62
    for ln in lines:
        d.text((36, y), ln, font=font, fill=INK)
        y += lh
    return layer


def draw_chars(frame, ids, ta, speaker=None, mouth_open=False, size=None, bounce_all=False):
    n = len(ids)
    base = size or min(420, int(W * 0.92 / n))
    for k, cid in enumerate(ids):
        speaking = cid == speaker
        s = int(base * 1.08) if speaking else base
        img = sprite(cid, "open" if (speaking and mouth_open) else "closed", s)
        if bounce_all:
            dy = -abs(math.sin(ta * 5 + k)) * 18
        elif speaking:
            dy = -abs(math.sin(ta * 9)) * 14
        else:
            dy = math.sin(ta * 2 + k) * 4
        cx = int((k + 1) * W / (n + 1))
        frame.paste(img, (cx - s // 2, int(H - 50 - s * 562 / 600 + dy)), img)


def load_mouth_flags(audio_path):
    """Per-video-frame boolean 'mouth open' flags from the audio loudness (None if silent)."""
    with wave.open(str(audio_path), "rb") as w:
        rate, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
        data = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32)
    if ch > 1:
        data = data[: len(data) // ch * ch].reshape(-1, ch).mean(axis=1)
    win = max(1, int(rate / FPS))
    count = len(data) // win
    if count == 0:
        return None
    rms = np.sqrt((data[: count * win].reshape(count, win) ** 2).mean(axis=1))
    peak = np.percentile(rms, 90)
    if peak < 1:
        return None
    return rms > 0.3 * peak


def build(ep_id):
    ep_dir = OUT_DIR / ep_id
    script = json.loads((ep_dir / "script.json").read_text(encoding="utf-8"))
    timeline = json.loads((ep_dir / "timeline.json").read_text(encoding="utf-8"))
    lines = timeline["lines"]
    audio = ep_dir / "episode_audio.wav"
    audio_total = timeline["total_seconds"]
    total = LEAD + audio_total + TAIL
    nframes = math.ceil(total * FPS)
    flags = load_mouth_flags(audio)

    scene_chars = {}
    for l in lines:
        lst = scene_chars.setdefault(l["scene"], [])
        if l["speaker"] not in lst:
            lst.append(l["speaker"])
    caps = [caption_layer(l["speaker"], l["text"]) for l in lines]
    all_ids = list(BIBLE["characters"])

    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", str(audio),
           "-filter_complex", f"[1:a]adelay={int(LEAD * 1000)}:all=1,apad[a]",
           "-map", "0:v", "-map", "[a]",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
           "-t", f"{total:.3f}", str(ep_dir / "video.mp4")]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    title_lines = wrap(script["title"], get_font(46), W - 200)[:2]
    idx = 0
    for f in range(nframes):
        t = f / FPS
        if t < LEAD:                                       # ---- title card
            frame = background("jungle").copy()
            d = ImageDraw.Draw(frame)
            outlined(d, (W // 2, 130), BIBLE["series"]["title"], get_font(120), (255, 222, 89), 10)
            for i, ln in enumerate(title_lines):
                outlined(d, (W // 2, 250 + i * 58), ln, get_font(46), (255, 255, 255), 6)
            draw_chars(frame, all_ids, t, size=240, bounce_all=True)
        elif t - LEAD >= audio_total:                      # ---- end card
            frame = background("sky").copy()
            d = ImageDraw.Draw(frame)
            outlined(d, (W // 2, 150), "See you tomorrow,", get_font(96), (255, 255, 255), 9)
            outlined(d, (W // 2, 260), BIBLE["series"]["title"] + "!", get_font(110), (255, 222, 89), 10)
            outlined(d, (W // 2, 360), "Subscribe for a new dino adventure every day!", get_font(36), (255, 255, 255), 5)
            draw_chars(frame, all_ids, t, size=240, bounce_all=True)
        else:                                              # ---- story
            ta = t - LEAD
            while idx + 1 < len(lines) and lines[idx + 1]["start"] <= ta:
                idx += 1
            line = lines[idx]
            speaking = line["start"] <= ta < line["end"] + 0.05
            if speaking:
                if flags is None:
                    mouth = int(ta * 6) % 2 == 0
                else:
                    mouth = bool(flags[min(int(ta * FPS), len(flags) - 1)])
            else:
                mouth = False
            frame = background(line["background"]).copy()
            draw_chars(frame, scene_chars[line["scene"]], ta,
                       speaker=line["speaker"] if speaking else None, mouth_open=mouth)
            if speaking or ta < line["end"] + 0.35:
                frame.paste(caps[idx], (60, 24), caps[idx])
        proc.stdin.write(frame.convert("RGB").tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        sys.exit("ffmpeg failed")

    # where each segment sits in the finished video, as fractions 0..1
    spans = {}
    for l in lines:
        a, b = l["start"] + LEAD, l["end"] + LEAD
        s = spans.setdefault(l["segment"], [a, b])
        s[0], s[1] = min(s[0], a), max(s[1], b)
    segs = [{"segment": "title", "start": 0.0, "end": round(LEAD / total, 4)}]
    for name in BIBLE["series"]["segments_in_order"]:
        if name in spans:
            segs.append({"segment": name, "start": round(spans[name][0] / total, 4),
                         "end": round(spans[name][1] / total, 4)})
    segs.append({"segment": "end", "start": round((LEAD + audio_total) / total, 4), "end": 1.0})
    (ep_dir / "segments.json").write_text(json.dumps({"duration": round(total, 2), "segments": segs}, indent=2))
    print(f"Video ready: {ep_dir / 'video.mp4'} ({total / 60:.1f} min)")


if __name__ == "__main__":
    ep = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else \
        (OUT_DIR / "latest.txt").read_text().strip()
    build(ep)
