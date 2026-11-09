"""'Hammasi boshlandi' — black hole approach. 2560x1440, 24 fps, 800 frames."""
import numpy as np, cairo, math, sys, os
import engine, sky
from backend import xp, asx, cpu
from engine import Cam, Lens

W, H = 2560, 1440
FPS = 24
NFR = 800  # 33.333 s
SCALE = 1.0  # for previews

def set_res(w, h):
    global W, H, SCALE
    W, H = w, h; SCALE = w / 2560.0

# ---------------------------------------------------------------- helpers
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def sstep(a, b, x):
    t = clamp((x - a) / (b - a)); return t * t * (3 - 2 * t)
def ssmooth(a, b, x):
    t = clamp((x - a) / (b - a)); return t * t * t * (t * (t * 6 - 15) + 10)
def lerp(a, b, t): return a + (b - a) * t
def V(*a): return np.array(a, float)
def norm(v): return v / np.linalg.norm(v)

def spline(keys, t):
    """keys: list of (time, np.array). C1 cubic Hermite with Catmull-Rom tangents, zero at ends."""
    ts = [k[0] for k in keys]
    if t <= ts[0]: return keys[0][1].copy()
    if t >= ts[-1]: return keys[-1][1].copy()
    i = max(j for j in range(len(ts) - 1) if ts[j] <= t)
    t0, t1 = ts[i], ts[i + 1]; p0, p1 = keys[i][1], keys[i + 1][1]
    def tan(j):
        if j == 0 or j == len(ts) - 1: return np.zeros_like(keys[j][1])
        return (keys[j + 1][1] - keys[j - 1][1]) / (ts[j + 1] - ts[j - 1])
    m0, m1 = tan(i) * (t1 - t0), tan(i + 1) * (t1 - t0)
    s = (t - t0) / (t1 - t0)
    h00 = 2 * s**3 - 3 * s**2 + 1; h10 = s**3 - 2 * s**2 + s
    h01 = -2 * s**3 + 3 * s**2; h11 = s**3 - s**2
    return h00 * p0 + h10 * m0 + h01 * p1 + h11 * m1

def skycam(cam, S):
    """camera whose basis is rotated into sky frame by matrix S (sky = S @ world)."""
    c = Cam.__new__(Cam)
    c.__dict__.update(cam.__dict__)
    c.f = S @ cam.f; c.r = S @ cam.r; c.u = S @ cam.u
    return c

def surf():
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    return s, cairo.Context(s)

def surf_np(s, host=False):
    s.flush()
    a = np.ndarray((H, W, 4), np.uint8, s.get_data(), strides=(s.get_stride(), 4, 1))
    if not host:
        a = asx(np.ascontiguousarray(a))
        a = a.astype(xp.float32) / 255.0
    else:
        a = a.astype(np.float32) / 255.0
    # BGRA premultiplied -> RGB premult, alpha
    return a[..., [2, 1, 0]], a[..., 3]

# ---------------------------------------------------------------- sky frames
S_GROUND = sky.rot_matrix([0, 0, 1], np.radians(-28)) @ sky.rot_matrix([1, 0, 0], np.radians(-48)) @ sky.rot_matrix([0, 1, 0], np.radians(25))
S_SPACE = sky.rot_matrix([0, 1, 0], np.radians(10)) @ sky.rot_matrix([1, 0, 0], np.radians(15))

# ================================================================= GROUND
LP_DIR = norm(V(-0.8, 0.0, -0.6))   # faint warm light-pollution dome on the horizon

def atmo_ground(D_sky, D_world):
    f32 = xp.float32
    el = xp.arcsin(xp.clip(D_world[:, 1], -1, 1))
    elc = xp.maximum(el, 0.0)
    trans = ((1 - xp.exp(-(elc + 0.004) / 0.045)) * (0.55 + 0.45 * xp.clip(elc / 0.5, 0, 1))).astype(f32)
    g_air = xp.exp(-elc / 0.10)[:, None] * asx(np.array([0.0075, 0.0095, 0.0130], np.float32))
    hxz = D_world[:, [0, 2]]
    lp = xp.clip(hxz @ asx(LP_DIR[[0, 2]].astype(np.float32)) / xp.maximum(xp.sqrt((hxz * hxz).sum(1)), 1e-6), 0, 1) ** 3
    g_lp = (xp.exp(-elc / 0.07) * lp)[:, None] * asx(np.array([0.0140, 0.0085, 0.0045], np.float32))
    zen = asx(np.array([0.0006, 0.0008, 0.0013], np.float32))
    return trans, (g_air + g_lp + zen).astype(f32)

def render_ground_sky(cam, lens_world=None):
    sc = skycam(cam, S_GROUND)
    Dw = cam.ray_dirs().reshape(-1, 3)
    def atmo(Dsky):
        return atmo_ground(Dsky, Dw)
    lens = None
    if lens_world is not None:
        n, thE, ths = lens_world
        lens = Lens(S_GROUND @ n, thE, ths)
    img = engine.render_sky(sc, lens, sky_gain=1.25, star_gain=5.0, atmo=atmo)
    return img

_NOISE = None
def tex_noise():
    global _NOISE
    if _NOISE is None:
        _NOISE = sky.fft_noise(512, 512, 2.0, 21)
    return _NOISE

def ridge_profile(xs, seed, amp, base, freqs):
    rng = np.random.default_rng(seed)
    h = np.full_like(xs, base, dtype=float)
    for j, f in enumerate(freqs):
        ph = rng.random() * 6.28
        h += amp * (0.55 ** j) * np.sin(xs * f + ph) * (0.6 + 0.4 * rng.random())
    return h

