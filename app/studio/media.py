"""Audio/video helpers for the app: beats, captions, final audio mix (ducking + loudness), exports."""
import json, os, shutil, subprocess
from pathlib import Path
import numpy as np

from .core_paths import TOOLS  # noqa: F401  (adds tools to sys.path)
import vz_analysis as va

NOWIN = va.NOWIN
SR = 48000


def ff():
    return va.ffmpeg_exe()


def run(cmd):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       creationflags=NOWIN)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg: " + r.stderr[-800:])
    return r


# ------------------------------------------------------------------ beats
def video_frames(path):
    """The real number of video frames in a file (a fast stream copy, nothing is decoded), or None.
    Judging a render by this is reliable; the 'fps' printed in a file's header is an average that
    can be slightly off for a perfectly good file made of several pieces."""
    try:
        r = subprocess.run([ff(), "-hide_banner", "-nostdin", "-i", str(path), "-map", "0:v:0", "-c", "copy",
                            "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           creationflags=NOWIN, timeout=300)
        import re
        n = re.findall(r"frame=\s*(\d+)", r.stderr)
        if n:
            return int(n[-1])
        # some ffmpeg builds print no frame counter for a stream copy: count the packets instead
        r = subprocess.run([ff(), "-hide_banner", "-nostdin", "-v", "error", "-i", str(path), "-map", "0:v:0",
                            "-c", "copy", "-f", "framecrc", "-"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", creationflags=NOWIN, timeout=300)
        k = sum(1 for ln in r.stdout.splitlines() if ln and not ln.startswith("#"))
        return k or None
    except Exception:
        return None


def detect_beats(path):
    """tempo + beat times + downbeats + energy sections (numpy only). Good for steady music."""
    sr, hop, n = 22050, 512, 2048
    x = va.decode_audio(path, sr)
    if len(x) < sr * 2:
        return {"bpm": None, "beats": [], "downbeats": [], "sections": []}
    win = np.hanning(n).astype(np.float32)
    frames = 1 + (len(x) - n) // hop
    idx = np.arange(n)[None, :] + hop * np.arange(frames)[:, None]
    S = np.abs(np.fft.rfft(x[idx] * win, axis=1))
    S = np.log1p(10 * S)
    flux = np.maximum(0, np.diff(S, axis=0)).sum(1)
    flux = np.r_[0, flux]
    flux = flux - np.convolve(flux, np.ones(16) / 16, mode="same")
    flux = np.maximum(flux, 0)
    fps = sr / hop
    t_of = lambda f: (f * hop + n / 2) / sr          # frame index -> seconds (window centre)
    ac = np.correlate(flux, flux, mode="full")[len(flux) - 1:]
    lo, hi = int(fps * 60 / 180), int(fps * 60 / 70)
    w = np.exp(-0.5 * (np.log2(np.arange(lo, hi) / (fps * 60 / 120)) / 0.9) ** 2)  # prefer ~120 bpm
    k0 = lo + int(np.argmax(ac[lo:hi] * w))
    y0, y1, y2 = ac[k0 - 1], ac[k0], ac[k0 + 1]
    period = k0 + 0.5 * (y0 - y2) / (y0 - 2 * y1 + y2 + 1e-12)   # fractional period (parabolic peak)
    bpm = 60 * fps / period
    # phase: comb over the first ~8 beats, then track beat by beat (follows small drifts)
    span = int(period * 8)
    scores = [sum(flux[int(round(p + j * period))] for j in range(8) if int(round(p + j * period)) < len(flux))
              for p in range(int(period))]
    b = float(int(np.argmax(scores)))
    beats = []
    while b < len(flux):
        a_, z_ = max(0, int(b - period * 0.15)), min(len(flux), int(b + period * 0.15) + 1)
        seg = flux[a_:z_] * np.exp(-0.5 * ((np.arange(a_, z_) - b) / (period * 0.08)) ** 2)
        f = a_ + int(np.argmax(seg)) if seg.size and seg.max() > 0 else int(round(b))
        beats.append(t_of(f))
        b = (f if seg.size and seg.max() > 0 else b) + period
    # downbeats: strongest of the 4 phases
    st = [sum(flux[min(len(flux) - 1, int(round((b * sr - n / 2) / hop)))] for b in beats[j::4]) for j in range(4)]
    j = int(np.argmax(st)) if beats else 0
    down = beats[j::4]
    # sections: novelty of 2 s energy
    rms = np.sqrt(np.convolve(x ** 2, np.ones(sr // 10) / (sr // 10), mode="same")[::sr // 10] + 1e-12)
    db = 20 * np.log10(rms)
    sm = np.convolve(db, np.ones(20) / 20, mode="same")
    nov = np.abs(sm[20:] - sm[:-20])
    secs = []
    for i in np.argsort(-nov):
        t = (i + 10) / 10
        if nov[i] < 4 or len(secs) >= 8:
            break
        if all(abs(t - s) > 6 for s in secs):
            secs.append(t)
    secs.sort()
    snap = lambda t: min(down, key=lambda d: abs(d - t)) if down else t
    return {"bpm": round(bpm, 1), "beats": [round(b, 3) for b in beats], "downbeats": [round(b, 3) for b in down],
            "sections": [round(snap(s), 3) for s in secs], "duration": round(len(x) / sr, 3)}


def write_beats(info, path):
    L = [f"# music: {info.get('bpm')} BPM, {len(info['beats'])} beats, duration {info.get('duration')} s",
         f"# section changes (energy jumps, snapped to downbeats): {', '.join(map(str, info['sections'])) or 'none'}",
         "# time\tdownbeat"]
    ds = set(info["downbeats"])
    L += [f"{b:.3f}\t{1 if b in ds else 0}" for b in info["beats"]]
    Path(path).write_text("\n".join(L) + "\n", encoding="utf-8")


# ------------------------------------------------------------------ captions
def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def make_srt(words, path, max_chars=32, max_dur=2.6, gap=0.6):
    cues, cur = [], []
    for w in words:
        s, e, txt = w
        if cur and (len(" ".join(x[2] for x in cur + [w])) > max_chars or e - cur[0][0] > max_dur or s - cur[-1][1] > gap
                    or cur[-1][2].rstrip()[-1:] in ".!?…"):
            cues.append(cur); cur = []
        cur.append(w)
    if cur:
        cues.append(cur)
    out = []
    for k, c in enumerate(cues, 1):
        end = c[-1][1] + 0.08
        if k < len(cues):
            end = min(end, cues[k][0][0] - 0.01)
        out += [str(k), f"{srt_time(c[0][0])} --> {srt_time(end)}", " ".join(x[2] for x in c), ""]
    Path(path).write_text("\n".join(out), encoding="utf-8")
    return len(cues)


# ------------------------------------------------------------------ final mix
def load48(path, n=None):
    a = va.decode_audio(path, SR, mono=False).astype(np.float32)
    if n is not None:
        a = a[:n] if len(a) >= n else np.vstack([a, np.zeros((n - len(a), 2), np.float32)])
    return a


def envelope(points, n, default=0.0):
    """[(t, dB), ...] -> per-sample linear gain"""
    if not points:
        return np.full(n, 10 ** (default / 20), np.float32)
    ts = np.array([p[0] for p in points], float); db = np.array([p[1] for p in points], float)
    return (10 ** (np.interp(np.arange(n) / SR, ts, db) / 20)).astype(np.float32)


def duck_gain(voice, depth_db, attack=0.08, release=0.45):
    """music gain that dips by depth_db while the voice speaks (smooth sidechain)."""
    m = np.abs(voice).mean(1)
    hop = SR // 100
    k = len(m) // hop
    r = np.sqrt((m[:k * hop].reshape(k, hop) ** 2).mean(1) + 1e-12)
    db = 20 * np.log10(r)
    active = (db > db.max() - 30).astype(float)
    g = np.zeros_like(active)
    a_c, r_c = np.exp(-1 / (attack * 100)), np.exp(-1 / (release * 100))
    for i in range(len(active)):
        prev = g[i - 1] if i else 0
        c = a_c if active[i] > prev else r_c
        g[i] = c * prev + (1 - c) * active[i]
    gain_db = -depth_db * g
    full = np.interp(np.arange(len(voice)) / hop, np.arange(len(gain_db)), gain_db)
    return (10 ** (full / 20)).astype(np.float32)


def build_audio(wd, order, narration, music, duration, out_wav, preview=False, bed_out=None):
    """mixes Claude's mix.wav (SFX/ambient) with the user's narration/music according to the order."""
    from scipy.io import wavfile
    n = int(round(duration * SR))
    exp = order["audio"]["export"]
    if preview and narration:          # previews always carry the voice so sync can be judged
        exp = {"sfx": "voice_sfx", "music_sfx": "voice_music_sfx", "silent": "voice_sfx"}.get(exp, exp)
    meta = {}
    mj = Path(wd) / "mix.json"
    if mj.exists():
        try:
            meta = json.loads(mj.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
    sfx = load48(Path(wd) / "mix.wav", n) if (Path(wd) / "mix.wav").exists() else np.zeros((n, 2), np.float32)
    if exp == "silent":
        out = np.zeros((n, 2), np.float32)
    else:
        out = sfx * envelope(meta.get("sfx_gain_db"), n)[:, None]
        v = None
        if "voice" in exp and narration:
            v = load48(narration, n) * envelope(meta.get("voice_gain_db"), n)[:, None]
            out = out + v
        if "music" in exp and music:
            mus = load48(music, n)
            fade = int(min(2.0, duration / 4) * SR)
            mus[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)[:, None]
            g = envelope(meta.get("music_gain_db"), n, default=float(meta.get("music_db", -4)))
            if v is not None:
                g = g * duck_gain(v, float(order["audio"].get("duck_db", 10)))
            out = out + mus * g[:, None]
        if bed_out:  # everything except the voice, before normalization (for voice-vs-bed analysis)
            wavfile.write(bed_out, SR, (out - v if v is not None else out).astype(np.float32))
    tmp = Path(out_wav).with_suffix(".raw.wav")
    wavfile.write(tmp, SR, out.astype(np.float32))
    target = str(order["audio"].get("loudness", "keep"))
    if exp != "silent" and target != "keep" and np.abs(out).max() > 1e-5:
        st = va.ebur128([tmp])
        gain = float(target) - (st["lufs"] or float(target))
        run([ff(), "-v", "error", "-y", "-i", tmp, "-af", f"volume={gain:.2f}dB,alimiter=limit=0.89:level=false",
             "-ar", SR, "-c:a", "pcm_s16le", out_wav])
    else:
        peak = float(np.abs(out).max())
        if peak > 0.99:
            out = out * (0.97 / peak)
        wavfile.write(out_wav, SR, (np.clip(out, -1, 1) * 32767).astype(np.int16))
    tmp.unlink(missing_ok=True)
    return exp


# ------------------------------------------------------------------ exports
def export_all(master, audio_wav, order, alpha, base_name, outdir, log, on_fmt=None):
    """master (mp4 H.264 or mov ProRes 4444) + final audio -> every requested format. Returns paths."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    silent = order["audio"]["export"] == "silent"
    A = [] if silent else ["-i", str(audio_wav)]
    amap = [] if silent else ["-map", "1:a"]
    fps = order["fps"]
    res = []
    flat = (["-filter_complex", "color=black:s={s}:r={r}[bg];[bg][0:v]overlay=shortest=1,format=yuv420p[v]",
             "-map", "[v]"] if alpha else ["-map", "0:v"])
    size = va.media_info(master)
    s = f"{size['width']}x{size['height']}"
    if alpha:
        flat[1] = flat[1].format(s=s, r=fps)

    def out(ext, tag=""):
        p = outdir / f"{base_name}{tag}.{ext}"
        if p.exists():
            (outdir / "old").mkdir(exist_ok=True)
            shutil.move(str(p), str(outdir / "old" / p.name.replace(f".{ext}", f"__{int(p.stat().st_mtime)}.{ext}")))
        return p
    for fi, f in enumerate(order["formats"]):
        if on_fmt:
            on_fmt(fi, len(order["formats"]), f)
        if f == "mp4_h264":
            p = out("mp4")
            vc = ["-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p"] if alpha or master.suffix == ".mov" else ["-c:v", "copy"]
            run([ff(), "-v", "error", "-y", "-i", master, *A, *flat, *amap, *vc, "-c:a", "aac", "-b:a", "256k",
                 "-movflags", "+faststart", "-shortest", p])
        elif f == "mp4_hevc":
            p = out("mp4", "__hevc")
            run([ff(), "-v", "error", "-y", "-i", master, *A, *flat, *amap, "-c:v", "libx265", "-crf", "20", "-preset",
                 "medium", "-tag:v", "hvc1", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-movflags",
                 "+faststart", "-shortest", p])
        elif f == "mov_prores":
            p = out("mov")
            vc = ["-c:v", "copy"] if master.suffix == ".mov" else ["-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le"]
            run([ff(), "-v", "error", "-y", "-i", master, *A, "-map", "0:v", *amap, *vc, "-c:a", "pcm_s16le", "-shortest", p])
        elif f == "webm":
            p = out("webm")
            pf = "yuva420p" if alpha else "yuv420p"
            run([ff(), "-v", "error", "-y", "-i", master, *A, "-map", "0:v", *amap, "-c:v", "libvpx-vp9", "-crf", "30",
                 "-b:v", "0", "-pix_fmt", pf, "-row-mt", "1", "-deadline", "good", "-cpu-used", "4",
                 "-c:a", "libopus", "-b:a", "160k", "-shortest", p])
        elif f == "gif":
            p = out("gif")
            gf = min(15, fps)
            gw = min(800, size["width"])
            run([ff(), "-v", "error", "-y", "-i", master, "-filter_complex",
                 f"fps={gf},scale={gw}:-2:flags=lanczos,split[a][b];[a]palettegen=reserve_transparent={1 if alpha else 0}"
                 f"[p];[b][p]paletteuse=dither=sierra2_4a", p])
        elif f == "png_seq":
            p = outdir / f"{base_name}__png"
            if p.exists():
                shutil.rmtree(p)
            p.mkdir()
            run([ff(), "-v", "error", "-y", "-i", master, "-pix_fmt", "rgba" if alpha else "rgb24",
                 str(p / "frame_%05d.png")])
        else:
            continue
        res.append(p)
        log(f"   exported {p.name}")
    return res
