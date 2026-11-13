"""Packs the episode for Vizavi Studio (Claude side). Run from the package root.
  python tools/vizavi_pack.py --kind preview      # user's app renders a 960px preview and sends it back
  python tools/vizavi_pack.py --kind final        # user's app renders the 2K final
Optional: --src episode  --out <dir>  --note "one line about this version"
When the user's notes ask for another shape or sound, change the order with the zip (the app applies it and tells the user):
  --size 1080x1080   main size      --also 9:16,1:1   extra versions (16:9 9:16 1:1 4:5, "none" = no extra)
  --sound music_sfx  sound in the export (sfx | voice_sfx | voice_music_sfx | music_sfx | silent)   --fps 30
Writes <episode>__<kind>_v<N>.zip (N comes from vizavi.json) and prints its path."""
import argparse, ast, json, re, sys, time, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KIT = {"backend.py", "render_all.py", "make_final.py", "check.py", "ff.py", "fakegpu.py", "KIT.md", "vzrender.py", "vz.js",
       "vzfast.py"}
SKIP_DIRS = {"__pycache__", "cache", "out", "check", "fonts", "assets", "brand", "input", ".git"}
SKIP_EXT = {".zip", ".pyc"}
REQUIRED = ["W", "H", "FPS", "NFR", "set_res", "render_frame", "prepare_assets", "SELFTEST_FRAMES", "SCENES"]


