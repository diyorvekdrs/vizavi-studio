# Direction: maximum result, minimum time (read fully, every project)

Speed comes from structure, not from less care: start from `templates/`, fill `PLAN_TEMPLATE.md`, build
scene by scene, check cheaply (stills, one scene at a time), stop at the Definition of done (§8).

## 0. Priorities
1. **Take care of** + **standing rules** (`input/brief.md`) – binding. 2. **Spec**. 3. **What I want**.
4. Style / purpose, then your taste. Never trade accuracy, readability or the voice for flash.

## 1a. Transcript (first, when `vizavi.json` → `transcript_source` is `"asr"` or the match is low)
Speech recognition is weak for Uzbek. `input/asr_passes.md` = two raw passes (Whisper large-v3, Uzbek
model) with times. Rebuild what was actually said like a careful native editor: both passes + the meaning of
the whole narration + grammar → **standard Uzbek Latin**, colloquial endings in standard written form, the
speaker's wording and order, punctuation, oʻ/gʻ written with ‘ (U+2018).
→ `episode/transcript.md` (clean text · English translation · uncertain words: time – choice – what was
heard – why) → `episode/transcript_clean.txt` → `python tools/retime.py` → use `episode/words.tsv` from now
on; list the uncertain words in your final reply. With a script (`"script"`): only check `script_alignment.md`.

## 1. Understand (PLAN.md §1)
Sentence table: `# | start–end | original | meaning (English) | what the viewer must see / understand / feel`.
Key claims, numbers, names, cause → effect; for educational content one line each on what is
physically/historically accurate and how it will be shown (black hole: black shadow, thin photon ring,
Doppler-bright approaching side of the disk, no sound and no twinkling in space). Show what is said; a metaphor
only for abstract ideas – then a clear one. Unknown real facts are not invented.

