"""
song_audio.py - everything you HEAR in the counting-song videos.

Structure of one video (each of the five dinosaur species gets a verse, in a different order every day):
  Round 1  "count up":   One little, two little ... ten little dinosaur babies!  + a species action chant
                         (Waddle! Play! Flap! Munch! Stomp!  Hooray, green dinos!)
  Round 2  "count down": Ten little, nine little ... one little dinosaur baby - bye bye!
  A friendly host (spoken, with intonation) introduces every verse and praises the little viewers.

Voices: every word is spoken by free TTS voices, then tuned to the melody note and fitted to the note length
with a high-quality pitch/time stretcher (ffmpeg's rubberband). Three different voices sing together like a
small children's chorus, with human touches (timing wobble, breaths, accents) and a studio polish chain
(EQ, compression, a little room echo). Everything else (toy-piano melody, beat, sound effects) is synthesised.
"""
import json
import subprocess
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
NUMBER_BEATS = [0, 2, 4, 8, 10, 12, 16, 18, 20, 24]
INTRO_BEATS, OUTRO_BEATS = 6, 6
PRE_FIRST, PRE_OTHER, VERSE_BEATS, CHORUS_BEATS, POST_BEATS = 4, 2, 32, 8, 2
CHORDS = ["C", "C", "F", "C", "C", "C", "G", "C"]
BASS = {"C": 48, "F": 53, "G": 55}
STAB = {"C": (60, 64, 67), "F": (60, 65, 69), "G": (59, 62, 67)}
SPLITS = {"little": (0.5, 0.5), "dinosaurs": (0.3, 0.3, 0.4), "dinosaur": (0.3, 0.3, 0.4), "babies": (0.5, 0.5),
          "baby": (0.5, 0.5), "waddle": (0.5, 0.5), "hooray": (0.5, 0.5), "yellow": (0.5, 0.5), "purple": (0.5, 0.5),
          "orange": (0.5, 0.5), "dinos": (0.5, 0.5)}
VOWEL = {"one": "o", "two": "u", "three": "e", "four": "o", "five": "a", "six": "i", "seven": "e", "eight": "a",
         "nine": "a", "ten": "e", "little": "i", "dinosaurs": "a", "dinosaur": "a", "babies": "e", "baby": "e",
         "bye": "a", "waddle": "o", "play": "e", "flap": "a", "munch": "u", "stomp": "o", "hooray": "e",
         "green": "i", "yellow": "e", "purple": "u", "teal": "i", "orange": "o", "dinos": "a"}
ACTION = {"steg": "waddle", "tri": "play", "ptero": "flap", "bronto": "munch", "trex": "stomp"}
COLOR = {"steg": "green", "tri": "yellow", "ptero": "purple", "bronto": "teal", "trex": "orange"}
NAME = {"steg": "stegosaurus", "tri": "triceratops", "ptero": "pterodactyl", "bronto": "brontosaurus", "trex": "T Rex"}
PRAISE = ["Great job!", "Wow!", "Yay!", "You did it!", "High five!", "Hooray!"]
COUNT_PHRASES = ["Count with me!", "Here we go!", "Ready? Go!"]
# three singers: (character whose voice config is used, loudness, delay s, cents, formant handling)
SINGERS = [("pip", 0.62, 0.0, 0.0, "preserved"), ("dina", 0.42, 0.013, 7.0, "shifted"), ("trixie", 0.34, 0.021, -8.0, "shifted")]


# ------------------------------------------------------------------ lyrics & melody (original tune)
def verse_tokens(kind="up"):
    """One verse = 32 beats: [{word, display, line, parts:[(beat, length_in_beats, midi)]}]"""
    words = NUMBER_WORDS if kind == "up" else NUMBER_WORDS[::-1]
    toks = []
    for line, (base, (a, b, c)) in enumerate(((0, (0, 1, 2)), (8, (3, 4, 5)), (16, (6, 7, 8)))):
        def num(i, beat, midi, first=False):
            w = words[i]
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
    last = words[9]
    toks.append(dict(word=last, display=last.capitalize(), line=3, parts=[(24, 1.0, 64)]))
    toks.append(dict(word="little", display="little", line=3, parts=[(25, 0.5, 67), (25.5, 0.5, 67)]))
    toks.append(dict(word="dinosaur", display="dinosaur", line=3, parts=[(26, 0.5, 69), (26.5, 0.5, 67), (27, 1.0, 64)]))
    if kind == "up":
        toks.append(dict(word="babies", display="babies!", line=3, parts=[(28, 1.0, 62), (29, 2.5, 60)]))
    else:
        toks.append(dict(word="baby", display="baby!", line=3, parts=[(28, 1.0, 62), (29, 1.0, 60)]))
        toks.append(dict(word="bye", display="Bye", line=3, parts=[(30, 0.5, 64)]))
        toks.append(dict(word="bye", display="bye!", line=3, parts=[(30.5, 0.5, 62)]))
    return toks


