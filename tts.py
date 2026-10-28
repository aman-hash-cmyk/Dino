"""
tts.py - turns one line of dialogue into a 24 kHz mono WAV, with intonation.

Engines (tried in this order, set env TTS_ENGINES to change, e.g. "piper"):
  edge   - free neural voices through the 'edge-tts' package (much more expressive).
           Unofficial service; if it is unreachable or blocked we silently use Piper.
  piper  - offline voices from the voices/ folder (always available as a safety net).

Intonation: every line is split into sentences. Each sentence gets its own speed and pitch from
the line's emotion (happy / excited / surprised / silly), and from its punctuation
(? lifts the pitch, ! is brighter and faster, ... slows down).
"""
import asyncio
import os
import re
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
VOICE_DIR = Path(os.environ.get("PIPER_VOICE_DIR", ROOT / "voices"))
RATE = 24000
ENGINES = [e.strip() for e in os.environ.get("TTS_ENGINES", "edge,piper").split(",") if e.strip()]
PROSODY = {                      # emotion -> (speed %, pitch Hz)
    "happy": (4, 4), "excited": (14, 16), "surprised": (8, 24), "silly": (6, 12),
}
PIPER_SPEED = {"happy": 1.0, "excited": 0.9, "surprised": 0.95, "silly": 1.0}
_engine = None


def clean(text):
    text = re.sub(r"[*_#`~]", "", text)
    text = re.sub(r"[^\w\s.,!?'’\-:;]", "", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def sentences(text):
    """[(sentence, last punctuation mark)]"""
    out = []
    for m in re.finditer(r"[^.!?]+(?:\.\.\.|[.!?])*", text):
        s = m.group(0).strip()
        if re.search(r"\w", s):
            mark = "..." if s.endswith("...") else (s[-1] if s[-1] in "!?" else ".")
            out.append((s, mark))
    return out or [(text, ".")]


def _num(s):
    return int(re.sub(r"[^\d+-]", "", str(s)) or 0)


def to_wav(src, dst):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-ar", str(RATE), "-ac", "1",
                    "-sample_fmt", "s16", str(dst)], check=True)


def join(paths, out_path, gap=0.12):
    chunks = []
    for p in paths:
        with wave.open(str(p), "rb") as w:
            x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
        peak = float(np.max(np.abs(x))) if len(x) else 0.0
        if peak > 0:
            x *= 0.8 * 32768 / peak                          # same loudness for every sentence / engine
        chunks.append(x)
        chunks.append(np.zeros(int(RATE * gap), dtype=np.float32))
    data = np.concatenate(chunks[:-1]) if len(chunks) > 1 else chunks[0]
    with wave.open(str(out_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(np.clip(data, -32768, 32767).astype(np.int16).tobytes())


# ------------------------------------------------------------------ engines
def edge_one(text, cfg, emotion, mark, out_wav):
    import edge_tts
    speed, pitch = PROSODY.get(emotion, PROSODY["happy"])
    speed += _num(cfg.get("rate", "+0%"))
    pitch += _num(cfg.get("pitch", "+0Hz"))
    if mark == "?":
        pitch += 14
        speed -= 2
    elif mark == "!":
        pitch += 8
        speed += 6
    elif mark == "...":
        speed -= 14
    speed = max(-40, min(60, speed))
    pitch = max(-45, min(45, pitch))
    last = None
    for attempt in range(3):
        try:
            with tempfile.TemporaryDirectory() as tmp:
                mp3 = Path(tmp) / "x.mp3"
                comm = edge_tts.Communicate(text, cfg["voice"], rate=f"{speed:+d}%", pitch=f"{pitch:+d}Hz")
                asyncio.run(comm.save(str(mp3)))
                if not mp3.exists() or mp3.stat().st_size < 500:
                    raise RuntimeError("empty audio")
                to_wav(mp3, out_wav)
            return
        except Exception as e:              # network hiccup, blocked, bad voice name ...
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"edge-tts failed: {last}")


def piper_one(text, voice, emotion, mark, out_wav):
    model = VOICE_DIR / f"{voice['model']}.onnx"
    if not model.exists():
        raise RuntimeError(f"Piper voice not found: {model}")
    scale = voice.get("length_scale", 1.0) * PIPER_SPEED.get(emotion, 1.0)
    scale *= 0.95 if mark == "!" else (1.04 if mark == "?" else 1.0)
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "p.wav"
        cmd = [sys.executable, "-m", "piper", "--model", str(model), "--output_file", str(raw),
               "--length_scale", f"{scale:.3f}", "--noise_scale", "0.8", "--noise_w", "0.9"]
        if "speaker" in voice:
            cmd += ["--speaker", str(voice["speaker"])]
        subprocess.run(cmd, input=text.encode("utf-8"), check=True, capture_output=True)
        to_wav(raw, out_wav)


def pick_engine():
    global _engine
    if _engine:
        return _engine
    for name in ENGINES:
        try:
            if name == "edge":
                with tempfile.TemporaryDirectory() as tmp:
                    edge_one("Hello friends!", {"voice": "en-US-JennyNeural"}, "happy", "!", Path(tmp) / "t.wav")
            elif name == "piper":
                if not any(VOICE_DIR.glob("*.onnx")):
                    raise RuntimeError("no Piper voice downloaded")
            else:
                continue
            _engine = name
            print(f"[tts] using the '{name}' voice engine")
            return _engine
        except Exception as e:
            print(f"[tts] '{name}' is not available ({e}); trying the next engine")
    sys.exit("No text-to-speech engine works. Run tools/download_voice.py or check your internet connection.")


def synthesize_line(text, character, emotion, out_path, mock=False):
    text = clean(text)
    if mock:
        with wave.open(str(out_path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(b"\x00\x00" * int(RATE * max(1.0, len(text.split()) * 0.38)))
        return
    engine = pick_engine()
    with tempfile.TemporaryDirectory() as tmp:
        parts = []
        for i, (sent, mark) in enumerate(sentences(text)):
            part = Path(tmp) / f"s{i}.wav"
            try:
                if engine == "edge":
                    edge_one(sent, character["edge"], emotion, mark, part)
                else:
                    piper_one(sent, character["voice"], emotion, mark, part)
            except Exception as e:
                if engine == "edge" and any(VOICE_DIR.glob("*.onnx")):
                    print(f"  [tts] edge failed for one sentence ({e}); using Piper for it")
                    piper_one(sent, character["voice"], emotion, mark, part)
                else:
                    raise
            parts.append(part)
        join(parts, out_path)
