"""The Claude-app connector end to end: MCP protocol, workspace, file tools, check on the real renderer, and a
preview rendered by a real engine (html engine; skipped without Playwright)."""
import sys, os, json, time, threading, tempfile, subprocess, zipfile, shutil
from pathlib import Path
APPDIR = Path(os.environ.get("VZ_APP") or Path(__file__).resolve().parent.parent / "app")
tmp = Path(tempfile.mkdtemp(prefix="vz_mcp_"))
os.environ["VZ_SETTINGS"] = str(tmp / "settings.json")           # never the real settings
sys.path.insert(0, str(APPDIR))
from studio import core, server
from http.server import ThreadingHTTPServer
fails = []
def check(n, c, x=""):
    print(("ok   " if c else "FAIL ") + n, "" if c else str(x)[:1500])
    if not c: fails.append(n)
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        p.chromium.launch().close()
    HAVE_PW = True
except Exception:
    HAVE_PW = False

# ---- a project waiting for Claude
S = core.load_settings(); S["projects_dir"] = str(tmp / "Projects"); S["downloads_dir"] = str(tmp / "dl")
S["watch_downloads"] = False; S["precise_timing"] = False
os.makedirs(S["projects_dir"]); os.makedirs(S["downloads_dir"])
core.save_settings(S)
pr = core.Project.open("demo", S, create=True)
pr.order.update(size=[1080, 1920], fps=12)
(pr.src / "order.json").write_text(json.dumps(pr.order), encoding="utf-8")
pr.set("request_ready", "request zip created", last_zip="", last_kind="request", duration=4.0, suggested_nfr=48)
man = {"app": "vizavi-studio", "kind": "request", "episode": "demo", "project": "demo", "next_version": 1, "fps": 12,
       "width": 1080, "height": 1920, "variants": [{"id": "9x16", "w": 1080, "h": 1920, "main": True}], "alpha": False,
       "engine": "html", "duration": 4.0, "suggested_nfr": 48, "text_checks": {"safe": [0.1, 0.22, 0.12], "latin_only": True}}
with zipfile.ZipFile(pr.outbox / "demo__request.zip", "w") as z:
    z.writestr("vizavi.json", json.dumps(man))
    z.writestr("input/brief.md", "# Brief: demo\n\n## What I want\nA short test.\n")
    z.writestr("CLAUDE_TASK.md", "task")
    z.writestr("../evil.txt", "must not escape")

# ---- a real engine on a test port
PORT = 47997
server.PORT = PORT
for n, v in (("ALLOWED_HOSTS", {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}), ("ALLOWED_ORIGINS", {f"http://127.0.0.1:{PORT}"})):
    getattr(server, n).clear(); getattr(server, n).update(v)
server.INCOMING = tmp / "incoming"; server.TOKEN_FILE = tmp / ".tok"
server.ST.core, server.ST.S, server.ST.ready = core, S, True
server.write_token()
threading.Thread(target=server.worker, daemon=True).start()
srv = ThreadingHTTPServer(("127.0.0.1", PORT), server.H); srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()

