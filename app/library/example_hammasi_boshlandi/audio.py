"""Ambient bed + sparse SFX for 'Hammasi boshlandi' (no voice). 48 kHz stereo, 33.333 s."""
import numpy as np
from scipy.signal import butter, sosfilt, fftconvolve
from scipy.io import wavfile

SR = 48000
DUR = 800 / 24
N = int(round(DUR * SR))
t = np.arange(N) / SR
rng = np.random.default_rng(5)

def env(points):
    """piecewise smooth envelope from (time, value) list (cosine interpolation)."""
    ts = np.array([p[0] for p in points]); vs = np.array([p[1] for p in points])
    out = np.interp(t, ts, vs)
    # smooth corners with cosine shaping between points
    idx = np.clip(np.searchsorted(ts, t) - 1, 0, len(ts) - 2)
    t0 = ts[idx]; t1 = ts[idx + 1]; v0 = vs[idx]; v1 = vs[idx + 1]
    s = np.clip((t - t0) / np.maximum(t1 - t0, 1e-9), 0, 1)
    s = 0.5 - 0.5 * np.cos(np.pi * s)
    return v0 + (v1 - v0) * s

def bp(x, lo, hi, order=2):
    sos = butter(order, [lo, hi], btype="band", fs=SR, output="sos"); return sosfilt(sos, x)
def lp(x, f, order=2):
    sos = butter(order, f, btype="low", fs=SR, output="sos"); return sosfilt(sos, x)
def hp(x, f, order=2):
    sos = butter(order, f, btype="high", fs=SR, output="sos"); return sosfilt(sos, x)

def noise(): return rng.standard_normal(N)
def brown():
    b = np.cumsum(rng.standard_normal(N)); b = hp(b, 15); return b / np.abs(b).max()

def tone(f, phase_mod=None):
    ph = 2 * np.pi * np.cumsum(np.broadcast_to(f, (N,))) / SR
    if phase_mod is not None: ph = ph + phase_mod
    return np.sin(ph)

def pad(freqs, detune=0.12, bright=900):
    out = np.zeros(N)
    for f in freqs:
        for d in (-detune, 0, detune):
            ff = f * (1 + d / 100)
            vib = 0.15 * np.sin(2 * np.pi * (0.07 + 0.03 * rng.random()) * t + rng.random() * 6)
            out += tone(ff + vib) * 0.33 + 0.10 * tone(2 * ff + vib) + 0.04 * tone(3 * ff)
    return lp(out / len(freqs), bright)

L = np.zeros(N); R = np.zeros(N)
def add(sig, gain=1.0, pan=0.0, width=0.0):
    global L, R
    gl = np.cos((pan + 1) * np.pi / 4); gr = np.sin((pan + 1) * np.pi / 4)
    if width > 0:
        d = int(width * SR / 1000)
        L += sig * gain * gl; R += np.roll(sig, d) * gain * gr
    else:
        L += sig * gain * gl; R += sig * gain * gr

# ---------------- drone bed (D minor colour), evolves gently
D2, A2, F3, D3, A3 = 73.42, 110.0, 174.61, 146.83, 220.0
bed = pad([D2, A2, D3], 0.10, 700)
bed_env = env([(0, 0), (1.8, 0.55), (4.0, 0.7), (12, 0.75), (16.2, 0.6), (18, 0.8), (22, 0.95), (26.0, 0.8),
               (27.0, 0.6), (31.5, 0.65), (33.0, 0.35), (DUR, 0.0)])
add(bed * bed_env, 0.16, -0.15, 9)
upper = pad([F3, A3], 0.15, 1400)
add(upper * env([(0, 0), (4.5, 0), (7, 0.5), (12, 0.6), (16, 0.3), (19, 0.0), (24.0, 0.0), (25.0, 0.0), (29, 0.4), (32.5, 0.3), (DUR, 0)]), 0.06, 0.2, 13)

# space air: filtered noise with slow sweeping band
air = bp(noise(), 300, 2400)
air2 = bp(noise(), 2000, 7000)
add(air * env([(0, 0), (3.2, 0.0), (4.4, 0.6), (16, 0.5), (22, 0.7), (26.5, 0.2), (27.5, 0.0), (DUR, 0)]), 0.010, -0.3, 17)
add(air2 * env([(0, 0), (3.2, 0.0), (4.4, 0.4), (16, 0.3), (26.5, 0.1), (27.5, 0.0), (DUR, 0)]), 0.004, 0.3, 11)

# ---------------- night wind on the ground (0-4.4, 26.2-end)
w = lp(noise(), 700) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.09 * t + 1) * np.sin(2 * np.pi * 0.023 * t))
w = hp(w, 90)
add(w * env([(0, 0), (1.2, 0.8), (3.2, 0.8), (4.4, 0.0), (26.2, 0.0), (27.2, 0.7), (32.6, 0.7), (DUR, 0.0)]), 0.030, 0.1, 21)

# ---------------- events
def burst(center, att, rel, sig, gain, pan=0.0, width=0.0):
    e = np.where(t < center, np.exp(-((center - t) / att) ** 2), np.exp(-(t - center) / rel))
    add(sig * e, gain, pan, width)

# 3.2-4.4 rise into space: airy swell
sw = bp(noise(), 500, 5000)
fsweep = env([(0, 400), (3.0, 400), (4.1, 2600), (5.5, 1800), (DUR, 1800)])
sw2 = lp(noise(), 3000) * 0.0
burst(4.0, 0.55, 0.9, bp(noise(), 400, 3200), 0.035, -0.2, 15)

