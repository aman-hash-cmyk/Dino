#!/usr/bin/env python3
"""
assemble_video.py - Stage 2: turn script + timeline + audio into an MP4.

  * 1280x720, 24 fps, H.264 + AAC (ffmpeg must be installed)
  * characters are animated puppets (rig.py): the head nods with the voice, arms/wings gesture,
    they jump with squash-and-stretch, blink, raise eyebrows, open their mouth to the real
    loudness of the voice, and their friends cheer along when something exciting happens
  * picture props pop up when the script names something (leaf, egg, bone ...)
  * "YOUR TURN!" moments: a countdown while the speaker waits, listening
  * song segment: big sing-along words, dancing characters, floating music notes
  * original background music (music.py) that ducks under speech, plus sound effects
  * writes segments.json: where intro/adventure/fact/song/outro sit in the video

Usage:  python assemble_video.py [episode_id]     (default: output/latest.txt)
"""
import json
import math
import os
import random
import subprocess
import sys
import wave
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

import music
from rig import Rig

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
OUT_DIR = ROOT / "output"
BIBLE = json.loads((ROOT / "characters.json").read_text(encoding="utf-8"))
W, H, FPS = 1280, 720, 24
LEAD, TAIL = 2.5, 4.0           # seconds of title card / end card
INK = (59, 42, 42)
SR = music.SR

FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]
SONG_COLORS = [(255, 222, 89), (255, 128, 171), (120, 220, 255), (160, 255, 140)]
GESTURES = ["wave", "open", "point", "swing", "cheer"]
_fonts, _bgs, _props, _shadows = {}, {}, {}, {}


# ------------------------------------------------------------------ small helpers
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


def background(name):
    if name not in _bgs:
        im = Image.open(ASSETS / "backgrounds" / f"{name}.png").convert("RGB").resize((W, H), Image.LANCZOS)
        im = ImageEnhance.Brightness(ImageEnhance.Contrast(ImageEnhance.Color(im).enhance(1.45)).enhance(1.08)).enhance(1.06)
        _bgs[name] = im                                    # extra vibrant and bright
    return _bgs[name]


def prop_img(name, size):
    key = (name, size)
    if key not in _props:
        _props[key] = Image.open(ASSETS / "props" / f"{name}.png").convert("RGBA").resize((size, size), Image.LANCZOS)
    return _props[key]


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


def ease_out_back(x):
    x = max(0.0, min(1.0, x))
    c1 = 1.70158
    return 1 + (c1 + 1) * (x - 1) ** 3 + c1 * (x - 1) ** 2


# ------------------------------------------------------------------ text layers
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


