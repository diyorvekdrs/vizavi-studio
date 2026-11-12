"""PROJECT TITLE – Python engine starter (Vizavi). Working skeleton: replace the demo scenes, keep the structure.
Linear-light HDR on the device (xp) → bloom → filmic tonemap → grade/vignette/grain → uint8; text and
captions on the host afterwards. Frame i depends only on i. GPU-safe (passes RENDER_FAKEGPU=1)."""
import math, re
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from backend import xp, ndi, asx, cpu

HERE = Path(__file__).parent
W, H, FPS = 2560, 1440, 24          # design size = the order's main size; fps exact
NFR = FPS * 20                      # >= suggested_nfr from vizavi.json
ALPHA = False
RESPONSIVE = False                  # True when several aspect versions are ordered (layout from W, H)
SELFTEST_FRAMES = [FPS * 2, FPS * 12]
U = 1.0                             # size unit: min(W, H) / 1440 (set in set_res)
F32 = np.float32


def set_res(w, h):
    global W, H, U
    W, H, U = w, h, min(w, h) / 1440.0
    _CACHE.clear()


# ------------------------------------------------------------------ narration timing (never hard-code)
def _norm(s):
    return re.sub(r"[^\w']", "", s.lower().replace("‘", "'").replace("ʻ", "'").replace("’", "'"))


def load_words():
    p = HERE / "input" / "words.tsv"
    if not p.exists():
        return []
    out = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        r = ln.split("\t")
        if len(r) >= 3 and r[0][:1].isdigit():
            out.append((float(r[0]), float(r[1]), r[2]))
    return out


WORDS = load_words()


def word_t(word, n=1, default=0.0):
    """start time of the n-th occurrence of a word in the narration (cue anchor)."""
    k = 0
    for s, e, w in WORDS:
        if _norm(w) == _norm(word):
            k += 1
            if k == n:
                return s
    return default


# Scenes / cues: anchor them to words so they follow the final (precise) timing.
SCENES = [("approach", 0.0, 8.0), ("title", 8.0, NFR / FPS)]
CUES = [(word_t("example", default=8.0) - 3 / FPS, "example", "title appears")]


# ------------------------------------------------------------------ math helpers (host)
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def lerp(a, b, k): return a + (b - a) * k
def smooth(a, b, x):
    k = clamp((x - a) / (b - a)); return k * k * (3 - 2 * k)
def ease_io(k):
    k = clamp(k); return 4 * k ** 3 if k < 0.5 else 1 - (-2 * k + 2) ** 3 / 2


def spline(keys, t):
    """C1 Catmull-Rom through (time, np.array) keys; zero tangents at the ends (smooth start/stop)."""
    ts = [k[0] for k in keys]
    if t <= ts[0]: return np.array(keys[0][1], float)
    if t >= ts[-1]: return np.array(keys[-1][1], float)
    i = max(j for j in range(len(ts) - 1) if ts[j] <= t)
    t0, t1 = ts[i], ts[i + 1]
    p0, p1 = np.array(keys[i][1], float), np.array(keys[i + 1][1], float)
    tan = lambda j: np.zeros_like(p0) if j in (0, len(ts) - 1) else \
        (np.array(keys[j + 1][1], float) - np.array(keys[j - 1][1], float)) / (ts[j + 1] - ts[j - 1])
    m0, m1 = tan(i) * (t1 - t0), tan(i + 1) * (t1 - t0)
    s = (t - t0) / (t1 - t0)
    return (2*s**3 - 3*s**2 + 1) * p0 + (s**3 - 2*s**2 + s) * m0 + (-2*s**3 + 3*s**2) * p1 + (s**3 - s**2) * m1


# ------------------------------------------------------------------ camera (one long trajectory, speed waves)
CAM_KEYS = [  # (t, [pos x, y, z, target x, y, z, fov])
    (0.0, [0, 0.4, 14, 0, 0, 0, 40]),
    (8.0, [2.5, 1.0, 8, 0, 0, 0, 36]),
    (NFR / FPS, [3.2, 1.3, 6.5, 0, 0.2, 0, 34]),
]


def camera_state(t):
    return spline(CAM_KEYS, t)


class Cam:
    def __init__(self, st):
        self.pos, tgt, self.fov = st[:3], st[3:6], st[6]
        f = tgt - self.pos; f /= np.linalg.norm(f)
        r = np.cross(f, [0, 1, 0]); r /= np.linalg.norm(r)
        self.f, self.r, self.u = f, r, np.cross(r, f)
        self.focal = (H / 2) / math.tan(math.radians(self.fov) / 2)

    def project(self, P):
        """host: world points (N,3) -> px, py, depth"""
        d = np.asarray(P, float) - self.pos
        z = d @ self.f
        zz = np.where(np.abs(z) < 1e-6, 1e-6, z)
        return W / 2 + (d @ self.r) / zz * self.focal, H / 2 - (d @ self.u) / zz * self.focal, z


