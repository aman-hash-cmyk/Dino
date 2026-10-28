"""
song_audio.py - everything you HEAR in the "10 Little Dinosaurs" counting song.

  * the timeline (intro, five verses, outro) with the time of every word and every egg hatching
  * bouncy toy-piano melody, bass, soft chords and a simple beat (all synthesised, royalty free)
  * a sung children's chorus: each word is spoken by the free TTS voice, then tuned to the melody
    note and stretched to the note length (3 slightly detuned copies make it sound like a chorus).
    If no voice engine is available it falls back to a synthesised "la-la" choir.
  * sound effects synced to the animation: egg cracks, pops, giggles, stomps, munching, wing flaps
"""
import json
import os
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

import music

SR = music.SR
ROOT = Path(__file__).resolve().parent
BIBLE = json.loads((ROOT / "characters.json").read_text(encoding="utf-8"))

SPECIES = ["steg", "tri", "ptero", "bronto", "trex"]
NUMBER_WORDS = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]
NUMBER_BEATS = [0, 2, 4, 8, 10, 12, 16, 18, 20, 24]          # when each number is sung (in beats)
INTRO_BEATS, PRE_BEATS, VERSE_BEATS, OUTRO_BEATS = 4, 2, 32, 4
CHORDS = ["C", "C", "F", "C", "C", "C", "G", "C"]
BASS = {"C": 48, "F": 53, "G": 55}
STAB = {"C": (60, 64, 67), "F": (60, 65, 69), "G": (59, 62, 67)}
SPLITS = {"little": (0.5, 0.5), "dinosaurs": (0.3, 0.3, 0.4), "dinosaur": (0.3, 0.3, 0.4), "babies": (0.5, 0.5)}
VOWEL = {"one": "o", "two": "u", "three": "e", "four": "o", "five": "a", "six": "i", "seven": "e", "eight": "a",
         "nine": "a", "ten": "e", "little": "i", "dinosaurs": "a", "dinosaur": "a", "babies": "e"}


# ------------------------------------------------------------------ lyrics & melody (original tune)
def verse_tokens():
    """One verse = 32 beats: [{word, display, line, parts:[(beat, length_in_beats, midi)]}]"""
    toks = []
    for line, (base, (a, b, c)) in enumerate(((0, (0, 1, 2)), (8, (3, 4, 5)), (16, (6, 7, 8)))):
        def num(i, beat, midi, first=False):
            w = NUMBER_WORDS[i]
            toks.append(dict(word=w, display=w.capitalize() if first else w, line=line, parts=[(beat, 1.0, midi)]))

        def little(beat, m1, m2, comma):
            toks.append(dict(word="little", display="little," if comma else "little", line=line,
                             parts=[(beat, 0.5, m1), (beat + 0.5, 0.5, m2)]))
        num(a, base, 60, True)
        little(base + 1, 62, 64, True)
        num(b, base + 2, 64)
        little(base + 3, 65, 67, True)
        num(c, base + 4, 67)
        little(base + 5, 69, 67, False)
        toks.append(dict(word="dinosaurs", display="dinosaurs", line=line,
                         parts=[(base + 6, 0.5, 64), (base + 6.5, 0.5, 62), (base + 7, 1.0, 60)]))
    toks.append(dict(word="ten", display="Ten", line=3, parts=[(24, 1.0, 64)]))
    toks.append(dict(word="little", display="little", line=3, parts=[(25, 0.5, 67), (25.5, 0.5, 67)]))
    toks.append(dict(word="dinosaur", display="dinosaur", line=3,
                     parts=[(26, 0.5, 69), (26.5, 0.5, 67), (27, 1.0, 64)]))
    toks.append(dict(word="babies", display="babies!", line=3, parts=[(28, 1.0, 62), (29, 2.5, 60)]))
    return toks