def song_layer(text, color):
    font = get_font(58)
    lines = wrap(text, font, W - 200)[:3]
    layer = Image.new("RGBA", (W, 30 + len(lines) * 76), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i, ln in enumerate(lines):
        outlined(d, (W // 2, 44 + i * 76), ln, font, color, 9)
    return layer


def your_turn_layer():
    layer = Image.new("RGBA", (560, 130), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((4, 4, 555, 125), radius=60, fill=(255, 92, 140, 245), outline=(255, 255, 255), width=8)
    outlined(d, (280, 66), "Your turn!", get_font(72), (255, 255, 255), 8)
    return layer


# ------------------------------------------------------------------ effects
def star4(d, x, y, r, color):
    d.polygon([(x, y - r), (x + r * .3, y - r * .3), (x + r, y), (x + r * .3, y + r * .3),
               (x, y + r), (x - r * .3, y + r * .3), (x - r, y), (x - r * .3, y - r * .3)], fill=color)


def sparkles(d, cx, cy, t, n=7, rad=170):
    cols = [(255, 240, 120), (255, 255, 255), (255, 170, 210), (170, 235, 255)]
    for i in range(n):
        a = t * 2.2 + i * 2 * math.pi / n
        r = rad + 25 * math.sin(t * 5 + i)
        s = 11 + 8 * abs(math.sin(t * 6 + i * 1.7))
        star4(d, cx + r * math.cos(a), cy - 60 + 0.6 * r * math.sin(a), s, cols[i % 4])


def music_notes(d, t):
    cols = [(255, 222, 89), (255, 128, 171), (120, 220, 255), (160, 255, 140)]
    for i in range(7):
        x = (i * 191 + 60 + 25 * math.sin(t * 1.5 + i)) % W
        y = H - ((t * 70 + i * 97) % (H - 100)) - 20
        c = cols[i % 4]
        d.ellipse((x - 11, y - 8, x + 11, y + 8), fill=c, outline=INK, width=3)
        d.line((x + 10, y, x + 10, y - 38), fill=INK, width=4)
        d.polygon([(x + 10, y - 38), (x + 26, y - 28), (x + 10, y - 24)], fill=c, outline=INK)


_confetti = None


def confetti(d, t):
    global _confetti
    if _confetti is None:
        rnd = random.Random(7)
        cols = [(255, 92, 140), (255, 222, 89), (90, 200, 255), (130, 230, 120), (190, 120, 255)]
        _confetti = [(rnd.random() * W, rnd.random() * H, 60 + rnd.random() * 90, 6 + rnd.random() * 8,
                      cols[rnd.randrange(5)]) for _ in range(55)]
    for x, y0, sp, s, c in _confetti:
        y = (y0 + t * sp) % H
        xx = x + 18 * math.sin(t * 2 + y0)
        d.ellipse((xx - s, y - s * .6, xx + s, y + s * .6), fill=c)


def draw_prop(frame, name, tl):
    size = int(190 * ease_out_back(tl / 0.35) * (1 + 0.04 * math.sin(tl * 5)))
    if size < 20:
        return
    cx, cy = W // 2, 300
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    r = int(size * 0.66)
    ImageDraw.Draw(glow).ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 255, 255, 215),
                                 outline=(255, 222, 89, 255), width=8)
    frame.paste(glow, (0, 0), glow)
    img = prop_img(name, size)
    frame.paste(img, (cx - size // 2, cy - size // 2), img)


# ------------------------------------------------------------------ puppet animation
def arm_raise(g, tl, big=1.0):
    """(left, right) arm raise in degrees for a gesture."""
    s = math.sin
    if g == "wave":
        return 6.0, 68 + 22 * s(tl * 9) * big
    if g == "open":
        a = 44 + 10 * s(tl * 5) * big
        return a, a
    if g == "point":
        return 4.0, 98 + 8 * s(tl * 4)
    if g == "swing":
        return 28 + 26 * s(tl * 6) * big, 28 + 26 * s(tl * 6 + math.pi) * big
    if g == "cheer":
        a = 105 + 24 * s(tl * 10) * big
        return a, a
    return 4.0, 4.0


def is_blink(k, t):
    return ((t + k * 0.9) % 3.6) < 0.16


def pose_for(cid, k, ta, c):
    """Everything one character does at time ta. Returns (pose, dy, sx, sy, scale)."""
    s = math.sin
    is_speaker = cid == c.speaker
    pose = {"head": 2.5 * s(ta * 0.8 + k), "tail": 7 * s(ta * 1.7 + k), "plates": 3 * s(ta * 1.3 + k),
            "mouth": "closed", "eyes": "blink" if is_blink(k, ta) else "open", "brows": "norm", "head_dy": 0.0}
    aL, aR = 3 + 2 * s(ta * 1.1 + k), 3 + 2 * s(ta * 1.3 + k + 1)
    if cid == "pip":
        aL = aR = 6 + 5 * s(ta * 5 + k)
    dy, scale = 0.0, 1.0
    sy = 1 + 0.012 * s(ta * 2 + k)                        # breathing
    sx = 1 / sy

    if c.song:                                            # everybody dances
        h = abs(s(ta * 4 + k))
        dy = -14 * h
        pose["head"] = 8 * s(ta * 4 + k + 1)
        aL, aR = 30 + 30 * s(ta * 4 + k), 30 + 30 * s(ta * 4 + k + math.pi)
        if cid == "pip":
            aL = aR = 25 + 25 * s(ta * 8 + k)
        sy = 1 + 0.05 * h - 0.06 * max(0.0, 1 - h * 4)
        sx = 1 / sy
        pose["brows"] = "up" if s(ta * 2 + k) > 0.3 else "norm"
    elif c.speaking and not is_speaker and c.emo in ("excited", "surprised"):   # friends cheer along
        h = abs(s(ta * 8 + k))
        dy = -9 * h
        aL = aR = 40 + 15 * s(ta * 8 + k)
        if cid == "pip":
            aL = aR = 25 + 20 * s(ta * 14 + k)
        pose["brows"] = "up"

    if is_speaker and c.speaking:
        tl = c.tl
        big = 1.5 if c.emo in ("excited", "silly") else 1.0
        scale = 1.08
        aL, aR = arm_raise(c.gesture, tl, big)
        if cid == "pip":
            aL = aR = 20 + 26 * s(tl * 14) * big
        pose["head"] = 4 * s(tl * 5) + (10 if c.question else 0)
        pose["head_dy"] = -7 * c.loud                      # nod with the voice
        dy = -6 * abs(s(tl * 9))
        pose["brows"] = "up" if c.question else "norm"
        if c.emo == "excited":
            h = abs(s(tl * 7))
            dy = -30 * h                                   # jump
            sy = 1 + 0.10 * h - 0.12 * max(0.0, 1 - h * 5)  # stretch in the air, squash on landing
            sx = 1 / sy
            if s(tl * 6) > 0:
                pose["brows"] = "up"
        elif c.emo == "silly":
            pose["head"] = 12 * s(tl * 11)
            aL, aR = arm_raise("swing", tl, 1.6)
            if cid == "pip":
                aL = aR = 30 + 30 * s(tl * 12)
        elif c.emo == "surprised":
            pop = max(0.0, 1 - tl / 0.45)
            dy -= 44 * s(math.pi * min(1.0, tl / 0.45))    # jump back in surprise
            scale += 0.15 * pop
            pose["eyes"], pose["brows"] = "wide", "up"
            aL, aR = 80 * pop + aL * (1 - pop), 80 * pop + aR * (1 - pop)
        if c.open_now:
            pose["mouth"] = "oh" if c.emo == "surprised" else "open"
    elif is_speaker and c.in_pause:                        # waiting, listening for the child's answer
        aL, aR = 4.0, 105.0
        if cid == "pip":
            aL = aR = 30.0
        pose["head"] = 10 + 4 * s(ta * 3)
        pose["brows"] = "up"
        if pose["eyes"] == "open":
            pose["eyes"] = "wide"
        dy, scale = -5 * abs(s(ta * 4)), 1.05

    pose["armL"] = -aL
    pose["armR"] = (aR - 55) * 0.55 if cid == "dina" else aR   # Dina already holds her brush up
    return pose, dy, sx, sy, scale


def draw_shadow(frame, cid, cx, S, scale, dy):
    rx = int(S * (120 if cid in ("pip", "dina") else 170) / 600 * scale * (1 - 0.35 * min(1.0, max(0.0, -dy) / 40)))
    ry = max(4, int(S * 20 / 600 * scale))
    if (rx, ry) not in _shadows:
        im = Image.new("RGBA", (rx * 2, ry * 2), (0, 0, 0, 0))
        ImageDraw.Draw(im).ellipse((0, 0, rx * 2 - 1, ry * 2 - 1), fill=(0, 0, 0, 55))
        _shadows[(rx, ry)] = im
    sh = _shadows[(rx, ry)]
    frame.paste(sh, (cx - rx, H - 50 - ry), sh)


def draw_char(frame, cid, S, pose, cx, dy, sx, sy, scale):
    comp = Rig.get(cid).compose(pose, S)
    w, h = int(S * scale * sx), int(S * scale * sy)
    if (w, h) != (S, S):
        comp = comp.resize((w, h), Image.BILINEAR)
    ax, ay = S / 2 * scale * sx, S * 562 / 600 * scale * sy
    frame.paste(comp, (int(cx - ax), int(H - 50 + dy - ay)), comp)


def load_audio_features(audio_path):
    """Per-video-frame 'mouth open' flags and loudness 0..1 from the voice (None, None if silent)."""
    with wave.open(str(audio_path), "rb") as w:
        rate, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
        data = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32)
    if ch > 1:
        data = data[: len(data) // ch * ch].reshape(-1, ch).mean(axis=1)
    win = max(1, int(rate / FPS))
    count = len(data) // win
    if count == 0:
        return None, None
    rms = np.sqrt((data[: count * win].reshape(count, win) ** 2).mean(axis=1))
    peak = np.percentile(rms, 90)
    if peak < 1:
        return None, None
    return rms > 0.3 * peak, np.clip(rms / (peak * 1.2), 0, 1)


# ------------------------------------------------------------------ audio mix
def mix_audio(ep_dir, lines, total, audio_total):
    """voice + original music (ducked under speech) + sound effects -> stereo wav."""
    with wave.open(str(ep_dir / "episode_audio.wav"), "rb") as w:
        rate, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
        v = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        v = v[: len(v) // ch * ch].reshape(-1, ch).mean(axis=1)
    if len(v) > 1 and rate != SR:
        v = np.interp(np.arange(int(len(v) * SR / rate)) * rate / SR, np.arange(len(v)), v).astype(np.float32)
    peak = float(np.max(np.abs(v))) if len(v) else 0.0
    if peak > 0:
        v = v * (0.85 / peak)

    n_total = int(total * SR)
    voice = np.zeros(n_total, dtype=np.float32)
    off = int(LEAD * SR)
    k = min(len(v), n_total - off)
    if k > 0:
        voice[off:off + k] = v[:k]

    firsts, seen = [], set()                               # music sections follow the story segments
    for l in lines:
        if l["segment"] not in seen:
            seen.add(l["segment"])
            firsts.append((l["segment"], l["start"] + LEAD))
    sections = [(0.0, LEAD, "title")]
    for i, (seg, st) in enumerate(firsts):
        en = firsts[i + 1][1] if i + 1 < len(firsts) else LEAD + audio_total
        sections.append((st, en, seg if seg in music.STYLES else "adventure"))
    sections.append((LEAD + audio_total, total, "end"))
    track = music.render(sections, total)
    if len(track) < n_total:
        track = np.pad(track, (0, n_total - len(track)))
    track = track[:n_total]

    blk = int(0.02 * SR)                                   # duck the music while someone talks
    nb = n_total // blk
    env = np.abs(voice[: nb * blk]).reshape(nb, blk).mean(axis=1)
    speech = np.convolve((env > 0.02).astype(np.float32), np.ones(12) / 12, mode="same")
    gain = 0.62 - 0.40 * np.clip(speech, 0, 1)
    gain = np.interp(np.arange(n_total) / blk, np.arange(nb) + 0.5, gain).astype(np.float32)
    mixed = voice + track * gain

    events = [(0.35, "sparkle")]                           # sound effects
    for i, l in enumerate(lines):
        t0 = l["start"] + LEAD
        prev = lines[i - 1] if i else None
        if prev and l["scene"] != prev["scene"]:
            events.append((t0 - 0.4, "whoosh"))
        if l.get("show"):
            events.append((t0 + 0.05, "pop"))
        if l.get("emotion") == "excited":
            events.append((t0, "sparkle"))
        if l.get("emotion") == "silly":
            events.append((t0, "boing"))
        if l.get("pause", 0) > 0:
            events.append((l["end"] + LEAD + 0.2, "ding"))
        if prev and prev.get("pause", 0) > 0:
            events.append((t0 - 0.05, "sparkle"))
    cache = {}
    for t, name in events:
        if name not in cache:
            cache[name] = music.sfx(name)
        music.put(mixed, cache[name] * 0.55, max(0.0, t) * SR)

    top = float(np.max(np.abs(mixed))) or 1.0
    if top > 0.95:
        mixed = mixed * (0.95 / top)
    out = ep_dir / "final_audio.wav"
    with wave.open(str(out), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.stack([mixed, mixed], axis=1) * 32767).astype(np.int16).tobytes())
    return out


# ------------------------------------------------------------------ main build
def quant_size(base):
    return max(200, int(round(base / 20.0) * 20))


def build(ep_id):
    ep_dir = OUT_DIR / ep_id
    script = json.loads((ep_dir / "script.json").read_text(encoding="utf-8"))
    timeline = json.loads((ep_dir / "timeline.json").read_text(encoding="utf-8"))
    lines = timeline["lines"]
    audio_total = timeline["total_seconds"]
    total = LEAD + audio_total + TAIL
    nframes = math.ceil(total * FPS)
    nframes = min(nframes, int(os.environ.get("DINO_MAX_FRAMES", nframes)))   # (testing aid)
    flags, loud = load_audio_features(ep_dir / "episode_audio.wav")

    print("Mixing music and sound effects ...")
    final_audio = mix_audio(ep_dir, lines, total, audio_total)

    scene_chars, scene_start = {}, {}
    for l in lines:
        lst = scene_chars.setdefault(l["scene"], [])
        if l["speaker"] not in lst:
            lst.append(l["speaker"])
        scene_start.setdefault(l["scene"], l["start"])
    caps = [caption_layer(l["speaker"], l["text"]) for l in lines]
    song_caps = [song_layer(l["text"], SONG_COLORS[i % 4]) for i, l in enumerate(lines)]
    your_turn = your_turn_layer()
    white = Image.new("RGB", (W, H), (255, 255, 255))
    all_ids = list(BIBLE["characters"])

    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", str(final_audio), "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
           "-t", f"{total:.3f}", str(ep_dir / "video.mp4")]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    title_lines = wrap(script["title"], get_font(46), W - 200)[:2]
    idx = 0
    for f in range(nframes):
        t = f / FPS
        if t < LEAD or t - LEAD >= audio_total:            # ---- title card / end card
            title = t < LEAD
            frame = background("jungle" if title else "sky").copy()
            d = ImageDraw.Draw(frame)
            confetti(d, t)
            if title:
                outlined(d, (W // 2, 130), BIBLE["series"]["title"], get_font(120), (255, 222, 89), 10)
                for i, ln in enumerate(title_lines):
                    outlined(d, (W // 2, 250 + i * 58), ln, get_font(46), (255, 255, 255), 6)
            else:
                outlined(d, (W // 2, 150), "See you tomorrow,", get_font(96), (255, 255, 255), 9)
                outlined(d, (W // 2, 260), BIBLE["series"]["title"] + "!", get_font(110), (255, 222, 89), 10)
                outlined(d, (W // 2, 360), "Subscribe for a new dino adventure every day!", get_font(36), (255, 255, 255), 5)
            c = SimpleNamespace(speaker=None, speaking=False, in_pause=False, song=True, emo="happy", tl=0,
                                loud=0, open_now=False, gesture="cheer", question=False)
            for k, cid in enumerate(all_ids):
                cx = int((k + 1) * W / (len(all_ids) + 1))
                pose, dy, sx, sy, sc = pose_for(cid, k, t, c)
                pose["brows"] = "up"
                pose["mouth"] = "open" if int(t * 3 + k) % 2 else "closed"
                draw_shadow(frame, cid, cx, 240, sc, dy)
                draw_char(frame, cid, 240, pose, cx, dy, sx, sy, sc)
            sparkles(d, W // 2, 320, t, n=9, rad=420)
        else:                                              # ---- story
            ta = t - LEAD
            while idx + 1 < len(lines) and lines[idx + 1]["start"] <= ta:
                idx += 1
            line = lines[idx]
            emo = line.get("emotion", "happy")
            pause = line.get("pause", 0) or 0
            tl = ta - line["start"]
            speaking = line["start"] <= ta < line["end"] + 0.05
            in_pause = pause > 0 and line["end"] <= ta < line["end"] + pause
            song = line["segment"] == "song"
            show = line.get("show") if line["start"] <= ta < line["end"] + pause + 0.6 else None
            question = line["text"].strip().endswith("?")
            fi = int(ta * FPS)
            if flags is None:
                open_now, lv = int(ta * 6) % 2 == 0, 0.5 + 0.5 * math.sin(ta * 12)
            else:
                fi = min(fi, len(flags) - 1)
                open_now, lv = bool(flags[fi]), float(loud[fi])
            c = SimpleNamespace(speaker=line["speaker"], speaking=speaking, in_pause=in_pause, song=song, emo=emo,
                                tl=tl, loud=lv, open_now=open_now, question=question,
                                gesture="open" if question else GESTURES[(idx * 3 + 1) % 5])

            frame = background(line["background"]).copy()
            ids = scene_chars[line["scene"]]
            n = len(ids)
            S = quant_size(min(300 if show else 420, int(W * 0.92 / n)))
            if song:
                music_notes(ImageDraw.Draw(frame), ta)

            poses = []
            for k, cid in enumerate(ids):
                cx = int((k + 1) * W / (n + 1))
                pose, dy, sx, sy, sc = pose_for(cid, k, ta, c)
                draw_shadow(frame, cid, cx, S, sc, dy)
                poses.append((cid, cx, pose, dy, sx, sy, sc))
            for cid, cx, pose, dy, sx, sy, sc in poses:
                draw_char(frame, cid, S, pose, cx, dy, sx, sy, sc)

            d = ImageDraw.Draw(frame)
            sk = ids.index(line["speaker"])
            if speaking and emo in ("excited", "surprised"):
                sparkles(d, int((sk + 1) * W / (n + 1)), H - 250, ta, n=7, rad=150)
            if in_pause:
                sparkles(d, int((sk + 1) * W / (n + 1)), H - 250, ta, n=5, rad=140)

            if in_pause:                                   # "Your turn!" + countdown dots
                p = (ta - line["end"]) / pause
                s = 1 + 0.05 * math.sin(ta * 8)
                yt = your_turn.resize((int(560 * s), int(130 * s)))
                frame.paste(yt, (W // 2 - yt.width // 2, 28), yt)
                for j in range(3):
                    x = W // 2 + (j - 1) * 64
                    d.ellipse((x - 20, 188, x + 20, 228), fill=(255, 222, 89) if p > j / 3 else (255, 255, 255),
                              outline=INK, width=5)
            elif song and (speaking or ta < line["end"] + 0.35):
                frame.paste(song_caps[idx], (0, 30), song_caps[idx])
            elif speaking or ta < line["end"] + 0.35:
                frame.paste(caps[idx], (60, 24), caps[idx])

            if show:                                       # prop drawn last so captions never hide it
                draw_prop(frame, show, tl)

            tsc = ta - scene_start[line["scene"]]          # quick flash when the scene changes
            if idx and tsc < 0.25 and lines[idx - 1]["scene"] != line["scene"]:
                frame = Image.blend(frame, white, max(0.0, 0.7 * (1 - tsc / 0.25)))
        proc.stdin.write(frame.convert("RGB").tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        sys.exit("ffmpeg failed")

    spans = {}                                             # where each segment sits, as fractions 0..1
    for l in lines:
        a, b = l["start"] + LEAD, l["end"] + LEAD
        s = spans.setdefault(l["segment"], [a, b])
        s[0], s[1] = min(s[0], a), max(s[1], b + (l.get("pause") or 0))
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
