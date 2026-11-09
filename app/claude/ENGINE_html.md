# HTML engine (HTML/CSS/SVG/Canvas/WebGL, rendered frame by frame in headless Chromium)

Start from `templates/html/*` + `templates/audio.py` (copy to `episode/`): responsive stage, scene dispatcher,
kinetic-type helper, word-timed captions with the active word, safe area, parallax dust, grain.
Files in `episode/`: `project.json`, `index.html` (+ your .js/.css/.svg/media), `audio.py`, `CHANGES.md`.
At render time the app puts `vz.js` (runtime), `vzrender.py`, `fonts/`, `assets/`, `brand/` and
`input/` next to index.html. The renderer loads `index.html?w=..&h=..`, waits for `VZ.isReady()`,
then for each frame calls `VZ.seek(t)` and takes a screenshot (transparent if alpha).

```json
project.json
{ "engine": "html", "width": 1080, "height": 1920, "fps": 30, "nfr": 900,
  "alpha": false, "responsive": true,
  "scenes": [["hook", 0, 2.4], ["point1", 2.4, 9.1]],
  "cues":   [[2.35, "birinchi", "card 1 slides in"]] }
```
```html
<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="style.css"></head>
<body><div id="stage"> … </div>
<script src="vz.js"></script><script src="main.js"></script></body></html>
```
## Rules
- Everything visible lives inside `#stage`. `responsive: false` → fixed design canvas of
  width×height, scaled to the output size. `responsive: true` (required when several aspect
  versions are ordered) → `#stage` is the output size; lay out with the CSS var `--u` (1% of the
  short side), `VZ.W`, `VZ.H`, `VZ.isPortrait`, and recompose per aspect.
- Motion ONLY as a function of time: `VZ.onFrame((t, VZ) => {...})` for canvas/SVG/DOM updates,
  or CSS animations / Web Animations with explicit delays (they are paused and scrubbed to t).
  Never requestAnimationFrame, setTimeout/setInterval, Date, performance.now or Math.random
  (use `VZ.rand(seed)`).
- Helpers: `VZ.prog(t, a, b, VZ.ease.inOut)` (0..1 inside [a,b]), `VZ.ease.{linear,smooth,in,out,inOut,outBack}`,
  `VZ.lerp`, `VZ.clamp`, `VZ.duration`, `VZ.fps`.
- Fonts: `@font-face { font-family: P; src: url(fonts/Poppins-Medium.ttf) }` (also Light/Regular,
  DejaVuSans*), brand fonts in `brand/`. No web fonts or CDN scripts: everything local.
- Images: `<img src="assets/name.png">` (decoded before frame 0). Video clips:
  `VZ.video(document.querySelector('video'))` - muted, seeked exactly per frame.
- Chromium here cannot play H.264. For any clip from the user, declare the cut in `media.json`
  (`{"clips":[{"out":"media/x.webm","src":"<asset>","start":s,"duration":d,"fps":FPS}]}`, see
  `input/ASSETS.md`) and use `media/x.webm`: the app makes it from the full-size original before each
  render. Never encode it yourself from the light copy for delivery (a test copy at that path is fine).
- Canvas: size it to `VZ.W × VZ.H` (or the design size when not responsive) and redraw fully in onFrame.
- Alpha: keep html/body/#stage transparent; the runtime enforces it.
- Text renders crisp at any size; prefer real text/SVG over bitmaps.
- `audio.py` is still Python (numpy/scipy) and writes `mix.wav` (SFX only; silence is fine).
- Preview the page in the sandbox only via `tools/sandbox_check.py` (it uses the same renderer).

## Craft techniques (motion design look)
- Grid and margins: a clear layout grid, ≥ 5% safe margins; align, don't scatter.
- Type: max two families; headline ≥ 7% of the short side, body ≥ 3.5%; tight tracking on big type;
  kinetic type by word/letter with staggered timing (20–60 ms), mask/clip reveals, emphasis on stressed
  words by scale, weight or color – the active spoken word is always identifiable.
- Easing: entrances `out`/expo-like, moves `inOut`, small overshoot (`outBack`) only where it fits the tone.
- Depth: layered parallax, soft shadows, blur for background layers, scale changes for push-ins.
- Transitions: masks, wipes along the composition's lines, shared-element moves, push-through – motivated.
- Texture: subtle noise/grain overlay, gradients with noise, light leaks if the style allows – avoid flat
  default-looking UI and generic rounded cards.
- Shapes: SVG paths with stroke-dash drawing, morphs between related shapes, canvas for particles.
- Charts: draw axes first, animate the data change, direct labels, highlight the insight, honest scales.
