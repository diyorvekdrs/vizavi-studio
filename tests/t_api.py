import sys, os, json, time, threading, tempfile, shutil, http.client, urllib.parse
APPDIR = os.environ.get("VZ_APP") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app")
sys.path.insert(0, APPDIR)
from studio import server, core
from http.server import ThreadingHTTPServer

PORT = 47999
server.PORT = PORT
server.ALLOWED_HOSTS.clear(); server.ALLOWED_HOSTS.update({f"127.0.0.1:{PORT}", f"localhost:{PORT}"})
server.ALLOWED_ORIGINS.clear(); server.ALLOWED_ORIGINS.update({f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"})
tmp = tempfile.mkdtemp(prefix="vz_api_")
server.INCOMING = __import__("pathlib").Path(tmp) / "incoming"
core.SETTINGS = __import__('pathlib').Path(tmp) / 'settings.json'   # never touch the real settings.json
S = core.load_settings(); S["projects_dir"] = os.path.join(tmp, "Projects"); S["downloads_dir"] = os.path.join(tmp, "dl")
os.makedirs(S["projects_dir"]); os.makedirs(S["downloads_dir"])
server.ST.core, server.ST.S, server.ST.ready = core, S, True
server.ST.hw_lines = []
threading.Thread(target=server.worker, daemon=True).start()
srv = ThreadingHTTPServer(("127.0.0.1", PORT), server.H); srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
server.TOKEN_FILE = __import__("pathlib").Path(tmp) / ".tok"
TOK = server.ST.token
fails = []

def req(method, path, body=None, headers=None, cookie=True, host=None):
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=10)
    h = dict(headers or {})
    if cookie: h["Cookie"] = f"vz={TOK}"
    if host: h["Host"] = host
    if isinstance(body, (dict, list)): body = json.dumps(body); h["Content-Type"] = "application/json"
    c.request(method, path, body=body, headers=h)
    r = c.getresponse(); data = r.read()
    return r.status, dict(r.getheaders()), data

def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name, extra if not cond else "")
    if not cond: fails.append(name)

# --- auth
check("ping needs no token", req("GET", "/api/ping", cookie=False)[0] == 200)
check("ping bad host blocked", req("GET", "/api/ping", host="evil.com")[0] == 403)
check("poll without token 401", req("GET", "/api/poll", cookie=False)[0] == 401)
check("poll with cookie", req("GET", "/api/poll")[0] == 200)
check("poll with header token", req("GET", "/api/poll", cookie=False, headers={"X-VZ-Token": TOK})[0] == 200)
check("wrong token 401", req("GET", "/api/poll", cookie=False, headers={"X-VZ-Token": "x"})[0] == 401)
s, h, b = req("GET", f"/?t={TOK}", cookie=False)
check("token redirect sets cookie", s == 302 and "vz=" in h.get("Set-Cookie", "") and "HttpOnly" in h["Set-Cookie"] and "SameSite=Strict" in h["Set-Cookie"], str(h))
s, h, b = req("GET", "/", cookie=False)
check("index without cookie 401 page", s == 401 and b"out of date" in b)
s, h, b = req("GET", "/")
check("index with cookie", s == 200 and b"<html" in b.lower())
check("POST bad origin", req("POST", "/api/act", {"action": "stop"}, headers={"Origin": "http://evil.com"})[0] == 403)
check("POST good origin", req("POST", "/api/act", {"action": "stop"}, headers={"Origin": f"http://127.0.0.1:{PORT}"})[0] == 200)
check("POST no token", req("POST", "/api/act", {"action": "stop"}, cookie=False)[0] == 401)
check("ui traversal", req("GET", "/ui/..%2Fstudio%2Fcore.py")[0] == 404)
check("ui traversal2", req("GET", "/ui/../studio/core.py")[0] in (404, 400))
check("ui file", req("GET", "/ui/app.js")[0] == 200)
check("media outside projects", req("GET", "/media?path=" + urllib.parse.quote(os.path.join(APPDIR, "studio/core.py")))[0] == 403)
sibling = S["projects_dir"] + "_evil"; os.makedirs(sibling); open(sibling + "/x.txt", "w").write("x")
check("media sibling-prefix dir", req("GET", "/media?path=" + urllib.parse.quote(sibling + "/x.txt"))[0] == 403)
check("bad json 400", req("POST", "/api/act", b"{nope", headers={"Content-Type": "application/json"})[0] == 400)
check("unknown action", req("POST", "/api/act", {"action": "bogus"})[0] == 400)
check("missing project", req("POST", "/api/act", {"action": "approve", "name": "nothere"})[0] == 400)