def names(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = set()
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                for e in ast.walk(t):
                    if isinstance(e, ast.Name):
                        out.add(e.id)
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            out.add(n.target.id)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True, choices=["preview", "final"])
    ap.add_argument("--src", default=str(ROOT / "episode"))
    ap.add_argument("--out", default="/mnt/user-data/outputs" if Path("/mnt/user-data/outputs").exists() else str(ROOT))
    ap.add_argument("--note", default="")
    ap.add_argument("--size", default="", help="new main size WxH (only when the user asked)")
    ap.add_argument("--also", default="", help="extra versions, e.g. 9:16,1:1 ('none' clears them)")
    ap.add_argument("--sound", default="", help="sound in the export: sfx|voice_sfx|voice_music_sfx|music_sfx|silent")
    ap.add_argument("--fps", default="")
    a = ap.parse_args()
    man = json.loads((ROOT / "vizavi.json").read_text(encoding="utf-8"))
    ep = man["episode"]
    ver = int(man.get("next_version", 1))
    src = Path(a.src)
    errs = []
    if (src / "project.json").exists():
        try:
            pj = json.loads((src / "project.json").read_text(encoding="utf-8"))
            miss = [k for k in ("engine", "width", "height", "fps", "nfr", "scenes") if k not in pj]
            if miss:
                errs.append("project.json lacks: " + ", ".join(miss))
        except Exception as e:
            errs.append(f"project.json is not valid JSON: {e}")
        if not (src / "index.html").exists():
            errs.append("episode/index.html missing (html engine)")
        elif "vz.js" not in (src / "index.html").read_text(encoding="utf-8", errors="replace"):
            errs.append("index.html must load vz.js")
    elif not (src / "film.py").exists():
        errs.append("episode/film.py (python engine) or episode/project.json + index.html (html engine) missing")
    else:
        miss = [n for n in REQUIRED if n not in names(src / "film.py")]
        if miss:
            errs.append("film.py lacks: " + ", ".join(miss))
    plan = src / "PLAN.md"
    ptxt = plan.read_text(encoding="utf-8", errors="replace") if plan.exists() else ""
    brief = ROOT / "input" / "brief.md"
    has_care = brief.exists() and "## Take care of" in brief.read_text(encoding="utf-8", errors="replace")
    if len(ptxt) < 600:
        errs.append("episode/PLAN.md missing or too thin (sentence table, concept, shot list, scores - DIRECTION.md)")
    elif not all(k in ptxt.lower() for k in ("beat", "self-critique")):
        errs.append("PLAN.md needs the Beats table and the Self-critique scores (PLAN_TEMPLATE.md)")
    elif sum(1 for l in ptxt.splitlines() if re.match(r"^\|\s*\d+\s*\|", l)
             and sum(1 for c in l.strip("|").split("|") if c.strip()) >= 6) < 3:
        errs.append("PLAN.md: the Beats / Self-critique tables are not filled in (need real rows, not the template)")
    elif has_care and "✓" not in ptxt:
        errs.append("PLAN.md: tick every Take-care-of item / standing rule with ✓ (DIRECTION.md §5)")
    if man.get("transcript_source") == "asr" and man.get("kind") == "request":
        if not (src / "transcript.md").exists() or not (src / "words.tsv").exists():
            errs.append("no script was given: rebuild the transcript first (DIRECTION.md §1) -> episode/transcript.md, "
                        "episode/transcript_clean.txt, then python tools/retime.py")
    if not (src / "audio.py").exists():
        errs.append("episode/audio.py missing (write mix.wav, silence is fine)")
    files = []
    for p in sorted(src.rglob("*")):
        rel = p.relative_to(src)
        if p.is_dir() or any(part in SKIP_DIRS for part in rel.parts[:-1]) or rel.parts[0] in SKIP_DIRS:
            continue
        if p.suffix.lower() in SKIP_EXT or p.name in ("mix.wav", "bed.wav") or (len(rel.parts) == 1 and p.name in KIT):
            continue
        if len(rel.parts) == 1 and p.suffix.lower() in {".mp4", ".mov", ".webm"}:
            continue
        if p.suffix == ".py":
            txt = p.read_text(encoding="utf-8", errors="replace")
            if "import cairo" in txt or "from cairo" in txt:
                errs.append(f"{rel}: uses cairo (not allowed, use Pillow)")
        files.append((p, rel))
    if errs:
        print("NOT PACKED:\n  " + "\n  ".join(errs))
        return 1
    Path(a.out).mkdir(parents=True, exist_ok=True)
    zp = Path(a.out) / f"{ep}__{a.kind}_v{ver}.zip"
    info = {"app": "vizavi-studio", "kind": a.kind, "episode": ep, "project": ep, "version": ver,
            "created": time.strftime("%Y-%m-%d %H:%M:%S"), "made_by": "claude", "note": a.note}
    ch = {}
    if a.size:
        try:
            ch["size"] = [int(x) for x in a.size.lower().split("x")]
        except ValueError:
            print("NOT PACKED: --size wants WxH, e.g. 1080x1080"); return 1
    if a.also:
        ch["variants"] = [] if a.also.strip().lower() == "none" else [v.strip() for v in a.also.split(",") if v.strip()]
        bad = [v for v in ch["variants"] if v not in ("16:9", "9:16", "1:1", "4:5")]
        if bad:
            print("NOT PACKED: --also takes 16:9, 9:16, 1:1, 4:5 – not " + ", ".join(bad)); return 1
    if a.sound:
        if a.sound not in ("sfx", "voice_sfx", "voice_music_sfx", "music_sfx", "silent"):
            print("NOT PACKED: --sound takes sfx, voice_sfx, voice_music_sfx, music_sfx or silent"); return 1
        ch["audio_export"] = a.sound
    if a.fps:
        ch["fps"] = float(a.fps)
    if ch:
        info["order_changes"] = ch
    total = 0
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("vizavi.json", json.dumps(info, indent=1, ensure_ascii=False))
        for p, rel in files:
            z.write(p, "episode/" + rel.as_posix())
            total += p.stat().st_size
    print(f"packed {len(files)} files ({total / 1e6:.2f} MB raw) -> {zp}"
          + (f"\norder change for the app: {json.dumps(ch)}" if ch else ""))
    print("deliver it with SendUserFile; the user drops it into Vizavi Studio.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