def chorus_tokens(sp):
    """8 beats of species action chant: 'Waddle, waddle, waddle, waddle! Hooray, hooray, green dinos!'"""
    act, col = ACTION[sp], COLOR[sp]
    toks = []
    for k, m in enumerate((64, 67, 69, 67)):
        parts = [(k, 0.5, m), (k + 0.5, 0.5, m)] if len(SPLITS.get(act, (1,))) == 2 else [(k, 0.85, m)]
        toks.append(dict(word=act, display=(act.capitalize() if k == 0 else act) + ("!" if k == 3 else ","), line=4, parts=parts))
    toks.append(dict(word="hooray", display="Hooray,", line=5, parts=[(4, 0.5, 67), (4.5, 0.5, 69)]))
    toks.append(dict(word="hooray", display="hooray,", line=5, parts=[(5, 0.5, 67), (5.5, 0.5, 64)]))
    cparts = [(6, 0.5, 62), (6.5, 0.5, 62)] if len(SPLITS.get(col, (1,))) == 2 else [(6, 1.0, 62)]
    toks.append(dict(word=col, display=col, line=5, parts=cparts))
    toks.append(dict(word="dinos", display="dinos!", line=5, parts=[(7, 0.5, 60), (7.5, 0.5, 60)]))
    return toks


def all_words():
    ws = set()
    for kind in ("up", "down"):
        ws |= {t["word"] for t in verse_tokens(kind)}
    for sp in SPECIES:
        ws |= {t["word"] for t in chorus_tokens(sp)}
    return sorted(ws)


def _convert(tokens, t0, bl):
    out = []
    for tk in tokens:
        parts = [{"start": round(t0 + b * bl, 3), "end": round(t0 + (b + d * 0.93) * bl, 3), "midi": m} for b, d, m in tk["parts"]]
        out.append({"word": tk["word"], "display": tk["display"], "line": tk["line"], "parts": parts,
                    "start": parts[0]["start"], "end": parts[-1]["end"]})
    return out


