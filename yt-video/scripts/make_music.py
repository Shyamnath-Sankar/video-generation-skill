#!/usr/bin/env python3
"""Generate a royalty-free background track in code (numpy + scipy), locked to the video's beat grid.
Only run this when the user asked for music.

usage: make_music.py --out music.wav --duration 31.4 [--mood upbeat] [--bpm 116] [--key C] [--seed 7]
                     [--accents 4.2,12.8] [--risers] [--fade 1.8]
       make_music.py --list

Beat 1 of bar 1 lands at t=0, so beat n is at n*60/bpm: the page can pulse on beats (K.beat / K.pulse) and
timeline.py can snap scene changes onto them. --accents adds a crash + sub drop at those times
(scene changes flagged "accent": true); --risers adds a noise riser into each accent.
Everything is synthesised from oscillators, filtered seeded noise and envelopes: no samples, no licences.
"""
import argparse, math, sys, wave
import numpy as np
from scipy.signal import butter, sosfilt

SR = 48000
SCALES = {"major": [0, 2, 4, 5, 7, 9, 11], "minor": [0, 2, 3, 5, 7, 8, 10]}
NOTE = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}

# progressions are scale degrees (0 = I/i), one chord per bar
MOODS = {
    "upbeat":    {"bpm": 116, "key": "C", "scale": "major", "prog": [0, 4, 5, 3], "drums": "house", "keys": "pad", "lead": "pluck", "bass": "offbeat", "pump": 0.55, "desc": "bright pop/house: four-on-the-floor, offbeat bass, plucked arps"},
    "chill":     {"bpm": 84,  "key": "F", "scale": "major", "prog": [0, 5, 3, 4], "drums": "soft", "keys": "rhodes", "lead": "pluck", "bass": "root", "pump": 0.0, "desc": "soft electric piano, light drums, warm - good under calm narration"},
    "lofi":      {"bpm": 78,  "key": "A", "scale": "minor", "prog": [0, 5, 2, 6], "drums": "boombap", "keys": "rhodes", "lead": None, "bass": "root", "pump": 0.0, "swing": 0.16, "vinyl": True, "desc": "lo-fi hip hop: swung drums, dusty keys, vinyl crackle"},
    "cinematic": {"bpm": 90,  "key": "D", "scale": "minor", "prog": [0, 5, 2, 6], "drums": "toms", "keys": "pad", "lead": "ostinato", "bass": "drone", "pump": 0.0, "desc": "wide pads, pulsing ostinato, toms - documentary/science"},
    "tech":      {"bpm": 128, "key": "E", "scale": "minor", "prog": [0, 0, 5, 6], "drums": "techno", "keys": "pad", "lead": "arp", "bass": "offbeat", "pump": 0.6, "desc": "driving minimal techno, filtered saw arp - dev/tech news"},
    "hype":      {"bpm": 140, "key": "F#", "scale": "minor", "prog": [0, 5, 3, 4], "drums": "trap", "keys": "pad", "lead": "pluck", "bass": "808", "pump": 0.3, "desc": "trap: 808 bass, hi-hat rolls, half-time snare - hype captions"},
    "corporate": {"bpm": 104, "key": "G", "scale": "major", "prog": [0, 4, 5, 3], "drums": "soft", "keys": "pad", "lead": "pluck", "bass": "root", "pump": 0.25, "desc": "clean, optimistic, unobtrusive - product/tutorial"},
}


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


