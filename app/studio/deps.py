"""First-run setup (stdlib only): installs missing Python packages, creates the app icon and the
Desktop + 'Send to' shortcuts. Everything is logged through the given log() callback."""
import importlib, json, os, re, shutil, subprocess, sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
NOWIN = 0x08000000 if os.name == "nt" else 0
MARK = APP / ".setup_done"


def py_exe():
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe" and exe.with_name("python.exe").exists():
        return str(exe.with_name("python.exe"))
    return str(exe)


def pyw_exe():
    exe = Path(sys.executable)
    w = exe.with_name("pythonw.exe")
    return str(w if w.exists() else exe)


def has(mod):
    importlib.invalidate_caches()
    try:
        r = subprocess.run([py_exe(), "-c", f"import {mod}"], capture_output=True, timeout=180, creationflags=NOWIN)
        return r.returncode == 0
    except Exception:
        return False


LOCK = APP / ".deps_lock.txt"      # versions that worked together last time: new installs are held to them
LOCK_PKGS = ("numpy", "scipy", "pillow", "imageio-ffmpeg", "faster-whisper", "ctranslate2", "transformers",
             "playwright", "cupy-cuda12x")


def write_lock(log):
    """remember the working versions (public version numbers only) so a later repair can't pull in something newer
    that breaks the app"""
    code = ("import importlib.metadata as m,sys\n"
            "for p in sys.argv[1:]:\n"
            "    try: print(p+'=='+m.version(p).split('+')[0])\n"
            "    except Exception: pass\n")
    try:
        r = subprocess.run([py_exe(), "-c", code, *LOCK_PKGS], capture_output=True, text=True, timeout=120,
                           creationflags=NOWIN)
        if r.returncode == 0 and r.stdout.strip():
            LOCK.write_text(r.stdout, encoding="utf-8")
    except Exception as e:
        log(f"(could not record package versions: {e})")


def pip(pkgs, log, extra_args=(), constrain=True):
    for extra in ([], ["--user"]):
        cons = ["-c", str(LOCK)] if constrain and LOCK.exists() else []
        cmd = [py_exe(), "-m", "pip", "install", "--disable-pip-version-check", *cons, *extra_args, *extra, *pkgs]
        log("pip install " + " ".join(pkgs) + (" (user)" if extra else ""))
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             encoding="utf-8", errors="replace", creationflags=NOWIN)
        for line in p.stdout:
            line = line.rstrip()
            if line and not line.startswith(("  Downloading", "  Using cached", "Requirement already")):
                log("   " + line[:200])
        if p.wait() == 0:
            return True
    return False


