"""Vizavi Studio core: projects of any kind (orders), Whisper, beats, packages for Claude,
preview/final renders (python or html engine, any aspect/fps/alpha, several variants), checks, exports.
GUI-independent. Debug CLI:
  python -m studio.core new --preset "Shorts / Reels / TikTok 9:16" --narration a.wav [--music m.mp3] [--name N]
                            [--script s.txt] [--brief b.txt] [--assets x.png y.mp4] [--set key=value ...]
  python -m studio.core drop <zip>          python -m studio.core approve <project>"""
import ast, copy, difflib, hashlib, json, math, os, platform, re, shutil, subprocess, sys, threading, time, traceback, zipfile
from collections import deque
from pathlib import Path

from .core_paths import APP, KIT, CL, TOOLS, ENGINES, FONTS, LIB, SETTINGS, is_inside, safe_member
from . import order as OD
import vz_analysis as va
import vz_checks as vc

from .version import VERSION
from . import trash as TR
NOWIN = va.NOWIN
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac", ".opus", ".wma", ".aiff", ".aif"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".svg", ".gif"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v"}
FONT_EXT = {".ttf", ".otf", ".woff", ".woff2"}
RUNTIME_FILES = {"backend.py", "render_all.py", "make_final.py", "check.py", "ff.py", "fakegpu.py", "KIT.md",
                 "vzrender.py", "vz.js", "vzfast.py"}
SKIP_DIRS = {"__pycache__", "cache", "out", "check", "fonts", "assets", "brand", "input", ".git"}

DEFAULTS = {
    "projects_dir": str(APP / "Projects"),
    "whisper_model": "large-v3", "whisper_device": "auto", "script_as_hint": True,
    "preview_long_side": 960, "preview_crf": 22, "final_crf": 14, "workers": "",
    "watch_downloads": True, "downloads_dir": "", "reuse_unchanged": True,
    "auto_play_preview": True, "models_dir": "", "review_zip_max_mb": 25,
    "uzbek_model": "islomov/rubaistt_v2_medium", "precise_timing": True,
    "mms_model": "MahmoudAshraf/mms-300m-1130-forced-aligner", "request_zip_max_mb": 28, "library_in_request": 3,
    "last_preset": "Narrated explainer 16:9 (cinematic, no voice)", "user_presets": {}, "standing_rules": "",
    "light_effects": False, "check_updates": True,
}


class UserMessage(Exception):
    """a problem the user should read (not a crash)"""


class StepError(Exception):
    def __init__(self, step, tail):
        super().__init__(f"{step} failed")
        self.step, self.tail = step, tail


class Ctx:
    def __init__(self):
        self.proc = None
        self.cancelled = False

    def log(self, s):
        print(s, flush=True)

    def progress(self, frac=None, label=None, detail=None, until=None, eta=None):
        if label:
            print(f"== {label}", flush=True)


# ------------------------------------------------------------------ settings / helpers
_WLOCK = threading.RLock()
SETTINGS_PROBLEM = ""      # text for the UI when settings.json had to be repaired


def atomic_write(path, text, keep_bak=False):
    """Write a text file so that a reader (or a crash) never sees half of it: write a temp file next to it,
    then swap it in. With keep_bak the previous GOOD version is kept as <name>.bak."""
    path = Path(path)
    with _WLOCK:
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        if keep_bak and path.exists():
            try:
                json.loads(path.read_text(encoding="utf-8"))
                shutil.copy2(path, path.with_name(path.name + ".bak"))
            except Exception:
                pass
        err = None
        for i in range(15):          # Windows refuses the swap while another thread has the file open
            try:
                os.replace(tmp, path)
                return
            except PermissionError as e:
                err = e
                time.sleep(0.04 * (i + 1))
        raise err


def read_json_safe(path):
    """(data, how): how = 'ok' | 'bak' (restored from the last good copy) | 'missing' | 'broken'."""
    path = Path(path)
    if not path.exists():
        return None, "missing"
    for _ in range(4):
        try:
            return json.loads(path.read_text(encoding="utf-8")), "ok"
        except (OSError, ValueError):
            time.sleep(0.05)
    try:
        return json.loads(path.with_name(path.name + ".bak").read_text(encoding="utf-8")), "bak"
    except (OSError, ValueError):
        return None, "broken"


def load_settings():
    """Never silently falls back to defaults: a damaged settings.json is kept aside and reported."""
    global SETTINGS_PROBLEM
    SETTINGS_PROBLEM = ""
    s = copy.deepcopy(DEFAULTS)
    data, how = read_json_safe(SETTINGS)
    if how == "broken":
        keep = SETTINGS.with_name(f"settings.broken_{time.strftime('%Y%m%d_%H%M%S')}.json")
        try:
            shutil.copy2(SETTINGS, keep)
        except OSError:
            keep = None
        SETTINGS_PROBLEM = ("settings.json could not be read, so the defaults are in use."
                            + (f" The damaged file was kept as {keep.name}." if keep else ""))
    elif how == "bak":
        SETTINGS_PROBLEM = "settings.json was damaged; the last good copy was restored."
    if isinstance(data, dict):
        s.update(data)
        if "episodes_dir" in data and "projects_dir" not in data:
            s["projects_dir"] = data["episodes_dir"]
    # older installers set models_dir to <app>\models: everything downloaded there was lost with every reinstall.
    # Blank = the shared model cache in the user profile, which survives reinstalls (old files there are still found).
    if str(s.get("models_dir") or "").strip().rstrip("\\/").lower() == str(APP / "models").lower():
        s["models_dir"] = ""
    if not str(s.get("downloads_dir") or "").strip():
        from .hw import downloads_dir
        s["downloads_dir"] = downloads_dir()
    return s


def SETTINGS_HAS(key):
    try:
        return key in json.loads(SETTINGS.read_text(encoding="utf-8"))
    except Exception:
        return False


def save_settings(s):
    atomic_write(SETTINGS, json.dumps({k: v for k, v in s.items() if k != "hw"}, indent=1, ensure_ascii=False),
                 keep_bak=True)


def apply_hw_profile(s, prof, force=False):
    """fit the speech/preview settings to this PC once (or again after 'Check and repair components').
    Only turns things off that the PC can't run; custom model names are kept."""
    s["hw"] = prof
    if s.get("hw_applied") and not force:
        return False
    if s.get("whisper_model") in ("large-v3", "medium", "large-v3-turbo", "", None):
        s["whisper_model"] = prof["whisper_model"]
    s["whisper_device"] = "auto" if prof["gpu_speech"] else "cpu"
    if not prof["uzbek_pack"]:
        s["uzbek_model"], s["precise_timing"] = "", False
    elif force and not s.get("uzbek_model"):
        s["uzbek_model"] = DEFAULTS["uzbek_model"]
    s["preview_long_side"] = prof["preview_long_side"]
    s["hw_applied"] = True
    return True


def py_exe():
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe" and exe.with_name("python.exe").exists():
        return str(exe.with_name("python.exe"))
    return str(exe)


def safe_name(s):
    s = re.sub(r"[^\w\-]+", "_", s.strip(), flags=re.UNICODE).strip("_")
    return (s or "project")[:60]


def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def run_proc(cmd, cwd, ctx, step, env=None, on_line=None, logfile=None):
    if getattr(ctx, "cancelled", False):          # Stop was pressed between two steps
        raise UserMessage("Stopped.")
    e = dict(os.environ)
    e.update({"PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"})
    if env:
        e.update(env)
    tail = deque(maxlen=400)
    lf = open(logfile, "a", encoding="utf-8") if logfile else None
    if lf:
        lf.write(f"\n### {now()} {step}: {' '.join(map(str, cmd))}\n")
    p = subprocess.Popen([str(c) for c in cmd], cwd=str(cwd), env=e, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                         bufsize=1, creationflags=NOWIN)
    ctx.proc = p
    try:
        for line in p.stdout:
            line = line.rstrip()
            if not line:
                continue
            tail.append(line)
            if lf:
                lf.write(line + "\n")
            if line.lstrip().startswith(("size=", "frame=")):
                continue
            if on_line is None or not on_line(line):
                ctx.log("  " + line)
        p.wait()
    finally:
        ctx.proc = None
        if lf:
            lf.close()
    if ctx.cancelled:
        raise UserMessage("Stopped.")
    if p.returncode != 0:
        raise StepError(step, list(tail))
    return list(tail)


def write_zip(path, entries):
    """entries: list of (arcname, Path | str | bytes)"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    stored = {".mp4", ".jpg", ".jpeg", ".png", ".mp3", ".m4a", ".webm", ".mov", ".woff2", ".zip"}
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for arc, src in entries:
            if isinstance(src, Path):
                if src.is_dir():
                    for f in sorted(src.rglob("*")):
                        if f.is_file() and "__pycache__" not in f.parts:
                            z.write(f, f"{arc}/{f.relative_to(src).as_posix()}",
                                    compress_type=zipfile.ZIP_STORED if f.suffix.lower() in stored else zipfile.ZIP_DEFLATED)
                elif src.exists():
                    z.write(src, arc, compress_type=zipfile.ZIP_STORED if src.suffix.lower() in stored else zipfile.ZIP_DEFLATED)
            elif isinstance(src, bytes):
                z.writestr(arc, src)
            else:
                z.writestr(arc, str(src))
    os.replace(tmp, path)
    return path


def episode_files(src):
    """the project's own source files (no runtime, fonts, user assets, caches, renders)."""
    out = []
    for p in sorted(Path(src).rglob("*")):
        rel = p.relative_to(src)
        if p.is_dir() or any(x in SKIP_DIRS for x in rel.parts[:-1]) or (len(rel.parts) > 1 and rel.parts[0] in SKIP_DIRS):
            continue
        if p.suffix.lower() in {".pyc", ".tmp", ".zip"} or p.name in {"mix.wav", "final_audio.wav", "preview_audio.wav",
                                                                       "bed.wav", "mix.json.bak", ".gpu_ok"}:
            continue
        if len(rel.parts) == 1 and p.name in RUNTIME_FILES:
            continue
        if p.suffix.lower() in VIDEO_EXT and len(rel.parts) == 1:
            continue
        out.append((rel.as_posix(), p))
    return out


# ------------------------------------------------------------------ projects
class Project:
    def __init__(self, root):
        self.root = Path(root)
        self.name = self.root.name
        self.src, self.outbox, self.inbox = self.root / "source", self.root / "to_claude", self.root / "from_claude"
        self.work, self.output, self.logs = self.root / "work", self.root / "output", self.root / "logs"
        self.state_file = self.root / "state.json"
        self.state = {}
        self.state_problem = ""
        data, how = read_json_safe(self.state_file)
        if how in ("ok", "bak") and isinstance(data, dict):
            self.state = data
        elif how != "missing":
            self._recover_state()

    def _recover_state(self):
        """state.json exists but cannot be read. Keep the damaged file and rebuild a minimal state from what is on
        disk - never start from an empty state, which would later overwrite the whole history."""
        keep = self.root / f"state.broken_{time.strftime('%Y%m%d_%H%M%S')}.json"
        try:
            shutil.copy2(self.state_file, keep)
        except OSError:
            pass
        stage = "new"
        if self.outbox.exists() and any(self.outbox.glob("*__request.zip")):
            stage = "request_ready"
        if self.output.exists() and any(self.output.glob("*.mp4")):
            stage = "done"
        self.state_problem = f"state.json was damaged and rebuilt (the damaged copy is {keep.name})"
        self.state = {"name": self.name, "created": now(), "stage": stage, "processed": [],
                      "history": [[now(), stage, self.state_problem]]}
        try:
            self.save()
        except OSError:
            pass

    @classmethod
    def open(cls, name, S, create=True):
        root = Path(S["projects_dir"]) / safe_name(name)
        if not root.exists() and not create:
            return None
        p = cls(root)
        p.ensure()
        return p

    def ensure(self):
        for d in (self.src, self.outbox, self.inbox, self.work, self.output, self.logs):
            d.mkdir(parents=True, exist_ok=True)
        if not self.state:
            self.state = {"name": self.name, "created": now(), "stage": "new", "history": [], "processed": []}
            self.save()

    def save(self):
        atomic_write(self.state_file, json.dumps(self.state, indent=1, ensure_ascii=False), keep_bak=True)

    def set(self, stage, msg, **kw):
        self.state["stage"] = stage
        self.state.update(kw)
        self.state.setdefault("history", []).append([now(), stage, msg])
        self.save()

    @property
    def order(self):
        f = self.src / "order.json"
        if f.exists():
            return OD.normalize(json.loads(f.read_text(encoding="utf-8")))
        o = OD.legacy_order()
        o["name"] = self.name
        if self.narration():
            o["audio"]["narration"] = self.narration().name
        return o

    def narration(self):
        return next(iter(sorted(self.src.glob("narration.*"))), None)

    def music(self):
        return next(iter(sorted(self.src.glob("music.*"))), None)

    def words(self):
        return va.load_words(self.src / "words.tsv")

    def beats(self):
        f = self.src / "beats.tsv"
        if not f.exists():
            return []
        return [float(l.split("\t")[0]) for l in f.read_text(encoding="utf-8").splitlines() if l[:1].isdigit()]


Episode = Project  # v1 name


def list_projects(S):
    root = Path(S["projects_dir"])
    if not root.exists():
        return []
    ps = [Project(d) for d in root.iterdir() if (d / "state.json").exists() and not d.name.startswith("_")]
    return sorted(ps, key=lambda e: (e.state.get("history") or [[""]])[-1][0], reverse=True)


list_episodes = list_projects

RUNNING_STAGES = ("transcribing", "rendering_preview", "rendering_final")


def project_exists(S, name):
    return (Path(S["projects_dir"]) / safe_name(str(name or "")) / "state.json").exists()


def project_stamp(root):
    """Cheap fingerprint of everything the project page shows (file dates only, nothing is read)."""
    r, out = Path(root), []
    for rel in ("state.json", "source/transcript_claude.md", "source/script.txt", "source/assets", "output"):
        try:
            out.append(str(os.stat(r / rel).st_mtime_ns))
        except OSError:
            out.append("0")
    return "|".join(out)