def build_timeline(order, bpms, bg_offset=0):
    bl0 = 60.0 / bpms[0]
    tl = {"order": order, "bpms": bpms, "intro": {"t0": 0.0, "t1": INTRO_BEATS * bl0}, "verses": []}
    t = INTRO_BEATS * bl0
    for k, (sp, bpm) in enumerate(zip(order, bpms)):
        bl = 60.0 / bpm
        t_pre, t_sing = t, t + PRE_BEATS * bl
        t_end = t_sing + VERSE_BEATS * bl
        toks = []
        for tk in verse_tokens():
            parts = [{"start": round(t_sing + b * bl, 3), "end": round(t_sing + (b + d * 0.93) * bl, 3), "midi": m}
                     for b, d, m in tk["parts"]]
            toks.append({"word": tk["word"], "display": tk["display"], "line": tk["line"], "parts": parts,
                         "start": parts[0]["start"], "end": parts[-1]["end"]})
        tl["verses"].append({"index": k, "bg": (k + bg_offset) % 5, "species": sp, "bpm": bpm, "beat": bl, "t_pre": round(t_pre, 3),
                             "t_sing": round(t_sing, 3), "t_end": round(t_end, 3),
                             "hatch": [round(t_sing + nb * bl, 3) for nb in NUMBER_BEATS], "tokens": toks})
        t = t_end
    bl_last = 60.0 / bpms[-1]
    tl["outro"] = {"t0": round(t, 3), "t1": round(t + OUTRO_BEATS * bl_last, 3)}
    tl["total"] = tl["outro"]["t1"]
    return tl


# ------------------------------------------------------------------ vocal engine (sung words)
def _read_wav(path):
    with wave.open(str(path), "rb") as w:
        rate, ch = w.getframerate(), w.getnchannels()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        x = x[: len(x) // ch * ch].reshape(-1, ch).mean(axis=1)
    return x, rate


def _write_wav(path, x, rate=SR):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def estimate_f0(x, rate=SR, fmin=130, fmax=520):
    frame, hop = int(0.05 * rate), int(0.015 * rate)
    lo, hi = int(rate / fmax), int(rate / fmin)
    thr = 0.08 * float(np.max(np.abs(x))) if len(x) else 0
    vals = []
    for s in range(0, max(1, len(x) - frame), hop):
        seg = x[s:s + frame]
        if len(seg) < frame or np.sqrt(np.mean(seg ** 2)) < thr:
            continue
        seg = seg - seg.mean()
        f = np.fft.rfft(seg, 2 * frame)
        ac = np.fft.irfft(f * np.conj(f))[:frame]
        if ac[0] <= 0:
            continue
        k = lo + int(np.argmax(ac[lo:hi]))
        if ac[k] > 0.35 * ac[0]:
            vals.append(rate / k)
    return float(np.median(vals)) if vals else None


def _atempo(x, factor):
    """Time-stretch with ffmpeg (factor > 1 = faster / shorter). Pitch stays the same."""
    factor = max(0.25, min(4.0, factor))
    if abs(factor - 1.0) < 0.02:
        return x
    chain, f = [], factor
    while f > 2.0:
        chain.append(2.0)
        f /= 2.0
    while f < 0.5:
        chain.append(0.5)
        f /= 0.5
    chain.append(f)
    with tempfile.TemporaryDirectory() as tmp:
        a, b = Path(tmp) / "a.wav", Path(tmp) / "b.wav"
        _write_wav(a, x)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(a), "-filter:a",
                        ",".join(f"atempo={c:.4f}" for c in chain), str(b)], check=True)
        y, _ = _read_wav(b)
    return y


def prepare_words(mock=False):
    """{word: (samples at 44.1k, f0)} spoken by the child voice, or None if no voice engine works."""
    words = sorted({tk["word"] for tk in verse_tokens()})
    out = {}
    if os.environ.get("SONG_FAKE_TTS"):                           # test aid: synthetic stand-in voice
        for w in words:
            syl = len(SPLITS.get(w, (1,)))
            v = music.voice_synth(250, 0.16 * syl + 0.14, VOWEL.get(w, "a"), vib=0)
            out[w] = (v, estimate_f0(v))
        return out
    if mock:
        return None
    try:
        import tts
        pip = BIBLE["characters"]["pip"]
        with tempfile.TemporaryDirectory() as tmp:
            for w in words:
                p = Path(tmp) / f"{w}.wav"
                tts.synthesize_line(w.capitalize() + ".", pip, "happy", p)
                x, rate = _read_wav(p)
                x = np.interp(np.arange(int(len(x) * SR / rate)) * rate / SR, np.arange(len(x)), x).astype(np.float32)
                keep = np.where(np.abs(x) > 0.05 * (np.max(np.abs(x)) or 1))[0]
                if len(keep):
                    x = x[max(0, keep[0] - int(0.01 * SR)): keep[-1] + int(0.02 * SR)]
                x = x / (np.max(np.abs(x)) or 1) * 0.8
                out[w] = (x, estimate_f0(x))
        print("[song] vocals: spoken words tuned to the melody")
        return out
    except BaseException as e:                                    # SystemExit when no engine exists
        print(f"[song] no voice engine available ({e}); using the synthesised 'la-la' choir instead")
        return None


