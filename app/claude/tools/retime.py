"""Puts YOUR clean transcript on the audio's word timing (Claude side).
  python tools/retime.py                      # reads episode/transcript_clean.txt
  python tools/retime.py path/to/clean.txt
Timing source: input/words.tsv (the app's best word timing). Writes episode/words.tsv (+ episode/captions.srt).
On the user's PC the app then refines these times precisely (MMS forced alignment) before rendering."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from vz_align import align  # noqa: E402


def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def make_srt(words, max_chars=32, max_dur=2.6, gap=0.6):
    cues, cur = [], []
    for w in words:
        if cur and (len(" ".join(x["w"] for x in cur + [w])) > max_chars or w["e"] - cur[0]["s"] > max_dur
                    or w["s"] - cur[-1]["e"] > gap or cur[-1]["w"].rstrip()[-1:] in ".!?…"):
            cues.append(cur); cur = []
        cur.append(w)
    if cur:
        cues.append(cur)
    out = []
    for k, c in enumerate(cues, 1):
        end = c[-1]["e"] + 0.08
        if k < len(cues):
            end = min(end, cues[k][0]["s"] - 0.01)
        out += [str(k), f"{srt_time(c[0]['s'])} --> {srt_time(end)}", " ".join(x["w"] for x in c), ""]
    return "\n".join(out)


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "episode" / "transcript_clean.txt"
    text = src.read_text(encoding="utf-8").strip()
    rows = [l.split("\t") for l in (ROOT / "input" / "words.tsv").read_text(encoding="utf-8").splitlines() if l[:1].isdigit()]
    timed = [{"w": r[2], "s": float(r[0]), "e": float(r[1]), "p": float(r[3]) if len(r) > 3 else 1.0} for r in rows]
    out, rep = align(timed, text, trust_text=True)
    if not out:
        print("nothing aligned - is the transcript empty?"); return 1
    ep = ROOT / "episode"
    lines = ["# start\tend\tword\tprob\tsource   (Claude's clean transcript on the audio timing)"]
    lines += [f"{w['s']:.3f}\t{w['e']:.3f}\t{w['w']}\t{w.get('p', 1):.2f}\tclaude" for w in out]
    (ep / "words.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (ep / "captions.srt").write_text(make_srt(out), encoding="utf-8")
    est = sum(1 for w in out if w["src"] == "script~")
    print(f"retimed {len(out)} words ({rep['exact']} identical to the timing source, {rep['corrected'] + 0} "
          f"re-spelled, {est} with estimated timing) -> episode/words.tsv, episode/captions.srt")
    print(f"span {out[0]['s']:.2f}s - {out[-1]['e']:.2f}s. Use episode/words.tsv for SCENES/CUES and captions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
