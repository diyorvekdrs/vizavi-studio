"""Updates from GitHub releases.

check()  -> what's new (the latest release of UPDATE_REPO)
stage()  -> download the release zip, verify its SHA-256, unpack app/ into .update/new
launch() -> start the helper (a copy of this file) and let the engine exit; the helper swaps the files while
            nothing runs, starts the new version and rolls back to the old one if it doesn't come up.

Only files that belong to a release are ever written or removed (release.json lists them), so settings,
projects, the Python environment, models and the user's own library are never touched."""
import hashlib, json, os, shutil, socket, subprocess, sys, time, urllib.request, zipfile
from pathlib import Path

WIN = os.name == "nt"
NOWIN = 0x08000000 if WIN else 0
DETACH = (0x00000008 | 0x00000200 | 0x08000000) if WIN else 0     # detached, new group, no window
API = "https://api.github.com/repos/{repo}/releases/latest"
UA = {"User-Agent": "VizaviStudio-updater", "Accept": "application/vnd.github+json"}


def vtuple(v):
    out = []
    for part in str(v).strip().lstrip("vV").split("."):
        num = "".join(ch for ch in part if ch.isdigit())
        out.append(int(num) if num else 0)
    return tuple(out + [0] * (3 - len(out)))[:3]


def newer(a, b):
    """is version a newer than b"""
    return vtuple(a) > vtuple(b)


def _get(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def check(repo, current, api=None):
    """{'current','latest','newer','notes','zip_url','zip_name','size','sums_url','page'} or raises OSError/ValueError"""
    data = json.loads(_get((api or API).format(repo=repo)))
    tag = str(data.get("tag_name") or "")
    assets = {a.get("name"): a for a in data.get("assets") or []}
    zipa = next((a for n, a in assets.items() if n and n.lower().endswith(".zip")), None)
    sums = assets.get("SHA256SUMS.txt")
    return {"current": current, "latest": tag.lstrip("vV"), "newer": bool(zipa) and newer(tag, current),
            "notes": (data.get("body") or "").strip()[:4000], "page": data.get("html_url"),
            "zip_url": zipa and zipa.get("browser_download_url"), "zip_name": zipa and zipa.get("name"),
            "size": zipa and zipa.get("size"), "sums_url": sums and sums.get("browser_download_url")}


def _download(url, dest, progress=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA["User-Agent"]})
    tmp = Path(str(dest) + ".part")
    with urllib.request.urlopen(req, timeout=30) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        got = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
            if progress and total:
                progress(got / total)
    os.replace(tmp, dest)
    return dest


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe(name):
    n = name.replace("\\", "/")
    if n.startswith("/") or ":" in n or any(p == ".." for p in n.split("/")):
        return None
    return n


def stage(info, app, progress=None, log=print):
    """download + verify + unpack. Returns the folder with the new app files."""
    app = Path(app)
    up = app / ".update"
    up.mkdir(exist_ok=True)
    if not info.get("zip_url") or not info.get("sums_url"):
        raise ValueError("this release has no update package")
    z = up / "download.zip"
    log(f"Downloading Vizavi Studio {info['latest']} ({(info.get('size') or 0) / 1e6:.0f} MB)…")
    _download(info["zip_url"], z, progress)
    sums = _get(info["sums_url"]).decode("utf-8", "replace")
    want = next((l.split()[0].lower() for l in sums.splitlines()
                 if l.strip() and l.split()[-1].lstrip("*") == info["zip_name"]), None)
    got = sha256(z)
    if not want or want != got:
        z.unlink(missing_ok=True)
        raise ValueError("the downloaded update is damaged (checksum mismatch) – try again later")
    new = up / "new"
    if new.exists():
        shutil.rmtree(new)
    new.mkdir()
    with zipfile.ZipFile(z) as zf:
        for m in zf.infolist():
            n = _safe(m.filename)
            if not n or not n.startswith("app/") or m.is_dir():
                continue
            dst = new / n[4:]
            dst.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(m) as s, open(dst, "wb") as d:
                shutil.copyfileobj(s, d)
    rel = json.loads((new / "release.json").read_text(encoding="utf-8"))
    files = rel.get("files") or []
    missing = [f for f in files if not (new / f).is_file()]
    if missing or not (new / "studio" / "server.py").is_file() or not (new / "Vizavi Studio.pyw").is_file():
        raise ValueError("the update package is incomplete" + (f" ({missing[0]} missing)" if missing else ""))
    z.unlink(missing_ok=True)
    return new


