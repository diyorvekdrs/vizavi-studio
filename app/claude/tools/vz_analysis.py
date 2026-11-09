"""Shared analysis helpers for Vizavi Studio (app side) and tools/sandbox_check.py (Claude side).
Standalone: numpy + Pillow + an ffmpeg binary (PATH or imageio-ffmpeg)."""
import json, math, os, re, shutil, subprocess
from pathlib import Path
import numpy as np

NOWIN = 0x08000000 if os.name == "nt" else 0
HERE = Path(__file__).resolve().parent


def ffmpeg_exe():
    p = shutil.which("ffmpeg")
    if p:
        return p
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        raise SystemExit("ffmpeg not found (pip install imageio-ffmpeg)")


def font_path(name="DejaVuSans.ttf"):
    for d in (HERE.parent / "fonts", HERE.parent.parent / "fonts", Path.cwd() / "fonts"):
        if (d / name).exists():
            return str(d / name)
    return None


def load_font(size, name="DejaVuSans.ttf"):
    from PIL import ImageFont
    p = font_path(name)
    try:
        return ImageFont.truetype(p, size) if p else ImageFont.load_default(size)
    except Exception:
        return ImageFont.load_default()


# ------------------------------------------------------------------ media
def media_info(path):
    """duration (s), width, height, fps, has_audio, has_video from `ffmpeg -i` banner."""
    r = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", str(path)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", creationflags=NOWIN)
    s = r.stderr
    info = {"duration": None, "width": None, "height": None, "fps": None,
            "has_audio": " Audio:" in s, "has_video": " Video:" in s}
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", s)
    if m:
        info["duration"] = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
    m = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", s)
    if m:
        info["width"], info["height"] = int(m[1]), int(m[2])
    m = re.search(r"([\d.]+) fps", s)
    if m:
        info["fps"] = float(m[1])
    return info


def decode_audio(path, sr=16000, mono=True):
    cmd = [ffmpeg_exe(), "-v", "error", "-i", str(path), "-ac", "1" if mono else "2", "-ar", str(sr),
           "-f", "f32le", "-"]
    r = subprocess.run(cmd, capture_output=True, creationflags=NOWIN)
    if r.returncode != 0:
        raise RuntimeError("audio decode failed: " + r.stderr.decode(errors="replace")[-400:])
    a = np.frombuffer(r.stdout, np.float32)
    return a if mono else a.reshape(-1, 2)


