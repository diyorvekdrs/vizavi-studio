import sys, os, json, tempfile, shutil, threading, zipfile, time
APPDIR = os.environ.get("VZ_APP") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app")
sys.path.insert(0, APPDIR)
from pathlib import Path
from studio import core, media
from studio.core_paths import is_inside, safe_member
from studio import order as OD
fails = []
def check(n, c, x=""):
    print(("ok   " if c else "FAIL ") + n, "" if c else x)
    if not c: fails.append(n)
tmp = Path(tempfile.mkdtemp(prefix="vz_core_"))
class Ctx:
    cancelled = False; proc = None
    def log(self, s): pass
    def progress(self, *a, **k): pass
ctx = Ctx()

# paths
check("is_inside sibling", not is_inside(tmp / "Projects2" / "x", tmp / "Projects"))
check("is_inside child", is_inside(tmp / "Projects" / "a" / "b", tmp / "Projects"))
check("is_inside dotdot", not is_inside(tmp / "Projects" / ".." / "x", tmp / "Projects"))
for bad in ("../x", "/etc/passwd", "C:/x", "a/../../b", "x:stream", "..\\y"):
    check(f"safe_member rejects {bad!r}", safe_member(bad) is None, safe_member(bad))
check("safe_member ok", safe_member("a/b.txt") == "a/b.txt")

# atomic write + bak + recovery
f = tmp / "s.json"
core.atomic_write(f, json.dumps({"a": 1}), keep_bak=True)
core.atomic_write(f, json.dumps({"a": 2}), keep_bak=True)
check("bak holds previous good", json.loads((tmp / "s.json.bak").read_text()) == {"a": 1})
f.write_text("{broken")
d, how = core.read_json_safe(f)
check("broken main -> restored from bak", how == "bak" and d == {"a": 1}, (d, how))
(tmp / "s.json.bak").write_text("nope")
check("both broken -> broken", core.read_json_safe(f)[1] == "broken")
check("missing", core.read_json_safe(tmp / "none.json")[1] == "missing")
# concurrent writers never leave a torn file
g = tmp / "c.json"
def hammer(i):
    for k in range(60): core.atomic_write(g, json.dumps({"i": i, "k": k, "pad": "x" * 5000}))
ts = [threading.Thread(target=hammer, args=(i,)) for i in range(4)]
[t.start() for t in ts]
bad = 0
while any(t.is_alive() for t in ts):
    try: json.loads(g.read_text())
    except (FileNotFoundError, PermissionError): pass     # Windows: the file is locked for a moment while it is swapped
    except ValueError: bad += 1
[t.join() for t in ts]
check("concurrent atomic writes never torn", bad == 0, bad)

# settings: damaged file kept aside
core.SETTINGS = tmp / "settings.json"                  # never read or write the real settings.json
S = core.load_settings()
S["projects_dir"] = str(tmp / "Projects"); S["downloads_dir"] = str(tmp / "dl"); os.makedirs(S["projects_dir"])
(tmp / "settings.json").write_text("{oops")
s2 = core.load_settings()
check("damaged settings reported + kept", "could not be read" in core.SETTINGS_PROBLEM and list(tmp.glob("settings.broken_*.json")), core.SETTINGS_PROBLEM)
core.save_settings(S)
core.load_settings(); check("good settings load clean", core.SETTINGS_PROBLEM == "")

# project state recovery + repair_stuck
p1 = core.Project.open("one", S); p1.set("rendering_preview", "go", attempt_v=3)
p2 = core.Project.open("two", S); p2.set("transcribing", "go")
p3 = core.Project.open("three", S); p3.set("rendering_final", "go", final_v=2, preview_v=2)
p4 = core.Project.open("four", S); p4.set("done", "ok"); p4.set("done", "ok again")
fixed = core.repair_stuck(S)
check("repair_stuck touched the 3 running", sorted(fixed) == ["one", "three", "two"], fixed)
chk = lambda n: core.Project.open(n, S, create=False).state
check("preview -> stopped w/ kind+version", chk("one")["stage"] == "stopped" and chk("one")["failed_kind"] == "preview" and chk("one")["failed_version"] == 3, chk("one"))
check("final -> stopped final v2", chk("three")["failed_kind"] == "final" and chk("three")["failed_version"] == 2)
check("transcribing -> failed", chk("two")["stage"] == "failed")
check("done untouched", chk("four")["stage"] == "done")
check("stopped project has retry target", core.retry_target(core.Project.open("one", S, create=False)) == ("preview", 3), core.retry_target(core.Project.open("one", S, create=False)))
# corrupted state.json is recovered from .bak
sf = p4.state_file; sf.write_text("{bad")
p4b = core.Project(p4.root); p4b.ensure()
check("corrupt state recovered", p4b.state.get("stage") == "done", p4b.state)

