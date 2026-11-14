# Look: Apple One-Take (Keynote style)

**Suits:** Product reveals, feature launches, “here's how it works” openers.

The user picked this look in Vizavi Studio. Build the whole video in it – it is binding, like a saved style: palette, type, layout, texture, motion and the Never list. Keep the content, story and timing from the narration and the brief; adapt the layout to this project's frame size(s). Look at `look/` (three frames of the look) first.

Build it with the **HTML engine** (canvas/SVG/DOM; see ENGINE_html.md). Rules below are written per frame size fraction, so they hold for 9:16, 16:9 and 1:1 alike.

## The look
- Flat light ground (#EEEEEC), ink #111113, paper #FBFBF9 and ONE red accent (#FF3B30) used on a single dot only. One soft blue gradient is allowed inside a “content” tile.
- Type: Inter Tight – the closing line 700 at ~9 % of frame height (176 px at 1920 tall), tracking −0.04em; UI labels 600; secondary text at 50–70 % opacity; counters with tabular figures.
- Everything is centred on one carrier object. The closing line sits a little above the middle, well inside the safe area.
- No texture, no vignette. Depth only from layered soft shadows (a tight contact shadow plus two wide soft ones) scaled to the object, which disappear once it becomes type.

## How it moves
- ONE object carries the whole film, each state growing out of the last: a dot grows a pill, a pointer presses it, it opens into a card, the card grows a bezel and becomes a phone, the camera pulls back and the bezel closes into the “O” of the closing line. The red dot survives every state and lands last as the full stop.
- Colour changes by geometry, never by crossfade: black turns white because the pill's dark edge thins from the inside out.
- Entrances on springs with ~10 % overshoot, big reshapes ~5 %. Contents trail their container by ~3 frames.
- Fast moves get directional motion blur sized from that object's own speed; holds are razor sharp.
- The pull-back shrinks exponentially (slows down like a real camera). The final line holds at least a second.

## Never
- A cut, crossfade or fade-in where a morph should be.
- A second accent colour, or the accent on anything but the hero dot.
- A gradient vignette on the ground (it bands in the export) – keep it flat.
- Text sliding at constant speed, or blur left on a held frame.

## Frame sizes
Works the same in every size: the carrier stays centred; on 9:16 keep the bottom fifth empty.

## Fonts (already in this project's `assets/`)
```css
@font-face { font-family: 'Inter Tight'; font-style: normal; font-weight: 600; font-display: block; src: url(assets/inter-tight-cyrillic-600-normal.woff2) format('woff2'); unicode-range: U+0301,U+0400-045F,U+0490-0491,U+04B0-04B1,U+2116; }
@font-face { font-family: 'Inter Tight'; font-style: normal; font-weight: 600; font-display: block; src: url(assets/inter-tight-latin-600-normal.woff2) format('woff2'); unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
@font-face { font-family: 'Inter Tight'; font-style: normal; font-weight: 600; font-display: block; src: url(assets/inter-tight-latin-ext-600-normal.woff2) format('woff2'); unicode-range: U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF; }
@font-face { font-family: 'Inter Tight'; font-style: normal; font-weight: 700; font-display: block; src: url(assets/inter-tight-cyrillic-700-normal.woff2) format('woff2'); unicode-range: U+0301,U+0400-045F,U+0490-0491,U+04B0-04B1,U+2116; }
@font-face { font-family: 'Inter Tight'; font-style: normal; font-weight: 700; font-display: block; src: url(assets/inter-tight-latin-700-normal.woff2) format('woff2'); unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
@font-face { font-family: 'Inter Tight'; font-style: normal; font-weight: 700; font-display: block; src: url(assets/inter-tight-latin-ext-700-normal.woff2) format('woff2'); unicode-range: U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF; }
```

## Before you hand it over
Watch the motion strips the checks make and hold each beat against “How it moves” and “Never”: those words are the fix list – name the rule a frame breaks and fix that, rather than adding effects.