class Synth:
    def __init__(self, seconds, seed):
        self.n = int(seconds * SR) + SR
        self.bus = {k: np.zeros((2, self.n)) for k in ("drums", "bass", "music", "send", "fx")}
        self.rng = np.random.default_rng(seed)
        self.tables = {}

    # ---------------------------------------------------------------- primitives
    def noise(self, n):
        return self.rng.uniform(-1, 1, n)

    def table(self, kind, nh):
        key = (kind, nh)
        if key not in self.tables:
            ph = np.arange(2048) / 2048 * 2 * np.pi
            t = np.zeros(2048)
            for k in range(1, nh + 1):
                if kind == "saw":
                    t += np.sin(k * ph) / k
                elif kind == "square" and k % 2:
                    t += np.sin(k * ph) / k
                elif kind == "tri" and k % 2:
                    t += (-1) ** ((k - 1) // 2) * np.sin(k * ph) / (k * k)
            t /= max(1e-9, np.abs(t).max())
            self.tables[key] = np.append(t, t[0])
        return self.tables[key]

    def osc(self, kind, f, n, phase=0.0):
        x = np.arange(n) / SR
        if kind == "sine":
            return np.sin(2 * np.pi * (f * x + phase))
        nh = max(1, min(96, int(SR / 2 / max(f, 1))))
        nh = 2 ** int(math.log2(nh))
        idx = ((phase + f * x) % 1.0) * 2048
        return np.interp(idx, np.arange(2049), self.table(kind, nh))

    @staticmethod
    def env(n, a, d, s, r, hold):
        """attack/decay/sustain then release after `hold` seconds; length n samples"""
        t = np.arange(n) / SR
        e = np.where(t < a, t / max(a, 1e-4), s + (1 - s) * np.exp(-(t - a) / max(d, 1e-4)))
        rel = np.clip((t - hold) / max(r, 1e-4), 0, 1)
        return e * (1 - rel) ** 2

    @staticmethod
    def filt(x, kind, f, order=2):
        f = np.clip(np.asarray(f, dtype=float), 20, SR / 2 * 0.95)
        f = [float(f[0]), float(f[1])] if kind == "band" else float(f)
        sos = butter(order, f, btype={"low": "lowpass", "high": "highpass", "band": "bandpass"}[kind], fs=SR, output="sos")
        return sosfilt(sos, x)

    def add(self, bus, t, sig, gain=1.0, pan=0.0, send=0.0):
        i = int(round(t * SR))
        if i >= self.n or i + len(sig) <= 0:
            return
        if i < 0:
            sig, i = sig[-i:], 0
        sig = sig[: self.n - i]
        l, r = math.cos((pan + 1) * math.pi / 4), math.sin((pan + 1) * math.pi / 4)
        self.bus[bus][0, i:i + len(sig)] += sig * gain * l * 1.414
        self.bus[bus][1, i:i + len(sig)] += sig * gain * r * 1.414
        if send:
            self.bus["send"][0, i:i + len(sig)] += sig * gain * send * l
            self.bus["send"][1, i:i + len(sig)] += sig * gain * send * r

    # ---------------------------------------------------------------- drums
    def kick(self, t, g=1.0, hard=False):
        n = int(0.5 * SR); x = np.arange(n) / SR
        f = 46 + (130 if hard else 105) * np.exp(-x * 30)
        s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 7.0)
        s += self.filt(self.noise(n), "high", 1500) * np.exp(-x * 320) * 0.35
        self.add("drums", t, np.tanh(1.8 * s) * 0.9, g)

    def snare(self, t, g=1.0):
        n = int(0.35 * SR); x = np.arange(n) / SR
        s = self.filt(self.noise(n), "band", [1600, 7000]) * np.exp(-x * 17) * 0.8 + np.sin(2 * np.pi * 190 * x) * np.exp(-x * 25) * 0.5
        self.add("drums", t, s, g, 0.0, 0.15)

    def clap(self, t, g=1.0):
        n = int(0.4 * SR); x = np.arange(n) / SR
        body = self.filt(self.noise(n), "band", [900, 2600])
        e = sum(np.where(x >= o, np.exp(-(x - o) * 140), 0) for o in (0, 0.011, 0.023)) + np.exp(-x * 16) * 0.5
        self.add("drums", t, body * e * 0.9, g, 0.0, 0.2)

    def hat(self, t, g=1.0, open_=False, pan=0.2):
        n = int((0.45 if open_ else 0.09) * SR); x = np.arange(n) / SR
        s = self.filt(self.noise(n), "high", 7500) * np.exp(-x * (8 if open_ else 60))
        self.add("drums", t, s * 0.45, g, pan)

    def shaker(self, t, g=1.0):
        n = int(0.12 * SR); x = np.arange(n) / SR
        s = self.filt(self.noise(n), "band", [4500, 9500]) * np.sin(np.pi * np.clip(x / 0.12, 0, 1)) ** 2
        self.add("drums", t, s * 0.4, g, -0.25)

    def tom(self, t, g=1.0, f0=110):
        n = int(0.7 * SR); x = np.arange(n) / SR
        f = f0 * (0.75 + 0.25 * np.exp(-x * 9))
        s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 5.5) + self.filt(self.noise(n), "low", 900) * np.exp(-x * 30) * 0.3
        self.add("drums", t, np.tanh(1.3 * s), g, 0.0, 0.3)

    def sub808(self, t, note, dur, g=1.0):
        n = int((dur + 0.15) * SR); x = np.arange(n) / SR
        f = hz(note) * (1 + 0.6 * np.exp(-x * 40))
        s = np.sin(2 * np.pi * np.cumsum(f) / SR) * self.env(n, 0.003, 0.6, 0.55, 0.12, dur)
        self.add("bass", t, np.tanh(2.2 * s) * 0.75, g)

    def crash(self, t, g=1.0):
        n = int(2.6 * SR); x = np.arange(n) / SR
        s = self.filt(self.noise(n), "high", 3800) * np.exp(-x * 1.8) * 0.35
        self.add("fx", t, s, g, 0.0, 0.4)

    def subdrop(self, t, g=1.0):
        n = int(1.6 * SR); x = np.arange(n) / SR
        f = 32 + 34 * np.exp(-x * 2.5)
        self.add("fx", t, np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 2.2) * 0.8, g)

    def riser(self, t_end, dur=1.8, g=1.0):
        n = int(dur * SR); x = np.arange(n) / SR
        src = self.noise(n); u = x / dur; out = np.zeros(n)
        centres = [500, 1000, 2000, 4000, 8000]          # crossfade static bands = a click-free sweep
        for k, fc in enumerate(centres):
            w = np.clip(1 - np.abs(u * (len(centres) - 1) - k), 0, 1)
            out += self.filt(src, "band", [fc * 0.7, fc * 1.4]) * w
        s = out * u ** 2 * 0.5
        self.add("fx", t_end - dur, s, g, 0.0, 0.5)

    def vinyl(self, dur):
        n = int(dur * SR)
        hiss = self.filt(self.noise(n), "band", [2000, 9000]) * 0.015
        pops = np.zeros(n); idx = self.rng.integers(0, n, int(dur * 7)); pops[idx] = self.rng.uniform(0.1, 0.5, len(idx))
        self.add("fx", 0, hiss + self.filt(pops, "high", 1200) * 0.4, 1.0)

    # ---------------------------------------------------------------- tonal
    def pad(self, t, notes, dur, cutoff=1400, g=1.0):
        n = int((dur + 0.9) * SR)
        e = self.env(n, 0.35, 1.0, 0.85, 0.8, dur)
        for k, m in enumerate(notes):
            for det, pan in ((-0.08, -0.6), (0.08, 0.6)):
                s = self.osc("saw", hz(m) * 2 ** (det / 12), n, phase=(k * 0.37 + det) % 1)
                self.add("music", t, self.filt(s, "low", cutoff) * e * 0.12, g, pan, 0.6)

    def rhodes(self, t, notes, dur, g=1.0):
        n = int((dur + 1.2) * SR); x = np.arange(n) / SR
        for k, m in enumerate(notes):
            f = hz(m)
            mod = np.sin(2 * np.pi * f * x) * 1.5 * np.exp(-x * 3.5)
            s = np.sin(2 * np.pi * f * x + mod) * self.env(n, 0.004, 1.4, 0.25, 0.5, dur) * (1 + 0.08 * np.sin(2 * np.pi * 4.5 * x))
            self.add("music", t + k * 0.012, s * 0.16, g, (k - 1) * 0.25, 0.35)

    def pluck(self, t, m, dur=0.6, g=1.0, pan=0.0, bright=0.5):
        f = hz(m); N = max(2, int(round(SR / f))); n = int((dur + 0.4) * SR)
        z = np.zeros(n + 1); z[1:N + 1] = self.filt(self.noise(N), "low", 2000 + 7000 * bright)
        for i in range(N + 1, n + 1, N):               # Karplus-Strong, one period per step
            j = min(i + N, n + 1); z[i:j] += 0.498 * (z[i - N:j - N] + z[i - N - 1:j - N - 1])
        s = z[1:] * self.env(n, 0.001, 9, 1, 0.15, dur)
        self.add("music", t, s * 0.35, g, pan, 0.35)

    def saw_note(self, t, m, dur, cutoff, g=1.0, pan=0.0, bus="music", send=0.25):
        n = int((dur + 0.12) * SR)
        s = self.filt(self.osc("saw", hz(m), n), "low", cutoff) * self.env(n, 0.004, 0.18, 0.4, 0.08, dur)
        self.add(bus, t, s * 0.22, g, pan, send)

    def bass(self, t, m, dur, g=1.0, cutoff=520):
        n = int((dur + 0.08) * SR)
        e = self.env(n, 0.004, 0.25, 0.7, 0.05, dur)
        s = self.filt(self.osc("saw", hz(m), n), "low", cutoff) * 0.5 + self.osc("sine", hz(m), n) * 0.6
        self.add("bass", t, np.tanh(1.4 * s) * e * 0.55, g)

    # ---------------------------------------------------------------- master
    @staticmethod
    def comb(x, d, g):
        """y[n] = x[n] + g*y[n-d], computed a block of d samples at a time (fast, exact)"""
        y = x.copy()
        for i in range(d, len(y), d):
            j = min(i + d, len(y)); y[i:j] += g * y[i - d:j - d]
        return y

    @staticmethod
    def allpass(x, d, g):
        """y[n] = -g*x[n] + x[n-d] + g*y[n-d]"""
        y = -g * x
        y[d:] += x[:-d]
        for i in range(d, len(y), d):
            j = min(i + d, len(y)); y[i:j] += g * y[i - d:j - d]
        return y

    def reverb(self, x):
        out = sum(self.comb(x, d, g) for d, g in ((1557, 0.84), (1617, 0.83), (1491, 0.82), (1422, 0.81), (1277, 0.80), (1356, 0.80))) / 6
        for d, g in ((225, 0.5), (556, 0.5)):
            out = self.allpass(out, d, g)
        return self.filt(out, "low", 6000) * 0.5

    def mixdown(self, pump=None, bpm=120, seconds=10.0):
        b = self.bus
        if pump is not None and pump > 0:
            t = np.arange(self.n) / SR
            ph = (t * bpm / 60) % 1.0
            g = 1 - pump * np.exp(-ph * 60 / bpm * 9) * (1 - np.exp(-ph * 60 / bpm * 400))
            b["music"] *= g; b["bass"] *= 0.35 + 0.65 * g
        wet = np.stack([self.reverb(b["send"][0]), self.reverb(np.roll(b["send"][1], 37))])   # offset R for width
        mix = b["drums"] * 0.9 + b["bass"] * 0.85 + b["music"] * 0.8 + b["fx"] * 0.8 + wet * 0.55
        mix = np.stack([self.filt(mix[0], "high", 28), self.filt(mix[1], "high", 28)])
        mix = np.tanh(mix * 1.1) / 1.1
        return mix[:, : int(seconds * SR)]