def build_timeline(order, kinds, bpms, bg_offset=0, seed=0):
    bl0 = 60.0 / bpms[0]
    tl = {"order": order, "kinds": kinds, "bpms": bpms, "intro": {"t0": 0.0, "t1": INTRO_BEATS * bl0},
          "verses": [], "host": []}
    tl["host"].append({"text": "Hi friends! Let's count the baby dinosaurs!", "t0": 0.35, "max": INTRO_BEATS * bl0 - 0.45, "kind": "intro"})
    t = INTRO_BEATS * bl0
    seen_down = False
    for k, (sp, kind, bpm) in enumerate(zip(order, kinds, bpms)):
        bl = 60.0 / bpm
        pre_beats = PRE_FIRST if (kind == "up" or not seen_down) else PRE_OTHER
        if kind == "down":
            seen_down = True
        t_pre = t
        t_sing = t_pre + pre_beats * bl
        t_end = t_sing + VERSE_BEATS * bl
        t_chorus_end = t_end + (CHORUS_BEATS * bl if kind == "up" else 0.0)
        t_done = t_chorus_end + POST_BEATS * bl
        if kind == "up":
            text = f"Meet the {COLOR[sp]} {NAME[sp]}!"
        elif pre_beats == PRE_FIRST:
            text = "Now let's count down!"
        else:
            text = COUNT_PHRASES[(k + seed) % len(COUNT_PHRASES)]
        tl["host"].append({"text": text, "t0": round(t_pre + 0.1, 3), "max": round(pre_beats * bl - 0.2, 3), "kind": "pre"})
        tl["host"].append({"text": PRAISE[(k * 2 + seed) % len(PRAISE)], "t0": round(t_chorus_end + 0.1, 3),
                           "max": round(POST_BEATS * bl - 0.15, 3), "kind": "praise"})
        V = {"index": k, "bg": (k + bg_offset) % 5, "species": sp, "kind": kind, "bpm": bpm, "beat": bl,
             "t_pre": round(t_pre, 3), "t_sing": round(t_sing, 3), "t_end": round(t_end, 3),
             "t_chorus_end": round(t_chorus_end, 3), "t_done": round(t_done, 3),
             "tokens": _convert(verse_tokens(kind), t_sing, bl),
             "chorus_tokens": _convert(chorus_tokens(sp), t_end, bl) if kind == "up" else []}
        V["hatch"] = [round(t_sing + nb * bl, 3) for nb in NUMBER_BEATS]
        if kind == "down":                                       # babies hop in, then leave one by one as we count down
            V["arrive"] = [round(t_pre + 0.1 + 0.05 * i, 3) for i in range(10)]
            V["leave"] = [None] + [round(t_sing + NUMBER_BEATS[10 - i] * bl + 0.12, 3) for i in range(1, 10)]
        tl["verses"].append(V)
        t = t_done
    bl_last = 60.0 / bpms[-1]
    tl["outro"] = {"t0": round(t, 3), "t1": round(t + OUTRO_BEATS * bl_last, 3)}
    tl["host"].append({"text": "Bye bye, friends! See you soon!", "t0": round(t + 0.35, 3), "max": OUTRO_BEATS * bl_last - 0.5, "kind": "outro"})
    tl["total"] = tl["outro"]["t1"]
    return tl


# ------------------------------------------------------------------ audio helpers
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


def _resample(x, rate):
    if rate == SR:
        return x.astype(np.float32)
    return np.interp(np.arange(int(len(x) * SR / rate)) * rate / SR, np.arange(len(x)), x).astype(np.float32)


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


_have_rb = []


def have_rubberband():
    if not _have_rb:
        try:
            out = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
            _have_rb.append(" rubberband " in out)
        except Exception:
            _have_rb.append(False)
    return _have_rb[0]


def ffmpeg_filter(x, af):
    with tempfile.TemporaryDirectory() as tmp:
        a, b = Path(tmp) / "a.wav", Path(tmp) / "b.wav"
        _write_wav(a, x)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(a), "-af", af, str(b)], check=True)
        y, _ = _read_wav(b)
    return y


def _atempo_chain(factor):
    factor = max(0.25, min(4.0, factor))
    chain, f = [], factor
    while f > 2.0:
        chain.append(2.0)
        f /= 2.0
    while f < 0.5:
        chain.append(0.5)
        f /= 0.5
    chain.append(f)
    return ",".join(f"atempo={c:.4f}" for c in chain)


def stretch_pitch(x, ratio, tempo, formant="shifted"):
    """Change pitch by `ratio` and speed by `tempo` (>1 = shorter). Uses rubberband when available."""
    if have_rubberband():
        tempo = max(0.12, min(8.0, tempo))
        return ffmpeg_filter(x, f"rubberband=tempo={tempo:.4f}:pitch={ratio:.4f}:transients=smooth:detector=soft:"
                                f"formant={formant}:pitchq=quality")
    pos = np.arange(0, len(x) - 1, ratio)                         # fallback: resample (also changes the length)
    y = np.interp(pos, np.arange(len(x)), x).astype(np.float32)
    factor = tempo / ratio
    return y if abs(factor - 1) < 0.02 else ffmpeg_filter(y, _atempo_chain(factor))


