"""Compose an original, royalty-free background track for the slideshow.

Light and happy: I-V-vi-IV in C major at 100 BPM with piano arpeggios,
a bell melody, warm pad, soft bass and gentle percussion.

Usage: python3 music.py <seconds> <out.wav>
"""
import sys
import wave

import numpy as np
from scipy.signal import butter, oaconvolve, sosfilt

SR = 44100
BPM = 100
BEAT = 60 / BPM
BAR = 4 * BEAT
rng = np.random.default_rng(2026)

# Chord per bar: (bass root, chord tones) as MIDI notes.
CHORDS = [
    (36, [60, 64, 67]),  # C
    (43, [59, 62, 67]),  # G
    (45, [57, 60, 64]),  # Am
    (41, [57, 60, 65]),  # F
]

# 8-bar bell melody: (bar, beat offset, midi, length in beats)
MELODY = [
    (0, 0, 76, 1), (0, 1, 79, 1), (0, 2, 84, 1.5), (0, 3.5, 83, .5),
    (1, 0, 83, 1), (1, 1, 79, 1), (1, 2, 74, 2),
    (2, 0, 72, 1), (2, 1, 76, 1), (2, 2, 81, 1.5), (2, 3.5, 79, .5),
    (3, 0, 77, 1), (3, 1, 81, 1), (3, 2, 81, 2),
    (4, 0, 79, .5), (4, .5, 76, .5), (4, 1, 79, 1), (4, 2, 84, 1), (4, 3, 88, 1),
    (5, 0, 86, 1.5), (5, 1.5, 83, .5), (5, 2, 79, 2),
    (6, 0, 81, 1), (6, 1, 84, 1), (6, 2, 83, 1), (6, 3, 81, 1),
    (7, 0, 79, 1), (7, 1, 77, 1), (7, 2, 76, 2),
]


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def env(n, attack, decay):
    t = np.arange(n) / SR
    a = np.minimum(t / attack, 1.0)
    return a * np.exp(-t / decay)


def add(buf, start, sig):
    i = int(start * SR)
    if i >= len(buf):
        return
    sig = sig[: len(buf) - i]
    buf[i:i + len(sig)] += sig


def piano(m, dur, vel):
    n = int((dur + 1.2) * SR)
    t = np.arange(n) / SR
    f = hz(m)
    s = (np.sin(2 * np.pi * f * t) + .45 * np.sin(4 * np.pi * f * t)
         + .18 * np.sin(6 * np.pi * f * t) + .06 * np.sin(8 * np.pi * f * t))
    return vel * s * env(n, .004, .55)


def bell(m, dur, vel):
    n = int((dur + 1.5) * SR)
    t = np.arange(n) / SR
    f = hz(m)
    s = (np.sin(2 * np.pi * f * t) + .35 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t / .25)
         + .15 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t / .1))
    return vel * s * env(n, .003, .8)


def pad(notes, dur, vel):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for m in notes:
        for det in (-.07, .07):
            f = hz(m + det)
            s += np.sin(2 * np.pi * f * t) + .3 * np.sin(4 * np.pi * f * t)
    fade = np.minimum(np.minimum(t / .5, (dur - t) / .5), 1.0).clip(0)
    return vel * s * fade / len(notes)


def bass(m, dur, vel):
    n = int((dur + .1) * SR)
    t = np.arange(n) / SR
    f = hz(m)
    s = np.sin(2 * np.pi * f * t) + .25 * np.sin(4 * np.pi * f * t)
    return vel * s * env(n, .01, dur * .9)


def kick(vel):
    n = int(.35 * SR)
    t = np.arange(n) / SR
    f = 50 + 70 * np.exp(-t / .03)
    return vel * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / .12)


_hp = butter(2, 6000, "highpass", fs=SR, output="sos")
_bp = butter(2, [900, 4000], "bandpass", fs=SR, output="sos")


def shaker(vel):
    n = int(.08 * SR)
    return vel * sosfilt(_hp, rng.standard_normal(n)) * env(n, .005, .025)


