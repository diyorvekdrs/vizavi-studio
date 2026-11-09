"""Script ↔ audio alignment. Whisper gives good TIMING but makes spelling mistakes (esp. Uzbek);
the author's script has the right SPELLING. We align the script to Whisper's words (fuzzy, letter level)
and keep: script words + audio times. Where the narrator really said something else, the audio wins
and the place is reported. Also: Uzbek Cyrillic → Latin, apostrophe normalization."""
import re
from difflib import SequenceMatcher

CYR = {"а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j", "з": "z", "и": "i",
       "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
       "у": "u", "ф": "f", "х": "x", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "ʼ", "ы": "i", "ь": "",
       "э": "e", "ю": "yu", "я": "ya", "ў": "oʻ", "қ": "q", "ғ": "gʻ", "ҳ": "h"}
APOS = "ʻʼ’‘`´'"


def has_cyrillic(s):
    return bool(re.search(r"[Ѐ-ӿ]", s))


def cyr2lat(s):
    out = []
    for i, ch in enumerate(s):
        lo = ch.lower()
        if lo == "е" and (i == 0 or not s[i - 1].isalpha()):
            t = "ye"                                   # word-initial е -> ye
        else:
            t = CYR.get(lo)
        if t is None:
            out.append(ch)
        else:
            out.append(t.capitalize() if ch.isupper() and t else t)
    return "".join(out)


def norm(t):
    t = cyr2lat(t).lower()
    for a in APOS:
        t = t.replace(a, "'")
    return re.sub(r"[^\w']", "", t)


def sim(a, b):
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def apostrophe_style(script):
    """the apostrophe the author uses in oʻ/gʻ (so Whisper's words can be written the same way)."""
    m = re.findall(r"[oOgG]([ʻʼ’‘`'])", script or "")
    return max(set(m), key=m.count) if m else "ʻ"


def fix_apostrophes(word, style):
    return re.sub(r"([oOgG])[ʻʼ’‘`']", lambda m: m[1] + style, word)