# ------------------------------------------------------------------ the singers
def prepare_voices(mock=False):
    """{singer: {"words": {word: (samples, f0)}, "formant": mode}} or None when no voice engine exists."""
    words = all_words()
    voices = {}
    import os
    if os.environ.get("SONG_FAKE_TTS"):                           # test aid: synthetic stand-in voices
        for name, _, _, _, formant in SINGERS:
            base = {"pip": 250, "dina": 215, "trixie": 200}[name]
            d = {}
            for w in words:
                syl = len(SPLITS.get(w, (1,)))
                v = music.voice_synth(base, 0.16 * syl + 0.14, VOWEL.get(w, "a"), vib=0)
                d[w] = (v, estimate_f0(v))
            voices[name] = {"words": d, "formant": formant}
        return voices
    if mock:
        return None
    try:
        import tts
        with tempfile.TemporaryDirectory() as tmp:
            for name, _, _, _, formant in SINGERS:
                d = {}
                for w in words:
                    p = Path(tmp) / f"{name}_{w}.wav"
                    tts.synthesize_line(w.capitalize() + ".", BIBLE["characters"][name], "happy", p)
                    x, rate = _read_wav(p)
                    x = _resample(x, rate)
                    keep = np.where(np.abs(x) > 0.05 * (np.max(np.abs(x)) or 1))[0]
                    if len(keep):
                        x = x[max(0, keep[0] - int(0.01 * SR)): keep[-1] + int(0.02 * SR)]
                    x = x / (np.max(np.abs(x)) or 1) * 0.8
                    d[w] = (x, estimate_f0(x))
                voices[name] = {"words": d, "formant": formant}
        print(f"[song] vocals: {len(voices)} voices sing together, tuned to the melody")
        return voices
    except BaseException as e:                                    # SystemExit when no engine exists
        print(f"[song] no voice engine available ({e}); using the synthesised 'la-la' choir instead")
        return None


_part_cache = {}


def sing_part(singer, word, idx, midi, dur, voices, extra_cents=0.0):
    """One syllable sung at a note: tuned to the pitch and fitted to `dur` seconds."""
    key = (singer, word, idx, midi, round(dur * 1000), round(extra_cents), voices is not None)
    if key in _part_cache:
        return _part_cache[key]
    f_t = 440.0 * 2 ** ((midi - 69) / 12) * 2 ** (extra_cents / 1200)
    vowel = VOWEL.get(word, "a")
    if voices is None or singer not in voices or word not in voices[singer]["words"]:
        y = music.voice_synth(f_t, dur, vowel, vol=0.55)
    else:
        x, f0 = voices[singer]["words"][word]
        split = SPLITS.get(word, (1.0,))
        a, b = int(sum(split[:idx]) * len(x)), int(sum(split[:idx + 1]) * len(x))
        seg = x[a:max(b, a + 400)]
        ratio = max(0.6, min(2.4, f_t / (f0 or 250.0)))
        natural = len(seg) / SR
        tempo = natural / dur
        min_tempo = 0.35 if have_rubberband() else 0.5
        y = stretch_pitch(seg, ratio, max(tempo, min_tempo), voices[singer]["formant"])
        if tempo < min_tempo:                                     # long note: hold the vowel with a soft 'ooh/aah'
            hold = dur - len(y) / SR
            if hold > 0.05:
                tail = float(np.sqrt(np.mean(y[-int(0.05 * SR):] ** 2))) or 0.1
                v = music.voice_synth(f_t, hold + 0.04, vowel, vol=min(0.6, tail * 2.0), attack=0.04)
                cf = int(0.03 * SR)
                y = np.concatenate([y[:-cf], y[-cf:] * np.linspace(1, 0, cf) + v[:cf] * np.linspace(0, 1, cf), v[cf:]])
        fade = int(0.006 * SR)
        if len(y) > 2 * fade:
            y = y.copy()
            y[:fade] *= np.linspace(0, 1, fade)
            y[-fade:] *= np.linspace(1, 0, fade)
    _part_cache[key] = y.astype(np.float32)
    return _part_cache[key]


def breath(seed):
    n = int(0.17 * SR)
    t = np.arange(n) / SR
    noise = np.random.default_rng(seed).standard_normal(n)
    sm = np.convolve(noise, np.ones(5) / 5, mode="same") - np.convolve(noise, np.ones(40) / 40, mode="same")
    return (sm * np.sin(np.pi * t / 0.17) ** 2 * 0.5).astype(np.float32)


