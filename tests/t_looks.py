"""Signature looks: every look has its recipe, frames, fonts and thumbnails; picking one puts LOOK.md, look/ and the
fonts into what Claude gets; the brief names it."""
import sys, os, json, tempfile
APPDIR = os.environ.get("VZ_APP") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app")
sys.path.insert(0, APPDIR)
from pathlib import Path
from studio import core
from studio import order as OD
fails = []
def check(n, c, x=""):
    print(("ok   " if c else "FAIL ") + n, "" if c else x)
    if not c: fails.append(n)

L = OD.looks()
check("ten looks load", len(L) == 10, list(L))
UI = Path(APPDIR) / "ui" / "looks"
for lid, lk in L.items():
    md = OD.LOOKS_DIR / f"{lid}.md"
    txt = md.read_text(encoding="utf-8") if md.exists() else ""
    check(f"{lid}: recipe with look, motion, never", all(h in txt for h in ("## The look", "## How it moves", "## Never", "@font-face")))
    check(f"{lid}: three reference frames", len(list((OD.LOOKS_DIR / "stills").glob(f"{lid}_*.jpg"))) == 3)
    check(f"{lid}: thumbnail clip and poster", (UI / f"{lid}.mp4").stat().st_size > 5000 and (UI / f"{lid}.jpg").exists())
    check(f"{lid}: fonts present", lk["fonts"] and all((OD.LOOKS_DIR / "fonts" / f).is_file() for f in lk["fonts"]), lk["fonts"])
    check(f"{lid}: font licences", all((OD.LOOKS_DIR / "fonts" / f"OFL-{fam}.txt").is_file() for fam in lk["font_families"]))
    check(f"{lid}: recipe fonts point to assets/", all(f"url(assets/{f})" in txt for f in lk["fonts"]))

o = OD.base(); o.update(name="x", style_preset="risograph")
b = OD.brief_md(o, assets=[])
check("brief names the look and LOOK.md", "Look: Risograph" in b and "LOOK.md" in b, b[-600:])
o["style_preset"] = "clean_minimal"
check("general styles unchanged", OD.STYLES["clean_minimal"] in OD.brief_md(o, assets=[]))
check("style names", OD.style_name("risograph").startswith("Risograph") and OD.style_name("clean_minimal") == "Clean minimal")

tmp = Path(tempfile.mkdtemp(prefix="vz_looks_")); core.SETTINGS = tmp / "settings.json"
S = core.load_settings(); S["projects_dir"] = str(tmp / "P"); os.makedirs(S["projects_dir"])
pr = core.Project.open("riso", S)
pr.src.mkdir(parents=True, exist_ok=True)
o = OD.base(); o.update(name="riso", style_preset="magazine_note")
(pr.src / "order.json").write_text(json.dumps(o), encoding="utf-8")
pr = core.Project.open("riso", S)
names = core.apply_look_fonts(pr, pr.order, [])
check("look fonts copied into assets", names == L["magazine_note"]["fonts"] and all((pr.src / "assets" / f).exists() for f in names), names)
check("font licences travel along", (pr.src / "assets" / "OFL-LaBelleAurore.txt").exists())
E = dict(core.look_entries(pr))
check("package has LOOK.md and three frames", "LOOK.md" in E and len([k for k in E if k.startswith("look/")]) == 3, list(E))
o["style_preset"] = "cinematic_dark"; (pr.src / "order.json").write_text(json.dumps(o), encoding="utf-8")
check("no look, no look files", core.look_entries(core.Project.open("riso", S)) == [])

print("\nFAILS:", fails or "none")
sys.exit(1 if fails else 0)
