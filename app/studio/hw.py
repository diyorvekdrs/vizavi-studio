"""What this PC can do (stdlib only, runs before anything is installed). The profile decides what gets
installed, which speech models are used, how many render workers run, and what Claude is told about the
render budget. Works on any Windows PC: NVIDIA (new or old driver, any VRAM), AMD/Intel graphics, CPU only."""
import json, os, platform, re, shutil, subprocess, sys
from pathlib import Path

WIN = os.name == "nt"
NOWIN = 0x08000000 if WIN else 0
CUDA12_MIN_DRIVER = 528.0      # Windows driver that runs CUDA 12 (cupy-cuda12x, CUDA 12 cuBLAS/cuDNN)


def _run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=NOWIN,
                           encoding="utf-8", errors="replace")
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def ram_gb():
    try:
        if WIN:
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = MS(); m.dwLength = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return round(m.ullTotalPhys / 2**30, 1)
        with open("/proc/meminfo") as f:
            return round(int(re.search(r"MemTotal:\s+(\d+)", f.read())[1]) / 2**20, 1)
    except Exception:
        return 8.0


def cpu_name():
    if WIN:
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            return re.sub(r"\s+", " ", winreg.QueryValueEx(k, "ProcessorNameString")[0]).strip()
        except Exception:
            pass
    try:
        with open("/proc/cpuinfo") as f:
            m = re.search(r"model name\s*:\s*(.+)", f.read())
            if m:
                return m[1].strip()
    except Exception:
        pass
    return platform.processor() or "CPU"


