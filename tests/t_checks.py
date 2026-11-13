import sys, os, json, tempfile
APPDIR = os.environ.get("VZ_APP") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app")
sys.path.insert(0, APPDIR); sys.path.insert(0, os.path.join(APPDIR, "claude", "tools")); sys.path.insert(0, os.path.join(APPDIR, "kit"))
import numpy as np
import vz_checks as vc
import vzrender
fails = []
def check(n, c, x=""):
    print(("ok   " if c else "FAIL ") + n, "" if c else x)
    if not c: fails.append(n)

W, H, step = 540, 960, 0.25
def item(k, text, box, px=40, contrast=12, cap=False, clip=False):
    return {"k": k, "text": text, "box": box, "px": px, "color": [255, 255, 255], "op": 1, "cap": cap, "clip": clip,
            "contrast": contrast}
def samples(n, fn):
    return [{"t": i * step, "items": fn(i * step)} for i in range(n)]

def kinds(iss): return sorted(i["kind"] for i in iss)

# a clean frame: nothing found
iss, sm = vc.analyze_text(samples(20, lambda t: [item("a", "Salom dunyo", [60, 300, 400, 350])]), W, H, step,
                          safe=(0.10, 0.22, 0.12), vocab_text="salom dunyo")
check("clean text: nothing found", iss == [], iss)

# an entrance from off-frame for one sample is not a problem; holding off-frame is
def slide(t): return [item("a", "Salom dunyo", [600 if t < 0.25 else 60, 300, 900 if t < 0.25 else 400, 350])]
iss, _ = vc.analyze_text(samples(20, slide), W, H, step)
check("one-sample entrance ignored", iss == [], iss)
iss, _ = vc.analyze_text(samples(20, lambda t: [item("a", "Salom dunyo", [300, 300, 700, 350])]), W, H, step)
check("held off frame is P1", kinds(iss) == ["text_off_frame"] and iss[0]["rank"] == "P1", iss)

# kinetic reveal: the block grows word by word; reading time counts the whole block
words = "Bu juda muhim gap".split()
def reveal(t): return [item("r", " ".join(words[:min(4, 1 + int(t / 0.25))]), [60, 300, 400, 350])]
iss, _ = vc.analyze_text(samples(12, reveal), W, H, step)
check("growing text is one block (no 'brief' per word)", "text_brief" not in kinds(iss), iss)

# brief, small, faint, button zone, clipped, Cyrillic, misspelled
def bad(t):
    out = [item("z", "Pastda", [60, 800, 300, 850]), item("s", "kichik", [60, 200, 120, 210], px=10),
           item("f", "xira", [60, 400, 200, 440], contrast=1.4), item("c", "Kesilgan matn", [60, 500, 300, 540], clip=True),
           item("y", "Привет", [60, 600, 300, 640]), item("m", "Toshkemt", [60, 650, 300, 690])]
    if 1.0 <= t < 1.25:
        out.append(item("b", "Bu juda tez yoziladigan uzun gap", [60, 260, 480, 290]))
    return out
iss, _ = vc.analyze_text(samples(20, bad), W, H, step, safe=(0.10, 0.22, 0.12), vocab_text="Toshkent shahri", latin_only=True)
k = kinds(iss)
for want in ("text_safe_zone", "text_small", "text_contrast", "text_clipped", "text_cyrillic", "text_spelling", "text_brief"):
    check(f"finds {want}", want in k, k)
rk = {i["kind"]: i["rank"] for i in iss}
check("ranks", rk["text_safe_zone"] == "P1" and rk["text_contrast"] == "P1" and rk["text_cyrillic"] == "P1"
      and rk["text_spelling"] == "P2" and rk["text_brief"] == "P2", rk)
iss2, _ = vc.analyze_text(samples(20, bad), W, H, step, vocab_text="")
check("no Latin rule, no vocab: Cyrillic not flagged", "text_cyrillic" not in kinds(iss2))
check("captions skip the reading-time check", not vc.analyze_text(samples(20, lambda t: [item("cap", "salom dunyo qalaysan " * (1 + int(t)), [60, 300, 400, 350], cap=True)]), W, H, step)[0])

# sparse samples (sandbox stills seconds apart): one sample is enough, no reading time
sp = [{"t": 0, "items": [item("a", "x y z", [300, 300, 700, 350])]}, {"t": 4, "items": []}]
iss, _ = vc.analyze_text(sp, W, H, 4.0, min_run=1)
check("sparse samples still find off-frame", kinds(iss) == ["text_off_frame"], iss)