def clap(vel):
    n = int(.25 * SR)
    return vel * sosfilt(_bp, rng.standard_normal(n)) * env(n, .002, .07)


def compose(seconds):
    total = int((seconds + 3) * SR)
    L = np.zeros(total)
    R = np.zeros(total)
    bars = int(np.ceil(seconds / BAR)) + 1
    for b in range(bars):
        t0 = b * BAR
        root, tones = CHORDS[b % 4]
        phrase = (b // 8) % 6  # 0: intro, then cycles of build/full/breather
        intro = b < 4
        full = phrase in (1, 2, 4, 5) and not intro
        # Pad: always present, softly
        p = pad(tones + [tones[0] + 12], BAR + .3, .10)
        add(L, t0, p)
        add(R, t0, p)
        # Piano arpeggio in eighth notes
        arp = [tones[0], tones[1], tones[2], tones[0] + 12, tones[2], tones[1], tones[0] + 12, tones[1]]
        for i, m in enumerate(arp):
            s = piano(m, BEAT / 2, .11 if i % 2 == 0 else .08)
            pan = .35 + .3 * (i % 2)
            add(L, t0 + i * BEAT / 2, s * (1 - pan))
            add(R, t0 + i * BEAT / 2, s * pan)
        if intro:
            continue
        # Bass on beats 1, 2.5, 3
        for off, d in ((0, 1.5), (1.5, .5), (2, 2)):
            s = bass(root, d * BEAT, .15)
            add(L, t0 + off * BEAT, s)
            add(R, t0 + off * BEAT, s)
        # Percussion
        for beat in range(4):
            if full and beat in (0, 2):
                add(L, t0 + beat * BEAT, kick(.22))
                add(R, t0 + beat * BEAT, kick(.22))
            if full and beat in (1, 3):
                c = clap(.10)
                add(L, t0 + beat * BEAT, c * .9)
                add(R, t0 + beat * BEAT, c)
            for s16 in range(4 if full else 2):
                step = 4 if full else 2
                v = .035 if s16 % 2 else .05
                sh = shaker(v)
                add(L, t0 + (beat + s16 / step) * BEAT, sh * .6)
                add(R, t0 + (beat + s16 / step) * BEAT, sh)
        # Bell melody in full sections
        if full:
            for bar, off, m, d in MELODY:
                if bar == b % 8:
                    s = bell(m, d * BEAT, .13)
                    add(L, t0 + off * BEAT, s * .55)
                    add(R, t0 + off * BEAT, s * .45)

    # Simple room reverb: decaying noise impulse response
    n_ir = int(1.6 * SR)
    t = np.arange(n_ir) / SR
    lp = butter(1, 5000, "lowpass", fs=SR, output="sos")
    irL = sosfilt(lp, rng.standard_normal(n_ir)) * np.exp(-t / .35)
    irR = sosfilt(lp, rng.standard_normal(n_ir)) * np.exp(-t / .35)
    irL /= np.sqrt((irL ** 2).sum())
    irR /= np.sqrt((irR ** 2).sum())
    L = L + .22 * oaconvolve(L, irL)[:total]
    R = R + .22 * oaconvolve(R, irR)[:total]

    out = np.stack([L, R], axis=1)[: int(seconds * SR)]
    # Fade in 2s, fade out 5s
    n = len(out)
    fade = np.ones(n)
    fi, fo = int(2 * SR), int(5 * SR)
    fade[:fi] = np.linspace(0, 1, fi)
    fade[-fo:] = np.minimum(fade[-fo:], np.linspace(1, 0, fo))
    out *= fade[:, None]
    # Gentle soft-clip and normalise to -1 dBFS
    out = np.tanh(out * 1.2)
    out *= 0.89 / np.abs(out).max()
    return out


def main():
    seconds = float(sys.argv[1])
    path = sys.argv[2]
    audio = compose(seconds)
    pcm = (audio * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


if __name__ == "__main__":
    main()
