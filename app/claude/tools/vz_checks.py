"""Ranked checks: what the text on screen does (cut off, under the app's buttons, too small, too faint, too brief,
wrong alphabet, likely misspelled) and a rank for every automatic finding.

Ranks:  P0 the video is broken (wrong length/size, missing sound)   - fix before anything else
        P1 a viewer would stop watching or misread it here           - fix in this pass
        P2 it costs attention (small/faint/brief text, mix, sync)    - fix if the pass has room
        P3 finishing (a few frames off a beat, close to an edge)     - fix last, or leave

Text samples come from the renderer (`vzrender.py ... --textprobe text.json`): every 0.25 s the html engine reports
each visible text block (VZ.textLayout() in vz.js), the python engine whatever film.py's text()/captions() drew
(film.TEXT_LOG); the renderer measures each item's contrast against the frame. Each item: {k: block id, text, box: [x0, y0, x1, y1] px, px: font size px, color: [r, g, b] | None,
op: opacity, cap: caption?, clip: cut by its container?, contrast: measured against the pixels behind it}."""
import difflib
import math
import re
import unicodedata

READ_S_PER_WORD = 0.3
READ_MIN_S = 1.0
MIN_TEXT_FRAC = 0.03            # of the short side; ENGINE_html says body text >= 3.5 %
MIN_TEXT_FRAC_VERTICAL = 0.035
CONTRAST_WEAK, CONTRAST_BAD = 3.0, 2.0
CYR = re.compile(r"[Ѐ-ӿ]")
WORD = re.compile(r"[^\W\d_]+(?:[ʻʼ'‘’`][^\W\d_]+)*", re.UNICODE)

RANK_RULES = [            # (rank, pattern) for the plain-text flags of the other checks; first match wins
    ("P0", r"^video has \d+ frames|^video has <3|^duration .* differs|^project size|^alpha is|several aspect"
           r"|shorter than narration|^mix\.wav length"),
    ("P1", r"sudden jump|brightness flicker|blown-out|true peak|SFX as loud as voice|near-black"),
    ("P2", r"^static|bed/SFX only|^cue '|^camera |SCENES missing"),
    ("P3", r"off the nearest beat"),
]


def rank_flag(text):
    for rank, pat in RANK_RULES:
        if re.search(pat, text):
            return rank
    return "P2"


def _norm(w):
    w = unicodedata.normalize("NFC", w.lower())
    return re.sub(r"[ʻʼ'‘’`]", "'", w)


def _words(s):
    return [_norm(w) for w in WORD.findall(s or "")]


def _fmt(t):
    return f"{t:.2f}s"


def _short(s, n=48):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[:n - 1] + "…"


