"""Writes app/claude/looks/: looks.json (cards in New project) and one LOOK recipe per look (what Claude reads).
Recipes are written for Vizavi Studio's HTML engine and any frame size. The ten looks are adapted from
Shaan Johari's "Animation styles you can build with Claude (or Codex)" (@viashaan) – credited in README.md."""
import json, sys
from pathlib import Path

OUT = Path(sys.argv[1])
SOURCE = ("Shaan Johari – “Animation styles you can build with Claude (or Codex)”",
          "https://ruby-cotija-fb5.notion.site/Animation-styles-you-can-build-with-Claude-or-Codex-3fa28691eca3814ebb34c73a7cc261bf")

L = [
 dict(id="glow_orb", name="Glow Orb", family="Glowing 2D", dark=True,
      suits="Calm one-liners: mindset, wellness, intros, a quiet statement.",
      swatch=["#070304", "#531829", "#F696DE", "#FBF6F8"],
      fonts={"Outfit": ["500"]},
      look=["Ground: near-black, warm (#070304). One orb a little above centre: white core (#FBF6F8) into pink (#F696DE), a thin bright rim, and a deep rose halo (#531829 → #13050B) that dies out well before the corners.",
            "Six or seven thin outline circles (#F6EFF2 at low opacity) scattered toward the edges at different sizes and depths, some cut by the frame.",
            "Type: Outfit Medium, sentence case ending in a full stop, about 6 % of frame height, tracking around −0.03em. One line, centred under the orb.",
            "Texture: only a very fine moving grain inside the glow so its long falloff never bands."],
      motion=["Frame one already shows a small lit orb. It winds back a touch, then takes one deep breath on a spring (~10 % overshoot) and settles; afterwards it breathes 2–3 % over about three seconds, the light lagging the body slightly.",
              "The circles drift with parallax as the view pushes gently toward the orb: near circles bigger, brighter and faster, far ones thin and dim. The push loses speed over a long tail.",
              "The line rises letter by letter out of an invisible mask (~2–3 frames apart), each letter overshooting slightly while the letter-spacing tightens into place. Settled by ~2.5 s, then it holds.",
              "One beat inside the hold: the orb exhales and its rim lifts off as a single thin ring that springs out to about twice the orb's size and stays there as an orbit."],
      never=["Fades of any kind – things rise, spring, drift or detach.",
             "Pink flooding the frame: the corners stay near-black, the glow belongs to the orb.",
             "Particles, sparkles, lens flares, a second accent colour.",
             "More than one line of type, or a heavy/rounded font."],
      sizes="9:16: orb in the upper third, the line under it, the bottom fifth empty. 16:9: same stack centred, circles spread wider. 1:1: orb just above centre."),
 dict(id="frosted_glass", name="Frosted Glass UI", family="Glassmorphism", dark=True,
      suits="App or tool walkthroughs, “how I'd do X”, any idea framed as a search.",
      swatch=["#0E2A3D", "#1F5A6E", "#FF8A5C", "#E3558A"],
      fonts={"Plus Jakarta Sans": ["400", "500", "600"]},
      look=["Background: a defocused dusk photo built from soft colour fields – teal-to-navy sky (#1F5A6E → #0E2A3D), a coral glow on the horizon (#FF8A5C), a rose field (#E3558A), a row of small out-of-focus city lights, a few big soft bokeh discs, darker blurred corners like a lens, fine grain.",
            "Glass: a much more blurred copy of that same background (not a CSS backdrop-filter over a gradient), slightly smoked and desaturated, with a bright rim strongest at the top-left, a faint inner glow at the edges and a soft drop shadow.",
            "One wide search bar (~85 % of the frame width, corners ~48 px at 1080 wide) and a results panel of the same width (radius ~22 px) below it. Rows share one left gutter: a small glass icon tile, then title over label. The highlight is inset ~14 px with a radius 14 px smaller than the panel.",
            "Type: Plus Jakarta Sans, sentence case – query medium, row titles semibold with slightly tight tracking, labels small at ~65 % opacity, a faint shadow under text so it keeps ≥ 4.5:1 contrast on the glass. Off-white text (#F8F9FB); the only cool accent is the caret (#9FD8FF)."],
      motion=["Frame one already shows the bar on the photo, settling from ~90 % scale with a soft overshoot.",
              "Typing feels human: ~1.3 frames per character with a little jitter and a beat between words. Caret solid while typing, blinking when idle.",
              "When the query is done the bar glides up and the panel unfolds from behind it (~9 % overshoot). Rows drop in from above on a ~3-frame stagger, each overshooting ~10 %.",
              "The highlight stretches between rows – leading edge on a stiff spring, trailing edge on a soft one. Selecting gives a small press pulse and a return keycap that pops in.",
              "The background drifts only a few pixels a second. Hold the last second."],
      never=["A live backdrop blur over a gradient – it bands. Blur the colour field itself (canvas filter on the painted field), add grain/dither, check the encoded file.",
             "Evenly spaced polka-dot bokeh, neon glow, purple-gradient wallpaper.",
             "Milky white glass with white text below 4.5:1.",
             "Panels or rows fading in – they unfold and drop."],
      sizes="9:16: bar and panel mid-frame, bottom fifth only blurred background. 16:9: the group can sit a bit higher with a wider bar (~70 % of width)."),
 dict(id="one_take", name="Apple One-Take", family="Keynote style", dark=False,
      suits="Product reveals, feature launches, “here's how it works” openers.",
      swatch=["#EEEEEC", "#111113", "#FBFBF9", "#FF3B30"],
      fonts={"Inter Tight": ["600", "700"]},
      look=["Flat light ground (#EEEEEC), ink #111113, paper #FBFBF9 and ONE red accent (#FF3B30) used on a single dot only. One soft blue gradient is allowed inside a “content” tile.",
            "Type: Inter Tight – the closing line 700 at ~9 % of frame height (176 px at 1920 tall), tracking −0.04em; UI labels 600; secondary text at 50–70 % opacity; counters with tabular figures.",
            "Everything is centred on one carrier object. The closing line sits a little above the middle, well inside the safe area.",
            "No texture, no vignette. Depth only from layered soft shadows (a tight contact shadow plus two wide soft ones) scaled to the object, which disappear once it becomes type."],
      motion=["ONE object carries the whole film, each state growing out of the last: a dot grows a pill, a pointer presses it, it opens into a card, the card grows a bezel and becomes a phone, the camera pulls back and the bezel closes into the “O” of the closing line. The red dot survives every state and lands last as the full stop.",
              "Colour changes by geometry, never by crossfade: black turns white because the pill's dark edge thins from the inside out.",
              "Entrances on springs with ~10 % overshoot, big reshapes ~5 %. Contents trail their container by ~3 frames.",
              "Fast moves get directional motion blur sized from that object's own speed; holds are razor sharp.",
              "The pull-back shrinks exponentially (slows down like a real camera). The final line holds at least a second."],
      never=["A cut, crossfade or fade-in where a morph should be.",
             "A second accent colour, or the accent on anything but the hero dot.",
             "A gradient vignette on the ground (it bands in the export) – keep it flat.",
             "Text sliding at constant speed, or blur left on a held frame."],
      sizes="Works the same in every size: the carrier stays centred; on 9:16 keep the bottom fifth empty."),
 dict(id="crt_glow", name="Retro CRT Glow", family="CRT / retro-futurism", dark=True,
      suits="Announcements, “coming up next”, premieres, throwbacks, anything that should feel broadcast.",
      swatch=["#07090F", "#0B0E16", "#FF9A90", "#F05A4A"],
      fonts={"Syncopate": ["700"], "Share Tech Mono": ["400"]},
      look=["Tube black (#07090F) with a faint blue-grey lift in the middle (#0B0E16). Phosphor core near-white (#FCFBF8), bloom soft rose-coral (#FF9A90), one small accent red (#F05A4A).",
            "Title: Syncopate Bold capitals, tracked out ~6 %, two stacked lines filling ~80 % of the frame width, just above the middle. Under it one line of system text in Share Tech Mono (spaced capitals, ~80 % brightness), anchored on the left so typing never shifts it, with a small red dot in front. Nothing in the corners.",
            "White-hot core inside a three-layer warm bloom (tight, medium, wide haze), drawn with dither. Fine horizontal scanlines following the glass, slight barrel curvature, a vignette darkening into the rounded tube edge, a faint diagonal sheen, a hint of red/blue fringe toward the sides, light snow."],
      motion=["Frame one is already a lit horizontal line across a dark tube. It swells for a few frames, splits into two bright edges that race apart, and the picture unfolds between them – starting squashed, overshooting ~10 % taller and settling, all in ~12 frames.",
              "The tube comes up hot: extra brightness, bloom, fringe and a little sync wobble on the open, easing off over ~0.5 s.",
              "System text types in at ~1 character every 1.5 frames behind a solid block cursor; the red dot pops when the line is done; then the cursor blinks with a short phosphor fade.",
              "In the hold a soft hum bar rolls slowly down and brightness flickers ~1 %. Hold at least 2 s.",
              "The exit is faster than the entry: the picture collapses into the bright line in ~9 frames, then the line narrows back to the opening state, so it loops."],
      never=["Saturated neon or a coloured outline glow – the core stays near-white, the colour lives in the haze.",
             "A box or border – the tube edge only ever reads as vignette.",
             "Fading the title in – it arrives with the picture opening.",
             "Heavy glitching, RGB split or jitter on settled text."],
      sizes="16:9 is the natural tube; on 9:16 stack the title on two to three lines and keep the bottom fifth empty."),
 dict(id="oscilloscope", name="Oscilloscope", family="Oscilloscope art", dark=True,
      suits="Tech, music, data, launches, any “it all clicked” moment.",
      swatch=["#030805", "#0D2216", "#46FF8C", "#D7FFF3"],
      fonts={"Share Tech Mono": ["400"]},
      look=["Screen #030805 with a faint tube-face lift (#09150E) in the middle; graticule #0D2216 of square divisions with ticks on the two centre axes, fading out toward the edges so there is never a border.",
            "The words ARE the trace: monoline geometric capitals drawn as one continuous stroke standing on the zero line, cap height ~9 % of the frame height. Readouts, if any, in small dim-green Share Tech Mono – a few words at most.",
            "Phosphor glow: an almost white core (#D7FFF3), a tight green halo (#46FF8C), a short persistence trail of the last few frames behind anything that moves, fine grain in the dark screen."],
      motion=["One continuous line for the whole piece. Every change is that line changing shape – never a cut or a swap.",
              "It opens on a scrolling sine wave that catches the trigger and locks, then folds into a slowly turning 2:3 Lissajous figure.",
              "The figure releases back into a wave and rings down to a flat line like a damped oscillation, swinging through zero once.",
              "The letters rise out of the flat line left to right, each overshooting ~10 % and settling, the persistence trail smearing beneath. Hold at least 1.5 s.",
              "Draw the trace as an SVG/canvas path; build the letters as polylines that start and end on the baseline so the beam never breaks; persistence = the same path at t−1, t−2, t−3 frames with falling opacity."],
      never=["Neon-sign glow – keep the halo tight and green, the core almost white.",
             "A box around the screen, or labels in the corners.",
             "Letters that appear from nowhere – they grow out of the line.",
             "More than one small line of readouts."],
      sizes="Any size: the beam runs off both sides of the frame like a real scope; on 9:16 use a shorter word or two stacked traces."),
 dict(id="magazine_note", name="Magazine Layout + Note", family="Editorial layout", dark=False,
      suits="Quotes, reading lists, essays, product stories – considered rather than loud.",
      swatch=["#EAEDED", "#1B1E25", "#C42E26", "#242E46"],
      fonts={"Bodoni Moda": ["400", "400i"], "Newsreader": ["400", "400i"], "La Belle Aurore": ["400"]},
      look=["Cool off-white paper (#EAEDED), near-black ink (#1B1E25), red ballpoint (#C42E26). The photo is a two-ink duotone from slate navy (#242E46) to pale grey-blue (#E2E7EC).",
            "Headline: Bodoni Moda (Regular + Italic) at ~9 % of frame height, tracking −0.03em, two lines – the second italic and indented. Body: Newsreader at ~1.4 % of frame height on generous leading, plus an italic caption. The note: La Belle Aurore, tilted about −7°.",
            "A thin rule across the top margin, the headline under it, a photo block on one side and a narrow body column on the other, caption under the photo. The note sits in the margin and an arrow crosses the gutter into the photo. Lots of white paper.",
            "Static paper grain with faint fibres, a light multiplied paper tooth over everything (ink and photo too), film grain inside the photo. No stock photo? Paint one: a dusk sea with a sun disk, torn cloud, a cloud bank and a glitter path on the water."],
      motion=["Frame one already shows the rule, the first headline line and a sliver of photo. Every line of type rises out of its own mask, 2–5 frames apart, ~10 % overshoot, soft settle.",
              "The photo opens upward like a blind while the image settles out of a gentle push, then keeps drifting very slowly.",
              "The note writes itself along the strokes of each letter at handwriting speed (~8 letters a second) with short pen lifts between words; i-dots and the full stop come last. (In the HTML engine: SVG text with a stroke-dashoffset reveal per glyph, or a mask that follows each letter.)",
              "After a beat the pen draws an arrow with a small loop, lifts, and flicks the arrowhead on in one move.",
              "Hold the last 1.5 s so the page can be read."],
      never=["Warm cream, beige or sepia paper – the paper is cool.",
             "A straight left-to-right wipe or typewriter reveal for the note.",
             "Drop shadows, page curls or frames around the photo.",
             "Fades – every element arrives through a mask or a stroke."],
      sizes="9:16: headline on top, photo and column stacked or side by side, bottom fifth bare. 16:9: photo left, column right (a spread)."),
 dict(id="blue_editorial", name="Blue Editorial", family="Editorial kinetic type", dark=True,
      suits="A bold one-line statement, a launch, a title card, a manifesto line.",
      swatch=["#2433F0", "#F4F5FA"],
      fonts={"Instrument Serif": ["400i"], "Schibsted Grotesk": ["900"]},
      look=["Electric ultramarine (#2433F0 – blue, never purple or navy), white (#F4F5FA), rules in the same white at ~55 % opacity. Nothing else; flat colour, crisp edges.",
            "Two faces only, all lowercase: huge words in Instrument Serif Italic (≈22 % of frame width per letter, tracking −0.03em), small words in Schibsted Grotesk Black (~6 % of frame height, tracking −0.045em). The contrast between huge italic and small heavy sans IS the style.",
            "A cover stack, not a grid: small kicker word over a full-width rule, a huge italic word whose ascender breaks through that rule, a small word right-aligned on a short second rule, a small word sitting on the baseline of a huge final italic word, a closing rule."],
      motion=["Frame one already shows huge letters rising through a baseline mask, 2–3 frames apart, ~10 % overshoot.",
              "Scale jump: the opening word holds huge for ~⅔ s, then snaps down to kicker size in ~8 frames with motion blur along the travel.",
              "A slanted wipe at the italic angle runs through the next word left to right, a thin white line riding its edge, collapsing as it exits.",
              "One word slides out from underneath another, as if it was tucked behind it.",
              "The last word flies in as four horizontal slices from alternating sides, lands off-register for a beat so the cut reads, then locks. Rules draw out on a fast ease. Each beat holds 8–15 frames; the finished cover holds ~1.5 s."],
      never=["Purple, navy, gradients or glow – one flat blue.",
             "A third typeface, or capitals.",
             "A modular grid, numbered labels or centred symmetry (that's Swiss – this is a cover).",
             "Fades or crossfades – words move, wipe, slice or slide."],
      sizes="9:16 is the cover; on 16:9 keep the stack in the central ~75 % of the width, big words slightly smaller."),
 dict(id="risograph", name="Risograph", family="Risograph print", dark=False,
      suits="Event promos, zines, music, playful brand moments – hand-made, not digital.",
      swatch=["#EDEFEE", "#FF48B0", "#3255A4", "#32186F"],
      fonts={"Bricolage Grotesque": ["800"]},
      look=["Cool off-white paper (#EDEFEE), fluorescent pink (#FF48B0), medium blue (#3255A4). Where they overlap you get deep violet (~#32186F) – from multiplying the inks (mix-blend-mode: multiply / canvas 'multiply'), never picked by hand.",
            "Type: Bricolage Grotesque ExtraBold capitals, tracked ~5 %, big enough to span the poster. One short word knocked out of a shape so the paper shows through.",
            "Poster layout: hero word across the top, two overlapping circles, a second word on a band of diagonal stripes, a row of dots growing left to right like a halftone ramp, wide paper margins.",
            "Each ink is its own plate: mottled density with paper-white specks and slightly ragged edges; halftone dots (~12 px cell at 1080 wide) for any tone, each ink on its own screen angle; plates a few pixels out of register so two-ink areas get a pink fringe on one side and a blue one on the other; faint paper cloud and fibre, a few stray specks."],
      motion=["Everything animates on twos (each drawing holds 2 frames). Every new drawing is a fresh print: re-roll the grain and shift the registration by a pixel or two.",
              "Shapes either stamp or slide. A stamp lands big (110–116 %) with a few degrees of tilt, undershoots ~9 % and settles over 4–5 steps. A slide comes in from off-frame on a spring with 8–12 % overshoot.",
              "Build the poster one element at a time, 4–6 frames apart, in reading order. Frame one already shows ink on paper.",
              "Second beat: a registration slip – both plates kick 20–30 px apart and spring back past register, so the two-ink word splits into a pink and a blue copy, then snaps together.",
              "Hold the finished poster at least a second on each side of the slip; a slow crawl in the stripes keeps it alive."],
      never=["Warm cream or bone paper, or more than two inks plus their overlap.",
             "Smooth 30 fps motion or motion blur – it's a stack of prints.",
             "Clean vector edges or flat digital colour without grain.",
             "Any gradient that isn't made of halftone dots."],
      sizes="Portrait poster on 9:16 (bottom fifth empty); on 16:9 run the hero word left and the circles right."),
 dict(id="swiss_grid", name="Swiss Grid", family="Swiss style", dark=False,
      suits="A bold one-line statement, a principle, a manifesto opener.",
      swatch=["#F0F0E8", "#101010", "#F03820"],
      fonts={"Public Sans": ["600", "800"]},
      look=["Paper #F0F0E8, ink #101010, signal red #F03820. Nothing else; flat colour, hard edges.",
            "Type: Public Sans ExtraBold, sentence case, tracking ~−0.05em, flush-left ragged-right. Leading equals one grid module so every baseline sits on a grid line, and the first stem of each line sits exactly on the margin. Small captions in Public Sans 600: numeral in full ink, word at ~60 %.",
            "Four equal columns inside wide side margins, rows on the same square module, thin 2 px lines edge to edge. The red field covers a block of whole cells and may bleed off the top/right. The circle is exactly one or two modules wide and sits on grid intersections. Type fills the rows under the field and overprints it."],
      motion=["The grid draws first, already mid-draw on frame one: verticals drop, horizontals sweep, ~2 frames apart, fast start and a long settle.",
              "The circle steps cell to cell along the grid like a rook – each step a crisp spring (~9 % overshoot) with real motion blur.",
              "The red field opens out of the cell where the circle stops: the cell grows, snaps across the columns, then up and down the rows; each edge overshoots its grid line and settles back onto it.",
              "Each line of type is pushed out of the left margin line along its row, 6 frames apart, overshoots ~8 % and locks flush-left. Captions drop from a grid line as each part lands. The circle winds back ~10 %, then grows into its final two-module slot.",
              "Everything settled by ~2.5 s. Hold."],
      never=["Centred type, or any edge landing between grid lines.",
             "A second accent, gradients, shadows, glow or grain.",
             "Fades – things snap, slide or grow out of a grid line.",
             "A geometric or rounded display face, or decorative corner labels."],
      sizes="Any size: derive the module from the frame width (4 columns inside the margins) and keep every element on whole cells."),
 dict(id="blueprint", name="Pencil to Blueprint", family="Technical drawing", dark=False,
      suits="Idea-to-product, process, design and engineering stories.",
      swatch=["#ECECE6", "#25262B", "#1C4C8F", "#EEF4FB"],
      fonts={"Barlow Semi Condensed": ["500", "600"]},
      look=["Paper #ECECE6 with a faint engineering grid (#7FA3C4), graphite #25262B, blueprint blue #1C4C8F, tide-line blue #143C76, ink white #EEF4FB.",
            "Type: Barlow Semi Condensed – measurements Medium with tabular figures; the label in caps SemiBold, tracking +0.07em, flush-left above a thin rule.",
            "One simple object in side view, large in the middle, standing on a ground line. The label top-left, aligned with the drawing's left edge; two or three dimensions to the side and underneath.",
            "Graphite with paper tooth: doubled, slightly bowed strokes with overshooting ends. Fine paper grain over everything, a very light mottle in the blue."],
      motion=["The sketch goes down in a real order: ground line and light construction axes, then confident outlines, joints as overshooting circles, quick hatching last. Each stroke eases in and out like a hand; the pencil is already moving on frame one.",
              "The finished sketch holds ~⅓ s. Then ink floods out from inside the drawing with an irregular wet edge and a darker tide line just inside it – fast at first, then slowing.",
              "Wherever the edge passes, graphite becomes white ink and each line springs straight. Construction strokes become dash-dot centre lines.",
              "Then the system lands: centre marks pop, extension lines grow, dimension lines draw out from their middle, arrowheads pop, numbers tick up. The label rises over a rule that draws first. Hold 1.5 s."],
      never=["A cut or crossfade from sketch to blueprint – it is one drawing, promoted.",
             "Glow on the white lines, or a gradient on the blue.",
             "A different object for the blueprint, or more than three dimensions.",
             "A handwriting font for the label, or a drawn pencil/hand on screen."],
      sizes="Any size: the object fills ~50 % of the frame height; on 9:16 put the label above the drawing and keep dimensions out of the bottom fifth."),
]