def repair_stuck(S):
    """At app start nothing can be running: a project still marked 'rendering…' or 'preparing…' was cut off by a
    crash, a power loss or closing the app. Mark it so the UI offers Retry instead of waiting forever."""
    fixed = []
    for pr in list_projects(S):
        st = pr.state.get("stage")
        if st not in RUNNING_STAGES:
            continue
        if st == "transcribing":
            pr.set("failed", "preparing was interrupted (the app was closed) - start the project again")
        else:
            kind = "preview" if st == "rendering_preview" else "final"
            ver = int((pr.state.get("attempt_v") if kind == "preview" else pr.state.get("final_v"))
                      or pr.state.get("preview_v") or 1)
            pr.set("stopped", f"{kind} v{ver} was interrupted (the app was closed or crashed)",
                   failed_kind=kind, failed_version=ver, stop_reason="interrupted")
        fixed.append(pr.name)
    return fixed


def delete_project(pr, S):
    """moves the project folder to Recently deleted (<projects>/_deleted), restorable for 30 days from Settings"""
    TR.to_trash(pr.root, S, "project", pr.name)
    return "Recently deleted"

STAGE_TEXT = {
    "stopped": "stopped - press Retry render",
    "new": "new", "transcribing": "preparing…",
    "request_ready": "① waiting for Claude (drag the request zip into Claude)",
    "rendering_preview": "rendering preview…",
    "preview_ready": "② preview ready → send review zip to Claude, or approve",
    "rendering_final": "rendering final…", "done": "✓ final ready",
    "error": "⚠ render failed → send error zip to Claude",
    "failed": "✗ setup failed – start the project again (this folder can be deleted)",
}
NOISE = ("UserWarning", "warnings.warn", "symlink", "Developer Mode", "developer mode", "HF_TOKEN",
         "unauthenticated", "huggingface.co/docs", "docs.microsoft.com", "To support symlinks")
MSG_TAIL = " Don't load any skill and don't ask questions - everything you need is in the zip."


def claude_message(kind, name, ver=None):
    if kind == "request":
        return f"Vizavi Studio: new project \"{name}\". Open the attached zip and follow CLAUDE_TASK.md inside it." + MSG_TAIL
    if kind == "review":
        return (f"Vizavi Studio: preview v{ver} of \"{name}\" is rendered. Review it and send the final. "
                f"Follow CLAUDE_TASK.md inside the attached zip." + MSG_TAIL)
    return f"Vizavi Studio: the render of \"{name}\" failed. Fix it - follow CLAUDE_TASK.md inside the attached zip." + MSG_TAIL


# ------------------------------------------------------------------ stage 0: inputs -> request zip
def norm_tok(t):
    t = t.lower()
    for ch in "ʻʼ’‘`´":
        t = t.replace(ch, "'")
    return re.sub(r"[^\w'\-]", "", t)


