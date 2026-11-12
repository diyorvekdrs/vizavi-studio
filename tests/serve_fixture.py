import sys, os, json, time, threading, tempfile
APPDIR = os.environ.get("VZ_APP") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app")
sys.path.insert(0, APPDIR)
from pathlib import Path
from studio import server, core
from http.server import ThreadingHTTPServer
PORT = 47998
server.PORT = PORT
for n, v in (("ALLOWED_HOSTS", {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}), ("ALLOWED_ORIGINS", {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"})):
    getattr(server, n).clear(); getattr(server, n).update(v)
tmp = tempfile.mkdtemp(prefix="vz_ui_")
os.environ["VZ_CLAUDE_CONFIG"] = os.path.join(tmp, "claude_desktop_config.json")
server.INCOMING = Path(tmp) / "incoming"
server.TOKEN_FILE = Path(tmp) / ".tok"
core.SETTINGS = __import__('pathlib').Path(tmp) / 'settings.json'   # never touch the real settings.json
S = core.load_settings(); S["projects_dir"] = os.path.join(tmp, "Projects"); S["downloads_dir"] = os.path.join(tmp, "dl"); S["watch_downloads"] = False
os.makedirs(S["projects_dir"]); os.makedirs(S["downloads_dir"])
server.ST.core, server.ST.S, server.ST.ready = core, S, True
server.ST.hw_lines = ["Test PC"]
a = core.Project.open("alpha", S, create=True)
a.set("preview_ready", "preview ready", preview_v=1, last_zip=str(Path(tmp) / "alpha__review_v1.zip"))
(a.work / "review_v1").mkdir(parents=True, exist_ok=True)
(a.work / "review_v1" / "report.json").write_text(json.dumps({"flags": ["cue 'x' at 3.00s is +0.40s from the spoken word", "scene 'intro' starts +0.30s off the nearest beat"], "issues": [{"rank": "P1", "text": "text runs off the frame 2.00s–4.00s: “Salom”"}, {"rank": "P2", "text": "cue 'x' at 3.00s is +0.40s from the spoken word"}, {"rank": "P3", "text": "scene 'intro' starts +0.30s off the nearest beat"}], "est_final_min": 12.4, "scene_cost": {"intro": 12, "main": 40, "outro": 5}}))
(a.work / "preview_v1").mkdir(parents=True, exist_ok=True); (a.work / "preview_v1" / "film.py").write_text("# look"); (a.work / "preview_v1" / "PLAN.md").write_text("plan")
b = core.Project.open("beta", S, create=True)
b.set("stopped", "preview v2 stopped by you", failed_kind="preview", failed_version=2, stop_reason="stopped")
c = core.Project.open("gamma", S, create=True)
old = core.Project.open("oldrep", S, create=True)      # a report from an older version: flags only
old.set("preview_ready", "preview ready", preview_v=1)
(old.work / "review_v1").mkdir(parents=True, exist_ok=True)
(old.work / "review_v1" / "report.json").write_text(json.dumps({"flags": ["sudden jump/pop at 1.00s (frame 24) - not at a scene boundary", "scene 'a' starts +0.10s off the nearest beat"]}))
c.set("request_ready", "request ready")
threading.Thread(target=server.worker, daemon=True).start()
srv = ThreadingHTTPServer(("127.0.0.1", PORT), server.H); srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
print(server.ST.token, flush=True)
# a control channel: lines on stdin tweak the server
for line in sys.stdin:
    cmd = line.strip()
    if cmd == "busy-beta":
        ev = threading.Event(); server.submit("slow", lambda: ev.wait(8), project="beta", key="kb"); 
    elif cmd == "restart":
        server.ST.token = "changed-token"
    elif cmd == "touch-alpha":
        a.set("preview_ready", "touched", preview_v=1)
    elif cmd == "update":
        server.ST.update = {"latest": "9.9.9", "notes": "Faster renders\nSave as style", "page": "x", "newer": True}
    elif cmd == "quit":
        break