# ---- the connector, as the Claude app starts it
env = dict(os.environ, VZ_PORT=str(PORT), VZ_TOKEN_FILE=str(server.TOKEN_FILE), PYTHONIOENCODING="utf-8")
mcp = subprocess.Popen([sys.executable, str(APPDIR / "studio" / "mcp_server.py")], stdin=subprocess.PIPE,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
replies, lock = {}, threading.Lock()
def reader():
    for line in mcp.stdout:
        m = json.loads(line)
        with lock:
            replies[m.get("id")] = m
threading.Thread(target=reader, daemon=True).start()
_id = [0]
def rpc(method, params=None, timeout=120):
    _id[0] += 1; i = _id[0]
    mcp.stdin.write((json.dumps({"jsonrpc": "2.0", "id": i, "method": method, "params": params or {}}) + "\n").encode())
    mcp.stdin.flush()
    t = time.time()
    while time.time() - t < timeout:
        with lock:
            if i in replies:
                return replies.pop(i)
        time.sleep(0.05)
    raise TimeoutError(method)
def tool(name, **args):
    r = rpc("tools/call", {"name": name, "arguments": args}, timeout=180)["result"]
    txt = "\n".join(c.get("text", "") for c in r["content"] if c["type"] == "text")
    imgs = [c for c in r["content"] if c["type"] == "image"]
    return r["isError"], txt, imgs

r = rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}})
check("initialize", r["result"]["serverInfo"]["name"] == "vizavi-studio" and r["result"]["protocolVersion"] == "2025-06-18", r)
check("unknown protocol version answered with ours", rpc("initialize", {"protocolVersion": "1999-01-01"})["result"]["protocolVersion"] == "2025-06-18")
mcp.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n'); mcp.stdin.flush()
check("ping", rpc("ping")["result"] == {})
tl = rpc("tools/list")["result"]["tools"]
check("tools listed", {"projects", "open_project", "read_file", "write_file", "edit_file", "check", "render_preview", "status", "review"}
      <= {t["name"] for t in tl}, [t["name"] for t in tl])
check("unknown method -> error", "error" in rpc("nope/nope"))
e, t, _ = tool("projects")
check("projects lists demo", not e and "demo" in t and "waiting for Claude" in t, t)
e, t, _ = tool("open_project", project="nope")
check("unknown project explained", e and "no project" in t, t)
e, t, _ = tool("open_project", project="demo")
ws = pr.root / "agent"
check("open_project makes the workspace", not e and (ws / "vizavi.json").exists() and (ws / "tools" / "sandbox_check.py").exists()
      and (ws / "kit" / "vz.js").exists() and (ws / "RULES.md").exists() and (ws / "episode").is_dir(), t[:500])
check("instructions returned", "Chat mode" in t and "render_preview" in t and "A short test" in t)
check("zip member with ../ not extracted", not (pr.root / "evil.txt").exists() and not (tmp / "evil.txt").exists())
e, t, _ = tool("write_file", project="demo", path="input/brief.md", content="x")
check("only episode/ is writable", e and "episode/" in t, t)
e, t, _ = tool("read_file", project="demo", path="../state.json")
check("no reading outside the workspace", e, t)
e, t, _ = tool("read_file", project="demo", path="RULES.md", limit=5)
check("read_file with limit", not e and "lines 1-5" in t, t[:200])

PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>#stage{background:#123;font-family:sans-serif}
#t{position:absolute;left:100px;top:700px;color:#fff;font-size:110px}#b{position:absolute;top:1100px;width:160px;height:160px;background:#fc0}</style></head>
<body><div id="stage"><div id="t">Salom</div><div id="b"></div></div><script src="vz.js"></script><script>
VZ.onFrame(t => { document.getElementById('b').style.left = (100 + 600 * VZ.prog(t, 0, 4, VZ.ease.inOut)) + 'px'; });
</script></body></html>"""
files = {"episode/project.json": json.dumps({"engine": "html", "width": 1080, "height": 1920, "fps": 12, "nfr": 48, "alpha": False,
                                             "responsive": False, "scenes": [["one", 0, 2], ["two", 2, 4]], "cues": []}),
         "episode/index.html": PAGE,
         "episode/audio.py": "import numpy as np\nfrom scipy.io import wavfile\nwavfile.write('mix.wav', 48000, np.zeros((48000 * 4, 2), np.int16))\n",
         "episode/PLAN.md": "# PLAN\n\n## Beats\n" + "".join(f"| {i} | a | b | c | d | e | f |\n" for i in range(1, 5))
                            + "\n## Self-critique\n| 1 | 4 | 4 | 4 | 4 | 4 | 4 |\n" + "x" * 700,
         "episode/CHANGES.md": "first version"}
for pth, c in files.items():
    e, t, _ = tool("write_file", project="demo", path=pth, content=c)
check("episode written", not e and (ws / "episode" / "index.html").exists(), t)
e, t, _ = tool("edit_file", project="demo", path="episode/CHANGES.md", old_text="first", new_text="the first")
check("edit_file", not e and (ws / "episode" / "CHANGES.md").read_text() == "the first version", t)
e, t, _ = tool("edit_file", project="demo", path="episode/CHANGES.md", old_text="zzz", new_text="y")
check("edit_file refuses a missing piece", e and "0 times" in t, t)

if HAVE_PW:
    e, t, imgs = tool("check", project="demo")
    if "still running" in t:
        e, t, imgs = tool("wait", project="demo", seconds=55)
    check("check runs on the PC", not e and "html engine" in t and "motion strip 'one'" in t, t[-1500:])
    check("check returns the images", len(imgs) >= 3, len(imgs))
    e, t, imgs = tool("check", project="demo", strip="0-2")
    if "still running" in t:
        e, t, imgs = tool("wait", project="demo", seconds=55)
    check("strip only", not e and "motion strip '0.0-2.0s'" in t and len(imgs) >= 1, t[-800:])
    e, t, _ = tool("render_preview", project="demo", note="test version")
    check("render_preview sends it to the app", not e and "v1 sent" in t, t)
    for _ in range(12):
        e, t, imgs = tool("status", project="demo", seconds=30)
        if "preview ready" in t or "problem" in t:
            break
    check("the app rendered the preview", "preview ready" in t and "Preview v1" in t, t[-3000:])
    check("status includes the review sheets", len(imgs) >= 1, len(imgs))
    pr2 = core.Project.open("demo", S, create=False)
    core.write_notes(pr2, 1, "Make the yellow box bigger")
    e, t, imgs = tool("review", project="demo")
    check("review has the user's notes", not e and "Make the yellow box bigger" in t and (ws / "review" / "report.md").exists(), t[:800])
    e, t, _ = tool("open_project", project="demo")
    e, t, _ = tool("render_preview", project="demo", note="v2")
    check("next version numbered 2", not e and "v2 sent" in t, t)
else:
    print("(check / render skipped: no Playwright)")

# ---- connecting the Claude app: other entries kept, a damaged file never overwritten
from studio import claude_link
cfg = tmp / "claude" / "claude_desktop_config.json"; cfg.parent.mkdir()
os.environ["VZ_CLAUDE_CONFIG"] = str(cfg)
cfg.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}, "globalShortcut": "Ctrl+Space"}), encoding="utf-8")
check("not connected at first", claude_link.status()["connected"] is False)
claude_link.connect()
d = json.loads(cfg.read_text(encoding="utf-8"))
check("connect adds the entry, keeps the rest", d["mcpServers"]["other"] == {"command": "x"} and d["globalShortcut"] == "Ctrl+Space"
      and d["mcpServers"]["vizavi-studio"]["args"][0].endswith("mcp_server.py"), d)
check("status: connected to this copy", claude_link.status() == {"connected": True, "current": True, "path": str(cfg), "problem": ""})
check("a backup is kept", cfg.with_suffix(".json.bak").exists())
claude_link.disconnect()
check("disconnect removes only ours", json.loads(cfg.read_text(encoding="utf-8"))["mcpServers"] == {"other": {"command": "x"}})
cfg.write_text("{broken", encoding="utf-8")
try:
    claude_link.connect(); check("damaged config is not overwritten", False)
except ValueError:
    check("damaged config is not overwritten", cfg.read_text(encoding="utf-8") == "{broken")
check("damaged config reported", bool(claude_link.status()["problem"]))
cfg.unlink(); claude_link.connect()
check("connect creates a missing config", "vizavi-studio" in json.loads(cfg.read_text(encoding="utf-8"))["mcpServers"])

mcp.stdin.close(); mcp.wait(timeout=10)
err = mcp.stderr.read().decode("utf-8", "replace")
check("nothing but the protocol on stdout (log on stderr)", "connector" in err, err[-500:])
print("\nFAILS:", fails or "none")
sys.exit(1 if fails else 0)