def align(words, script, trust_text=False):
    """words: [{'w','s','e','p'}] from Whisper; script: text.
    Returns (aligned_words, report) - aligned words have 'src': script | audio | script~ (timing estimated).
    trust_text=True: the text is the better transcript (Uzbek model) - its words are always kept; the audio
    words only lend their timing."""
    st = script.split()
    sn = [norm(x) for x in st]
    an = [norm(w["w"]) for w in words]
    n, m = len(st), len(words)
    GAP = -0.6
    # Needleman-Wunsch with fuzzy letter similarity
    S = [[0.0] * (m + 1) for _ in range(n + 1)]
    B = [[0] * (m + 1) for _ in range(n + 1)]   # 1 diag, 2 up (script only), 3 left (audio only)
    for i in range(1, n + 1):
        S[i][0], B[i][0] = S[i - 1][0] + GAP, 2
    for j in range(1, m + 1):
        S[0][j], B[0][j] = S[0][j - 1] + GAP, 3
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            r = sim(sn[i - 1], an[j - 1])
            d = S[i - 1][j - 1] + (2 * r - 0.8)          # good match > 0, poor match < 0
            u, l = S[i - 1][j] + GAP, S[i][j - 1] + GAP
            best = max(d, u, l)
            S[i][j], B[i][j] = best, (1 if best == d else 2 if best == u else 3)
    pairs, i, j = [], n, m
    while i > 0 or j > 0:
        b = B[i][j] if i > 0 and j > 0 else (2 if i > 0 else 3)
        if b == 1:
            pairs.append((i - 1, j - 1)); i -= 1; j -= 1
        elif b == 2:
            pairs.append((i - 1, None)); i -= 1
        else:
            pairs.append((None, j - 1)); j -= 1
    pairs.reverse()

    # group pairs; absorb split/merged words (Whisper "milyard lab" = script "milliardlab", and vice versa)
    J = lambda xs, arr: "".join(arr[x] for x in xs)
    groups = []
    for si, aj in pairs:
        groups.append(([si] if si is not None else [], [aj] if aj is not None else []))
    merged = []
    for g in groups:
        if merged and merged[-1][0] and merged[-1][1]:
            ps, pa = merged[-1]
            if not g[0] and g[1] and g[1][0] == pa[-1] + 1 and sim(J(ps, sn), J(pa + g[1], an)) > sim(J(ps, sn), J(pa, an)) + 0.05:
                merged[-1] = (ps, pa + g[1]); continue
            if g[0] and not g[1] and g[0][0] == ps[-1] + 1 and sim(J(ps + g[0], sn), J(pa, an)) > sim(J(ps, sn), J(pa, an)) + 0.05:
                merged[-1] = (ps + g[0], pa); continue
        if g[0] and g[1] and merged and not merged[-1][0] and merged[-1][1] and merged[-1][1][-1] == g[1][0] - 1:
            pa = merged[-1][1]
            if sim(J(g[0], sn), J(pa + g[1], an)) > sim(J(g[0], sn), J(g[1], an)) + 0.05:
                merged[-1] = (g[0], pa + g[1]); continue
        merged.append(g)

    ANCHOR, RUN = 0.7, 0.7
    out, rep = [], {"script_words": n, "audio_words": m, "exact": 0, "corrected": 0, "audio_only": [],
                    "not_spoken": [], "changed": []}
    style = apostrophe_style(script)
    is_anchor = lambda g: g[0] and g[1] and sim(J(g[0], sn), J(g[1], an)) >= ANCHOR

    def emit_script(sidx, aidx, p=None):
        t0, t1 = words[aidx[0]]["s"], words[aidx[-1]]["e"]
        for q, x in enumerate(sidx):
            if len(sidx) == 1:
                a_, b_ = t0, t1
            else:
                a_, b_ = t0 + (t1 - t0) * q / len(sidx), t0 + (t1 - t0) * (q + 1) / len(sidx) - 0.02
            out.append({"w": st[x], "s": round(a_, 3), "e": round(b_, 3),
                        "p": p if p is not None else min(words[y].get("p", 1.0) for y in aidx),
                        "src": "script" if len(sidx) == 1 and len(aidx) == 1 else "script~"})

    def emit_audio(aidx):
        for x in aidx:
            w = words[x]
            out.append({"w": fix_apostrophes(cyr2lat(w["w"]), style), "s": w["s"], "e": w["e"],
                        "p": w.get("p", 1.0), "src": "audio"})

    k = 0
    while k < len(merged):
        g = merged[k]
        if is_anchor(g):
            emit_script(g[0], g[1])
            exact = len(g[0]) == 1 and len(g[1]) == 1 and sn[g[0][0]] == an[g[1][0]]
            rep["exact" if exact else "corrected"] += len(g[0])
            k += 1
            continue
        run = []
        while k < len(merged) and not is_anchor(merged[k]):
            run.append(merged[k]); k += 1
        sidx = [x for g_ in run for x in g_[0]]
        aidx = [x for g_ in run for x in g_[1]]
        stext = " ".join(st[x] for x in sidx)
        atext = " ".join(cyr2lat(words[x]["w"]) for x in aidx)
        if trust_text and sidx:
            if aidx:
                emit_script(sidx, aidx, p=0.6)
            else:   # no recognized audio words here: spread between the neighbours
                t0 = out[-1]["e"] + 0.02 if out else 0.0
                nxt = next((words[g_[1][0]]["s"] for g_ in merged[k:] if g_[1]), t0 + 0.4 * len(sidx))
                t1 = max(t0 + 0.15 * len(sidx), nxt - 0.02)
                for q, x in enumerate(sidx):
                    out.append({"w": st[x], "s": round(t0 + (t1 - t0) * q / len(sidx), 3),
                                "e": round(t0 + (t1 - t0) * (q + 1) / len(sidx) - 0.02, 3), "p": 0.5, "src": "script~"})
            rep["corrected"] += len(sidx)
        elif trust_text:
            pass    # recognizer noise with no counterpart in the better text
        elif sidx and aidx:
            if sim(J(sidx, sn), J(aidx, an)) >= RUN:      # same words, badly recognized
                emit_script(sidx, aidx, p=0.8)
                rep["corrected"] += len(sidx)
            else:                                          # the narrator said something else: audio wins
                emit_audio(aidx)
                rep["changed"].append((words[aidx[0]]["s"], stext, atext))
        elif aidx:
            emit_audio(aidx)
            rep["audio_only"].append((words[aidx[0]]["s"], atext))
        elif sidx:
            rep["not_spoken"].append((out[-1]["e"] if out else 0.0, stext))
    return out, rep


def clean_transcript(words, script=""):
    """no script: Cyrillic -> Latin, consistent apostrophes."""
    style = apostrophe_style(script)
    return [dict(w, w=fix_apostrophes(cyr2lat(w["w"]), style), src="audio") for w in words]
