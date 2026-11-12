"""Recently deleted + daily backups.

Deleting a project or a saved style moves it to <projects>/_deleted/ (not the Windows Recycle Bin, which clean-up
tools empty without asking). It can be restored from Settings for 30 days; after that it is removed for good.
Once a day the small, irreplaceable parts (saved styles, every project's settings, texts and Claude's latest code)
are zipped to <projects>/_backups/ - the last 7 days are kept. Recordings and renders are too big for that."""
import json
import os
import shutil
import time
import zipfile
from pathlib import Path

KEEP_DAYS = 30
KEEP_BACKUPS = 7
META = ".vz_deleted.json"
BACKUP_TEXT_EXT = {".json", ".md", ".txt", ".srt", ".tsv", ".py", ".js", ".html", ".css", ".svg"}
BACKUP_FILE_MAX = 4 * 1024 * 1024        # one file larger than this is not text worth backing up
BACKUP_PROJECT_MAX = 40 * 1024 * 1024


class TrashError(Exception):
    pass


def trash_dir(S):
    return Path(S["projects_dir"]) / "_deleted"


def styles_root(S):
    return Path(S["projects_dir"]) / "_styles"


def _clean(s):
    return "".join(c if c.isalnum() or c in "-_ ." else "_" for c in str(s)).strip(" .") or "item"


def _free(dest):
    """dest, or dest (2), dest (3)... - never over something that exists"""
    if not dest.exists():
        return dest
    for i in range(2, 1000):
        d = dest.with_name(f"{dest.name} ({i})")
        if not d.exists():
            return d
    raise TrashError(f"Too many items named {dest.name}")


