import sys, os, json, tempfile, shutil, zipfile, hashlib, threading, time, subprocess, socket
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
sys.path.insert(0, os.environ.get("VZ_APP") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
from studio import update as UP
fails = []
def check(n, c, x=""):
    print(("ok   " if c else "FAIL ") + n, "" if c else x)
    if not c: fails.append(n)
tmp = Path(tempfile.mkdtemp(prefix="vz_up_"))
check("version compare", UP.newer("v2.2.1", "2.2.0") and not UP.newer("2.2.0", "2.2.0") and UP.newer("2.10.0", "2.9.9") and not UP.newer("v2.1", "2.2.0"))

FAKE_PYW = '''import os, sys, json, time
from http.server import HTTPServer, BaseHTTPRequestHandler
if open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "studio", "version.py")).read().find("BROKEN") >= 0:
    sys.exit(1)
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        b = json.dumps({"app": "vizavi", "ok": True}).encode(); self.send_response(200)
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
srv = HTTPServer(("127.0.0.1", int(os.environ["FAKE_PORT"])), H)
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "started_" + os.environ.get("VZ_TOKEN", "none")), "w").write("x")
srv.timeout = 1
t0 = time.time()
while time.time() - t0 < 6: srv.handle_request()
'''
def make_release(folder, version, files, broken=False):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "studio").mkdir(exist_ok=True)
    (folder / "studio" / "version.py").write_text(f'VERSION = "{version}"\n' + ("# BROKEN\n" if broken else ""))
    (folder / "studio" / "server.py").write_text("# server " + version)
    (folder / "Vizavi Studio.pyw").write_text(FAKE_PYW)
    for rel, txt in files.items():
        (folder / rel).parent.mkdir(parents=True, exist_ok=True); (folder / rel).write_text(txt)
    allf = sorted(["studio/version.py", "studio/server.py", "Vizavi Studio.pyw", "release.json"] + list(files))
    (folder / "release.json").write_text(json.dumps({"version": version, "files": allf}))
    return allf

# installed app 2.2.0 + user data
app = tmp / "VizaviStudio"
make_release(app, "2.2.0", {"ui/app.js": "old js", "studio/old_module.py": "gone in 2.3"})
(app / "settings.json").write_text('{"mine": true}'); (app / "library" / "my_project").mkdir(parents=True)
(app / "library" / "my_project" / "film.py").write_text("my code"); (app / ".venv").mkdir(); (app / ".venv" / "x").write_text("env")

# release 2.3.0 zipped like git archive: app/... at the top
rel_dir = tmp / "build" / "app"
make_release(rel_dir, "2.3.0", {"ui/app.js": "new js", "studio/new_module.py": "new"})
zpath = tmp / "vizavi-studio-2.3.0.zip"
with zipfile.ZipFile(zpath, "w") as z:
    z.writestr("Install Vizavi Studio.cmd", "rem")
    for p in rel_dir.rglob("*"):
        if p.is_file(): z.write(p, "app/" + p.relative_to(rel_dir).as_posix())
    z.writestr("app/../../evil.txt", "no")
