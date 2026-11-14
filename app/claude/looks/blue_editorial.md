# Look: Blue Editorial (Editorial kinetic type)

**Suits:** A bold one-line statement, a launch, a title card, a manifesto line.

The user picked this look in Vizavi Studio. Build the whole video in it – it is binding, like a saved style: palette, type, layout, texture, motion and the Never list. Keep the content, story and timing from the narration and the brief; adapt the layout to this project's frame size(s). Look at `look/` (three frames of the look) first.

Build it with the **HTML engine** (canvas/SVG/DOM; see ENGINE_html.md). Rules below are written per frame size fraction, so they hold for 9:16, 16:9 and 1:1 alike.

## The look
- Electric ultramarine (#2433F0 – blue, never purple or navy), white (#F4F5FA), rules in the same white at ~55 % opacity. Nothing else; flat colour, crisp edges.
- Two faces only, all lowercase: huge words in Instrument Serif Italic (≈22 % of frame width per letter, tracking −0.03em), small words in Schibsted Grotesk Black (~6 % of frame height, tracking −0.045em). The contrast between huge italic and small heavy sans IS the style.
- A cover stack, not a grid: small kicker word over a full-width rule, a huge italic word whose ascender breaks through that rule, a small word right-aligned on a short second rule, a small word sitting on the baseline of a huge final italic word, a closing rule.

## How it moves
- Frame one already shows huge letters rising through a baseline mask, 2–3 frames apart, ~10 % overshoot.
- Scale jump: the opening word holds huge for ~⅔ s, then snaps down to kicker size in ~8 frames with motion blur along the travel.
- A slanted wipe at the italic angle runs through the next word left to right, a thin white line riding its edge, collapsing as it exits.
- One word slides out from underneath another, as if it was tucked behind it.
- The last word flies in as four horizontal slices from alternating sides, lands off-register for a beat so the cut reads, then locks. Rules draw out on a fast ease. Each beat holds 8–15 frames; the finished cover holds ~1.5 s.

## Never
- Purple, navy, gradients or glow – one flat blue.
- A third typeface, or capitals.
- A modular grid, numbered labels or centred symmetry (that's Swiss – this is a cover).
- Fades or crossfades – words move, wipe, slice or slide.

## Frame sizes
9:16 is the cover; on 16:9 keep the stack in the central ~75 % of the width, big words slightly smaller.

## Fonts (already in this project's `assets/`)
```css
@font-face { font-family: 'Instrument Serif'; font-style: italic; font-weight: 400; font-display: block; src: url(assets/instrument-serif-latin-400-italic.woff2) format('woff2'); unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
@font-face { font-family: 'Instrument Serif'; font-style: italic; font-weight: 400; font-display: block; src: url(assets/instrument-serif-latin-ext-400-italic.woff2) format('woff2'); unicode-range: U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF; }
@font-face { font-family: 'Schibsted Grotesk'; font-style: normal; font-weight: 900; font-display: block; src: url(assets/schibsted-grotesk-latin-900-normal.woff2) format('woff2'); unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
@font-face { font-family: 'Schibsted Grotesk'; font-style: normal; font-weight: 900; font-display: block; src: url(assets/schibsted-grotesk-latin-ext-900-normal.woff2) format('woff2'); unicode-range: U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF; }
```

## Before you hand it over
Watch the motion strips the checks make and hold each beat against “How it moves” and “Never”: those words are the fix list – name the rule a frame breaks and fix that, rather than adding effects.