## 2. One thread (PLAN.md §2)
**The point** first: the one sentence the viewer should believe after one watch (`brief.md` → "The point"; if
it's missing, write it yourself from What I want). Every beat serves it; a beat that doesn't is cut.
**Kind** (`brief.md` → "Kind", else decide): explain · pitch · story · promo · mood – it picks the questions in §7.
3 candidate concepts (one line each: *what acts, what changes, what the result proves*) → choose one.
Not the previous video's sequence under a new name; no reflex circle / letter O / portal motif.
Visual language, one line each: palette (3–5), light motivation, type pair, motion character, sound palette.

## 3. Beats (PLAN.md §3 – the plan card, one row per beat, usually one sentence, 2–6 s)
| field | content |
|---|---|
| time · cue | interval; the cue word (lead it by 2–4 frames) or beat/downbeat with music |
| options | **3 one-line variants** differing in action, composition/space, metaphor or transition (colour/font changes don't count) → the chosen one |
| action | state before → trigger → action → reaction → result |
| space | composition; foreground / midground / background; light; material |
| text | exact words, their action, reading window (≥ 0.3 s/word + 0.5 s) – or none |
| camera | path, speed curve, target, framing, FOV, focus |
| link | entry from the previous beat → what carries the transition → exit |
| sound | bed change / SFX on which event – or explicit silence |
| risk | the main risk of this beat and how you'll check it |
Rhythm: vary framing, alternate calm/intense, one climax, no idea held > ~6 s while the voice runs, calm
readable ending.

## 4. Craft
**Camera & depth.** One long coherent trajectory with *waves* of speed – not the same ease-in-out stopping
dead on every accent. At joins match position, direction, screen speed and acceleration. Big moves resolve
into a calm arc/drift while something is read. Three planes that differ in scale, relative motion, overlap
and perspective; tracking a subject still shows parallax around it. A meaningful cut needs no continuous
world coordinate between different places.
**Optics & form.** Motion blur follows *relative screen motion* (a tracked subject stays sharp, the
background smears; blur fades on deceleration). Depth of field follows the meaningful detail; text and the
subject stay recognisable. Radial/zoom blur is a stylised accent, not a substitute for DOF or motion blur.
Form reads through geometry, light, thickness, contact shadow and occlusion – grain, glow and particles never
fix a wrong construction.
**Motion.** Preparation → action → contact → reaction → settle, with different masses and curves. One
main accent at a time; secondary layers support it. No repeated flashes/strobes as fake energy.
**Transitions** are designed with both beats: a match cut agrees in silhouette, scale, orientation and
direction; a mask really reveals the next scene inside it; one location keeps poses, perspective, light and
speeds; a reveal is tied to a real occlusion or action.
**Typography.** Design the readable final layout first, then the letters' action (assembly, masks, width,
interaction with objects) – the effect must mean something. Check the glyphs exist (Uzbek ‘, Cyrillic) in the
font. Labels near moving 3D objects follow the projected anchor without lag or jitter; never let geometry
cross the text.
**Simplicity guard.** "Cleaner" is not allowed to delete required characters, text, environment or actions.

## 5. Sound
Ambient + SFX per the spec (music only when the spec asks: then motif/groove, development, contrast, an
ending – a pile of whooshes is not music). SFX belong to motion, contact, material and transitions – not the
same whoosh on every cut, not doubling every musical hit. Accent map in PLAN.md: `t (frame/fps) – audio
accent – visual event`; with music use `beats.tsv` (real beats/sections), not a guessed grid. Voice
intelligibility and reading beat any beat-grid; silence is a tool.

## 6. Build fast and correct
- Start from `templates/python/` or `templates/html/` (working skeletons: scene dispatcher, camera,
  HDR/bloom/grain or stage/captions, safe areas, word-timed captions, audio helpers). Adapt; don't rewrite.
- One function per beat/scene; frame `i` depends only on `i` (cold seek works).
- Never hard-code word times: read `input/words.tsv` at render time (html: `VZ.words`).
- Forbidden: cairo, CDN/web fonts, network; html: requestAnimationFrame/setTimeout/Date/Math.random for
  motion; python: numpy↔xp mixing (ENGINE_python.md GPU-safety).
- **Risk probe before the full build**: render the riskiest beat at real size (`sandbox_check --times T
  --width 960`) and fix the approach early.

## 7. Check and self-critique (PLAN.md §5)
`python tools/sandbox_check.py episode` (all), then `--scene NAME` for the scene you're improving.
Look at the sheets as a sequence. Score every beat 1–5: **Meaning · Accuracy · Beauty · Motion · Sync ·
Readability**. Below 4 → fix. Then one extra pass on the two weakest beats. Tick every Take-care-of item
(`✓ how`). Log real issues as `interval → observation → cause → fix → re-checked`.
Then judge **the whole piece** with the questions for its kind (PLAN.md §5b), each *weak / ok / strong*;
any *weak* is fixed before packing:
- **open** (explain, pitch, story, promo): do the first 2 s hold something that makes this audience stay, and
  does it raise a question the rest answers?
- **point** (all): after one watch, could the viewer say the point in one plain sentence?
- **shown** (explain, pitch, promo): when the voice claims something, is it on screen at that moment, working –
  not only described?
- **loop** (explain): does it follow one example through, each step leading to the next, instead of jumping
  between unrelated examples?
- **pull** (story): does each scene end on something unresolved?
- **land** (explain, pitch, story, promo): does the end land – a next step, a payoff or a return to the opening?
- **pace** (all): do shot lengths follow what they hold, nothing still longer than it earns, cuts on words/beats?
- **read** (all): is every word that matters big, sharp against what's behind it and on long enough?
- **sound** (all): is the voice clear over everything, effects marking moments rather than filling space?
- **world** (all): do colour, type, motion and sound keep one direction from first frame to last?
- **own** (all): with the name hidden, could this only be this project and not any video in its category?
Honest statuses in CHANGES.md: *built* · *seen in stills* · *not yet seen in motion* (the app's preview
shows motion; never claim what you couldn't see).

## 8. Definition of done (then stop and pack)
No ERROR (P0/P1) from sandbox_check · no *weak* whole-piece answer · every beat ≥ 4 · two weakest beats got the extra pass · every Take-care-of ✓ ·
transcript done (asr projects) · PLAN.md and CHANGES.md complete. Remaining ideas are taste – note them in one
line in CHANGES.md, don't keep polishing.

## 9. Kinds of video (quick rules)
Explainer/science: accuracy, scale comparisons, cause → effect. · Shorts/Reels/TikTok: hook in the first
second, a change every 1–2 s, big captions, loop-friendly end. · Music promo: cuts on beats, accents on
downbeats, energy follows sections. · Kinetic type: words land on their syllable, emphasis by scale/weight/
colour, motion mirrors meaning. · Logo sting: anticipation → build → reveal → settle, clean last second. ·
UI demo: natural cursor paths, highlight what matters, zoom to detail. · Data viz: one insight per chart,
animate the change, direct labels, honest axes.

## 10. Review of a preview (stage 2)
USER_NOTES first (transcript corrections → fix `transcript_clean.txt`, re-run `retime.py`). One note can hold
several asks: restate them first (TASK_review.md, CHANGES.md "Notes → asks"). **A change keeps; a redesign
replaces:** an ask touches what it names and leaves everything else exactly as it was – only "this isn't
working / start over" allows a redesign. Then `report.md`: every P0 and P1 is fixed (or, if it is on purpose,
say why in CHANGES.md); P2 if the pass has room; P3 last. Then the sheets as
one sequence (story, clarity, beauty, motion, accuracy, sync, readability) → PLAN.md, What I want, Take care
of → `report.md`. Fix causes, not symptoms; improve the two weakest beats even if nothing flags them; update
scores (old → new) and CHANGES.md; stop at §8.

## 11. Refuse (each of these has been corrected before; allowed only when the brief asks for it by name)
- **Template captions**: white bold text with one yellow word, an emoji pop, a zoom on every sentence, a whoosh on
  every entrance.
- **The same move everywhere**: one entrance, zoom or sound on every beat makes every beat weaker.
- **Effects stacked until the subject blurs**: bloom + grain + glow + blur + lens tricks. One effect, where it means
  something; glow only where the eye should go.
- **Cutting to a fixed tempo** (every N seconds or a BPM grid) instead of words, beats and sections.
- **Cameras that ease A → B and stop dead**: keep moving through the cut unless following a subject that stops.
- **Wide, empty frames** with the subject small in the middle; **close-ups with no reason**.
- **A tour of features / a list of facts** instead of one example followed through.
- **Copy that sounds like an ad**: buzzwords, "Not X. Y." cadences, slogans, a label above every headline.
- **Never**: invented facts, numbers, quotes or results; redrawn logos (use the real files); calling it done
  without looking at the stills.
