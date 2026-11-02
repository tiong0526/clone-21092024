"""Compose an original background track for the slideshow from real
instrument recordings (piano, strings, guitar, harp, flute, xylophone).

The note samples come from the MIT-licensed tonejs-instruments npm packages
listed in package.json; they are installed into video/node_modules on first
use. Every melody and arrangement here is original, so the result is free to
use on YouTube.

Styles:
  heartfelt  piano and strings, warm and touching (72 BPM, D major)
  sunny      acoustic guitar, piano and xylophone, bright and cheerful (100 BPM, G major)
  gentle     harp, flute and nylon guitar, light and dreamy (84 BPM, F major)

Usage: python3 music.py <seconds> <out.wav> [--style heartfelt]
"""
import argparse
import subprocess
import wave
from functools import lru_cache
from pathlib import Path

import numpy as np

SR = 44100
HERE = Path(__file__).resolve().parent
MODULES = HERE / "node_modules"
NOTE_NAMES = {"C": 0, "Cs": 1, "D": 2, "Ds": 3, "E": 4, "F": 5, "Fs": 6, "G": 7, "Gs": 8,
              "A": 9, "As": 10, "B": 11}

# Per-instrument level after each sample is RMS-normalised.
GAIN = {"piano": 1.0, "cello": .8, "violin": .65, "contrabass": .9, "guitar-acoustic": .8,
        "guitar-nylon": .9, "harp": .9, "flute": .7, "xylophone": 1.0}


def ensure_samples():
    if not (MODULES / "tonejs-instrument-piano-mp3").exists():
        subprocess.run(["npm", "install", "--no-audit", "--no-fund", "--prefix", str(HERE)], check=True)


def note_midi(name):
    i = 2 if len(name) > 1 and name[1] == "s" else 1
    return 12 * (int(name[i:]) + 1) + NOTE_NAMES[name[:i]]


@lru_cache(None)
def sample_map(inst):
    d = MODULES / f"tonejs-instrument-{inst}-mp3"
    out = {}
    for f in d.glob("*.mp3"):
        if " " not in f.stem:  # skip alternates like "F2 v2"
            out[note_midi(f.stem)] = f
    return out


