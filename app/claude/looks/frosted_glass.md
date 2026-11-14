# Look: Frosted Glass UI (Glassmorphism)

**Suits:** App or tool walkthroughs, “how I'd do X”, any idea framed as a search.

The user picked this look in Vizavi Studio. Build the whole video in it – it is binding, like a saved style: palette, type, layout, texture, motion and the Never list. Keep the content, story and timing from the narration and the brief; adapt the layout to this project's frame size(s). Look at `look/` (three frames of the look) first.

Build it with the **HTML engine** (canvas/SVG/DOM; see ENGINE_html.md). Rules below are written per frame size fraction, so they hold for 9:16, 16:9 and 1:1 alike.

## The look
- Background: a defocused dusk photo built from soft colour fields – teal-to-navy sky (#1F5A6E → #0E2A3D), a coral glow on the horizon (#FF8A5C), a rose field (#E3558A), a row of small out-of-focus city lights, a few big soft bokeh discs, darker blurred corners like a lens, fine grain.
- Glass: a much more blurred copy of that same background (not a CSS backdrop-filter over a gradient), slightly smoked and desaturated, with a bright rim strongest at the top-left, a faint inner glow at the edges and a soft drop shadow.
- One wide search bar (~85 % of the frame width, corners ~48 px at 1080 wide) and a results panel of the same width (radius ~22 px) below it. Rows share one left gutter: a small glass icon tile, then title over label. The highlight is inset ~14 px with a radius 14 px smaller than the panel.
- Type: Plus Jakarta Sans, sentence case – query medium, row titles semibold with slightly tight tracking, labels small at ~65 % opacity, a faint shadow under text so it keeps ≥ 4.5:1 contrast on the glass. Off-white text (#F8F9FB); the only cool accent is the caret (#9FD8FF).

## How it moves
- Frame one already shows the bar on the photo, settling from ~90 % scale with a soft overshoot.
- Typing feels human: ~1.3 frames per character with a little jitter and a beat between words. Caret solid while typing, blinking when idle.
- When the query is done the bar glides up and the panel unfolds from behind it (~9 % overshoot). Rows drop in from above on a ~3-frame stagger, each overshooting ~10 %.
- The highlight stretches between rows – leading edge on a stiff spring, trailing edge on a soft one. Selecting gives a small press pulse and a return keycap that pops in.
- The background drifts only a few pixels a second. Hold the last second.

## Never
- A live backdrop blur over a gradient – it bands. Blur the colour field itself (canvas filter on the painted field), add grain/dither, check the encoded file.
- Evenly spaced polka-dot bokeh, neon glow, purple-gradient wallpaper.
- Milky white glass with white text below 4.5:1.
- Panels or rows fading in – they unfold and drop.

## Frame sizes
9:16: bar and panel mid-frame, bottom fifth only blurred background. 16:9: the group can sit a bit higher with a wider bar (~70 % of width).

## Fonts (already in this project's `assets/`)
```css
@font-face { font-family: 'Plus Jakarta Sans'; font-style: normal; font-weight: 400; font-display: block; src: url(assets/plus-jakarta-sans-latin-400-normal.woff2) format('woff2'); unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
@font-face { font-family: 'Plus Jakarta Sans'; font-style: normal; font-weight: 400; font-display: block; src: url(assets/plus-jakarta-sans-latin-ext-400-normal.woff2) format('woff2'); unicode-range: U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF; }
@font-face { font-family: 'Plus Jakarta Sans'; font-style: normal; font-weight: 500; font-display: block; src: url(assets/plus-jakarta-sans-latin-500-normal.woff2) format('woff2'); unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
@font-face { font-family: 'Plus Jakarta Sans'; font-style: normal; font-weight: 500; font-display: block; src: url(assets/plus-jakarta-sans-latin-ext-500-normal.woff2) format('woff2'); unicode-range: U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF; }
@font-face { font-family: 'Plus Jakarta Sans'; font-style: normal; font-weight: 600; font-display: block; src: url(assets/plus-jakarta-sans-latin-600-normal.woff2) format('woff2'); unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
@font-face { font-family: 'Plus Jakarta Sans'; font-style: normal; font-weight: 600; font-display: block; src: url(assets/plus-jakarta-sans-latin-ext-600-normal.woff2) format('woff2'); unicode-range: U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF; }
```

## Before you hand it over
Watch the motion strips the checks make and hold each beat against “How it moves” and “Never”: those words are the fix list – name the rule a frame breaks and fix that, rather than adding effects.