# ------------------------------------------------------------------ device helpers
_CACHE = {}


def grid():
    """device (yy, xx) pixel-centre coordinates, cached per resolution"""
    if "grid" not in _CACHE:
        yy, xx = np.mgrid[0:H, 0:W].astype(F32) + F32(0.5)
        _CACHE["grid"] = (asx(yy), asx(xx))
    return _CACHE["grid"]


def blur(img, sigma):
    """separable gaussian on the device (works with CuPy and the strict fake GPU)"""
    sigma = max(0.3, float(sigma))
    r = int(3 * sigma) + 1
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2).astype(F32)
    k = asx(k / k.sum())
    out = ndi.correlate1d(img, k, axis=0, mode="nearest")
    return ndi.correlate1d(out, k, axis=1, mode="nearest")


def bloom(img, thr=1.0, amount=0.6):
    """only truly bright pixels glow, at three radii"""
    hi = xp.maximum(img - F32(thr), F32(0))
    return img + F32(amount) * (blur(hi, 4 * U) * F32(0.5) + blur(hi, 16 * U) * F32(0.3) + blur(hi, 48 * U) * F32(0.2))


def glow(img, cx, cy, r, color, power=1.0):
    """additive soft light (HDR), e.g. a star or an engine flare"""
    yy, xx = grid()
    d2 = ((xx - F32(cx)) ** 2 + (yy - F32(cy)) ** 2) / F32(max(r, 1e-3) ** 2)
    f = F32(power) / (F32(1) + d2 * F32(8))
    return img + f[..., None] * asx(np.array(color, F32))[None, None, :]


def stars(cam, t):
    """host splat of the catalogue (varied magnitude & colour, no twinkling) -> device image"""
    D, mag, col = _CACHE.get("stars") or _star_catalogue()
    px, py, z = cam.project(cam.pos + D * 1e4)
    ok = (z > 0) & (px >= 0) & (px < W - 1) & (py >= 0) & (py < H - 1)
    acc = np.zeros((H, W, 3), F32)
    xi, yi = px[ok].astype(int), py[ok].astype(int)
    np.add.at(acc, (yi, xi), (col[ok] * mag[ok, None]).astype(F32))
    return blur(asx(acc), 0.7 * U)


def _star_catalogue(n=6000, seed=7):
    rng = np.random.default_rng(seed)
    v = rng.normal(size=(n, 3)); v /= np.linalg.norm(v, axis=1, keepdims=True)
    mag = (rng.pareto(2.2, n) * 0.25 + 0.05).clip(0, 6).astype(F32)
    temp = rng.random(n)
    col = np.stack([0.85 + 0.15 * temp, 0.9 * np.ones(n), 1.0 - 0.2 * temp], 1).astype(F32)
    _CACHE["stars"] = (v, mag, col)
    return _CACHE["stars"]


