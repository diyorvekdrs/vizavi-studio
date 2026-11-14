"""Vizavi Studio engine: a tiny local web server (standard library only) + the UI in an Edge/Chrome
app window. Jobs run one at a time in a worker thread; the page polls /api/poll for live status.
Only listens on 127.0.0.1."""
import json, mimetypes, os, queue, re, secrets, shutil, subprocess, sys, threading, time, traceback, urllib.parse, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .core_paths import is_inside
from . import update as UP
from . import trash as TR
from .version import VERSION, UPDATE_REPO

APP = Path(__file__).resolve().parent.parent
UI = APP / "ui"
PORT = 47613
WIN = os.name == "nt"
NOWIN = 0x08000000 if WIN else 0
INCOMING = APP / ".incoming"
TOKEN_FILE = APP / ".session_token"     # lets a second launch ("Send to") hand files to the running engine
ALIVE_FILE = APP / ".last_alive"        # when the engine last ran: Downloads zips newer than this are caught up on
ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
ALLOWED_ORIGINS = {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}


# ------------------------------------------------------------------ shared state
class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.logs = []                 # (id, text)
        self.next_id = 1
        self.ready = False
        self.busy = False
        self.job = ""
        self.jobs = queue.Queue()
        self.version = 1               # bumps when projects change
        self.device = "?"
        self.toasts = []               # (id, kind, text)
        self.pending = []              # local paths handed over by the launcher / Send to
        self.last_seen = time.time()
        self.core = None
        self.S = None
        from .status import Tracker
        self.tr = Tracker()
        self.proc_ctx = None
        self.token = secrets.token_urlsafe(24)   # every request to the engine must carry it
        self.keys = set()             # jobs queued or running: refuses a double click / the same zip twice
        self.proj_jobs = {}           # project name -> number of queued + running jobs
        self.job_proj = ""            # project of the running job
        self.update = None            # info about a newer release (GitHub), when there is one
        self.restarting = False       # an update is being installed: the engine is about to restart

    def log(self, s):
        with self.lock:
            for line in str(s).splitlines() or [""]:
                self.logs.append((self.next_id, line))
                self.next_id += 1
            if len(self.logs) > 3000:
                self.logs = self.logs[-2000:]

    def toast(self, kind, text):
        with self.lock:
            self.toasts.append((self.next_id, kind, text))
            self.next_id += 1
            self.toasts = self.toasts[-20:]


ST = State()


class Ctx:
    def __init__(self):
        self.proc, self.cancelled = None, False

    def log(self, s):
        ST.log(s)

    def toast(self, kind, text):
        ST.toast(kind, text)

    def progress(self, frac=None, label=None, detail=None, until=None, eta=None):
        ST.tr.update(frac=frac, label=label, detail=detail, until=until, eta=eta)
        if label:
            ST.log("— " + label)
        if detail:
            m = re.search(r"\bon (GPU[^·|]*|CPU[^·|]*|Chromium)", detail)
            if m:
                ST.device = m[1].strip()


CTX = Ctx()


def submit(name, fn, *args, project=None, key=None):
    """Queue a job. `key` refuses an identical job that is already queued or running (double click, same zip
    twice). `project` lets the UI show which project is busy and stops it being deleted meanwhile.
    Returns False when it was refused as a duplicate."""
    with ST.lock:
        dup = bool(key) and key in ST.keys
        if not dup:
            if key:
                ST.keys.add(key)
            if project:
                ST.proj_jobs[project] = ST.proj_jobs.get(project, 0) + 1
    if dup:
        ST.log(f"Already queued: {name}")
        return False
    if ST.busy:
        ST.log(f"Queued: {name}")
    ST.jobs.put((name, fn, args, project, key))
    return True


def worker():
    while True:
        name, fn, args, project, key = ST.jobs.get()
        ST.busy, ST.job, ST.job_proj = True, name, project or ""
        CTX.cancelled = False
        ST.tr.start(name)
        try:
            res = fn(*args)
            after_job(res)
        except Exception as e:
            core = ST.core
            if core and isinstance(e, core.UserMessage):
                ST.log("\u26a0 " + str(e)); ST.toast("warn", str(e))
            else:
                ST.log("ERROR:\n" + traceback.format_exc()); ST.toast("error", f"{name} failed: {e}")
        finally:
            snap = ST.tr.snapshot()
            ST.last_job = {"name": name, "seconds": snap["elapsed"] if snap else 0}
            ST.tr.reset()
            CTX.cancelled = False
            with ST.lock:
                if key:
                    ST.keys.discard(key)
                if project:
                    n = ST.proj_jobs.get(project, 0) - 1
                    if n > 0:
                        ST.proj_jobs[project] = n
                    else:
                        ST.proj_jobs.pop(project, None)
            ST.busy, ST.job, ST.job_proj = False, "", ""
            ST.version += 1


def after_job(res):
    core = ST.core
    if isinstance(res, tuple):                      # new project / redo transcript -> (project, zip)
        pr, z = res
        ST.focus = pr.name
        ST.toast("move", f"\u201c{pr.name}\u201d: request package ready \u2013 copy the message and drag the zip into Claude.")
        reveal(z)
    elif isinstance(res, dict):
        pr = res["episode"]
        ST.focus = pr.name
        k = res["kind"]
        if k == "preview":
            ST.toast("move", f"\u201c{pr.name}\u201d: preview ready \u2013 watch it, then approve or send the review zip.")
            reveal(res["zip"])
        elif k == "error":
            ST.toast("error", f"\u201c{pr.name}\u201d: the render failed \u2013 press Retry render, or send the error zip to Claude.")
            if res.get("zip"):
                reveal(res["zip"])
        elif k == "stopped":
            ST.toast("warn", f"\u201c{pr.name}\u201d: stopped \u2013 press Retry render to continue.")
        elif k == "final":
            ST.toast("done", f"\u201c{pr.name}\u201d: final files ready.")
            reveal(res["video"])


# ------------------------------------------------------------------ OS helpers
def reveal(path):
    path = Path(path)
    try:
        if WIN:
            subprocess.Popen(f'explorer /select,"{path}"')
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])
    except Exception:
        pass


def open_path(path):
    try:
        if WIN:
            os.startfile(str(path))
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


def open_window(url):
    """Edge (built into Windows) or Chrome in app mode = a clean app window; else the default browser."""
    cands = []
    if WIN:
        for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
            if base:
                cands += [Path(base) / "Microsoft/Edge/Application/msedge.exe", Path(base) / "Google/Chrome/Application/chrome.exe"]
    else:
        for n in ("microsoft-edge", "google-chrome", "chromium", "chromium-browser"):
            p = shutil.which(n)
            if p:
                cands.append(Path(p))
    for exe in cands:
        if exe.exists():
            try:
                subprocess.Popen([str(exe), f"--app={url}", f"--user-data-dir={APP / '.ui_profile'}",
                                  "--window-size=1360,880", "--no-first-run", "--no-default-browser-check",
                                  "--disable-background-timer-throttling", "--disable-renderer-backgrounding",
                                  "--disable-features=Translate,msEdgeSidebarV2"], creationflags=NOWIN)
                return True
            except Exception:
                continue
    import webbrowser
    webbrowser.open(url)
    return False


