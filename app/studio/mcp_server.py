"""Vizavi Studio connector for the Claude desktop app (MCP over stdio) - "chat mode", no zips.

Claude talks with you in the Claude app as usual, but builds the video right here on your PC: it opens the
project's workspace (<project>/agent/ = the same files a request zip would hold), writes the code in
agent/episode/, renders stills and 6 fps motion strips on your graphics card, reads the checks, and sends the
version to Vizavi Studio, which renders the preview exactly as for a zip. Your notes from the app's notes box come
back to Claude with the review tool.

Started by the Claude app (Settings → Connect to the Claude app writes the entry). Only this protocol is written to
stdout; messages for people go to stderr (the Claude app's MCP log)."""
import base64, io, json, os, re, shutil, subprocess, sys, threading, time, traceback, urllib.error, urllib.parse, urllib.request, zipfile
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
from studio.version import VERSION  # noqa: E402

PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
PORT = int(os.environ.get("VZ_PORT") or 47613)          # (overridable for tests)
TOKEN_FILE = Path(os.environ.get("VZ_TOKEN_FILE") or APP / ".session_token")
NOWIN = 0x08000000 if os.name == "nt" else 0
CHECK_WAIT = 50          # seconds a tool call waits before answering "still running" (clients time out at ~60 s)
MAX_IMAGES = 6
EDITABLE = ("episode/",)

INSTRUCTIONS = (
    "Vizavi Studio makes videos on the user's PC. Workflow: projects → open_project (read the instructions it "
    "returns, then RULES.md, DIRECTION.md and the engine doc with read_file) → write the video in episode/ with "
    "write_file → check (stills, motion strips, text/sound checks on the user's GPU; look at the images) → fix → "
    "render_preview → status until the preview is ready → review. When the user has written notes in the app, call "
    "review, make the asked changes, check, render_preview again. Never ask the user to move zips.")


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# ------------------------------------------------------------------ the app's own code (read only) + its engine
_core = None


def core():
    global _core
    if _core is None:
        from studio import core as c
        _core = c
    return _core


def settings():
    return core().load_settings()          # read fresh: the app may have changed them; never saved from here


def project(name):
    if not isinstance(name, str) or not name.strip():
        raise ToolError("Give the project name (see the projects tool).")
    pr = core().Project.open(name, settings(), create=False)
    if pr is None:
        raise ToolError(f"There is no project “{name}”. The projects tool lists them; new projects are made in "
                        "Vizavi Studio (New project) – the app transcribes the voice first.")
    return pr


class ToolError(Exception):
    pass


def token():
    try:
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def engine(path, body=None, timeout=20):
    """call the running Vizavi Studio; starts it (without a window) when it isn't running"""
    for attempt in range(2):
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", method="POST" if body is not None else "GET",
                                         data=None if body is None else json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json", "X-VZ-Token": token()})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read()).get("error")
            except Exception:
                msg = None
            raise ToolError(msg or f"Vizavi Studio answered {e.code}")
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
            if attempt:
                raise ToolError("Vizavi Studio is not running and could not be started – ask the user to open it.")
            start_engine()


def start_engine():
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe") if os.name == "nt" and exe.with_name("pythonw.exe").exists() else exe
    log("starting Vizavi Studio (no window)…")
    subprocess.Popen([str(pyw), str(APP / "Vizavi Studio.pyw"), "--no-window"], cwd=str(APP),
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=NOWIN | (0x00000008 if os.name == "nt" else 0), start_new_session=os.name != "nt")
    for _ in range(60):
        time.sleep(1)
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/ping", timeout=1) as r:
                if json.loads(r.read()).get("app") == "vizavi":
                    for _ in range(90):                       # setup (component check) finishes
                        p = engine_poll()
                        if p.get("ready"):
                            return
                        time.sleep(1)
                    return
        except Exception:
            pass


def engine_poll():
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}/api/poll?since=999999999",
                                     headers={"X-VZ-Token": token()})
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read())
    except Exception:
        return {}


