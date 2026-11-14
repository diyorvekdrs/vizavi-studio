# Look: Pencil to Blueprint (Technical drawing)

**Suits:** Idea-to-product, process, design and engineering stories.

The user picked this look in Vizavi Studio. Build the whole video in it – it is binding, like a saved style: palette, type, layout, texture, motion and the Never list. Keep the content, story and timing from the narration and the brief; adapt the layout to this project's frame size(s). Look at `look/` (three frames of the look) first.

Build it with the **HTML engine** (canvas/SVG/DOM; see ENGINE_html.md). Rules below are written per frame size fraction, so they hold for 9:16, 16:9 and 1:1 alike.

## The look
- Paper #ECECE6 with a faint engineering grid (#7FA3C4), graphite #25262B, blueprint blue #1C4C8F, tide-line blue #143C76, ink white #EEF4FB.
- Type: Barlow Semi Condensed – measurements Medium with tabular figures; the label in caps SemiBold, tracking +0.07em, flush-left above a thin rule.
- One simple object in side view, large in the middle, standing on a ground line. The label top-left, aligned with the drawing's left edge; two or three dimensions to the side and underneath.
- Graphite with paper tooth: doubled, slightly bowed strokes with overshooting ends. Fine paper grain over everything, a very light mottle in the blue.

## How it moves
- The sketch goes down in a real order: ground line and light construction axes, then confident outlines, joints as overshooting circles, quick hatching last. Each stroke eases in and out like a hand; the pencil is already moving on frame one.
- The finished sketch holds ~⅓ s. Then ink floods out from inside the drawing with an irregular wet edge and a darker tide line just inside it – fast at first, then slowing.
- Wherever the edge passes, graphite becomes white ink and each line springs straight. Construction strokes become dash-dot centre lines.
- Then the system lands: centre marks pop, extension lines grow, dimension lines draw out from their middle, arrowheads pop, numbers tick up. The label rises over a rule that draws first. Hold 1.5 s.

## Never
- A cut or crossfade from sketch to blueprint – it is one drawing, promoted.
- Glow on the white lines, or a gradient on the blue.
- A different object for the blueprint, or more than three dimensions.
- A handwriting font for the label, or a drawn pencil/hand on screen.

## Frame sizes
Any size: the object fills ~50 % of the frame height; on 9:16 put the label above the drawing and keep dimensions out of the bottom fifth.

## Fonts (already in this project's `assets/`)
```css
@font-face { font-family: 'Barlow Semi Condensed'; font-style: normal; font-weight: 500; font-display: block; src: url(assets/barlow-semi-condensed-latin-500-normal.woff2) format('woff2'); unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
@font-face { font-family: 'Barlow Semi Condensed'; font-style: normal; font-weight: 500; font-display: block; src: url(assets/barlow-semi-condensed-latin-ext-500-normal.woff2) format('woff2'); unicode-range: U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF; }
@font-face { font-family: 'Barlow Semi Condensed'; font-style: normal; font-weight: 600; font-display: block; src: url(assets/barlow-semi-condensed-latin-600-normal.woff2) format('woff2'); unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
@font-face { font-family: 'Barlow Semi Condensed'; font-style: normal; font-weight: 600; font-display: block; src: url(assets/barlow-semi-condensed-latin-ext-600-normal.woff2) format('woff2'); unicode-range: U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF; }
```

## Before you hand it over
Watch the motion strips the checks make and hold each beat against “How it moves” and “Never”: those words are the fix list – name the rule a frame breaks and fix that, rather than adding effects.
