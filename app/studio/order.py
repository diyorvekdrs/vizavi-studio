"""Project 'order': everything the user can ask for (size, aspect variants, fps, duration source,
audio routing, captions, formats, engine, style, brand, assets) + built-in presets."""
import copy, json
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
BRANDS = APP / "brands"

SIZES = {
    "16:9 · 2K 2560×1440": (2560, 1440), "16:9 · Full HD 1920×1080": (1920, 1080), "16:9 · 4K 3840×2160": (3840, 2160),
    "9:16 · 1080×1920 (Shorts/Reels/TikTok)": (1080, 1920), "9:16 · 2K 1440×2560": (1440, 2560),
    "1:1 · 1080×1080": (1080, 1080), "4:5 · 1080×1350 (Instagram feed)": (1080, 1350),
    "21:9 · 2560×1080": (2560, 1080), "4:3 · 1440×1080": (1440, 1080), "GIF · 800×800": (800, 800),
}
EXTRA_VARIANTS = {"16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1080, 1080), "4:5": (1080, 1350)}
FPS = [24, 25, 30, 50, 60, 15, 12]
DURATION = {"narration": "Length of the narration", "music": "Length of the music", "fixed": "Fixed seconds"}
AUDIO_EXPORT = {
    "sfx": "Ambient + SFX only (no voice, no music)",
    "voice_sfx": "Voice + SFX",
    "voice_music_sfx": "Voice + music + SFX (music ducks under voice)",
    "music_sfx": "Music + SFX",
    "silent": "Silent video",
}
CAPTIONS = {"none": "No captions", "srt": "Separate .srt file", "burned": "Burned into the video",
            "burned+srt": "Burned in + .srt file"}
FORMATS = {
    "mp4_h264": "MP4 H.264 (universal)", "mp4_hevc": "MP4 H.265 (smaller)",
    "mov_prores": "MOV ProRes (editing; 4444 with alpha)", "webm": "WebM VP9 (web; alpha ok)",
    "gif": "GIF", "png_seq": "PNG sequence",
}
ENGINES = {"auto": "Claude decides", "python": "Python/GPU (realistic, 3D-ish, particles, space…)",
           "html": "HTML/Canvas/SVG (typography, UI, charts, flat motion graphics)"}
REVIEW = {"preview": "Preview first, then Claude reviews (best quality)",
          "direct": "Straight to final (fast, for simple jobs)"}
LOUDNESS = {"keep": "Keep Claude's levels", "-14": "-14 LUFS (YouTube/social)", "-16": "-16 LUFS (podcast/web)",
            "-23": "-23 LUFS (broadcast)"}
SAFE_AREA = {"none": "None", "shorts": "YouTube Shorts UI", "tiktok": "TikTok UI", "reels": "Instagram Reels UI"}
# (top, bottom, right) as a fraction of the frame kept free of text/key action. ONE table used for the brief
# Claude reads AND for the blue box in the preview, so the two can never disagree.
SAFE_BOXES = {"tiktok": (0.10, 0.22, 0.12), "shorts": (0.10, 0.20, 0.12), "reels": (0.10, 0.22, 0.10)}
LANGS = ["uz", "auto", "en", "ru", "tr", "kk", "ky", "tg", "de", "fr", "es", "ar", "zh", "ja", "ko"]
STYLES = {
    "cinematic_dark": "Dark, realistic (not toy-like), cinematic. Slow smooth camera, depth, soft light, subtle film grain.",
    "clean_minimal": "Clean minimal motion design: lots of negative space, one accent color, crisp type, eased moves.",
    "bold_social": "Bold, high-contrast, fast-reading social style: big type, punchy cuts on beats, vivid accents.",
    "documentary": "Documentary: archival textures, maps, photos with slow Ken Burns moves, restrained type.",
    "corporate": "Corporate/product: brand colors, tidy grid, UI mockups, smooth easing, confident but calm.",
    "neon_tech": "Futuristic/tech: dark background, neon glows, grids, data particles, HUD details.",
    "flat_illustration": "Flat illustration motion graphics: friendly shapes, soft palette, playful secondary motion.",
    "retro_film": "Retro film: warm grade, grain, gate weave, light leaks, vintage type.",
    "custom": "",
}


def base():
    return {
        "name": "", "preset": "Narrated explainer 16:9 (cinematic, no voice)",
        "size": [2560, 1440], "variants": [], "fps": 24,
        "duration": {"mode": "narration", "seconds": 30.0, "tail": 1.5},
        "audio": {"narration": None, "music": None, "export": "sfx", "generate_music": False,
                  "loudness": "keep", "duck_db": 10},
        "language": "uz", "captions": "none", "text_amount": "very little, only where it truly helps",
        "style_preset": "cinematic_dark", "style": "", "formats": ["mp4_h264"], "alpha": False,
        "engine": "auto", "review": "preview", "safe_area": "none", "brand": "", "purpose": "", "brief": "", "wants": "", "care": "",
        "standing_rules": "",
        "assets": [],
    }


PRESETS = {
    "Narrated explainer 16:9 (cinematic, no voice)": {},
    "YouTube video 16:9 (voice + music)": {"size": [1920, 1080], "fps": 30, "audio": {"export": "voice_music_sfx",
                                           "loudness": "-14"}, "style_preset": "clean_minimal"},
    "Shorts / Reels / TikTok 9:16": {"size": [1080, 1920], "fps": 30, "captions": "burned", "safe_area": "tiktok",
                                     "audio": {"export": "voice_music_sfx", "loudness": "-14"}, "style_preset": "bold_social",
                                     "text_amount": "captions + a few key words"},
    "Instagram feed 4:5": {"size": [1080, 1350], "fps": 30, "captions": "burned",
                           "audio": {"export": "voice_music_sfx", "loudness": "-14"}, "style_preset": "bold_social"},
    "Square 1:1": {"size": [1080, 1080], "fps": 30, "audio": {"export": "voice_music_sfx", "loudness": "-14"}},
    "Music promo (beat-synced)": {"size": [1920, 1080], "fps": 30, "duration": {"mode": "music"},
                                  "audio": {"export": "music_sfx", "loudness": "-14"}, "style_preset": "bold_social",
                                  "text_amount": "short words on the beats"},
    "Kinetic typography": {"size": [1920, 1080], "fps": 30, "engine": "html", "style_preset": "clean_minimal",
                           "audio": {"export": "voice_music_sfx", "loudness": "-14"},
                           "text_amount": "the text IS the visual: animate the spoken words"},
    "Logo sting / intro (transparent)": {"size": [1920, 1080], "fps": 60, "duration": {"mode": "fixed", "seconds": 5},
                                         "alpha": True, "formats": ["mov_prores", "webm", "mp4_h264"],
                                         "audio": {"export": "sfx"}, "review": "preview", "style_preset": "clean_minimal"},
    "Product / UI demo": {"size": [1920, 1080], "fps": 60, "engine": "html", "style_preset": "corporate",
                          "audio": {"export": "voice_music_sfx", "loudness": "-14"}},
    "Data visualization": {"size": [1920, 1080], "fps": 30, "engine": "html", "style_preset": "clean_minimal",
                           "audio": {"export": "voice_music_sfx", "loudness": "-14"},
                           "text_amount": "labels, values and a title per chart"},
    "4K cinematic 16:9": {"size": [3840, 2160], "fps": 24},
    "GIF / sticker": {"size": [800, 800], "fps": 15, "duration": {"mode": "fixed", "seconds": 4},
                      "formats": ["gif", "mp4_h264"], "audio": {"export": "silent"}, "engine": "html",
                      "style_preset": "flat_illustration"},
    "Custom": {},
}


def deep_update(d, u):
    for k, v in u.items():
        if isinstance(v, dict) and isinstance(d.get(k), dict):
            deep_update(d[k], v)
        else:
            d[k] = copy.deepcopy(v)
    return d


def from_preset(name, user_presets=None):
    o = base()
    allp = dict(PRESETS)
    allp.update(user_presets or {})
    deep_update(o, allp.get(name, {}))
    o["preset"] = name
    return o


def _to_float(x, default):
    try:
        v = float(x)
        return v if v == v and abs(v) != float("inf") else default
    except (TypeError, ValueError):
        return default


def normalize(o):
    """fill missing keys (old projects / hand-edited orders) and make the numbers usable.
    Sizes become whole, even numbers (H.264 needs that); out-of-range values are kept so problems() can say so."""
    o = deep_update(base(), o or {})
    if o.get("brief") and not o.get("wants"):   # v2.0 field name
        o["wants"] = o["brief"]
    dflt = base()["size"]
    size = o.get("size") if isinstance(o.get("size"), (list, tuple)) and len(o["size"]) >= 2 else dflt
    w, h = (int(round(_to_float(v, d))) for v, d in zip(size[:2], dflt))
    o["size"] = [even(w) if w > 0 else 0, even(h) if h > 0 else 0]
    o["fps"] = _to_float(o.get("fps"), 24.0)
    if o["fps"] == int(o["fps"]):
        o["fps"] = int(o["fps"])
    d = o["duration"] if isinstance(o.get("duration"), dict) else {}
    d["seconds"] = _to_float(d.get("seconds"), 30.0)
    d["tail"] = _to_float(d.get("tail"), 1.5)
    o["duration"] = d
    return o


def legacy_order():
    return from_preset("Narrated explainer 16:9 (cinematic, no voice)")


def even(x):
    return max(2, int(round(x / 2)) * 2)


def variants(o):
    w, h = o["size"]
    out = [{"id": aspect_id(w, h), "w": w, "h": h, "main": True}]
    for v in o.get("variants", []):
        vw, vh = EXTRA_VARIANTS.get(v, (None, None)) if isinstance(v, str) else v
        if vw and (vw, vh) != (w, h) and abs(vw / vh - w / h) > 0.01:
            out.append({"id": aspect_id(vw, vh), "w": vw, "h": vh, "main": False})
    return out


def aspect_id(w, h):
    from math import gcd
    g = gcd(w, h)
    a, b = w // g, h // g
    known = {(16, 9): "16x9", (9, 16): "9x16", (1, 1): "1x1", (4, 5): "4x5", (64, 27): "21x9", (4, 3): "4x3"}
    return known.get((a, b), f"{w}x{h}")


def preview_size(w, h, long_side=960):
    s = long_side / max(w, h)
    return even(w * s), even(h * s)


def needs_narration(o):
    return o["duration"]["mode"] == "narration" or o["audio"]["export"] in ("voice_sfx", "voice_music_sfx") \
        or o["captions"] != "none"


def problems(o, have_narration, have_music):
    p = []
    w, h = o["size"]
    if not (64 <= w <= 8192 and 64 <= h <= 8192):
        p.append(f"Size {w}×{h} is not usable: width and height must each be between 64 and 8192.")
    if not (1 <= o["fps"] <= 120):
        p.append("Frame rate must be between 1 and 120.")
    if o["duration"]["mode"] == "fixed" and not (0.5 <= o["duration"]["seconds"] <= 3600):
        p.append("Fixed length must be between 0.5 and 3600 seconds.")
    if not (0 <= o["duration"]["tail"] <= 30):
        p.append("The calm ending after the voice must be between 0 and 30 seconds.")
    if str(o["audio"].get("loudness", "keep")) not in LOUDNESS:
        p.append("Unknown loudness setting.")
    if o["duration"]["mode"] == "narration" and not have_narration:
        p.append("Duration follows the narration, but no narration file was given.")
    if o["duration"]["mode"] == "music" and not have_music:
        p.append("Duration follows the music, but no music file was given.")
    if o["audio"]["export"] in ("voice_sfx", "voice_music_sfx") and not have_narration:
        p.append("Audio export includes the voice, but no narration file was given.")
    if o["captions"] != "none" and not have_narration:
        p.append("Captions need a narration file.")
    if o["alpha"] and not set(o["formats"]) & {"mov_prores", "webm", "png_seq"}:
        p.append("Transparent background needs MOV ProRes, WebM or PNG sequence.")
    if not o["formats"]:
        p.append("Choose at least one output format.")
    return p


def brand_info(name):
    d = BRANDS / name
    if not name or not d.exists():
        return None, []
    info = {}
    try:
        info = json.loads((d / "brand.json").read_text(encoding="utf-8"))
    except Exception:
        pass
    files = [f for f in sorted(d.iterdir()) if f.is_file() and f.name != "brand.json"]
    return info, files


def list_brands():
    return sorted(d.name for d in BRANDS.iterdir() if d.is_dir() and not d.name.startswith("_")) if BRANDS.exists() else []


def brief_md(o, words=None, music=None, assets=None):
    """the exact spec Claude must follow, generated from the order."""
    vs = variants(o)
    A = o["audio"]
    dm = o["duration"]
    dur = {"narration": f"narration length + {dm.get('tail', 1.5)} s calm ending",
           "music": "music length (end exactly with the music)",
           "fixed": f"exactly {dm.get('seconds')} s"}[dm["mode"]]
    L = [f"# Brief: {o['name']}", ""]
    care = (o.get("care") or "").strip()
    rules = (o.get("standing_rules") or "").strip()
    if care or rules:
        L += ["## Take care of (binding – never get these wrong)"]
        if care:
            L += [care]
        if rules:
            L += ["", "Standing rules (the user's rules for every project):", rules]
        L += [""]
    if (o.get("wants") or "").strip():
        L += ["## What I want (the user's vision – realize it)", o["wants"].strip(), ""]
    L += ["## Spec (exact, from the user's order)",
         f"- Preset: {o['preset']}",
         f"- Main size: {vs[0]['w']}×{vs[0]['h']} ({vs[0]['id']}), {o['fps']} fps"]
    if len(vs) > 1:
        L.append("- Also delivered in: " + ", ".join(f"{v['w']}×{v['h']} ({v['id']})" for v in vs[1:]) +
                 " → the layout MUST be responsive (same film, re-composed per aspect; see RULES)")
    L += [f"- Duration: {dur}",
          f"- Transparent background (alpha): {'YES - render RGBA, no background fill' if o['alpha'] else 'no'}",
          f"- Engine: {ENGINES[o['engine']]}",
          f"- Audio in the exported file: {AUDIO_EXPORT[A['export']]}"]
    if A.get("narration"):
        L.append("- Narration given: input/narration.* (word timings in input/words.tsv)" +
                 (" - it is NOT in the export: your mix.wav is only ambient/SFX" if A["export"] in ("sfx", "music_sfx", "silent")
                  else " - the app mixes it into the export; leave room for it"))
    if A.get("music"):
        L.append("- Music given: input/music.* (beats in input/beats.tsv) - the app mixes it" +
                 (f", ducked {A.get('duck_db', 10)} dB under the voice" if "voice" in A["export"] else "") +
                 "; your mix.wav = SFX only, sync cuts/accents to the beats")
    elif A.get("generate_music"):
        L.append("- No music file, but the user wants music: synthesize a fitting, unobtrusive music bed in audio.py")
    if A["export"] == "silent":
        L.append("- Silent export: still write mix.wav (silence is fine)")
    L += [f"- Loudness of the export: {LOUDNESS.get(str(A.get('loudness', 'keep')), A.get('loudness'))} (the app normalizes)",
          f"- Captions: {CAPTIONS[o['captions']]}" + (" → draw them yourself from input/captions.srt / words.tsv, "
                                                      "readable, in the safe area" if o["captions"].startswith("burned") else ""),
          f"- On-screen text: {o['text_amount']}",
          f"- Output formats (the app encodes them): {', '.join(FORMATS[f] for f in o['formats'])}"]
    if o.get("safe_area", "none") != "none":
        t_, b_, r_ = SAFE_BOXES.get(o["safe_area"], (0.10, 0.22, 0.12))
        L.append(f"- Keep text/key action out of the {SAFE_AREA[o['safe_area']]} zones "
                 f"(top {t_ * 100:.0f}%, bottom {b_ * 100:.0f}%, right {r_ * 100:.0f}%)")
    L += ["", "## Style", STYLES.get(o["style_preset"], ""), o.get("style", "").strip()]
    if o.get("style_ref"):
        L += [f"**Match the user's saved style “{o.get('style_ref_name') or o['style_ref']}”** – read "
              "style_ref/STYLE.md and look at style_ref/stills/ first; it overrides the style preset above."]
    if o.get("purpose", "").strip():
        L += ["", "## Purpose / topic", o["purpose"].strip()]

    if o.get("brand"):
        info, files = brand_info(o["brand"])
        L += ["", f"## Brand: {o['brand']}", "Files in input/brand/: " + ", ".join(f.name for f in files)]
        if info:
            L.append("```json\n" + json.dumps(info, indent=1, ensure_ascii=False) + "\n```")
    if assets:
        L += ["", "## User assets (input/assets/, available at render time as assets/<name>)"]
        L += [f"- {a}" for a in assets]
    return "\n".join(x for x in L if x is not None) + "\n"
