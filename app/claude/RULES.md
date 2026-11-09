# Vizavi project contract (read once per chat)

This package comes from **Vizavi Studio**, the user's desktop app. The user does no manual work:
they drop zips between the app and this chat. Every reply ends with a zip made by
`tools/vizavi_pack.py`, delivered with SendUserFile. Do not ask questions: decide, and write your
assumptions in `episode/CHANGES.md`.

## What to make
`input/brief.md` is the order: **Take care of** + **standing rules** (must-haves / must-nots, binding),
**Spec** (exact: size, aspect versions, fps, duration, alpha, audio routing, captions, formats, safe area),
**What I want** (the user's vision), **Style** and **Purpose**. `input/order.json` is the same in JSON.
How to turn it into a strong video: **DIRECTION.md** (process, craft, self-critique) – follow it.

Inputs that may exist: `input/narration.*` + `words.tsv` (word timings of the REAL voice; the words use
the script's spelling where the narrator followed it – `source` column: `script`, `script~` = timing
estimated inside a misheard span, `audio` = the narrator said something not in the script; spell those
as spoken) + `script_alignment.md` (where the audio differs from the script) + `captions.srt`
(built from words.tsv); `asr_passes.md` = two raw recognizer passes (rebuild the transcript from them when no
script was given – DIRECTION.md §1a); `words_whisper.tsv` is raw, often misspelled output – never use it for text;
`input/script.txt` (the author's text – best source for meaning);
`input/music.*` + `beats.tsv` (beats, downbeats, section changes); `input/assets/*` (the user's images,
video clips, logos, fonts – LIGHT COPIES; at render time the full-size originals are at `assets/<name>` –
read `input/ASSETS.md`: never ship re-encoded/trimmed/scaled copies of them, declare clip cuts in `media.json`);
`style_ref/` when present (a saved style the user wants matched – read `style_ref/STYLE.md` first);
`input/brand/*` (logo, fonts, `brand.json` colors). Use what's given; don't invent brand facts.

## Choose the engine (unless the spec fixes it)
- **python** (`ENGINE_python.md`): realistic/cinematic, space, 3D-ish scenes, particles, lensing,
  volumetric light, photographic compositing - anything per-pixel. Uses the GPU on the user's PC when HARDWARE.md says it has one, else the CPU.
- **html** (`ENGINE_html.md`): kinetic typography, captions-heavy social video, UI/product demos,
  charts and data viz, flat or illustrated motion graphics, layout across several aspect ratios.
- One engine per project. Read only that engine's doc.

## Avoid waste (not effort)
- Don't invoke any skill (e.g. vizavi-motion), don't ask the user questions, don't send a storyboard
  for approval. Decide, and record assumptions in `episode/CHANGES.md`.
- Don't render the full video in the sandbox (2 CPU cores, no GPU) – the user's PC renders the preview
  in about a minute. Use `tools/sandbox_check.py` for stills, spec, camera and sound checks.
- Don't rewrite what `library/` already solves (see LIBRARY.md): reuse techniques and code, not looks.
- The sandbox has no pip/network: numpy, scipy, Pillow, ffmpeg, Playwright/Chromium and the kit only.
  No cairo. No CDN links or web fonts in html (use `fonts/` and local files).
- Do spend the saved time on the visuals: the plan, the craft and the self-critique in DIRECTION.md are
  required. Your chat reply stays short (what the video shows + anything the user must know).

## Sound
`audio.py` writes `mix.wav` (48 kHz stereo, exactly NFR/FPS s): **only your ambient bed and SFX**
(and a synthesized music bed if the spec asks for generated music). Never put the narration or the
user's music in it – the app mixes those per the spec (ducking, loudness). Keep SFX sparse and
pleasant, ≥ 12 dB under the voice while it speaks, true peak ≤ −1 dBTP.
Optional `mix.json` written next to it: `{"music_db": -4, "music_gain_db": [[t, dB], ...],
"sfx_gain_db": [[t, dB], ...]}` for music level / automation (the app also ducks music under the voice).

## Every project must provide
- the engine's entry (`film.py` or `project.json` + `index.html`), `audio.py`, `CHANGES.md`
- `PLAN.md`: sentence table, concept, visual language, shot list, self-critique scores and the
  Take-care-of checklist (DIRECTION.md) – the pack tool refuses a project without it
- `SCENES = [[name, start_s, end_s], ...]` covering 0..duration (HUD, checks, beat/cut sync)
- `CUES = [[t_s, "word", "what happens"], ...]` - your sync plan; the report checks each cue
  against when the word is actually spoken
- exact `fps`, frame count `NFR`, alpha flag, `responsive` flag as the spec requires
- deterministic frames: frame i depends only on i (frames render out of order in parallel)
- several aspect versions → responsive layout: recompose per aspect (not just crop/letterbox)

## Burned-in captions (when the spec asks)
Draw them yourself: 1–2 short lines, active word highlighted, inside the safe area, never covering key
action, consistent position and style. **Read the words at render time**, never hard-code their times: the
app puts the final, precisely timed `input/words.tsv` + `input/captions.srt` next to film.py / index.html
(html engine: also `VZ.words` = [[start, end, word], …] and `VZ.wordAt(t)`). The text uses ‘ in oʻ/gʻ.

## Tools
```
python tools/sandbox_check.py episode                   # stills, spec check, other aspects, camera, sound
python tools/sandbox_check.py episode --times 12.4,31   # only what you changed
python tools/vizavi_pack.py --kind preview|final --note "..."
```
Outputs: `check/sheet_XX.jpg` (labelled: time, frame, scene, spoken word), `check/variant_<id>.jpg`,
`check/audio_plot.png`, `check/report.txt`. Fix every ERROR line before packing.
