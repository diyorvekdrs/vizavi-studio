"""Procedural sky: Milky Way equirect texture pyramid + star catalogue. Cached to disk."""
import numpy as np, os

TW, TH = 8192, 4096
CACHE = os.path.join(os.path.dirname(__file__), "cache")
os.makedirs(CACHE, exist_ok=True)

def rot_matrix(axis, ang):
    axis = np.asarray(axis, float); axis /= np.linalg.norm(axis)
    a = np.cos(ang / 2); b, c, d = -axis * np.sin(ang / 2)
    return np.array([[a*a+b*b-c*c-d*d, 2*(b*c+a*d), 2*(b*d-a*c)],
                     [2*(b*c-a*d), a*a+c*c-b*b-d*d, 2*(c*d+a*b)],
                     [2*(b*d+a*c), 2*(c*d-a*b), a*a+d*d-b*b-c*c]])

# Galactic frame: world dir -> galactic dir. World: y up.
# Tilt the galactic plane so the band crosses the sky diagonally.
RG = rot_matrix([1, 0, 0], np.radians(62)) @ rot_matrix([0, 1, 0], np.radians(-35))

def fft_noise(h, w, beta, seed):
    import scipy.fft as sf
    rng = np.random.default_rng(seed)
    n = rng.standard_normal((h, w), dtype=np.float32)
    F = sf.rfft2(n, workers=2); del n
    ky = np.fft.fftfreq(h).astype(np.float32)[:, None]; kx = np.fft.rfftfreq(w).astype(np.float32)[None, :]
    k = np.sqrt(kx**2 + ky**2); k[0, 0] = 1
    F *= (k ** np.float32(-beta / 2)); F[0, 0] = 0; del k
    out = sf.irfft2(F, s=(h, w), workers=2).astype(np.float32); del F
    out /= out.std()
    return out

def build_milkyway():
    p = os.path.join(CACHE, "mw.npy")
    if os.path.exists(p):
        return np.load(p)
    N = {}
    for name, beta, seed in (("n1", 3.2, 1), ("n2", 2.4, 2), ("n3", 1.8, 3), ("n4", 2.9, 5), ("big", 3.4, 6),
                             ("fine", 0.6, 4), ("neb", 3.6, 7), ("neb2", 3.6, 8)):
        N[name] = fft_noise(TH, TW, beta, seed)
    tex = np.empty((TH, TW, 3), np.float16)
    rng = np.random.default_rng(77)
    l = ((np.arange(TW) + 0.5) / TW * 2 * np.pi - np.pi).astype(np.float32)
    warm = np.array([1.0, 0.90, 0.80], np.float32); cool = np.array([0.78, 0.86, 1.0], np.float32)
    for y0 in range(0, TH, 256):
        y1 = min(TH, y0 + 256)
        b = (np.pi / 2 - (np.arange(y0, y1) + 0.5) / TH * np.pi).astype(np.float32)
        L, B = np.meshgrid(l, b)
        n1, n2, n3, n4, big, fine = (N[k][y0:y1] for k in ("n1", "n2", "n3", "n4", "big", "fine"))
        core = np.exp(-(L / 0.55) ** 2)
        sig = np.radians(5.5) + np.radians(7.5) * core
        band = np.exp(-(B / sig) ** 2)
        bulge = np.exp(-((L / 0.32) ** 2 + (B / 0.20) ** 2))
        clump = np.clip(1 + 0.5 * n1 + 0.3 * n2, 0.0, None) ** 1.3
        glow = band * (0.35 + 0.9 * core) * clump + 1.6 * bulge * np.clip(1 + 0.3 * n2, 0.2, None)
        ridge = np.clip(1 - np.abs(n4 * 0.8 + n3 * 0.2), 0, None) ** 3
        lane_center = np.radians(0.8) * np.sin(L * 3) + np.radians(0.6) * n1 * 0.4
        lane = np.exp(-((B - lane_center) / (np.radians(2.2) + np.radians(2.5) * core)) ** 2)
        dust = np.clip(lane * (0.30 + 0.80 * ridge) * 1.1 + 0.55 * band * ridge * np.clip(big, 0, None) ** 1.5, 0, 0.95)
        grain = np.clip(1 + 0.08 * fine, 0, None)
        speck = rng.random(L.shape, dtype=np.float32) ** 24 * 4.0
        lum = glow * grain * (0.92 + speck * 0.5 * band)
        mix = np.clip(core * 0.9 + bulge, 0, 1)[..., None]
        col = cool * (1 - mix) + warm * mix
        ext = np.stack([1 - dust * 0.90, 1 - dust * 0.93, 1 - dust * 0.95], -1)
        t = lum[..., None] * col * ext
        t += (np.clip(N["neb"][y0:y1], 0, None) ** 2 * band)[..., None] * np.array([0.15, 0.03, 0.05], np.float32)
        t += (np.clip(N["neb2"][y0:y1], 0, None) ** 2 * band)[..., None] * np.array([0.02, 0.06, 0.08], np.float32)
        tex[y0:y1] = (t * 0.020 + 0.0004).astype(np.float16)
    np.save(p, tex)
    return tex