def analyze_text(samples, W, H, step=0.25, safe=None, vocab_text="", latin_only=False, min_run=2):
    """samples: [{"t": seconds, "items": [...]}, ...] sorted by t. safe: (top, bottom, right) fractions of the
    frame kept free for a platform's buttons, or None. min_run: how many samples in a row make a position a problem
    rather than an animation passing through (1 when the samples are seconds apart). Returns (issues, summary)."""
    issues = []
    short = min(W, H)
    vertical = H > W
    min_px = (MIN_TEXT_FRAC_VERTICAL if vertical else MIN_TEXT_FRAC) * short
    zones = []
    if safe:
        top, bottom, right = safe
        zones = [("top", (0, 0, W, top * H)), ("bottom", (0, H * (1 - bottom), W, H)),
                 ("right", (W * (1 - right), 0, W, H))]
        if vertical:
            zones.append(("left", (0, 0, 0.05 * W, H)))
    edge = 0.02 * short

    # runs: one block (k) visible in consecutive samples
    runs, open_ = [], {}
    prev_t = None
    for s in samples:
        t = float(s["t"])
        seen = set()
        for it in s.get("items") or []:
            k = str(it.get("k") or it.get("text"))
            seen.add(k)
            r = open_.get(k)
            if r is None or (prev_t is not None and r["last"] < prev_t - 1e-6):
                r = {"k": k, "first": t, "last": t, "items": []}
                open_[k] = r
                runs.append(r)
            r["last"] = t
            r["items"].append((t, it))
        prev_t = t
        for k in [k for k, r in open_.items() if k not in seen]:
            del open_[k]

    def overlap(b, z):
        x0, y0, x1, y1 = max(b[0], z[0]), max(b[1], z[1]), min(b[2], z[2]), min(b[3], z[3])
        return max(0, x1 - x0) * max(0, y1 - y0)

    def persistent(tis, pred, need=min_run):
        """(start, end) of the longest stretch of consecutive samples where pred holds, if it lasts `need`
        samples - an entrance or exit animation passes through a bad position only briefly"""
        best, start, n = None, None, 0
        for t, it in tis:
            if pred(it):
                n += 1
                start = t if n == 1 else start
                if n >= need and (best is None or n > best[2]):
                    best = (start, t, n)
            else:
                n = 0
        return best[:2] if best else None

    vocab = set(_words(vocab_text))
    vocab_cyr = bool(CYR.search(vocab_text or ""))
    spelled = set()
    for r in runs:
        tis = r["items"]
        longest = max((it.get("text") or "" for _, it in tis), key=len)
        label = f"“{_short(longest)}”"
        cap = any(it.get("cap") for _, it in tis)
        dur = r["last"] - r["first"] + step

        def box(it):
            return it.get("box") or [0, 0, 0, 0]

        off = hit = persistent(tis, lambda it: box(it)[0] < -edge / 2 or box(it)[1] < -edge / 2
                               or box(it)[2] > W + edge / 2 or box(it)[3] > H + edge / 2)
        if hit:
            issues.append({"rank": "P1", "kind": "text_off_frame", "t0": hit[0], "t1": hit[1],
                           "text": f"text runs off the frame {_fmt(hit[0])}–{_fmt(hit[1])}: {label}"})
        hit = persistent(tis, lambda it: bool(it.get("clip")))
        if hit:
            issues.append({"rank": "P1", "kind": "text_clipped", "t0": hit[0], "t1": hit[1],
                           "text": f"text cut off by its box {_fmt(hit[0])}–{_fmt(hit[1])}: {label}"})
        for zn, z in zones:
            def in_zone(it, z=z):
                b = box(it)
                a = max(1.0, (b[2] - b[0]) * (b[3] - b[1]))
                return overlap(b, z) / a > 0.15
            hit = persistent(tis, in_zone)
            if hit:
                issues.append({"rank": "P1", "kind": "text_safe_zone", "t0": hit[0], "t1": hit[1],
                               "text": f"text in the app's {zn} button zone {_fmt(hit[0])}–{_fmt(hit[1])}: {label}"})
                break
        if not zones and not off:
            hit = persistent(tis, lambda it: (box(it)[0] < edge or box(it)[1] < edge or box(it)[2] > W - edge
                                              or box(it)[3] > H - edge) and box(it)[2] > 0 and box(it)[3] > 0
                             and box(it)[0] < W and box(it)[1] < H, need=min_run + 1)
            if hit:
                issues.append({"rank": "P3", "kind": "text_edge", "t0": hit[0], "t1": hit[1],
                               "text": f"text touches the frame edge {_fmt(hit[0])}–{_fmt(hit[1])}: {label}"})
        px = max(float(it.get("px") or 0) for _, it in tis)
        if 0 < px < min_px and len(tis) >= min_run:
            rank = "P1" if px < 0.6 * min_px else "P2"
            issues.append({"rank": rank, "kind": "text_small", "t0": r["first"], "t1": r["last"],
                           "text": f"text small: {px:.0f} px (want ≥ {min_px:.0f} px at this size) at "
                                   f"{_fmt(r['first'])}: {label}"})
        cs = sorted(float(it["contrast"]) for _, it in tis if it.get("contrast"))
        if cs:
            med = cs[len(cs) // 2]
            if med < CONTRAST_WEAK:
                issues.append({"rank": "P1" if med < CONTRAST_BAD else "P2", "kind": "text_contrast",
                               "t0": r["first"], "t1": r["last"],
                               "text": f"text hard to read against what's behind it (contrast {med:.1f}:1, want ≥ 3:1) "
                                       f"at {_fmt(r['first'])}: {label}"})
        nw = len(_words(longest))
        need = max(READ_MIN_S, READ_S_PER_WORD * nw)
        ends_video = samples and r["last"] >= float(samples[-1]["t"]) - 1e-6
        if not cap and nw and min_run > 1 and dur + 1e-6 < need - step and not ends_video:
            issues.append({"rank": "P2", "kind": "text_brief", "t0": r["first"], "t1": r["last"],
                           "text": f"text on screen only about {math.ceil(dur * 10) / 10:.1f}s ({nw} word{'s' if nw != 1 else ''}, needs "
                                   f"{need:.1f}s to read) at {_fmt(r['first'])}: {label}"})
        if CYR.search(longest) and (latin_only or (vocab and not vocab_cyr)):
            issues.append({"rank": "P1" if latin_only else "P2", "kind": "text_cyrillic", "t0": r["first"],
                           "t1": r["last"], "text": f"Cyrillic letters on screen at {_fmt(r['first'])}"
                                                    f"{' (rule: Latin only)' if latin_only else ''}: {label}"})
        if vocab:
            for w in _words(longest):
                if len(w) < 4 or w in vocab or w in spelled:
                    continue
                close = difflib.get_close_matches(w, vocab, n=1, cutoff=0.82)
                if close and close[0] != w:
                    spelled.add(w)
                    issues.append({"rank": "P2", "kind": "text_spelling", "t0": r["first"], "t1": r["last"],
                                   "text": f"possible misspelling on screen at {_fmt(r['first'])}: “{w}” – the "
                                           f"script/transcript has “{close[0]}”"})
    summary = {"blocks": len(runs), "samples": len(samples), "step": step,
               "min_text_px": round(min_px), "safe_zones": [z[0] for z in zones]}
    return issues, summary


def ranked(flags, text_issues=()):
    """every finding as {rank, text, kind?, t0?}, most severe first"""
    out = [{"rank": rank_flag(f), "text": f, "kind": "check"} for f in flags]
    out += [dict(i) for i in text_issues]
    order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    return sorted(out, key=lambda i: (order.get(i["rank"], 2), i.get("t0") or 0))


def counts(issues):
    c = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    for i in issues:
        c[i["rank"]] = c.get(i["rank"], 0) + 1
    return c


def report_md(issues, summary=None, engine=""):
    md = []
    c = counts(issues)
    md.append(f"P0 {c['P0']} · P1 {c['P1']} · P2 {c['P2']} · P3 {c['P3']}  "
              "(P0 broken · P1 viewer leaves/misreads · P2 costs attention · P3 finishing)")
    if summary is not None:
        md.append(f"- text checked: {summary.get('blocks', 0)} text blocks in {summary.get('samples', 0)} samples "
                  f"(every {summary.get('step', 0.25)} s); smallest comfortable size here {summary.get('min_text_px')} px"
                  + (f"; button zones: {', '.join(summary['safe_zones'])}" if summary.get("safe_zones") else ""))
    elif engine:
        md.append("- text not checked" + (" (python engine: draw on-screen text with text()/captions() so it is "
                                            "reported)" if engine == "python" else ""))
    return md