_part_cache = {}


def sing_part(word, idx, midi, dur, words, detune=0.0):
    """One syllable sung at a note: tuned to the pitch and fitted to `dur` seconds."""
    key = (word, idx, midi, round(dur * 1000), detune, words is not None)
    if key in _part_cache:
        return _part_cache[key]
    f_t = 440.0 * 2 ** ((midi - 69) / 12) * 2 ** (detune / 1200)
    vowel = VOWEL.get(word, "a")
    if words is None or word not in words:
        y = music.voice_synth(f_t, dur, vowel, vol=0.55)
    else:
        x, f0 = words[word]
        split = SPLITS.get(word, (1.0,))
        a, b = int(sum(split[:idx]) * len(x)), int(sum(split[:idx + 1]) * len(x))
        seg = x[a:max(b, a + 200)]
        r = max(0.6, min(2.2, f_t / (f0 or 260.0)))
        pos = np.arange(0, len(seg) - 1, r)
        y = np.interp(pos, np.arange(len(seg)), seg).astype(np.float32)          # pitch change (also changes length)
        natural = len(y) / SR
        if natural / dur >= 0.5:
            y = _atempo(y, natural / dur)
        else:                                                                    # long note: stretch, then hold the vowel
            y = _atempo(y, 0.5)
            hold = dur - len(y) / SR
            if hold > 0.05:
                tail = float(np.sqrt(np.mean(y[-int(0.05 * SR):] ** 2))) or 0.1
                v = music.voice_synth(f_t, hold + 0.04, vowel, vol=min(0.6, tail * 2.0), attack=0.04)
                cf = int(0.03 * SR)
                y = np.concatenate([y[:-cf], y[-cf:] * np.linspace(1, 0, cf) + v[:cf] * np.linspace(0, 1, cf), v[cf:]])
        fade = int(0.006 * SR)
        if len(y) > 2 * fade:
            y[:fade] *= np.linspace(0, 1, fade)
            y[-fade:] *= np.linspace(1, 0, fade)
    _part_cache[key] = y.astype(np.float32)
    return _part_cache[key]


# ------------------------------------------------------------------ music
def put_t(buf, sig, t):
    music.put(buf, sig, t * SR)


def verse_music(buf, V):
    bl, t0, tp = V["beat"], V["t_sing"], V["t_pre"]
    for bar in range(8):
        b0 = t0 + bar * 4 * bl
        ch = CHORDS[bar]
        put_t(buf, music.tone(music.midi(BASS[ch]), bl * 0.9, "sine", 5, 0.5), b0)
        put_t(buf, music.tone(music.midi(BASS[ch] + 7), bl * 0.8, "sine", 5, 0.4), b0 + 2 * bl)
        for k in (0.5, 1.5, 2.5, 3.5):
            for m in STAB[ch]:
                put_t(buf, music.tone(music.midi(m), bl * 0.35, "tri", 12, 0.07), b0 + k * bl)
        for k in (0, 2):
            put_t(buf, music.kick() * 0.5, b0 + k * bl)
        for k in (1, 3):
            put_t(buf, music.block() * 0.5, b0 + k * bl)
        for k in range(8):
            put_t(buf, music.shaker(k) * (1.0 if k % 2 else 0.6), b0 + k * bl / 2)
    for tk in V["tokens"]:                                       # toy-piano doubles the tune, an octave up
        for p in tk["parts"]:
            put_t(buf, music.tone(music.midi(p["midi"] + 12), min(1.4, p["end"] - p["start"] + 0.15), "bell", 6.0, 0.2), p["start"])
    for k in range(4):                                           # pick-up into the verse
        put_t(buf, music.tone(music.midi(79 + [0, 2, 4, 5][k]), bl * 0.3, "bell", 7, 0.18), tp + (1 + k * 0.25) * bl)
    for k in range(4):
        put_t(buf, music.shaker(k) * 0.7, tp + k * bl / 2)


