"""Core renderer: camera, lensed sky sampling, star splatting, post. Runs on GPU (CuPy) or CPU (NumPy)."""
import math
import numpy as np
import sky
from backend import xp, ndi, asx, cpu, GPU

F32 = np.float32

class Cam:
    def __init__(self, pos, fwd, up, fovy_deg, W, H):
        self.pos = np.asarray(pos, float)
        f = np.asarray(fwd, float); f /= np.linalg.norm(f)
        r = np.cross(f, up); r /= np.linalg.norm(r)
        u = np.cross(r, f)
        self.f, self.r, self.u = f, r, u
        self.W, self.H = W, H
        self.ty = np.tan(np.radians(fovy_deg) / 2)
        self.tx = self.ty * W / H
        self.focal = (H / 2) / self.ty

    @staticmethod
    def look(pos, target, up, fovy, W, H, roll=0.0):
        f = np.asarray(target, float) - np.asarray(pos, float)
        f /= np.linalg.norm(f)
        up = np.asarray(up, float)
        if roll:
            up = sky.rot_matrix(f, roll) @ up
        return Cam(pos, f, up, fovy, W, H)

    def project(self, P):
        """CPU: P (...,3) world -> px, py, z (camera depth)."""
        d = np.asarray(P, float) - self.pos
        z = d @ self.f
        x = d @ self.r; y = d @ self.u
        zz = np.where(np.abs(z) < 1e-9, 1e-9, z)
        px = self.W / 2 + x / zz * self.focal
        py = self.H / 2 - y / zz * self.focal
        return px, py, z

    def project_dir(self, D):
        """backend arrays: dirs (N,3) -> px, py, z"""
        f = asx(self.f, F32); r = asx(self.r, F32); u = asx(self.u, F32)
        z = D @ f
        x = D @ r; y = D @ u
        zz = xp.where(z < 1e-6, F32(1e-6), z)
        return self.W / 2 + x / zz * F32(self.focal), self.H / 2 - y / zz * F32(self.focal), z

    def ray_dirs(self):
        """backend (H,W,3) float32 unit ray directions"""
        W, H = self.W, self.H
        xs = ((xp.arange(W, dtype=F32) + F32(0.5)) - F32(W / 2)) / F32(self.focal)
        ys = (F32(H / 2) - (xp.arange(H, dtype=F32) + F32(0.5))) / F32(self.focal)
        f = asx(self.f, F32); r = asx(self.r, F32); u = asx(self.u, F32)
        D = f[None, None, :] + xs[None, :, None] * r[None, None, :] + ys[:, None, None] * u[None, None, :]
        D /= xp.sqrt((D * D).sum(-1, keepdims=True))
        return D

_PYR = None; _STARS = None
def assets():
    global _PYR, _STARS
    if _PYR is None:
        mw = sky.build_milkyway()
        pyr = sky.build_pyramid(mw, 8)
        _PYR = [asx(p) for p in pyr]
        sd, sf, sc = sky.build_stars()
        _STARS = (asx(sd, F32), asx(sf, F32), asx(sc, F32))
    return _PYR, _STARS

def sample_equirect(tex, gdir):
    """bilinear sample of equirect texture with galactic dirs (N,3)."""
    th, tw = tex.shape[:2]
    lon = xp.arctan2(gdir[:, 0], gdir[:, 2])
    lat = xp.arcsin(xp.clip(gdir[:, 1], -1, 1))
    x = (lon + F32(math.pi)) * F32(tw / (2 * math.pi)) - F32(0.5)
    y = (F32(math.pi / 2) - lat) * F32(th / math.pi) - F32(0.5)
    x0f = xp.floor(x); y0f = xp.floor(y)
    fx = (x - x0f)[:, None].astype(F32); fy = (y - y0f)[:, None].astype(F32)
    x0 = x0f.astype(xp.int32) % tw; x1 = (x0 + 1) % tw
    y0 = xp.clip(y0f.astype(xp.int32), 0, th - 1); y1 = xp.clip(y0 + 1, 0, th - 1)
    a = tex[y0, x0].astype(F32); b = tex[y0, x1].astype(F32)
    c = tex[y1, x0].astype(F32); d = tex[y1, x1].astype(F32)
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy

class Lens:
    """Point-mass lens seen from camera. n: unit dir to BH; thE: Einstein angle (rad); ths: shadow angle."""
    def __init__(self, n, thE, ths, strength=1.0):
        self.n = np.asarray(n, float) / np.linalg.norm(n)
        self.thE = thE * strength; self.ths = ths * strength
        self.strength = strength

def lens_dirs(D, lens):
    """map image dirs -> source dirs. returns src dirs, shadow mask, magnif (for mip), theta."""
    n = asx(lens.n, F32)
    c = xp.clip(D @ n, -1, 1)
    th = xp.arccos(c)
    e = D - c[:, None] * n[None]
    en = xp.sqrt((e * e).sum(1, keepdims=True)); e /= xp.maximum(en, F32(1e-9))
    th_safe = xp.maximum(th, F32(1e-6))
    tE2 = F32(lens.thE ** 2)
    beta = th - tE2 / th_safe
    src = xp.cos(beta)[:, None] * n[None] + xp.sin(beta)[:, None] * e
    radial = 1 + tE2 / th_safe ** 2
    tang = xp.abs(xp.sin(beta)) / xp.maximum(xp.sin(th_safe), F32(1e-6))
    mag = xp.maximum(radial, tang)
    shadow = th < F32(lens.ths)
    return src.astype(F32), shadow, mag, th

def to_gal(d):
    return d @ asx(sky.RG.T, F32)