def ensure(log, prof=None, force=False):
    """returns list of warnings. Fast when everything is installed. prof = studio.hw profile of this PC:
    GPU parts are only installed where they can run, the Uzbek pack only with enough memory/disk."""
    warn = []
    prof = prof or {"gpu_speech": bool(shutil.which("nvidia-smi")), "gpu_render": bool(shutil.which("nvidia-smi")),
                    "uzbek_pack": True, "low_disk": False}
    if prof.get("low_disk"):
        warn.append("Less than 12 GB free on this drive – speech models and renders may not fit. Free some space.")
    need = [(m, p) for m, p in (("numpy", "numpy"), ("scipy", "scipy"), ("PIL", "pillow"),
                                ("imageio_ffmpeg", "imageio-ffmpeg")) if not has(m)]
    if need:
        log("Installing basic components (one time)…")
        if not pip([p for _, p in need], log):
            warn.append("Could not install: " + ", ".join(p for _, p in need))
    if not has("faster_whisper") and not has("whisper"):
        log("Installing Whisper (one time, a few minutes)…")
        if not (pip(["faster-whisper"], log) and has("faster_whisper")):
            log("faster-whisper unavailable, trying openai-whisper…")
            if not (pip(["openai-whisper"], log) and has("whisper")):
                warn.append("Whisper could not be installed - transcription will fail. "
                            "Try: py -m pip install faster-whisper")
    try:
        cfg = json.loads((APP / "settings.json").read_text(encoding="utf-8"))
    except Exception:
        cfg = {}
    if prof["gpu_speech"] and not (APP / ".cuda_libs_ok").exists():
        log("Installing CUDA libraries so Whisper can use the GPU (one time, ~1 GB)…")
        if pip(["nvidia-cublas-cu12", "nvidia-cudnn-cu12"], log):
            (APP / ".cuda_libs_ok").write_text("ok")
        else:
            warn.append("CUDA libraries for Whisper could not be installed - transcription will use the CPU.")
    if prof["uzbek_pack"] and (cfg.get("uzbek_model", "x") or cfg.get("precise_timing", True)):
        if not (has("torch") and has("transformers")):
            log("Installing the Uzbek accuracy pack (PyTorch + Transformers, one time)…")
            if not install_torch(log, prof):
                warn.append("Uzbek accuracy pack missing (torch/transformers): the Uzbek model and precise timing "
                            "are skipped; Whisper large-v3 is used.")
            elif not pip(["transformers"], log) or not has("transformers"):
                warn.append("Uzbek accuracy pack missing (transformers): the Uzbek model and precise timing "
                            "are skipped; Whisper large-v3 is used.")
        elif prof.get("gpu_speech") and force and not torch_cuda_ok():
            # only on 'Check and repair components' (it is a multi-GB download): swap a processor-only PyTorch for the graphics-card build
            if not install_torch(log, prof, replace=True):
                warn.append("PyTorch runs on the processor only (the Uzbek model and precise timing will be slower).")
    if not has("playwright"):
        log("Installing the HTML engine (Playwright + Chromium, one time)…")
        if not pip(["playwright"], log):
            warn.append("Playwright missing: HTML-engine projects cannot render. Try: py -m pip install playwright")
    if has("playwright") and not (APP / ".chromium_ok").exists():
        log("Downloading Chromium for the HTML engine (one time, ~150 MB)…")
        r = subprocess.run([py_exe(), "-m", "playwright", "install", "chromium"], capture_output=True, text=True,
                           creationflags=NOWIN)
        if r.returncode == 0:
            (APP / ".chromium_ok").write_text("ok")
        else:
            warn.append("Chromium download failed (HTML engine): " + (r.stderr or r.stdout)[-300:])
    if prof["gpu_render"]:
        if not has("cupy"):
            log("Installing CuPy for GPU rendering (one time)…")
            if not (pip(["cupy-cuda12x[ctk]"], log) and has("cupy")):
                warn.append("CuPy could not be installed: renders run on the processor (slower).")
        if has("cupy"):
            ok, err = cupy_works()
            if not ok and re.search(r"CUDA headers|nvrtc|NVRTC|cuda_fp16|cuda_runtime", err):
                # CuPy 13+ compiles its kernels with NVRTC and needs the CUDA headers (pip extra 'ctk')
                log("CuPy cannot compile GPU kernels (CUDA headers missing) – installing them (one time)…")
                pip(["cupy-cuda12x[ctk]"], log)
                ok, err = cupy_works()
            if not ok:
                log("CuPy self-check failed: " + err[-300:])
                warn.append("The graphics card could not be used by CuPy, so renders run on the processor (slower). "
                            "Details are in the log.")
    elif not prof["gpu_render"]:
        log("No usable NVIDIA graphics card: renders run on the processor (no GPU parts installed).")
    if not MARK.exists():
        done = True
        try:
            make_icon()
            if os.name == "nt":
                done = make_shortcuts(log)
        except Exception as e:
            log(f"(shortcut setup skipped: {e})")
        if done:
            MARK.write_text("ok")
    return warn


def cupy_works():
    """(True, '') when CuPy can run and compile a kernel on the card; otherwise (False, the error text)"""
    code = ("import cupy as cp\na = cp.arange(8, dtype=cp.float32)\nb = (a - cp.float32(2)) * cp.float32(3)\n"
            "cp.cuda.Stream.null.synchronize()\nassert abs(float(b.sum()) - 36.0) < 1e-3\nprint('ok')\n")
    try:
        r = subprocess.run([py_exe(), "-c", code], capture_output=True, text=True, timeout=240, creationflags=NOWIN)
    except Exception as e:
        return False, str(e)
    return r.returncode == 0 and "ok" in r.stdout, (r.stderr or r.stdout)[-600:]


TORCH_MARK = APP / ".torch_cuda_tried"
CUDA_TAGS = ("cu128", "cu126", "cu124", "cu121")      # newest first; the first one this driver can run wins