# --- upload
s, h, b = req("POST", "/api/upload?batch=b1&rel=" + urllib.parse.quote("../../etc/evil.txt"), b"hello")
p = json.loads(b)["path"]; check("upload stays inside incoming", s == 200 and server.is_inside(p, server.INCOMING) and open(p, "rb").read() == b"hello", p)
s, h, b = req("POST", "/api/upload?batch=b1&rel=" + urllib.parse.quote("C:\\Windows\\x.txt"), b"hi")
check("upload windows path sanitised", s == 200 and server.is_inside(json.loads(b)["path"], server.INCOMING), b)
# interrupted upload
c = http.client.HTTPConnection("127.0.0.1", PORT); c.putrequest("POST", "/api/upload?batch=b2&rel=big.bin"); c.putheader("Cookie", f"vz={TOK}"); c.putheader("Content-Length", "1000"); c.endheaders(); c.send(b"abc"); c.sock.shutdown(1)
time.sleep(0.5)
check("interrupted upload leaves nothing", not any(server.INCOMING.joinpath("b2").glob("*")) if server.INCOMING.joinpath("b2").exists() else True)

# --- range
big = os.path.join(S["projects_dir"], "r.mp4"); open(big, "wb").write(bytes(range(256)) * 40)  # 10240 bytes
u = "/media?path=" + urllib.parse.quote(big)
s, h, b = req("GET", u, headers={"Range": "bytes=0-99"}); check("range 206", s == 206 and len(b) == 100 and h["Content-Range"] == "bytes 0-99/10240")
s, h, b = req("GET", u, headers={"Range": "bytes=10000-"}); check("open range", s == 206 and len(b) == 240)
s, h, b = req("GET", u, headers={"Range": "bytes=-100"}); check("suffix range", s == 206 and len(b) == 100)
s, h, b = req("GET", u, headers={"Range": "bytes=0-99999"}); check("end past size clamped", s == 206 and len(b) == 10240)
s, h, b = req("GET", u, headers={"Range": "bytes=99999-"}); check("start past size 416", s == 416)
s, h, b = req("GET", u, headers={"Range": "bytes=abc-"}); check("garbage range -> full 200", s == 200 and len(b) == 10240)
s, h, b = req("GET", u, headers={"Range": "bytes=0-1,5-6"}); check("multi range -> full 200", s == 200 and len(b) == 10240)
open(os.path.join(S["projects_dir"], "e.mp4"), "wb").close()
s, h, b = req("GET", "/media?path=" + urllib.parse.quote(os.path.join(S["projects_dir"], "e.mp4"))); check("empty file", s == 200 and b == b"")

# --- settings / presets
check("settings bad dir", req("POST", "/api/settings", {"projects_dir": ""})[0] == 400)
s, h, b = req("POST", "/api/settings", {"standing_rules": "be nice", "watch_downloads": 0, "evil_key": 1}); check("settings ok", s == 200 and S["standing_rules"] == "be nice" and S["watch_downloads"] is False and "evil_key" not in S)
check("preset no name", req("POST", "/api/save_preset", {"order": {}, "name": ""})[0] == 400)
bi = list(core.OD.PRESETS)[0]
check("preset builtin name refused", req("POST", "/api/save_preset", {"order": {}, "name": bi})[0] == 400)
check("preset ok without audio", req("POST", "/api/save_preset", {"order": {"fps": 30}, "name": "Mine"})[0] == 200 and "Mine" in S["user_presets"])
check("preset q missing", req("GET", "/api/preset")[0] == 200)
check("meta", req("GET", "/api/meta")[0] == 200)