# ------------------------------------------------------------------ setup / watcher threads
def detect_hw(force_apply=False):
    from . import hw
    ST.hw = hw.detect(APP)
    ST.hw_lines = hw.explain(ST.hw)
    if ST.core:
        ST.core.HW_INFO = ST.hw
        if ST.core.apply_hw_profile(ST.S, ST.hw["profile"], force=force_apply):
            ST.core.save_settings(ST.S)
            ST.log("Settings fitted to this PC.")
    return ST.hw


def setup():
    from . import deps
    try:
        ST.phase = "Checking this PC"
        h = detect_hw()
        ST.log("This PC: " + " | ".join(ST.hw_lines))
        ST.phase = "Installing components"
        warns = list(deps.ensure_cached(ST.log, prof=h["profile"]))
        ST.phase = "Starting"
        sys.path.insert(0, str(APP))
        from studio import core
        ST.core = core
        ST.S = core.load_settings()
        core.HW_INFO = h
        if core.apply_hw_profile(ST.S, h["profile"]):
            core.save_settings(ST.S); ST.log("Settings fitted to this PC.")
        if core.SETTINGS_PROBLEM:
            warns.append(core.SETTINGS_PROBLEM)
        for name in core.repair_stuck(ST.S):      # cut off by a crash / closing the app: offer Retry, don't hang
            ST.log(f"\u201c{name}\u201d was cut off last time (app closed or crashed) \u2013 open it and press Retry render.")
        ST.warnings = warns
        for w in warns:
            ST.log("\u26a0 " + w); ST.toast("warn", w)
        ST.ready = True
        ST.log(f"Ready. (Vizavi Studio {VERSION})")
        update_result()
        threading.Thread(target=update_checker, daemon=True).start()
        threading.Thread(target=housekeeping, daemon=True).start()
        clean_incoming()
        threading.Thread(target=watcher, daemon=True).start()
    except Exception:
        ST.phase = "failed"
        ST.log("Setup failed:\n" + traceback.format_exc())


# ------------------------------------------------------------------ updates
def update_result():
    """after an update (or undo) the helper leaves result.json: tell the user how it went"""
    f = APP / ".update" / "result.json"
    try:
        r = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    try:
        f.unlink()
    except OSError:
        pass
    if r.get("ok") and r.get("undo"):
        msg = f"Update undone – back on Vizavi Studio {r.get('to')}."
        ST.log(msg); ST.toast("done", msg)
    elif r.get("ok"):
        msg = f"Updated to Vizavi Studio {r.get('to')}."
        ST.log(msg); ST.toast("done", msg)
    else:
        msg = (f"The update to {r.get('to') or 'the new version'} did not work ({r.get('error')}) – "
               f"you are still on {VERSION}. Details: .update/update.log")
        ST.log("\u26a0 " + msg); ST.toast("warn", msg)


def check_update(quiet=True):
    try:
        info = UP.check(UPDATE_REPO, VERSION)
    except Exception as e:
        if not quiet:
            raise ST.core.UserMessage(f"GitHub didn't answer (tried 3 times: {type(e).__name__}). Check the internet "
                                      "connection and try again in a minute.")
        return None
    ST.update = info if info["newer"] else None
    if ST.update and getattr(ST, "_told_update", None) != info["latest"]:
        ST._told_update = info["latest"]
        ST.log(f"Update available: Vizavi Studio {info['latest']} (you have {VERSION}).")
    ST.version += 1
    return info


def update_checker():
    """quietly looks for a new release at start and every 6 hours (Settings can turn it off)"""
    time.sleep(5)
    while True:
        if ST.S and ST.S.get("check_updates", True):
            check_update()
        time.sleep(6 * 3600)


def housekeeping():
    """Recently deleted older than 30 days goes for good; once a day a small backup of styles and project texts"""
    from . import trash as TR
    time.sleep(20)
    while True:
        try:
            S, core = ST.S, ST.core
            TR.migrate_old(S)
            TR.purge_old(S, ST.log)
            TR.daily_backup(S, latest_code=lambda d: (core.latest_code_dir(core.Project(d)) or [None])[0], log=ST.log)
        except Exception as e:
            ST.log(f"Housekeeping skipped: {e}")
        time.sleep(3 * 3600)


def update_job():
    if not ST.jobs.empty():
        raise ST.core.UserMessage("Finish the queued jobs first – the update restarts Vizavi Studio.")
    try:
        info = check_update(quiet=False)
    except ST.core.UserMessage:
        # GitHub didn't answer this time, but the bar was shown from an earlier check: that release is still good
        # (the download is verified against its checksum anyway)
        info = ST.update
        if not info:
            raise
        ST.log(f"GitHub is slow to answer – using the release found earlier ({info['latest']}).")
    if not info or not info.get("newer"):
        raise ST.core.UserMessage(f"You already have the newest version ({VERSION}).")
    CTX.progress(0, f"Updating to Vizavi Studio {info['latest']}", until=0.9)
    new = UP.stage(info, APP, progress=lambda f: CTX.progress(0.9 * f, detail=f"downloading {f * 100:.0f}%"), log=ST.log)
    CTX.progress(0.95, "Restarting with the new version…")
    restart_with(lambda: UP.launch(APP, new, sys.executable, ST.token, PORT))


def restart_with(start_helper):
    ST.restarting = True
    ST.log("Vizavi Studio restarts now – this window reconnects by itself.")
    write_alive()
    start_helper()
    threading.Timer(2.0, lambda: os._exit(0)).start()


def clean_incoming():
    if INCOMING.exists():
        for d in INCOMING.iterdir():
            try:
                if time.time() - d.stat().st_mtime > 24 * 3600:
                    shutil.rmtree(d, ignore_errors=True)
            except OSError:
                pass


