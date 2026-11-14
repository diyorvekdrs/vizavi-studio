# Look: Glow Orb (Glowing 2D)

**Suits:** Calm one-liners: mindset, wellness, intros, a quiet statement.

The user picked this look in Vizavi Studio. Build the whole video in it – it is binding, like a saved style: palette, type, layout, texture, motion and the Never list. Keep the content, story and timing from the narration and the brief; adapt the layout to this project's frame size(s). Look at `look/` (three frames of the look) first.

Build it with the **HTML engine** (canvas/SVG/DOM; see ENGINE_html.md). Rules below are written per frame size fraction, so they hold for 9:16, 16:9 and 1:1 alike.

## The look
- Ground: near-black, warm (#070304). One orb a little above centre: white core (#FBF6F8) into pink (#F696DE), a thin bright rim, and a deep rose halo (#531829 → #13050B) that dies out well before the corners.
- Six or seven thin outline circles (#F6EFF2 at low opacity) scattered toward the edges at different sizes and depths, some cut by the frame.
- Type: Outfit Medium, sentence case ending in a full stop, about 6 % of frame height, tracking around −0.03em. One line, centred under the orb.
- Texture: only a very fine moving grain inside the glow so its long falloff never bands.

## How it moves
- Frame one already shows a small lit orb. It winds back a touch, then takes one deep breath on a spring (~10 % overshoot) and settles; afterwards it breathes 2–3 % over about three seconds, the light lagging the body slightly.
- The circles drift with parallax as the view pushes gently toward the orb: near circles bigger, brighter and faster, far ones thin and dim. The push loses speed over a long tail.
- The line rises letter by letter out of an invisible mask (~2–3 frames apart), each letter overshooting slightly while the letter-spacing tightens into place. Settled by ~2.5 s, then it holds.
- One beat inside the hold: the orb exhales and its rim lifts off as a single thin ring that springs out to about twice the orb's size and stays there as an orbit.

## Never
- Fades of any kind – things rise, spring, drift or detach.
- Pink flooding the frame: the corners stay near-black, the glow belongs to the orb.
- Particles, sparkles, lens flares, a second accent colour.
- More than one line of type, or a heavy/rounded font.

## Frame sizes
9:16: orb in the upper third, the line under it, the bottom fifth empty. 16:9: same stack centred, circles spread wider. 1:1: orb just above centre.

## Fonts (already in this project's `assets/`)
```css
@font-face { font-family: 'Outfit'; font-style: normal; font-weight: 500; font-display: block; src: url(assets/outfit-latin-500-normal.woff2) format('woff2'); unicode-range: U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD; }
@font-face { font-family: 'Outfit'; font-style: normal; font-weight: 500; font-display: block; src: url(assets/outfit-latin-ext-500-normal.woff2) format('woff2'); unicode-range: U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF; }
```

## Before you hand it over
Watch the motion strips the checks make and hold each beat against “How it moves” and “Never”: those words are the fix list – name the rule a frame breaks and fix that, rather than adding effects.