@lru_cache(None)
def decode(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "2",
                          "-ar", str(SR), "-"], check=True, capture_output=True).stdout
    a = np.frombuffer(raw, "<f4").reshape(-1, 2).astype(np.float64)
    mono = np.abs(a).max(axis=1)
    start = int(np.argmax(mono > mono.max() * .02))  # trim leading silence
    a = a[max(start - 40, 0):]
    rms = np.sqrt((a[: SR // 2] ** 2).mean()) + 1e-9
    return a * (.1 / rms)


@lru_cache(None)
def sample(inst, midi):
    m = sample_map(inst)
    src = min(m, key=lambda k: (abs(k - midi), k > midi))  # nearest, prefer shifting up
    a = decode(m[src])
    ratio = 2 ** ((midi - src) / 12)
    if ratio == 1:
        return a
    idx = np.arange(0, len(a) - 1, ratio)
    x = np.arange(len(a))
    return np.stack([np.interp(idx, x, a[:, 0]), np.interp(idx, x, a[:, 1])], axis=1)


class Mix:
    def __init__(self, seconds, seed):
        self.buf = np.zeros((int((seconds + 12) * SR), 2))
        self.rng = np.random.default_rng(seed)

    def note(self, inst, t, midi, dur, vel=.8, pan=0., attack=0., release=.35, human=True):
        if human:
            t += self.rng.normal(0, .006)
            vel *= 1 + self.rng.normal(0, .06)
        s = sample(inst, midi)
        n = min(len(s), int((dur + release) * SR))
        s = s[:n].copy()
        r = min(int(release * SR), n)
        s[n - r:] *= np.linspace(1, 0, r)[:, None] ** 2
        if attack:
            a = min(int(attack * SR), n)
            s[:a] *= np.linspace(0, 1, a)[:, None]
        g = vel * GAIN[inst]
        ang = (pan + 1) * np.pi / 4
        i = max(int(t * SR), 0)
        n = min(n, len(self.buf) - i)
        self.buf[i:i + n, 0] += s[:n, 0] * g * np.cos(ang)
        self.buf[i:i + n, 1] += s[:n, 1] * g * np.sin(ang)

    def noise_hit(self, t, kind, vel):
        """Soft synthesized percussion (kick, shaker, clap)."""
        if kind == "kick":
            n = int(.35 * SR)
            tt = np.arange(n) / SR
            f = 50 + 70 * np.exp(-tt / .03)
            s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / .12)
            s = np.stack([s, s], axis=1)
        else:
            n = int((.08 if kind == "shaker" else .22) * SR)
            tt = np.arange(n) / SR
            x = self.rng.standard_normal((n + 2, 2))
            x = np.diff(x, 2 if kind == "shaker" else 1, axis=0)[:n]
            if kind == "clap":
                x = np.cumsum(x, axis=0) * .5 - np.cumsum(np.cumsum(x, axis=0), axis=0) * .002
                x /= np.abs(x).max()
            s = x * (np.minimum(tt / .004, 1) * np.exp(-tt / (.025 if kind == "shaker" else .06)))[:, None]
        i = int(t * SR)
        self.buf[i:i + n] += s[: len(self.buf) - i] * vel


# ---------------------------------------------------------------- arrangement

def chord(bass, *tones):
    return bass, list(tones)


def plan(n_bars, intro=4, outro=2):
    """Section label per bar: intro, then a repeating cycle of 8-bar sections."""
    cycle = ["A", "A2", "B", "A3", "brk", "B2", "A2", "A3"]
    labels = ["intro"] * intro
    k = 0
    while len(labels) < n_bars - outro:
        labels += [cycle[k % len(cycle)]] * 8
        k += 1
    labels = labels[: n_bars - outro] + ["outro"] * outro
    return labels


def bar_pos(labels, b):
    """Index of bar b inside its section."""
    j = b
    while j > 0 and labels[j - 1] == labels[b]:
        j -= 1
    return b - j


def melody_at(mel, pos):
    return [(o, m, d) for bar, o, m, d in mel if bar == pos % 8]


def heartfelt(mix, seconds):
    bpm = 72
    beat = 60 / bpm
    bar = 4 * beat
    prog_a = [chord(38, 62, 66, 69), chord(37, 61, 64, 69), chord(35, 62, 66, 71), chord(31, 62, 67, 71),
              chord(42, 62, 66, 69), chord(31, 62, 67, 71), chord(40, 62, 64, 67, 71), chord(33, 61, 64, 69)]
    prog_b = [chord(31, 62, 67, 71), chord(33, 61, 64, 69), chord(42, 61, 66, 69), chord(35, 62, 66, 71),
              chord(31, 62, 67, 71), chord(33, 61, 64, 69), chord(38, 62, 66, 69), chord(38, 62, 66, 69)]
    mel_a = [(0, 0, 78, 1.5), (0, 1.5, 76, .5), (0, 2, 74, 1), (0, 3, 69, 1),
             (1, 0, 76, 2), (1, 2, 73, 1), (1, 3, 69, 1),
             (2, 0, 74, 1.5), (2, 1.5, 73, .5), (2, 2, 71, 1), (2, 3, 78, 1),
             (3, 0, 76, 3), (3, 3, 74, 1),
             (4, 0, 74, 1), (4, 1, 78, 1), (4, 2, 81, 1.5), (4, 3.5, 79, .5),
             (5, 0, 78, 1), (5, 1, 76, 1), (5, 2, 74, 1), (5, 3, 71, 1),
             (6, 0, 71, 1), (6, 1, 74, 1), (6, 2, 76, 1.5), (6, 3.5, 74, .5),
             (7, 0, 73, 2), (7, 2, 69, 2)]
    mel_b = [(0, 0, 71, 1), (0, 1, 74, 1), (0, 2, 79, 2),
             (1, 0, 78, 1), (1, 1, 76, 1), (1, 2, 73, 2),
             (2, 0, 73, 1), (2, 1, 78, 1), (2, 2, 81, 2),
             (3, 0, 78, 3), (3, 3, 76, 1),
             (4, 0, 74, 1), (4, 1, 76, 1), (4, 2, 79, 1), (4, 3, 78, 1),
             (5, 0, 76, 1), (5, 1, 78, 1), (5, 2, 81, 1.5), (5, 3.5, 79, .5),
             (6, 0, 78, 4),
             (7, 0, 74, 3)]
    n_bars = int((seconds - 1) // bar)
    labels = plan(n_bars)
    for b, lab in enumerate(labels):
        t0 = b * bar
        pos = bar_pos(labels, b)
        is_b = lab.startswith("B")
        bass, tones = (prog_b if is_b else prog_a)[pos % 8]
        if lab == "outro":
            bass, tones = 38, [62, 66, 69]
        # Piano: broken chords in eighths (left hand bass + right hand pattern)
        top = sorted(tones)[-3:]
        if lab in ("intro", "brk", "outro"):
            pattern = [(0, bass + 12), (1, top[0]), (2, top[1]), (3, top[2])]
            for k, m in pattern:
                mix.note("piano", t0 + k * beat, m, beat * 2, .5 if k else .6, pan=-.15 + .1 * k)
            if lab == "outro":
                mix.note("piano", t0, bass, bar * 2, .55)
                if pos == 1:
                    mix.note("piano", t0 + bar, 74, bar * 2, .5, pan=.2)
                    break
        else:
            pattern = [bass, bass + 7, bass + 12, top[1], top[2], top[1], bass + 12, bass + 7]
            for k, m in enumerate(pattern):
                mix.note("piano", t0 + k * beat / 2, m, beat, .32 if k % 2 else .4, pan=-.25 + .07 * k)
        # Cello: long bowed bass note
        if lab not in ("intro", "brk"):
            c = bass + 12 if bass < 36 else bass
            while c < 36:
                c += 12
            mix.note("cello", t0, c, bar, .38, pan=-.35, attack=.25, release=.5, human=False)
        # Violin pad on chord tones in B sections
        if lab in ("B", "B2", "A3"):
            for i, m in enumerate(top[1:]):
                mix.note("violin", t0, m - 12 if m > 70 else m, bar, .22, pan=.3 + .2 * i,
                         attack=.4, release=.6, human=False)
        # Melody
        mel = mel_b if is_b else mel_a
        if lab in ("A", "brk"):
            for o, m, d in melody_at(mel, pos):
                mix.note("piano", t0 + o * beat, m, d * beat, .65, pan=.15)
        elif lab in ("A2", "B", "A3", "B2"):
            for o, m, d in melody_at(mel, pos):
                mix.note("violin", t0 + o * beat, m, d * beat, .8, pan=.1, attack=.06, release=.3)
            if lab in ("A3", "B2"):
                for o, m, d in melody_at(mel, pos):
                    mix.note("piano", t0 + o * beat, m + 12, d * beat, .3, pan=.25)
    return {"reverb": 2.6, "wet": .30}


def sunny(mix, seconds):
    bpm = 100
    beat = 60 / bpm
    bar = 4 * beat
    G = (43, [43, 47, 50, 55, 59, 67])
    Dm = (38, [50, 57, 62, 66])
    Em = (40, [40, 47, 52, 55, 59, 64])
    C = (36, [48, 52, 55, 60, 64])
    Bm = (35, [47, 54, 59, 62, 66])
    prog_a = [G, Dm, Em, C, G, Dm, Em, C]
    prog_b = [C, Dm, Bm, Em, C, Dm, G, Dm]
    mel_a = [(0, 0, 71, .5), (0, .5, 74, .5), (0, 1, 79, 1), (0, 2, 78, .5), (0, 2.5, 79, .5), (0, 3, 74, 1),
             (1, 0, 78, 1), (1, 1, 76, .5), (1, 1.5, 74, .5), (1, 2, 69, 2),
             (2, 0, 71, .5), (2, .5, 76, .5), (2, 1, 79, 1), (2, 2, 78, .5), (2, 2.5, 76, .5), (2, 3, 71, 1),
             (3, 0, 72, .5), (3, .5, 76, .5), (3, 1, 79, 1.5), (3, 2.5, 76, .5), (3, 3, 74, 1),
             (4, 0, 71, .5), (4, .5, 74, .5), (4, 1, 79, 1), (4, 2, 81, .5), (4, 2.5, 83, .5), (4, 3, 79, 1),
             (5, 0, 81, 1.5), (5, 1.5, 78, .5), (5, 2, 74, 2),
             (6, 0, 76, 1), (6, 1, 79, 1), (6, 2, 83, 1), (6, 3, 81, .5), (6, 3.5, 79, .5),
             (7, 0, 79, 1.5), (7, 1.5, 76, .5), (7, 2, 74, 2)]
    mel_b = [(0, 0, 76, 1), (0, 1, 79, 1), (0, 2, 84, 2),
             (1, 0, 83, 1), (1, 1, 81, 1), (1, 2, 78, 2),
             (2, 0, 78, 1), (2, 1, 83, 1), (2, 2, 86, 1.5), (2, 3.5, 83, .5),
             (3, 0, 79, 3), (3, 3, 76, 1),
             (4, 0, 76, .5), (4, .5, 79, .5), (4, 1, 84, 1), (4, 2, 83, .5), (4, 2.5, 81, .5), (4, 3, 79, 1),
             (5, 0, 78, 1), (5, 1, 81, 1), (5, 2, 86, 1), (5, 3, 84, 1),
             (6, 0, 83, 3), (6, 3, 81, 1),
             (7, 0, 81, 1), (7, 1, 78, 1), (7, 2, 74, 2)]
    strum = [(0, 1, .9), (1, 1, .7), (1.5, -1, .5), (2.5, -1, .55), (3, 1, .7), (3.5, -1, .5)]
    n_bars = int((seconds - 1) // bar)
    labels = plan(n_bars)
    for b, lab in enumerate(labels):
        t0 = b * bar
        pos = bar_pos(labels, b)
        is_b = lab.startswith("B")
        bass, voicing = (prog_b if is_b else prog_a)[pos % 8]
        if lab == "outro":
            bass, voicing = G
        # Acoustic guitar
        if lab == "outro":
            for i, m in enumerate(voicing):
                mix.note("guitar-acoustic", t0 + i * .03, m, bar * 2, .6, pan=-.3)
            mix.note("piano", t0, 43, bar * 2, .5)
            mix.note("xylophone", t0 + .02, 79, bar, .6, pan=.3)
            break
        if lab == "brk":
            pick = [0, 3, 4, 5, 2, 4, 3, 5]
            for k, idx in enumerate(pick):
                mix.note("guitar-acoustic", t0 + k * beat / 2, voicing[idx % len(voicing)], beat, .55, pan=-.2)
        else:
            for off, direction, v in strum:
                notes = voicing if direction > 0 else voicing[::-1][:4]
                for i, m in enumerate(notes):
                    mix.note("guitar-acoustic", t0 + off * beat + i * .012, m, beat * .9,
                             v * (.45 if lab == "intro" else .45), pan=-.35 + .1 * i / len(notes))
        # Bass: piano left hand on 1 and 3
        if lab not in ("intro", "brk"):
            mix.note("piano", t0, bass, beat * 1.5, .55, pan=-.1)
            mix.note("piano", t0 + 2 * beat, bass + (7 if pos % 2 else 0), beat * 1.5, .5, pan=-.1)
        # Light percussion
        if lab not in ("intro", "brk"):
            for k in range(8):
                mix.noise_hit(t0 + k * beat / 2, "shaker", .012 if k % 2 else .018)
        if lab in ("A2", "B", "B2", "A3"):
            mix.noise_hit(t0, "kick", .12)
            mix.noise_hit(t0 + 2 * beat, "kick", .1)
            mix.noise_hit(t0 + beat, "clap", .05)
            mix.noise_hit(t0 + 3 * beat, "clap", .05)
        # Melody
        mel = mel_b if is_b else mel_a
        if lab in ("A", "A2", "B", "A3", "B2"):
            for o, m, d in melody_at(mel, pos):
                mix.note("piano", t0 + o * beat, m, d * beat, .55, pan=.15)
        if lab in ("A2", "B2", "brk"):
            for o, m, d in melody_at(mel, pos):
                mix.note("xylophone", t0 + o * beat, m, d * beat, .9, pan=.35)
    return {"reverb": 1.6, "wet": .18}


def gentle(mix, seconds):
    bpm = 84
    beat = 60 / bpm
    bar = 4 * beat
    F = (41, [53, 57, 60])
    Cc = (36, [48, 52, 55])
    Dm = (38, [50, 53, 57])
    Bb = (34, [46, 50, 53])
    Am = (33, [45, 48, 52])
    Gm = (31, [43, 46, 50])
    prog_a = [F, Cc, Dm, Bb, F, Cc, Bb, Cc]
    prog_b = [Bb, Cc, Am, Dm, Gm, Cc, F, F]
    mel_a = [(0, 0, 69, 1), (0, 1, 72, 1), (0, 2, 77, 1.5), (0, 3.5, 76, .5),
             (1, 0, 76, 1), (1, 1, 74, 1), (1, 2, 72, 2),
             (2, 0, 74, 1), (2, 1, 77, 1), (2, 2, 81, 1.5), (2, 3.5, 79, .5),
             (3, 0, 77, 3), (3, 3, 74, 1),
             (4, 0, 72, 1), (4, 1, 77, 1), (4, 2, 79, 1), (4, 3, 81, 1),
             (5, 0, 79, 1.5), (5, 1.5, 76, .5), (5, 2, 72, 2),
             (6, 0, 74, 1), (6, 1, 77, 1), (6, 2, 82, 1), (6, 3, 81, 1),
             (7, 0, 79, 2), (7, 2, 76, 2)]
    mel_b = [(0, 0, 77, 1), (0, 1, 74, 1), (0, 2, 70, 2),
             (1, 0, 72, 1), (1, 1, 76, 1), (1, 2, 79, 2),
             (2, 0, 81, 1), (2, 1, 76, 1), (2, 2, 72, 2),
             (3, 0, 74, 1), (3, 1, 77, 1), (3, 2, 81, 2),
             (4, 0, 82, 1), (4, 1, 81, 1), (4, 2, 79, 1), (4, 3, 74, 1),
             (5, 0, 76, 1), (5, 1, 79, 1), (5, 2, 84, 2),
             (6, 0, 81, 4),
             (7, 0, 77, 4)]
    n_bars = int((seconds - 1) // bar)
    labels = plan(n_bars)
    for b, lab in enumerate(labels):
        t0 = b * bar
        pos = bar_pos(labels, b)
        is_b = lab.startswith("B")
        bass, tri = (prog_b if is_b else prog_a)[pos % 8]
        if lab == "outro":
            bass, tri = F
            for i, m in enumerate([41, 53, 57, 60, 65, 69, 72, 77]):
                mix.note("harp", t0 + i * beat / 4, m, bar * 2, .55, pan=-.3 + .08 * i)
            mix.note("flute", t0 + 2 * beat, 77, bar, .4, pan=.2, attack=.1, release=.8)
            break
        # Harp: rising and falling arpeggio over two octaves in eighths
        up = [bass + 12, tri[0] + 12, tri[1] + 12, tri[2] + 12, tri[0] + 24, tri[2] + 12, tri[1] + 12, tri[0] + 12]
        while min(up) < 36:
            up = [m + 12 for m in up]
        for k, m in enumerate(up):
            mix.note("harp", t0 + k * beat / 2, m, beat * 1.5, .36 if k % 2 else .44, pan=-.4 + .08 * k)
        # Nylon guitar: soft chord on beats 1 and 3 from A2 onward
        if lab not in ("intro", "A"):
            for off in (0, 2):
                for i, m in enumerate(tri):
                    mix.note("guitar-nylon", t0 + off * beat + i * .02, m + 12 if m < 52 else m,
                             beat * 2, .32, pan=.35)
        # Cello bass in fuller sections
        if lab in ("B", "A3", "B2"):
            c = bass
            while c < 36:
                c += 12
            mix.note("cello", t0, c, bar, .55, pan=-.2, attack=.3, release=.5, human=False)
        # Melody: flute, with harp taking it in breaks
        mel = mel_b if is_b else mel_a
        if lab in ("A", "A2", "B", "A3", "B2"):
            for o, m, d in melody_at(mel, pos):
                mix.note("flute", t0 + o * beat, m, d * beat, .75, pan=.1, attack=.05, release=.35)
        elif lab == "brk":
            for o, m, d in melody_at(mel, pos):
                mix.note("harp", t0 + o * beat, m + 12, d * beat, .45, pan=.25)
    return {"reverb": 2.4, "wet": .28}


STYLES = {"heartfelt": heartfelt, "sunny": sunny, "gentle": gentle}


def reverb(x, seconds, wet, seed=7):
    """Convolve with a synthetic hall impulse (decaying, darkened noise)."""
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    ir = rng.standard_normal((n, 2)) * np.exp(-t * 6.9 / seconds)[:, None]
    # darken the tail with a gentle lowpass
    spec = np.fft.rfft(ir, axis=0)
    f = np.fft.rfftfreq(n, 1 / SR)
    spec *= (1 / (1 + (f / 4500) ** 2))[:, None]
    ir = np.fft.irfft(spec, n, axis=0)
    ir[: int(.012 * SR)] = 0  # pre-delay
    ir /= np.sqrt((ir ** 2).sum(axis=0))
    block = 1 << 18
    nfft = 1 << int(np.ceil(np.log2(block + n)))
    H = np.fft.rfft(ir, nfft, axis=0)
    out = np.zeros((len(x) + n, 2))
    for i in range(0, len(x), block):
        seg = x[i:i + block]
        y = np.fft.irfft(np.fft.rfft(seg, nfft, axis=0) * H, nfft, axis=0)[: len(seg) + n]
        out[i:i + len(y)] += y
    return x + wet * out[: len(x)]


def compose(seconds, style):
    ensure_samples()
    mix = Mix(seconds, seed=2026)
    fx = STYLES[style](mix, seconds)
    x = reverb(mix.buf, fx["reverb"], fx["wet"])[: int(seconds * SR)]
    n = len(x)
    fade = np.ones(n)
    fi, fo = int(1.5 * SR), int(4 * SR)
    fade[:fi] = np.linspace(0, 1, fi)
    fade[-fo:] = np.minimum(fade[-fo:], np.linspace(1, 0, fo))
    x *= fade[:, None]
    # Background level: about -20 dBFS RMS, with any stray peaks softly held under -1 dBFS
    x *= .1 / np.sqrt((x[fi:-fo] ** 2).mean())
    loud = np.abs(x) > .7
    x[loud] = np.sign(x[loud]) * (.7 + .19 * np.tanh((np.abs(x[loud]) - .7) / .19))
    return x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("seconds", type=float)
    ap.add_argument("out")
    ap.add_argument("--style", choices=sorted(STYLES), default="heartfelt")
    args = ap.parse_args()
    audio = compose(args.seconds, args.style)
    pcm = (audio * 32767).astype("<i2")
    with wave.open(args.out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


if __name__ == "__main__":
    main()
