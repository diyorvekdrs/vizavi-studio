"""Precise word timing: CTC forced alignment of the final words onto the narration with Meta's MMS
forced-alignment model (wav2vec2, 1100+ languages incl. Uzbek; license CC-BY-NC-4.0 - non-commercial).
The text is already right (script / Uzbek model); this only moves word start/end times to the exact
spoken boundaries (20 ms resolution). Falls back to the Whisper timing on any problem.
Run as a subprocess:  python -m studio.mms_align <narration> <words.tsv> [--model ID]
Prints 'LOG ...' / 'PROGRESS x' lines, rewrites words.tsv in place (timing column only)."""
import argparse, os, re, sys, warnings
from pathlib import Path
import numpy as np

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "claude" / "tools"))

MODEL = "MahmoudAshraf/mms-300m-1130-forced-aligner"
SR, HOP = 16000, 320            # wav2vec2: 20 ms per frame
APOS = "ʻʼ’‘`´"


def log(s):
    print("LOG " + s, flush=True)


def prog(x):
    print(f"PROGRESS {max(0.0, min(1.0, x)):.3f}", flush=True)


def normalize(word, vocab):
    """Uzbek Latin word -> characters the aligner knows (a-z and ')."""
    from studio.align import cyr2lat
    w = cyr2lat(word).lower()
    for a in APOS:
        w = w.replace(a, "'")
    return [c for c in w if c in vocab]


def ctc_align(logp, tokens, blank):
    """Viterbi CTC forced alignment. logp: (T, V) log-probs; tokens: list of ids (no blanks).
    Returns (state_per_frame, path_score). State s: even = blank, odd = token (s-1)//2."""
    T = logp.shape[0]
    L = len(tokens)
    S = 2 * L + 1
    if T < L:
        raise ValueError(f"audio too short for the text ({T} frames < {L} characters)")
    ext = np.full(S, blank, np.int64)
    ext[1::2] = tokens
    NEG = -1e30
    skip = np.zeros(S, bool)
    skip[2:] = (ext[2:] != blank) & (ext[2:] != ext[:-2])
    dp = np.full(S, NEG)
    dp[0] = logp[0, blank]
    if S > 1:
        dp[1] = logp[0, ext[1]]
    bp = np.zeros((T, S), np.int8)
    for t in range(1, T):
        p1 = np.empty(S); p1[0] = NEG; p1[1:] = dp[:-1]
        p2 = np.full(S, NEG); p2[2:] = dp[:-2]; p2[~skip] = NEG
        cand = np.stack([dp, p1, p2])
        arg = cand.argmax(0)
        dp = cand[arg, np.arange(S)] + logp[t, ext]
        bp[t] = arg
    s = S - 1 if S == 1 or dp[S - 1] >= dp[S - 2] else S - 2
    score = dp[s]
    states = np.empty(T, np.int64)
    for t in range(T - 1, -1, -1):
        states[t] = s
        s -= int(bp[t, s])
    return states, float(score)


def token_spans(states, L):
    """frame span (start, end) of every token from the Viterbi state path."""
    spans = [[None, None] for _ in range(L)]
    for t, s in enumerate(states):
        if s % 2 == 1:
            k = (s - 1) // 2
            if spans[k][0] is None:
                spans[k][0] = t
            spans[k][1] = t + 1
    return spans


def emissions(audio, model, torch, chunk_s=30, ctx_s=1.5):
    """log-probs for the whole file, computed in chunks with context on both sides."""
    n = len(audio)
    step, ctx = int(chunk_s * SR), int(ctx_s * SR)
    out = []
    starts = list(range(0, n, step))
    for i, s in enumerate(starts):
        a, b = max(0, s - ctx), min(n, s + step + ctx)
        x = torch.from_numpy(audio[a:b]).float()[None]
        x = (x - x.mean()) / (x.std() + 1e-7)
        with torch.inference_mode():
            lg = model(x.to(model.device)).logits[0].float()
        lp = torch.log_softmax(lg, -1).cpu().numpy()
        f0 = (s - a) // HOP
        f1 = f0 + (min(n, s + step) - s) // HOP
        out.append(lp[f0:min(f1, len(lp))])
        prog((i + 1) / len(starts) * 0.7)
    return np.concatenate(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio"); ap.add_argument("words_tsv")
    ap.add_argument("--model", default=MODEL)
    a = ap.parse_args()
    import vz_analysis as va
    lines = Path(a.words_tsv).read_text(encoding="utf-8").splitlines()
    head = [l for l in lines if not l[:1].isdigit()]
    rows = [l.split("\t") for l in lines if l[:1].isdigit()]
    if not rows:
        log("no words to align"); return
    log(f"Precise timing: loading the MMS aligner (first time downloads ~1.2 GB)…")
    import torch
    from transformers import AutoModelForCTC, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(a.model)
    model = AutoModelForCTC.from_pretrained(a.model).eval()
    if torch.cuda.is_available():
        model = model.to("cuda")
    vocab = tok.get_vocab()
    blank = vocab.get("<blank>", tok.pad_token_id if tok.pad_token_id is not None else 0)
    audio = va.decode_audio(a.audio, SR).astype(np.float32)
    log(f"aligning {len(rows)} words to {len(audio) / SR:.1f}s of audio…")
    lp = emissions(audio, model, torch)
    tokens, owner = [], []
    for i, r in enumerate(rows):
        for c in normalize(r[2], vocab):
            tokens.append(vocab[c]); owner.append(i)
    states, score = ctc_align(lp, tokens, blank)
    prog(0.9)
    spans = token_spans(states, len(tokens))
    ws = [[None, None] for _ in rows]
    for k, (f0, f1) in enumerate(spans):
        i = owner[k]
        if f0 is None:
            continue
        ws[i][0] = f0 if ws[i][0] is None else min(ws[i][0], f0)
        ws[i][1] = f1 if ws[i][1] is None else max(ws[i][1], f1)
    old = [(float(r[0]), float(r[1])) for r in rows]
    new = []
    for i, (f0, f1) in enumerate(ws):
        new.append((f0 * HOP / SR, f1 * HOP / SR) if f0 is not None else None)
    # words without alignable characters (numbers, symbols): place between neighbours
    for i in range(len(new)):
        if new[i] is None:
            prev = next((new[j][1] for j in range(i - 1, -1, -1) if new[j]), old[i][0])
            nxt = next((new[j][0] for j in range(i + 1, len(new)) if new[j]), old[i][1])
            new[i] = (prev, max(prev + 0.05, nxt - 0.01))
    diffs = np.array([abs(n_[0] - o[0]) for n_, o in zip(new, old)])
    per_frame = score / max(1, len(lp))
    log(f"precise timing: median shift vs Whisper {np.median(diffs) * 1000:.0f} ms, "
        f"max {diffs.max():.2f}s, path confidence {per_frame:.2f}/frame")
    if np.median(diffs) > 1.0 or per_frame < -2.5:
        log("⚠ precise alignment looks wrong (text and audio may not match) – keeping the Whisper timing")
        sys.exit(3)
    out = head[:1] or ["# start\tend\tword\tprob\tsource"]
    for r, (s0, e0) in zip(rows, new):
        r = list(r) + [""] * (5 - len(r))
        r[0], r[1] = f"{s0:.3f}", f"{e0:.3f}"
        out.append("\t".join(r[:5]))
    Path(a.words_tsv).write_text("\n".join(out) + "\n", encoding="utf-8")
    prog(1)
    log("precise timing applied (MMS forced alignment)")


if __name__ == "__main__":
    main()
