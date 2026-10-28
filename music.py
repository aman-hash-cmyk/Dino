"""
music.py - original, royalty-free background music and sound effects, made with maths.

No audio files, no licences, no downloads. The same melodies are used for every episode,
so the channel gets its own recognisable "theme" sound.

  render(sections, total_seconds) -> mono float32 array at 44.1 kHz
        sections = [(start_s, end_s, style), ...]   style: title|intro|adventure|fact|song|outro|end
  sfx(name) -> float32 array      name: pop|whoosh|sparkle|boing|ding
"""
import numpy as np

SR = 44100
PROG = [(48, (0, 4, 7)), (43, (0, 4, 7)), (45, (0, 3, 7)), (41, (0, 4, 7))]   # C - G - Am - F
PENTA = [0, 2, 4, 7, 9]                                                      # C major pentatonic

STYLES = {
    #            bpm  layers
    "title":     (120, ("bass", "arp", "melody", "kick", "hat")),
    "intro":     (112, ("bass", "arp", "melody", "clap")),
    "adventure": (104, ("bass", "arp", "hat", "melody_soft")),
    "fact":      (92,  ("pad", "arp_slow", "melody_soft")),
    "song":      (120, ("bass", "arp", "melody", "kick", "hat", "clap")),
    "outro":     (100, ("pad", "arp", "melody_soft")),
    "end":       (108, ("bass", "arp", "melody", "kick", "hat")),
}


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def tone(freq, dur, kind="tri", decay=6.0, vol=1.0):
    n = max(1, int(dur * SR))
    t = np.arange(n) / SR
    ph = 2 * np.pi * freq * t
    if kind == "sine":
        w = np.sin(ph)
    elif kind == "tri":
        w = 2 / np.pi * np.arcsin(np.sin(ph))
    elif kind == "bell":
        w = (np.sin(ph) + 0.45 * np.sin(2 * ph) + 0.2 * np.sin(3.01 * ph)) / 1.65
    else:
        w = np.sin(ph)
    attack = np.minimum(1.0, t / 0.005)
    return (w * np.exp(-t * decay) * attack * vol).astype(np.float32)


def put(buf, sig, pos):
    pos = int(pos)
    if pos >= len(buf) or pos < 0:
        return
    end = min(len(buf), pos + len(sig))
    buf[pos:end] += sig[: end - pos]


def kick():
    n = int(0.22 * SR)
    t = np.arange(n) / SR
    f = 45 + 110 * np.exp(-t * 18)
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 14)).astype(np.float32)


def hat(seed=1):
    n = int(0.05 * SR)
    noise = np.random.default_rng(seed).standard_normal(n) * np.exp(-np.arange(n) / SR * 90)
    hp = noise - np.concatenate(([0.0], noise[:-1]))
    return (hp * 0.35).astype(np.float32)


def clap(seed=2):
    n = int(0.12 * SR)
    noise = np.random.default_rng(seed).standard_normal(n) * np.exp(-np.arange(n) / SR * 35)
    return (noise * 0.35).astype(np.float32)


_loops = {}