# ------------------------------------------------------------------ the workspace
def workspace(pr):
    return pr.root / "agent"


def inside(ws, rel, write=False):
    rel = str(rel or "").replace("\\", "/").lstrip("/")
    c = core()
    clean = c.safe_member(rel) if rel else ""
    if rel and clean is None:
        raise ToolError(f"“{rel}” is not a path inside the project workspace.")
    p = ws / clean if clean else ws
    if not c.is_inside(p, ws):
        raise ToolError(f"“{rel}” is outside the project workspace.")
    if write and not any((clean + "/").startswith(e) or clean.startswith(e) for e in EDITABLE):
        raise ToolError("Only files in episode/ can be written (everything else is the app's input and tools).")
    return p, clean


def latest_version(pr):
    st = pr.state
    return max(int(st.get(k) or 0) for k in ("preview_v", "final_v", "attempt_v", "failed_version", "last_version"))


def prepare_workspace(pr, sync=False):
    """<project>/agent from the project's request package; episode/ seeded from Claude's newest code if there is some"""
    ws = workspace(pr)
    notes = []
    req = pr.outbox / f"{pr.name}__request.zip"
    if not (ws / "vizavi.json").exists():
        if not req.exists():
            raise ToolError(f"“{pr.name}” has no request package yet – it is still being prepared in Vizavi Studio "
                            "(or failed there). Try again when the app shows 'waiting for Claude'.")
        ws.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(req) as z:
            for info in z.infolist():
                clean = core().safe_member(info.filename)
                if clean is None or info.is_dir():
                    continue
                out = ws / clean
                out.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as s, open(out, "wb") as d:
                    shutil.copyfileobj(s, d)
        notes.append("workspace created from the request package")
    refresh_runtime(ws)
    ep = ws / "episode"
    found = core().latest_code_dir(pr)
    empty = not ep.exists() or not any(ep.iterdir())
    if found and (empty or sync):
        src, kind, ver = found
        if ep.exists() and not empty:
            bak = ws / f"episode_before_sync_{time.strftime('%Y%m%d_%H%M%S')}"
            shutil.move(str(ep), str(bak))
            notes.append(f"previous episode/ kept as {bak.name}")
        ep.mkdir(parents=True, exist_ok=True)
        for rel, p in core().episode_files(src):
            if rel.split("/")[0] in ("input", "out", "check", "fonts", "assets", "brand", "cache", "media") or \
                    (("/" not in rel) and p.name in core().RUNTIME_FILES):
                continue
            (ep / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, ep / rel)
        notes.append(f"episode/ holds the code of {kind} v{ver} (the version the user last saw)")
    elif found and not empty:
        src, kind, ver = found
        try:
            newer = max(f.stat().st_mtime for f in src.rglob("*.py")) > max(f.stat().st_mtime for f in ep.rglob("*") if f.is_file())
        except ValueError:
            newer = False
        if newer:
            notes.append(f"note: {kind} v{ver} in the app is newer than episode/ (made outside this chat?) – "
                         "open_project with sync=true copies it in")
    ep.mkdir(parents=True, exist_ok=True)
    return ws, notes


def refresh_runtime(ws):
    """the instructions, tools and render kit always come from the app as it is now (it may have been updated
    since the request package was made)"""
    c = core()
    for f in ("RULES.md", "DIRECTION.md", "ENGINE_python.md", "ENGINE_html.md", "PLAN_TEMPLATE.md", "TASK_review.md"):
        if (c.CL / f).exists():
            shutil.copy2(c.CL / f, ws / f)
    for sub, src in (("tools", c.TOOLS), ("kit", c.KIT)):
        (ws / sub).mkdir(exist_ok=True)
        for f in src.glob("*.py" if sub == "tools" else "*"):
            if f.is_file():
                shutil.copy2(f, ws / sub / f.name)
    shutil.copy2(c.ENGINES / "vz.js", ws / "kit" / "vz.js")
    for sub, src in (("templates", c.CL / "templates"), ("fonts", c.FONTS)):
        if src.exists() and not (ws / sub).exists():
            shutil.copytree(src, ws / sub)