def arrange(s, dur, mood, bpm, key, accents, risers, prog=None, nbars=None):
    M = MOODS[mood]
    root = 48 + NOTE[key]                       # C3 region
    scale = SCALES[M["scale"]]
    note = lambda deg, octv=0: root + scale[deg % 7] + 12 * (deg // 7) + 12 * octv
    beat = 60 / bpm; bar = 4 * beat
    nbars = nbars or int(math.ceil((dur + 1.0) / bar)) + 1
    swing = M.get("swing", 0)
    sw = lambda i8: (beat / 2) * (swing if i8 % 2 else 0)   # swing the off 8ths
    prog = prog or M["prog"]
    acc_bars = {int(a // bar) for a in accents}
    for b in range(nbars):
        t0 = b * bar
        deg = prog[b % len(prog)]
        chord = [note(deg), note(deg + 2), note(deg + 4)]
        intro = b == 0
        fill = (b % 8 == 7) or (b + 1) in acc_bars
        dr = M["drums"]
        # ---- drums
        for q in range(4):
            tq = t0 + q * beat
            if dr in ("house", "techno"):
                if not intro or dr == "techno":
                    s.kick(tq, 0.95, hard=dr == "techno")
                s.hat(tq + beat / 2, 0.8 if not intro else 0.5, open_=dr == "house")
                if dr == "techno":
                    s.hat(tq + beat / 4, 0.35); s.hat(tq + 3 * beat / 4, 0.35)
                if q in (1, 3) and not intro:
                    s.clap(tq, 0.7)
            elif dr == "soft":
                if not intro and q in (0, 2):
                    s.kick(tq, 0.55)
                if not intro and q in (1, 3):
                    s.snare(tq, 0.32)
                s.shaker(tq + beat / 2 + sw(1), 0.6)
            elif dr == "boombap":
                if q in (0, 2):
                    s.kick(tq + (sw(1) if q == 2 and b % 2 else 0), 0.7)
                if q in (1, 3):
                    s.snare(tq, 0.5)
                for e8 in range(2):
                    s.hat(tq + e8 * beat / 2 + sw(e8), 0.4 if e8 else 0.55)
            elif dr == "toms":
                if q == 0:
                    s.tom(tq, 0.7, 70)
                if q == 2 and b % 2:
                    s.tom(tq, 0.45, 95)
                if not intro and b % 4 == 3 and q == 3:
                    s.tom(tq, 0.5, 120); s.tom(tq + beat / 2, 0.55, 100)
            elif dr == "trap":
                for e16 in range(4):
                    roll = (b % 2 == 1 and q == 3)
                    s.hat(tq + e16 * beat / 4, 0.45 if e16 % 2 else 0.6)
                    if roll:
                        s.hat(tq + e16 * beat / 4 + beat / 8, 0.35)
                if q == 2 and not intro:
                    s.clap(tq, 0.85); s.snare(tq, 0.4)
            if fill and q == 3 and not intro and dr not in ("toms",):
                for k in range(4):
                    s.snare(tq + k * beat / 4, 0.25 + 0.1 * k)
        # ---- bass
        bm = note(deg, -1)
        if M["bass"] == "offbeat" and not intro:
            for q in range(4):
                s.bass(t0 + q * beat + beat / 2, bm, beat * 0.42, 0.9)
        elif M["bass"] == "root" and not intro:
            s.bass(t0, bm, beat * 1.6, 0.8); s.bass(t0 + 2.5 * beat + sw(1), bm, beat * 1.2, 0.6)
        elif M["bass"] == "drone":
            s.bass(t0, note(deg, -1), bar * 0.98, 0.55, cutoff=260)
        elif M["bass"] == "808" and not intro:
            s.sub808(t0, note(deg, -1), beat * 1.4, 0.9)
            s.sub808(t0 + 2.5 * beat, note(deg, -1) + (0 if b % 2 else 7), beat * 1.2, 0.7)
            s.kick(t0, 0.7); s.kick(t0 + 2.5 * beat, 0.6)
        # ---- harmony
        if M["keys"] == "pad":
            s.pad(t0, [n + 12 for n in chord], bar * 0.98, cutoff=900 if intro else (1800 if mood != "cinematic" else 1200), g=0.9)
        elif M["keys"] == "rhodes":
            vo = [chord[0] + 12, chord[1] + 12, chord[2] + 12, note(deg + 6) + 12]   # add the 7th
            s.rhodes(t0, vo, beat * 1.8, 0.9)
            s.rhodes(t0 + 2.5 * beat + sw(1), vo[1:], beat * 1.2, 0.6)
        # ---- lead
        ld = M["lead"]
        if ld == "pluck" and not intro:
            pat = [0, 2, 1, 2, 0, 2, 1, 3] if mood != "hype" else [0, 2, 3, 2]
            step = beat / 2 if mood != "hype" else beat
            for k, p in enumerate(pat):
                tones = [chord[0] + 24, chord[1] + 24, chord[2] + 24, chord[0] + 36]
                s.pluck(t0 + k * step + sw(k), tones[p], 0.5, 0.75, pan=0.3 if k % 2 else -0.3, bright=0.45)
        elif ld == "arp":
            for k in range(16):
                tones = [chord[0] + 24, chord[1] + 24, chord[2] + 24, chord[1] + 36]
                cut = 500 + 2600 * (0.5 - 0.5 * math.cos(2 * math.pi * ((b * 16 + k) / 64)))
                s.saw_note(t0 + k * beat / 4, tones[k % 4], beat / 4 * 0.8, cut, 0.8, pan=0.25 if k % 2 else -0.25)
        elif ld == "ostinato" and not intro:
            for k in range(8):
                s.saw_note(t0 + k * beat / 2, chord[0] + 12 if k % 2 == 0 else chord[2] + 12, beat * 0.3, 1100, 0.6, pan=0.0, send=0.5)
    if M.get("vinyl"):
        s.vinyl(dur + 1)
    for a in accents:
        s.crash(a, 0.9); s.subdrop(a, 0.9)
        if risers and a > 2.0:
            s.riser(a, 1.8, 0.8)


def long_track(A, M, bpm, key, accents, loop_bars=16, tail_bars=2):
    """Long videos: render an intro bar + a 16-bar loop twice (A, and a B variation), then tile A A B ... with
    overlap-add so reverb tails carry over. Memory stays at a few loops no matter how long the video is."""
    bar = 240.0 / bpm
    core_len = (1 + loop_bars + tail_bars) * bar

    def core(seed, prog):
        s = Synth(core_len + 4, seed)
        arrange(s, core_len, A.mood, bpm, key, [], False, prog, nbars=1 + loop_bars)   # tail bars = decays only
        return s.mixdown(M.get("pump", 0), bpm, core_len).astype(np.float32)
    rot = M["prog"][2:] + M["prog"][:2]
    cores = {"A": core(A.seed, M["prog"]), "B": core(A.seed + 1, rot)}
    n = int(round(A.duration * SR))
    out = np.zeros((2, n), dtype=np.float32)
    intro = cores["A"][:, : int(round(bar * SR))]
    out[:, : min(n, intro.shape[1])] = intro[:, : min(n, intro.shape[1])]
    seg_len = int(round((loop_bars + tail_bars) * bar * SR))
    body = int(round(loop_bars * bar * SR))
    fade = np.ones(seg_len, dtype=np.float32); fade[body:] = np.linspace(1, 0, seg_len - body, dtype=np.float32)
    k = 0
    while True:
        start = int(round((bar + k * loop_bars * bar) * SR))   # exact beat grid: copy k starts on bar 1 + 16k
        if start >= n:
            break
        src = cores["B" if k % 3 == 2 else "A"]
        b0 = int(round(bar * SR))
        seg = src[:, b0: b0 + seg_len] * fade[: src.shape[1] - b0 if src.shape[1] - b0 < seg_len else seg_len]
        m = min(seg.shape[1], n - start)
        out[:, start: start + m] += seg[:, :m]
        k += 1
    if accents:   # crash + sub drop (+ riser) rendered once, added at each accent
        s = Synth(6, A.seed + 7)
        s.crash(2.0, 0.9); s.subdrop(2.0, 0.9)
        if A.risers:
            s.riser(2.0, 1.8, 0.8)
        hit = (s.bus["fx"] * 0.8).astype(np.float32)
        for a in accents:
            i0 = int(round((a - 2.0) * SR)); j0 = max(0, -i0); i0 = max(0, i0)
            m = min(hit.shape[1] - j0, n - i0)
            if m > 0:
                out[:, i0: i0 + m] += hit[:, j0: j0 + m]
    print(f"long track: intro + {k} x {loop_bars}-bar loops (A/A/B), {len(accents)} accent(s)")
    return out


def write_wav(path, x):
    x = np.clip(x, -1, 1)
    pcm = (x.T * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out"); ap.add_argument("--duration", type=float)
    ap.add_argument("--mood", default="upbeat"); ap.add_argument("--bpm", type=float); ap.add_argument("--key")
    ap.add_argument("--seed", type=int, default=7); ap.add_argument("--accents", default="")
    ap.add_argument("--risers", action="store_true"); ap.add_argument("--fade", type=float, default=1.8)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--loop-after", type=float, default=100.0, help="tracks longer than this many seconds are built from tiled loops")
    A = ap.parse_args()
    if A.list:
        for k, v in MOODS.items():
            print(f"{k:10s} {v['bpm']:>4} BPM  {v['key']} {v['scale']:5s}  {v['desc']}")
        return 0
    if not A.out or not A.duration:
        ap.error("--out and --duration are required")
    if A.mood not in MOODS:
        ap.error(f"unknown mood {A.mood}; one of {', '.join(MOODS)}")
    M = MOODS[A.mood]
    bpm = A.bpm or M["bpm"]; key = A.key or M["key"]
    if key not in NOTE:
        ap.error(f"unknown key {key}")
    accents = [float(a) for a in A.accents.split(",") if a.strip()]
    if A.duration <= A.loop_after:
        s = Synth(A.duration + 4, A.seed)
        arrange(s, A.duration, A.mood, bpm, key, accents, A.risers)
        mix = s.mixdown(M.get("pump", 0), bpm, A.duration)
    else:
        mix = long_track(A, M, bpm, key, accents)
    n = mix.shape[1]
    t = np.arange(n) / SR
    fade = np.clip((A.duration - t) / max(A.fade, 0.01), 0, 1) ** 1.5 * np.clip(t / 0.01, 0, 1)
    mix *= fade.astype(mix.dtype)
    peak = np.abs(mix).max()
    mix *= (10 ** (-1 / 20)) / max(peak, 1e-6)
    write_wav(A.out, mix)
    rms = 20 * math.log10(max(1e-9, float(np.sqrt((mix ** 2).mean()))))
    print(f"music -> {A.out}  {A.duration:.2f}s  {A.mood} {bpm:g} BPM in {key} {M['scale']}  seed {A.seed}  rms {rms:.1f} dBFS"
          + (f"  accents at {', '.join(f'{a:.2f}' for a in accents)}" if accents else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