# ranking of the older plain-text flags
fl = ["video has 10 frames, project says 12", "sudden jump/pop at 1.00s (frame 24) - not at a scene boundary",
      "bed/SFX only 6.0 dB under the voice while speaking (want >= 12 dB)", "scene 'a' starts +0.10s off the nearest beat",
      "something new nobody ranked"]
r = vc.ranked(fl)
check("flag ranks", [i["rank"] for i in r] == ["P0", "P1", "P2", "P2", "P3"], [i["rank"] for i in r])
check("counts", vc.counts(r) == {"P0": 1, "P1": 1, "P2": 2, "P3": 1})

# contrast measuring on real pixels
img = np.zeros((100, 200, 3), np.uint8); img[:] = (30, 30, 30)
img[40:60, 20:30] = 255; img[40:60, 50:60] = 255             # "glyphs"
m = vzrender.measure([{"box": [10, 30, 100, 70], "color": [255, 255, 255]}], img)
check("white on dark: high contrast", m[0]["contrast"] > 10, m)
img2 = np.full((100, 200, 3), 250, np.uint8)
m = vzrender.measure([{"box": [10, 30, 100, 70], "color": [255, 255, 255]}], img2)
check("white on white: contrast 1", m[0]["contrast"] == 1.0, m)
m = vzrender.measure([{"box": [10, 30, 100, 70], "color": None}], img)
check("gradient text not judged", "contrast" not in m[0])

# vzfast: np.convolve of long signals via FFT - same numbers, any mode, either order
import time as _t
_np_conv = np.convolve
import vzfast
rng = np.random.default_rng(1)
sig = (rng.random(400000) > .5).astype(float); ker = np.ones(3000) / 3000
for mode in ("full", "same", "valid"):
    ref = _np_conv(sig, ker, mode); got = np.convolve(sig, ker, mode); rev = np.convolve(ker, sig, mode)
    check(f"vzfast {mode}", got.shape == ref.shape and np.allclose(got, ref, atol=1e-9)
          and rev.shape == _np_conv(ker, sig, mode).shape and np.allclose(rev, _np_conv(ker, sig, mode), atol=1e-9))
check("vzfast keeps small/int convolutions exact", np.array_equal(np.convolve([1, 2, 3], [0, 1, 0.5]), _np_conv([1, 2, 3], [0, 1, 0.5]))
      and np.convolve(np.arange(10), np.arange(5)).dtype == _np_conv(np.arange(10), np.arange(5)).dtype)
t0 = _t.time(); np.convolve(np.ones(48000 * 120), np.ones(16800) / 16800, "same"); dt = _t.time() - t0
check("vzfast: a 2-minute 48 kHz smoothing takes seconds", dt < 5, dt)
np.convolve = _np_conv

# core: the report wiring
from studio import core
tmp = tempfile.mkdtemp()
from pathlib import Path
core.SETTINGS = Path(tmp) / "settings.json"            # never touch the real settings.json
S = core.load_settings(); S["projects_dir"] = os.path.join(tmp, "P"); os.makedirs(S["projects_dir"])
pr = core.Project.open("t", S, create=True)
o = pr.order
o.update(safe_area="tiktok", care="Ekrandagi matn faqat lotin alifbosida")
(pr.src / "order.json").write_text(json.dumps(o), encoding="utf-8")
(pr.src / "script.txt").write_text("Toshkent shahri", encoding="utf-8")
opts = core.text_check_opts(pr)
check("Latin rule found in Take care of (Uzbek 'lotin')", opts["latin_only"] and tuple(opts["safe"]) == core.OD.SAFE_BOXES["tiktok"], opts)
pf = os.path.join(tmp, "text.json")
json.dump({"engine": "html", "W": W, "H": H, "step": step, "supported": True, "samples": samples(20, bad)}, open(pf, "w"))
iss, sm = core.run_text_checks(pr, pf, o)
check("core runs the text checks with the order's rules", "text_cyrillic" in kinds(iss) and "text_spelling" in kinds(iss), kinds(iss))
json.dump({"engine": "python", "W": W, "H": H, "step": step, "supported": False, "samples": []}, open(pf, "w"))
check("unsupported probe -> not checked", core.run_text_checks(pr, pf, o) == ([], None))
check("missing probe -> not checked", core.run_text_checks(pr, pf + "x", o) == ([], None))

print("\nFAILS:", fails or "none")
sys.exit(1 if fails else 0)
