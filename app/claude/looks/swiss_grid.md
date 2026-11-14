# Look: Swiss Grid (Swiss style)

**Suits:** A bold one-line statement, a principle, a manifesto opener.

The user picked this look in Vizavi Studio. Build the whole video in it – it is binding, like a saved style: palette, type, layout, texture, motion and the Never list. Keep the content, story and timing from the narration and the brief; adapt the layout to this project's frame size(s). Look at `look/` (three frames of the look) first.

Build it with the **HTML engine** (canvas/SVG/DOM; see ENGINE_html.md). Rules below are written per frame size fraction, so they hold for 9:16, 16:9 and 1:1 alike.

## The look
- Paper #F0F0E8, ink #101010, signal red #F03820. Nothing else; flat colour, hard edges.
- Type: Public Sans ExtraBold, sentence case, tracking ~−0.05em, flush-left ragged-right. Leading equals one grid module so every baseline sits on a grid line, and the first stem of each line sits exactly on the margin. Small captions in Public Sans 600: numeral in full ink, word at ~60 %.
- Four equal columns inside wide side margins, rows on the same square module, thin 2 px lines edge to edge. The red field covers a block of whole cells and may bleed off the top/right. The circle is exactly one or two modules wide and sits on grid intersections. Type fills the rows under the field and overprints it.

## How it moves
- The grid draws first, already mid-draw on frame one: verticals drop, horizontals sweep, ~2 frames apart, fast start and a long settle.
- The circle steps cell to cell along the grid like a rook – each step a crisp spring (~9 % overshoot) with real motion blur.
- The red field opens out of the cell where the circle stops: the cell grows, snaps across the columns, then up and down the rows; each edge overshoots its grid line and settles back onto it.
- Each line of type is pushed out of the left margin line along its row, 6 frames apart, overshoots ~8 % and locks flush-left. Captions drop from a grid line as each part lands. The circle winds back ~10 %, then grows into its final two-module slot.
- Everything settled by ~2.5 s. Hold.

## Never
- Centred type, or any edge landing between grid lines.
- A second accent, gradients, shadows, glow or grain.
- Fades – things snap, slide or grow out of a grid line.
- A geometric or rounded display face, or decorative corner labels.

## Frame sizes
Any size: derive the module from the frame width (4 columns inside the margins) and keep every element on whole cells.

## Fonts (already in this project's `assets/`)
```css
@font-face { font-family: 'Public Sans'; font-style: normal; font-weight: 600; font-display: block; src: url(assets/public-sans-latin-600-normal.woff2) format('woff2'); unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
@font-face { font-family: 'Public Sans'; font-style: normal; font-weight: 600; font-display: block; src: url(assets/public-sans-latin-ext-600-normal.woff2) format('woff2'); unicode-range: U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF; }
@font-face { font-family: 'Public Sans'; font-style: normal; font-weight: 800; font-display: block; src: url(assets/public-sans-latin-800-normal.woff2) format('woff2'); unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
@font-face { font-family: 'Public Sans'; font-style: normal; font-weight: 800; font-display: block; src: url(assets/public-sans-latin-ext-800-normal.woff2) format('woff2'); unicode-range: U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF; }
```

## Before you hand it over
Watch the motion strips the checks make and hold each beat against “How it moves” and “Never”: those words are the fix list – name the rule a frame breaks and fix that, rather than adding effects.