def finish(lin, i, exposure=1.0):
    """HDR linear -> filmic tonemap -> grade -> vignette -> grain + dither -> numpy uint8"""
    x = bloom(lin) * F32(exposure)
    a, b, c, d, e = 2.51, 0.03, 2.43, 0.59, 0.14              # ACES (Narkowicz) fit
    x = xp.clip((x * (F32(a) * x + F32(b))) / (x * (F32(c) * x + F32(d)) + F32(e)), 0, 1)
    yy, xx = grid()
    r2 = ((xx / F32(W) - F32(0.5)) ** 2 + (yy / F32(H) - F32(0.5)) ** 2) * F32(2.2)
    x = x * (F32(1) - F32(0.35) * r2)[..., None]               # vignette
    x = x ** F32(1 / 2.2)
    if "noise" not in _CACHE:
        _CACHE["noise"] = asx(np.random.default_rng(3).standard_normal((256, 256)).astype(F32))
    nz = _CACHE["noise"]
    o = (i * 37) % 256
    tile = xp.roll(nz, o, axis=0)
    reps = (H // 256 + 1, W // 256 + 1)
    g = xp.tile(tile, reps)[:H, :W]
    x = x + (g * F32(0.012))[..., None]                         # 1.2 % grain, also dithers 8-bit banding
    return cpu((xp.clip(x, 0, 1) * F32(255) + F32(0.5)).astype(xp.uint8))


# ------------------------------------------------------------------ text & captions (host, after finish)
_FONTS = {}
TEXT_LOG = None    # the renderer sets a list here a few times a second: text() and captions() note what they draw
                   # (for the automatic text checks - draw ALL on-screen text through these two)


def _note_text(s, box, px, color, alpha, cap=False):
    if TEXT_LOG is not None and alpha > 0.15 and str(s).strip():
        TEXT_LOG.append({"k": ("cap" if cap else f"{s}"), "text": str(s), "box": [float(v) for v in box],
                         "px": float(px), "color": [int(c) for c in color[:3]], "op": float(alpha), "cap": cap,
                         "clip": False})


def font(px, name="Poppins-Medium.ttf"):
    key = (name, int(px))
    if key not in _FONTS:
        _FONTS[key] = ImageFont.truetype(str(HERE / "fonts" / name), max(6, int(px)))
    return _FONTS[key]


def text(img, s, x, y, size=0.06, color=(240, 240, 240), alpha=1.0, anchor="mm", name="Poppins-Medium.ttf"):
    """size = fraction of the short side; x, y in pixels; alpha 0..1"""
    if alpha <= 0.001:
        return img
    im = Image.fromarray(img).convert("RGBA")
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d, f = ImageDraw.Draw(ov), font(size * min(W, H), name)
    d.text((x, y), s, font=f, fill=tuple(color) + (int(255 * clamp(alpha)),), anchor=anchor)
    _note_text(s, d.textbbox((x, y), s, font=f, anchor=anchor), f.size, color, alpha)
    return np.asarray(Image.alpha_composite(im, ov).convert("RGB"))


CAPTIONS = False   # True when the spec asks for burned-in captions


def captions(img, t, max_chars=32, safe_bottom=0.12):
    """word-timed captions from input/words.tsv: 1 line, active word highlighted, inside the safe area"""
    if not WORDS:
        return img
    groups, cur = [], []
    for w in WORDS:
        if cur and (len(" ".join(x[2] for x in cur + [w])) > max_chars or w[0] - cur[-1][1] > 0.6
                    or cur[-1][2][-1:] in ".!?"):
            groups.append(cur); cur = []
        cur.append(w)
    if cur:
        groups.append(cur)
    g = next((g for g in groups if g[0][0] - 0.05 <= t <= g[-1][1] + 0.25), None)
    if not g:
        return img
    f = font(0.052 * min(W, H), "Poppins-Medium.ttf")
    im = Image.fromarray(img).convert("RGBA")
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    widths = [d.textlength(w[2] + " ", font=f) for w in g]
    x = (W - sum(widths)) / 2
    y = H * (1 - safe_bottom) - f.size
    started = [w for w in WORDS if w[0] <= t]
    act = started[-1] if started and t <= started[-1][1] + 0.25 else None   # exactly one active word
    x_start = x
    for (s, e, w), wd in zip(g, widths):
        col = (255, 190, 90, 255) if (s, e, w) == act else (245, 245, 245, 235)
        d.text((x + 2 * U, y + 2 * U), w, font=f, fill=(0, 0, 0, 160))
        d.text((x, y), w, font=f, fill=col)
        x += wd
    line = " ".join(w[2] for w in g)
    bb = d.textbbox((x_start, y), line, font=f)
    _note_text(line, bb, f.size, (245, 245, 245), 1.0, cap=True)
    return np.asarray(Image.alpha_composite(im, ov).convert("RGB"))


# ------------------------------------------------------------------ scenes (one function per beat/scene)
def scene_approach(tl, t, cam):
    img = stars(cam, t) * F32(1.2)
    px, py, z = cam.project([[0, 0, 0]])
    if z[0] > 0:
        img = glow(img, px[0], py[0], 40 * U, (1.6, 1.0, 0.6), power=2.5)
    return img


def scene_title(tl, t, cam):
    return scene_approach(tl, t, cam)


SCENE_FN = {"approach": scene_approach, "title": scene_title}


def overlays(img, t):
    a = smooth(SCENES[1][1], SCENES[1][1] + 0.8, t)
    img = text(img, "Sarlavha", W / 2, H * 0.22, size=0.07, alpha=a)
    if CAPTIONS:
        img = captions(img, t)
    return img


# ------------------------------------------------------------------ entry points
def prepare_assets():
    (HERE / "cache").mkdir(exist_ok=True)
    _star_catalogue()


def scene_at(t):
    for name, a, b in SCENES:
        if a <= t < b:
            return name, a
    return SCENES[-1][0], SCENES[-1][1]


def render_frame(i):
    t = i / FPS
    name, a = scene_at(t)
    cam = Cam(camera_state(t))
    lin = SCENE_FN[name](t - a, t, cam)
    out = finish(lin, i)
    return overlays(out, t)