GENERAL_NEVER = ["No neon glow unless the look is built on glow.", "No particle bursts or sparkles.",
                 "No crossfades – things change shape or cut, they don't dissolve.",
                 "No bounce on everything: choose the one moment that bounces.", "No camera shake, no lens flares.",
                 "No glowing grid floors.", "No text in the corners of the frame.", "Nothing that looks like a template."]

FONT_FILES = {"Outfit": "outfit", "Plus Jakarta Sans": "plus-jakarta-sans", "Inter Tight": "inter-tight", "Syncopate": "syncopate",
              "Share Tech Mono": "share-tech-mono", "Bodoni Moda": "bodoni-moda", "Newsreader": "newsreader",
              "La Belle Aurore": "la-belle-aurore", "Instrument Serif": "instrument-serif", "Schibsted Grotesk": "schibsted-grotesk",
              "Bricolage Grotesque": "bricolage-grotesque", "Public Sans": "public-sans", "Barlow Semi Condensed": "barlow-semi-condensed"}
FONTDIR = OUT / "fonts"


def files_for(fam, weights):
    out = []
    for w in weights:
        style = "italic" if w.endswith("i") else "normal"
        num = w.rstrip("i")
        out += sorted(p.name for p in FONTDIR.glob(f"{FONT_FILES[fam]}-*-{num}-{style}.woff2"))
    return out