def set_next_version(ws, pr):
    f = ws / "vizavi.json"
    man = json.loads(f.read_text(encoding="utf-8"))
    man["next_version"] = latest_version(pr) + 1
    man["kind"] = "review" if pr.state.get("preview_v") else "request"
    f.write_text(json.dumps(man, indent=1, ensure_ascii=False), encoding="utf-8")
    return man["next_version"]


# ------------------------------------------------------------------ images
def image_block(path, max_side=1600):
    from PIL import Image
    im = Image.open(path)
    im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "JPEG", quality=80)
    return {"type": "image", "data": base64.b64encode(buf.getvalue()).decode(), "mimeType": "image/jpeg"}


def text(s):
    return {"type": "text", "text": s}


# ------------------------------------------------------------------ tools
def t_projects(a):
    c = core()
    S = settings()
    rows = []
    for pr in c.list_projects(S):
        st = pr.state
        rows.append(f"- {pr.name}: {c.STAGE_TEXT.get(st.get('stage', 'new'), st.get('stage'))}"
                    f" · {st.get('preset') or ''} · {st.get('duration') or '?'} s"
                    + (" · workspace ready" if (workspace(pr) / "vizavi.json").exists() else ""))
    return [text("Projects in Vizavi Studio:\n" + ("\n".join(rows) or "(none – make one in the app: New project)"))]


def t_open_project(a):
    pr = project(a.get("project"))
    ws, notes = prepare_workspace(pr, bool(a.get("sync")))
    man = json.loads((ws / "vizavi.json").read_text(encoding="utf-8"))
    brief = (ws / "input" / "brief.md").read_text(encoding="utf-8") if (ws / "input" / "brief.md").exists() else ""
    task = (core().CL / "TASK_agent.md").read_text(encoding="utf-8").replace("{{EP}}", pr.name)
    st = pr.state
    out = [f"# Project “{pr.name}” – {core().STAGE_TEXT.get(st.get('stage', 'new'), st.get('stage'))}",
           *[f"({n})" for n in notes], "", task, "",
           "## vizavi.json", json.dumps({k: man.get(k) for k in ("width", "height", "fps", "variants", "alpha", "engine",
                                                                  "duration", "suggested_nfr", "narration_duration",
                                                                  "transcript_source", "transcript_match", "text_checks")},
                                         ensure_ascii=False), "", brief]
    if st.get("preview_v"):
        out += ["", f"A preview (v{st['preview_v']}) exists – call review for the user's notes and the checks."]
    return [text("\n".join(out))]


def t_list_files(a):
    pr = project(a.get("project"))
    ws, _ = prepare_workspace(pr)
    d, clean = inside(ws, a.get("folder", ""))
    if not d.is_dir():
        raise ToolError(f"No folder “{clean}”.")
    rows = []
    for p in sorted(d.iterdir()):
        if p.name.startswith(("episode_before_sync", "__pycache__")):
            continue
        rows.append(f"{p.relative_to(ws).as_posix()}{'/' if p.is_dir() else ''}"
                    + ("" if p.is_dir() else f"  ({p.stat().st_size / 1024:.0f} KB)"))
    return [text("\n".join(rows[:400]) or "(empty)")]


def t_read_file(a):
    pr = project(a.get("project"))
    ws, _ = prepare_workspace(pr)
    p, clean = inside(ws, a.get("path"))
    if not p.is_file():
        raise ToolError(f"No file “{clean}”.")
    if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"):
        return [text(clean), image_block(p)]
    if p.suffix.lower() in (".wav", ".mp3", ".m4a", ".mp4", ".mov", ".webm", ".ttf", ".otf", ".zip", ".npy"):
        return [text(f"{clean} is a binary file ({p.stat().st_size / 1e6:.1f} MB) – use it from your code by its path.")]
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    off = max(0, int(a.get("offset") or 1) - 1)
    lim = int(a.get("limit") or 1500)
    part = lines[off:off + lim]
    more = f"\n… {len(lines) - off - lim} more lines (offset={off + lim + 1})" if off + lim < len(lines) else ""
    return [text(f"{clean} (lines {off + 1}-{off + len(part)} of {len(lines)})\n" + "\n".join(part) + more)]


