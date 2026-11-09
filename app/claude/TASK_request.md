# Vizavi Studio · new project "{{EP}}" · build the {{KIND}} package

Extract this zip, `cd` into it, then:

1. Read `input/brief.md` (the order: Take care of, standing rules, spec, What I want, style), `RULES.md`,
   `DIRECTION.md` and `HARDWARE.md` (the PC that renders this – CPU-only PCs need light scenes). Main size {{SIZE}} @ {{FPS}} fps; all versions: {{VARIANTS}}; responsive: {{RESP}}.
   Duration {{DUR}} s → suggested NFR = {{NFR}}.
2. **Transcript** (DIRECTION §1a): if `vizavi.json` → `transcript_source` is `"asr"` (no script given),
   rebuild the clean Uzbek transcript from `input/asr_passes.md` → `episode/transcript.md` +
   `transcript_clean.txt` → `python tools/retime.py`. With a script: just check `script_alignment.md`.
3. **Understand** (DIRECTION §1): sentence table in `episode/PLAN.md` from `input/script.txt` (meaning)
   and `input/words.tsv` (timing); key facts and how to show them accurately.
4. **Concept + beats** (DIRECTION §2–3): copy `PLAN_TEMPLATE.md` to `episode/PLAN.md` and fill it: 3 concepts → choose, visual language, one beat
   per sentence with cue words, camera, transitions, text, sound.
5. Choose the engine (RULES.md), read that engine's doc including its craft techniques, skim
   `LIBRARY.md` and reuse techniques/code from it.
6. Risk probe on the riskiest beat, then build `episode/` from `templates/` (SCENES and CUES from the beats,
   anchored to words) and `audio.py`.
7. `python tools/sandbox_check.py episode` → study `check/sheet_*.jpg` (+ `variant_*.jpg`,
   `audio_plot.png`) as a sequence. Fix every ERROR. **Self-critique** (DIRECTION §5): score every beat,
   improve anything below 4 and the two weakest beats (`--scene NAME` for quick re-checks), tick every
   Take-care-of item. Stop at the Definition of done (DIRECTION §8).
8. `python tools/vizavi_pack.py --kind {{KIND}} --note "..."`, send the zip with SendUserFile. Reply in a few
   lines: the concept in one sentence, the uncertain transcript words (if you rebuilt it), anything else
   the user must know.

The user drops your zip into Vizavi Studio, which renders it on their PC (see HARDWARE.md)
({{KIND}} = "preview": a 960 px preview comes back to you for review; "final": the finished files).