# project_exists / stamp
check("project_exists", core.project_exists(S, "one") and not core.project_exists(S, "nope") and not core.project_exists(S, None))
st1 = core.project_stamp(p1.root); time.sleep(0.02); p1.set("stopped", "again"); check("stamp changes", st1 != core.project_stamp(p1.root))

# add_assets: names, duplicates, collisions, folders
a = tmp / "in"; (a / "sub").mkdir(parents=True)
(a / "pic one.png").write_bytes(b"A"); (a / "sub" / "pic one.png").write_bytes(b"B"); os.utime(a / "sub" / "pic one.png", (1000000000, 1000000000)); (a / "clip.mp4").write_bytes(b"C")
added = core.add_assets(p1, [str(a / "pic one.png"), str(a / "pic one.png")], ctx)
check("same file twice added once", len(added) == 1, added)
added2 = core.add_assets(p1, [str(a / "sub")], ctx)
check("different file same name -> unique name", len(added2) == 1 and added2[0] != added[0], (added, added2))
names = sorted(x.name for x in (p1.src / "assets").iterdir())
check("assets folder has both", len(names) == 2, names)
core.add_assets(p1, [str(a / "clip.mp4")], ctx)

# proxy cache: second run reuses
out = tmp / "px"; calls = []
orig = shutil.copy2
shutil.copy2 = lambda *a, **k: (calls.append(a[1]), orig(*a, **k))[1]
core.proxy_assets(p1, out, ctx); first = len(calls)
calls.clear(); core.proxy_assets(p1, out, ctx)
shutil.copy2 = orig
check("proxy: first run copies, second run reuses", first == 3 and len(calls) == 0, (first, len(calls)))
idx = json.loads((p1.work / "_asset_proxies.json").read_text())
check("proxy index written", len(idx) == 3, idx)
# changed original is redone
time.sleep(0.02); (p1.src / "assets" / "clip.mp4").write_bytes(b"CCCC")
shutil.copy2 = lambda *a, **k: (calls.append(a[1]), orig(*a, **k))[1]
core.proxy_assets(p1, out, ctx); shutil.copy2 = orig
check("proxy: changed file redone only", len(calls) == 1, len(calls))

# zip extraction safety
z = tmp / "evil.zip"
with zipfile.ZipFile(z, "w") as zf:
    zf.writestr("film.py", "x"); zf.writestr("ok/a.txt", "fine"); zf.writestr("../escape.txt", "no"); zf.writestr("/abs.txt", "no"); zf.writestr("C:/win.txt", "no")
dest = tmp / "ex"
names = [i.filename for i in zipfile.ZipFile(z).infolist()]
skipped = core.extract_episode(z, names, dest)
check("unsafe members skipped", skipped == 3 and (dest / "ok" / "a.txt").exists() and not (tmp / "escape.txt").exists(), skipped)

# zip ids: content-based
z1, z2 = tmp / "a.zip", tmp / "b.zip"
z1.write_bytes(b"x" * 100); z2.write_bytes(b"y" * 100)
check("zip_ids differ for different content", core.zip_ids(z1)[1] != core.zip_ids(z2)[1])
check("zip_ids same content/other name", (shutil.copy2(z1, tmp / "c.zip"), core.zip_ids(z1)[1] == core.zip_ids(tmp / "c.zip")[1])[1])

# order normalisation / validation
o = OD.normalize({"size": [1081, 1921], "fps": "25", "duration": {"mode": "fixed", "seconds": "abc", "tail": "2"}})
check("size made even", o["size"][0] % 2 == 0 and o["size"][1] % 2 == 0, o["size"])
check("fps numeric", o["fps"] == 25, o["fps"])
check("bad seconds fall back to number", isinstance(o["duration"]["seconds"], (int, float)))
probs = OD.problems(OD.normalize({"size": [10, 10], "fps": 500}), True, False)
check("tiny size + huge fps reported", len(probs) >= 1, probs)
check("normal order has no problems", OD.problems(OD.normalize(OD.from_preset(list(OD.PRESETS)[0])), True, False) == [], OD.problems(OD.normalize(OD.from_preset(list(OD.PRESETS)[0])), True, False))

# video_frames
import subprocess, imageio_ffmpeg
ff = imageio_ffmpeg.get_ffmpeg_exe(); v = tmp / "t.mp4"
subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=red:s=64x64:r=25:d=2", "-pix_fmt", "yuv420p", str(v)], check=True)
check("video_frames exact", media.video_frames(v) == 50, media.video_frames(v))

shutil.rmtree(tmp, ignore_errors=True)
print("\nFAILS:", fails if fails else "none")
