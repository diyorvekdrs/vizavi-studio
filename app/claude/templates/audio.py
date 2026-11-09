"""Ambient bed + SFX for the project (no voice, no user music - the app mixes those).
Writes mix.wav: 48 kHz stereo float, exactly NFR/FPS seconds. Edit BED and EVENTS; keep the levels
(bed around -32 dBFS RMS, hits peaking ≤ -10 dBFS) so the voice stays ≥ 12 dB above everything."""
import json, re
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

HERE = Path(__file__).parent
SR = 48000
if (HERE / "project.json").exists():
    _p = json.loads((HERE / "project.json").read_text(encoding="utf-8")); DUR = _p["nfr"] / _p["fps"]
else:
    import film; DUR = film.NFR / film.FPS
N = int(round(DUR * SR))
t = np.arange(N) / SR
rng = np.random.default_rng(11)


def words():
    p = HERE / "input" / "words.tsv"
    return [(float(r[0]), float(r[1]), r[2]) for r in (l.split("\t") for l in p.read_text(encoding="utf-8").splitlines())
            if r and r[0][:1].isdigit()] if p.exists() else []


def word_t(w, n=1, default=0.0):
    nm = lambda s: re.sub(r"[^\w']", "", s.lower().replace("‘", "'").replace("ʻ", "'"))
    k = 0
    for s, e, x in words():
        if nm(x) == nm(w):
            k += 1
            if k == n:
                return s
    return default


def filt(x, kind, f, order=2):
    return sosfilt(butter(order, f, btype=kind, fs=SR, output="sos"), x)


def env(points):
    """smooth piecewise envelope from [(time, value), ...]"""
    ts = np.array([p[0] for p in points]); vs = np.array([p[1] for p in points])
    i = np.clip(np.searchsorted(ts, t) - 1, 0, len(ts) - 2)
    k = np.clip((t - ts[i]) / np.maximum(ts[i + 1] - ts[i], 1e-9), 0, 1)
    k = 0.5 - 0.5 * np.cos(np.pi * k)
    return vs[i] + (vs[i + 1] - vs[i]) * k


def at(t0, dur):
    """index slice + local time for an event"""
    a, b = int(max(0, t0) * SR), int(min(DUR, t0 + dur) * SR)
    return slice(a, b), (np.arange(b - a) / SR)


# ---------------------------------------------------------------- sound palette
def drone(freqs=(55, 82.4, 110), drift=0.07):
    out = np.zeros(N)
    for k, f in enumerate(freqs):
        ph = 2 * np.pi * np.cumsum(f * (1 + drift * 0.01 * np.sin(2 * np.pi * (0.03 + 0.01 * k) * t))) / SR
        out += np.sin(ph) / (k + 1)
    return out / len(freqs)


def air():
    return filt(filt(rng.standard_normal(N), "low", 900), "high", 120)


def whoosh(t0, dur=1.2, up=True, gain=0.25):
    out = np.zeros(N); s, lt = at(t0, dur)
    n = rng.standard_normal(len(lt)); k = lt / dur
    e = np.sin(np.pi * k) ** 2
    lo, hi = filt(n, "band", [200, 900]), filt(n, "band", [1500, 6000])
    m = k if up else 1 - k                      # spectral sweep low -> high (or reverse)
    out[s] = (lo * (1 - m) + hi * m) * e * gain
    return out


def impact(t0, weight=1.0, gain=0.2):
    out = np.zeros(N); s, lt = at(t0, 2.5)
    body = np.sin(2 * np.pi * (45 + 60 * np.exp(-lt * 6)) * lt) * np.exp(-lt * 2.2)
    click = filt(rng.standard_normal(len(lt)), "high", 2000) * np.exp(-lt * 40) * 0.3
    out[s] = (body * weight + click) * gain
    return out


def riser(t0, dur=3.0, gain=0.18):
    out = np.zeros(N); s, lt = at(t0, dur); k = lt / dur
    out[s] = np.sin(2 * np.pi * np.cumsum(120 + 900 * k ** 2) / SR) * k ** 2 * gain
    return out


def shimmer(t0, dur=2.0, gain=0.08):
    out = np.zeros(N); s, lt = at(t0, dur)
    tone = sum(np.sin(2 * np.pi * f * lt + p) for f, p in ((1760, 0), (2637, 1), (3520, 2)))
    out[s] = tone * np.exp(-lt * 2.5) * (1 - np.exp(-lt * 30)) * gain / 3
    return out


# ---------------------------------------------------------------- the mix
BED = (drone() * 0.020 + air() * 0.012) * env([(0, 0), (1.5, 1), (DUR - 2.0, 1), (DUR, 0)])
EVENTS = [                      # anchor to words / scene starts – not every cut needs a sound
    whoosh(word_t("example", default=7.6) - 0.6),
    impact(word_t("example", default=8.0), weight=0.6),
]
mono = BED + sum(EVENTS)
d = int(0.011 * SR)             # small stereo width
L, R = mono, np.concatenate([np.zeros(d), mono[:-d]])
mix = np.stack([L, R], 1)
peak = np.abs(mix).max()
if peak > 0.3:                  # keep hits ≤ -10 dBFS: under the voice, never masking it
    mix *= 0.3 / peak
wavfile.write(HERE / "mix.wav", SR, mix.astype(np.float32))
