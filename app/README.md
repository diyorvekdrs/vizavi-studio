# Vizavi Studio 2

Make any kind of video with Claude by dragging and dropping files: narrated explainers, Shorts, Reels
and TikToks, music promos, kinetic typography, logo stings with transparency, product/UI demos, data
visualizations, GIFs. Any size, aspect ratio, frame rate, sound setup and file format.

## One-time setup
Use **Install Vizavi Studio.cmd** from the shared zip (it installs Python if needed, the app into
`%LOCALAPPDATA%\VizaviStudio` with its own Python environment, and shortcuts on the Desktop, Start menu and
right-click **Send to**). The first start checks this PC and installs only what it can use (see *Any PC*
below); the first transcription downloads the speech models (3–6 GB).

## Every project
| # | You | Studio / Claude |
|---|-----|-----------------|
| 1 | Drop your files on Studio (voice, music, images, clips, logo, script .txt) **or** click **＋ New project**. Pick a preset, adjust anything, **Create package** | Whisper word timings, music beats, captions → `NAME__request.zip` (folder opens, chat message copied) |
| 2 | Drag the zip into a Claude chat, **Ctrl+V**, **Enter** | Claude builds it → `NAME__preview_v1.zip` |
| 3 | Click download | Studio picks it up from Downloads, renders a preview (with voice, timing bar, safe-area box), plays it, makes `NAME__review_v1.zip` |
| 4 | Drag the review zip into the **same** chat (notes optional) – or click **Approve** | Claude fixes what it finds → `NAME__final_v2.zip` |
| 5 | Click download | Studio renders every size and format → `Projects\NAME\output\` |

Workflow "Straight to final" (in the dialog) skips steps 3–4 for simple jobs.
A failed render becomes `NAME__error_vN.zip`; drag it into the chat the same way.

## What you can ask for (New project dialog)
- **Presets**: Narrated explainer 16:9 · YouTube 16:9 with voice+music · Shorts/Reels/TikTok 9:16 ·
  Instagram 4:5 · Square 1:1 · Music promo (beat-synced) · Kinetic typography · Logo sting (transparent) ·
  Product/UI demo · Data visualization · 4K cinematic · GIF/sticker · Custom. Save your own with
  **Save as my preset…**
- **Size** (any W×H) and **extra aspect versions** (16:9, 9:16, 1:1, 4:5) – one project, re-composed per aspect
- **Frame rate** 12–60 · **Duration** from the narration, the music, or fixed seconds
- **Audio**: narration and/or music in; export as ambient+SFX only, voice+SFX, voice+music+SFX
  (music automatically ducks under the voice), music+SFX, or silent; Claude can compose a music bed;
  loudness −14 / −16 / −23 LUFS or as-is
- **Captions**: none, .srt, burned in (styled, active word highlighted), or both · narration language
- **Safe area** for Shorts/TikTok/Reels UI · **Transparent background**
- **Formats**: MP4 H.264, MP4 H.265, MOV ProRes (4444 with alpha), WebM VP9 (alpha), GIF, PNG sequence
- **Engine**: Python/GPU (realistic, cinematic, particles, space) or HTML/Canvas/SVG (typography, UI,
  charts, flat motion graphics) – or let Claude decide
- **What I want** (your vision: story, mood, must-show moments) and **Take care of** (must-haves, must-nots,
  accuracy) – Take care of is binding and Claude must tick off every item before it may pack
- **My rules** (Settings): standing rules added to every project, e.g. "text in Uzbek Latin only"
- **Style** presets + notes, purpose/topic, **brand kits** (`brands\NAME\`: brand.json, logo, fonts)

## Built-in quality and speed
- Claude starts from tested **templates** (`claude/templates/`: Python/GPU and HTML engines + sound) and a fill-in
  **PLAN_TEMPLATE.md** (beats with 3 variants each, camera, transitions, accent map, scores); it checks single
  scenes with `sandbox_check --scene` and stops at a clear Definition of done – less time, fewer errors.
- `DIRECTION.md` in every zip makes Claude work like a director: understand each sentence, pick one
  concept, write a shot list (`PLAN.md`), use real craft techniques, then score every scene and rework the
  weakest before packing; the review stage is a director's pass, not just a bug fix.
- Instructions travel in every zip (`CLAUDE_TASK.md`, `RULES.md`, engine docs) – any chat works, no skill
  or storyboard round-trips, Claude never renders the full video in its sandbox.
- Library of finished projects (`library\`) sent with new requests, best matches first.
- Automatic checks on every preview: spec mismatches, glitches/unplanned cuts, black/blown frames,
  flicker, static stretches, camera smoothness, cue-vs-word sync, scene-vs-beat sync, voice-vs-music/SFX
  balance, loudness, durations, and stills of every other aspect version.
- Heavy assets are sent to Claude as light copies; renders use your originals.

## Uzbek transcription (maximum accuracy)
1. **Whisper large-v3** on the GPU gives the timing (the app installs the CUDA libraries it needs).
2. **islomov/rubaistt_v2_medium** (Whisper fine-tuned on ~475 h of Uzbek) gives better words
   (downloaded + converted once, ~3 GB).
3. **Your script**, when pasted, is the truth for spelling; the voice decides where you changed words.
4. **No script? Claude rebuilds the transcript** from both passes (standard Uzbek Latin, English translation,
   list of uncertain words) as the first step of every project, and re-times it onto the audio.
5. **Precise timing**: Meta's MMS forced aligner moves every word to its exact spoken boundary (20 ms) on
   your PC – also for Claude's corrected words. License CC-BY-NC-4.0 (non-commercial use);
   `"precise_timing": false` in settings.json turns it off.
Captions and the preview timing bar always use the final words. **Check transcript** shows the result,
**Redo transcript…** re-runs it (e.g. after pasting the script) and rebuilds the request zip.
First run downloads ~5 GB of models in total (one time). Every step falls back safely if something fails.

## Settings (`settings.json`)
`projects_dir`, `whisper_model` (large-v3), `whisper_device` (auto/cpu), `preview_long_side` (960),
`preview_crf`, `final_crf` (14), `workers` (blank = auto), `watch_downloads`, `downloads_dir`,
`auto_play_preview`, `library_in_request`, `user_presets`, `uzbek_model`, `precise_timing`, `mms_model`, `models_dir` (where the Whisper model is stored; blank = your user profile; e.g. `"D:\\VizaviStudio\\models"` to keep it with the app on a USB drive).

## Any PC
At every start the app checks the PC (Settings → **This PC** shows the result) and fits itself to it:
- **NVIDIA card with a recent driver (≥ 528) and ≥ 4 GB:** renders and speech on the GPU; 1–3 render
  workers by graphics memory; small cards use the memory-saving speech mode automatically.
- **Older NVIDIA driver, AMD or Intel graphics, or no graphics card:** nothing GPU-specific is installed;
  speech and renders run on the processor with workers fitted to cores and memory; a smaller Whisper model
  on weaker processors; 720 px previews.
- **Less than 8 GB memory or 12 GB free disk:** the Uzbek model and precise timing are switched off.
- Every package tells Claude about the PC (`HARDWARE.md`), so on a processor-only PC Claude designs lighter
  scenes and says when a final will take long.
After a hardware or driver change, press **Check and repair components** in Settings.

## Folders
`Projects\NAME\` → `source` (order, narration, music, assets, timings, beats, captions), `to_claude`,
`from_claude`, `work`, `output`, `logs`. `kit\` = render kit (your original files unchanged + `vzrender.py`),
`claude\` = what goes into the zips, `library\` = reusable projects, `brands\` = brand kits.

## Troubleshooting
- Something didn't install: Settings → **Check and repair components**, then read the log (bottom right).
- The window doesn't open: run `Start Vizavi Studio (if double-click does nothing).bat`; errors go to
  `crash.log` next to the app.
- Logs: `Projects\NAME\logs\`, `crash.log` next to the app. Manual render in any `work\...` folder:
  `python vzrender.py out\test.mp4 --size 1920x1080` (add `--codec prores` for alpha).
