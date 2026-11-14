# Look: Risograph (Risograph print)

**Suits:** Event promos, zines, music, playful brand moments – hand-made, not digital.

The user picked this look in Vizavi Studio. Build the whole video in it – it is binding, like a saved style: palette, type, layout, texture, motion and the Never list. Keep the content, story and timing from the narration and the brief; adapt the layout to this project's frame size(s). Look at `look/` (three frames of the look) first.

Build it with the **HTML engine** (canvas/SVG/DOM; see ENGINE_html.md). Rules below are written per frame size fraction, so they hold for 9:16, 16:9 and 1:1 alike.

## The look
- Cool off-white paper (#EDEFEE), fluorescent pink (#FF48B0), medium blue (#3255A4). Where they overlap you get deep violet (~#32186F) – from multiplying the inks (mix-blend-mode: multiply / canvas 'multiply'), never picked by hand.
- Type: Bricolage Grotesque ExtraBold capitals, tracked ~5 %, big enough to span the poster. One short word knocked out of a shape so the paper shows through.
- Poster layout: hero word across the top, two overlapping circles, a second word on a band of diagonal stripes, a row of dots growing left to right like a halftone ramp, wide paper margins.
- Each ink is its own plate: mottled density with paper-white specks and slightly ragged edges; halftone dots (~12 px cell at 1080 wide) for any tone, each ink on its own screen angle; plates a few pixels out of register so two-ink areas get a pink fringe on one side and a blue one on the other; faint paper cloud and fibre, a few stray specks.

## How it moves
- Everything animates on twos (each drawing holds 2 frames). Every new drawing is a fresh print: re-roll the grain and shift the registration by a pixel or two.
- Shapes either stamp or slide. A stamp lands big (110–116 %) with a few degrees of tilt, undershoots ~9 % and settles over 4–5 steps. A slide comes in from off-frame on a spring with 8–12 % overshoot.
- Build the poster one element at a time, 4–6 frames apart, in reading order. Frame one already shows ink on paper.
- Second beat: a registration slip – both plates kick 20–30 px apart and spring back past register, so the two-ink word splits into a pink and a blue copy, then snaps together.
- Hold the finished poster at least a second on each side of the slip; a slow crawl in the stripes keeps it alive.

## Never
- Warm cream or bone paper, or more than two inks plus their overlap.
- Smooth 30 fps motion or motion blur – it's a stack of prints.
- Clean vector edges or flat digital colour without grain.
- Any gradient that isn't made of halftone dots.

## Frame sizes
Portrait poster on 9:16 (bottom fifth empty); on 16:9 run the hero word left and the circles right.

## Fonts (already in this project's `assets/`)
```css
@font-face { font-family: 'Bricolage Grotesque'; font-style: normal; font-weight: 800; font-display: block; src: url(assets/bricolage-grotesque-latin-800-normal.woff2) format('woff2'); unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
@font-face { font-family: 'Bricolage Grotesque'; font-style: normal; font-weight: 800; font-display: block; src: url(assets/bricolage-grotesque-latin-ext-800-normal.woff2) format('woff2'); unicode-range: U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF; }
```

## Before you hand it over
Watch the motion strips the checks make and hold each beat against “How it moves” and “Never”: those words are the fix list – name the rule a frame breaks and fix that, rather than adding effects.