def render_sky(cam, lens=None, sky_gain=1.0, star_gain=1.0, star_size=1.0, atmo=None, shutter=None, D=None):
    """returns HDR image (H,W,3) float32 backend array of sky (MW + stars), with lensing."""
    pyr, (sdir, sflux, scol) = assets()
    W, H = cam.W, cam.H
    if D is None:
        D = cam.ray_dirs().reshape(-1, 3)
    pix_ang = 1.0 / cam.focal  # rad per px
    tex_ang = 2 * np.pi / pyr[0].shape[1]
    if lens is not None:
        src, shadow, mag, th = lens_dirs(D, lens)
    else:
        src, shadow, mag = D, None, xp.ones(len(D), F32)
    g = to_gal(src).astype(F32)
    lvl = xp.log2(xp.maximum(mag * F32(pix_ang / tex_ang), F32(1.0)))
    lvl = xp.clip(lvl, 0, len(pyr) - 1.001)
    out = xp.zeros((len(D), 3), F32)
    l0 = xp.floor(lvl).astype(xp.int32)
    for L in cpu(xp.unique(l0)).tolist():
        idx = xp.nonzero(l0 == L)[0]
        f = (lvl[idx] - L)[:, None].astype(F32)
        a = sample_equirect(pyr[L], g[idx])
        b = sample_equirect(pyr[min(L + 1, len(pyr) - 1)], g[idx])
        out[idx] = a * (1 - f) + b * f
    out *= F32(sky_gain)
    if lens is not None:
        x = (th - F32(lens.ths)) / F32(lens.ths * 0.035 + 1.5 * pix_ang)
        ring = xp.exp(-xp.maximum(x, 0) ** 2 * F32(0.8)) * (x > 0)
        out *= (1 - shadow[:, None])
        out += ring[:, None] * asx(np.array([1.0, 0.9, 0.8], F32) * F32(0.010 * sky_gain))
        out[shadow] = 0
    if atmo is not None:
        trans, glow = atmo(D)
        out = out * trans[:, None] + glow
    img = out.reshape(H, W, 3)
    # stars
    acc = xp.zeros((3, H + 4, W + 4), F32)
    cf = asx(cam.f, F32)
    if lens is None:
        vis = (sdir @ cf) > F32(math.cos(math.radians(75)))
        sd = sdir[vis]; sf = sflux[vis] ** F32(0.68) * F32(star_gain); sc = scol[vis]
        _splat_dirs(cam, acc, sd, sf, sc, shutter)
    else:
        sd = sdir; sf = sflux ** F32(0.68) * F32(star_gain); sc = scol
        n = asx(lens.n, F32)
        c = xp.clip(sd @ n, -1, 1)
        beta = xp.arccos(c)
        e = sd - c[:, None] * n[None]
        e /= xp.maximum(xp.sqrt((e * e).sum(1, keepdims=True)), F32(1e-9))
        tE = F32(lens.thE)
        u = xp.maximum(beta / tE, F32(1e-4))
        sq = xp.sqrt(beta ** 2 + 4 * tE ** 2)
        thp = (beta + sq) / 2; thm = (beta - sq) / 2
        base = (u ** 2 + 2) / (2 * u * xp.sqrt(u ** 2 + 4))
        for thi, mu in ((thp, base + 0.5), (thm, base - 0.5)):
            mu = xp.minimum(mu, F32(60.0))
            d = xp.cos(thi)[:, None] * n[None] + xp.sin(thi)[:, None] * e
            ok = (xp.abs(thi) > F32(lens.ths * 1.02)) & ((d @ cf) > F32(math.cos(math.radians(80)))) & (mu * sf > F32(2e-5))
            okn = xp.nonzero(ok)[0]
            if len(okn) == 0:
                continue
            dd = d[okn]; ff = (sf * mu)[okn]; cc = sc[okn]; ti = thi[okn]
            stretch = xp.abs(ti) / xp.maximum(beta[okn], F32(1e-6))
            sin_t = xp.maximum(xp.abs(xp.sin(ti)), F32(1e-6))
            phi = xp.minimum(F32(1.2 * pix_ang) * stretch / sin_t, F32(math.pi))
            nseg = xp.clip((phi / (F32(pix_ang) / sin_t) * F32(1.6)).astype(xp.int64), 1, 900)
            big = nseg > 1
            small = xp.nonzero(~big)[0]
            if len(small):
                _splat_dirs(cam, acc, dd[small], ff[small], cc[small], shutter)
            bigi = xp.nonzero(big)[0]
            if len(bigi):
                db, fb, cb, pb, nb = dd[bigi], ff[bigi], cc[bigi], phi[bigi], nseg[bigi]
                ends = xp.cumsum(nb)
                total = int(ends[-1])
                rep = xp.searchsorted(ends, xp.arange(total), side="right")
                starts = ends - nb
                k = (xp.arange(len(rep)) - starts[rep]).astype(F32)
                nbr = nb[rep].astype(F32)
                tpar = (k + F32(0.5)) / nbr * 2 - 1
                ang = tpar * pb[rep]
                w = xp.sqrt(xp.maximum(1 - tpar ** 2, 0)) * F32(1.2732)
                v = db[rep]
                ca = xp.cos(ang)[:, None]; sa = xp.sin(ang)[:, None]
                nn = n[None]
                vr = v * ca + xp.cross(nn, v) * sa + nn * (v @ n)[:, None] * (1 - ca)
                _splat_dirs(cam, acc, vr.astype(F32), fb[rep] * w / nbr, cb[rep], shutter)
    stars = xp.ascontiguousarray(acc[:, 2:-2, 2:-2].transpose(1, 2, 0))
    if atmo is not None:
        stars *= trans.reshape(H, W, 1)
    if lens is not None:
        stars[shadow.reshape(H, W)] = 0
    s1 = gblur(stars, 0.55 * star_size)
    halo = _blur_small(stars, 3.0 * star_size) * F32(0.10) + _blur_small(stars, 14 * star_size) * F32(0.025)
    return img + s1 + halo

_KCACHE = {}
def _gk(sigma):
    key = round(float(sigma), 4)
    if key not in _KCACHE:
        r = max(1, int(4 * sigma + 0.5))
        x = np.arange(-r, r + 1, dtype=F32)
        k = np.exp(-0.5 * (x / sigma) ** 2); k /= k.sum()
        _KCACHE[key] = asx(k.astype(F32))
    return _KCACHE[key]

def gblur(x, sigma):
    """separable gaussian over the two image axes of (H,W,C)."""
    if sigma <= 0:
        return x
    k = _gk(sigma)
    y = ndi.correlate1d(x, k, axis=0, mode="nearest")
    return ndi.correlate1d(y, k, axis=1, mode="nearest")

