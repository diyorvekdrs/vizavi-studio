"""html engine end to end: text probe + reuse of unchanged batches (skipped when Playwright/Chromium is missing)"""
import sys, os, json, shutil, subprocess, tempfile
from pathlib import Path
APPDIR = Path(os.environ.get("VZ_APP") or Path(__file__).resolve().parent.parent / "app")
fails = []
def check(n, c, x=""):
    print(("ok   " if c else "FAIL ") + n, "" if c else x)
    if not c: fails.append(n)
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        p.chromium.launch().close()
except Exception as e:
    print(f"skipped (no Playwright/Chromium: {e})\n\nFAILS: none"); sys.exit(0)

wd = Path(tempfile.mkdtemp(prefix="vz_render_"))
for f in (APPDIR / "kit").glob("*.py"):
    shutil.copy(f, wd)
shutil.copy(APPDIR / "claude" / "engines" / "vz.js", wd)
(wd / "project.json").write_text(json.dumps({"engine": "html", "width": 1080, "height": 1920, "fps": 12, "nfr": 48,
                                             "responsive": False, "scenes": [["a", 0, 4]], "cues": []}))
PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>#stage{background:#111;font-family:sans-serif}
.t{position:absolute;color:#fff;white-space:nowrap;font-size:90px}</style></head><body><div id="stage">
<div class="t" id="a" style="left:100px;top:600px">Salom dunyo</div>
<div class="t" id="b" style="left:700px;top:900px">Juda uzun sarlavha</div>
<div class="t" id="c" style="left:100px;top:1200px">LATE</div>
</div><script src="vz.js"></script><script>
VZ.onFrame(t => { document.getElementById('c').textContent = t < 2 ? 'Birinchi' : 'WORD'; });
</script></body></html>"""
(wd / "index.html").write_text(PAGE.replace("WORD", "Ikkinchi"), encoding="utf-8")
env = dict(os.environ, VZ_CHUNK_CACHE=str(wd / "cache"), WORKERS="2")
def render(out):
    r = subprocess.run([sys.executable, "vzrender.py", out, "--size", "540x960", "--textprobe", out + ".json"], cwd=wd,
                       env=env, capture_output=True, text=True)
    if r.returncode:
        print(r.stdout[-2000:], r.stderr[-2000:])
    return r.stdout
o1 = render("a.mp4")
P = json.loads((wd / "a.mp4.json").read_text(encoding="utf-8"))
check("probe written", P["supported"] and len(P["samples"]) == 16, len(P["samples"]))
texts = {i["text"] for s in P["samples"] for i in s["items"]}
check("probe sees the text", {"Salom dunyo", "Juda uzun sarlavha", "Birinchi", "Ikkinchi"} <= texts, texts)
sys.path.insert(0, str(APPDIR / "claude" / "tools"))
import vz_checks as vc
iss, _ = vc.analyze_text(P["samples"], P["W"], P["H"], P["step"])
check("off-frame headline found", any(i["kind"] == "text_off_frame" and "sarlavha" in i["text"] for i in iss), iss)
o2 = render("b.mp4")
check("second render reuses every batch", "reused 4 unchanged batch(es) of 4" in o2, o2[-500:])
check("reused video identical", (wd / "a.mp4").stat().st_size == (wd / "b.mp4").stat().st_size)
(wd / "index.html").write_text(PAGE.replace("WORD", "Uchinchi"), encoding="utf-8")
o3 = render("c.mp4")
check("only the changed seconds re-render", "reused 2 unchanged batch(es) of 4" in o3, o3[-600:])
P3 = json.loads((wd / "c.mp4.json").read_text(encoding="utf-8"))
check("probe follows the change", "Uchinchi" in {i["text"] for s in P3["samples"] for i in s["items"]})
env["VZ_NO_REUSE"] = "1"
o4 = render("d.mp4")
check("VZ_NO_REUSE renders everything", "reused" not in o4, o4[-300:])
print("\nFAILS:", fails or "none")
sys.exit(1 if fails else 0)
