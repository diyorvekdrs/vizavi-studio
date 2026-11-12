"""Runs every test: python tests (t_*.py) and the UI test (needs Node + jsdom: `npm install` in tests/).
usage: python tests/run_all.py            exit code 0 = all passed"""
import os, shutil, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHON=sys.executable)
results = []
for t in sorted(HERE.glob("t_*.py")):
    t0 = time.time()
    r = subprocess.run([sys.executable, str(t)], cwd=HERE, env=env, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=900)
    ok = r.returncode == 0 and "FAILS: none" in r.stdout
    results.append((t.name, ok, time.time() - t0))
    print(f"{'PASS' if ok else 'FAIL'}  {t.name}  ({time.time() - t0:.0f}s)", flush=True)
    if not ok:
        print("\n".join(l for l in r.stdout.splitlines() if l.startswith("FAIL")) or r.stdout[-3000:])
        print(r.stderr[-3000:])
node = shutil.which("node")
if node and (HERE / "node_modules" / "jsdom").exists():
    t0 = time.time()
    r = subprocess.run([node, str(HERE / "ui_test.js")], cwd=HERE, env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=600)
    ok = r.returncode == 0 and "FAILS: none" in r.stdout
    results.append(("ui_test.js", ok, time.time() - t0))
    print(f"{'PASS' if ok else 'FAIL'}  ui_test.js  ({time.time() - t0:.0f}s)")
    if not ok:
        print(r.stdout[-4000:], r.stderr[-2000:])
else:
    print("skip  ui_test.js  (run `npm install` in tests/ to include it)")
bad = [n for n, ok, _ in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} passed" + (f" – failed: {', '.join(bad)}" if bad else ""))
sys.exit(1 if bad else 0)