# observatory
DOME_C = V(4.0, 9.0, -46.0); DOME_R = 4.2; DRUM_H = 3.2
SLIT_AZ = norm(V(-0.09, 0, 1.0))  # slit faces roughly the camera, a bit left
TEL_DIR = norm(V(-0.25, 0.9, 0.35))

def obs_ridge_h(x):
    # plateau at drum base under the dome, falling off both sides
    base = DOME_C[1] - DRUM_H
    d = np.abs(x - DOME_C[0])
    fall = np.clip((d - 7.0) / 40.0, 0, None)
    h = base - 9.0 * fall ** 1.3 - 0.4 * np.sin(x * 0.7) * np.clip((d - 6) / 6, 0, 1)
    h += 0.25 * np.sin(x * 2.3 + 1) * np.clip((d - 6.5) / 3, 0, 1)
    return h

LAYERS = None
def ground_layers():
    global LAYERS
    if LAYERS is None:
        L = []
        xs = np.linspace(-9000, 9000, 1400)
        L.append(dict(z=-3600, xs=xs, h=ridge_profile(xs, 1, 230, 60, [0.0009, 0.0021, 0.0047, 0.011, 0.023]),
                      col=np.array([0.0042, 0.0050, 0.0068]), rim=0.35))
        xs = np.linspace(-2600, 2600, 1400)
        L.append(dict(z=-900, xs=xs, h=ridge_profile(xs, 2, 40, 6, [0.003, 0.007, 0.016, 0.035, 0.08]),
                      col=np.array([0.0026, 0.0030, 0.0040]), rim=0.45))
        xs = np.linspace(-400, 400, 1600)
        L.append(dict(z=-150, xs=xs, h=ridge_profile(xs, 3, 7, 1.5, [0.02, 0.05, 0.11, 0.25, 0.6]),
                      col=np.array([0.0014, 0.0016, 0.0021]), rim=0.5))
        xs = np.linspace(-160, 160, 2400)
        L.append(dict(z=-46.5, xs=xs, h=obs_ridge_h(xs), col=np.array([0.0009, 0.0010, 0.0013]), rim=0.6, obs=True))
        xs = np.linspace(-40, 40, 3000)
        rng = np.random.default_rng(9)
        hh = ridge_profile(xs, 5, 0.5, -0.9, [0.3, 0.8, 1.9, 4.0])
        grass = np.abs(rng.standard_normal(len(xs))) * 0.06 + np.clip(rng.standard_normal(len(xs)), 0, None) ** 3 * 0.05
        L.append(dict(z=-9.0, xs=xs, h=hh + grass, col=np.array([0.0004, 0.00045, 0.0006]), rim=0.2, blur=2.2))
        LAYERS = L
    return LAYERS

def layer_mask(cam, L):
    P = np.stack([L["xs"], L["h"], np.full_like(L["xs"], L["z"])], -1)
    px, py, z = cam.project(P)
    ok = z > 0.1
    px, py = px[ok], py[ok]
    if len(px) < 2: return None, None
    s, c = surf()
    c.move_to(px[0], H + 50)
    for x, y in zip(px, py): c.line_to(x, y)
    c.line_to(px[-1], H + 50); c.close_path()
    c.set_source_rgba(1, 1, 1, 1); c.fill()
    _, a = surf_np(s)
    # top edge per column for rim lighting
    cols = np.arange(W)
    order = np.argsort(px)
    top = np.interp(cols, px[order], py[order])
    return a, top

