# Vizavi Studio · "{{EP}}" · the {{STAGE}} render FAILED on the user's PC

`error/log.txt` is the end of the log, `error/env.txt` the user's environment (Windows version, graphics card,
CuPy, Playwright/Chromium and Python versions - read it, don't assume). `episode/` is the exact code that failed.

1. Find the cause in the log. Python engine GPU problems are usually GPU-safety violations
   (ENGINE_python.md); html engine problems show as "JS error"/"console.error" lines.
   Reproduce with `python tools/sandbox_check.py episode --no-audio` and fix.
2. Change nothing else unless it is needed for the fix.
3. `python tools/vizavi_pack.py --kind {{KIND}} --note "fix: ..."`, send with SendUserFile, reply in 1–2 lines.