CSS = {}
for line in (OUT / "fonts.css").read_text(encoding="utf-8").splitlines():
    import re
    m = re.search(r"url\(fonts/([^)]+)\)", line)
    if m:
        CSS[m[1]] = line.replace("url(fonts/", "url(assets/")


def recipe(l):
    fl = [f for fam, ws in l["fonts"].items() for f in files_for(fam, ws)]
    md = [f"# Look: {l['name']} ({l['family']})", "",
          f"**Suits:** {l['suits']}", "",
          "The user picked this look in Vizavi Studio. Build the whole video in it – it is binding, like a saved style: "
          "palette, type, layout, texture, motion and the Never list. Keep the content, story and timing from the narration "
          "and the brief; adapt the layout to this project's frame size(s). Look at `look/` (three frames of the look) first.", "",
          "Build it with the **HTML engine** (canvas/SVG/DOM; see ENGINE_html.md). Rules below are written per frame size "
          "fraction, so they hold for 9:16, 16:9 and 1:1 alike.", "",
          "## The look", *[f"- {x}" for x in l["look"]], "",
          "## How it moves", *[f"- {x}" for x in l["motion"]], "",
          "## Never", *[f"- {x}" for x in l["never"]], "",
          "## Frame sizes", l["sizes"], "",
          "## Fonts (already in this project's `assets/`)", "```css", *[CSS[f] for f in fl if f in CSS], "```", "",
          "## Before you hand it over",
          "Watch the motion strips the checks make and hold each beat against “How it moves” and “Never”: those words "
          "are the fix list – name the rule a frame breaks and fix that, rather than adding effects.", ""]
    return "\n".join(md), fl


cards = []
for l in L:
    md, fl = recipe(l)
    (OUT / f"{l['id']}.md").write_text(md, encoding="utf-8")
    cards.append({k: l[k] for k in ("id", "name", "family", "suits", "swatch", "dark")} | {"fonts": fl, "font_families": [f.replace(" ", "") for f in l["fonts"]], "engine": "html"})
(OUT / "looks.json").write_text(json.dumps({"source": {"title": SOURCE[0], "url": SOURCE[1]}, "general_never": GENERAL_NEVER,
                                            "looks": cards}, indent=1, ensure_ascii=False), encoding="utf-8")
print(len(cards), "looks")
