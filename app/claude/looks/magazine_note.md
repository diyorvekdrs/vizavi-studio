# Look: Magazine Layout + Note (Editorial layout)

**Suits:** Quotes, reading lists, essays, product stories – considered rather than loud.

The user picked this look in Vizavi Studio. Build the whole video in it – it is binding, like a saved style: palette, type, layout, texture, motion and the Never list. Keep the content, story and timing from the narration and the brief; adapt the layout to this project's frame size(s). Look at `look/` (three frames of the look) first.

Build it with the **HTML engine** (canvas/SVG/DOM; see ENGINE_html.md). Rules below are written per frame size fraction, so they hold for 9:16, 16:9 and 1:1 alike.

## The look
- Cool off-white paper (#EAEDED), near-black ink (#1B1E25), red ballpoint (#C42E26). The photo is a two-ink duotone from slate navy (#242E46) to pale grey-blue (#E2E7EC).
- Headline: Bodoni Moda (Regular + Italic) at ~9 % of frame height, tracking −0.03em, two lines – the second italic and indented. Body: Newsreader at ~1.4 % of frame height on generous leading, plus an italic caption. The note: La Belle Aurore, tilted about −7°.
- A thin rule across the top margin, the headline under it, a photo block on one side and a narrow body column on the other, caption under the photo. The note sits in the margin and an arrow crosses the gutter into the photo. Lots of white paper.
- Static paper grain with faint fibres, a light multiplied paper tooth over everything (ink and photo too), film grain inside the photo. No stock photo? Paint one: a dusk sea with a sun disk, torn cloud, a cloud bank and a glitter path on the water.

## How it moves
- Frame one already shows the rule, the first headline line and a sliver of photo. Every line of type rises out of its own mask, 2–5 frames apart, ~10 % overshoot, soft settle.
- The photo opens upward like a blind while the image settles out of a gentle push, then keeps drifting very slowly.
- The note writes itself along the strokes of each letter at handwriting speed (~8 letters a second) with short pen lifts between words; i-dots and the full stop come last. (In the HTML engine: SVG text with a stroke-dashoffset reveal per glyph, or a mask that follows each letter.)
- After a beat the pen draws an arrow with a small loop, lifts, and flicks the arrowhead on in one move.
- Hold the last 1.5 s so the page can be read.

## Never
- Warm cream, beige or sepia paper – the paper is cool.
- A straight left-to-right wipe or typewriter reveal for the note.
- Drop shadows, page curls or frames around the photo.
- Fades – every element arrives through a mask or a stroke.

## Frame sizes
9:16: headline on top, photo and column stacked or side by side, bottom fifth bare. 16:9: photo left, column right (a spread).

## Fonts (already in this project's `assets/`)
```css
@font-face { font-family: 'Bodoni Moda'; font-style: normal; font-weight: 400; font-display: block; src: url(assets/bodoni-moda-latin-400-normal.woff2) format('woff2'); unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
@font-face { font-family: 'Bodoni Moda'; font-style: normal; font-weight: 400; font-display: block; src: url(assets/bodoni-moda-latin-ext-400-normal.woff2) format('woff2'); unicode-range: U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF; }
@font-face { font-family: 'Bodoni Moda'; font-style: italic; font-weight: 400; font-display: block; src: url(assets/bodoni-moda-latin-400-italic.woff2) format('woff2'); unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
@font-face { font-family: 'Bodoni Moda'; font-style: italic; font-weight: 400; font-display: block; src: url(assets/bodoni-moda-latin-ext-400-italic.woff2) format('woff2'); unicode-range: U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF; }
@font-face { font-family: 'Newsreader'; font-style: normal; font-weight: 400; font-display: block; src: url(assets/newsreader-latin-400-normal.woff2) format('woff2'); unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
@font-face { font-family: 'Newsreader'; font-style: normal; font-weight: 400; font-display: block; src: url(assets/newsreader-latin-ext-400-normal.woff2) format('woff2'); unicode-range: U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF; }
@font-face { font-family: 'Newsreader'; font-style: italic; font-weight: 400; font-display: block; src: url(assets/newsreader-latin-400-italic.woff2) format('woff2'); unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
@font-face { font-family: 'Newsreader'; font-style: italic; font-weight: 400; font-display: block; src: url(assets/newsreader-latin-ext-400-italic.woff2) format('woff2'); unicode-range: U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF; }
@font-face { font-family: 'La Belle Aurore'; font-style: normal; font-weight: 400; font-display: block; src: url(assets/la-belle-aurore-latin-400-normal.woff2) format('woff2'); unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
@font-face { font-family: 'La Belle Aurore'; font-style: normal; font-weight: 400; font-display: block; src: url(assets/la-belle-aurore-latin-ext-400-normal.woff2) format('woff2'); unicode-range: U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF; }
```

## Before you hand it over
Watch the motion strips the checks make and hold each beat against “How it moves” and “Never”: those words are the fix list – name the rule a frame breaks and fix that, rather than adding effects.