def host_clip(text, max_dur, mock):
    """The friendly spoken host (Dr. Dina's voice, excited): returns samples at 44.1 kHz or None."""
    if mock:
        return None
    try:
        import tts
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "h.wav"
            tts.synthesize_line(text, BIBLE["characters"]["dina"], "excited", p)
            x, rate = _read_wav(p)
        x = _resample(x, rate)
        keep = np.where(np.abs(x) > 0.04 * (np.max(np.abs(x)) or 1))[0]
        if len(keep):
            x = x[max(0, keep[0] - int(0.02 * SR)): keep[-1] + int(0.05 * SR)]
        x = x / (np.max(np.abs(x)) or 1) * 0.9
        dur = len(x) / SR
        if dur > max_dur:                                          # speak a little faster to fit
            x = ffmpeg_filter(x, _atempo_chain(min(1.5, dur / max_dur)))
            x = x[: int(max_dur * SR)]
        return x
    except BaseException as e:
        print(f"[song] host voice unavailable ({e})")
        return None


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
        put_t(buf, music.tone(music.midi(79 + [0, 2, 4, 5][k]), bl * 0.3, "bell", 7, 0.18), V["t_sing"] - bl + k * bl * 0.25)
    for k in range(int((V["t_sing"] - tp) / (bl / 2))):
        put_t(buf, music.shaker(k) * 0.7, tp + k * bl / 2)
    if V["kind"] == "up":                                        # action chant: a bouncier, brighter 2 bars
        c0 = V["t_end"]
        for bar in range(2):
            b0 = c0 + bar * 4 * bl
            ch = "F" if bar == 0 else "G"
            put_t(buf, music.tone(music.midi(BASS[ch]), bl * 0.9, "sine", 5, 0.55), b0)
            put_t(buf, music.tone(music.midi(BASS[ch] + 7), bl * 0.8, "sine", 5, 0.45), b0 + 2 * bl)
            for k in range(4):
                put_t(buf, music.kick() * 0.55, b0 + k * bl)
                put_t(buf, music.block() * 0.5, b0 + (k + 0.5) * bl)
                for m in STAB[ch]:
                    put_t(buf, music.tone(music.midi(m), bl * 0.3, "tri", 12, 0.08), b0 + (k + 0.5) * bl)
            for k in range(8):
                put_t(buf, music.shaker(k) * 0.9, b0 + k * bl / 2)
        for tk in V["chorus_tokens"]:
            for p in tk["parts"]:
                put_t(buf, music.tone(music.midi(p["midi"] + 12), (p["end"] - p["start"]) + 0.12, "bell", 6.0, 0.2), p["start"])
    put_t(buf, music.tone(music.midi(60), bl * 1.8, "bell", 3.0, 0.2), V["t_chorus_end"])      # tidy landing chord
    put_t(buf, music.tone(music.midi(64), bl * 1.8, "bell", 3.0, 0.15), V["t_chorus_end"])
    put_t(buf, music.tone(music.midi(67), bl * 1.8, "bell", 3.0, 0.15), V["t_chorus_end"])


def intro_music(buf, t0, bl, beats):
    for k in range(beats * 2):
        m = (72, 76, 79, 84, 79, 76, 72, 67)[k % 8]
        put_t(buf, music.tone(music.midi(m), bl * 0.7, "bell", 6, 0.22), t0 + k * bl / 2)
        put_t(buf, music.shaker(k) * 0.7, t0 + k * bl / 2)
    put_t(buf, music.tone(music.midi(48), bl * (beats - 0.5), "sine", 1.5, 0.4), t0)


def outro_music(buf, t0, bl):
    for m in (60, 64, 67, 72, 76):
        put_t(buf, music.tone(music.midi(m), 2.5, "bell", 2.2, 0.22), t0)
    put_t(buf, music.voice_synth(music.midi(60), OUTRO_BEATS * bl, "a", vol=0.25, attack=0.2, release=0.6), t0)
    put_t(buf, music.tone(music.midi(48), 2.0, "sine", 2.0, 0.45), t0)