def nvidia():
    """first NVIDIA GPU: name, VRAM GB, driver version (None without NVIDIA driver)."""
    exe = shutil.which("nvidia-smi") or (r"C:\Windows\System32\nvidia-smi.exe" if WIN else None)
    if not exe or not Path(exe).exists():
        return None
    out = _run([exe, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"])
    if not out:
        return None
    best = None
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 3:
            try:
                g = {"name": parts[0], "vram_gb": round(float(parts[1]) / 1024, 1), "driver": parts[2]}
            except ValueError:
                continue
            if not best or g["vram_gb"] > best["vram_gb"]:
                best = g
    return best


def other_gpus():
    if not WIN:
        return []
    out = _run(["powershell", "-NoProfile", "-Command",
                "(Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name) -join '|'"], timeout=12)
    return [g for g in out.split("|") if g.strip()]


def disk_free_gb(path):
    try:
        p = Path(path)
        while not p.exists() and p.parent != p:
            p = p.parent
        return round(shutil.disk_usage(p).free / 2**30, 1)
    except Exception:
        return None


def downloads_dir():
    """the real Downloads folder (it can be moved to another drive or into OneDrive)."""
    if WIN:
        try:
            import ctypes, uuid
            from ctypes import wintypes
            fid = uuid.UUID("{374DE290-123F-4565-9164-39C4925E467B}")
            guid = (ctypes.c_byte * 16).from_buffer_copy(fid.bytes_le)
            p = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(guid, 0, None, ctypes.byref(p)) == 0:
                path = p.value
                ctypes.windll.ole32.CoTaskMemFree(p)
                return path
        except Exception:
            pass
    return str(Path.home() / "Downloads")


def detect(app_dir):
    cores = os.cpu_count() or 4
    ram = ram_gb()
    nv = nvidia()
    drv = 0.0
    if nv:
        try:
            drv = float(".".join(nv["driver"].split(".")[:2]))
        except ValueError:
            pass
    vram = nv["vram_gb"] if nv else 0.0
    cuda_ok = bool(nv) and drv >= CUDA12_MIN_DRIVER
    info = {
        "os": platform.platform(), "arch": platform.machine(), "python": sys.version.split()[0],
        "python_bits": 64 if sys.maxsize > 2**32 else 32,
        "cpu": cpu_name(), "threads": cores, "ram_gb": ram, "nvidia": nv, "cuda_ok": cuda_ok,
        "gpus": other_gpus() if not nv else [nv["name"]], "disk_free_gb": disk_free_gb(app_dir),
    }
    info["profile"] = profile(info)
    return info


def profile(h):
    cores, ram, nv = h["threads"], h["ram_gb"], h["nvidia"]
    vram = nv["vram_gb"] if nv else 0.0
    gpu_render = h["cuda_ok"] and vram >= 3.5
    gpu_speech = h["cuda_ok"] and vram >= 3.5
    disk = h["disk_free_gb"] if h["disk_free_gb"] is not None else 100
    strong_cpu = cores >= 12 and ram >= 16
    p = {
        "gpu_render": gpu_render,
        "gpu_speech": gpu_speech,
        "speech_compute": "float16" if vram >= 7 else "int8_float16",
        # Whisper only gives the timing pass when the Uzbek model + MMS run; large-v3 on a weak CPU is very slow
        "whisper_model": "large-v3" if (gpu_speech or strong_cpu) else "medium",
        # Uzbek model + MMS precise timing need PyTorch (~2.5 GB with models) and RAM to load them
        "uzbek_pack": ram >= 7.5 and disk >= 12,
        "gpu_workers": 3 if vram >= 10 else 2 if vram >= 6 else 1,
        "cpu_workers": max(1, min(cores - 1, int(ram / 2.5), 10)),
        "html_workers": max(1, min(6, cores // 2, int(ram / 1.5))),
        "preview_long_side": 960 if (gpu_render or strong_cpu) else 720,
        "low_disk": disk < 12,
    }
    p["tier"] = "gpu" if gpu_render else ("cpu_strong" if strong_cpu else "cpu")
    return p


def explain(h):
    """short human lines for the UI."""
    p, nv = h["profile"], h["nvidia"]
    lines = []
    if nv:
        lines.append(f"{nv['name']}, {nv['vram_gb']:g} GB" + ("" if h["cuda_ok"] else
                     f" – driver {nv['driver']} is too old for GPU rendering; update the NVIDIA driver and press "
                     "Check and repair components"))
    elif h["gpus"]:
        lines.append(", ".join(h["gpus"]) + " (not NVIDIA: renders and speech run on the processor)")
    else:
        lines.append("No dedicated graphics card found: renders and speech run on the processor")
    lines.append(f"{h['cpu']}, {h['threads']} threads, {h['ram_gb']:g} GB memory")
    if h["disk_free_gb"] is not None:
        lines.append(f"{h['disk_free_gb']:g} GB free on the app's drive" +
                     (" – low: speech models need about 8 GB" if p["low_disk"] else ""))
    if p["gpu_render"]:
        lines.append(f"Renders on the graphics card, {p['gpu_workers']} at a time")
    else:
        lines.append(f"Renders on the processor, {p['cpu_workers']} at a time (slower – Claude is told to keep scenes light)")
    if not p["uzbek_pack"]:
        lines.append("Uzbek speech model and precise timing are off on this PC (needs 8 GB memory and 12 GB free disk)")
    return lines


def hardware_md(h):
    """what Claude reads in every package: the render budget of the machine that will render it."""
    p, nv = h["profile"], h["nvidia"]
    gpu = f"{nv['name']} {nv['vram_gb']:g} GB" if nv else (", ".join(h["gpus"]) or "none")
    s = ["# The PC that renders this project", "",
         f"- Graphics: {gpu}; GPU rendering (CuPy): {'yes' if p['gpu_render'] else 'NO'}",
         f"- CPU: {h['cpu']}, {h['threads']} threads; memory {h['ram_gb']:g} GB",
         f"- Render workers: {p['gpu_workers'] if p['gpu_render'] else p['cpu_workers']} (python engine), "
         f"{p['html_workers']} (html engine)", ""]
    if p["gpu_render"]:
        s.append("Budget: normal. The python engine runs on the GPU; the usual DIRECTION.md cost rules apply.")
    else:
        s += ["Budget: **CPU only – keep per-frame cost low.** The final is rendered on this processor, so every",
              "full-frame per-pixel effect is paid at final size for every frame.",
              "- Prefer the html engine for text, graphics, UI and 2D motion (Chromium is fast on any PC).",
              "- In the python engine: do blur/bloom/glow at half or quarter resolution and upscale; cap particles",
              "  (≈20k stars, ≈5k particles); no per-frame full-res noise fields; cache static layers once.",
              "- sandbox_check prints the average frame time at check size; the final costs about that",
              "  × (final pixels ÷ check pixels). Keep the estimated final render under ~30 min and say in",
              "  your reply if it will take longer."]
    return "\n".join(s) + "\n"


if __name__ == "__main__":
    h = detect(Path(__file__).resolve().parent.parent)
    print(json.dumps(h, indent=1))
    print("\n".join(explain(h)))
    print(hardware_md(h))