def t_write_file(a):
    pr = project(a.get("project"))
    ws, _ = prepare_workspace(pr)
    p, clean = inside(ws, a.get("path"), write=True)
    content = a.get("content")
    if not isinstance(content, str):
        raise ToolError("content must be the whole file as text.")
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, p)
    return [text(f"wrote {clean} ({len(content.encode('utf-8')) / 1024:.1f} KB)")]


def t_edit_file(a):
    pr = project(a.get("project"))
    ws, _ = prepare_workspace(pr)
    p, clean = inside(ws, a.get("path"), write=True)
    if not p.is_file():
        raise ToolError(f"No file “{clean}” – use write_file to create it.")
    s = p.read_text(encoding="utf-8")
    old, new = a.get("old_text"), a.get("new_text", "")
    if not isinstance(old, str) or not old:
        raise ToolError("old_text must be text copied exactly from the file.")
    n = s.count(old)
    if n != 1:
        raise ToolError(f"old_text occurs {n} times in {clean} – it must occur exactly once (add surrounding lines).")
    p.write_text(s.replace(old, new), encoding="utf-8")
    return [text(f"edited {clean}")]


_jobs = {}       # project -> {"proc", "kind", "started", "args"}


def run_job(pr, kind, cmd, cwd):
    j = _jobs.get(pr.name)
    if j and j["proc"].poll() is None:
        raise ToolError(f"A {j['kind']} is still running for this project – call wait (or check again) for its result.")
    logf = open(cwd / f".{kind}.log", "w", encoding="utf-8")
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    proc = subprocess.Popen(cmd, cwd=str(cwd), stdout=logf, stderr=subprocess.STDOUT, env=env, creationflags=NOWIN)
    _jobs[pr.name] = {"proc": proc, "kind": kind, "started": time.time(), "log": cwd / f".{kind}.log", "ws": cwd}
    return wait_job(pr, CHECK_WAIT)


def wait_job(pr, seconds):
    j = _jobs.get(pr.name)
    if not j:
        return None
    t_end = time.time() + max(1, min(55, seconds))
    while j["proc"].poll() is None and time.time() < t_end:
        time.sleep(0.5)
    if j["proc"].poll() is None:
        tail = j["log"].read_text(encoding="utf-8", errors="replace").strip().splitlines()[-3:]
        return [text(f"{j['kind']} still running ({time.time() - j['started']:.0f} s so far) – call wait to get the "
                     f"result. Last lines:\n" + "\n".join(tail))]
    _jobs.pop(pr.name, None)
    return job_result(j)


def job_result(j):
    ws = j["ws"]
    out = j["log"].read_text(encoding="utf-8", errors="replace")
    if j["kind"] != "check":
        return [text(f"{j['kind']} finished (exit {j['proc'].returncode}):\n" + out[-6000:])]
    rep = (ws / "check" / "report.txt").read_text(encoding="utf-8") if (ws / "check" / "report.txt").exists() else out[-6000:]
    blocks = [text(f"check finished (exit {j['proc'].returncode}) in {time.time() - j['started']:.0f} s\n\n{rep}"
                   + ("" if j["proc"].returncode == 0 else "\n\nlog tail:\n" + out[-3000:]))]
    imgs = sorted((ws / "check").glob("strip_*.jpg")) + sorted((ws / "check").glob("sheet_*.jpg")) + \
        sorted((ws / "check").glob("variant_*.jpg")) + sorted((ws / "check").glob("audio_plot.png"))
    for p in imgs[:MAX_IMAGES]:
        blocks += [text(f"check/{p.name}"), image_block(p)]
    if len(imgs) > MAX_IMAGES:
        blocks.append(text(f"(+{len(imgs) - MAX_IMAGES} more images in check/: " + ", ".join(p.name for p in imgs[MAX_IMAGES:])
                           + " – read_file shows them)"))
    return blocks