def make_loop(style):
    if style in _loops:
        return _loops[style]
    bpm, layers = STYLES[style]
    beat = 60.0 / bpm
    bars = 8
    buf = np.zeros(int(bars * 4 * beat * SR) + SR, dtype=np.float32)
    rng = np.random.default_rng(sum(map(ord, style)))

    # a 4-bar melodic phrase, repeated twice (second time ends differently)
    phrase = []
    for bar in range(4):
        notes, t = [], 0.0
        while t < 4 - 1e-6:
            length = float(rng.choice([1.0, 0.5, 0.5, 1.0, 2.0])) if t < 3 else 1.0
            length = min(length, 4 - t)
            notes.append((t, length, int(rng.integers(0, len(PENTA))), int(rng.integers(0, 2))))
            t += length
        phrase.append(notes)

    for bar in range(bars):
        root, ivs = PROG[bar % 4]
        b0 = bar * 4 * beat
        if "bass" in layers:
            for k in (0, 1.5, 2, 3.5):
                put(buf, tone(midi(root), beat * 0.8, "sine", 5, 0.5), (b0 + k * beat) * SR)
        if "pad" in layers:
            for iv in ivs:
                put(buf, tone(midi(root + 12 + iv), 4 * beat, "sine", 0.6, 0.10), b0 * SR)
        if "arp" in layers or "arp_slow" in layers:
            step = beat / 2 if "arp" in layers else beat
            count = 8 if "arp" in layers else 4
            order = (0, 1, 2, 1, 0, 1, 2, 1)
            for i in range(count):
                note = root + 24 + ivs[order[i] % 3]
                put(buf, tone(midi(note), step * 1.6, "bell", 6, 0.2), (b0 + i * step) * SR)
        if "kick" in layers:
            for k in (0, 1, 2, 3) if style == "song" else (0, 2):
                put(buf, kick() * 0.7, (b0 + k * beat) * SR)
        if "hat" in layers:
            for k in range(8):
                if k % 2 == 1 or style in ("song", "title"):
                    put(buf, hat(k) , (b0 + k * beat / 2) * SR)
        if "clap" in layers:
            for k in (1, 3):
                put(buf, clap(k), (b0 + k * beat) * SR)
        if "melody" in layers or "melody_soft" in layers:
            vol = 0.30 if "melody" in layers else 0.17
            octave = 72 if "melody" in layers else 67
            for (t, length, deg, up) in phrase[bar % 4]:
                if bar >= 4 and bar % 4 == 3 and t >= 3:
                    deg = 0                                    # clean ending on the second pass
                note = octave + PENTA[deg] + 12 * up * (1 if "melody" in layers else 0)
                put(buf, tone(midi(note), length * beat * 1.1, "tri", 3.5, vol), (b0 + t * beat) * SR)

    loop = buf[: int(bars * 4 * beat * SR)]
    peak = float(np.max(np.abs(loop))) or 1.0
    _loops[style] = (loop / peak * 0.9).astype(np.float32)
    return _loops[style]


def render(sections, total):
    out = np.zeros(int(total * SR), dtype=np.float32)
    for start, end, style in sections:
        n = int((end - start) * SR)
        if n <= 0:
            continue
        loop = make_loop(style)
        reps = int(np.ceil(n / len(loop))) + 1
        seg = np.tile(loop, reps)[:n].copy()
        f = min(int(0.3 * SR), n // 2)
        if f > 0:
            seg[:f] *= np.linspace(0, 1, f)
            seg[-f:] *= np.linspace(1, 0, f)
        put(out, seg, start * SR)
    return out * 0.55


# ---------------------------------------------------------------- sound effects
def sfx(name, seed=0):
    if name == "pop":
        n = int(0.12 * SR)
        t = np.arange(n) / SR
        f = 300 + 700 * np.exp(-t * 28)
        return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 28) * 0.7).astype(np.float32)
    if name == "whoosh":
        n = int(0.5 * SR)
        t = np.arange(n) / SR
        noise = np.random.default_rng(5).standard_normal(n)
        sm = np.convolve(noise, np.ones(14) / 14, mode="same")
        return (sm * np.sin(np.pi * t / 0.5) ** 2 * 0.9).astype(np.float32)
    if name == "sparkle":
        buf = np.zeros(int(0.9 * SR), dtype=np.float32)
        for i, n_ in enumerate((84, 88, 91, 96)):
            put(buf, tone(midi(n_), 0.5, "bell", 7, 0.35), i * 0.07 * SR)
        return buf
    if name == "boing":
        n = int(0.45 * SR)
        t = np.arange(n) / SR
        f = 160 + 260 * np.exp(-t * 6) + 25 * np.sin(2 * np.pi * 14 * t)
        return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 6) * 0.6).astype(np.float32)
    if name == "ding":
        buf = np.zeros(int(0.9 * SR), dtype=np.float32)
        put(buf, tone(midi(88), 0.6, "bell", 5, 0.4), 0)
        put(buf, tone(midi(95), 0.6, "bell", 5, 0.3), 0.12 * SR)
        return buf
    a = _more_sfx(name, seed)
    pk = float(np.max(np.abs(a))) or 1.0
    return a * (0.8 / pk) if pk > 0.8 else a