def write_timing_files(pr, tj, script, ctx=None):
    """words.tsv = the script's spelling on the audio's timing (Whisper alone misspells, esp. Uzbek)."""
    from .align import align, clean_transcript, cyr2lat
    raw = tj["words"]
    (pr.src / "words_whisper.tsv").write_text("# raw Whisper output (for reference)\n" + "\n".join(
        f"{w['s']:.3f}\t{w['e']:.3f}\t{w['w']}\t{w.get('p', 0):.2f}" for w in raw) + "\n", encoding="utf-8")
    tr = "\n".join(f"[{s_['s']:7.2f} - {s_['e']:7.2f}] {cyr2lat(s_['text'])}" for s_ in tj["segments"])
    (pr.src / "transcript.txt").write_text(tr + "\n", encoding="utf-8")
    md = [f"# Transcript check\nTranscriber: {tj['backend']}. Timing always comes from the audio.\n"]
    if script.strip():
        words, rep = align(raw, script)
        n = rep["script_words"]
        ok = rep["exact"] + rep["corrected"]
        md.append(f"Words = your script's spelling on the audio's timing. Matched {ok}/{n} script words "
                  f"({100 * ok / max(1, n):.0f}%): {rep['exact']} heard exactly, {rep['corrected']} misheard by Whisper "
                  f"and corrected from the script.\n")
        md.append("## Where the narrator said something different (the AUDIO is used here)")
        md += [f"- {t:6.2f}s  script: «{a_}»  →  spoken: «{b_}»" for t, a_, b_ in rep["changed"]] or ["- none"]
        md.append("\n## Spoken but not in the script (kept from the audio)")
        md += [f"- {t:6.2f}s  «{a_}»" for t, a_ in rep["audio_only"]] or ["- none"]
        md.append("\n## In the script but not spoken (left out)")
        md += [f"- after {t:6.2f}s  «{a_}»" for t, a_ in rep["not_spoken"]] or ["- none"]
        summary = (f"Transcript: {ok}/{n} script words matched ({rep['corrected']} spellings fixed from the script)"
                   + (f", {len(rep['changed'])} place(s) where the narrator changed the text" if rep["changed"] else "")
                   + (f", {len(rep['not_spoken'])} skipped" if rep["not_spoken"] else "")
                   + (f", {len(rep['audio_only'])} extra" if rep["audio_only"] else ""))
        if ok / max(1, n) < 0.6:
            md.insert(1, "⚠ **Less than 60% matched – is this the right script for this audio?**\n")
            summary += " ⚠ low match – right script?"
    else:
        ok, n = 0, 0
        words = clean_transcript(raw)
        md.append("No script was given, so the words are Whisper's (Cyrillic converted to Latin). Whisper makes "
                  "spelling mistakes, especially in Uzbek – paste the script next time for exact captions.")
        summary = f"Transcript: {len(words)} words from Whisper (no script given – spelling may have mistakes)"
    low = [w for w in words if w.get("p", 1) < 0.4 and w.get("src") == "audio"]
    if low:
        md.append("\n## Low-confidence words from the audio\n" + ", ".join(f"{w['w']}@{w['s']:.1f}s" for w in low[:40]))
    lines = ["# start\tend\tword\tprob\tsource   (source: script = script spelling, exact audio timing; "
             "script~ = timing estimated inside a misheard span; audio = spoken word not in the script)"]
    lines += [f"{w['s']:.3f}\t{w['e']:.3f}\t{w['w']}\t{w.get('p', 0):.2f}\t{w.get('src', 'audio')}" for w in words]
    (pr.src / "words.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (pr.src / "script_alignment.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    # both recognizer passes, side by side with times, for Claude's transcript reconstruction
    P = [f"# Raw speech-recognition passes (language: {tj.get('language')})",
         "Both are machine transcripts of the SAME audio and both contain mistakes. Rebuild the real text from "
         "them (DIRECTION.md §1).", ""]
    for title, segs in (("Pass A - Whisper large-v3 (good timing, weak Uzbek)", tj.get("segments_large_v3") or tj["segments"]),
                        ("Pass B - Uzbek-trained model (better words)", tj.get("segments_uzbek") or [])):
        if segs:
            P += [f"## {title}"] + [f"[{x['s']:06.1f}-{x['e']:06.1f}] {cyr2lat(x['text'])}" for x in segs] + [""]
    (pr.src / "asr_passes.md").write_text("\n".join(P) + "\n", encoding="utf-8")
    pr.state["transcript_source"] = "script" if script.strip() else "asr"
    pr.state["transcript_match"] = round(ok / max(1, n), 2) if script.strip() else None
    if ctx:
        ctx.log(summary)
    return words


def transcribe(pr, nar, script, o, S, ctx):
    out = pr.src / "timings.json"

    def on_line(line):
        if line.startswith("PROGRESS "):
            x = float(line.split()[1])
            stage = "downloading/loading" if x < 0.4 else (f"Whisper {S['whisper_model']} (timing)" if x < 0.6 else "Uzbek model (words)")
            ctx.progress(0.02 + 0.68 * x, detail=f"{stage} · {int(x * 100)}%")
            return True
        if line.startswith("LOG "):
            ctx.log(line[4:])
            if "downloaded" in line:
                ctx.progress(detail="Whisper model:" + line.split("downloaded", 1)[1])
            return True
        return any(k in line for k in NOISE)   # harmless library warnings stay in the log file only
    lang = o.get("language", "uz")
    cmd = [py_exe(), "-m", "studio.transcribe", nar, out, "--lang", "" if lang == "auto" else lang,
           "--model", S["whisper_model"]]
    if S.get("script_as_hint") and (script or "").strip():
        cmd += ["--prompt", pr.src / "script.txt"]
    if lang == "uz" and str(S.get("uzbek_model", "")).strip():
        cmd += ["--uz-model", S["uzbek_model"], "--models-dir",
                str(Path(S.get("models_dir") or Path.home() / ".cache" / "huggingface" / "vizavi").expanduser())]
    menv = {"HF_HUB_CACHE": str(Path(S["models_dir"]).expanduser())} if str(S.get("models_dir", "")).strip() else {}
    menv["VZ_SPEECH_COMPUTE"] = (S.get("hw") or {}).get("speech_compute", "float16")
    try:
        run_proc(cmd + ["--device", S["whisper_device"]], APP, ctx, "transcribe", env=menv, on_line=on_line,
                 logfile=pr.logs / "prepare.log")
    except StepError:
        if S["whisper_device"] == "cpu":
            raise
        ctx.log("retrying transcription on CPU…")
        run_proc(cmd + ["--device", "cpu"], APP, ctx, "transcribe", env=menv, on_line=on_line, logfile=pr.logs / "prepare.log")
    tj = json.loads(out.read_text(encoding="utf-8"))
    if not tj["words"]:
        raise UserMessage("Whisper found no words in the narration.")
    write_timing_files(pr, tj, script or "", ctx)
    if S.get("precise_timing") and lang in ("uz", "auto", "ru", "kk", "ky", "tg", "tr", "en", "de", "fr", "es"):
        precise_timing(pr, S, ctx, menv)
    return tj


def precise_timing(pr, S, ctx, env=None):
    """MMS CTC forced alignment of words.tsv onto the narration (exact word boundaries). Never fatal."""
    ctx.progress(0.7, "Precise word timing (MMS aligner)", until=0.82)

    def on_line(line):
        if line.startswith("PROGRESS "):
            ctx.progress(0.7 + 0.12 * float(line.split()[1]), detail=f"aligning · {int(float(line.split()[1]) * 100)}%")
            return True
        if line.startswith("LOG "):
            ctx.log(line[4:])
            return True
        return any(k in line for k in NOISE)
    try:
        run_proc([py_exe(), "-m", "studio.mms_align", pr.narration(), pr.src / "words.tsv", "--model", S["mms_model"]],
                 APP, ctx, "precise timing", env=env, on_line=on_line, logfile=pr.logs / "prepare.log")
        pr.state["timing"] = "mms"
    except StepError as e:
        pr.state["timing"] = "whisper"
        last = next((l for l in reversed(e.tail) if l.startswith("LOG") or "Error" in l), "")
        ctx.log("(precise timing skipped, Whisper timing kept" + (f": {last[4:] if last.startswith('LOG') else last}" if last else "") + ")")


def redo_transcript(pr, script, S, ctx):
    """re-run transcription (e.g. with the script pasted or better models) and rebuild the request zip."""
    if not pr.narration():
        raise UserMessage("This project has no narration.")
    o = pr.order
    ctx.progress(0, f"Redo transcript of “{pr.name}”", until=0.02)
    (pr.src / "script.txt").write_text(script or "", encoding="utf-8")
    ctx.progress(0.02, "Transcribing the narration", until=0.82)
    tj = transcribe(pr, pr.narration(), script, o, S, ctx)
    from . import media
    pr.state["caption_lines"] = media.make_srt(pr.words(), pr.src / "captions.srt")
    if o["duration"]["mode"] == "narration":
        dur = max(tj["duration"], tj["words"][-1]["e"] + float(o["duration"].get("tail", 1.5)))
        pr.state.update(duration=round(dur, 3), suggested_nfr=math.ceil(dur * float(o["fps"])))
    pr.state.update(narration_duration=tj["duration"], words=len(tj["words"]), transcriber=tj["backend"])
    ctx.progress(0.9, "Rebuilding the request package", until=1.0)
    z = build_request_zip(pr, S, ctx)
    pr.set("request_ready", "transcript redone, new request zip", last_zip=str(z), last_kind="request", last_version=0)
    ctx.progress(1, "Request package ready")
    ctx.log(f"✓ {z.name} rebuilt with the new transcript – send it to Claude (a new chat is best).")
    return pr, z


def classify(paths):
    """dropped files -> narration/music candidates, assets, script text"""
    audio = [p for p in paths if p.suffix.lower() in AUDIO_EXT]
    txt = [p for p in paths if p.suffix.lower() in {".txt", ".md"}]
    assets = [p for p in paths if p.suffix.lower() in IMAGE_EXT | VIDEO_EXT | FONT_EXT
              or (p.suffix.lower() in AUDIO_EXT and p not in audio[:2])]
    return audio, txt, assets


def new_project(o, files, S, ctx):
    """o: order dict; files: {'narration': Path|None, 'music': Path|None, 'assets': [Path], 'script': str}"""
    holder = {}
    try:
        return _new_project(o, files, S, ctx, holder)
    except Exception as e:
        pr = holder.get("pr")
        if pr is not None:      # never leave a project looking "stuck"
            pr.set("failed", f"setup failed: {type(e).__name__}: {e}")
        raise


def _new_project(o, files, S, ctx, holder):
    o = OD.normalize(o)
    if not o.get("standing_rules"):
        o["standing_rules"] = (S.get("standing_rules") or "").strip()
    nar, mus = files.get("narration"), files.get("music")
    probs = OD.problems(o, bool(nar), bool(mus))
    if probs:
        raise UserMessage("\n".join(probs))
    base = safe_name(o.get("name") or (Path(nar).stem if nar else Path(mus).stem if mus else "project"))
    root, k = Path(S["projects_dir"]) / base, 2
    while (root / "state.json").exists():
        root, k = Path(S["projects_dir"]) / f"{base}_{k}", k + 1
    pr = Project(root)
    pr.ensure()
    holder["pr"] = pr
    o["name"] = pr.name
    ctx.progress(0, f"New project “{pr.name}” ({o['preset']})", until=0.02)
    pr.set("transcribing", "preparing inputs")
    script = files.get("script") or ""
    (pr.src / "script.txt").write_text(script, encoding="utf-8")
    if nar:
        dst = pr.src / ("narration" + Path(nar).suffix.lower()); shutil.copy2(nar, dst); o["audio"]["narration"] = dst.name
    if mus:
        dst = pr.src / ("music" + Path(mus).suffix.lower()); shutil.copy2(mus, dst); o["audio"]["music"] = dst.name
    ad = pr.src / "assets"
    ad.mkdir(exist_ok=True)
    names = []
    for a in files.get("assets", []):
        a = Path(a)
        if not a.is_file():
            ctx.log(f"(skipped asset {a.name}: not a file)")
            continue
        dst = ad / safe_asset_name(a.name, names)
        try:
            shutil.copy2(a, dst)
        except OSError as e:
            ctx.log(f"(skipped asset {a.name}: {e.strerror or e})")
            continue
        names.append(dst.name)
    names = apply_style_fonts(pr, S, o, names, ctx)
    names = apply_look_fonts(pr, o, names, ctx)
    o["assets"] = names
    if o.get("brand"):
        info, bfiles = OD.brand_info(o["brand"])
        (pr.src / "brand").mkdir(exist_ok=True)
        for f in bfiles:
            shutil.copy2(f, pr.src / "brand" / f.name)
        if info:
            (pr.src / "brand" / "brand.json").write_text(json.dumps(info, indent=1, ensure_ascii=False), encoding="utf-8")
    fps = float(o["fps"])
    durs, info = {}, {}
    if nar:
        ctx.progress(0.02, "Transcribing the narration (Whisper)", until=0.82)
        tj = transcribe(pr, pr.narration(), script, o, S, ctx)
        durs["narration"] = max(tj["duration"], tj["words"][-1]["e"] + float(o["duration"].get("tail", 1.5)))
        info.update(narration_duration=tj["duration"], words=len(tj["words"]), transcriber=tj["backend"])
        from . import media
        n = media.make_srt(pr.words(), pr.src / "captions.srt")
        info["caption_lines"] = n
    if mus:
        ctx.progress(0.85, "Finding the beats in the music", until=0.95)
        from . import media
        b = media.detect_beats(pr.music())
        media.write_beats(b, pr.src / "beats.tsv")
        durs["music"] = b.get("duration") or va.media_info(pr.music())["duration"]
        info.update(music_duration=durs["music"], bpm=b.get("bpm"))
        ctx.log(f"music: {b.get('bpm')} BPM, {len(b['beats'])} beats, sections at {b['sections']}")
    mode = o["duration"]["mode"]
    dur = durs.get(mode) if mode in durs else float(o["duration"].get("seconds") or 10)
    nfr = math.ceil(dur * fps)
    info.update(duration=round(dur, 3), suggested_nfr=nfr)
    (pr.src / "order.json").write_text(json.dumps(o, indent=1, ensure_ascii=False), encoding="utf-8")
    (pr.src / "brief.md").write_text(OD.brief_md(o, assets=names), encoding="utf-8")
    pr.state.update(info)
    pr.state["preset"] = o["preset"]
    z = build_request_zip(pr, S, ctx)
    pr.set("request_ready", "request zip created", last_zip=str(z), last_kind="request", last_version=0)
    ctx.progress(1, "Request package ready")
    ctx.log(f"✓ {z.name} ({z.stat().st_size / 1e6:.1f} MB): {o['preset']}, {dur:.1f}s @ {o['fps']} fps"
            + (f", {info['words']} words via {info['transcriber']}" if nar else ""))
    return pr, z


def safe_asset_name(name, taken):
    stem, ext = Path(name).stem, Path(name).suffix.lower()
    s = re.sub(r"[^\w\-]+", "_", stem).strip("_") or "asset"
    out, k = f"{s}{ext}", 2
    while out in taken:
        out, k = f"{s}_{k}{ext}", k + 1
    return out


# ------------------------------------------------------------------ full-quality assets
def asset_manifest(pr):
    """input/ASSETS.md: Claude only gets light copies - this tells it the real sizes and how to cut clips so the
    app can make them again from the originals at full quality."""
    ad = pr.src / "assets"
    rows = []
    for f in sorted(ad.iterdir()) if ad.exists() else []:
        if not f.is_file():
            continue
        ext = f.suffix.lower()
        mb = f.stat().st_size / 1e6
        if ext in VIDEO_EXT:
            i = va.media_info(f)
            real = f"video {i.get('width')}×{i.get('height')}, {i.get('fps') or '?'} fps, {i.get('duration') or 0:.1f} s" \
                   + (", has sound" if i.get("has_audio") else "")
            copy = "≤ 640 px wide, no sound" if mb > 3 else "same file"
        elif ext in IMAGE_EXT and ext not in {".svg"}:
            try:
                from PIL import Image
                with Image.open(f) as im:
                    real = f"image {im.width}×{im.height}"
            except Exception:
                real = "image"
            copy = "≤ 2048 px" if mb > 1.5 and ext not in {".gif"} else "same file"
        elif ext in FONT_EXT:
            real, copy = "font", "same file"
        else:
            real, copy = ext.lstrip(".") or "file", "same file"
        rows.append(f"| {f.name} | {real} ({mb:.1f} MB) | {copy} |")
    if not rows:
        return None
    return "\n".join([
        "# Your assets are LIGHT COPIES – the originals are bigger",
        "",
        "`input/assets/` holds small copies so the zip stays small. At render time the user's ORIGINAL files are at",
        "`assets/<name>` (same names, the sizes below). So:",
        "",
        "- Always load `assets/<name>`. Size and place things relative to the frame, never by the copy's pixels.",
        "- Never ship a re-encoded, trimmed, cropped or scaled version of these files: it would only have the light",
        "  copy's quality. When a clip needs cutting, cropping, a frame rate or a format the renderer can play (the",
        "  HTML engine's Chromium cannot play H.264 – it needs .webm), declare it in `media.json` next to film.py /",
        "  index.html and the app makes it from the ORIGINAL before every render:",
        "",
        "```json",
        '{"clips": [{"out": "media/lesson.webm", "src": "<asset file name>", "start": 2935.9, "duration": 24.4,',
        '            "fps": 24, "audio": false, "crop": [0.0, 0.0, 1.0, 1.0], "max_width": 2560}]}',
        "```",
        "  `start`/`duration` in seconds of the source; `crop` (optional) = [x, y, w, h] as fractions 0..1 of the",
        "  source frame; `max_width` (optional) only limits the size; `out` ends in .webm, .mp4 or .mov.",
        "  For your own sandbox test you may put a low-quality version at the same `out` path – it is replaced.",
        "- Don't ship a `cache/` folder built from these copies; build caches in `prepare_assets()` at render time.",
        "",
        "| file | original (used for the render) | light copy you have |",
        "|---|---|---|",
    ] + rows) + "\n"


MEDIA_RECIPE_V = "1"


def build_media(pr, wd, ctx):
    """Claude only had light copies of the user's clips, so every clip it cut (trim / crop / .webm for Chromium) is
    made again here from the ORIGINAL at full quality, as declared in media.json. Results are cached per recipe."""
    spec = Path(wd) / "media.json"
    if not spec.exists():
        return []
    try:
        clips = json.loads(spec.read_text(encoding="utf-8")).get("clips") or []
    except (ValueError, AttributeError) as e:
        raise StepError("media.json", [f"media.json could not be read: {e}"])
    made = []
    cache = pr.work / "_media_cache"
    for k, c in enumerate(clips):
        if not isinstance(c, dict):
            continue
        out_rel = safe_member(str(c.get("out") or ""))
        ext = Path(out_rel or "").suffix.lower()
        src = pr.src / "assets" / Path(str(c.get("src") or "")).name
        if not out_rel or ext not in {".webm", ".mp4", ".mov"} or out_rel.split("/")[0] in ("assets", "input"):
            ctx.log(f"(media.json clip {k + 1}: unusable 'out' {c.get('out')!r} – skipped)")
            continue
        if not src.is_file():
            ctx.log(f"(media.json clip {k + 1}: the original {src.name} is not in the project – Claude's copy is used)")
            continue
        inf = va.media_info(src)
        sw, sh = inf.get("width") or 0, inf.get("height") or 0
        if not sw or not sh:
            ctx.log(f"(media.json clip {k + 1}: {src.name} has no video – skipped)")
            continue
        vf = []
        cr = c.get("crop")
        cw, chh = sw, sh
        if isinstance(cr, (list, tuple)) and len(cr) == 4:
            x, y, w, h = (min(1.0, max(0.0, float(v))) for v in cr)
            w, h = max(0.01, min(w, 1 - x)), max(0.01, min(h, 1 - y))
            cw, chh = max(2, int(sw * w) // 2 * 2), max(2, int(sh * h) // 2 * 2)
            vf.append(f"crop={cw}:{chh}:{int(sw * x)}:{int(sh * y)}")
        mw = c.get("max_width")
        if mw and float(mw) < cw:
            vf.append(f"scale={int(float(mw)) // 2 * 2}:-2:flags=lanczos")
        elif cw % 2 or chh % 2:
            vf.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")
        if c.get("fps"):
            vf.append(f"fps={float(c['fps']):g}")
        audio = bool(c.get("audio")) and inf.get("has_audio")
        st = src.stat()
        key = hashlib.sha1(json.dumps([MEDIA_RECIPE_V, c, st.st_size, st.st_mtime_ns], sort_keys=True,
                                      default=str).encode()).hexdigest()[:16]
        cached = cache / f"{key}{ext}"
        if not cached.exists():
            cache.mkdir(parents=True, exist_ok=True)
            ctx.progress(detail=f"cutting {Path(out_rel).name} from the original {src.name} ({sw}×{sh})")
            ctx.log(f"Making {out_rel} from the original {src.name} ({sw}×{sh}) – full quality instead of Claude's light copy")
            cmd = [va.ffmpeg_exe(), "-v", "error", "-y"]
            if c.get("start"):
                cmd += ["-ss", f"{float(c['start']):.3f}"]
            cmd += ["-i", str(src)]
            if c.get("duration"):
                cmd += ["-t", f"{float(c['duration']):.3f}"]
            if vf:
                cmd += ["-vf", ",".join(vf)]
            if ext == ".webm":
                cmd += ["-c:v", "libvpx-vp9", "-crf", "20", "-b:v", "0", "-row-mt", "1", "-deadline", "good",
                        "-cpu-used", "4", "-pix_fmt", "yuv420p"] + (["-c:a", "libopus", "-b:a", "128k"] if audio else ["-an"])
            elif ext == ".mov":
                cmd += ["-c:v", "prores_ks", "-profile:v", "3"] + (["-c:a", "pcm_s16le"] if audio else ["-an"])
            else:
                cmd += ["-c:v", "libx264", "-crf", "14", "-preset", "medium", "-pix_fmt", "yuv420p"] + \
                       (["-c:a", "aac", "-b:a", "192k"] if audio else ["-an"])
            tmp = cache / f"{key}.part{ext}"
            r = subprocess.run(cmd + [str(tmp)], capture_output=True, text=True, creationflags=NOWIN)
            if r.returncode != 0 or not tmp.exists():
                tmp.unlink(missing_ok=True)
                raise StepError(f"cutting {out_rel} from {src.name}", (r.stderr or "").splitlines()[-20:])
            os.replace(tmp, cached)
        dst = Path(wd) / out_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cached, dst)
        made.append(out_rel)
    if made:
        ctx.log("Full-quality clips: " + ", ".join(made))
    return made


# ------------------------------------------------------------------ saved styles (a look you liked, for new projects)
CODE_EXT = {".py", ".md", ".json", ".txt", ".html", ".js", ".css", ".svg"}


def styles_dir(S):
    return Path(S["projects_dir"]) / "_styles"


def latest_code_dir(pr):
    """the newest render folder that holds Claude's code: (folder, 'final'|'preview', version) or None"""
    st = pr.state
    for kind, v in (("final", st.get("final_v")), ("preview", st.get("preview_v")),
                    ("preview", st.get("attempt_v")), (st.get("failed_kind"), st.get("failed_version"))):
        if kind and v:
            d = pr.work / f"{kind}_v{v}"
            if (d / "film.py").exists() or (d / "project.json").exists():
                return d, kind, int(v)
    cands = [d for d in pr.work.glob("*_v*") if d.is_dir() and ((d / "film.py").exists() or (d / "project.json").exists())]
    if not cands:
        return None
    d = max(cands, key=lambda p: p.stat().st_mtime)
    kind, _, v = d.name.partition("_v")
    return d, kind, int(v) if v.isdigit() else 0


def save_style(pr, name, note, S, ctx):
    found = latest_code_dir(pr)
    if not found:
        raise UserMessage(f"“{pr.name}” has no video from Claude yet – save a style after the first preview.")
    src, kind, ver = found
    name = (name or pr.name).strip()[:60]
    sid = safe_name(name)
    if not sid:
        raise UserMessage("Give the style a name.")
    root = styles_dir(S)
    d = root / sid
    if d.exists():                       # saving over a style keeps the old one in Recently deleted
        delete_style(S, sid) if (d / "style.json").exists() else shutil.rmtree(d)
    d.mkdir(parents=True)
    n = 0
    for rel, p in episode_files(src):
        if p.suffix.lower() in CODE_EXT and not rel.startswith(("input/", "media/")):
            (d / "code" / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, d / "code" / rel)
            n += 1
    # what it looks like: stills from the newest video
    vid = None
    for p in (pr.state.get("last_final"), pr.state.get("last_preview")):
        if p and Path(p).exists() and Path(p).suffix.lower() in VIDEO_EXT:
            vid = Path(p)
            break
    stills = []
    if vid:
        dur = va.media_info(vid).get("duration") or 0
        (d / "stills").mkdir()
        for i, frac in enumerate((0.08, 0.25, 0.42, 0.58, 0.75, 0.92)):
            out = d / "stills" / f"still_{i + 1}.jpg"
            subprocess.run([va.ffmpeg_exe(), "-v", "error", "-y", "-ss", f"{dur * frac:.2f}", "-i", str(vid),
                            "-frames:v", "1", "-vf", "scale='min(1280,iw)':-2", "-q:v", "3", str(out)],
                           capture_output=True, creationflags=NOWIN)
            if out.exists():
                stills.append(out.name)
    # the fonts it was made with travel along (copied into new projects that use the style)
    fonts = []
    ad = pr.src / "assets"
    for f in sorted(ad.iterdir()) if ad.exists() else []:
        if f.is_file() and f.suffix.lower() in FONT_EXT:
            (d / "fonts").mkdir(exist_ok=True)
            shutil.copy2(f, d / "fonts" / f.name)
            fonts.append(f.name)
    o = pr.order
    info = {"id": sid, "name": name, "note": (note or "").strip()[:2000], "source_project": pr.name,
            "source_version": f"{kind} v{ver}", "engine": "html" if (src / "project.json").exists() else "python",
            "size": o["size"], "fps": o["fps"], "preset": o.get("preset"), "style_preset": o.get("style_preset"),
            "style_notes": o.get("style", ""), "text_amount": o.get("text_amount"), "captions": o.get("captions"),
            "fonts": fonts, "stills": stills, "files": n, "created": now()}
    (d / "style.json").write_text(json.dumps(info, indent=1, ensure_ascii=False), encoding="utf-8")
    ctx.log(f"Saved style “{name}” from {pr.name} ({kind} v{ver}): {n} code files, {len(stills)} stills"
            + (f", fonts: {', '.join(fonts)}" if fonts else ""))
    return info


def list_styles(S):
    out = []
    root = styles_dir(S)
    for d in sorted(root.iterdir()) if root.exists() else []:
        try:
            info = json.loads((d / "style.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if d.name.startswith("_"):
            continue
        out.append({k: info.get(k) for k in ("id", "name", "note", "engine", "source_project", "created", "fonts")}
                   | {"thumb": bool(info.get("stills"))})
    return out


def delete_style(S, sid):
    d = styles_dir(S) / safe_name(str(sid or ""))
    if not (d / "style.json").exists():
        raise UserMessage("That style no longer exists.")
    try:
        name = json.loads((d / "style.json").read_text(encoding="utf-8")).get("name") or d.name
    except (OSError, ValueError):
        name = d.name
    TR.to_trash(d, S, "style", name)


def style_entries(S, o):
    """style_ref/ in the request zip: the code, plan and stills of a video the user liked"""
    sid = o.get("style_ref")
    if not sid:
        return []
    d = styles_dir(S) / safe_name(str(sid))
    try:
        info = json.loads((d / "style.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    md = [f"# Match this style: “{info.get('name')}”",
          "",
          f"The user liked how “{info.get('source_project')}” looked ({info.get('source_version')}, "
          f"{info.get('engine')} engine) and wants this new video in the SAME style.",
          "Reuse its visual language – palette, typography and type sizes, layout and spacing, backgrounds and textures,",
          "camera moves, transitions and their timing, motion curves, sound feel – and adapt its code where that helps.",
          "Do NOT copy its content, text or story: the new video follows this project's narration and brief.",
          ""]
    if info.get("note"):
        md += ["What the user likes about it (binding):", "", info["note"], ""]
    md += ["- `style_ref/stills/` – frames of the finished video (look at them first)",
           "- `style_ref/code/` – the code that made it (PLAN.md explains the ideas)"]
    if info.get("fonts"):
        md.append("- fonts it used are in this project's assets: " + ", ".join(info["fonts"]))
    E = [("style_ref/STYLE.md", "\n".join(md) + "\n")]
    for sub in ("stills", "code"):
        if (d / sub).exists():
            E.append((f"style_ref/{sub}", d / sub))
    return E


def apply_style_fonts(pr, S, o, names, ctx):
    """a saved style's fonts are copied into the new project's assets (the renders need them)"""
    sid = o.get("style_ref")
    fd = styles_dir(S) / safe_name(str(sid or "")) / "fonts"
    if not sid or not fd.exists():
        return names
    ad = pr.src / "assets"
    ad.mkdir(exist_ok=True)
    for f in sorted(fd.iterdir()):
        if f.is_file() and f.name not in names and not (ad / f.name).exists():
            shutil.copy2(f, ad / f.name)
            names.append(f.name)
            ctx.log(f"font from the style: {f.name}")
    return names


def apply_look_fonts(pr, o, names, ctx=None):
    """a signature look's fonts go into the project's assets (Claude's code and the renders load them from there)"""
    lk = OD.look_of(o)
    if not lk:
        return names
    ad = pr.src / "assets"
    ad.mkdir(exist_ok=True)
    for fn in lk.get("fonts", []):
        f = OD.LOOKS_DIR / "fonts" / fn
        if f.is_file() and fn not in names and not (ad / fn).exists():
            shutil.copy2(f, ad / fn)
            names.append(fn)
    for lic in {OD.LOOKS_DIR / "fonts" / f"OFL-{fam}.txt" for fam in lk.get("font_families", [])}:
        if lic.is_file() and not (ad / lic.name).exists():
            shutil.copy2(lic, ad / lic.name)
    if ctx and lk.get("fonts"):
        ctx.log(f"look “{lk['name']}”: {len(lk['fonts'])} font files in assets")
    return names


def look_entries(pr):
    """LOOK.md + look/ (three frames of it) when the project uses a signature look"""
    lk = OD.look_of(pr.order)
    if not lk:
        return []
    apply_look_fonts(pr, pr.order, list(pr.order.get("assets") or []))
    E = [("LOOK.md", OD.LOOKS_DIR / f"{lk['id']}.md")]
    for f in sorted((OD.LOOKS_DIR / "stills").glob(f"{lk['id']}_*.jpg")):
        E.append((f"look/{f.name}", f))
    return E


def proxy_assets(pr, tmpdir, ctx):
    """light copies of the user's assets for Claude (same names); the app renders with the originals.
    Converted copies are kept between packages and only redone when the original file changed."""
    src = pr.src / "assets"
    out = Path(tmpdir)
    out.mkdir(parents=True, exist_ok=True)
    idx_file = pr.work / "_asset_proxies.json"
    try:
        idx = json.loads(idx_file.read_text(encoding="utf-8"))
    except Exception:
        idx = {}
    new_idx, keep = {}, set()
    for f in sorted(src.glob("*")) if src.exists() else []:
        if not f.is_file():
            continue
        ext = f.suffix.lower()
        dst = out / f.name
        st = f.stat()
        key = f"{st.st_size}|{st.st_mtime_ns}"
        keep.add(f.name)
        if idx.get(f.name) == key and dst.exists():
            new_idx[f.name] = key
            continue
        try:
            if ext in VIDEO_EXT and st.st_size > 3e6:
                subprocess.run([va.ffmpeg_exe(), "-v", "error", "-y", "-i", str(f), "-vf", "scale='min(640,iw)':-2",
                                "-c:v", "libx264" if ext in {".mp4", ".mov", ".m4v", ".mkv"} else "libvpx-vp9",
                                "-crf", "30", "-an", str(dst)], creationflags=NOWIN, check=True)
            elif ext in IMAGE_EXT - {".svg", ".gif"} and st.st_size > 1.5e6:
                from PIL import Image
                im = Image.open(f)
                im.thumbnail((2048, 2048))
                im.save(dst)
            else:
                shutil.copy2(f, dst)
            new_idx[f.name] = key
        except Exception as e:
            ctx.log(f"(could not make a light copy of {f.name}: {e}; sending the original)")
            shutil.copy2(f, dst)
    for g in list(out.iterdir()):
        if g.name not in keep:
            if g.is_file():
                g.unlink()
            else:
                shutil.rmtree(g, ignore_errors=True)
    try:
        atomic_write(idx_file, json.dumps(new_idx))
    except OSError:
        pass
    return out


def common_entries(pr, kind, task_md, next_version, extra_manifest=None, narration=True, assets=True, ctx=None):
    o = pr.order
    man = {"app": "vizavi-studio", "app_version": VERSION, "kind": kind, "episode": pr.name, "project": pr.name,
           "next_version": next_version, "created": now(), "fps": o["fps"], "width": o["size"][0], "height": o["size"][1],
           "variants": OD.variants(o), "alpha": o["alpha"], "engine": o["engine"],
           "duration": pr.state.get("duration"), "suggested_nfr": pr.state.get("suggested_nfr"),
           "narration_duration": pr.state.get("narration_duration"),
           "transcript_source": pr.state.get("transcript_source"), "transcript_match": pr.state.get("transcript_match"),
           "text_checks": text_check_opts(pr)}
    man.update(extra_manifest or {})
    E = [("vizavi.json", json.dumps(man, indent=1, ensure_ascii=False)), ("CLAUDE_TASK.md", task_md),
         ("RULES.md", CL / "RULES.md"), ("DIRECTION.md", CL / "DIRECTION.md"),
         ("ENGINE_python.md", CL / "ENGINE_python.md"),
         ("ENGINE_html.md", CL / "ENGINE_html.md")]
    for f in ("brief.md", "order.json", "script.txt", "words.tsv", "words_whisper.tsv", "transcript.txt", "script_alignment.md",
              "asr_passes.md",
              "captions.srt", "beats.tsv"):
        if (pr.src / f).exists():
            E.append((f"input/{f}", pr.src / f))
    for f in (pr.narration(), pr.music()):
        if f and (narration is True or (narration == "small" and f.stat().st_size < 8e6)):
            E.append((f"input/{f.name}", f))
    if (pr.src / "brand").exists():
        E.append(("input/brand", pr.src / "brand"))
    E += look_entries(pr)
    if assets and (pr.src / "assets").exists() and any((pr.src / "assets").iterdir()):
        E.append(("input/assets", proxy_assets(pr, pr.work / "_asset_proxies", ctx or Ctx())))
        man = asset_manifest(pr)
        if man:
            E.append(("input/ASSETS.md", man))
    for f in sorted(KIT.iterdir()):
        if f.is_file():
            E.append((f"kit/{f.name}", f))
    E.append(("kit/vz.js", ENGINES / "vz.js"))
    E.append(("templates", CL / "templates"))
    E.append(("PLAN_TEMPLATE.md", CL / "PLAN_TEMPLATE.md"))
    for f in ("vz_analysis.py", "vz_checks.py", "sandbox_check.py", "vizavi_pack.py", "vz_align.py", "retime.py"):
        E.append((f"tools/{f}", TOOLS / f))
    E.append(("fonts", FONTS))
    E += hardware_entry()
    return E


def fill(tpl, **kw):
    s = (CL / tpl).read_text(encoding="utf-8")
    for k, v in kw.items():
        s = s.replace("{{" + k + "}}", str(v))
    return s


def library_entries(S, o):
    items = []
    for d in sorted(LIB.iterdir()) if LIB.exists() else []:
        if d.is_dir() and ((d / "film.py").exists() or (d / "project.json").exists()):
            info = {}
            try:
                info = json.loads((d / "info.json").read_text(encoding="utf-8"))
            except Exception:
                pass
            info.setdefault("engine", "html" if (d / "project.json").exists() else "python")
            items.append((d, info))
    ex = [i for i in items if i[0].name.startswith("example")]
    rest = [i for i in items if not i[0].name.startswith("example")]

    def score(it):
        d, info = it
        s = 0
        if o["engine"] != "auto" and info.get("engine") == o["engine"]:
            s += 4
        if info.get("preset") == o["preset"]:
            s += 3
        if info.get("aspect") == OD.aspect_id(*o["size"]):
            s += 1
        return (s, info.get("date", ""))
    rest.sort(key=score, reverse=True)
    chosen = ex + rest[:int(S.get("library_in_request", 3))]
    md = ["# Library: earlier projects you can reuse\n",
          "Copy and adapt pieces instead of rewriting. Python examples: camera, splines, sky/lensing, stars,",
          "glow, tonemap, grain, sound. HTML examples: stage setup, typography, canvas drawing, timing helpers.",
          "Note: the first python example uses cairo for 2D overlays - replace that with Pillow when reusing.\n"]
    E = []
    for d, info in chosen:
        md.append(f"## {d.name}  ({info.get('engine')} engine)")
        if info.get("preset"):
            md.append(f"Preset: {info['preset']}, {info.get('size')}, {info.get('fps')} fps, {info.get('duration', '?')} s")
        if info.get("scenes"):
            md.append("Scenes: " + ", ".join(s[0] for s in info["scenes"]))
        if info.get("brief_first_line"):
            md.append(f"Brief: {info['brief_first_line']}")
        for f in sorted(d.rglob("*")):
            if f.is_file() and f.suffix in {".py", ".html", ".js", ".json", ".css"} and f.name != "info.json":
                fns = []
                if f.suffix == ".py":
                    try:
                        fns = [n.name for n in ast.parse(f.read_text(encoding="utf-8")).body
                               if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
                    except Exception:
                        pass
                md.append(f"- `{f.relative_to(d).as_posix()}` ({max(1, f.stat().st_size // 1024)} KB)" +
                          (": " + ", ".join(fns[:40]) if fns else ""))
        md.append("")
        E.append((f"library/{d.name}", d))
    return [("LIBRARY.md", "\n".join(md))] + E


HW_INFO = None      # set by the app at start (studio.hw.detect); detected on demand otherwise


def hardware_entry():
    """HARDWARE.md: the render budget of the PC that will render the package (it may be a laptop without GPU)."""
    global HW_INFO
    try:
        from . import hw
        HW_INFO = HW_INFO or hw.detect(APP)
        return [("HARDWARE.md", hw.hardware_md(HW_INFO))]
    except Exception:
        return []


def build_request_zip(pr, S, ctx):
    o = pr.order
    vs = OD.variants(o)
    task = fill("TASK_request.md", EP=pr.name, DUR=f"{pr.state.get('duration', 0):.2f}", NFR=pr.state.get("suggested_nfr"),
                FPS=o["fps"], SIZE=f"{vs[0]['w']}×{vs[0]['h']}", VARIANTS=", ".join(f"{v['w']}×{v['h']}" for v in vs),
                KIND="final" if o["review"] == "direct" else "preview",
                RESP="yes - responsive layout required" if len(vs) > 1 else "no")
    E = common_entries(pr, "request", task, 1, {"words": pr.state.get("words"), "transcriber": pr.state.get("transcriber"),
                                                "preset": o["preset"]}, ctx=ctx)
    E += style_entries(S, o)
    E += library_entries(S, o)
    z = write_zip(pr.outbox / f"{pr.name}__request.zip", E)
    if z.stat().st_size / 1e6 > float(S["request_zip_max_mb"]):
        ctx.log(f"⚠ {z.name} is {z.stat().st_size / 1e6:.0f} MB – Claude may reject big uploads. "
                f"Use fewer/smaller assets or a compressed narration (mp3).")
    return z


# ------------------------------------------------------------------ zips from Claude
def read_manifest(path):
    path = Path(path)
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            man = json.loads(z.read("vizavi.json").decode("utf-8")) if "vizavi.json" in names else {}
    except zipfile.BadZipFile:
        raise UserMessage(f"{path.name} is not a valid zip.")
    if man.get("project") and not man.get("episode"):
        man["episode"] = man["project"]
    m = re.match(r"(.+?)__(preview|final|request|review|error)(?:_v(\d+))?(?:\s*\(\d+\))?$", path.stem)
    if not man.get("kind") and m:
        man.update(kind=m[2], episode=m[1], version=int(m[3] or 1))
    if not man.get("kind"):
        if any(n.endswith(("film.py", "project.json")) for n in names):
            kind = "final" if "final" in path.stem.lower() else "preview"
            man.update(kind=kind, episode=re.sub(r"[_\- ]*(preview|final).*$", "", path.stem, flags=re.I) or path.stem,
                       version=1, guessed=True)
        else:
            raise UserMessage(f"{path.name} is not a Vizavi package (no vizavi.json / film.py / project.json).")
    man["_names"] = names
    return man


MAX_UNPACKED = 4 * 1024 ** 3


def extract_episode(zpath, names, dest):
    """Unpack Claude's zip into `dest`. Every member must stay inside `dest` (no absolute paths, drive letters,
    '..' or alternate streams) and the whole zip may not unpack to more than 4 GB. Returns how many members
    were skipped as unsafe."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    if any(n.startswith("episode/") for n in names):
        prefix = "episode/"
    else:
        cands = [n for n in names if n.endswith(("film.py", "project.json"))]
        prefix = cands[0].rsplit("/", 1)[0] + "/" if cands and "/" in cands[0] else ""
    skipped = 0
    with zipfile.ZipFile(zpath) as z:
        if sum(i.file_size for i in z.infolist()) > MAX_UNPACKED:
            raise UserMessage(f"{Path(zpath).name} would unpack to more than 4 GB - refusing to open it.")
        for info in z.infolist():
            n = info.filename
            if not n.startswith(prefix) or n.endswith("/") or n == "vizavi.json":
                continue
            rel = safe_member(n[len(prefix):])
            if rel is None:
                skipped += 1
                continue
            out = dest / rel
            if not is_inside(out, dest):
                skipped += 1
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(out, "wb") as dst:
                shutil.copyfileobj(src, dst, 1 << 20)
    if not (dest / "film.py").exists() and not (dest / "project.json").exists():
        raise UserMessage("The zip has neither film.py nor project.json.")
    return skipped


def install_runtime(pr, wd):
    for f in KIT.glob("*.py"):
        shutil.copy2(f, wd / f.name)
    shutil.copy2(ENGINES / "vz.js", wd / "vz.js")
    for name, src in (("fonts", FONTS), ("assets", pr.src / "assets"), ("brand", pr.src / "brand")):
        if (wd / name).exists():
            shutil.rmtree(wd / name)
        if src.exists():
            shutil.copytree(src, wd / name)
    if (wd / "assets").exists() is False:
        (wd / "assets").mkdir()
    # music/narration available to the episode too (e.g. for analysis); never required
    inp = wd / "input"
    inp.mkdir(exist_ok=True)
    for f in (pr.narration(), pr.music(), pr.src / "words.tsv", pr.src / "beats.tsv", pr.src / "captions.srt",
              pr.src / "transcript_claude.md"):
        if f and Path(f).exists():
            shutil.copy2(f, inp / Path(f).name)


def zip_ids(path):
    """(old_id, content_id). The old id (name + size) is only used to recognise zips processed by earlier versions;
    new records use the content id, so a re-sent zip with the same name and size but other content is not skipped."""
    p = Path(path)
    st = p.stat()
    old = hashlib.sha1(f"{p.name}|{st.st_size}".encode()).hexdigest()[:16]
    h = hashlib.sha1(str(st.st_size).encode())
    with open(p, "rb") as f:
        h.update(f.read(1 << 20))
        if st.st_size > (2 << 20):
            f.seek(st.st_size - (1 << 20))
            h.update(f.read(1 << 20))
    return old, "c" + h.hexdigest()[:15]


def zip_id(path):
    return zip_ids(path)[0]


def zip_project_problem(S, man, path):
    """why Claude's zip can't be rendered here, or None. An empty project is never built around Claude's code:
    without the voice, the pictures and the transcript the render is broken, and a deleted project would come back
    as an empty copy next to the real one."""
    name = safe_name(str(man.get("episode") or ""))
    if name and project_exists(S, name):
        return None
    if name and any(e["kind"] == "project" and safe_name(e["name"]) == name for e in TR.list_trash(S)):
        return (f"“{name}” is in Recently deleted – restore it first (Settings → Recently deleted), then drop "
                f"{Path(path).name} again. Its voice, pictures and transcript are in there.")
    return (f"{Path(path).name} is for a project called “{name}”, which isn't on this PC. Claude's zip only holds "
            "the code – the project (voice, pictures, transcript) has to be here first.")


ORDER_CHANGE_KEYS = ("size", "variants", "audio_export", "fps")


def change_order(pr, ch, ctx=None, who="you"):
    """change what the final is made as: main size, extra versions, sound in the export, frame rate. Used by the
    project page and by Claude (a zip's vizavi.json "order_changes", when the user asked for it in the notes).
    Returns the list of changes in words; raises UserMessage for values that can't be used."""
    if not isinstance(ch, dict):
        raise UserMessage("No changes given.")
    o = pr.order
    said = []
    if ch.get("size") is not None:
        try:
            w, h = (int(x) for x in ch["size"][:2])
        except (TypeError, ValueError):
            raise UserMessage("Size must be width and height.")
        w, h = OD.even(w), OD.even(h)
        if not (64 <= w <= 8192 and 64 <= h <= 8192):
            raise UserMessage(f"Size {w}×{h} is not usable.")
        if [w, h] != list(o["size"]):
            said.append(f"size {o['size'][0]}×{o['size'][1]} → {w}×{h}")
            o["size"] = [w, h]
    if ch.get("variants") is not None:
        vs = [v for v in ch["variants"] if isinstance(v, str) and v in OD.EXTRA_VARIANTS]
        if sorted(vs) != sorted(o.get("variants") or []):
            said.append("also as: " + (", ".join(vs) or "nothing else"))
            o["variants"] = vs
    if ch.get("audio_export") is not None:
        a = str(ch["audio_export"])
        if a not in OD.AUDIO_EXPORT:
            raise UserMessage(f"Unknown sound choice “{a}”.")
        if a != o["audio"].get("export"):
            said.append(f"sound: {OD.AUDIO_EXPORT[a]}")
            o["audio"]["export"] = a
    if ch.get("fps") is not None:
        try:
            f = float(ch["fps"])
        except (TypeError, ValueError):
            raise UserMessage("Frame rate must be a number.")
        if not 1 <= f <= 120:
            raise UserMessage(f"Frame rate {f:g} is not usable.")
        f = int(f) if f == int(f) else f
        if f != o["fps"]:
            said.append(f"{o['fps']} → {f} fps")
            o["fps"] = f
    if said:
        (pr.src / "order.json").write_text(json.dumps(o, indent=1, ensure_ascii=False), encoding="utf-8")
        pr.state["final_long_side"] = None           # a new shape: the old "Final size" choice no longer fits
        pr.save()
        if ctx:
            ctx.log(f"Order of “{pr.name}” changed by {who}: " + "; ".join(said))
    return said


def size_mismatch(pr, wd):
    """Claude's design is another shape than anything the final will render (e.g. built 1:1, ordered 9:16)"""
    try:
        if (wd / "project.json").exists():
            pj = json.loads((wd / "project.json").read_text(encoding="utf-8"))
            if pj.get("responsive"):
                return None                          # recomposes for any size: nothing to warn about
            w, h = int(pj["width"]), int(pj["height"])
        else:
            return None
    except (OSError, ValueError, KeyError, TypeError):
        return None
    shapes = [v["w"] / v["h"] for v in OD.variants(pr.order)]
    if any(abs(w / h - s) < 0.01 for s in shapes):
        return None
    return (f"Claude built this version as {w}×{h}, but the project is ordered as "
            f"{', '.join(f'{v['w']}×{v['h']}' for v in OD.variants(pr.order))} – change the size on the project page "
            "(More → Size and sound…) if that's not what you want.")


def process_zip(path, S, ctx):
    path = Path(path)
    man = read_manifest(path)
    kind = man["kind"]
    if kind in ("request", "review", "error"):
        raise UserMessage(f"{path.name} is a package FOR Claude. Drag it into the Claude chat "
                          f"(the message to paste is on your clipboard).")
    problem = zip_project_problem(S, man, path)
    if problem:
        raise UserMessage(problem)
    pr = Project.open(man["episode"], S, create=False)
    try:
        ver = int(man.get("version", 1))
    except (TypeError, ValueError):
        ver = 1
    if path.parent != pr.inbox:
        shutil.copy2(path, pr.inbox / path.name)
    pr.state.setdefault("processed", []).append(zip_ids(path)[1])
    pr.save()
    wd = pr.work / f"{kind}_v{ver}"
    skipped = extract_episode(path, man["_names"], wd)
    if skipped:
        ctx.log(f"(ignored {skipped} file path(s) in the zip that pointed outside the project folder)")
    adopt_claude_words(pr, wd, S, ctx)
    install_runtime(pr, wd)
    if man.get("note"):
        ctx.log(f"Claude's note: {man['note']}")
    if man.get("order_changes"):                    # the user asked Claude for another size / sound in the notes
        try:
            said = change_order(pr, {k: man["order_changes"].get(k) for k in ORDER_CHANGE_KEYS}, ctx, who="Claude (your notes)")
            if said:
                ctx.toast("info", f"“{pr.name}”: Claude changed the order as you asked – " + "; ".join(said)) \
                    if hasattr(ctx, "toast") else None
        except UserMessage as e:
            ctx.log(f"Claude asked for an order change that can't be used: {e}")
    warn = size_mismatch(pr, wd)
    if warn:
        ctx.log("⚠ " + warn)
    return run_guarded(pr, kind, ver, wd, S, ctx)


def adopt_claude_words(pr, wd, S, ctx):
    """Claude's corrected transcript (episode/words.tsv) becomes the project's words: precise MMS timing on
    this PC, new captions. The app's own version is kept as words_app.tsv."""
    cw = wd / "words.tsv"
    if not cw.exists() or not pr.narration():
        return
    new = cw.read_text(encoding="utf-8")
    cur = (pr.src / "words.tsv").read_text(encoding="utf-8") if (pr.src / "words.tsv").exists() else ""
    if (pr.src / "words_claude_raw.tsv").exists() and (pr.src / "words_claude_raw.tsv").read_text(encoding="utf-8") == new:
        return      # same transcript as last time: already adopted (and refined)
    ctx.progress(0, "Adopting Claude's corrected transcript", until=0.02)
    if cur and not (pr.src / "words_app.tsv").exists():
        (pr.src / "words_app.tsv").write_text(cur, encoding="utf-8")
    (pr.src / "words_claude_raw.tsv").write_text(new, encoding="utf-8")
    (pr.src / "words.tsv").write_text(new, encoding="utf-8")
    if (wd / "transcript.md").exists():
        shutil.copy2(wd / "transcript.md", pr.src / "transcript_claude.md")
    if S.get("precise_timing"):
        menv = {"HF_HUB_CACHE": str(Path(S["models_dir"]).expanduser())} if str(S.get("models_dir", "")).strip() else None
        precise_timing(pr, S, ctx, menv)
    from . import media
    media.make_srt(pr.words(), pr.src / "captions.srt")
    shutil.copy2(pr.src / "words.tsv", cw)
    if (wd / "captions.srt").exists():
        shutil.copy2(pr.src / "captions.srt", wd / "captions.srt")
    pr.save()
    n = len(pr.words())
    ctx.log(f"Claude's transcript adopted ({n} words" + (", precise timing" if pr.state.get("timing") == "mms" else "")
            + ") – see Check transcript")


def run_guarded(pr, kind, ver, wd, S, ctx):
    """Runs a render and always leaves the project in a state the UI can act on:
    done / preview ready, 'stopped' (you pressed Stop), or 'error' with a package for Claude. Never 'rendering…'."""
    try:
        build_media(pr, wd, ctx)          # clips Claude cut from light copies are made again from the originals
        if kind == "preview":
            return render_preview(pr, wd, ver, S, ctx)
        return render_final(pr, wd, ver, S, ctx)
    except UserMessage as e:
        if getattr(ctx, "cancelled", False) or str(e) == "Stopped.":
            pr.set("stopped", f"{kind} v{ver} stopped by you", failed_kind=kind, failed_version=ver, stop_reason="stopped")
            ctx.log(f"Stopped. Press Retry render to start {kind} v{ver} again.")
            return {"kind": "stopped", "episode": pr}
        pr.set("stopped", f"{kind} v{ver}: {e}", failed_kind=kind, failed_version=ver, stop_reason="message")
        raise
    except StepError as e:
        err = e
    except Exception as e:      # a crash in our own code (disk full, bad file...) is also an error package, not a hang
        tail = traceback.format_exc().splitlines()[-40:]
        err = StepError(f"{kind} render ({type(e).__name__}: {str(e)[:120]})", tail)
    try:
        z = build_error_zip(pr, wd, kind, ver, err, S, ctx)
    except Exception as e2:
        ctx.log(f"(could not build the error package: {type(e2).__name__}: {e2})")
        z = None
    pr.set("error", f"{kind} v{ver}: {err.step} failed", last_zip=str(z) if z else None, last_kind="error",
           last_version=ver, failed_kind=kind, failed_version=ver)
    ctx.log(f"\u26a0 {err.step} failed." + (f" Error package for Claude: {z.name}" if z else ""))
    return {"kind": "error", "zip": z, "episode": pr}


_RUN_DIR = re.compile(r"^(preview|final)_v(\d+)$")


def retry_target(pr):
    """(kind, version) of the render a Retry would run: the failed one, else the newest render folder."""
    st = pr.state
    if st.get("stage") in ("error", "stopped") and st.get("failed_kind") and st.get("failed_version"):
        return st["failed_kind"], int(st["failed_version"])
    best = None
    if pr.work.exists():
        for d in pr.work.iterdir():
            m = _RUN_DIR.match(d.name)
            if d.is_dir() and m and ((d / "film.py").exists() or (d / "project.json").exists()):
                if best is None or d.stat().st_mtime > best[2]:
                    best = (m[1], int(m[2]), d.stat().st_mtime)
    if best:
        return best[0], best[1]
    for z in sorted(pr.inbox.glob(f"{pr.name}__*_v*.zip"), key=lambda p: p.stat().st_mtime, reverse=True):
        m = re.search(r"__(preview|final)_v(\d+)", z.stem)
        if m:
            return m[1], int(m[2])
    return None


def retry_render(pr, S, ctx):
    """Retry button: run the last (failed) render again with the same Claude zip. Re-extracts the zip when it is
    in from_claude/, refreshes the runtime and the project's assets (so footage added since is picked up)."""
    tgt = retry_target(pr)
    if not tgt:
        raise UserMessage(f"“{pr.name}” has nothing to retry yet – drop Claude's zip on the window first.")
    kind, ver = tgt
    wd = pr.work / f"{kind}_v{ver}"
    zp = pr.inbox / f"{pr.name}__{kind}_v{ver}.zip"
    if zp.exists():
        man = read_manifest(zp)
        extract_episode(zp, man["_names"], wd)
        adopt_claude_words(pr, wd, S, ctx)
    elif not ((wd / "film.py").exists() or (wd / "project.json").exists()):
        raise UserMessage(f"Can't retry {kind} v{ver}: neither {zp.name} nor the render folder is there any more.")
    else:
        for junk in ("out", "cache"):
            if (wd / junk).exists():
                shutil.rmtree(wd / junk, ignore_errors=True)
    install_runtime(pr, wd)
    n = len(list((pr.src / "assets").glob("*"))) if (pr.src / "assets").exists() else 0
    ctx.log(f"Retrying {kind} v{ver} ({n} asset file(s) in the project)")
    return run_guarded(pr, kind, ver, wd, S, ctx)


def add_assets(pr, paths, ctx):
    """Copy files (footage, images, logos...) into the project's source/assets - used by every later render.
    Names are cleaned like at project creation, nothing is overwritten (a different file with the same name gets
    _2), folders are flattened with unique names, and the same file added twice is skipped."""
    ad = pr.src / "assets"
    ad.mkdir(parents=True, exist_ok=True)
    files = []
    for p in map(Path, paths):
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            files += [f for f in sorted(p.rglob("*")) if f.is_file()]
    if len(files) > 300:
        ctx.log(f"(only the first 300 of {len(files)} files are added)")
        files = files[:300]
    taken = {f.name for f in ad.iterdir() if f.is_file()}
    added = []
    for f in files:
        same = ad / safe_asset_name(f.name, set())
        try:
            if same.exists() and same.stat().st_size == f.stat().st_size \
                    and int(same.stat().st_mtime) == int(f.stat().st_mtime):
                continue                                  # this exact file is already there
        except OSError:
            pass
        dst = ad / safe_asset_name(f.name, taken)
        try:
            shutil.copy2(f, dst)
        except OSError as e:
            ctx.log(f"(skipped asset {f.name}: {e.strerror or e})")
            continue
        taken.add(dst.name)
        added.append(dst.name)
    if added:
        of = pr.src / "order.json"
        try:
            data = json.loads(of.read_text(encoding="utf-8"))
            data["assets"] = list(dict.fromkeys(list(data.get("assets") or []) + added))
            atomic_write(of, json.dumps(data, indent=1, ensure_ascii=False))
        except Exception:
            pass
        pr.state.setdefault("history", []).append([now(), pr.state.get("stage", "new"), f"assets added: {', '.join(added)}"])
        pr.save()
        ctx.log(f"Added to \u201c{pr.name}\u201d assets: {', '.join(added)}")
    return added


def build_error_zip(pr, wd, kind, ver, err, S, ctx):
    task = fill("TASK_error.md", EP=pr.name, STAGE=kind, KIND=kind)
    E = common_entries(pr, "error", task, ver + 1, {"failed_kind": kind, "failed_version": ver, "failed_step": err.step},
                       narration=False, ctx=ctx)
    E.append(("error/log.txt", "\n".join(err.tail[-300:])))
    E.append(("error/env.txt", env_report()))
    E += [(f"episode/{rel}", p) for rel, p in episode_files(wd)]
    return write_zip(pr.outbox / f"{pr.name}__error_v{ver}.zip", E)


def env_report():
    lines = [f"app {VERSION}", f"python {sys.version}", f"platform {platform.platform()}",
             f"cpu {platform.processor()} x{os.cpu_count()}"]
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
                           capture_output=True, text=True, timeout=20, creationflags=NOWIN)
        lines.append("gpu " + r.stdout.strip())
    except Exception:
        lines.append("gpu (nvidia-smi not available)")
    for code in ("import cupy,numpy,scipy;print('cupy',cupy.__version__,'numpy',numpy.__version__,'scipy',scipy.__version__)",
                 "import playwright;from importlib.metadata import version;print('playwright',version('playwright'))"):
        try:
            r = subprocess.run([py_exe(), "-c", code], capture_output=True, text=True, timeout=60, creationflags=NOWIN)
            lines.append(r.stdout.strip() or r.stderr.strip()[-200:])
        except Exception as e:
            lines.append(f"check failed: {e}")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ rendering
def render_progress(ctx, base, span):
    rx = re.compile(r"^\[(\d+)/(\d+)\]")
    state = {"dev": None, "batches": [], "chunk": None}

    def on_line(line):
        m = rx.match(line)
        if m:
            g = re.search(r" on (.+?) \|", line)
            if g:
                state["dev"] = g[1]
            b = re.search(r"batch (\d+) in (\d+)s", line)
            if b:
                state["batches"].append((int(b[1]), int(b[2])))
            left = re.search(r"~(\d+)s left", line)
            ctx.progress(base + span * int(m[1]) / int(m[2]),
                         detail=f"batch {m[1]}/{m[2]}" + (f" on {state['dev']}" if state["dev"] else ""),
                         eta=float(left[1]) if left else None)
            return True
        if line.startswith("still f"):
            ctx.progress(detail=line)
            return True
        c = re.search(r"batches of (\d+) frames", line)
        if c:
            state["chunk"] = int(c[1])
        if " render (" in line and "frames" in line:      # "GPU render (python engine): 386 frames ..."
            ctx.progress(detail=line.split(":", 1)[-1].strip())
        return False
    return on_line, state


def project_meta(wd, ctx, logfile):
    tail = run_proc([py_exe(), "vzrender.py", "--meta"], wd, ctx, "read project metadata", env={"RENDER_CPU": "1"},
                    on_line=lambda l: l.startswith("VZMETA"), logfile=logfile)
    meta = next((json.loads(l[6:]) for l in reversed(tail) if l.startswith("VZMETA")), None)
    if not meta:
        raise StepError("read project metadata", tail)
    meta["camera"] = None
    if meta["engine"] == "python":
        code = ("import json, sys\nsys.path.insert(0, %s)\nimport film, vz_analysis as va\n"
                "cs = getattr(film, 'camera_state', None)\n"
                "print('VZCAM' + json.dumps(va.camera_check(cs, film.NFR / film.FPS, film.FPS) if cs else None, default=str))\n"
                ) % json.dumps(str(TOOLS))
        try:
            t2 = run_proc([py_exe(), "-c", code], wd, ctx, "camera check", env={"RENDER_CPU": "1"},
                          on_line=lambda l: l.startswith("VZCAM"), logfile=logfile)
            meta["camera"] = next((json.loads(l[5:]) for l in reversed(t2) if l.startswith("VZCAM")), None)
        except StepError as e:
            ctx.log("(camera check skipped: " + (e.tail[-1] if e.tail else "?") + ")")
    return meta


def spec_mismatch(meta, o):
    """film/project vs the order."""
    out = []
    vs = OD.variants(o)
    if abs(meta["fps"] - float(o["fps"])) > 1e-6:
        out.append(f"project fps {meta['fps']:g} ≠ ordered {o['fps']}")
    if abs(meta["W"] / meta["H"] - vs[0]["w"] / vs[0]["h"]) > 0.01 and not meta.get("responsive"):
        out.append(f"project size {meta['W']}x{meta['H']} has a different aspect than ordered {vs[0]['w']}x{vs[0]['h']}")
    if len(vs) > 1 and not meta.get("responsive"):
        out.append("several aspect variants were ordered but the project is not marked responsive")
    if bool(meta.get("alpha")) != bool(o["alpha"]):
        out.append(f"alpha is {meta.get('alpha')} but the order says {o['alpha']}")
    return out


def render_env(S, pr=None):
    """worker counts fitted to this PC (hw.profile); a number in settings "workers" overrides all.
    With a project: where the renderer keeps the last render's batches, so seconds that did not change are reused."""
    if str(S.get("workers", "")).strip():
        env = {"WORKERS": str(S["workers"])}
    else:
        p = S.get("hw") or {}
        env = {k: str(p[v]) for k, v in (("GPU_WORKERS", "gpu_workers"), ("CPU_WORKERS", "cpu_workers"),
                                         ("HTML_WORKERS", "html_workers")) if p.get(v)}
    if pr is not None and S.get("reuse_unchanged", True):
        env["VZ_CHUNK_CACHE"] = str(pr.work / "_render_cache")
    return env or None


def render_preview(pr, wd, ver, S, ctx):
    t0 = time.time()
    o = pr.order
    log = pr.logs / f"preview_v{ver}.log"
    pr.set("rendering_preview", f"preview v{ver} started", attempt_v=ver)   # preview_v is set only when it SUCCEEDS
    meta = project_meta(wd, ctx, log)
    vs = OD.variants(o)
    pw, ph = OD.preview_size(vs[0]["w"], vs[0]["h"], int(S["preview_long_side"]))
    ctx.progress(0, f"Rendering preview v{ver} ({meta['engine']} engine, {pw}×{ph})", until=0.7)
    on_line, rs = render_progress(ctx, 0, 0.7)
    (wd / "out").mkdir(exist_ok=True)
    tr = time.time()
    (wd / "out" / "text.json").unlink(missing_ok=True)
    run_proc([py_exe(), "vzrender.py", "out/preview.mp4", "--size", f"{pw}x{ph}", "--crf", S["preview_crf"],
              "--textprobe", "out/text.json"], wd, ctx,
             "preview render", env=render_env(S, pr), on_line=on_line, logfile=log)
    render_s = time.time() - tr
    ctx.progress(0.72, "Building the sound + mix", until=0.76)
    run_proc([py_exe(), "vzfast.py", "audio.py"], wd, ctx, "audio.py", logfile=log)
    if not (wd / "mix.wav").exists():
        raise StepError("audio.py (no mix.wav written)", ["audio.py finished but mix.wav is missing"])
    from . import media
    dur = meta["nfr"] / meta["fps"]
    media.build_audio(wd, o, pr.narration(), pr.music(), dur, wd / "preview_audio.wav", preview=True, bed_out=wd / "bed.wav")
    rv = pr.work / f"review_v{ver}"
    if rv.exists():
        shutil.rmtree(rv)
    (rv / "sheets").mkdir(parents=True)
    extra = []
    for v in vs[1:]:
        ctx.progress(0.76, f"Stills of the {v['id']} version", until=0.8)
        sw, sh = OD.preview_size(v["w"], v["h"], 640)
        times = ",".join(f"{dur * k:.2f}" for k in (0.08, 0.3, 0.55, 0.8, 0.97))
        sd = wd / "out" / f"stills_{v['id']}"
        run_proc([py_exe(), "vzrender.py", "--stills", sd, "--size", f"{sw}x{sh}", "--times", times], wd, ctx,
                 f"{v['id']} stills", on_line=on_line, logfile=log)
        extra.append(stills_sheet(sd, rv / f"variant_{v['id']}.jpg", meta["fps"]))
    ctx.progress(0.8, "Adding the timing bar + audio", until=0.92)
    prev = pr.output / f"{pr.name}__preview_v{ver}.mp4"
    hud_pass(wd / "out" / "preview.mp4", wd / "preview_audio.wav", prev, pr.words(), meta["scenes"], meta["fps"], ctx,
             beats=pr.beats(), safe=o.get("safe_area", "none"), nfr=meta["nfr"])
    ctx.progress(0.92, "Automatic checks + review package", until=1.0)
    make_report(pr, wd, ver, meta, rv, render_s, rs["dev"], (pw, ph), o, rs)
    subprocess.run([va.ffmpeg_exe(), "-v", "error", "-y", "-i", str(prev), "-vf",
                    f"fps=1,scale={'320' if pw >= ph else '200'}:-2,tile={'4x4' if pw >= ph else '6x2'}",
                    "-q:v", "4", str(rv / "sheets" / "sheet_%02d.jpg")], creationflags=NOWIN, check=True)
    shrink_for_upload(prev, rv / "preview.mp4", float(S["review_zip_max_mb"]) * 0.7)
    z = build_review_zip(pr, ver, notes="", ctx=ctx)
    pr.set("preview_ready", f"preview v{ver} ready", last_zip=str(z), last_kind="review", last_version=ver,
           last_preview=str(prev), preview_v=ver)
    ctx.progress(1, "Preview ready")
    rj = json.loads((rv / "report.json").read_text(encoding="utf-8"))
    iss, c = rj.get("issues") or [], rj.get("counts") or {}
    ctx.log(f"✓ preview v{ver} in {time.time() - t0:.0f}s → {prev.name}; review package {z.name} "
            f"({z.stat().st_size / 1e6:.1f} MB); checks: " + (", ".join(f"{c[k]} {k}" for k in ("P0", "P1", "P2", "P3") if c.get(k))
                                                             or "nothing found")
            + (" – " + "; ".join(i["text"] for i in iss[:3]) if iss else ""))
    return {"kind": "preview", "video": prev, "zip": z, "episode": pr}


def stills_sheet(d, out, fps):
    from PIL import Image, ImageDraw
    ims = sorted(Path(d).glob("f*.png"))
    if not ims:
        return None
    tiles = []
    for f in ims:
        im = Image.open(f).convert("RGBA")
        bg = Image.new("RGBA", im.size, (30, 30, 34, 255))
        bg.alpha_composite(im)
        t = int(f.stem[1:]) / fps
        ImageDraw.Draw(bg).text((6, 4), f"{t:.2f}s", fill=(255, 255, 255, 255), font=va.load_font(14, "DejaVuSansMono.ttf"))
        tiles.append(bg.convert("RGB"))
    w, h = tiles[0].size
    sheet = Image.new("RGB", (len(tiles) * (w + 6) - 6, h), (60, 60, 60))
    for i, t in enumerate(tiles):
        sheet.paste(t, (i * (w + 6), 0))
    sheet.save(out, quality=85)
    return out


def shrink_for_upload(src, dst, max_mb):
    if src.stat().st_size / 1e6 <= max_mb:
        shutil.copy2(src, dst)
        return
    inf = va.media_info(src)
    long0 = max(inf["width"] or 960, inf["height"] or 540)
    for long_side, crf in ((long0, 28), (768, 30), (640, 32)):
        sc = f"scale={long_side}:-2" if (inf["width"] or 1) >= (inf["height"] or 1) else f"scale=-2:{long_side}"
        subprocess.run([va.ffmpeg_exe(), "-v", "error", "-y", "-i", str(src), "-vf", sc, "-c:v", "libx264", "-preset",
                        "veryfast", "-crf", str(crf), "-c:a", "aac", "-b:a", "96k", str(dst)], creationflags=NOWIN, check=True)
        if dst.stat().st_size / 1e6 <= max_mb:
            return


def saved_notes(pr):
    """the notes currently stored in the review zip of the ready preview ('' when none)"""
    ver = pr.state.get("preview_v")
    f = pr.work / f"review_v{ver}" / "USER_NOTES.md" if ver else None
    try:
        t = f.read_text(encoding="utf-8") if f and f.exists() else ""
    except OSError:
        return ""
    if not t.startswith("# Notes from the user"):
        return ""
    return t[len("# Notes from the user"):].strip()


def write_notes(pr, ver, notes):
    """store the user's notes for the review zip of preview `ver` (also used by the page's auto-save)"""
    rv = pr.work / f"review_v{ver}"
    rv.mkdir(parents=True, exist_ok=True)
    (rv / "USER_NOTES.md").write_text(("# Notes from the user\n\n" + notes.strip() + "\n") if notes.strip()
                                      else "(no notes from the user)\n", encoding="utf-8")


def build_review_zip(pr, ver, notes="", ctx=None):
    rv = pr.work / f"review_v{ver}"
    wd = pr.work / f"preview_v{ver}"
    if not wd.exists():
        raise UserMessage(f"The folder of preview v{ver} is gone, so no review package can be built for it.")
    if notes is not None:
        write_notes(pr, ver, notes)
    o = pr.order
    task = fill("TASK_review.md", EP=pr.name, V=ver, KIND="final")
    E = common_entries(pr, "review", task, ver + 1, {"reviewed_version": ver}, narration="small", ctx=ctx)
    E += [(f"episode/{rel}", p) for rel, p in episode_files(wd)]
    E.append(("review", rv))
    return write_zip(pr.outbox / f"{pr.name}__review_v{ver}.zip", E)


SAFE_BOXES = OD.SAFE_BOXES      # one table for the brief Claude reads and the blue box in the preview


def hud_pass(video, audio_wav, out, words, scenes, fps, ctx, beats=None, safe="none", nfr=None):
    """Preview = rendered video + a timing bar underneath (clock, scene, spoken words, beats) + the audio.
    ffmpeg decodes the preview and stacks it on top of the bar itself; Python only draws the small bar strip,
    and re-uses a drawn strip for as long as nothing but the clock changes. No full frame ever passes through
    Python, which is several times faster than the old frame-by-frame loop."""
    from PIL import Image, ImageDraw
    inf = va.media_info(video)
    W, H = inf["width"], inf["height"]
    bar = max(44, round(min(W, H) * 0.1)) // 2 * 2
    ff = va.ffmpeg_exe()
    n_est = int(nfr) if nfr else (int(round((inf["duration"] or 0) * fps)) or 1)
    dur = n_est / fps
    fm = va.load_font(int(bar * 0.28), "DejaVuSansMono.ttf")
    fw = va.load_font(int(bar * 0.34), "DejaVuSans.ttf")
    fb = va.load_font(int(bar * 0.38), "DejaVuSans-Bold.ttf")
    sb = OD.SAFE_BOXES.get(safe)
    chain = "null"
    if sb:      # the blue safe-area box is drawn by ffmpeg on the video part
        y0b, y1b, x1b = int(H * sb[0]), int(H * (1 - sb[1])), int(W * (1 - sb[2]))
        chain = f"drawbox=x=0:y={y0b}:w={x1b}:h={max(2, y1b - y0b)}:color=0x50C8FF:t=1"
    # setpts on both inputs: frames pair up 1:1 by index, whatever the timestamps in the files look like
    flt = (f"[0:v]{chain},setpts=N/({fps}*TB)[v0];[1:v]format=yuv420p,setpts=N/({fps}*TB)[b];"
           f"[v0][b]vstack=inputs=2:shortest=1,format=yuv420p[v]")
    errf = open(str(out) + ".log", "w")
    wr = subprocess.Popen([ff, "-v", "error", "-y", "-i", str(video),
                           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{bar}", "-r", str(fps), "-i", "-",
                           "-i", str(audio_wav), "-filter_complex", flt, "-map", "[v]", "-map", "2:a",
                           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(out)],
                          stdin=subprocess.PIPE, stderr=errf, creationflags=NOWIN)
    BG = (8, 8, 10)
    y0 = 2
    ty = 11
    tl0 = f"{0:6.2f}s f{0:04d}"
    cache = {}

    def base_strip(wi, speaking, sname):
        """everything in the bar that does not change every frame"""
        im = Image.new("RGB", (W, bar), BG)
        g = ImageDraw.Draw(im)
        for k, sc in enumerate(scenes or []):
            x0, x1 = W * sc[1] / max(dur, 1e-6), W * sc[2] / max(dur, 1e-6)
            g.rectangle([x0, y0, x1, y0 + 4], fill=(60, 64, 80) if k % 2 else (90, 96, 120))
        for b in beats or []:
            xb = W * b / max(dur, 1e-6)
            g.line([xb, y0 + 5, xb, y0 + 8], fill=(150, 110, 60))
        g.text((6, ty + int(bar * 0.38)), sname, fill=(150, 160, 200), font=fm)
        left = max(g.textbbox((6, ty), tl0, font=fm)[2], g.textbbox((6, ty), sname or " ", font=fm)[2])
        x = max(int(W * 0.30), left + 18)
        back = 3 if W >= 900 else (1 if W >= 480 else 0)
        rng = range(max(0, wi - back), min(len(words), wi + 3)) if wi >= 0 else range(0, min(3, len(words)))
        for j in rng:
            w = words[j][2]
            if j == wi and speaking:
                g.text((x, ty), w, fill=(255, 255, 255), font=fb)
                bb = g.textbbox((x, ty), w, font=fb)
                g.rectangle([bb[0], bb[3] + 3, bb[2], bb[3] + 5], fill=(230, 180, 80))
                x = bb[2] + 12
            else:
                g.text((x, ty + 2), w, fill=(120, 120, 125) if j <= wi else (80, 80, 85), font=fw)
                x = g.textbbox((x, ty + 2), w, font=fw)[2] + 10
            if x > W - 20:
                break
        return im

    i = 0
    try:
        for i in range(n_est + 2):      # two spare frames: the video (shortest input) decides where it ends
            if getattr(ctx, "cancelled", False):
                raise UserMessage("Stopped.")
            t = i / fps
            wi, speaking = va.word_at(words, t)
            sname = va.scene_at(scenes, t)[:24]
            key = (wi, bool(speaking), sname)
            im = cache.get(key)
            if im is None:
                if len(cache) > 64:
                    cache.clear()
                im = cache[key] = base_strip(wi, speaking, sname)
            frame = im.copy()
            g = ImageDraw.Draw(frame)
            g.rectangle([0, y0, W * min(t, dur) / max(dur, 1e-6), y0 + 4], fill=(230, 180, 80))
            g.text((6, ty), f"{t:6.2f}s f{i:04d}", fill=(200, 200, 200), font=fm)
            try:
                wr.stdin.write(frame.tobytes())
            except (BrokenPipeError, OSError):
                break
            if i % 48 == 0:
                ctx.progress(0.8 + 0.12 * min(1, i / max(1, n_est)), detail=f"frame {i}/{n_est}")
    finally:
        try:
            wr.stdin.close()
        except OSError:
            pass
        if getattr(ctx, "cancelled", False):
            wr.kill()
        wr.wait()
        errf.close()
    if wr.returncode != 0 or i == 0:
        raise StepError("HUD/audio mux", Path(str(out) + ".log").read_text(errors="replace").splitlines()[-30:])
    os.remove(str(out) + ".log")


LATIN_RULE = re.compile(r"latin|lotin", re.I)


def text_check_opts(pr):
    """what the text checks need to know about the order: the platform's button zones and the Latin-only rule"""
    o = pr.order
    rules = " ".join(str(o.get(k) or "") for k in ("standing_rules", "care", "wants"))
    return {"safe": OD.SAFE_BOXES.get(o.get("safe_area") or "none"), "latin_only": bool(LATIN_RULE.search(rules))}


def text_vocab(pr):
    """the words the video is about, spelled right: the author's script and the transcript"""
    parts = []
    for f in ("script.txt", "transcript_claude.md", "transcript.txt"):
        try:
            parts.append((pr.src / f).read_text(encoding="utf-8"))
        except OSError:
            pass
    parts.append(" ".join(w[2] for w in pr.words()))
    parts.append(str(pr.order.get("wants") or ""))
    return "\n".join(parts)


def run_text_checks(pr, probe_file, o):
    """(issues, summary) from the renderer's text probe; ([], None) when there is nothing to judge"""
    try:
        P = json.loads(Path(probe_file).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [], None
    if not P.get("supported"):
        return [], None
    opts = text_check_opts(pr)
    return vc.analyze_text(P["samples"], P["W"], P["H"], step=P.get("step", 0.25), safe=opts["safe"],
                           vocab_text=text_vocab(pr), latin_only=opts["latin_only"])


def make_report(pr, wd, ver, meta, rv, render_s, dev, psize, o, rs=None):
    fps, nfr = meta["fps"], meta["nfr"]
    vd = nfr / fps
    words = pr.words()
    flags = spec_mismatch(meta, o)
    vres = va.analyze_video(wd / "out" / "preview.mp4", fps, meta["scenes"])
    flags += vres["flags"]
    if vres["frames"] != nfr:
        flags.append(f"video has {vres['frames']} frames, project says {nfr}")
    want = pr.state.get("duration")
    if want and abs(vd - want) > 1.0 and o["duration"]["mode"] != "narration":
        flags.append(f"duration {vd:.2f}s differs from the ordered {want:.2f}s")
    bed = wd / "bed.wav" if (wd / "bed.wav").exists() else wd / "mix.wav"
    ares = va.analyze_audio(bed, pr.narration(), vd, words, meta["scenes"], rv / "audio_plot.png")
    flags += ares["flags"]
    cam = meta.get("camera")
    if cam and cam.get("issues"):
        flags += [f"camera {k} at {t}s" for t, k in cam["issues"]]
    if not meta["scenes"]:
        flags.append("SCENES missing")
    cue_rows = []
    for c in meta.get("cues", []):
        t, wtxt = float(c[0]), (str(c[1]) if len(c) > 1 else "")
        what = c[2] if len(c) > 2 else ""
        cands = [w for w in words if norm_tok(w[2]) == norm_tok(wtxt) and abs(w[0] - t) < 2.0]
        if cands and wtxt:
            w = min(cands, key=lambda w: abs(w[0] - t))
            off = t - w[0]
            ok = -0.3 <= off <= 0.15
            cue_rows.append(f"| {t:.2f} | {wtxt} | {w[0]:.2f} | {off:+.2f} | {'ok' if ok else 'OFF'} | {what} |")
            if not ok:
                flags.append(f"cue '{wtxt}' at {t:.2f}s is {off:+.2f}s from the spoken word ({w[0]:.2f}s)")
        elif wtxt:
            cue_rows.append(f"| {t:.2f} | {wtxt} | – | – | word not found ±2s | {what} |")
    beats = pr.beats()
    beat_rows = []
    if beats:
        for sc in meta["scenes"][1:]:
            b = min(beats, key=lambda x: abs(x - sc[1]))
            off = sc[1] - b
            beat_rows.append(f"| {sc[0]} | {sc[1]:.2f} | {b:.2f} | {off:+.3f} |")
            if abs(off) > 1.5 / fps:
                flags.append(f"scene '{sc[0]}' starts {off:+.2f}s off the nearest beat")
    text_issues, text_sum = run_text_checks(pr, wd / "out" / "text.json", o)
    issues = vc.ranked(flags, text_issues)
    full = max(OD.variants(o)[0]["w"], OD.variants(o)[0]["h"])
    est = render_s * (full / max(psize)) ** 2 / 60 * len(OD.variants(o))
    cost = {}       # where the render time goes, per scene (worker seconds of the preview render)
    if rs and rs.get("batches") and rs.get("chunk") and meta["scenes"]:
        for ci, dt in rs["batches"]:
            nm = va.scene_at(meta["scenes"], (ci * rs["chunk"] + rs["chunk"] / 2) / fps) or "?"
            cost[nm] = cost.get(nm, 0) + dt
    md = [f"# Automatic report – {pr.name} preview v{ver}", "",
          f"- order: {o['preset']}; {OD.variants(o)[0]['w']}×{OD.variants(o)[0]['h']} @ {o['fps']} fps; "
          f"variants {[v['id'] for v in OD.variants(o)]}; alpha {o['alpha']}; audio export '{o['audio']['export']}'",
          f"- engine {meta['engine']} on {dev or '?'}; preview {psize[0]}×{psize[1]} took {render_s:.0f}s → final ≈ {est:.0f} min (rough)",
          f"- durations: video {vd:.2f}s ({nfr} f), narration {ares.get('narration_duration')}s, ordered {want}s",
          f"- mean luma {vres.get('mean_luma')}, median frame-to-frame change {vres.get('motion_p50')}",
          "- the preview audio always includes the narration (for judging sync), even if the export won't", "",
          "## Findings, most severe first (fix P0/P1; P2/P3 if the pass has room)"]
    md += vc.report_md(issues, text_sum, meta["engine"])
    md += [f"- **{i['rank']}** {i['text']}" for i in issues] or ["- none"]
    md += ["", "## Scene boundaries", "| t | frame | change | type |", "|---|---|---|---|"]
    md += [f"| {b['t']} | {b['frame']} | {b['change']} | {b['type']} |" for b in vres.get("boundaries", [])]
    md += ["", "## Camera", "- n/a (html engine)" if meta["engine"] == "html" else
           ("- not checked (camera_state missing)" if not cam else (("- smooth" if cam.get("ok") else "- issues: " +
            "; ".join(f"{t}s {k}" for t, k in cam.get("issues", []))) if not cam.get("error") else "- " + cam["error"]))]
    md += ["", "## Sound",
           f"- bed (everything but the voice): {ares.get('mix_lufs')} LUFS, true peak {ares.get('mix_true_peak')} dBTP",
           f"- narration: {ares.get('narration_lufs')} LUFS; under the voice while speaking: {ares.get('voice_over_bed_db')} dB (want ≥ 12)",
           "- see audio_plot.png (orange = bed incl. music if any)"]
    if beat_rows:
        md += ["", "## Scene starts vs beats", "| scene | starts | nearest beat | offset |", "|---|---|---|---|"] + beat_rows
    if cue_rows:
        md += ["", "## Cue sync (CUES vs spoken words; want −0.30…+0.15 s)", "| cue t | word | spoken at | offset | | action |",
               "|---|---|---|---|---|---|"] + cue_rows
    if cost and sum(cost.values()) > 0:
        tot = sum(cost.values())
        md += ["", "## Render cost per scene (preview render; the final costs about the same share)",
               "| scene | seconds | share |", "|---|---|---|"]
        md += [f"| {k} | {v:.0f} | {100 * v / tot:.0f}% |" for k, v in sorted(cost.items(), key=lambda kv: -kv[1])]
    if len(OD.variants(o)) > 1:
        md += ["", "## Other aspect versions", "Stills: " + ", ".join(f"variant_{v['id']}.jpg" for v in OD.variants(o)[1:])]
    (rv / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (rv / "report.json").write_text(json.dumps({"flags": flags, "issues": issues, "counts": vc.counts(issues),
                                                "text": text_sum, "video": {k: v for k, v in vres.items() if not k.startswith("_")},
                                                "audio": ares, "camera": cam, "render_seconds": render_s,
                                                "est_final_min": round(est, 1), "scene_cost": cost},
                                               indent=1, default=str), encoding="utf-8")


def final_variants(pr, o):
    """the sizes to render for the final. 'Final size' on the project page can lower the longest side (e.g. 1920) to
    make the final several times faster; never above the ordered size."""
    vs = OD.variants(o)
    try:
        ls = int(pr.state.get("final_long_side") or 0)
    except (TypeError, ValueError):
        ls = 0
    if ls < 320:
        return vs
    out = []
    for v in vs:
        s = ls / max(v["w"], v["h"])
        out.append(v if s >= 1 else {**v, "w": OD.even(v["w"] * s), "h": OD.even(v["h"] * s)})
    return out


def keep_earlier_finals(pr, ctx):
    """a new final never overwrites the last one: earlier final files move to output/earlier finals/<date time>/"""
    old = [f for f in pr.output.iterdir() if (f.is_file() and "__preview_v" not in f.name)
           or (f.is_dir() and f.name.endswith("__png"))] if pr.output.exists() else []
    if not old:
        return
    dest = pr.output / "earlier finals" / time.strftime("%Y-%m-%d %H-%M")
    dest.mkdir(parents=True, exist_ok=True)
    for f in old:
        try:
            shutil.move(str(f), str(dest / f.name))
        except OSError as e:
            ctx.log(f"(couldn't keep {f.name} aside: {e})")
    ctx.log(f"The previous final is kept in output/earlier finals/{dest.name}/")


def render_final(pr, wd, ver, S, ctx):
    t0 = time.time()
    o = pr.order
    log = pr.logs / f"final_v{ver}.log"
    pr.set("rendering_final", f"final v{ver} started", final_v=ver)
    meta = project_meta(wd, ctx, log)
    vs = final_variants(pr, o)
    if vs[0]["w"] != OD.variants(o)[0]["w"]:
        ctx.log(f"Final size lowered to {vs[0]['w']}x{vs[0]['h']} (ordered {OD.variants(o)[0]['w']}x{OD.variants(o)[0]['h']})")
    alpha = bool(o["alpha"]) and bool(meta.get("alpha"))
    (wd / "out").mkdir(exist_ok=True)
    ctx.progress(0.0, f"Final v{ver}: building the sound", until=0.03)
    for f in ("mix.wav",):
        if (wd / f).exists():
            (wd / f).unlink()
    run_proc([py_exe(), "vzfast.py", "audio.py"], wd, ctx, "audio.py", logfile=log)
    from . import media
    dur = meta["nfr"] / meta["fps"]
    media.build_audio(wd, o, pr.narration(), pr.music(), dur, wd / "final_audio.wav")
    keep_earlier_finals(pr, ctx)
    outputs = []
    span = 0.9 / len(vs)
    for k, v in enumerate(vs):
        ext = ".mov" if alpha else ".mp4"
        master = wd / "out" / f"master_{v['id']}{ext}"
        ctx.progress(0.03 + k * span, f"Rendering {v['w']}×{v['h']} ({v['id']}, {k + 1} of {len(vs)}) – "
                                      f"{meta['engine']} engine", until=0.03 + (k + 0.85) * span)
        on_line, _ = render_progress(ctx, 0.03 + k * span, span * 0.85)
        run_proc([py_exe(), "vzrender.py", master, "--size", f"{v['w']}x{v['h']}", "--crf", S["final_crf"]] +
                 (["--codec", "prores"] if alpha else []), wd, ctx, f"final render {v['id']}", env=render_env(S, pr),
                 on_line=on_line, logfile=log)
        ctx.progress(0.03 + (k + 0.85) * span, f"Encoding {', '.join(o['formats'])} for {v['id']}",
                     until=0.03 + (k + 1) * span)
        base = pr.name if len(vs) == 1 else f"{pr.name}__{v['id']}"
        try:
            b0 = 0.03 + (k + 0.85) * span
            outputs += media.export_all(master, wd / "final_audio.wav", o, alpha, base, pr.output, ctx.log,
                                        on_fmt=lambda i, n, f: ctx.progress(b0 + 0.15 * span * i / n,
                                                                            detail=f"format {i + 1}/{n}: {f}"))
        except RuntimeError as e:
            raise StepError(f"export {v['id']}", str(e).splitlines())
        master.unlink(missing_ok=True)
    if o["captions"] in ("srt", "burned+srt") and (pr.src / "captions.srt").exists():
        dst = pr.output / f"{pr.name}.srt"
        shutil.copy2(pr.src / "captions.srt", dst)
        outputs.append(dst)
    problems = []
    for p in outputs:
        if p.suffix == ".mp4":
            inf = va.media_info(p)
            nreal = media.video_frames(p)
            if nreal is not None and abs(nreal - meta["nfr"]) > 1:
                problems.append(f"{p.name}: {nreal} frames instead of {meta['nfr']}")
            elif nreal is None and inf["fps"] and abs(inf["fps"] - float(o["fps"])) > 0.5:
                problems.append(f"{p.name}: fps {inf['fps']}")
            if o["audio"]["export"] != "silent" and not inf["has_audio"]:
                problems.append(f"{p.name}: no audio track")
            if inf["duration"] and abs(inf["duration"] - dur) > 0.1:
                problems.append(f"{p.name}: {inf['duration']:.2f}s instead of {dur:.2f}s")
    save_library(pr, wd, ctx, meta)
    main_out = next((p for p in outputs if p.suffix in (".mp4", ".mov", ".webm")), outputs[0] if outputs else pr.output)
    pr.set("done", f"final v{ver} ready" + (f" (check: {', '.join(problems)})" if problems else ""),
           last_final=str(main_out), last_kind="final", last_version=ver, last_zip=None)
    ctx.progress(1, "Final ready")
    ctx.log(f"✓ final in {(time.time() - t0) / 60:.1f} min: " + ", ".join(p.name for p in outputs) +
            (f"  ⚠ {', '.join(problems)}" if problems else ""))
    return {"kind": "final", "video": main_out, "outputs": outputs, "episode": pr, "problems": problems}


def approve_preview(pr, S, ctx):
    if pr.state.get("stage") != "preview_ready":
        raise UserMessage("There is no preview waiting for approval.")
    ver = int(pr.state.get("preview_v") or 0)
    src = pr.work / f"preview_v{ver}"
    if not ver or not src.exists():
        raise UserMessage("No rendered preview to approve.")
    wd = pr.work / f"final_v{ver}"
    if wd.exists():
        shutil.rmtree(wd)
    shutil.copytree(src, wd, ignore=shutil.ignore_patterns("out", "*.wav", "__pycache__"))
    install_runtime(pr, wd)
    return run_guarded(pr, "final", ver, wd, S, ctx)


def save_library(pr, wd, ctx, meta):
    d = LIB / pr.name
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    for rel, p in episode_files(wd):
        if p.suffix.lower() in {".py", ".md", ".json", ".txt", ".html", ".js", ".css", ".svg"} and rel != "input":
            if rel.startswith("input/"):
                continue
            (d / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, d / rel)
    o = pr.order
    brief = (o.get("wants") or o.get("brief") or o.get("purpose") or "").strip().splitlines()
    info = {"episode": pr.name, "date": now(), "duration": pr.state.get("duration"), "scenes": meta.get("scenes", []),
            "engine": meta.get("engine"), "preset": o["preset"], "size": o["size"], "fps": o["fps"],
            "aspect": OD.aspect_id(*o["size"]), "brief_first_line": brief[0][:160] if brief else ""}
    (d / "info.json").write_text(json.dumps(info, indent=1, ensure_ascii=False), encoding="utf-8")


# ------------------------------------------------------------------ CLI (debugging)
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    a1 = sp.add_parser("new")
    a1.add_argument("--preset", default="Narrated explainer 16:9 (cinematic, no voice)")
    a1.add_argument("--narration"); a1.add_argument("--music"); a1.add_argument("--name", default="")
    a1.add_argument("--script", default=""); a1.add_argument("--brief", default="")
    a1.add_argument("--assets", nargs="*", default=[]); a1.add_argument("--set", nargs="*", default=[])
    a2 = sp.add_parser("drop"); a2.add_argument("zip")
    a3 = sp.add_parser("approve"); a3.add_argument("project")
    a4 = sp.add_parser("notes"); a4.add_argument("project"); a4.add_argument("text")
    a = ap.parse_args()
    S, ctx = load_settings(), Ctx()
    rd = lambda p: Path(p).read_text(encoding="utf-8") if p else ""
    try:
        if a.cmd == "new":
            o = OD.from_preset(a.preset, S.get("user_presets"))
            o["name"] = a.name
            o["wants"] = rd(a.brief)
            for kv in a.set:
                k, v = kv.split("=", 1)
                cur = o
                ks = k.split(".")
                for kk in ks[:-1]:
                    cur = cur[kk]
                cur[ks[-1]] = json.loads(v) if v[:1] in "[{0123456789tf-" or v in ("true", "false") else v
            new_project(o, {"narration": Path(a.narration) if a.narration else None,
                            "music": Path(a.music) if a.music else None,
                            "assets": [Path(x) for x in a.assets], "script": rd(a.script)}, S, ctx)
        elif a.cmd == "drop":
            r = process_zip(a.zip, S, ctx)
            print({k: str(v) for k, v in r.items()})
        elif a.cmd == "approve":
            print(approve_preview(Project.open(a.project, S, create=False), S, ctx))
        elif a.cmd == "notes":
            pr = Project.open(a.project, S, create=False)
            print(build_review_zip(pr, int(pr.state["preview_v"]), a.text))
    except UserMessage as e:
        print("MESSAGE:", e)
        sys.exit(1)