# 5.45-7.0 strange wobble: two close low tones beating
wob = (tone(110.0) + tone(111.6)) * 0.5 + 0.3 * tone(55.0 + 0.6 * np.sin(2 * np.pi * 0.8 * t))
add(lp(wob, 600) * env([(0, 0), (5.3, 0), (6.0, 0.8), (7.2, 0.6), (8.6, 0.0), (DUR, 0)]), 0.05, 0.0, 6)

# 7.5-9.3 calculation shimmer: sparse soft glints (pentatonic, quiet)
notes = [880.0, 987.8, 1174.7, 1318.5, 1568.0, 1174.7, 1318.5]
for k, (tt, f) in enumerate(zip(np.linspace(7.6, 9.2, 7), notes)):
    g = np.exp(-np.clip(t - tt, 0, None) / 0.9) * (t >= tt)
    s = (tone(f) + 0.3 * tone(2 * f)) * g
    add(s, 0.010, -0.5 + k * 0.16, 7)

# 10.2 'natijada' resolve: soft bell dyad
for f, g in ((587.33, 1.0), (880.0, 0.7), (1174.7, 0.25)):
    e = np.exp(-np.clip(t - 10.15, 0, None) / 2.4) * (t >= 10.15) * (1 - np.exp(-np.clip(t - 10.15, 0, None) / 0.01))
    add(tone(f) * e * g, 0.018, 0.1, 9)

# 12.05 reticle on the unknown body: gentle low 'thoom'
e = np.exp(-np.clip(t - 12.05, 0, None) / 1.3) * (t >= 12.05) * (1 - np.exp(-np.clip(t - 12.05, 0, None) / 0.03))
add(tone(48.0 - 6 * np.clip(t - 12.05, 0, 2)) * e, 0.10, 0.0)
add(lp(noise(), 200) * e, 0.04, 0.0)

# 13.7-16 approach: subtle pulse in the drone (very soft)
puls = lp(noise(), 120) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.5 * t)) ** 3
add(puls * env([(0, 0), (13.6, 0), (14.8, 0.6), (16.4, 0.3), (17.5, 0), (DUR, 0)]), 0.06)

# 16.0-16.6 dissolve 'bir-ikki oy oldin': airy swell
burst(16.35, 0.45, 1.0, bp(noise(), 300, 2600), 0.032, 0.2, 15)

# 17.6-22 gravity rumble growing + slow downward bend as orbits break
rum = lp(brown(), 90)
add(rum * env([(0, 0), (17.4, 0), (19.5, 0.4), (21.5, 0.9), (23.5, 1.0), (25.5, 0.7), (26.6, 0.0), (DUR, 0)]), 0.35)
bend = tone(env([(0, 92.5), (19.4, 92.5), (22.4, 82.4), (DUR, 82.4)]))
add(lp(bend, 400) * env([(0, 0), (19.2, 0), (20.4, 0.6), (22.2, 0.5), (23.5, 0), (DUR, 0)]), 0.05, -0.1, 8)

# 22.2-26 approach: long air swell, then 24.75 'halqa' warm bloom chord
burst(24.6, 1.6, 1.2, bp(noise(), 250, 4000), 0.030, 0.0, 19)
chord = pad([146.83, 220.0, 293.66, 369.99, 440.0], 0.18, 2200)
add(chord * env([(0, 0), (24.6, 0), (25.2, 0.9), (26.3, 0.7), (28.0, 0.25), (31, 0.0), (DUR, 0)]), 0.10, 0.0, 14)

# 26.2-26.9 back to Earth: soft descending air
burst(26.5, 0.35, 0.8, bp(noise(), 200, 1800), 0.026, -0.2, 15)

# 27.0-30.5 optical effects in the sky: glassy shimmer, very quiet
sh = (tone(1760.0 + 3 * np.sin(2 * np.pi * 0.3 * t)) + tone(2217.5) * 0.6 + tone(2637.0) * 0.4)
sh *= 0.5 + 0.5 * np.sin(2 * np.pi * 0.6 * t + 1)
add(sh * env([(0, 0), (27.0, 0), (28.2, 0.5), (30.0, 0.4), (31.5, 0.0), (DUR, 0)]), 0.006, 0.35, 11)

# ending resolve: low D sustained, fades by the end
fin = pad([D2, A2, D3, 293.66], 0.1, 900)
add(fin * env([(0, 0), (30.8, 0), (31.8, 0.7), (33.0, 0.35), (DUR, 0.0)]), 0.10, 0.0, 10)

# ---------------- reverb (synthetic IR) and master
def ir(sec, seed):
    r = np.random.default_rng(seed); n = int(sec * SR)
    x = r.standard_normal(n) * np.exp(-np.arange(n) / SR / (sec / 6.5))
    return lp(x, 6000) / np.sqrt((x ** 2).sum())
Lw = fftconvolve(L, ir(3.5, 1))[:N]; Rw = fftconvolve(R, ir(3.5, 2))[:N]
L = L * 0.75 + Lw * 0.55; R = R * 0.75 + Rw * 0.55
L = hp(L, 25); R = hp(R, 25)
# fades
fi = np.clip(t / 0.4, 0, 1); fo = np.clip((DUR - t) / 0.6, 0, 1)
L *= fi * fo; R *= fi * fo
pk = max(np.abs(L).max(), np.abs(R).max())
g = 10 ** (-7 / 20) / pk
st = np.stack([L * g, R * g], 1)
wavfile.write("mix.wav", SR, (st * 32767).astype(np.int16))
print("peak", pk, "len", N / SR)