def intro_music(buf, t0, bl):
    for k, m in enumerate((72, 76, 79, 84, 79, 76, 72, 67)):
        put_t(buf, music.tone(music.midi(m), bl * 0.7, "bell", 6, 0.22), t0 + k * bl / 2)
        put_t(buf, music.shaker(k) * 0.7, t0 + k * bl / 2)
    put_t(buf, music.tone(music.midi(48), bl * 3.5, "sine", 1.5, 0.4), t0)


def outro_music(buf, t0, bl):
    for m in (60, 64, 67, 72, 76):
        put_t(buf, music.tone(music.midi(m), 2.5, "bell", 2.2, 0.22), t0)
    put_t(buf, music.voice_synth(music.midi(60), OUTRO_BEATS * bl, "a", vol=0.25, attack=0.2, release=0.6), t0)
    put_t(buf, music.tone(music.midi(48), 2.0, "sine", 2.0, 0.45), t0)


# ------------------------------------------------------------------ the whole soundtrack
def build(ep_dir, order, bpms, mock=False, bg_offset=0):
    ep_dir = Path(ep_dir)
    tl = build_timeline(order, bpms, bg_offset)
    total = tl["total"] + 0.6
    n = int(total * SR)
    mus = np.zeros(n, dtype=np.float32)
    voc = np.zeros(n, dtype=np.float32)
    sfx = np.zeros(n, dtype=np.float32)

    intro_music(mus, 0.0, 60.0 / bpms[0])
    for V in tl["verses"]:
        verse_music(mus, V)
    outro_music(mus, tl["outro"]["t0"], 60.0 / bpms[-1])

    words = prepare_words(mock)
    layers = ((0.0, 0.0, 0.6), (9.0, 0.011, 0.35), (-9.0, 0.019, 0.35))          # detune cents, delay s, gain
    for V in tl["verses"]:
        for tk in V["tokens"]:
            for idx, p in enumerate(tk["parts"]):
                dur = p["end"] - p["start"]
                for cents, delay, gain in layers:
                    y = sing_part(tk["word"], idx, p["midi"], dur, words, cents)
                    put_t(voc, y * gain * (1.0 if tk["word"] in NUMBER_WORDS else 0.85), p["start"] + delay)

    cache = {}

    def fx(name, t, seed=0, vol=0.6):
        if (name, seed) not in cache:
            cache[(name, seed)] = music.sfx(name, seed)
        put_t(sfx, cache[(name, seed)] * vol, max(0.0, t))

    fx("sparkle", 0.2)
    for V in tl["verses"]:
        bl, sp = V["beat"], V["species"]
        for i, th in enumerate(V["hatch"]):
            fx("bloop", V["t_pre"] + 0.15 + 0.035 * i, i, 0.35)
            fx("crack", th - 0.42, i, 0.5)
            fx("pop", th, i, 0.5)
            fx("giggle", th + 0.1, i + 10 * V["index"], 0.45)
        first = V["hatch"][0]
        for b in range(int((V["t_end"] - first) / bl)):
            t = first + b * bl
            if sp == "trex":
                fx("stomp", t, 0, 0.45)
            elif sp == "bronto":
                fx("munch", t, b % 3, 0.4)
            elif sp == "ptero" and b % 2 == 0:
                fx("flap", t, 0, 0.3)
        fx("sparkle", V["t_sing"] + 28 * bl, 0, 0.6)
        fx("whoosh", V["t_end"] - 0.1, 0, 0.5)
    fx("sparkle", tl["outro"]["t0"], 0, 0.7)
    fx("ding", tl["outro"]["t0"] + 0.3, 0, 0.5)

    def peak(x):
        return float(np.max(np.abs(x))) or 1.0
    mixed = mus / peak(mus) * 0.5 + voc / peak(voc) * 0.85 + sfx / peak(sfx) * 0.45
    top = peak(mixed)
    if top > 0.95:
        mixed *= 0.95 / top
    out = ep_dir / "final_audio.wav"
    with wave.open(str(out), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.stack([mixed, mixed], axis=1) * 32767).astype(np.int16).tobytes())
    (ep_dir / "song_timeline.json").write_text(json.dumps(tl, indent=1))
    return tl
