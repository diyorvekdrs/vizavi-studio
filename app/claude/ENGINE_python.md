# Python engine (numpy / CuPy on the user's RTX 3060)

Start from `templates/python/film.py` + `templates/audio.py` (copy to `episode/`): camera spline, stars,
bloom, ACES tonemap, grain/dither, text, word-timed captions, scene dispatcher – all GPU-safe.
Files in `episode/`: `film.py`, `audio.py`, helper modules, `CHANGES.md`. At render time the app puts
the kit (`backend.py`, `fakegpu.py`, `ff.py`, `vzrender.py`), `fonts/`, `assets/`, `brand/` and
`input/` (narration, music, words.tsv, beats.tsv, captions.srt) next to film.py.

```
film.py
  W, H, FPS, NFR            design size (the main spec size), exact fps, frame count
  ALPHA = False             True -> render_frame returns RGBA (H, W, 4); background alpha 0
  RESPONSIVE = False        True when several aspect versions are ordered: layout from W/H each time
  set_res(w, h)             called before rendering at any size/aspect (preview 960 long side, finals)
  render_frame(i) -> numpy uint8 (H, W, 3) or (H, W, 4)
  prepare_assets()          build/cache heavy assets into ./cache (runs once per render)
  SELFTEST_FRAMES = [2 heavy, representative frames]
  SCENES = [("name", start_s, end_s), ...]
  CUES   = [(t_s, "word", "what happens"), ...]
  camera_state(t) -> 1D array (pos + target [+ fov])   # enables the smoothness check
audio.py  writes mix.wav (may import NFR/FPS from film)
```
- Scale every size with `min(W, H)` or `W / design_W`; never hard-code pixels.
- Fonts: `Path(__file__).parent / "fonts" / "Poppins-Medium.ttf"` (Poppins-Light/Regular/Medium,
  DejaVuSans, DejaVuSans-Bold, DejaVuSansMono) or brand fonts in `brand/`. Text via Pillow on the
  host after `cpu()`; supersample 2× for crisp edges. **Draw all on-screen text with the template's `text()` and
  `captions()`** (or call `_note_text(...)` from your own text code): they report what is on screen to the
  automatic checks (cut off, in the app's button zones, too small, too faint, too brief, alphabet, spelling);
  text drawn any other way goes unchecked.
- Images/clips from `assets/`: load with Pillow / ffmpeg in `prepare_assets()`, cache as .npy. These are the
  full-size originals at render time (you only have light copies – `input/ASSETS.md`): size by the frame,
  never by the copy's pixels; cuts/crops go in `media.json` (the app makes them from the original).
- Per-frame cost close to the library examples (a 2K final should stay within minutes).

## GPU-safety (the sandbox checks with the strict fake GPU - `RENDER_FAKEGPU=1`)
- all per-pixel arrays via `xp` / `ndi` from `backend`; host data → `asx()`; to numpy only via `cpu()`
- never mix numpy and xp arrays in one operation; no `np.asarray()` on device arrays
- `np.mgrid` / `np.linspace` results must go through `asx()` before xp math
- no `xp.repeat` with an array of counts (cumsum + searchsorted instead)
- PIL works on numpy; convert with `asx()` before compositing on the device

## Craft techniques (cinematic look)
- Work in linear light (float32), composite in HDR, then tonemap (filmic/ACES-like) and apply the grade;
  add tiny dither noise before the 8-bit conversion to avoid banding in dark gradients.
- Bloom from pixels above a threshold, at 2–3 blur radii; never bloom the whole frame.
- Light: one motivated key, physically plausible falloff, rim light to separate subjects from black space.
- Depth: parallax layers moving at different speeds; depth of field by blurring layers by distance from
  the focus plane; atmospheric fade for distant layers.
- Motion blur: average 3–5 sub-frame samples (or blur along the motion vector) when anything moves fast;
  the camera's own motion blurs the background, not the subject it tracks.
- Organic detail: fBm / domain-warped noise for gas, dust, plasma, clouds; animate the noise slowly.
- Particles: many small ones with varied size/brightness, sorted by depth, size shrinking with distance.
- Space realism: stars of varied magnitude and slight color, no twinkling in vacuum; black holes need a
  black shadow, a thin photon ring and a Doppler-asymmetric disk.
- Camera: C1 splines (library `spline`), ease in/out, slow drift; expose `camera_state(t)` for the check.
- Finish: subtle vignette, 1–2% film grain, very light chromatic aberration at the edges at most.