def composite_ground(img, cam, t):
    nz = tex_noise()
    yy = xp.arange(H, dtype=xp.float32)[:, None]
    ti = asx(np.tile(nz, (H // 512 + 1, W // 512 + 1))[:H, :W].astype(np.float32))
    tex = 1 + 0.12 * ti
    for L in ground_layers():
        a, top = layer_mask(cam, L)
        if a is None: continue
        if L.get("blur"):
            a = engine.gblur(a, L["blur"] * SCALE)
        dist = xp.maximum(yy - asx(top.astype(np.float32))[None, :], 0) / (40 * SCALE)
        rim = 1 + L["rim"] * xp.exp(-dist) * 1.2
        col = asx(L["col"].astype(np.float32))[None, None, :] * (rim * tex)[..., None]
        if L.get("obs"):
            img = img * (1 - a[..., None]) + col * a[..., None]
            img = render_dome(img, cam, t)
        else:
            img = img * (1 - a[..., None]) + col * a[..., None]
    return img

def render_dome(img, cam, t):
    # bounding box
    pts = DOME_C[None] + np.array([[sx * DOME_R * 1.2, sy, sz * DOME_R * 1.2] for sx in (-1, 1) for sz in (-1, 1) for sy in (-DRUM_H - 0.3, DOME_R * 1.1 + 3)])
    px, py, z = cam.project(pts)
    if (z <= 0.1).any(): return img
    x0 = int(max(0, px.min() - 4)); x1 = int(min(W, px.max() + 4))
    y0 = int(max(0, py.min() - 4)); y1 = int(min(H, py.max() + 4))
    if x1 <= x0 or y1 <= y0: return img
    # supersample 2x for AA
    ss = 2
    xs = (np.arange(x0 * ss, x1 * ss) + 0.5) / ss
    ys = (np.arange(y0 * ss, y1 * ss) + 0.5) / ss
    X, Y = np.meshgrid((xs - W / 2) / cam.focal, (H / 2 - ys) / cam.focal)
    D = cam.f[None, None] + X[..., None] * cam.r + Y[..., None] * cam.u
    D /= np.linalg.norm(D, axis=-1, keepdims=True)
    O = cam.pos
    oc = O - DOME_C
    # sphere
    b = D @ oc; c = oc @ oc - DOME_R ** 2
    disc = b * b - c
    hit_s = disc > 0
    ts = np.where(hit_s, -b - np.sqrt(np.maximum(disc, 0)), np.inf)
    Ps = O + ts[..., None] * D
    hit_s &= Ps[..., 1] >= DOME_C[1]
    ts = np.where(hit_s, ts, np.inf)
    # cylinder
    dxz = D[..., [0, 2]]; oxz = oc[[0, 2]]
    A = (dxz ** 2).sum(-1); B = dxz @ oxz; Cc = oxz @ oxz - DOME_R ** 2
    dc = B * B - A * Cc
    tc = np.where(dc > 0, (-B - np.sqrt(np.maximum(dc, 0))) / np.maximum(A, 1e-9), np.inf)
    Pc = O + tc[..., None] * D
    hit_c = (dc > 0) & (Pc[..., 1] <= DOME_C[1]) & (Pc[..., 1] >= DOME_C[1] - DRUM_H)
    tc = np.where(hit_c, tc, np.inf)
    tt = np.minimum(ts, tc)
    hit = np.isfinite(tt)
    P = O + np.where(hit, tt, 0)[..., None] * D
    on_s = ts <= tc
    N = np.where(on_s[..., None], (P - DOME_C) / DOME_R,
                 np.concatenate([(P - DOME_C)[..., :1], np.zeros_like(P[..., :1]), (P - DOME_C)[..., 2:]], -1) / DOME_R)
    # slit: on the sphere, within half-width of the great circle through SLIT_AZ and up
    q = (P - DOME_C) / DOME_R
    perp = norm(np.cross(SLIT_AZ, V(0, 1, 0)))
    lat_side = q @ perp
    fwd = q @ SLIT_AZ
    slit = on_s & hit & (np.abs(lat_side) < 0.11) & ((fwd > 0.05) & (q[..., 1] > 0.10))
    # lighting
    ny = N[..., 1]
    lp = np.clip(N @ LP_DIR, 0, None)
    az = np.arctan2(q[..., 0], q[..., 2])
    seams = 1 - 0.25 * (np.abs(np.sin(az * 12)) < 0.06)
    ring_seam = 1 - 0.3 * ((np.abs(q[..., 1] - 0.55) < 0.012) & on_s)
    alb = 0.75 * seams * ring_seam
    alb = np.where(on_s, alb, 0.55)
    sky_amb = np.array([0.016, 0.018, 0.024])
    key = norm(V(0.75, 0.55, 0.35))
    kl = np.clip(N @ key, 0, None)
    col = alb[..., None] * (sky_amb * 0.45 * (0.15 + 0.85 * (0.5 + 0.5 * ny))[..., None]
                            + np.array([0.016, 0.010, 0.006]) * lp[..., None]
                            + np.array([0.010, 0.012, 0.016]) * kl[..., None])
    base_ao = np.clip((P[..., 1] - (DOME_C[1] - DRUM_H)) / 1.2, 0.35, 1.0)
    col = col * base_ao[..., None]
    # specular sheen from bright zenith sky
    R = D - 2 * (D * N).sum(-1, keepdims=True) * N
    spec = np.clip(R[..., 1], 0, 1) ** 8 * 0.0025
    col = col + spec[..., None] * on_s[..., None]
    fres = (1 - np.abs((D * N).sum(-1))) ** 3
    col = col + fres[..., None] * np.array([0.010, 0.012, 0.016])
    # drum: door light
    door = (~on_s) & hit & (np.abs(q @ SLIT_AZ - 0.98) < 0.03) & False
    # slit interior: dim red light + telescope tube silhouette
    if slit.any():
        # distance from ray to telescope axis segment
        tb = DOME_C + V(0, 0.4, 0); td = TEL_DIR
        w0 = O - tb
        a_ = 1.0; b_ = D @ td; c_ = td @ td; d_ = D @ w0; e_ = w0 @ td
        den = a_ * c_ - b_ * b_
        sc_ = (b_ * e_ - c_ * d_) / np.maximum(den, 1e-9)
        tc_ = (a_ * e_ - b_ * d_) / np.maximum(den, 1e-9)
        tc_ = np.clip(tc_, -1.0, 4.5)
        dist = np.linalg.norm(O + sc_[..., None] * D - (tb + tc_[..., None] * td), axis=-1)
        tube = dist < 0.55
        inner = np.array([0.0045, 0.0010, 0.0007]) * (0.6 + 0.4 * np.clip(1 - q[..., 1], 0, 1))[..., None]
        tubec = np.array([0.0012, 0.0005, 0.0004]) * (1 + 3.0 * np.exp(-((dist - 0.5) / 0.06) ** 2))[..., None]
        ic = np.where(tube[..., None], tubec, inner)
        col = np.where(slit[..., None], ic, col)
    # downsample
    h_, w_ = hit.shape
    alpha = hit.astype(np.float32).reshape(h_ // ss, ss, w_ // ss, ss).mean((1, 3))
    colm = (col * hit[..., None]).reshape(h_ // ss, ss, w_ // ss, ss, 3).mean((1, 3))
    reg = img[y0:y1, x0:x1]
    img[y0:y1, x0:x1] = reg * (1 - asx(alpha.astype(np.float32))[..., None]) + asx(colm.astype(np.float32))
    # faint red spill glow from the slit
    return img

def ground_scene(t, cam, lens_world=None):
    img = render_ground_sky(cam, lens_world)
    img = composite_ground(img, cam, t)
    return img

# ================================================================= SPACE (solar system)
PL = [  # name, R(visual), size, color, omega rad/s, phase
    ("mercury", 1.79, 0.075, (0.55, 0.52, 0.50)),
    ("venus", 2.50, 0.11, (0.86, 0.80, 0.66)),
    ("earth", 3.00, 0.12, (0.35, 0.52, 0.80)),
    ("mars", 3.75, 0.09, (0.78, 0.45, 0.30)),
    ("jupiter", 7.40, 0.40, (0.82, 0.72, 0.60)),
    ("saturn", 10.3, 0.34, (0.86, 0.78, 0.60)),
    ("uranus", 15.3, 0.23, (0.62, 0.82, 0.86)),
    ("neptune", 19.4, 0.22, (0.40, 0.55, 0.88)),
]
PHASE = [0.4, 2.2, 4.0, 5.3, 3.9, 3.4, 5.9, 2.6]
ECC = [0.10, 0.01, 0.017, 0.06, 0.05, 0.055, 0.046, 0.01]
OMEGA0 = 0.16

def planet_angle(k, t):
    R = PL[k][1]
    return PHASE[k] + OMEGA0 * (3.0 / R) ** 1.5 * t

def orbit_point(k, ang, perturb=None):
    R = PL[k][1]; e = ECC[k]
    r = R * (1 - e * e) / (1 + e * np.cos(ang - k))
    P = np.stack([r * np.cos(ang), np.zeros_like(ang), r * np.sin(ang)], -1)
    if perturb is not None:
        P = P + perturb(P, k)
    return P

def wobble_offset(k, ang, t, A):
    """the 'strange wobble': small radial oscillation along the actual path."""
    if A <= 0: return 0.0
    return A * (k - 3.5) / 4.5 * np.sin(ang * 9 + t * 1.3 + k) * 0.9

def draw_polyline(ctx, px, py, ok, width, rgba_fn=None, rgba=None):
    ctx.set_line_width(width)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    if rgba is not None:
        started = False
        for x, y, o in zip(px, py, ok):
            if not o:
                if started: ctx.stroke(); started = False
                continue
            if not started: ctx.move_to(x, y); started = True
            else: ctx.line_to(x, y)
        if started: ctx.stroke()
        return
    for i in range(len(px) - 1):
        if not (ok[i] and ok[i + 1]): continue
        r, g, b, a = rgba_fn(i)
        if a <= 0.002: continue
        ctx.set_source_rgba(r, g, b, a)
        ctx.move_to(px[i], py[i]); ctx.line_to(px[i + 1], py[i + 1]); ctx.stroke()

def add_glow(img, cx, cy, core, r0, halo, r1, col):
    """additive radial glow at screen position."""
    rad = int(min(max(r1 * 6, r0 * 30), 1600 * SCALE))
    x0, x1 = int(max(0, cx - rad)), int(min(W, cx + rad))
    y0, y1 = int(max(0, cy - rad)), int(min(H, cy + rad))
    if x1 <= x0 or y1 <= y0: return
    yy = xp.arange(y0, y1, dtype=xp.float32)[:, None]; xx = xp.arange(x0, x1, dtype=xp.float32)[None, :]
    r = xp.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    v = core / (1 + (r / r0) ** 2) ** 1.6 + halo * xp.exp(-r / r1)
    img[y0:y1, x0:x1] += (v[..., None] * asx(np.array(col, np.float32))).astype(xp.float32)

def render_planet(img, cam, P, size, col, sunpos, kname, ring=False, t=0):
    px, py, z = cam.project(P[None])
    px, py, z = px[0], py[0], z[0]
    if z <= 0.05: return
    rp = size / z * cam.focal
    if px < -50 or px > W + 50 or py < -50 or py > H + 50: return
    if rp < 0.9:
        # point-like: add as a small light
        L = norm(sunpos - P); vdir = norm(cam.pos - P)
        phase = 0.5 + 0.5 * (L @ vdir)
        add_glow(img, px, py, 0.08 * phase * min(1, rp + 0.3), 0.9 * SCALE + 0.5, 0, 1, col)
        return
    rr = int(rp * (2.6 if ring else 1.0) + 3)
    x0, x1 = int(max(0, px - rr)), int(min(W, px + rr + 1))
    y0, y1 = int(max(0, py - rr)), int(min(H, py + rr + 1))
    if x1 <= x0 or y1 <= y0: return
    ss = 3
    xs = (np.arange(x0 * ss, x1 * ss) + 0.5) / ss; ys = (np.arange(y0 * ss, y1 * ss) + 0.5) / ss
    X, Y = np.meshgrid((xs - W / 2) / cam.focal, (H / 2 - ys) / cam.focal)
    D = cam.f + X[..., None] * cam.r + Y[..., None] * cam.u
    D /= np.linalg.norm(D, axis=-1, keepdims=True)
    oc = cam.pos - P
    b = D @ oc; c = oc @ oc - size ** 2
    disc = b * b - c
    hit = disc > 0
    th = -b - np.sqrt(np.maximum(disc, 0))
    Q = cam.pos + th[..., None] * D
    N = (Q - P) / size
    L = norm(sunpos - P)
    lam = np.clip(N @ L, 0, 1)
    # soft terminator + slight atmosphere limb
    shade = lam ** 0.9
    albedo = np.array(col)
    if kname in ("jupiter", "saturn"):
        band = 1 + 0.12 * np.sin(N[..., 1] * 22) + 0.06 * np.sin(N[..., 1] * 47 + 1)
        albedo = albedo[None, None] * band[..., None]
    elif kname == "earth":
        albedo = albedo[None, None] * (1 + 0.25 * (np.sin(N[..., 0] * 9) * np.sin(N[..., 1] * 7) > 0.3))[..., None]
    else:
        albedo = albedo[None, None] * np.ones_like(shade)[..., None]
    colr = albedo * shade[..., None] * 0.9
    alpha = hit.astype(np.float32)
    if ring:
        # ring plane tilted
        rn = norm(V(0.25, 1, 0.1))
        dn = D @ rn
        tr = -(oc @ rn) / np.where(np.abs(dn) < 1e-6, 1e-6, dn)
        Qr = cam.pos + tr[..., None] * D
        rr_ = np.linalg.norm(Qr - P, axis=-1) / size
        inring = (rr_ > 1.25) & (rr_ < 2.3) & (tr > 0)
        dens = (0.55 + 0.45 * np.sin(rr_ * 31) ** 2) * (np.abs(rr_ - 1.95) > 0.05)
        front = inring & (~hit | (tr < th))
        rl = 0.55 * abs(L @ rn) + 0.25
        rc = np.array([0.85, 0.78, 0.62]) * rl
        a_r = (dens * 0.85) * front
        colr = colr * (1 - a_r[..., None]) * np.where(hit, 1, 0)[..., None] + rc * a_r[..., None]
        alpha = np.clip(alpha * (1 - a_r) + a_r, 0, 1)
    h_, w_ = alpha.shape
    am = alpha.reshape(h_ // ss, ss, w_ // ss, ss).mean((1, 3))
    cm = (colr * (alpha if not ring else 1)[..., None] if not ring else colr).reshape(h_ // ss, ss, w_ // ss, ss, 3).mean((1, 3))
    if not ring:
        cm = (colr * alpha[..., None]).reshape(h_ // ss, ss, w_ // ss, ss, 3).mean((1, 3))
    reg = img[y0:y1, x0:x1]
    img[y0:y1, x0:x1] = reg * (1 - asx(am.astype(np.float32))[..., None]) + asx((cm * 0.9).astype(np.float32))

SUN = V(0, 0, 0)

def draw_sun(img, cam, gain=1.0):
    px, py, z = cam.project(SUN[None])
    if z[0] <= 0.1: return
    rp = 0.30 / z[0] * cam.focal
    add_glow(img, px[0], py[0], 40.0 * gain, max(rp, 1.2), 0.0, 1, (1.0, 0.93, 0.82))
    add_glow(img, px[0], py[0], 0.0, 1, 0.10 * gain, 9 * SCALE + rp * 1.5, (1.0, 0.86, 0.66))
    add_glow(img, px[0], py[0], 0.0, 1, 0.010 * gain, 120 * SCALE, (1.0, 0.80, 0.60))

# incoming body: hyperbolic-ish path, parameter s: 0 = far start ("years ago"), 1 = near system
B_FAR = V(-78.0, 30.0, -112.0)
B_NEAR = V(-26.0, 4.5, -15.0)
def traj_point(s, var=None):
    """quadratic bezier from far point to near, curving; var=(dx,dy,dz) perturbs the control point."""
    ctrl = V(-58.0, 18.0, -50.0)
    end = V(-12.0, 1.0, 6.0)
    if var is not None:
        ctrl = ctrl + var[0]; end = end + var[1]
    s = np.asarray(s)[..., None]
    return (1 - s) ** 2 * B_FAR + 2 * (1 - s) * s * ctrl + s ** 2 * end

RS_BH = 0.2
def bh_lens(cam, Bpos, strength=1.0, S=None):
    if S is None: S = S_SPACE
    d = Bpos - cam.pos
    D = np.linalg.norm(d)
    thE = math.sqrt(2 * RS_BH / D)
    ths = min(2.6 * RS_BH / D, 1.2)
    return Lens(S @ (d / D), thE * strength, ths * strength ** 2), D

def space_scene(t, cam, mode, P):
    """mode 'B' (years ago: system + calculation) or 'C' (months ago: BH near)."""
    sc = skycam(cam, S_SPACE)
    lens = None
    if mode == "B":
        Bpos = B_FAR
        ls = P.get("bh_strength", 1.0)
        if ls > 0:
            lens, Dbh = bh_lens(cam, Bpos, ls * 1.5)
    else:
        Bpos = P["bh_pos"]
        lens, Dbh = bh_lens(cam, Bpos, 1.0)
    img = engine.render_sky(sc, lens, sky_gain=1.7, star_gain=3.0)
    ov_gain = P.get("overlay", 1.0)
    # ---------- overlay: orbits / trails / trajectories (additive light)
    s, ctx = surf()
    perturb = None
    if mode == "C":
        k_dist = P.get("distort", 0.0)
        def perturb(Pts, k):
            d = Bpos[None] - Pts
            r = np.linalg.norm(d, axis=-1, keepdims=True)
            pull = k_dist * 6.0 * (PL[k][1] / 19.4) ** 2 / (1 + (r / 8.0) ** 2)
            return d / r * pull
    wob = P.get("wobble", 0.0)
    if ov_gain > 0:
        ang = np.linspace(0, 2 * np.pi, 721)
        for k in range(8):
            Pts = orbit_point(k, ang, perturb)
            px, py, z = cam.project(Pts)
            ok = z > 0.2
            depth = np.clip(z, 1, None)
            a0 = 0.20 * ov_gain * P.get("orbit_alpha", 1.0)
            # fade with depth so far side is dimmer
            dn = (depth - depth.min()) / max(np.ptp(depth), 1e-6)
            fn = lambda i: (0.62, 0.72, 0.88, a0 * (1.0 - 0.45 * dn[i]))
            draw_polyline(ctx, px, py, ok, 1.5 * SCALE, rgba_fn=fn)
        # wobble trails for outer planets
        if wob > 0:
            for k in range(4, 8):
                a1 = planet_angle(k, t)
                span = 0.9 if k < 6 else 0.55
                tang = np.linspace(a1 - span, a1, 120)
                base = orbit_point(k, tang, perturb)
                rdir = base / np.maximum(np.linalg.norm(base, axis=-1, keepdims=True), 1e-6)
                off = wobble_offset(k, tang, t, wob)
                Pts = base + rdir * np.asarray(off)[..., None] * (1 + 0 * tang[..., None])
                px, py, z = cam.project(Pts)
                ok = z > 0.2
                fn = lambda i: (0.95, 0.86, 0.70, 0.55 * wob * ov_gain * (i / 120) ** 1.5)
                draw_polyline(ctx, px, py, ok, 2.0 * SCALE, rgba_fn=fn)
        # calculation: candidate trajectories
        cand = P.get("cand", 0.0)  # draw progress 0..1
        conv = P.get("conv", 0.0)  # convergence 0..1
        if cand > 0:
            rng = np.random.default_rng(3)
            vars_ = [(rng.normal(0, 16, 3) * V(1, 0.7, 1), rng.normal(0, 4, 3) * V(1, 0.3, 1)) for _ in range(7)]
            for j, (v0, v1) in enumerate(vars_):
                vv = ((1 - conv) * v0, (1 - conv) * v1)
                s1 = 1.0; s0 = 1.0 - clamp(cand * 1.25 - j * 0.04) * 1.0
                ss_ = np.linspace(s1, max(s0, 0), 220)
                Pts = traj_point(ss_, vv)
                px, py, z = cam.project(Pts)
                ok = z > 0.2
                alpha = 0.55 * ov_gain * (1 - 0.85 * conv) * P.get("cand_fade", 1.0)
                ctx.set_dash([10 * SCALE, 8 * SCALE])
                ctx.set_source_rgba(0.95, 0.80, 0.60, alpha)
                draw_polyline(ctx, px, py, ok, 1.7 * SCALE, rgba=True)
                ctx.set_dash([])
        sol = P.get("solution", 0.0)
        if sol > 0:
            ext = P.get("sol_extent", 1.0)
            ss_ = np.linspace(1.0, 1.0 - ext, 400)
            Pts = traj_point(ss_)
            px, py, z = cam.project(Pts)
            ok = z > 0.2
            fn = lambda i: (1.0, 0.82, 0.62, 0.70 * sol * ov_gain * (0.35 + 0.65 * (i / 400)))
            draw_polyline(ctx, px, py, ok, 1.8 * SCALE, rgba_fn=fn)
            flow = P.get("flow", 0.0)
            if flow > 0:
                # bright dashes travelling inward (toward the Sun)
                for q in range(14):
                    u = ((q / 14.0) - t * 0.045) % 1.0
                    seg = np.linspace(u, min(u + 0.018, 1.0), 12)
                    Pp = traj_point(seg)
                    px, py, z = cam.project(Pp)
                    ok = z > 0.2
                    ctx.set_source_rgba(1.0, 0.88, 0.70, 0.55 * flow * ov_gain * math.sin(math.pi * u) ** 0.5)
                    draw_polyline(ctx, px, py, ok, 2.4 * SCALE, rgba=True)
    rgb, a = surf_np(s)
    img += rgb * 0.22
    # ---------- reticle around the unknown body
    ret = P.get("reticle", 0.0)
    if ret > 0 and mode == "B":
        px, py, z = cam.project(B_FAR[None])
        if z[0] > 0:
            s2, c2 = surf()
            R0 = (70 + 18 * (1 - ret)) * SCALE
            c2.set_source_rgba(0.95, 0.88, 0.75, 0.75 * ret)
            c2.set_line_width(1.6 * SCALE)
            for q in range(4):
                a0 = q * math.pi / 2 + math.pi / 4
                c2.arc(px[0], py[0], R0, a0 - 0.32, a0 + 0.32); c2.stroke()
            # tiny centre ticks
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                c2.move_to(px[0] + dx * R0 * 1.18, py[0] + dy * R0 * 1.18)
                c2.line_to(px[0] + dx * R0 * 1.34, py[0] + dy * R0 * 1.34); c2.stroke()
            rgb2, a2 = surf_np(s2)
            img += rgb2 * 0.22
    # ---------- planets, then sun glare on top (glare is optical)
    if P.get("planets", 1.0) > 0:
        for k, (nm, R, size, col) in enumerate(PL):
            a1 = planet_angle(k, t)
            Pp = orbit_point(k, np.array([a1]), perturb)[0]
            if wob > 0 and k >= 4:
                Pp = Pp + Pp / np.linalg.norm(Pp) * wobble_offset(k, a1, t, wob)
            render_planet(img, cam, Pp, size, col, SUN, nm, ring=(nm == "saturn"), t=t)
    draw_sun(img, cam, P.get("sun", 1.0))
    return img

# ================================================================= TIMELINE
def cam_ground1(t):
    keys_pos = [(0.0, V(0, 1.7, 0)), (2.4, V(0.6, 1.9, -2.2)), (4.6, V(1.1, 2.1, -3.8))]
    keys_tgt = [(0.0, V(3.0, 9.0, -46)), (2.4, V(1.5, 18.0, -46)), (4.6, V(-6.0, 48.0, -36))]
    pos = spline(keys_pos, t); tgt = spline(keys_tgt, t)
    fov = lerp(42, 40, sstep(0, 4.6, t))
    return Cam.look(pos, tgt, V(0, 1, 0), fov, W, H, roll=np.radians(-1.0) * sstep(0, 4.6, t))

def mix_target(pos, pA, pB, w):
    dA = norm(pA - pos); dB = norm(pB - pos)
    return pos + norm(w * dA + (1 - w) * dB) * 10.0

def cam_space_B(t):
    # S2 (3.2-7.2): oblique orbit; S3 (7.2-16.6): rise, pull back, frame system + far body, push to the body
    kp = [(3.2, V(14, 9.5, 34)), (5.2, V(8, 10.5, 33)), (7.2, V(2, 13, 33)),
          (9.6, V(-2, 26, 46)), (12.0, V(-6, 34, 52)), (14.3, V(-16, 36, 42)), (16.6, V(-30, 34, 22))]
    pos = spline(kp, t)
    w = spline([(3.2, V(1.0)), (7.2, V(1.0)), (9.6, V(0.80)), (12.0, V(0.50)), (14.3, V(0.30)), (16.6, V(0.0))], t)[0]
    tgt = mix_target(pos, V(0.3, 0, 0), B_FAR, w)
    fov = spline([(3.2, V(40.0)), (9.6, V(44.0)), (12.0, V(48.0)), (14.3, V(46.0)), (16.6, V(40.0))], t)[0]
    roll = np.radians(spline([(3.2, V(-4.0)), (7.2, V(-2.0)), (12.0, V(4.0)), (16.6, V(1.5))], t)[0])
    return Cam.look(pos, tgt, V(0, 1, 0), fov, W, H, roll=roll)

def cam_space_C(t):
    # months ago: BH just outside Neptune's orbit; 16-22 frame system + BH; 22-26.9 approach BH with lateral arc
    B = B_NEAR
    kp = [(16.0, V(10, 24, 34)), (19.0, V(4, 22, 30)), (22.0, V(-6, 16, 18)),
          (24.0, B + V(9, 5.0, 12)), (26.9, B + V(1.55, 0.6, 2.5))]
    pos = spline(kp, t)
    w = spline([(16.0, V(0.40)), (19.0, V(0.42)), (21.0, V(0.36)), (22.6, V(0.0)), (26.9, V(0.0))], t)[0]
    tgt = mix_target(pos, V(0, 0, 0), B, w)
    fov = spline([(16.0, V(48.0)), (22.0, V(46.0)), (26.9, V(52.0))], t)[0]
    roll = np.radians(spline([(16.0, V(2.0)), (22.0, V(-3.0)), (26.9, V(-9.0))], t)[0])
    return Cam.look(pos, tgt, V(0, 1, 0), fov, W, H, roll=roll)

BH_SKY_G = norm(V(-0.25, 0.62, -0.75))  # BH direction in the Earth sky (world frame)
def azel(az, el):
    az, el = np.radians(az), np.radians(el)
    return V(np.sin(az) * np.cos(el), np.sin(el), -np.cos(az) * np.cos(el))

BH_AZ = math.degrees(math.atan2(BH_SKY_G[0], -BH_SKY_G[2])); BH_EL = math.degrees(math.asin(BH_SKY_G[1]))
def cam_ground2(t):
    kp = [(26.2, V(0.8, 1.7, -2.0)), (29.5, V(0.4, 1.7, -0.6)), (33.4, V(-0.6, 1.65, 2.5))]
    pos = spline(kp, t)
    az = spline([(26.2, V(BH_AZ + 2)), (28.8, V(BH_AZ + 3.5)), (31.5, V(-7.0)), (33.4, V(-5.5))], t)[0]
    el = spline([(26.2, V(BH_EL - 1)), (28.8, V(BH_EL - 4)), (31.5, V(22.5)), (33.4, V(21.0))], t)[0]
    fov = spline([(26.2, V(36.0)), (33.4, V(50.0))], t)[0]
    return Cam.look(pos, pos + azel(az, el) * 10, V(0, 1, 0), fov, W, H, roll=np.radians(1.5) * (1 - sstep(26.2, 33.4, t)))

def params_B(t):
    return dict(
        wobble=sstep(5.3, 6.6, t) * (1 - 0.5 * sstep(9.0, 11.0, t)),
        orbit_alpha=sstep(3.3, 4.6, t),
        cand=sstep(7.5, 9.3, t), conv=ssmooth(9.3, 10.4, t), cand_fade=1 - sstep(10.2, 10.9, t),
        solution=sstep(9.6, 10.6, t), sol_extent=lerp(0.2, 1.0, ssmooth(9.6, 12.2, t)),
        reticle=sstep(12.0, 12.9, t), flow=sstep(13.7, 14.6, t),
        bh_strength=lerp(0.25, 1.0, sstep(11.5, 13.3, t)),
        sun=1.0, planets=1.0,
    )

def params_C(t):
    app = sstep(22.0, 26.9, t)
    return dict(bh_pos=B_NEAR, distort=ssmooth(19.4, 22.2, t), overlay=1 - sstep(22.6, 24.6, t),
                wobble=0.0, sun=1 - 0.6 * app, planets=1 - sstep(23.0, 24.5, t))

def ground2_lens(t, cam):
    # BH appears in the Earth sky; grows in from 26.6 to 28.6, drifting slowly
    st = ssmooth(26.4, 28.8, t)
    drift = sky.rot_matrix([0, 1, 0], np.radians(-0.25 * (t - 26.2))) @ BH_SKY_G
    return (drift, np.radians(6.5) * st, np.radians(0.75) * st ** 2)


def gal_vec(l, b):
    l, b = np.radians(l), np.radians(b)
    return np.array([np.cos(b) * np.sin(l), np.sin(b), np.cos(b) * np.cos(l)]) @ sky.RG

def frame_two(a1, a2, l1, b1=0.0, sign=1.0):
    """rotation S with S@a1 on galactic (l1,b1) and S@a2 on the galactic plane further along."""
    a1 = norm(a1); a2 = norm(a2)
    th = math.degrees(math.acos(np.clip(a1 @ a2, -1, 1)))
    g1 = gal_vec(l1, b1); g2 = gal_vec(l1 + sign * th, b1)
    def basis(x, y):
        e2 = norm(y - (y @ x) * x); return np.stack([x, e2, np.cross(x, e2)], 1)
    return basis(g1, g2) @ basis(a1, a2).T

def _init_frames():
    global S_SPACE, S_GROUND
    c = cam_space_C(24.8); hero = norm(B_NEAR - c.pos)
    c2 = cam_space_B(5.0); sysd = c2.f
    S_SPACE = frame_two(hero, sysd, -4.0, 1.5, 1.0)
    up_dome = norm(V(1.0, 30.0, -46.0) - V(0, 1.7, 0))
    S_GROUND = frame_two(BH_SKY_G, up_dome, 8.0, 0.5, -1.0)
_init_frames()

def render_hdr(t):
    layers = []
    # (weight, fn)
    def wA(t): return 1 - ssmooth(3.2, 4.4, t)
    def wB(t): return ssmooth(3.2, 4.4, t) * (1 - ssmooth(16.0, 16.65, t))
    def wC(t): return ssmooth(16.0, 16.65, t) * (1 - ssmooth(26.2, 26.95, t))
    def wD(t): return ssmooth(26.2, 26.95, t)
    out = None
    for w, fn in ((wA(t), lambda: ground_scene(t, cam_ground1(min(t, 4.6)))),
                  (wB(t), lambda: space_scene(t, cam_space_B(clamp(t, 3.2, 16.6)), "B", params_B(t))),
                  (wC(t), lambda: space_scene(t, cam_space_C(clamp(t, 16.0, 26.9)), "C", params_C(t))),
                  (wD(t), lambda: (lambda c: ground_scene(t, c, ground2_lens(t, c)))(cam_ground2(max(t, 26.2))))):
        if w <= 1e-4: continue
        im = fn() * w
        out = im if out is None else out + im
    return out

# ---------------------------------------------------------------- text
FONT = "Inter Display"
def draw_caption(rgb8, text, t, t0, t1):
    a = sstep(t0, t0 + 0.7, t) * (1 - sstep(t1 - 0.7, t1, t))
    if a <= 0: return rgb8
    s, c = surf()
    c.select_font_face(FONT, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    fo = cairo.FontOptions(); fo.set_antialias(cairo.ANTIALIAS_GRAY); c.set_font_options(fo)
    size = 40 * SCALE
    c.set_font_size(size)
    track = (0.30 + 0.10 * ssmooth(t0, t1, t)) * size  # letters breathe apart slowly
    x = 180 * SCALE; y = H - 200 * SCALE
    # thin rule that draws in
    rule = 70 * SCALE * ssmooth(t0, t0 + 1.0, t)
    c.set_source_rgba(0.92, 0.88, 0.80, 0.55 * a)
    c.set_line_width(1.4 * SCALE)
    c.move_to(x, y - 62 * SCALE); c.line_to(x + rule, y - 62 * SCALE); c.stroke()
    c.set_source_rgba(0.93, 0.90, 0.84, 0.92 * a)
    dx = 0
    for ch in text:
        c.move_to(x + dx, y + 6 * SCALE * (1 - a)); c.show_text(ch)
        dx += c.text_extents(ch).x_advance + track
    rgb, al = surf_np(s, host=True)
    f = rgb8.astype(np.float32) / 255
    f = f * (1 - al[..., None]) + rgb
    return (np.clip(f, 0, 1) * 255 + 0.5).astype(np.uint8)

def render_frame(i):
    t = i / FPS
    img = render_hdr(t)
    img = engine.bloom(img, 0.07)
    fade = sstep(0.0, 1.1, t) * (1 - sstep(33.05, 33.33, t) * 0.0)
    out = engine.finish(img, i, exposure=1.0, vignette=0.32, grain=0.010, fade=fade)
    out = draw_caption(out, "BIR NECHA YIL OLDIN", t, 0.55, 2.75)
    out = draw_caption(out, "BIR-IKKI OY OLDIN", t, 16.35, 18.8)
    return out

if __name__ == "__main__":
    from PIL import Image
    mode = sys.argv[1]
    if mode == "preview":
        set_res(int(sys.argv[2]), int(sys.argv[2]) * 9 // 16)
        times = [float(x) for x in sys.argv[3].split(",")]
        os.makedirs("prev", exist_ok=True)
        for tt in times:
            im = render_frame(int(round(tt * FPS)))
            Image.fromarray(im).save(f"prev/t{tt:05.2f}.png")
            print("done", tt, flush=True)

# ---------------------------------------------------------------- kit contract
SELFTEST_FRAMES = [36, int(24.8 * 24)]  # a ground frame and the lensing close-up

def prepare_assets():
    """build cached heavy assets once in the main process (before workers start)."""
    sky.build_milkyway(); sky.build_stars()