good = hashlib.sha256(zpath.read_bytes()).hexdigest()
state = {"sum": good}
class GH(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        base = f"http://127.0.0.1:{self.server.server_port}"
        if self.path.startswith("/repos/"):
            b = json.dumps({"tag_name": "v2.3.0", "body": "Faster renders\nSave as style", "html_url": base + "/rel",
                            "assets": [{"name": zpath.name, "browser_download_url": base + "/zip", "size": zpath.stat().st_size},
                                       {"name": "SHA256SUMS.txt", "browser_download_url": base + "/sums"}]}).encode()
        elif self.path == "/zip": b = zpath.read_bytes()
        elif self.path == "/sums": b = f"{state['sum']}  {zpath.name}\n".encode()
        else: self.send_response(404); self.end_headers(); return
        self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
gh = ThreadingHTTPServer(("127.0.0.1", 0), GH); threading.Thread(target=gh.serve_forever, daemon=True).start()
api = f"http://127.0.0.1:{gh.server_port}/repos/{{repo}}/releases/latest"

info = UP.check("me/vizavi", "2.2.0", api=api)
check("newer release found", info["newer"] and info["latest"] == "2.3.0" and "Faster" in info["notes"], info)
check("not newer when equal", not UP.check("me/vizavi", "2.3.0", api=api)["newer"])
# a slow / dropped connection: tried again, a real 404 is not
import urllib.request as _ur, urllib.error as _ue
_real, calls = _ur.urlopen, []
def flaky(req, timeout=None):
    calls.append(1)
    if len(calls) < 3:
        raise TimeoutError("The read operation timed out")
    return _real(req, timeout=timeout)
_ur.urlopen = flaky; UP.time.sleep = lambda s: None
try:
    check("timeouts are retried", UP.check("me/vizavi", "2.2.0", api=api)["newer"] and len(calls) == 3, len(calls))
    calls.clear()
    def always(req, timeout=None):
        calls.append(1); raise TimeoutError("slow")
    _ur.urlopen = always
    try:
        UP.check("me/vizavi", "2.2.0", api=api); check("gives up after 3 tries", False)
    except TimeoutError:
        check("gives up after 3 tries", len(calls) == 3, len(calls))
    calls.clear()
    def notfound(req, timeout=None):
        calls.append(1); raise _ue.HTTPError("u", 404, "Not Found", {}, None)
    _ur.urlopen = notfound
    try:
        UP.check("me/vizavi", "2.2.0", api=api)
    except _ue.HTTPError:
        check("a 404 is not retried", len(calls) == 1, len(calls))
finally:
    _ur.urlopen = _real
state["sum"] = "0" * 64
try:
    UP.stage(info, app, log=lambda s: None); check("tampered download refused", False)
except ValueError as e:
    check("tampered download refused", "checksum" in str(e))
state["sum"] = good
prog = []
new = UP.stage(info, app, progress=prog.append, log=lambda s: None)
check("staged and verified", (new / "ui" / "app.js").read_text() == "new js" and prog and prog[-1] == 1.0)
check("zip paths outside app/ ignored", not (tmp / "evil.txt").exists() and not (app.parent / "evil.txt").exists())

created = UP.apply_files(app, new, print)
check("new files in place", (app / "ui" / "app.js").read_text() == "new js" and (app / "studio" / "new_module.py").exists())
check("files dropped from the release removed", not (app / "studio" / "old_module.py").exists())
check("user data untouched", json.loads((app / "settings.json").read_text()) == {"mine": True}
      and (app / "library" / "my_project" / "film.py").read_text() == "my code" and (app / ".venv" / "x").exists())
check("backup has the old files", (app / ".update" / "backup" / "ui" / "app.js").read_text() == "old js"
      and (app / ".update" / "backup" / "studio" / "old_module.py").exists())
check("created list", created == ["studio/new_module.py"], created)
UP.restore_files(app, print)
check("undo restores old version", (app / "ui" / "app.js").read_text() == "old js" and (app / "studio" / "old_module.py").exists()
      and not (app / "studio" / "new_module.py").exists() and 'VERSION = "2.2.0"' in (app / "studio" / "version.py").read_text())

# full helper run: engine closed -> swap -> start new engine -> ping
def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p
port = free_port()
env = dict(os.environ, FAKE_PORT=str(port), VZ_TOKEN="tok123")
shutil.copy2(UP.__file__, app / ".update" / "helper.py")
r = subprocess.run([sys.executable, "-I", str(app / ".update" / "helper.py"), "apply", str(app), str(new), str(port)], env=env, timeout=120)
res = json.loads((app / ".update" / "result.json").read_text())
check("helper: update ok + new engine answered", res.get("ok") and res.get("to") == "2.3.0", res)
check("helper: engine got the same token", (app / "started_tok123").exists())
check("helper: on the new version", (app / "ui" / "app.js").read_text() == "new js")
time.sleep(7)  # fake engine exits
# broken release -> rollback
(app / ".update" / "result.json").unlink(); (app / "started_tok123").unlink()
bad = tmp / "bad"; make_release(bad, "2.4.0", {"ui/app.js": "broken js"}, broken=True)
port2 = free_port(); env2 = dict(env, FAKE_PORT=str(port2))
src_py = (app / "studio" / "version.py").read_text()
r = subprocess.run([sys.executable, "-I", str(app / ".update" / "helper.py"), "apply", str(app), str(bad), str(port2)], env=env2, timeout=200)
res = json.loads((app / ".update" / "result.json").read_text())
check("helper: broken update rolled back", not res.get("ok") and (app / "ui" / "app.js").read_text() == "new js"
      and (app / "studio" / "version.py").read_text() == src_py, res)
check("helper: old version started again", (app / "started_tok123").exists())
check("update log written", "rolling back" in (app / ".update" / "update.log").read_text())
gh.shutdown(); shutil.rmtree(tmp, ignore_errors=True)
print("\nFAILS:", fails or "none")