def t_check(a):
    pr = project(a.get("project"))
    ws, _ = prepare_workspace(pr)
    if not ((ws / "episode" / "film.py").exists() or (ws / "episode" / "project.json").exists()):
        raise ToolError("episode/ has no film.py or project.json yet – write the video first.")
    cmd = [sys.executable, "tools/sandbox_check.py", "episode", "--real"]
    for k, flag in (("scene", "--scene"), ("times", "--times"), ("strip", "--strip"), ("every", "--every"), ("width", "--width")):
        if a.get(k) not in (None, ""):
            cmd += [flag, str(a[k])]
    if not a.get("audio"):
        cmd.append("--no-audio")
    if a.get("scene") or a.get("strip") or a.get("times"):
        cmd.append("--no-variants")
    return run_job(pr, "check", cmd, ws)


def t_wait(a):
    pr = project(a.get("project"))
    r = wait_job(pr, int(a.get("seconds") or 50))
    if r is None:
        return t_status(a)
    return r


def t_retime(a):
    pr = project(a.get("project"))
    ws, _ = prepare_workspace(pr)
    return run_job(pr, "retime", [sys.executable, "tools/retime.py"], ws)


def t_render_preview(a):
    pr = project(a.get("project"))
    ws, _ = prepare_workspace(pr)
    ver = set_next_version(ws, pr)
    outd = ws / "_packs"
    outd.mkdir(exist_ok=True)
    for f in outd.glob("*.zip"):
        f.unlink()
    r = subprocess.run([sys.executable, "tools/vizavi_pack.py", "--kind", a.get("kind") or "preview", "--src",
                        str(ws / "episode"), "--out", str(outd), "--note", str(a.get("note") or "")],
                       cwd=str(ws), capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=NOWIN)
    zips = list(outd.glob("*.zip"))
    if r.returncode or not zips:
        raise ToolError((r.stdout + r.stderr).strip()[-3000:] or "packing failed")
    res = engine("/api/process_zip", {"paths": [str(zips[0])]})
    return [text(f"v{ver} sent to Vizavi Studio ({'rendering' if res.get('started') else 'already queued'}). "
                 "The user sees the progress in the app. Call status (it waits up to ~50 s per call) until the "
                 "preview is ready, then review.")]


def t_status(a):
    pr = project(a.get("project"))
    t_end = time.time() + max(0, min(55, int(a.get("seconds") or 45)))
    while True:
        pj = engine(f"/api/project?name={urllib.parse.quote(pr.name)}")
        poll = engine_poll()
        busy = pj.get("busy")
        stage = pj.get("stage")
        if not busy and stage not in ("rendering_preview", "rendering_final", "transcribing") or time.time() >= t_end:
            break
        time.sleep(2)
    st = poll.get("status") or {}
    line = f"stage: {pj.get('stage_text')}" + (f" · {poll.get('job')}" if busy and poll.get("job") else "")
    if busy and isinstance(st, dict):
        line += "".join(f" · {v}" for v in (st.get("label"), st.get("detail")) if v)
        if st.get("frac") is not None:
            line += f" · {st['frac'] * 100:.0f}% done" + (f", about {st['eta']:.0f} s left" if st.get("eta") else "")
    out = [text(line)]
    if stage == "preview_ready" and not busy:
        out += t_review({"project": pr.name, "_brief": True})
    elif stage in ("error", "failed", "stopped") and not busy:
        out.append(text("problem: " + str(pj.get("problem") or "") + "\n" + error_tail(pr)))
    return out


def error_tail(pr):
    logs = sorted(pr.logs.glob("*.log"), key=lambda p: p.stat().st_mtime)
    if not logs:
        return ""
    t = logs[-1].read_text(encoding="utf-8", errors="replace").strip().splitlines()
    return f"{logs[-1].name} (last lines):\n" + "\n".join(t[-40:])