def build_pyramid(tex, levels=7):
    from scipy.ndimage import gaussian_filter
    pyr = [tex]
    cur = tex
    for i in range(levels - 1):
        cur = gaussian_filter(cur.astype(np.float32), sigma=(1.0, 1.0, 0), mode=("nearest", "wrap", "nearest"))
        cur = cur[::2, ::2].astype(np.float16)
        pyr.append(cur)
    return pyr

def bt_color(T):
    # approximate blackbody tint, normalized, desaturated for realism
    T = np.asarray(T, float) / 100.0
    r = np.where(T <= 66, 255, 329.7 * (T - 60) ** -0.1332)
    g = np.where(T <= 66, 99.47 * np.log(T) - 161.1, 288.1 * (T - 60) ** -0.0755)
    bl = np.where(T >= 66, 255, np.where(T <= 19, 0, 138.5 * np.log(np.maximum(T - 10, 1e-3)) - 305.0))
    c = np.clip(np.stack([r, g, bl], -1) / 255.0, 0, 1)
    c = c / c.max(-1, keepdims=True)
    return 0.55 * c + 0.45 * c.mean(-1, keepdims=True)

def build_stars(N=1200000, seed=11):
    p = os.path.join(CACHE, "stars.npz")
    if os.path.exists(p):
        d = np.load(p); return d["dir"], d["flux"], d["col"]
    rng = np.random.default_rng(seed)
    out = []
    while sum(len(o) for o in out) < N:
        v = rng.standard_normal((N, 3)); v /= np.linalg.norm(v, axis=1, keepdims=True)
        b = np.arcsin(np.clip(v[:, 1], -1, 1))  # in galactic coords, y = galactic pole
        dens = 1 + 9.0 * np.exp(-(b / np.radians(7)) ** 2)
        keep = rng.random(N) < dens / 10.0
        out.append(v[keep])
    g = np.concatenate(out)[:N]
    # galactic -> world
    world = g @ RG  # since gal = world @ RG.T
    # magnitudes
    u = rng.random(N)
    mmin, mmax, k = -1.0, 11.0, 0.42
    m = np.log10(u * (10 ** (k * mmax) - 10 ** (k * mmin)) + 10 ** (k * mmin)) / k
    flux = 10 ** (-0.4 * m)
    T = np.clip(rng.lognormal(np.log(5600), 0.28, N), 2800, 22000)
    col = bt_color(T).astype(np.float32)
    np.savez(p, dir=world.astype(np.float32), flux=flux.astype(np.float32), col=col)
    return world.astype(np.float32), flux.astype(np.float32), col

def world_to_gal(d):
    return d @ RG.T

if __name__ == "__main__":
    import time
    t = time.time(); tex = build_milkyway(); print("mw", time.time() - t, tex.max(), tex.mean())
    t = time.time(); s = build_stars(); print("stars", time.time() - t, s[1].max())