def upsample(s, f, H, W):
    """bilinear upsample of (h,w,C) by integer factor f to (H,W,C) (pixel-center aligned)."""
    h, w = s.shape[:2]
    def axis_w(n_out, n_in):
        pos = (xp.arange(n_out, dtype=F32) + F32(0.5)) / F32(f) - F32(0.5)
        i0 = xp.floor(pos); t = (pos - i0).astype(F32)
        i0 = i0.astype(xp.int32)
        return xp.clip(i0, 0, n_in - 1), xp.clip(i0 + 1, 0, n_in - 1), t
    y0, y1, ty = axis_w(H, h)
    x0, x1, tx = axis_w(W, w)
    rows = s[y0] * (1 - ty)[:, None, None] + s[y1] * ty[:, None, None]
    return rows[:, x0] * (1 - tx)[None, :, None] + rows[:, x1] * tx[None, :, None]

def _blur_small(x, sigma):
    f = 4 if sigma > 6 else 2
    h, w, C = x.shape
    s = x[: h // f * f, : w // f * f].reshape(h // f, f, w // f, f, C).mean((1, 3))
    s = gblur(s, sigma / f)
    return upsample(s, f, h, w)

def _splat_dirs(cam, acc, d, f, c, shutter=None):
    """bilinear splat of star images into acc (3,H+4,W+4)."""
    cams = shutter if shutter else [cam]
    wgt = F32(1.0 / len(cams))
    Hh, Ww = acc.shape[1:]
    for cm in cams:
        px, py, z = cm.project_dir(d)
        ok = xp.nonzero((z > 0.05) & (px > -1) & (py > -1) & (px < cm.W + 1) & (py < cm.H + 1))[0]
        if len(ok) == 0:
            continue
        x = px[ok] + F32(1.5); y = py[ok] + F32(1.5)
        x0f = xp.floor(x); y0f = xp.floor(y)
        fx = x - x0f; fy = y - y0f
        x0 = x0f.astype(xp.int64); y0 = y0f.astype(xp.int64)
        val = (f[ok] * wgt)[:, None] * c[ok]
        lin = xp.concatenate([xp.clip(y0 + dy, 0, Hh - 1) * Ww + xp.clip(x0 + dx, 0, Ww - 1)
                              for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1))])
        wv = xp.concatenate([(1 - fx) * (1 - fy), fx * (1 - fy), (1 - fx) * fy, fx * fy])
        for ch in range(3):
            acc[ch] += xp.bincount(lin, weights=xp.tile(val[:, ch], 4) * wv, minlength=Hh * Ww).astype(F32).reshape(Hh, Ww)

def bloom(img, amount=0.06):
    b1 = _blur_small(img, 6); b2 = _blur_small(img, 30)
    return img + F32(amount) * b1 + F32(amount * 0.6) * b2

def tonemap(img, exposure=1.0):
    x = img * F32(exposure)
    a, b, c, d, e = 2.51, 0.03, 2.43, 0.59, 0.14
    return xp.clip((x * (a * x + b)) / (x * (c * x + d) + e), 0, 1)

def finish(img, frame, exposure=1.0, vignette=0.35, grain=0.012, fade=1.0):
    """HDR backend image -> uint8 numpy (H,W,3)."""
    H, W = img.shape[:2]
    y = tonemap(img, exposure)
    xx = xp.arange(W, dtype=F32)[None, :]; yy = xp.arange(H, dtype=F32)[:, None]
    r2 = ((xx - W / 2) / (W / 2)) ** 2 * F32(0.75) + ((yy - H / 2) / (H / 2)) ** 2 * F32(0.75)
    y *= (1 - F32(vignette) * xp.clip(r2, 0, 1.5) ** F32(1.3))[..., None]
    y = xp.power(xp.clip(y, 0, 1), F32(1 / 2.2))
    rs = xp.random.RandomState(frame * 7919 + 13)
    gr = rs.standard_normal((H // 2, W // 2)).astype(F32)
    gr = xp.repeat(xp.repeat(gr, 2, 0), 2, 1)[:H, :W]
    y = y + F32(grain) * gr[..., None] * (F32(0.4) + F32(0.6) * xp.sqrt(xp.clip(y, 0, 1)))
    y *= F32(fade)
    y = y + (rs.random_sample((H, W, 1)).astype(F32) - F32(0.5)) / F32(255)
    return cpu((xp.clip(y, 0, 1) * 255 + 0.5).astype(xp.uint8))