# ------------------------------------------------------------------ the whole soundtrack
def build(ep_dir, order, kinds, bpms, mock=False, bg_offset=0, seed=0):
    ep_dir = Path(ep_dir)
    tl = build_timeline(order, kinds, bpms, bg_offset, seed)
    total = tl["total"] + 0.6
    n = int(total * SR)
    mus = np.zeros(n, dtype=np.float32)
    voc = np.zeros(n, dtype=np.float32)
    hst = np.zeros(n, dtype=np.float32)
    sfx = np.zeros(n, dtype=np.float32)

    intro_music(mus, 0.0, 60.0 / bpms[0], INTRO_BEATS)
    for V in tl["verses"]:
        verse_music(mus, V)
    outro_music(mus, tl["outro"]["t0"], 60.0 / bpms[-1])

    voices = prepare_voices(mock)
    rng = np.random.default_rng(1234 + seed)
    for V in tl["verses"]:
        first_of_line = {}
        for tk in V["tokens"] + V["chorus_tokens"]:
            first_of_line.setdefault(tk["line"], tk)
        for ln, tk in first_of_line.items():                       # a little breath before each line
            put_t(voc, breath(int(tk["start"] * 100)) * 0.5, max(0.0, tk["start"] - 0.2))
        for tk in V["tokens"] + V["chorus_tokens"]:
            accent = 1.12 if tk["word"] in NUMBER_WORDS else 1.0
            for idx, p in enumerate(tk["parts"]):
                dur = p["end"] - p["start"]
                jitter = float(rng.uniform(-0.011, 0.011))        # humans are never perfectly on the grid
                gvar = float(rng.uniform(0.9, 1.08)) * accent
                for name, gain, delay, cents, _ in SINGERS:
                    y = sing_part(name, tk["word"], idx, p["midi"], dur, voices, cents if voices is None else 0.0)
                    put_t(voc, y * gain * gvar, p["start"] + delay + jitter)

    host_info = []
    for h in tl["host"]:                                            # spoken host lines
        clip = host_clip(h["text"], h["max"], mock)
        dur = (len(clip) / SR) if clip is not None else min(h["max"], 0.33 * len(h["text"].split()) + 0.4)
        if clip is not None:
            put_t(hst, clip, h["t0"])
        host_info.append(dict(h, dur=round(float(dur), 2)))
    tl["host"] = host_info

    cache = {}

    def fx(name, t, seed_=0, vol=0.6):
        if (name, seed_) not in cache:
            cache[(name, seed_)] = music.sfx(name, seed_)
        put_t(sfx, cache[(name, seed_)] * vol, max(0.0, t))

    fx("sparkle", 0.2)
    chorus_fx = {"steg": "bloop", "tri": "boing", "ptero": "flap", "bronto": "munch", "trex": "stomp"}
    for V in tl["verses"]:
        bl, sp = V["beat"], V["species"]
        if V["kind"] == "up":
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
            for b in range(8):                                      # the action chant
                fx(chorus_fx[sp], V["t_end"] + b * bl, b % 3, 0.5)
        else:
            for i, ta in enumerate(V["arrive"]):
                fx("bloop", ta, i, 0.35)
            for i, tl_ in enumerate(V["leave"]):
                if tl_:
                    fx("pop", tl_, i, 0.4)
                    fx("giggle", tl_ + 0.05, i + 10 * V["index"], 0.4)
        fx("sparkle", V["t_sing"] + 28 * bl, 0, 0.6)
        fx("whoosh", V["t_done"] - 0.15, 0, 0.45)
    fx("sparkle", tl["outro"]["t0"], 0, 0.7)
    fx("ding", tl["outro"]["t0"] + 0.3, 0, 0.5)

    def peak(x):
        return float(np.max(np.abs(x))) or 1.0

    if voices is not None or float(np.max(np.abs(voc))) > 0:        # studio polish for the singers
        try:
            voc = ffmpeg_filter(voc, "highpass=f=140,equalizer=f=3000:t=q:w=1.2:g=3.5,"
                                     "acompressor=threshold=0.12:ratio=3:attack=8:release=90:makeup=2,"
                                     "aecho=0.8:0.55:45|78:0.20|0.10")[:n]
            voc = np.pad(voc, (0, n - len(voc)))
        except Exception as e:
            print("[song] vocal polish skipped:", e)

    # music dips a little while the host talks so the words are easy to understand
    blk = int(0.02 * SR)
    nb = n // blk
    env = np.abs(hst[: nb * blk]).reshape(nb, blk).mean(axis=1)
    duck = np.convolve((env > 0.01).astype(np.float32), np.ones(10) / 10, mode="same")
    duck = np.interp(np.arange(n) / blk, np.arange(nb) + 0.5, 1 - 0.5 * np.clip(duck, 0, 1)).astype(np.float32)
    mixed = mus / peak(mus) * 0.5 * duck + voc / peak(voc) * 0.85 + hst / peak(hst) * 0.9 + sfx / peak(sfx) * 0.45
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
