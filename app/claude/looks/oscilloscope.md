# Look: Oscilloscope (Oscilloscope art)

**Suits:** Tech, music, data, launches, any “it all clicked” moment.

The user picked this look in Vizavi Studio. Build the whole video in it – it is binding, like a saved style: palette, type, layout, texture, motion and the Never list. Keep the content, story and timing from the narration and the brief; adapt the layout to this project's frame size(s). Look at `look/` (three frames of the look) first.

Build it with the **HTML engine** (canvas/SVG/DOM; see ENGINE_html.md). Rules below are written per frame size fraction, so they hold for 9:16, 16:9 and 1:1 alike.

## The look
- Screen #030805 with a faint tube-face lift (#09150E) in the middle; graticule #0D2216 of square divisions with ticks on the two centre axes, fading out toward the edges so there is never a border.
- The words ARE the trace: monoline geometric capitals drawn as one continuous stroke standing on the zero line, cap height ~9 % of the frame height. Readouts, if any, in small dim-green Share Tech Mono – a few words at most.
- Phosphor glow: an almost white core (#D7FFF3), a tight green halo (#46FF8C), a short persistence trail of the last few frames behind anything that moves, fine grain in the dark screen.

## How it moves
- One continuous line for the whole piece. Every change is that line changing shape – never a cut or a swap.
- It opens on a scrolling sine wave that catches the trigger and locks, then folds into a slowly turning 2:3 Lissajous figure.
- The figure releases back into a wave and rings down to a flat line like a damped oscillation, swinging through zero once.
- The letters rise out of the flat line left to right, each overshooting ~10 % and settling, the persistence trail smearing beneath. Hold at least 1.5 s.
- Draw the trace as an SVG/canvas path; build the letters as polylines that start and end on the baseline so the beam never breaks; persistence = the same path at t−1, t−2, t−3 frames with falling opacity.

## Never
- Neon-sign glow – keep the halo tight and green, the core almost white.
- A box around the screen, or labels in the corners.
- Letters that appear from nowhere – they grow out of the line.
- More than one small line of readouts.

## Frame sizes
Any size: the beam runs off both sides of the frame like a real scope; on 9:16 use a shorter word or two stacked traces.

## Fonts (already in this project's `assets/`)
```css
@font-face { font-family: 'Share Tech Mono'; font-style: normal; font-weight: 400; font-display: block; src: url(assets/share-tech-mono-latin-400-normal.woff2) format('woff2'); unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
```

## Before you hand it over
Watch the motion strips the checks make and hold each beat against “How it moves” and “Never”: those words are the fix list – name the rule a frame breaks and fix that, rather than adding effects.