# ---------------------------------------------------------------- voice-like sounds (choir, giggles)
VOWELS = {"a": (800, 1150, 2900), "e": (350, 2200, 2900), "i": (300, 2300, 3000),
          "o": (500, 900, 2800), "u": (330, 870, 2250)}


def voice_synth(f0, dur, vowel="a", vib=5.5, vol=1.0, attack=0.03, release=0.08):
    """A simple 'ooh/aah' singing voice: harmonics shaped by vowel formants."""
    n = max(8, int(dur * SR))
    t = np.arange(n) / SR
    f = f0 * (1 + 0.008 * np.sin(2 * np.pi * vib * t))
    ph = 2 * np.pi * np.cumsum(f) / SR
    fm = VOWELS.get(vowel, VOWELS["a"])
    out = np.zeros(n, dtype=np.float32)
    for h in range(1, 40):
        fh = h * f0
        if fh > 5500:
            break
        amp = sum(np.exp(-0.5 * ((fh - c) / bw) ** 2) for c, bw in zip(fm, (110, 160, 260))) / h ** 0.6
        out += (amp * np.sin(h * ph)).astype(np.float32)
    env = np.minimum(1.0, t / attack) * np.minimum(1.0, (dur - t) / release).clip(0, 1)
    peak = float(np.max(np.abs(out))) or 1.0
    return (out / peak * env * vol).astype(np.float32)


def block():
    n = int(0.06 * SR)
    t = np.arange(n) / SR
    return ((np.sin(2 * np.pi * 1500 * t) * np.exp(-t * 70) + 0.5 * np.sin(2 * np.pi * 900 * t) * np.exp(-t * 55)) * 0.7).astype(np.float32)


def shaker(seed=3):
    n = int(0.07 * SR)
    noise = np.random.default_rng(seed).standard_normal(n) * np.exp(-np.arange(n) / SR * 60)
    return ((noise - np.concatenate(([0.0], noise[:-1]))) * 0.3).astype(np.float32)


def _more_sfx(name, seed):
    rng = np.random.default_rng(seed + 11)
    if name == "crack":
        buf = np.zeros(int(0.3 * SR), dtype=np.float32)
        for k, off in enumerate((0.0, 0.07, 0.15)):
            n = int(0.05 * SR)
            noise = rng.standard_normal(n) * np.exp(-np.arange(n) / SR * 90)
            hp = noise - np.concatenate(([0.0], noise[:-1]))
            put(buf, (hp * 0.5).astype(np.float32), off * SR)
            put(buf, tone(180 + 40 * k, 0.06, "sine", 45, 0.35), off * SR)
        return buf
    if name == "giggle":
        buf = np.zeros(int(0.7 * SR), dtype=np.float32)
        base = 560 + 90 * rng.random()
        for k in range(3):
            put(buf, voice_synth(base * (1 + 0.07 * k), 0.1, "e", vib=0, vol=0.55, attack=0.01, release=0.05), (0.02 + k * 0.16) * SR)
        return buf
    if name == "stomp":
        n = int(0.2 * SR)
        t = np.arange(n) / SR
        f = 48 + 50 * np.exp(-t * 20)
        return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 16) * 0.8).astype(np.float32)
    if name == "munch":
        buf = np.zeros(int(0.3 * SR), dtype=np.float32)
        for off in (0.0, 0.11):
            n = int(0.08 * SR)
            noise = np.convolve(rng.standard_normal(n), np.ones(6) / 6, mode="same") * np.exp(-np.arange(n) / SR * 38)
            put(buf, (noise * 0.9).astype(np.float32), off * SR)
        return buf
    if name == "flap":
        n = int(0.22 * SR)
        t = np.arange(n) / SR
        noise = np.convolve(rng.standard_normal(n), np.ones(30) / 30, mode="same")
        return (noise * np.sin(np.pi * t / 0.22) ** 2 * 1.4).astype(np.float32)
    if name == "bloop":
        n = int(0.14 * SR)
        t = np.arange(n) / SR
        f = 280 + 420 * (t / 0.14)
        return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 14) * 0.6).astype(np.float32)
    raise ValueError(name)