def t_review(a):
    pr = project(a.get("project"))
    ver = pr.state.get("preview_v")
    if not ver:
        return [text("There is no preview yet – render_preview first.")]
    rv = pr.work / f"review_v{ver}"
    ws, _ = prepare_workspace(pr)
    dst = ws / "review"
    if dst.exists():
        shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(rv, dst, ignore=shutil.ignore_patterns("*.mp4"))
    notes = core().saved_notes(pr).strip()
    rep = (rv / "report.md").read_text(encoding="utf-8") if (rv / "report.md").exists() else ""
    head = [f"# Preview v{ver} of “{pr.name}”",
            "## The user's notes (top priority – restate them as asks first, TASK_review.md)",
            notes or "(no notes yet – the user writes them in the app under the preview; ask in the chat if you need them)",
            "", rep[:12000], "",
            "The review material is also in review/ (sheets/sheet_*.jpg = 1 frame per second of the real render). "
            "Frames at any time: check with times=… renders them from episode/."]
    blocks = [text("\n".join(head))]
    sheets = sorted((rv / "sheets").glob("sheet_*.jpg"))
    for p in sheets[: (2 if a.get("_brief") else MAX_IMAGES)]:
        blocks += [text(f"review/sheets/{p.name}"), image_block(p)]
    if len(sheets) > (2 if a.get("_brief") else MAX_IMAGES):
        blocks.append(text(f"({len(sheets)} sheets in review/sheets/ – read_file shows the others)"))
    return blocks


TOOLS = [
    ("projects", "List the user's Vizavi Studio projects and where each one stands.", {}, [], t_projects),
    ("open_project", "Open a project: prepares its workspace on the user's PC and returns the instructions, the "
     "spec and the brief. Call this first. sync=true replaces episode/ with the code of the newest version in the app.",
     {"sync": {"type": "boolean"}}, ["project"], t_open_project),
    ("list_files", "List a folder of the project workspace (input/, episode/, tools/, kit/, templates/, check/, review/…).",
     {"folder": {"type": "string"}}, ["project"], t_list_files),
    ("read_file", "Read a file of the workspace (text; images are shown). Use offset/limit for long files.",
     {"path": {"type": "string"}, "offset": {"type": "integer"}, "limit": {"type": "integer"}}, ["project", "path"], t_read_file),
    ("write_file", "Write a whole file in episode/ (the video's code, PLAN.md, CHANGES.md, transcript files).",
     {"path": {"type": "string"}, "content": {"type": "string"}}, ["project", "path", "content"], t_write_file),
    ("edit_file", "Replace one exact piece of text in an episode/ file (old_text must occur exactly once).",
     {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}},
     ["project", "path", "old_text", "new_text"], t_edit_file),
    ("check", "Render stills and 6 fps motion strips of episode/ on the user's GPU and run the spec, text, camera and "
     "sound checks; returns the report and the images. Without options: the whole video every 4 s + one strip per "
     "scene. scene=NAME: that scene. times='12.5,31': those moments. strip='12-15' or a scene name: motion only. "
     "audio=true also runs audio.py.",
     {"scene": {"type": "string"}, "times": {"type": "string"}, "strip": {"type": "string"},
      "every": {"type": "number"}, "width": {"type": "integer"}, "audio": {"type": "boolean"}}, ["project"], t_check),
    ("wait", "Wait for a running check/retime of this project (up to ~50 s per call) and return its result.",
     {"seconds": {"type": "integer"}}, ["project"], t_wait),
    ("retime", "After writing episode/transcript_clean.txt: put the corrected words on the audio timing (tools/retime.py).",
     {}, ["project"], t_retime),
    ("render_preview", "Send episode/ to Vizavi Studio: it renders the preview (real assets, full checks) as for a zip. "
     "kind='final' renders the final directly – only when the user asked for it.",
     {"note": {"type": "string"}, "kind": {"type": "string", "enum": ["preview", "final"]}}, ["project"], t_render_preview),
    ("status", "Where the project stands in Vizavi Studio; waits up to ~45 s while it renders. When the preview is "
     "ready it includes the review.", {"seconds": {"type": "integer"}}, ["project"], t_status),
    ("review", "The user's notes on the newest preview, the automatic checks (ranked P0–P3) and the preview's frame "
     "sheets. Also copied to review/ in the workspace.", {}, ["project"], t_review),
]