def to_trash(src, S, kind, name):
    """move a project ('project') or saved style ('style') folder into Recently deleted"""
    src = Path(src)
    root = trash_dir(S)
    root.mkdir(parents=True, exist_ok=True)
    dest = _free(root / f"{kind}__{_clean(src.name)}__{time.strftime('%Y%m%d_%H%M%S')}")
    shutil.move(str(src), str(dest))
    try:
        (dest / META).write_text(json.dumps({"kind": kind, "name": name, "folder": src.name,
                                             "deleted": time.time()}, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return dest


def _meta(d):
    try:
        m = json.loads((d / META).read_text(encoding="utf-8"))
        if m.get("kind") in ("project", "style"):
            return m
    except (OSError, ValueError):
        pass
    # made by an older version: no note, so work it out from the folder
    kind = "style" if (d / "style.json").exists() else "project" if (d / "state.json").exists() else None
    if not kind:
        return None
    if d.name.startswith(("project__", "style__")) and d.name.count("__") >= 2:
        folder = d.name.split("__", 1)[1].rsplit("__", 1)[0]
    else:                                   # older versions: <name>__<date>_<time>
        folder = d.name.rsplit("__", 1)[0]
    try:
        when = d.stat().st_mtime
    except OSError:
        when = time.time()
    return {"kind": kind, "name": folder, "folder": folder, "deleted": when}


def migrate_old(S):
    """styles deleted by older versions sit in _styles/_deleted - bring them into the one list"""
    old = styles_root(S) / "_deleted"
    if not old.is_dir():
        return
    for d in list(old.iterdir()):
        if d.is_dir() and (d / "style.json").exists():
            try:
                name = json.loads((d / "style.json").read_text(encoding="utf-8")).get("name") or d.name
            except (OSError, ValueError):
                name = d.name
            try:
                mt = d.stat().st_mtime
                dest = to_trash(d, S, "style", name)
                m = json.loads((dest / META).read_text(encoding="utf-8"))
                m["deleted"], m["folder"] = mt, d.name.rsplit("_", 2)[0]
                (dest / META).write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
            except (OSError, ValueError):
                pass
    try:
        old.rmdir()
    except OSError:
        pass


def list_trash(S):
    root = trash_dir(S)
    out = []
    for d in sorted(root.iterdir()) if root.is_dir() else []:
        if not d.is_dir():
            continue
        m = _meta(d)
        if not m:
            continue
        left = KEEP_DAYS - (time.time() - float(m.get("deleted") or 0)) / 86400
        out.append({"id": d.name, "kind": m["kind"], "name": m.get("name") or d.name,
                    "deleted": time.strftime("%Y-%m-%d %H:%M", time.localtime(float(m.get("deleted") or 0))),
                    "days_left": max(0, int(left + 0.999))})
    return sorted(out, key=lambda e: e["deleted"], reverse=True)


def _entry(S, tid):
    tid = str(tid or "")
    if not tid or "/" in tid or "\\" in tid or tid.startswith(".") or ".." in tid:
        raise TrashError("That item is not in Recently deleted.")
    d = trash_dir(S) / tid
    m = _meta(d) if d.is_dir() else None
    if not m:
        raise TrashError("That item is not in Recently deleted any more.")
    return d, m


def restore(S, tid):
    """put it back where it was (under a new name if that name is taken). Returns (kind, new name)."""
    d, m = _entry(S, tid)
    folder = _clean(m.get("folder") or m.get("name") or "restored")
    if m["kind"] == "project":
        dest = _free(Path(S["projects_dir"]) / folder)
    else:
        styles_root(S).mkdir(parents=True, exist_ok=True)
        dest = _free(styles_root(S) / folder)
    try:
        (d / META).unlink()
    except OSError:
        pass
    shutil.move(str(d), str(dest))
    if m["kind"] == "style" and dest.name != folder:     # the style's id follows its folder
        f = dest / "style.json"
        try:
            info = json.loads(f.read_text(encoding="utf-8"))
            info["id"] = dest.name
            info["name"] = f"{info.get('name') or folder} {dest.name[len(folder):].strip()}"
            f.write_text(json.dumps(info, indent=1, ensure_ascii=False), encoding="utf-8")
        except (OSError, ValueError):
            pass
    return m["kind"], dest.name


def purge(S, tid):
    d, _ = _entry(S, tid)
    shutil.rmtree(d, ignore_errors=True)
    if d.exists():
        raise TrashError("Couldn't remove it completely - a file in it may be open in another program.")


def purge_old(S, log=None):
    n = 0
    for e in list_trash(S):
        if e["days_left"] <= 0:
            try:
                purge(S, e["id"])
                n += 1
            except TrashError:
                pass
    if n and log:
        log(f"Recently deleted: removed {n} item(s) older than {KEEP_DAYS} days")
    return n


# ---------------------------------------------------------------- backups

def backups_dir(S):
    return Path(S["projects_dir"]) / "_backups"


def _project_files(root, code_dir):
    """the small text files that make a project: settings, transcript, script, plan, Claude's code"""
    total = 0
    picks = [root / "state.json"]
    for sub in ("source",):
        p = root / sub
        if p.is_dir():
            picks += [f for f in p.iterdir() if f.is_file() and f.suffix.lower() in BACKUP_TEXT_EXT]
    if code_dir:
        picks += [f for f in code_dir.rglob("*") if f.is_file() and f.suffix.lower() in BACKUP_TEXT_EXT
                  and "media" not in f.relative_to(code_dir).parts[:1]]
    for f in picks:
        try:
            sz = f.stat().st_size
        except OSError:
            continue
        if sz > BACKUP_FILE_MAX:
            continue
        total += sz
        if total > BACKUP_PROJECT_MAX:
            break
        yield f


def daily_backup(S, latest_code=None, log=None, force=False):
    """one zip per day; returns its path, or None when today's exists already / nothing to keep"""
    root = Path(S["projects_dir"])
    if not root.is_dir():
        return None
    bd = backups_dir(S)
    out = bd / f"vizavi_backup_{time.strftime('%Y-%m-%d')}.zip"
    if out.exists() and not force:
        return None
    bd.mkdir(parents=True, exist_ok=True)
    part = out.with_suffix(".zip.part")
    n = 0
    with zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED) as z:
        sr = styles_root(S)
        for f in sorted(sr.rglob("*")) if sr.is_dir() else []:
            rel = f.relative_to(root)
            if f.is_file() and "_deleted" not in rel.parts:
                z.write(f, rel.as_posix())
                n += 1
        for d in sorted(root.iterdir()):
            if not d.is_dir() or d.name.startswith("_") or not (d / "state.json").exists():
                continue
            code = None
            if latest_code:
                try:
                    code = latest_code(d)
                except Exception:
                    code = None
            for f in _project_files(d, code):
                z.write(f, f.relative_to(root).as_posix())
                n += 1
    if not n:
        part.unlink(missing_ok=True)
        return None
    os.replace(part, out)
    old = sorted(bd.glob("vizavi_backup_*.zip"))
    for f in old[:-KEEP_BACKUPS]:
        try:
            f.unlink()
        except OSError:
            pass
    if log:
        log(f"Backup: {n} files → {out.name}")
    return out
