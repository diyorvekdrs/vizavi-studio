# Vizavi Studio · "{{EP}}" · REVIEW preview v{{V}} and build the FINAL package

The user rendered your preview v{{V}} on their PC. `episode/` is the exact code that was rendered and
`episode/PLAN.md` your plan and scores; `input/brief.md` is the order (Take care of, standing rules,
spec, What I want).

Review material in `review/`:
- `USER_NOTES.md` – the user's notes on this preview (if present: top priority, do exactly what they ask)
  (corrections of transcript words: fix `episode/transcript_clean.txt` + transcript.md, re-run `python tools/retime.py`)
- `sheets/sheet_*.jpg` – 1 frame per second; the bar under each frame shows time, frame, scene and the
  spoken word (beats are ticks on the timeline; blue box = social safe area if ordered)
- `variant_<id>.jpg` – stills of the other aspect versions (if ordered)
- `report.md` – automatic checks: spec mismatches, glitches, black/blown frames, flicker, static spans,
  scene cuts, camera smoothness, loudness and voice/bed balance, cue sync against the spoken words,
  scene starts against the beats, durations, render speed
- `audio_plot.png` – narration (blue) vs everything else (orange) over time
- `preview.mp4` – extract extra frames only where needed: `ffmpeg -ss 12.5 -i review/preview.mp4 -frames:v 1 f.jpg`

Steps:
1. Read `RULES.md`, `DIRECTION.md` and the engine doc only if you haven't in this chat.
2. **Director's pass** (DIRECTION §6): USER_NOTES → the sheets as one sequence (story, clarity, beauty,
   motion, accuracy, sync, readability) → PLAN.md, What I want, Take care of → report.md.
3. Fix the causes in `episode/`; improve at least the two weakest beats even if nothing flags them.
   Re-check what changed: `python tools/sandbox_check.py episode --times ...`
4. Update PLAN.md scores (old → new) and CHANGES.md.
5. `python tools/vizavi_pack.py --kind final --note "..."` (use `--kind preview` only if the user's notes
   ask for another preview or you made a major rework). Send with SendUserFile; reply in a few lines
   listing what you changed.
