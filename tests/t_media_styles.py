import sys, os, json, tempfile, shutil, subprocess, zipfile
APPDIR = os.environ.get("VZ_APP") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app")
sys.path.insert(0, APPDIR)
from pathlib import Path
from studio import core
from studio import order as OD
import vz_analysis as va
fails = []
def check(n, c, x=""):
    print(("ok   " if c else "FAIL ") + n, "" if c else x)
    if not c: fails.append(n)
class Ctx:
    cancelled = False; proc = None; logs = []
    def log(self, s): self.logs.append(s)
    def progress(self, *a, **k): pass
ctx = Ctx()
tmp = Path(tempfile.mkdtemp(prefix="vz_ms_")); core.SETTINGS = tmp / "settings.json"
S = core.load_settings(); S["projects_dir"] = str(tmp / "P"); os.makedirs(S["projects_dir"])
ff = va.ffmpeg_exe()
src = tmp / "rec.mp4"
subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1920x1080:r=25:d=12", "-f", "lavfi", "-i", "sine=d=12",
                "-pix_fmt", "yuv420p", "-c:v", "libx264", "-crf", "20", "-c:a", "aac", "-shortest", str(src)], check=True)
img = tmp / "big.png"
from PIL import Image
Image.effect_noise((3000, 2000), 64).convert("RGB").save(img)
pr = core.Project.open("clipper", S)
core.add_assets(pr, [str(src), str(img)], ctx)
man = core.asset_manifest(pr)
check("ASSETS.md lists the real sizes", "rec.mp4 | video 1920×1080" in man and "big.png | image 3000×2000" in man, man[-400:])
check("ASSETS.md explains media.json", "media.json" in man and "LIGHT COPIES" in man)
# a Claude render folder that shipped a soft 640px cut and declared the recipe
wd = pr.work / "preview_v1"; (wd / "media").mkdir(parents=True)
subprocess.run([ff, "-v", "error", "-y", "-ss", "2", "-i", str(src), "-t", "4", "-vf", "scale=640:-2", "-an", str(wd / "media" / "cut.webm")], check=True)
(wd / "media.json").write_text(json.dumps({"clips": [
    {"out": "media/cut.webm", "src": "rec.mp4", "start": 2, "duration": 4, "fps": 24, "audio": False},
    {"out": "media/crop.mp4", "src": "rec.mp4", "start": 1, "duration": 2, "crop": [0.5, 0.5, 0.5, 0.5], "audio": True},
    {"out": "media/small.webm", "src": "rec.mp4", "duration": 1, "max_width": 960},
    {"out": "../escape.webm", "src": "rec.mp4"}, {"out": "media/x.webm", "src": "missing.mp4"}]}))
made = core.build_media(pr, wd, ctx)
check("clips rebuilt", made == ["media/cut.webm", "media/crop.mp4", "media/small.webm"], made)
i1 = va.media_info(wd / "media" / "cut.webm")
check("webm at full source size", (i1["width"], i1["height"]) == (1920, 1080) and abs(i1["duration"] - 4) < 0.15 and not i1["has_audio"], i1)
check("webm fps", abs((i1["fps"] or 0) - 24) < 0.1, i1)
i2 = va.media_info(wd / "media" / "crop.mp4")
check("crop by fractions + audio kept", (i2["width"], i2["height"]) == (960, 540) and i2["has_audio"], i2)
i3 = va.media_info(wd / "media" / "small.webm")
check("max_width limits size", i3["width"] == 960, i3)
check("unsafe out ignored", not (pr.work / "escape.webm").exists() and any("unusable" in l for l in ctx.logs))
check("missing source keeps Claude's copy and says so", any("missing.mp4 is not in the project" in l for l in ctx.logs))
n_before = len(list((pr.work / "_media_cache").iterdir()))
ctx.logs.clear(); core.build_media(pr, wd, ctx)
check("second render reuses the cache", len(list((pr.work / "_media_cache").iterdir())) == n_before and not any("Making" in l for l in ctx.logs))
(wd / "media.json").write_text("{nope")
try:
    core.build_media(pr, wd, ctx); check("bad media.json -> step error", False)
except core.StepError:
    check("bad media.json -> step error", True)
(wd / "media.json").unlink()
check("no media.json -> nothing", core.build_media(pr, wd, ctx) == [])

# styles
(wd / "project.json").write_text(json.dumps({"engine": "html", "width": 1920, "height": 1080, "fps": 24, "nfr": 48}))
(wd / "main.js").write_text("// look"); (wd / "PLAN.md").write_text("plan"); (wd / "style.css").write_text("body{}")
for k in ("backend.py", "vzrender.py"): (wd / k).write_text("# kit")
(pr.src / "assets" / "Brand-Bold.otf").write_bytes(b"font")
pv = pr.output / "clipper__preview_v1.mp4"; shutil.copy2(src, pv)
pr.set("preview_ready", "ok", preview_v=1, last_preview=str(pv))
info = core.save_style(pr, "My Zoom look", "the paper map, big type", S, ctx)
sd = core.styles_dir(S) / info["id"]
code = sorted(p.relative_to(sd / "code").as_posix() for p in (sd / "code").rglob("*") if p.is_file())
check("style keeps Claude's code, not the kit", "main.js" in code and "PLAN.md" in code and "project.json" in code and "vzrender.py" not in code and "backend.py" not in code, code)
check("style stills", len(list((sd / "stills").glob("*.jpg"))) == 6)
check("style fonts", (sd / "fonts" / "Brand-Bold.otf").exists() and info["fonts"] == ["Brand-Bold.otf"])
L = core.list_styles(S)
check("listed", len(L) == 1 and L[0]["name"] == "My Zoom look" and L[0]["thumb"], L)
o = OD.normalize(OD.from_preset(list(OD.PRESETS)[0])); o["style_ref"] = info["id"]; o["style_ref_name"] = "My Zoom look"
E = core.style_entries(S, o)
names = [a for a, _ in E]
check("request gets style_ref/", names[0] == "style_ref/STYLE.md" and "style_ref/stills" in names and "style_ref/code" in names, names)
check("STYLE.md carries the note", "the paper map, big type" in E[0][1] and "Do NOT copy its content" in E[0][1])
check("brief points to the style", "style_ref/STYLE.md" in OD.brief_md(o, assets=[]))
pr2 = core.Project.open("newone", S); names2 = core.apply_style_fonts(pr2, S, o, [], ctx)
check("style fonts copied into a new project", names2 == ["Brand-Bold.otf"] and (pr2.src / "assets" / "Brand-Bold.otf").exists())
z = core.write_zip(tmp / "r.zip", E)
with zipfile.ZipFile(z) as zz:
    nm = zz.namelist()
check("zip has stills and code", any(n.startswith("style_ref/stills/") for n in nm) and "style_ref/code/main.js" in nm, nm[:8])
info2 = core.save_style(pr, "My Zoom look", "", S, ctx); check("same name replaces", len(core.list_styles(S)) == 1)
pr3 = core.Project.open("empty", S)
try:
    core.save_style(pr3, "x", "", S, ctx); check("no code -> clear message", False)
except core.UserMessage as e:
    check("no code -> clear message", "no video from Claude yet" in str(e))
core.delete_style(S, info["id"]); check("delete", core.list_styles(S) == [] and any(e["kind"] == "style" for e in core.TR.list_trash(S)))
check("projects list ignores _styles", [p.name for p in core.list_projects(S)].count("_styles") == 0)
shutil.rmtree(tmp, ignore_errors=True)
print("\nFAILS:", fails or "none")