def ebur128(inputs, filt=None):
    """Integrated loudness (LUFS) and true peak (dBTP). inputs: list of paths; filt: optional
    filter_complex producing [a] from the inputs (e.g. a mix)."""
    cmd = [ffmpeg_exe(), "-hide_banner", "-nostats"]
    for p in inputs:
        cmd += ["-i", str(p)]
    if filt:
        cmd += ["-filter_complex", filt + ";[a]ebur128=peak=true[o]", "-map", "[o]"]
    else:
        cmd += ["-af", "ebur128=peak=true"]
    cmd += ["-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=NOWIN)
    s = r.stderr[r.stderr.rfind("Summary:"):] if "Summary:" in r.stderr else r.stderr
    I = re.search(r"I:\s*(-?[\d.]+|-inf)\s*LUFS", s)
    P = re.search(r"Peak:\s*(-?[\d.]+|-inf)\s*dBFS", s)
    f = lambda m: (float(m[1]) if m and m[1] != "-inf" else None)
    return {"lufs": f(I), "true_peak": f(P)}


def rms_db(a, sr, win=0.1):
    n = int(sr * win)
    k = len(a) // n
    if k == 0:
        return np.array([-90.0])
    x = a[:k * n].reshape(k, n)
    return np.maximum(-90.0, 20 * np.log10(np.sqrt((x.astype(np.float64) ** 2).mean(1)) + 1e-9))


# ------------------------------------------------------------------ words / scenes
def load_words(path):
    """words.tsv (start<TAB>end<TAB>word) -> list of (s, e, w)."""
    out = []
    p = Path(path)
    if not p.exists():
        return out
    for ln in p.read_text(encoding="utf-8").splitlines():
        parts = ln.split("\t")
        if len(parts) >= 3 and parts[0][:1].isdigit():
            try:
                out.append((float(parts[0]), float(parts[1]), parts[2]))
            except ValueError:
                pass
    return out


def word_at(words, t):
    """index of the word spoken at t (or last finished word), and whether it is being spoken."""
    if not words:
        return -1, False
    starts = [w[0] for w in words]
    i = int(np.searchsorted(starts, t, side="right")) - 1
    if i < 0:
        return -1, False
    return i, t <= words[i][1] + 0.05


def scene_at(scenes, t):
    for sc in scenes or []:
        try:
            if sc[1] <= t < sc[2]:
                return str(sc[0])
        except Exception:
            pass
    return ""


# ------------------------------------------------------------------ camera
def camera_check(fn, dur, fps=24, sub=4):
    """fn(t) -> 1D array. Finds velocity jumps (C1 breaks) and acceleration spikes (jerky moves)."""
    n = int(dur * fps * sub) + 1
    ts = np.linspace(0, dur, n)
    try:
        P = np.array([np.asarray(fn(float(t)), float).ravel() for t in ts])
    except Exception as e:
        return {"ok": None, "error": f"camera_state failed: {e}"}
    dt = ts[1] - ts[0]
    v = np.diff(P, axis=0) / dt
    a = np.diff(v, axis=0) / dt
    sp = np.linalg.norm(v, axis=1)
    ac = np.linalg.norm(a, axis=1)
    ref_v = np.percentile(sp, 90) + 1e-9
    ref_a = max(np.percentile(ac, 75), 0.1 * ref_v) + 1e-9
    issues = []
    jv = np.linalg.norm(np.diff(v, axis=0), axis=1)  # per-step velocity change
    thr_jump = max(0.15 * ref_v, 1e-6)
    for i in np.where(jv > thr_jump)[0]:
        issues.append((round(float(ts[i + 1]), 2), "velocity jump (camera snaps / not C1)"))
    spikes = np.where(ac > 12 * ref_a)[0]
    for i in spikes:
        issues.append((round(float(ts[i + 1]), 2), "acceleration spike (abrupt start/stop)"))
    # merge neighbours
    merged = []
    for t, kind in sorted(issues):
        if merged and t - merged[-1][0] < 0.3 and merged[-1][1] == kind:
            continue
        merged.append((t, kind))
    return {"ok": not merged, "issues": merged[:20], "max_speed": float(sp.max()),
            "p90_speed": float(ref_v)}


# ------------------------------------------------------------------ video analysis
def analyze_video(path, fps=24, scenes=None):
    """Decodes at 160x90 gray. Returns flags for pops/jumps, black, blown, flicker, static spans."""
    cmd = [ffmpeg_exe(), "-v", "error", "-i", str(path), "-vf", "scale=160:90,format=gray", "-f", "rawvideo", "-"]
    r = subprocess.run(cmd, capture_output=True, creationflags=NOWIN)
    F = np.frombuffer(r.stdout, np.uint8)
    n = F.size // (160 * 90)
    F = F[:n * 160 * 90].reshape(n, 90, 160).astype(np.float32)
    res = {"frames": n, "flags": []}
    if n < 3:
        res["flags"].append("video has <3 frames")
        return res
    D = np.abs(np.diff(F, axis=0))
    d = D.mean((1, 2))                       # d[i] = change from frame i to i+1
    area = (D > 10).mean((1, 2))             # share of the frame that changed clearly
    del D
    luma = F.mean((1, 2))
    clip = (F >= 250).mean((1, 2))
    bounds = sorted({int(round(sc[1] * fps)) for sc in (scenes or []) if sc[1] > 0})
    near_b = lambda i: any(abs(i + 1 - b) <= 2 for b in bounds)
    T = lambda i: f"{i / fps:.2f}s"
    # pops / jumps
    pops = []
    for i in range(len(d)):
        lo, hi = max(0, i - 12), min(len(d), i + 13)
        loc = np.median(np.r_[d[lo:i], d[i + 1:hi]]) if hi - lo > 1 else 0
        nb = max(d[i - 2] if i > 1 else 0, d[i + 2] if i + 2 < len(d) else 0)   # skip the twin spike of a bad frame
        if d[i] > max(5.0, 5 * loc) and d[i] > 2.5 * nb and area[i] > 0.2 and not near_b(i):
            # one-frame spike over a large area = glitch / unplanned cut (caption or small text changes are fine)
            pops.append(i + 1)
    for f in _merge(pops):
        res["flags"].append(f"sudden jump/pop at {T(f)} (frame {f}) - not at a scene boundary")
    res["boundaries"] = [{"frame": b, "t": round(b / fps, 2),
                          "change": round(float(d[b - 1]), 2) if 0 < b <= len(d) else None,
                          "type": ("hard cut" if 0 < b <= len(d) and d[b - 1] > 8 else "smooth")} for b in bounds]
    # black / blown / static
    for name, mask, minlen in (("near-black", luma < 3.0, 12), ("blown-out (>20% clipped)", clip > 0.2, 6),
                               ("static (no visible motion)", np.r_[d < 0.03, False], 48)):
        for a, b in _runs(mask, minlen):
            res["flags"].append(f"{name} {T(a)}-{T(b)} ({(b - a) / fps:.1f}s)")
    # flicker: alternating brightness
    if n > 12:
        k = 9
        ma = np.convolve(luma, np.ones(k) / k, mode="same")
        hp = luma - ma
        sig = (np.abs(hp) > 1.2) * np.sign(hp)
        alt = np.r_[0, (sig[1:] * sig[:-1] < 0).astype(int)]
        cnt = np.convolve(alt, np.ones(12), mode="same")
        for a, b in _runs(cnt >= 6, 6):
            res["flags"].append(f"brightness flicker {T(a)}-{T(b)}")
    res["mean_luma"] = round(float(luma.mean()), 1)
    res["motion_p50"] = round(float(np.median(d)), 3)
    res["_luma"] = luma
    res["_diff"] = d
    return res


def _merge(idx, gap=3):
    out = []
    for i in idx:
        if not out or i - out[-1] > gap:
            out.append(i)
    return out


def _runs(mask, minlen):
    out, start = [], None
    for i, m in enumerate(list(mask) + [False]):
        if m and start is None:
            start = i
        elif not m and start is not None:
            if i - start >= minlen:
                out.append((start, i))
            start = None
    return out


# ------------------------------------------------------------------ audio analysis + plot
def analyze_audio(mix, narration=None, video_dur=None, words=None, scenes=None, plot_path=None):
    res = {"flags": []}
    m = decode_audio(mix, 16000)
    res["mix_duration"] = round(len(m) / 16000, 3)
    if video_dur and abs(len(m) / 16000 - video_dur) > 1 / 24 + 0.01:
        res["flags"].append(f"mix.wav length {len(m) / 16000:.3f}s != video {video_dur:.3f}s")
    st = ebur128([mix])
    res["mix_lufs"], res["mix_true_peak"] = st["lufs"], st["true_peak"]
    if st["true_peak"] is not None and st["true_peak"] > -1.0:
        res["flags"].append(f"mix true peak {st['true_peak']} dBTP > -1 (risk of clipping)")
    md = rms_db(m, 16000)
    nd = None
    if narration and Path(narration).exists():
        nv = decode_audio(narration, 16000)
        res["narration_duration"] = round(len(nv) / 16000, 3)
        if video_dur and len(nv) / 16000 > video_dur + 0.05:
            res["flags"].append(f"video ({video_dur:.2f}s) is shorter than narration ({len(nv) / 16000:.2f}s)")
        sn = ebur128([narration])
        res["narration_lufs"] = sn["lufs"]
        both = ebur128([mix, narration], "[0:a][1:a]amix=inputs=2:duration=first:normalize=0[a]")
        res["combined_lufs"], res["combined_true_peak"] = both["lufs"], both["true_peak"]
        nd = rms_db(nv, 16000)
        L = min(len(nd), len(md))
        speech = nd[:L] > (nd.max() - 25)
        if speech.any():
            gap = float(np.median(nd[:L][speech] - md[:L][speech]))
            res["voice_over_bed_db"] = round(gap, 1)
            if gap < 10:
                res["flags"].append(f"bed/SFX only {gap:.1f} dB under the voice while speaking (want >= 12 dB)")
        loud = np.where(md[:L] > nd[:L] - 3)[0] if L else []
        loud = [i for i in loud if speech[i]]
        for a in _merge(loud, 5)[:8]:
            res["flags"].append(f"SFX as loud as voice at {a * 0.1:.1f}s (masks narration)")
    if plot_path:
        _plot(plot_path, md, nd, words, scenes)
    return res


def _plot(path, md, nd, words, scenes, W=1600, H=380):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H), (14, 15, 18))
    g = ImageDraw.Draw(img)
    f = load_font(13)
    n = max(len(md), len(nd) if nd is not None else 0)
    dur = n * 0.1
    X = lambda t: 40 + (W - 60) * t / max(dur, 1e-6)
    Y = lambda db: 20 + (H - 80) * (0 - max(-70, min(0, db))) / 70
    for db in (-10, -20, -30, -40, -50, -60):
        g.line([(40, Y(db)), (W - 20, Y(db))], fill=(32, 34, 40))
        g.text((4, Y(db) - 7), f"{db}", fill=(110, 110, 120), font=f)
    for sc in scenes or []:
        x = X(sc[1])
        g.line([(x, 14), (x, H - 58)], fill=(70, 70, 90))
        g.text((x + 3, 4), str(sc[0])[:18], fill=(150, 150, 175), font=f)
    for arr, col in ((nd, (110, 180, 255)), (md, (255, 160, 70))):
        if arr is None:
            continue
        pts = [(X(i * 0.1), Y(v)) for i, v in enumerate(arr)]
        g.line(pts, fill=col, width=2)
    for i, (s, e, w) in enumerate(words or []):
        x = X(s)
        g.line([(x, H - 56), (x, H - 48)], fill=(160, 160, 160))
        if i % 2 == 0:
            g.text((x, H - 46), w[:12], fill=(170, 170, 170), font=f)
        else:
            g.text((x, H - 30), w[:12], fill=(130, 130, 130), font=f)
    for s in range(0, int(dur) + 1, 5):
        g.text((X(s), H - 14), f"{s}s", fill=(120, 120, 120), font=f)
    g.text((W - 330, 4), "blue = narration   orange = ambient+SFX (dB RMS)", fill=(200, 200, 200), font=f)
    img.save(path)
