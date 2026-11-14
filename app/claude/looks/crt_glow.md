# Look: Retro CRT Glow (CRT / retro-futurism)

**Suits:** Announcements, “coming up next”, premieres, throwbacks, anything that should feel broadcast.

The user picked this look in Vizavi Studio. Build the whole video in it – it is binding, like a saved style: palette, type, layout, texture, motion and the Never list. Keep the content, story and timing from the narration and the brief; adapt the layout to this project's frame size(s). Look at `look/` (three frames of the look) first.

Build it with the **HTML engine** (canvas/SVG/DOM; see ENGINE_html.md). Rules below are written per frame size fraction, so they hold for 9:16, 16:9 and 1:1 alike.

## The look
- Tube black (#07090F) with a faint blue-grey lift in the middle (#0B0E16). Phosphor core near-white (#FCFBF8), bloom soft rose-coral (#FF9A90), one small accent red (#F05A4A).
- Title: Syncopate Bold capitals, tracked out ~6 %, two stacked lines filling ~80 % of the frame width, just above the middle. Under it one line of system text in Share Tech Mono (spaced capitals, ~80 % brightness), anchored on the left so typing never shifts it, with a small red dot in front. Nothing in the corners.
- White-hot core inside a three-layer warm bloom (tight, medium, wide haze), drawn with dither. Fine horizontal scanlines following the glass, slight barrel curvature, a vignette darkening into the rounded tube edge, a faint diagonal sheen, a hint of red/blue fringe toward the sides, light snow.

## How it moves
- Frame one is already a lit horizontal line across a dark tube. It swells for a few frames, splits into two bright edges that race apart, and the picture unfolds between them – starting squashed, overshooting ~10 % taller and settling, all in ~12 frames.
- The tube comes up hot: extra brightness, bloom, fringe and a little sync wobble on the open, easing off over ~0.5 s.
- System text types in at ~1 character every 1.5 frames behind a solid block cursor; the red dot pops when the line is done; then the cursor blinks with a short phosphor fade.
- In the hold a soft hum bar rolls slowly down and brightness flickers ~1 %. Hold at least 2 s.
- The exit is faster than the entry: the picture collapses into the bright line in ~9 frames, then the line narrows back to the opening state, so it loops.

## Never
- Saturated neon or a coloured outline glow – the core stays near-white, the colour lives in the haze.
- A box or border – the tube edge only ever reads as vignette.
- Fading the title in – it arrives with the picture opening.
- Heavy glitching, RGB split or jitter on settled text.

## Frame sizes
16:9 is the natural tube; on 9:16 stack the title on two to three lines and keep the bottom fifth empty.

## Fonts (already in this project's `assets/`)
```css
@font-face { font-family: 'Syncopate'; font-style: normal; font-weight: 700; font-display: block; src: url(assets/syncopate-latin-700-normal.woff2) format('woff2'); unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
@font-face { font-family: 'Syncopate'; font-style: normal; font-weight: 700; font-display: block; src: url(assets/syncopate-latin-ext-700-normal.woff2) format('woff2'); unicode-range: U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF; }
@font-face { font-family: 'Share Tech Mono'; font-style: normal; font-weight: 400; font-display: block; src: url(assets/share-tech-mono-latin-400-normal.woff2) format('woff2'); unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
```

## Before you hand it over
Watch the motion strips the checks make and hold each beat against “How it moves” and “Never”: those words are the fix list – name the rule a frame breaks and fix that, rather than adding effects.