def read_alive():
    try:
        return float(ALIVE_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def write_alive():
    try:
        ALIVE_FILE.write_text(str(time.time()), encoding="utf-8")
    except OSError:
        pass


def watcher():
    """Claude's zips (<name>__preview_vN.zip / __final_vN.zip) are picked up from Downloads once complete.
    Only genuine Vizavi packages for projects that exist HERE are opened on their own (anything else is
    reported and left for you to drag in). Zips that arrived while the app was closed are caught up at start."""
    seen, queued, told = {}, set(), set()
    rx = re.compile(r"__(preview|final)_v\d+")
    since = read_alive() or (time.time() - 6 * 3600)      # first ever start: look back 6 hours
    last_beat = 0.0
    while True:
        try:
            S, core = ST.S, ST.core
            now = time.time()
            if now - last_beat > 30:
                write_alive(); last_beat = now
            d = Path(S["downloads_dir"])
            if S.get("watch_downloads") and d.exists():
                done_ids = None
                for f in d.glob("*.zip"):
                    if not rx.search(f.stem):
                        continue
                    try:
                        stt = f.stat()
                    except OSError:
                        continue
                    key, sig = str(f), (stt.st_size, stt.st_mtime)
                    prev = seen.get(key); seen[key] = sig
                    if stt.st_mtime < since - 60 or (key, sig) in queued or prev != sig:
                        continue                  # older than the last run / already handled / still being written
                    queued.add((key, sig))
                    if done_ids is None:
                        done_ids = set()
                        for ep in core.list_projects(S):
                            done_ids.update(ep.state.get("processed", []))
                    old_id, new_id = core.zip_ids(f)
                    if new_id in done_ids or old_id in done_ids:
                        continue
                    try:
                        man = core.read_manifest(f)
                    except core.UserMessage:
                        continue                  # not a Vizavi package at all
                    name = man.get("episode")
                    if man.get("kind") not in ("preview", "final") or man.get("guessed") or man.get("app") != "vizavi-studio":
                        if key not in told:
                            told.add(key)
                            ST.log(f"Left {f.name} alone: it is not a package from Claude for Vizavi Studio. "
                                   f"If it is, drag it onto the window.")
                        continue
                    if not core.project_exists(S, name):
                        if key not in told:
                            told.add(key)
                            msg = (f"{f.name} in Downloads is for a project called \u201c{name}\u201d, which isn't here. "
                                   f"If it is yours, drag the zip onto the window.")
                            ST.log(msg); ST.toast("warn", msg)
                        continue
                    ST.log(f"Found {f.name} in Downloads")
                    submit(f"Process {f.name}", core.process_zip, f, S, CTX,
                           project=core.safe_name(str(name)), key="zip:" + new_id)
        except Exception as e:
            ST.log(f"(Downloads watcher: {e})")
        time.sleep(3)


IDLE_EXIT_S = 15 * 60


def idle_exit():
    """quit when no window has been open for a while and nothing is running.
    A PC that slept (or a window the browser froze while minimised) is not 'no window': after a sleep the clock
    jumps, so the wait starts again instead of quitting under a window that is about to wake up."""
    last = time.time()
    while True:
        time.sleep(10)
        now = time.time()
        if now - last > 60:                  # we were asleep: give the windows time to poll again
            ST.last_seen = now
        last = now
        if now - ST.last_seen > IDLE_EXIT_S and not ST.busy and ST.jobs.empty():
            write_alive()
            os._exit(0)


# ------------------------------------------------------------------ API
def report_info(pr):
    """flags / time estimate / per-scene cost of the ready preview (written by make_report), {} when absent"""
    ver = pr.state.get("preview_v")
    if not ver:
        return {}
    try:
        return json.loads((pr.work / f"review_v{ver}" / "report.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def project_json(pr, full=False):
    core = ST.core
    st = pr.state
    stage = st.get("stage", "new")
    hist = st.get("history") or []
    out = {"name": pr.name, "stage": stage, "stage_text": core.STAGE_TEXT.get(stage, stage),
           "preset": st.get("preset") or pr.order.get("preset"), "duration": st.get("duration"),
           "updated": (hist or [[""]])[-1][0], "thumb": bool(thumb_source(pr)),
           "busy": ST.proj_jobs.get(pr.name, 0) > 0}
    if not full:
        return out
    o = pr.order
    vs = core.OD.variants(o)
    out.update(size=f"{vs[0]['w']}×{vs[0]['h']}", fps=o["fps"], variants=[v["id"] for v in vs], formats=o["formats"],
               order_size=list(o["size"]), order_variants=list(o.get("variants") or []), audio_export=o["audio"].get("export"),
               words=st.get("words"), transcriber=st.get("transcriber"), timing=st.get("timing"),
               transcript_source=st.get("transcript_source"),
               last_kind=st.get("last_kind"), last_zip=Path(st["last_zip"]).name if st.get("last_zip") else None,
               preview_v=st.get("preview_v"), history=hist[-8:],
               stop_reason=st.get("stop_reason"), failed_kind=st.get("failed_kind"),
               final_long_side=st.get("final_long_side") or None,
               problem=(hist[-1][2] if hist and stage in ("failed", "error", "stopped") and len(hist[-1]) > 2 else None))
    prev = st.get("last_preview")
    out["preview"] = media_url(prev) if prev and Path(prev).exists() else None
    rep = report_info(pr)
    cost = rep.get("scene_cost") or {}
    out["flags"] = [str(f) for f in (rep.get("flags") or [])][:60]
    iss = rep.get("issues")
    if not isinstance(iss, list):            # a report made by an older version: rank its plain flags now
        iss = core.vc.ranked(out["flags"])
    out["issues"] = [{"rank": str(i.get("rank") or "P2"), "text": str(i.get("text") or "")} for i in iss
                     if isinstance(i, dict)][:80]
    out["est_final_min"] = rep.get("est_final_min")
    out["scene_cost"] = [[k, round(v, 1)] for k, v in sorted(cost.items(), key=lambda kv: -kv[1])][:10] \
        if isinstance(cost, dict) else []
    try:
        out["notes_saved"] = core.saved_notes(pr)
    except Exception:
        out["notes_saved"] = ""
    outs = []
    if pr.output.exists():
        for f in sorted(pr.output.iterdir()):
            if f.is_file() and "__preview_v" not in f.name:
                outs.append({"name": f.name, "mb": round(f.stat().st_size / 1e6, 1),
                             "url": media_url(f) if f.suffix.lower() in (".mp4", ".webm", ".mov") else None})
            elif f.is_dir() and f.name.endswith("__png"):
                outs.append({"name": f.name + "/", "mb": None, "url": None})
    out["outputs"] = outs
    kind = st.get("last_kind", "request")
    out["chat_message"] = (f"Make the video for my Vizavi Studio project “{pr.name}”." if not st.get("preview_v") else
                           f"I wrote my notes on preview v{st.get('preview_v')} of “{pr.name}” in Vizavi Studio – "
                           "review them and make the next version.")
    out["message"] = core.claude_message(kind if kind in ("request", "review", "error") else "request", pr.name,
                                         st.get("preview_v"))
    tc = pr.src / "transcript_claude.md"
    al = pr.src / "script_alignment.md"
    out["transcript"] = tc.read_text(encoding="utf-8", errors="replace")[:20000] if tc.exists() else None
    out["alignment"] = al.read_text(encoding="utf-8", errors="replace")[:6000] if al.exists() else None
    sc = pr.src / "script.txt"
    out["script"] = sc.read_text(encoding="utf-8", errors="replace") if sc.exists() else ""
    out["has_narration"] = bool(pr.narration())
    ad = pr.src / "assets"
    out["assets"] = [{"name": f.name, "mb": round(f.stat().st_size / 1e6, 1)} for f in sorted(ad.iterdir())
                     if f.is_file()] if ad.exists() else []
    tgt = core.retry_target(pr)
    out["retry"] = f"{tgt[0]} v{tgt[1]}" if tgt else None
    out["has_code"] = bool(core.latest_code_dir(pr))
    return out


def media_url(p):
    return "/media?path=" + urllib.parse.quote(str(p))


def thumb_source(pr):
    st = pr.state
    for p in (st.get("last_final"), st.get("last_preview")):
        if p and Path(p).exists() and Path(p).suffix.lower() in (".mp4", ".webm", ".mov"):
            return Path(p)
    return None


THUMB_LOCK = threading.Lock()


def make_thumb(pr):
    src = thumb_source(pr)
    if not src:
        return None
    th = pr.root / ".thumb.jpg"
    with THUMB_LOCK:                       # one ffmpeg at a time, never two for the same card
        if th.exists() and th.stat().st_mtime >= src.stat().st_mtime:
            return th
        import vz_analysis as va
        d = va.media_info(src).get("duration") or 2
        subprocess.run([va.ffmpeg_exe(), "-v", "error", "-y", "-ss", f"{d * 0.35:.2f}", "-i", str(src), "-frames:v", "1",
                        "-vf", "scale=320:-2", "-q:v", "4", str(th)], creationflags=NOWIN, capture_output=True,
                       stdin=subprocess.DEVNULL, timeout=60)
    return th if th.exists() else None


def classify(paths):
    core = ST.core
    paths = [Path(p) for p in paths if Path(p).exists()]
    out = {"zips": [], "narration": None, "music": None, "assets": [], "script": ""}
    files = []
    for p in paths:
        if p.is_dir():
            media = core.IMAGE_EXT | core.VIDEO_EXT | core.FONT_EXT | core.AUDIO_EXT
            fl = [f for f in sorted(p.rglob("*")) if f.is_file() and f.suffix.lower() in media]
            fonts = [f for f in fl if f.suffix.lower() in core.FONT_EXT]
            rest = [f for f in fl if f not in fonts]
            if len(fonts) > 8:
                pick = [f for f in fonts if re.search(r"regular|medium|semibold|bold", f.stem, re.I)
                        and not re.search(r"italic|oblique|condensed|compressed|expanded", f.stem, re.I)]
                pick = sorted(pick, key=lambda f: (0 if "display" in f.stem.lower() else 1 if "text" in f.stem.lower() else 2,
                                                   f.stem))[:8] or fonts[:8]
                ST.log(f"{p.name}: {len(fonts)} font files – using {len(pick)}")
                fonts = pick
            out["assets"] += [str(f) for f in fonts + rest[:40]]
        else:
            files.append(p)
    for p in files:
        ext = p.suffix.lower()
        if ext == ".zip":
            out["zips"].append(str(p))
        elif ext in core.AUDIO_EXT and not out["narration"]:
            out["narration"] = str(p)
        elif ext in core.AUDIO_EXT and not out["music"]:
            out["music"] = str(p)
        elif ext in {".txt", ".md"}:
            out["script"] = p.read_text(encoding="utf-8", errors="replace")
        else:
            out["assets"].append(str(p))
    return out


def meta():
    core = ST.core
    OD = core.OD
    S = ST.S
    return {
        "sizes": {k: list(v) for k, v in OD.SIZES.items()}, "extra_variants": list(OD.EXTRA_VARIANTS),
        "fps": OD.FPS, "duration": OD.DURATION, "audio_export": OD.AUDIO_EXPORT, "captions": OD.CAPTIONS,
        "formats": OD.FORMATS, "engines": OD.ENGINES, "review": OD.REVIEW, "loudness": OD.LOUDNESS,
        "safe_area": OD.SAFE_AREA, "kinds": OD.KINDS, "langs": OD.LANGS, "styles": list(OD.STYLES), "brands": OD.list_brands(),
        "presets": list(OD.PRESETS) + [k for k in S.get("user_presets", {}) if k not in OD.PRESETS],
        "preset_cards": preset_cards(S), "style_desc": OD.STYLES, "looks": list(OD.looks().values()),
        "saved_styles": core.list_styles(S), "claude_link": claude_link_status(), "trash": TR.list_trash(S), "trash_days": TR.KEEP_DAYS,
        "version": VERSION, "can_undo_update": UP.has_backup(APP), "storage": storage_info(S),
        "last_preset": S.get("last_preset"), "hw": getattr(ST, "hw_lines", []),
        "warnings": getattr(ST, "warnings", []),
        "settings": {k: S.get(k) for k in ("standing_rules", "watch_downloads", "auto_play_preview", "precise_timing",
                                           "uzbek_model", "projects_dir", "downloads_dir", "whisper_model",
                                           "light_effects", "check_updates")},
    }


def claude_link_status():
    try:
        from . import claude_link
        return claude_link.status()
    except Exception as e:
        return {"connected": False, "current": False, "path": "", "problem": str(e)}


def preset_cards(S):
    """what each preset makes, for the cards in New project: size, fps, length, captions"""
    OD = ST.core.OD
    out = {}
    for name in list(OD.PRESETS) + [k for k in S.get("user_presets", {}) if k not in OD.PRESETS]:
        try:
            o = OD.from_preset(name, S.get("user_presets"))
        except Exception:
            continue
        w, h = o["size"]
        bits = [f"{w}×{h}", f"{o['fps']} fps"]
        d = o["duration"]
        bits.append({"narration": "as long as the voice", "music": "as long as the music"}.get(d["mode"], f"{d['seconds']:g} s"))
        if str(o.get("captions", "none")).startswith("burned"):
            bits.append("captions")
        if o.get("alpha"):
            bits.append("transparent")
        out[name] = {"w": w, "h": h, "line": " · ".join(bits), "user": name not in OD.PRESETS}
    return out


SETTING_KEYS = ("standing_rules", "watch_downloads", "auto_play_preview", "precise_timing", "uzbek_model",
                "projects_dir", "downloads_dir", "whisper_model", "light_effects", "check_updates")


def need_project(a):
    core, S = ST.core, ST.S
    name = a.get("name")
    if not isinstance(name, str) or not name.strip():
        raise core.UserMessage("No project was given.")
    pr = core.Project.open(name, S, create=False)
    if pr is None:
        raise core.UserMessage(f"Project “{name}” no longer exists.")
    return pr


def queue_job(label, fn, *args, pr=None, key=None):
    if not submit(label, fn, *args, project=pr.name if pr else None, key=key):
        raise ST.core.UserMessage(f"{label} is already queued or running.")


def idle_project(pr, what):
    if ST.proj_jobs.get(pr.name, 0) > 0:
        raise ST.core.UserMessage(f"“{pr.name}” is being processed – {what} when it has finished (or press Stop).")


def review_job(pr, ver, notes):
    core = ST.core
    z = core.build_review_zip(pr, ver, notes, CTX)
    ST.log(f"Review package for {pr.name} v{ver} is ready.")
    ST.toast("move", f"“{pr.name}”: review package ready – copy the message and drag the zip into Claude.")
    ST.focus = pr.name
    reveal(z)


def storage_info(S):
    """where the program, the speech models and the projects are, with the free space on each drive"""
    def free(p):
        try:
            return round(shutil.disk_usage(Path(p).anchor or p).free / 1e9, 1)
        except OSError:
            return None
    models = S.get("models_dir") or str(Path.home() / ".cache" / "huggingface")
    return [{"what": w, "path": str(p), "free_gb": free(p)} for w, p in
            (("Program", APP), ("Speech models", models), ("Projects", S.get("projects_dir") or ""))]


def act(a):
    core, S = ST.core, ST.S
    kind = a.get("action")
    if kind == "open_projects":
        d = Path(S["projects_dir"]); d.mkdir(parents=True, exist_ok=True); open_path(d)
        return {}
    if kind == "open_claude":
        import webbrowser; webbrowser.open("https://claude.ai/new")
        return {}
    if kind == "stop":
        if not ST.busy:
            ST.toast("warn", "Nothing is running.")
            return {}
        CTX.cancelled = True
        p = CTX.proc
        if p and p.poll() is None:
            if WIN:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True, creationflags=NOWIN)
            else:
                p.kill()
        ST.log("Stopped by you.")
        return {}
    if kind == "check_update":
        info = check_update(quiet=False)
        return {"newer": bool(info and info.get("newer")), "latest": info and info.get("latest"), "current": VERSION}
    if kind == "apply_update":
        if ST.busy or not ST.jobs.empty():
            raise core.UserMessage("A job is running – update when it has finished.")
        queue_job("Update Vizavi Studio", update_job, key="update")
        return {}
    if kind == "undo_update":
        if ST.busy or not ST.jobs.empty():
            raise core.UserMessage("A job is running – try again when it has finished.")
        if not UP.has_backup(APP):
            raise core.UserMessage("There is no update to undo.")
        restart_with(lambda: UP.restore_launch(APP, sys.executable, ST.token, PORT))
        return {"restarting": True}
    if kind in ("restore_deleted", "purge_deleted"):
        tid = a.get("id")
        try:
            if kind == "restore_deleted":
                what, name = TR.restore(S, tid)
                ST.log(f"Restored {what} “{name}” from Recently deleted")
                ST.version += 1
                return {"kind": what, "name": name}
            TR.purge(S, tid)
        except TR.TrashError as e:
            raise core.UserMessage(str(e))
        ST.version += 1
        return {}
    if kind in ("connect_claude", "disconnect_claude"):
        from . import claude_link
        try:
            done = claude_link.connect() if kind == "connect_claude" else claude_link.disconnect()
        except Exception as e:
            raise core.UserMessage(f"Couldn't change the Claude app's settings: {e}")
        ST.log(("Connected to" if kind == "connect_claude" else "Disconnected from") + " the Claude app: " + ", ".join(done))
        return {"done": done, "status": claude_link.status()}
    if kind == "add_rule":                   # a note worth keeping for every project -> My rules
        rule = " ".join(str(a.get("text") or "").split()).strip(" •-")
        if not rule:
            raise core.UserMessage("Write the rule first.")
        if len(rule) > 500:
            raise core.UserMessage("Keep a rule under 500 characters.")
        cur = (S.get("standing_rules") or "").rstrip()
        if rule.lower() in [l.strip(" •-").lower() for l in cur.splitlines()]:
            return {"added": False}
        S["standing_rules"] = (cur + "\n" if cur else "") + rule
        core.save_settings(S)
        ST.version += 1
        return {"added": True}
    if kind == "open_backups":
        d = TR.backups_dir(S)
        if not any(d.glob("*.zip")) if d.exists() else True:
            TR.daily_backup(S, latest_code=lambda x: (core.latest_code_dir(core.Project(x)) or [None])[0], log=ST.log)
        d.mkdir(parents=True, exist_ok=True)
        open_path(d)
        return {}
    if kind == "delete_style":
        core.delete_style(S, a.get("id"))
        ST.version += 1
        return {}
    if kind == "recheck":
        from . import deps
        def recheck():
            h = detect_hw(force_apply=True)
            ST.log("This PC: " + " | ".join(ST.hw_lines))
            ST.warnings = deps.ensure_cached(ST.log, force=True, prof=h["profile"])
            for w in ST.warnings:
                ST.log("⚠ " + w)
            ST.log("Components checked." if not ST.warnings else "Components checked – see the warnings above.")
        queue_job("Check components", recheck, key="recheck")
        return {}
    if kind not in ("approve", "retry", "add_assets", "redo", "notes", "save_notes", "delete", "open_folder",
                    "reveal_zip", "open_file", "reveal_output", "set_final_size", "save_style", "set_order"):
        raise core.UserMessage("Unknown action.")
    pr = need_project(a)
    if kind == "approve":
        if pr.state.get("stage") != "preview_ready":
            raise core.UserMessage(f"“{pr.name}” has no preview waiting for approval.")
        queue_job(f"Final of {pr.name}", core.approve_preview, pr, S, CTX, pr=pr, key=f"final:{pr.name}")
    elif kind == "retry":
        tgt = core.retry_target(pr)
        if not tgt:
            raise core.UserMessage(f"“{pr.name}” has nothing to retry yet.")
        idle_project(pr, "retry")
        queue_job(f"Retry {tgt[0]} v{tgt[1]} of {pr.name}", core.retry_render, pr, S, CTX, pr=pr,
                  key=f"retry:{pr.name}")
    elif kind == "add_assets":
        idle_project(pr, "add files")
        paths = [p for p in (a.get("paths") or []) if isinstance(p, str)]
        return {"added": core.add_assets(pr, paths, CTX)}
    elif kind == "redo":
        idle_project(pr, "redo the transcript")
        queue_job(f"Redo transcript of {pr.name}", core.redo_transcript, pr, str(a.get("text") or ""), S, CTX, pr=pr,
                  key=f"redo:{pr.name}")
    elif kind == "save_style":                       # the look of this video, for new projects
        info = core.save_style(pr, str(a.get("style_name") or ""), str(a.get("note") or ""), S, CTX)
        ST.version += 1
        return {"style": {k: info[k] for k in ("id", "name")}}
    elif kind == "set_order":                        # size / extra versions / sound / fps after the project was made
        idle_project(pr, "change the size or sound")
        said = core.change_order(pr, {k: a.get(k) for k in core.ORDER_CHANGE_KEYS}, CTX, who="you")
        ST.version += 1
        return {"changed": said}
    elif kind == "set_final_size":                   # longest side of the final video; 0 = as ordered
        try:
            n = int(a.get("value") or 0)
        except (TypeError, ValueError):
            n = -1
        if n != 0 and not 320 <= n <= 8192:
            raise core.UserMessage("Choose a final size between 320 and 8192 pixels.")
        idle_project(pr, "change the final size")
        pr.state["final_long_side"] = n or None
        pr.save()
    elif kind == "save_notes":                       # cheap auto-save while typing: only the notes file
        ver = pr.state.get("preview_v")
        if ver:
            core.write_notes(pr, int(ver), str(a.get("text") or ""))
        return {}
    elif kind == "notes":
        ver = pr.state.get("preview_v")
        if not ver:
            raise core.UserMessage(f"“{pr.name}” has no preview yet, so there is nothing to review.")
        idle_project(pr, "build the review package")
        queue_job(f"Review package of {pr.name}", review_job, pr, int(ver), str(a.get("text") or ""), pr=pr,
                  key=f"review:{pr.name}")
        return {"message": core.claude_message("review", pr.name, ver) + " My notes are in review/USER_NOTES.md."}
    elif kind == "delete":
        idle_project(pr, "delete it")
        where = core.delete_project(pr, S)
        ST.log(f"Deleted project “{pr.name}” → {where}")
    elif kind == "open_folder":
        pr.output.mkdir(parents=True, exist_ok=True)
        open_path(pr.output if any(pr.output.glob("*")) else pr.root)
    elif kind == "reveal_zip":
        z = pr.state.get("last_zip")
        if z and Path(z).exists():
            reveal(z)
        else:
            raise core.UserMessage("That zip is no longer there – it is rebuilt when you start the step again.")
    elif kind == "open_file":
        p = Path(a["path"]) if a.get("path") else None
        if p and p.exists() and is_inside(p, S["projects_dir"]):
            open_path(p)
    elif kind == "reveal_output":
        f = pr.output / Path(str(a.get("file") or "")).name
        if f.exists():
            reveal(f)
    ST.version += 1
    return {}


def read_json_body(handler):
    raw = handler.body()
    if not raw:
        return {}
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("expected an object")
    return data


def check_settings(core, S, data):
    """validated copy of the settings the UI may change"""
    out = {}
    for k, v in data.items():
        if k not in SETTING_KEYS:
            continue
        if k in ("watch_downloads", "auto_play_preview", "precise_timing", "light_effects", "check_updates"):
            out[k] = bool(v)
        elif k in ("projects_dir", "downloads_dir"):
            v = str(v or "").strip().strip('"')
            if not v:
                raise core.UserMessage("The folder cannot be empty.")
            p = Path(os.path.expandvars(os.path.expanduser(v)))
            try:
                p.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                raise core.UserMessage(f"Cannot use that folder: {e}")
            if k == "projects_dir" and str(p) != str(S.get("projects_dir")) and (ST.busy or not ST.jobs.empty()):
                raise core.UserMessage("Wait until the running job has finished before changing the projects folder.")
            out[k] = str(p)
        else:
            out[k] = str(v or "")
    return out


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "Vizavi"
    sys_version = ""

    def log_message(self, *a):
        pass

    # ---------------------------------------------------------- responses
    def send_json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        if code >= 400:
            self.send_header("Connection", "close")     # a request body may still be unread
            self.close_connection = True
        self.end_headers()
        self.wfile.write(b)

    def send_page(self, text, code=200):
        b = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        if code >= 400:
            self.send_header("Connection", "close"); self.close_connection = True
        self.end_headers()
        self.wfile.write(b)

    def body(self):
        n = max(0, int(self.headers.get("Content-Length") or 0))
        return self.rfile.read(n) if n else b""

    def send_file(self, p, ctype=None, cache="no-cache"):
        p = Path(p)
        size = p.stat().st_size
        ctype = ctype or mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        start, end, code = 0, size - 1, 200
        rng = (self.headers.get("Range") or "").strip()
        m = re.fullmatch(r"bytes=(\d*)-(\d*)", rng)
        if m and (m[1] or m[2]):                       # one simple range; anything fancier gets the whole file
            if m[1]:
                start = int(m[1])
                end = min(int(m[2]), size - 1) if m[2] else size - 1
            else:
                start, end = max(0, size - int(m[2])), size - 1
            if start >= size or start > end:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            code = 206
        try:
            f = open(p, "rb")
        except OSError:
            return self.send_json({"error": "file not available"}, 404)
        with f:
            self.send_response(code)
            if code == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(max(0, end - start + 1)))
            self.send_header("Cache-Control", cache)
            self.end_headers()
            f.seek(start)
            left = end - start + 1
            while left > 0:
                chunk = f.read(min(1 << 20, left))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                    self.close_connection = True
                    return
                left -= len(chunk)

    # ---------------------------------------------------------- who may talk to the engine
    def cookie_token(self):
        for part in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == "vz":
                return v
        return ""

    def host_ok(self):
        """Host + Origin must be this engine itself: stops other web pages (and DNS rebinding) from using it"""
        if (self.headers.get("Host") or "").lower() not in ALLOWED_HOSTS:
            self.send_json({"error": "forbidden host"}, 403)
            return False
        origin = self.headers.get("Origin")
        if origin and origin not in ALLOWED_ORIGINS:
            self.send_json({"error": "forbidden origin"}, 403)
            return False
        return True

    def has_token(self):
        tok = (self.headers.get("X-VZ-Token") or self.cookie_token()).encode("utf-8", "replace")
        return secrets.compare_digest(tok, ST.token.encode())

    def authed(self):
        if not self.host_ok():
            return False
        if not self.has_token():
            self.send_json({"error": "unauthorized"}, 401)
            return False
        return True

    # ---------------------------------------------------------- GET
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        try:
            if not self.host_ok():
                return
            if u.path == "/api/ping":
                return self.send_json({"app": "vizavi", "ok": True})
            if u.path in ("/", "/index.html"):
                t = q.get("t")
                if t and secrets.compare_digest(t.encode(), ST.token.encode()):     # first load: hand out the cookie
                    self.send_response(302)
                    self.send_header("Set-Cookie", f"vz={ST.token}; Path=/; HttpOnly; SameSite=Strict")
                    self.send_header("Location", "/")
                    self.send_header("Content-Length", "0")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    return
                if not self.has_token():
                    return self.send_page(
                        "<!doctype html><meta charset=utf-8><title>Vizavi Studio</title>"
                        "<body style='font:16px system-ui;background:#111;color:#eee;padding:40px'>"
                        "<h2>This window is out of date</h2><p>Vizavi Studio was restarted. Close this window and "
                        "open Vizavi Studio again from the desktop or Start menu.</p></body>", 401)
                return self.send_file(UI / "index.html", "text/html; charset=utf-8")
            if not self.has_token():
                return self.send_json({"error": "unauthorized"}, 401)
            if u.path.startswith("/ui/"):
                f = (UI / u.path[4:]).resolve()
                if is_inside(f, UI) and f.is_file():
                    return self.send_file(f)
                return self.send_json({"error": "not found"}, 404)
            if u.path == "/fonts/" + Path(u.path).name:
                f = APP / "claude" / "fonts" / Path(u.path).name
                return self.send_file(f, cache="max-age=86400") if f.is_file() else self.send_json({}, 404)
            ST.last_seen = time.time()
            if u.path == "/api/poll":
                try:
                    since = int(q.get("since", 0))
                except ValueError:
                    since = 0
                with ST.lock:
                    logs = [l for l in ST.logs if l[0] > since][-400:]
                    toasts = [t for t in ST.toasts if t[0] > since]
                    pending, ST.pending = ST.pending, []
                    busy_projects = dict(ST.proj_jobs)
                L = ST.tr.lines() if ST.busy else None
                focus = getattr(ST, "focus", None); ST.focus = None
                stamp = None
                if ST.ready and q.get("proj"):         # lets the page reload a project only when it really changed
                    try:
                        stamp = ST.core.project_stamp(Path(ST.S["projects_dir"]) / ST.core.safe_name(q["proj"]))
                    except Exception:
                        stamp = None
                return self.send_json({
                    "ready": ST.ready, "busy": ST.busy, "job": ST.job, "queue": ST.jobs.qsize(), "device": ST.device,
                    "version": ST.version, "logs": logs, "toasts": toasts, "pending": pending, "focus": focus,
                    "next": ST.next_id - 1, "last_job": getattr(ST, "last_job", None),
                    "watch": bool(ST.S and ST.S.get("watch_downloads")),
                    "phase": getattr(ST, "phase", ""), "hw": getattr(ST, "hw_lines", None) if not ST.ready else None,
                    "busy_projects": busy_projects, "running_project": ST.job_proj, "stamp": stamp,
                    "app_version": VERSION, "restarting": ST.restarting,
                    "update": {k: ST.update.get(k) for k in ("latest", "notes", "page")} if ST.update else None,
                    "status": None if not L else {k: L[k] for k in ("label", "detail", "frac", "step_frac", "eta",
                                                                     "step_eta", "elapsed", "step_elapsed")}})
            if not ST.ready:
                return self.send_json({"error": "starting"}, 503)
            core, S = ST.core, ST.S
            if u.path == "/api/projects":
                return self.send_json([project_json(p) for p in core.list_projects(S)])
            if u.path == "/api/project":
                pr = core.Project.open(q.get("name", ""), S, create=False)
                return self.send_json(project_json(pr, full=True) if pr else {"error": "gone"})
            if u.path == "/api/meta":
                return self.send_json(meta())
            if u.path == "/api/preset":
                return self.send_json(core.OD.from_preset(q.get("name", ""), S.get("user_presets")))
            if u.path == "/media":
                p = Path(q.get("path", "")).resolve()
                if is_inside(p, S["projects_dir"]) and p.is_file():
                    return self.send_file(p)
                return self.send_json({"error": "forbidden"}, 403)
            if u.path == "/style_thumb":
                d = core.styles_dir(S) / core.safe_name(q.get("id", ""))
                f = next((x for x in (d / "stills" / "still_2.jpg", d / "stills" / "still_1.jpg") if x.exists()), None)
                return self.send_file(f, "image/jpeg", cache="private, max-age=60") if f else self.send_json({}, 404)
            if u.path == "/thumb":
                pr = core.Project.open(q.get("name", ""), S, create=False)
                try:
                    th = make_thumb(pr) if pr else None
                except Exception:
                    th = None
                return self.send_file(th, "image/jpeg", cache="private, max-age=60") if th else self.send_json({}, 404)
            return self.send_json({"error": "not found"}, 404)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.close_connection = True
        except Exception as e:
            ST.log("UI request failed: " + traceback.format_exc()[-800:])
            try:
                return self.send_json({"error": str(e)}, 500)
            except OSError:
                self.close_connection = True

    # ---------------------------------------------------------- POST
    def upload(self, q):
        """raw body; ?batch=&rel=relative/path/name  ->  .incoming/<batch>/<rel>"""
        batch = re.sub(r"[^\w\-]", "", q.get("batch", "x"))[:40] or "x"
        rel = str(q.get("rel", "file")).replace("\\", "/")
        parts = [re.sub(r'[<>:"|?*\x00-\x1f]', "_", p).strip(" .")[:120] for p in rel.split("/") if p not in ("", ".", "..")]
        parts = [p for p in parts if p] or ["file"]
        dest = INCOMING.joinpath(batch, *parts)
        if not is_inside(dest, INCOMING):
            return self.send_json({"error": "bad file name"}, 400)
        n = max(0, int(self.headers.get("Content-Length") or 0))
        tmp = dest.with_name(dest.name + ".part")
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            left = n
            with open(tmp, "wb") as f:
                while left > 0:
                    chunk = self.rfile.read(min(1 << 20, left))
                    if not chunk:
                        break
                    f.write(chunk); left -= len(chunk)
            if left > 0:
                tmp.unlink(missing_ok=True)
                self.close_connection = True
                return self.send_json({"error": "upload was interrupted"}, 400)
            os.replace(tmp, dest)
        except OSError as e:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            self.close_connection = True
            return self.send_json({"error": f"could not store the file ({e.strerror or e})"}, 507)
        return self.send_json({"path": str(dest)})

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        try:
            if not self.authed():
                return
            if u.path == "/api/upload":
                return self.upload(q)
            try:
                data = read_json_body(self)
            except (ValueError, UnicodeDecodeError):
                return self.send_json({"error": "bad request"}, 400)
            if u.path == "/api/open":                  # second launch / Send to: open a window, hand over files
                paths = [p for p in (data.get("paths") or []) if isinstance(p, str)]
                if paths:
                    with ST.lock:
                        ST.pending += paths
                open_window(f"http://127.0.0.1:{PORT}/?t={ST.token}")
                return self.send_json({"ok": True})
            if u.path == "/api/heartbeat":
                ST.last_seen = time.time()
                return self.send_json({"ok": True})
            if not ST.ready:
                return self.send_json({"error": "Still starting – try again in a moment."}, 503)
            core, S = ST.core, ST.S
            if u.path == "/api/classify":
                return self.send_json(classify([p for p in data.get("paths", []) if isinstance(p, str)]))
            if u.path == "/api/process_zip":
                items = []
                for z in data.get("paths", []):
                    if not isinstance(z, str) or not Path(z).is_file():
                        return self.send_json({"error": f"{Path(str(z)).name} was not found."}, 400)
                    man = core.read_manifest(z)        # UserMessage -> 400 with a readable text
                    if man["kind"] in ("request", "review", "error"):
                        return self.send_json({"error": f"{Path(z).name} is a package FOR Claude – drag it into the "
                                                         "Claude chat instead."}, 400)
                    why = core.zip_project_problem(S, man, z)
                    if why:
                        return self.send_json({"error": why}, 400)
                    items.append((z, man))
                started = 0
                for z, man in items:
                    new_id = core.zip_ids(z)[1]
                    name = core.safe_name(str(man.get("episode") or ""))
                    if submit(f"Process {Path(z).name}", core.process_zip, Path(z), S, CTX, project=name,
                              key="zip:" + new_id):
                        started += 1
                return self.send_json({"ok": True, "started": started})
            if u.path == "/api/new_project":
                o = data.get("order")
                if not isinstance(o, dict):
                    return self.send_json({"error": "No order was sent."}, 400)
                files = {"narration": data.get("narration") or None, "music": data.get("music") or None,
                         "assets": [x for x in data.get("assets", []) if isinstance(x, str)],
                         "script": str(data.get("script") or "")}
                for k in ("narration", "music"):
                    if files[k] and not Path(files[k]).is_file():
                        return self.send_json({"error": f"The {k} file was not found – add it again."}, 400)
                files["assets"] = [Path(x) for x in files["assets"] if Path(x).exists()]
                files["narration"] = Path(files["narration"]) if files["narration"] else None
                files["music"] = Path(files["music"]) if files["music"] else None
                probs = core.OD.problems(core.OD.normalize(o), bool(files["narration"]), bool(files["music"]))
                if probs:
                    return self.send_json({"error": " ".join(probs)}, 400)
                S["last_preset"] = o.get("preset", S.get("last_preset")); core.save_settings(S)
                nm = str(o.get("name") or "").strip()
                ok = submit(f"New project {nm}".strip(), core.new_project, o, files, S, CTX,
                            key=("new:" + core.safe_name(nm)) if nm else None)
                if not ok:
                    return self.send_json({"error": "This project is already being created."}, 400)
                return self.send_json({"ok": True})
            if u.path == "/api/act":
                return self.send_json(act(data) or {})
            if u.path == "/api/settings":
                S.update(check_settings(core, S, data))
                core.save_settings(S); ST.version += 1
                return self.send_json({"ok": True})
            if u.path == "/api/save_preset":
                o, nm = data.get("order"), str(data.get("name") or "").strip()
                if not isinstance(o, dict) or not nm:
                    return self.send_json({"error": "Give the preset a name."}, 400)
                if len(nm) > 40 or re.search(r'[<>:"/\\|?*\x00-\x1f]', nm):
                    return self.send_json({"error": "Use a shorter name without special characters."}, 400)
                if nm in core.OD.PRESETS:
                    return self.send_json({"error": f"“{nm}” is a built-in preset – choose another name."}, 400)
                keep = {k: o[k] for k in ("size", "variants", "fps", "duration", "language", "captions", "text_amount",
                                          "style_preset", "style", "formats", "alpha", "engine", "review", "safe_area",
                                          "brand", "care", "purpose", "kind", "style_ref", "style_ref_name") if k in o}
                au = o.get("audio") if isinstance(o.get("audio"), dict) else {}
                keep["audio"] = {k: au[k] for k in ("export", "generate_music", "loudness", "duck_db") if k in au}
                S.setdefault("user_presets", {})[nm] = keep
                core.save_settings(S); ST.version += 1
                return self.send_json({"ok": True})
            return self.send_json({"error": "not found"}, 404)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.close_connection = True
        except Exception as e:
            core = ST.core
            try:
                if core and isinstance(e, core.UserMessage):
                    return self.send_json({"error": str(e)}, 400)
                ST.log("UI action failed: " + traceback.format_exc()[-800:])
                return self.send_json({"error": f"{type(e).__name__}: {e}"}, 500)
            except OSError:
                self.close_connection = True


# ------------------------------------------------------------------ main
def read_token():
    try:
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


TOKEN_MAX_AGE = 30 * 86400


def reuse_token():
    """keep the last run's token (rotated monthly): a window still open from before a restart keeps working
    instead of showing 'out of date'. The token only has to stay unknown to web pages, and it lives in this file anyway."""
    try:
        t = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if re.fullmatch(r"[A-Za-z0-9_\-]{24,64}", t) and time.time() - TOKEN_FILE.stat().st_mtime < TOKEN_MAX_AGE:
            return t
    except OSError:
        pass
    return ""


def write_token():
    if read_token() == ST.token:            # unchanged: keep the file's date, it tells the token's age
        return
    try:
        TOKEN_FILE.write_text(ST.token, encoding="utf-8")
        try:
            os.chmod(TOKEN_FILE, 0o600)
        except OSError:
            pass
    except OSError:
        pass


def already_running(argv):
    """another engine owns the port: hand it the files (with its token) and let it open the window"""
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/ping", timeout=1.5) as r:
            if json.loads(r.read()).get("app") != "vizavi":
                return False
    except Exception:
        return False
    payload = json.dumps({"paths": [str(Path(p).resolve()) for p in argv]}).encode()
    for attempt in range(3):                      # the other engine may still be writing its token file
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{PORT}/api/open", method="POST", data=payload,
                                         headers={"Content-Type": "application/json", "X-VZ-Token": read_token()})
            urllib.request.urlopen(req, timeout=3).read()
            return True
        except Exception:
            time.sleep(0.7)
    return True      # something with our name owns the port; do not start a second engine on top of it


