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
- `report.md` – automatic checks, **ranked**: P0 broken · P1 a viewer leaves or misreads · P2 costs
  attention · P3 finishing. Text on screen (cut off, runs off the frame, in the app's button zones, too small,
  too faint, too brief, Cyrillic against a Latin rule, likely misspelled), spec, glitches, black/blown frames,
  flicker, static spans, camera, loudness and voice/bed balance, cue sync, scene starts against the beats
- `audio_plot.png` – narration (blue) vs everything else (orange) over time
- `preview.mp4` – extract extra frames only where needed: `ffmpeg -ss 12.5 -i review/preview.mp4 -frames:v 1 f.jpg`

Steps:
1. Read `RULES.md`, `DIRECTION.md` and the engine doc only if you haven't in this chat.
2. **Notes → asks** (before changing anything): in `episode/CHANGES.md` add a table
   `| # | the user's words | the ask (one change) | where (time/scene/element) | keep unchanged | done how |`.
   One note can hold several asks – one row each. "Bolder/Quieter/Faster/…: x" lines from the quick buttons are
   one ask each. A change keeps everything it doesn't name; only "start over / this isn't working" allows a
   redesign (then say what is kept).
3. **Director's pass** (DIRECTION §10): the asks → report.md P0/P1 (all fixed, or why it's on purpose) → the
   sheets as one sequence (story, clarity, beauty, motion, accuracy, sync, readability) → PLAN.md, What I want,
   Take care of → P2/P3 if there is room.
4. Fix the causes in `episode/`; improve at least the two weakest beats even if nothing flags them – without
   touching what an ask said to keep. Re-check what changed: `python tools/sandbox_check.py episode --times ...`
5. Update PLAN.md scores (old → new, incl. 5b) and CHANGES.md (fill "done how" for every ask).
6. `python tools/vizavi_pack.py --kind final --note "..."` (use `--kind preview` only if the user's notes
   ask for another preview or you made a major rework). Send with SendUserFile; reply in a few lines
   listing what you changed.
