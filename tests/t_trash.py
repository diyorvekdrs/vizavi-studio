import sys, os, json, tempfile, time, zipfile
APPDIR = os.environ.get("VZ_APP") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app")
sys.path.insert(0, APPDIR)
from pathlib import Path
from studio import trash as TR
fails = []
def check(n, c, x=""):
    print(("ok   " if c else "FAIL ") + n, "" if c else x)
    if not c: fails.append(n)

tmp = Path(tempfile.mkdtemp(prefix="vz_trash_"))
S = {"projects_dir": str(tmp / "Projects")}
P = tmp / "Projects"
def mkproj(name, code=True):
    d = P / name; (d / "source").mkdir(parents=True)
    (d / "state.json").write_text(json.dumps({"name": name}), encoding="utf-8")
    (d / "source" / "script.txt").write_text("salom dunyo", encoding="utf-8")
    (d / "source" / "narration.wav").write_bytes(b"\0" * 1000)
    if code:
        (d / "work" / "preview_v1").mkdir(parents=True)
        (d / "work" / "preview_v1" / "film.py").write_text("print(1)", encoding="utf-8")
    return d
def mkstyle(sid, name):
    d = P / "_styles" / sid; d.mkdir(parents=True)
    (d / "style.json").write_text(json.dumps({"id": sid, "name": name}), encoding="utf-8")
    return d

a = mkproj("alpha")
dest = TR.to_trash(a, S, "project", "alpha")
check("project moved out", not a.exists() and dest.exists())
L = TR.list_trash(S)
check("listed", len(L) == 1 and L[0]["kind"] == "project" and L[0]["name"] == "alpha" and L[0]["days_left"] == 30, L)
mkproj("alpha")            # a new project took the name meanwhile
kind, name = TR.restore(S, L[0]["id"])
check("restore under a free name", kind == "project" and name == "alpha (2)" and (P / "alpha (2)" / "state.json").exists(), name)
check("meta note removed on restore", not (P / "alpha (2)" / TR.META).exists())
check("trash empty", TR.list_trash(S) == [])

# styles: restore with a taken id rewrites style.json
s1 = mkstyle("look", "Look")
TR.to_trash(s1, S, "style", "Look"); mkstyle("look", "Look")
tid = TR.list_trash(S)[0]["id"]
kind, name = TR.restore(S, tid)
info = json.loads((P / "_styles" / name / "style.json").read_text(encoding="utf-8"))
check("style restored with new id", kind == "style" and info["id"] == name == "look (2)" and info["name"] == "Look (2)", info)

# bad ids
for bad in ("", "../x", "a/b", ".vz", "nope"):
    try:
        TR.restore(S, bad); check(f"bad id {bad!r} refused", False)
    except TR.TrashError:
        check(f"bad id {bad!r} refused", True)

# old formats: project from an older version, style in _styles/_deleted
od = P / "_deleted" / "beta__20261101_101010"; od.mkdir(parents=True); (od / "state.json").write_text("{}")
os.utime(od, (time.time() - 40 * 86400,) * 2)
os_ = P / "_styles" / "_deleted" / "Englify_20261102_111111"; os_.mkdir(parents=True)
(os_ / "style.json").write_text(json.dumps({"id": "Englify", "name": "Englify reklama"}))
TR.migrate_old(S)
L = {e["name"]: e for e in TR.list_trash(S)}
check("old project understood", "beta" in L and L["beta"]["days_left"] == 0, L)
check("old style migrated", "Englify reklama" in L and not (P / "_styles" / "_deleted").exists(), L)
check("purge old", TR.purge_old(S) == 1 and "beta" not in {e["name"] for e in TR.list_trash(S)})
kind, name = TR.restore(S, L["Englify reklama"]["id"])
check("migrated style restores to its folder", name == "Englify" and (P / "_styles" / "Englify" / "style.json").exists(), name)
TR.purge(S, TR.to_trash(mkproj("gamma"), S, "project", "gamma").name)
check("purge for good", not any("gamma" in e["name"] for e in TR.list_trash(S)))

# backups
out = TR.daily_backup(S, latest_code=lambda d: d / "work" / "preview_v1" if (d / "work" / "preview_v1").exists() else None)
names = zipfile.ZipFile(out).namelist() if out else []
check("backup made", out and out.exists(), out)
check("backup has style + project texts + code", "_styles/Englify/style.json" in names and "alpha/source/script.txt" in names
      and "alpha/work/preview_v1/film.py" in names and "alpha/state.json" in names, names)
check("backup skips recordings and trash", not any(n.endswith(".wav") or "_deleted" in n for n in names), names)
check("one backup a day", TR.daily_backup(S) is None)
for i in range(10):
    (P / "_backups" / f"vizavi_backup_2020-01-{i + 10:02d}.zip").write_bytes(b"x")
TR.daily_backup(S, force=True)
check("keeps 7 backups", len(list((P / "_backups").glob("*.zip"))) == 7)
check("today's kept", (P / "_backups" / f"vizavi_backup_{time.strftime('%Y-%m-%d')}.zip").exists())

print("\nFAILS:", fails or "none")
sys.exit(1 if fails else 0)
