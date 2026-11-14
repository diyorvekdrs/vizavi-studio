"""Uzbek window language: the dictionary loads, every {n} in an Uzbek text exists in its English key, no key twice
with different texts, and index.html loads the files in the right order."""
import sys, os, json, shutil, subprocess
from pathlib import Path
APPDIR = Path(os.environ.get("VZ_APP") or Path(__file__).resolve().parent.parent / "app")
fails = []
def check(n, c, x=""):
    print(("ok   " if c else "FAIL ") + n, "" if c else x)
    if not c: fails.append(n)

node = shutil.which("node")
if not node:
    print("skip (no node)"); print("\nFAILS: none"); sys.exit(0)
js = ("const fs=require('fs');global.window={};eval(fs.readFileSync(process.argv[1],'utf8'));"
      "process.stdout.write(JSON.stringify(window.VZ_UZ))")
r = subprocess.run([node, "-e", js, str(APPDIR / "ui" / "lang" / "uz.js")], capture_output=True, text=True, encoding="utf-8")
check("uz.js loads", r.returncode == 0, r.stderr[-500:])
D = json.loads(r.stdout or "[]")
check("hundreds of entries", len(D) > 400, len(D))
import re
seen = {}
for en, uz in D:
    ph_en, ph_uz = set(re.findall(r"\{\d\}", en)), set(re.findall(r"\{\d\}", uz))
    if not ph_uz <= ph_en:
        check(f"placeholders of “{en[:50]}”", False, (ph_en, ph_uz))
    if en in seen and seen[en] != uz:
        check(f"one text for “{en[:50]}”", False, (seen[en], uz))
    seen[en] = uz
check("Uzbek uses the modifier letter ʻ, not a backtick", not any("`" in uz for _, uz in D))
html = (APPDIR / "ui" / "index.html").read_text(encoding="utf-8")
i, j, k = html.find("/ui/lang/uz.js"), html.find("/ui/i18n.js"), html.find("/ui/app.js")
check("index.html: dictionary, then i18n, then app", -1 < i < j < k, (i, j, k))
print("\nFAILS:", fails or "none")
sys.exit(1 if fails else 0)