def torch_cuda_ok():
    try:
        r = subprocess.run([py_exe(), "-c", "import torch,sys;sys.exit(0 if torch.cuda.is_available() else 3)"],
                           capture_output=True, timeout=180, creationflags=NOWIN)
        return r.returncode == 0
    except Exception:
        return False


def install_torch(log, prof, replace=False):
    """PyTorch for the Uzbek model / precise timing. With an NVIDIA card the default pip wheel on Windows is
    processor-only, so the CUDA builds are tried first and each is verified with torch.cuda.is_available();
    anything that fails falls back to the plain wheel. True when torch imports afterwards."""
    if prof.get("gpu_speech"):
        for tag in CUDA_TAGS:
            log(f"Installing PyTorch for the graphics card ({tag}, large download – one time)…")
            args = ["--index-url", f"https://download.pytorch.org/whl/{tag}"]
            if replace:
                args += ["--upgrade", "--force-reinstall", "--no-deps"]
            if pip(["torch"], log, extra_args=args, constrain=False) and has("torch") and torch_cuda_ok():
                try:
                    TORCH_MARK.write_text(tag)
                except OSError:
                    pass
                log(f"PyTorch with graphics-card support is ready ({tag}).")
                return True
            log(f"PyTorch {tag} did not give a working graphics card – trying the next one…")
        try:
            TORCH_MARK.write_text("none")
        except OSError:
            pass
        if replace:
            log("No CUDA build of PyTorch worked here; keeping the processor version.")
            return has("torch")
        log("No CUDA build of PyTorch worked here; installing the processor version instead.")
    return pip(["torch"], log) and has("torch")


def make_icon():
    ico = APP / "studio" / "vizavi.ico"
    if ico.exists():
        return ico
    from PIL import Image, ImageDraw, ImageFilter
    S = 256
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    g = ImageDraw.Draw(im)
    g.ellipse([8, 8, S - 8, S - 8], fill=(12, 12, 16, 255))
    ring = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(ring).ellipse([46, 46, S - 46, S - 46], outline=(255, 170, 70, 255), width=22)
    im.alpha_composite(ring.filter(ImageFilter.GaussianBlur(6)))
    im.alpha_composite(ring)
    g = ImageDraw.Draw(im)
    g.ellipse([70, 70, S - 70, S - 70], fill=(0, 0, 0, 255))
    im.save(ico, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return ico


def make_shortcuts(log):
    """True when the shortcuts were created. Paths go through PowerShell single-quoted strings, so a ' in a folder
    or user name (O'Brien) is doubled instead of breaking the command."""
    q = lambda s: str(s).replace("'", "''")
    target = APP / "Vizavi Studio.pyw"
    ico = APP / "studio" / "vizavi.ico"
    ps = ("$w=New-Object -ComObject WScript.Shell;"
          "foreach($d in @([Environment]::GetFolderPath('Desktop'),[Environment]::GetFolderPath('SendTo'),[Environment]::GetFolderPath('Programs'))){"
          "$s=$w.CreateShortcut((Join-Path $d 'Vizavi Studio.lnk'));"
          f"$s.TargetPath='{q(pyw_exe())}';$s.Arguments='\"{q(target)}\"';$s.WorkingDirectory='{q(APP)}';"
          f"$s.IconLocation='{q(ico)}';$s.Save()}}")
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                       capture_output=True, text=True, creationflags=NOWIN)
    log("Shortcuts created: Desktop + right-click 'Send to' → Vizavi Studio" if r.returncode == 0
        else "Shortcut creation failed: " + r.stderr[-300:])
    return r.returncode == 0


DEPS_VERSION = "6"
CACHE = APP / ".deps_ok"


def ensure_cached(log, force=False, prof=None):
    """instant on normal starts: the full check runs once per Python version / app dependency set / hardware."""
    p = prof or {}
    key = f"{sys.version.split()[0]}|{DEPS_VERSION}|{p.get('gpu_speech')}|{p.get('gpu_render')}|{p.get('uzbek_pack')}"
    if not force and CACHE.exists() and CACHE.read_text(encoding="utf-8").strip() == key:
        return []
    warn = ensure(log, prof, force=force)
    if not warn:
        write_lock(log)
        CACHE.write_text(key, encoding="utf-8")
    return warn