def storage_env():
    """installed in a folder of your choice: big downloads (pip packages, Chromium, GPU kernels) go there too,
    not to drive C:. Set before the component check runs, so every helper process inherits it."""
    try:
        cache = json.loads((APP / "settings.json").read_text(encoding="utf-8")).get("cache_dir")
    except (OSError, ValueError):
        cache = None
    if cache:
        c = Path(cache)
        for k, sub in (("PIP_CACHE_DIR", "pip"), ("PLAYWRIGHT_BROWSERS_PATH", "ms-playwright"), ("CUPY_CACHE_DIR", "cupy")):
            os.environ.setdefault(k, str(c / sub))


def main(argv, open_ui=True):
    storage_env()
    if "--no-window" in argv:                 # restarted by the updater: the open window reconnects by itself
        argv = [a for a in argv if a != "--no-window"]
        open_ui = False
    tok = os.environ.pop("VZ_TOKEN", "")
    if already_running(argv):
        return
    tok = tok or reuse_token()
    if tok:
        ST.token = tok
    ST.pending = [str(Path(p).resolve()) for p in argv]
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    except OSError as e:
        print(f"Vizavi Studio could not start: port {PORT} is in use ({e}).", file=sys.stderr)
        return
    srv.daemon_threads = True
    write_token()
    for fn in (setup, worker, idle_exit):
        threading.Thread(target=fn, daemon=True).start()
    if open_ui:
        open_window(f"http://127.0.0.1:{PORT}/?t={ST.token}")
    srv.serve_forever()


if __name__ == "__main__":
    main(sys.argv[1:])