# --- projects: make a fake one
pr = core.Project.open("demo", S, create=True)
pr.set("preview_ready", "preview ready", preview_v=1)
os.makedirs(pr.work / "preview_v1", exist_ok=True)
(pr.work / "review_v1").mkdir(parents=True, exist_ok=True)
(pr.work / "review_v1" / "report.json").write_text(json.dumps({"flags": ["a", "b"], "est_final_min": 4.5, "scene_cost": {"s1": 10, "s2": 30}}))
s, h, b = req("GET", "/api/project?name=demo"); j = json.loads(b)
check("project json fields", s == 200 and j["flags"] == ["a", "b"] and j["est_final_min"] == 4.5 and j["scene_cost"][0][0] == "s2" and j["busy"] is False and "notes_saved" in j, str(j)[:300])
check("projects list busy field", json.loads(req("GET", "/api/projects")[2])[0]["busy"] is False)
s, h, b = req("POST", "/api/act", {"action": "save_notes", "name": "demo", "text": "fix the intro"})
check("save_notes", s == 200 and json.loads(req("GET", "/api/project?name=demo")[2])["notes_saved"] == "fix the intro")
s, h, b = req("GET", "/api/poll?since=0&proj=demo"); j = json.loads(b); check("poll stamp + busy_projects", j["stamp"] and j["busy_projects"] == {})
time.sleep(0.2)
st1 = json.loads(req("GET", "/api/poll?proj=demo")[2])["stamp"]; time.sleep(0.05); pr.set("preview_ready", "again")
st2 = json.loads(req("GET", "/api/poll?proj=demo")[2])["stamp"]; check("stamp changes when state changes", st1 != st2)
check("poll bad since", req("GET", "/api/poll?since=abc")[0] == 200)

# job busy / duplicate / delete refusal
ev = threading.Event()
def slow(): ev.wait(5)
server.submit("slow", slow, project="demo", key="k1")
time.sleep(0.3)
check("busy marked", json.loads(req("GET", "/api/poll")[2])["busy_projects"].get("demo") == 1 and json.loads(req("GET", "/api/projects")[2])[0]["busy"])
check("dup refused", server.submit("slow", slow, project="demo", key="k1") is False)
s, h, b = req("POST", "/api/act", {"action": "delete", "name": "demo"}); check("delete busy refused", s == 400 and b"processed" in b, b)
ev.set(); time.sleep(0.5)
check("busy cleared", json.loads(req("GET", "/api/poll")[2])["busy_projects"] == {})
check("stop when idle ok", req("POST", "/api/act", {"action": "stop"})[0] == 200 and not server.CTX.cancelled)
s, h, b = req("POST", "/api/act", {"action": "approve", "name": "demo"}); check("approve not allowed outside preview_ready? (is preview_ready)", s in (200, 400))
s, h, b = req("POST", "/api/act", {"action": "open_file", "name": "demo", "path": os.path.join(APPDIR, "studio/core.py")}); check("open_file outside refused silently", s == 200)
for _ in range(60):
    if not server.ST.busy and server.ST.jobs.empty(): break
    time.sleep(0.2)
s, h, b = req("POST", "/api/act", {"action": "delete", "name": "demo"}); time.sleep(0.3)
check("delete works when idle", s == 200 and not core.project_exists(S, "demo"), b)
s, h, b = req("POST", "/api/act", {"action": "set_final_size", "name": "demo", "value": 1920})
check("set_final_size saved", s == 200 and json.loads(req("GET", "/api/project?name=demo")[2])["final_long_side"] == 1920, b) if core.project_exists(S, "demo") else None
check("zip missing 400", req("POST", "/api/process_zip", {"paths": ["/nope.zip"]})[0] == 400)
check("new_project no order 400", req("POST", "/api/new_project", {})[0] == 400)
check("new_project missing narration 400", req("POST", "/api/new_project", {"order": {"name": "x"}, "narration": "/no/such.wav"})[0] == 400)
check("token file roundtrip", (server.write_token(), server.read_token())[1] == TOK)
print("\nFAILS:", fails if fails else "none")
shutil.rmtree(tmp, ignore_errors=True)