def tool_list():
    out = []
    for name, desc, props, req, _ in TOOLS:
        p = {"project": {"type": "string", "description": "the project's name (projects lists them)"}} if "project" in req else {}
        p.update(props)
        out.append({"name": name, "description": desc,
                    "inputSchema": {"type": "object", "properties": p, "required": req, "additionalProperties": False}})
    return out


def call(name, args):
    fn = next((t[4] for t in TOOLS if t[0] == name), None)
    if fn is None:
        return {"content": [text(f"Unknown tool {name}")], "isError": True}
    try:
        return {"content": fn(args or {}), "isError": False}
    except ToolError as e:
        return {"content": [text(str(e))], "isError": True}
    except Exception as e:
        if _core is not None and isinstance(e, _core.UserMessage):
            return {"content": [text(str(e))], "isError": True}
        log(traceback.format_exc())
        return {"content": [text(f"{name} failed: {type(e).__name__}: {e}")], "isError": True}


# ------------------------------------------------------------------ JSON-RPC over stdio
def handle(msg):
    mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if mid is None:                           # notifications (initialized, cancelled…) need no answer
        return None
    try:
        if method == "initialize":
            want = params.get("protocolVersion")
            res = {"protocolVersion": want if want in PROTOCOLS else PROTOCOLS[0],
                   "capabilities": {"tools": {"listChanged": False}},
                   "serverInfo": {"name": "vizavi-studio", "version": VERSION}, "instructions": INSTRUCTIONS}
        elif method == "ping":
            res = {}
        elif method == "tools/list":
            res = {"tools": tool_list()}
        elif method == "tools/call":
            res = call(params.get("name"), params.get("arguments"))
        elif method in ("resources/list", "prompts/list"):
            res = {method.split("/")[0]: []}
        else:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Method not found: {method}"}}
        return {"jsonrpc": "2.0", "id": mid, "result": res}
    except Exception as e:
        log(traceback.format_exc())
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": f"{type(e).__name__}: {e}"}}


def private_stdin():
    """Our own handle to the protocol stream; fd 0 becomes 'nul'. On Windows a subprocess started anywhere in the app
    code (ffmpeg, nvidia-smi…) duplicates the standard input handle, and duplicating a pipe handle that another thread
    is blocked reading on hangs until that read ends - i.e. the tool call never finishes."""
    fd = os.dup(0)
    nul = os.open(os.devnull, os.O_RDONLY)
    os.dup2(nul, 0)
    os.close(nul)
    if os.name == "nt":
        try:
            import ctypes, msvcrt
            ctypes.windll.kernel32.SetStdHandle(-10, msvcrt.get_osfhandle(0))     # STD_INPUT_HANDLE -> nul
        except Exception:
            pass
    return os.fdopen(fd, "rb", buffering=0)


def main():
    stdin = private_stdin()
    out = sys.stdout.buffer
    lock = threading.Lock()

    def send(obj):
        with lock:
            out.write((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))
            out.flush()

    sys.stdout = sys.stderr                  # nothing else may reach the protocol stream
    log(f"Vizavi Studio connector {VERSION} ready")
    buf = b""
    while True:
        chunk = stdin.read(65536)
        if not chunk:
            break
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            dispatch(line, send)


def dispatch(line, send):
    line = line.strip()
    if not line:
        return
    try:
        msg = json.loads(line.decode("utf-8"))
    except ValueError:
        send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})
        return
    # every request in its own thread: a long tool doesn't block a ping or a second request
    for m in (msg if isinstance(msg, list) else [msg]):
        threading.Thread(target=lambda m=m: (lambda r: r and send(r))(handle(m)), daemon=True).start()


if __name__ == "__main__":
    main()