def launch(app, new, python, token, port):
    """copy this file next to the update and start it as the helper; the caller exits right after"""
    app = Path(app)
    helper = app / ".update" / "helper.py"
    shutil.copy2(Path(__file__), helper)
    pyw = Path(python)
    if WIN and pyw.name.lower() == "python.exe" and pyw.with_name("pythonw.exe").exists():
        pyw = pyw.with_name("pythonw.exe")
    env = dict(os.environ, VZ_TOKEN=token)
    subprocess.Popen([str(pyw), "-I", str(helper), "apply", str(app), str(new), str(port)], cwd=str(app / ".update"),
                     env=env, creationflags=DETACH, close_fds=True, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def restore_launch(app, python, token, port):
    app = Path(app)
    helper = app / ".update" / "helper.py"
    shutil.copy2(Path(__file__), helper)
    env = dict(os.environ, VZ_TOKEN=token)
    pyw = Path(python)
    if WIN and pyw.name.lower() == "python.exe" and pyw.with_name("pythonw.exe").exists():
        pyw = pyw.with_name("pythonw.exe")
    subprocess.Popen([str(pyw), "-I", str(helper), "restore", str(app), "-", str(port)], cwd=str(app / ".update"),
                     env=env, creationflags=DETACH, close_fds=True, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def has_backup(app):
    return (Path(app) / ".update" / "backup" / "restore.json").exists()


# ------------------------------------------------------------------ the helper (runs while the engine is closed)
def _port_open(port):
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=0.5):
            return True
    except OSError:
        return False


def _ping(port):
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/ping", headers={"Host": f"127.0.0.1:{port}"})
        with urllib.request.urlopen(req, timeout=2) as r:
            return json.loads(r.read()).get("app") == "vizavi"
    except Exception:
        return False


def _copy(src, dst, tries=20):
    dst.parent.mkdir(parents=True, exist_ok=True)
    for i in range(tries):
        try:
            shutil.copy2(src, dst)
            return
        except PermissionError:
            time.sleep(0.25 * (i + 1))
    shutil.copy2(src, dst)


def _release_files(folder):
    try:
        return list(json.loads((Path(folder) / "release.json").read_text(encoding="utf-8")).get("files") or [])
    except (OSError, ValueError):
        return []


def _start_engine(app, port, wait=90):
    py = Path(sys.executable)
    subprocess.Popen([str(py), str(Path(app) / "Vizavi Studio.pyw"), "--no-window"], cwd=str(app), env=os.environ.copy(),
                     creationflags=DETACH, close_fds=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)
    t0 = time.time()
    while time.time() - t0 < wait:
        if _ping(port):
            return True
        time.sleep(1)
    return False


def apply_files(app, new, log):
    """swap in the new files (with a backup of everything touched). Returns the list of files that were new."""
    app, new = Path(app), Path(new)
    old_files = set(_release_files(app))
    new_files = _release_files(new)
    if not new_files:
        raise ValueError("release.json is empty")
    drop = sorted(f for f in old_files - set(new_files) if _safe(f))
    bk = app / ".update" / "backup"
    if bk.exists():
        shutil.rmtree(bk)
    bk.mkdir(parents=True)
    created = []
    for rel in new_files + drop:
        if not _safe(rel):
            continue
        p = app / rel
        if p.is_file():
            _copy(p, bk / rel)
        elif rel in new_files:
            created.append(rel)
    if (app / "release.json").exists() and "release.json" not in new_files + drop:
        _copy(app / "release.json", bk / "release.json")
    (bk / "restore.json").write_text(json.dumps({"created": created, "time": time.time()}), encoding="utf-8")
    for rel in new_files:
        if _safe(rel):
            _copy(new / rel, app / rel)
    for rel in drop:
        try:
            (app / rel).unlink()
        except OSError:
            pass
    log(f"copied {len(new_files)} files, removed {len(drop)}, backup of {len(new_files) + len(drop) - len(created)}")
    return created


def restore_files(app, log):
    app = Path(app)
    bk = app / ".update" / "backup"
    info = json.loads((bk / "restore.json").read_text(encoding="utf-8"))
    for p in sorted(bk.rglob("*")):
        if p.is_file() and p.name != "restore.json":
            _copy(p, app / p.relative_to(bk))
    for rel in info.get("created") or []:
        if _safe(rel):
            try:
                (app / rel).unlink()
            except OSError:
                pass
    log("previous version restored")


def helper_main(argv):
    mode, app, new, port = argv[0], Path(argv[1]), argv[2], int(argv[3])
    up = app / ".update"
    logf = open(up / "update.log", "a", encoding="utf-8")
    log = lambda s: (logf.write(time.strftime("%Y-%m-%d %H:%M:%S ") + s + "\n"), logf.flush())
    for _ in range(120):                      # wait until the old engine has closed
        if not _port_open(port):
            break
        time.sleep(0.5)
    time.sleep(1.0)
    old_v = _version_of(app)
    try:
        if mode == "apply":
            new_v = _version_of(Path(new))
            log(f"updating {old_v} -> {new_v}")
            apply_files(app, new, log)
            if _start_engine(app, port):
                (up / "result.json").write_text(json.dumps({"ok": True, "from": old_v, "to": new_v}), encoding="utf-8")
                log("new version is running")
                shutil.rmtree(new, ignore_errors=True)
                return
            log("the new version did not start – rolling back")
            restore_files(app, log)
            (up / "result.json").write_text(json.dumps({"ok": False, "from": old_v, "to": new_v,
                                                        "error": "the new version did not start"}), encoding="utf-8")
        else:
            log(f"undoing the update of {old_v}")
            restore_files(app, log)
            (up / "result.json").write_text(json.dumps({"ok": True, "undo": True, "from": old_v,
                                                        "to": _version_of(app)}), encoding="utf-8")
            shutil.rmtree(up / "backup", ignore_errors=True)
    except Exception as e:
        log(f"failed: {type(e).__name__}: {e}")
        try:
            if mode == "apply" and (up / "backup" / "restore.json").exists():
                restore_files(app, log)
        except Exception as e2:
            log(f"restore failed too: {e2}")
        (up / "result.json").write_text(json.dumps({"ok": False, "from": old_v, "error": str(e)}), encoding="utf-8")
    _start_engine(app, port)


def _version_of(folder):
    try:
        for line in (Path(folder) / "studio" / "version.py").read_text(encoding="utf-8").splitlines():
            if line.startswith("VERSION"):
                return line.split("=", 1)[1].strip().strip('"\'')
    except OSError:
        pass
    return "?"


if __name__ == "__main__":
    helper_main(sys.argv[1:])
