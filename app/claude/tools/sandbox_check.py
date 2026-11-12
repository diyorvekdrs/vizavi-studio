"""Quick sandbox check for a project (Claude side), python or html engine. Renders a few stills
(python engine on the strict fake GPU, html engine in headless Chromium), makes labelled contact
sheets, checks the spec against vizavi.json, the text on screen (cut off, in the app's button zones, too
small, too faint, too brief, wrong alphabet, likely misspelled - the same ranked checks the app runs on the
preview), camera smoothness and the sound. Never renders the full video.
usage (from the package root):
  python tools/sandbox_check.py episode                       # every 4 s + scene boundaries + other aspects
  python tools/sandbox_check.py episode --every 2 --width 640
  python tools/sandbox_check.py episode --times 12.5,31.2 --no-audio --no-variants
  python tools/sandbox_check.py episode --scene hook          # one scene: stills + a 6 fps motion strip of it
  python tools/sandbox_check.py episode --strip 12.0-14.5     # only a motion strip of that stretch
Outputs: check/sheet_XX.jpg, check/strip_<scene>.jpg (consecutive frames at 6 fps: judge motion, timing and
easing - one row = one second), check/variant_<id>.jpg, check/audio_plot.png, check/report.txt
On the user's PC (agent mode) add --real: the real GPU instead of the strict fake one."""
import argparse, json, os, shutil, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vz_analysis as va  # noqa: E402
import vz_checks as vc  # noqa: E402


def even(x):
    return max(2, int(round(x / 2)) * 2)


def mirror_runtime(ep):
    """what the app puts next to the project at render time"""
    for f in list((ROOT / "kit").glob("*.py")) + [ROOT / "kit" / "vz.js"]:
        if f.exists():
            shutil.copy(f, ep / f.name)
    for name, src in (("fonts", ROOT / "fonts"), ("assets", ROOT / "input" / "assets"), ("brand", ROOT / "input" / "brand")):
        if src.exists() and not (ep / name).exists():
            shutil.copytree(src, ep / name)
    (ep / "assets").mkdir(exist_ok=True)
    inp = ep / "input"
    inp.mkdir(exist_ok=True)
    for f in (ROOT / "input").glob("*"):
        if f.is_file() and (f.name.startswith(("narration.", "music.")) or f.name in ("words.tsv", "beats.tsv", "captions.srt")):
            shutil.copy(f, inp / f.name)
    for f in ("words.tsv", "captions.srt"):      # Claude's corrected transcript wins (the app does the same)
        if (ep / f).exists():
            shutil.copy(ep / f, inp / f)


def motion_notes(tiles, frames, fps, h):
    """hints from consecutive frames: nothing moves, a jump between two frames, a move that stops dead"""
    import numpy as np
    g = [np.asarray(t.crop((0, 0, t.width, h)).convert("L").resize((96, max(8, int(96 * h / t.width)))), np.float32)
         for t in tiles]
    d = np.array([float(np.abs(b - a).mean()) for a, b in zip(g, g[1:])])
    if not len(d):
        return []
    med, mx, k = float(np.median(d)), float(d.max()), int(d.argmax())
    out = [f"motion per step: typical {med:.1f}, largest {mx:.1f} (0-255 scale)"]
    if mx < 0.4:
        out.append("WARNING: nothing visibly moves here - intended hold? (a held frame needs a reason)")
    elif mx > 2 and mx > 3 * max(med, 0.3):
        t = frames[k + 1] / fps
        out.append(f"WARNING: uneven motion - a jump at {t:.2f}s ({mx:.1f} vs typical {med:.1f}); a pop, a missing "
                   f"ease or a cut inside the scene?")
    stops = [i for i in range(1, len(d)) if d[i - 1] > 1.5 and d[i] < 0.08 * d[i - 1]]
    if stops:
        out.append(f"note: motion stops dead at {frames[stops[0] + 1] / fps:.2f}s - ease out or keep a slow drift")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode", nargs="?", default="episode")
    ap.add_argument("--width", type=int, default=0, help="long side of the stills (default 480)")
    ap.add_argument("--every", type=float, default=4.0)
    ap.add_argument("--times", default="")
    ap.add_argument("--scene", default="", help="only this scene: 8 frames across it + its boundaries")
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--no-boundaries", action="store_true")
    ap.add_argument("--no-variants", action="store_true")
    ap.add_argument("--cpu", action="store_true", help="python engine: plain NumPy instead of strict fake GPU")
    ap.add_argument("--real", action="store_true", help="on the user's PC: use the real GPU (no fake-GPU checks)")
    ap.add_argument("--strip", default="", help="motion strip of a scene name or a stretch 't0-t1' (seconds)")
    ap.add_argument("--strip-fps", type=float, default=6.0)
    ap.add_argument("--no-strips", action="store_true", help="skip the motion strips of the full check")
    a = ap.parse_args()

    ep = Path(a.episode).resolve()
    out = ROOT / "check"
    out.mkdir(exist_ok=True)
    for f in out.glob("*"):
        f.unlink()
    man = json.loads((ROOT / "vizavi.json").read_text(encoding="utf-8")) if (ROOT / "vizavi.json").exists() else {}
    mirror_runtime(ep)
    if a.cpu:
        os.environ["RENDER_CPU"] = "1"
    elif not a.real:
        os.environ["RENDER_FAKEGPU"] = "1"
    os.chdir(ep)
    sys.path.insert(0, str(ep))
    import vzrender
    import numpy as np
    from PIL import Image, ImageDraw
    rep = []
    P = lambda s: (print(s, flush=True), rep.append(s))

    meta = vzrender.load_meta(ep)
    eng = meta["engine"]
    if eng == "python":
        import film
        t0 = time.time(); film.prepare_assets(); P(f"prepare_assets: {time.time() - t0:.1f}s")
    fps, nfr = meta["fps"], meta["nfr"]
    dur = nfr / fps
    scenes, words = meta["scenes"], va.load_words(ep / "input" / "words.tsv")
    P(f"{eng} engine: design {meta['W']}x{meta['H']}, NFR={nfr} ({dur:.2f}s @ {fps:g}fps), alpha={meta['alpha']}, "
      f"responsive={meta['responsive']}, scenes={len(scenes)}, words={len(words)}")
    # spec vs order
    vs = man.get("variants") or [{"id": "main", "w": meta["W"], "h": meta["H"]}]
    if man.get("fps") and abs(float(man["fps"]) - fps) > 1e-6:
        P(f"ERROR: fps {fps:g} but the order says {man['fps']}")
    if abs(meta["W"] / meta["H"] - vs[0]["w"] / vs[0]["h"]) > 0.01 and not meta["responsive"]:
        P(f"ERROR: design {meta['W']}x{meta['H']} has the wrong aspect for {vs[0]['w']}x{vs[0]['h']}")
    if len(vs) > 1 and not meta["responsive"]:
        P("ERROR: several aspect versions ordered -> make the project responsive (RESPONSIVE = True / \"responsive\": true)")
    if "alpha" in man and bool(man["alpha"]) != bool(meta["alpha"]):
        P(f"ERROR: alpha={meta['alpha']} but the order says {man['alpha']}")
    if man.get("suggested_nfr") and abs(nfr - man["suggested_nfr"]) > fps * 1.5:
        P(f"WARNING: NFR {nfr} vs suggested {man['suggested_nfr']}")
    if not scenes:
        P("WARNING: SCENES missing (the Studio HUD/checks use them)")
    elif abs(scenes[0][1]) > 1e-6 or abs(scenes[-1][2] - dur) > 1 / fps + 1e-6:
        P(f"WARNING: SCENES should cover 0..{dur:.3f}s (got {scenes[0][1]}..{scenes[-1][2]})")
    if words and words[-1][1] > dur:
        P(f"ERROR: narration ends at {words[-1][1]:.2f}s but the video is {dur:.2f}s")

    fr = set()
    if a.scene:
        sc = next((x for x in scenes if str(x[0]) == a.scene), None)
        if not sc:
            P(f"ERROR: no scene '{a.scene}' (scenes: {', '.join(str(x[0]) for x in scenes)})"); return 1
        a.times = ",".join(f"{sc[1] + (sc[2] - sc[1]) * k / 7:.3f}" for k in range(8))
        a.no_audio, a.no_variants = True, True
    if a.strip and not a.scene and not a.times:      # only the strip: no stills, no sound
        a.no_audio, a.no_variants, a.no_boundaries = True, True, True
        a.times = "-1"
    if a.times:
        fr |= {min(nfr - 1, max(0, int(round(float(t) * fps)))) for t in a.times.split(",") if t.strip() and float(t) >= 0}
    else:
        k = 0.0
        while k < dur:
            fr.add(min(nfr - 1, int(round(k * fps)))); k += a.every
        fr.add(nfr - 1)
        if eng == "python":
            fr |= set(getattr(__import__("film"), "SELFTEST_FRAMES", []))
        if not a.no_boundaries:
            for sc in scenes[1:]:
                b = int(round(sc[1] * fps)); fr |= {max(0, b - 1), min(nfr - 1, b)}
    fr = sorted(fr)

    def size_for(w, h, long_side):
        s = long_side / max(w, h)
        return even(w * s), even(h * s)

    def sheet(images, path, cols):
        tw, th = images[0].size
        rows = (len(images) + cols - 1) // cols
        sh = Image.new("RGB", (cols * tw + (cols - 1) * 4, rows * th + (rows - 1) * 4), (40, 40, 40))
        for j, im in enumerate(images):
            sh.paste(im, ((j % cols) * (tw + 4), (j // cols) * (th + 4)))
        sh.save(path, quality=82)

    probe = []

    def render_set(w, h, frames, label_words=True, record=False):
        src = vzrender.make_source(eng, w, h, meta["alpha"])
        font = va.load_font(max(11, min(w, h) // 30), "DejaVuSansMono.ttf")
        tiles, times = [], []
        for i in frames:
            t1 = time.time()
            if record:
                src.begin_probe()
            img = src.frame(i, i / fps)
            times.append(time.time() - t1)
            if record:
                items = src.end_probe()
                if items is not None:
                    probe.append({"t": i / fps, "items": vzrender.measure([dict(x) for x in items], vzrender.flatten(img, w, h))})
            if not (isinstance(img, np.ndarray) and img.dtype == np.uint8 and img.shape[:2] == (h, w) and img.shape[2] in (3, 4)):
                raise SystemExit(f"ERROR: frame {i} returned {type(img).__name__} {getattr(img, 'dtype', '')} "
                                 f"{getattr(img, 'shape', '')}, need numpy uint8 ({h},{w},3|4)")
            if meta["alpha"] and img.shape[2] == 4:
                a_ = img[..., 3]
                if a_.min() == 255:
                    P(f"WARNING: alpha project but frame {i} is fully opaque")
            im = Image.fromarray(vzrender.flatten(img, w, h))
            lab = Image.new("RGB", (w, font.size + 10), (0, 0, 0))
            t = i / fps
            wi, speaking = va.word_at(words, t)
            wtxt = (words[wi][2] if wi >= 0 else "") + ("" if speaking or not words else " (pause)")
            ImageDraw.Draw(lab).text((4, 4), f"{t:5.2f}s f{i} {va.scene_at(scenes, t)} | {wtxt}"[:120],
                                     fill=(230, 230, 230), font=font)
            tile = Image.new("RGB", (w, h + lab.height)); tile.paste(im, (0, 0)); tile.paste(lab, (0, h))
            tiles.append(tile)
        src.close()
        return tiles, times

    long_side = a.width or 480
    w, h = size_for(vs[0]["w"], vs[0]["h"], long_side)
    if fr:
        tiles, times = render_set(w, h, fr, record=True)
        P(f"rendered {len(fr)} frames at {w}x{h}: avg {np.mean(times):.2f}s, max {max(times):.2f}s (slowest f{fr[int(np.argmax(times))]})")
        cols = 4 if w >= h else 6
        per = cols * (4 if w >= h else 2)
        for s in range(0, len(tiles), per):
            sheet(tiles[s:s + per], out / f"sheet_{s // per + 1:02d}.jpg", cols)
        P("contact sheets: " + ", ".join(p.name for p in sorted(out.glob("sheet_*.jpg"))) + " in check/")

    # motion strips: consecutive frames at ~6 fps, one row per second - stills can't show easing, speed or jerks
    strips = []
    step = max(1, int(round(fps / max(1.0, a.strip_fps))))
    def span(t0, t1, cap):
        f0, f1 = max(0, int(round(t0 * fps))), min(nfr - 1, int(round(t1 * fps)))
        frs = list(range(f0, max(f0 + 1, f1), step))     # end excluded: the next scene starts there
        if len(frs) > cap:
            mid = len(frs) // 2
            frs = frs[max(0, mid - cap // 2): max(0, mid - cap // 2) + cap]
        return frs
    if a.strip:
        sc = next((x for x in scenes if str(x[0]) == a.strip), None)
        if sc:
            strips.append((str(sc[0]), span(sc[1], sc[2], 36)))
        else:
            try:
                t0, t1 = (float(x) for x in a.strip.split("-", 1))
                strips.append((f"{t0:.1f}-{t1:.1f}s", span(t0, t1, 60)))
            except ValueError:
                P(f"ERROR: --strip wants a scene name or t0-t1 (scenes: {', '.join(str(x[0]) for x in scenes)})")
    elif a.scene:
        sc = next((x for x in scenes if str(x[0]) == a.scene), None)
        mid = (sc[1] + sc[2]) / 2
        strips.append((str(sc[0]), span(max(sc[1], mid - 1.5), min(sc[2], mid + 1.5), 18)))
    elif not a.times and not a.no_strips:
        for sc in scenes:
            mid = (sc[1] + sc[2]) / 2
            strips.append((str(sc[0]), span(max(sc[1], mid - 0.5), min(sc[2], mid + 0.5), 7)))
    if strips:
        sw, sh_ = size_for(vs[0]["w"], vs[0]["h"], 240 if vs[0]["w"] >= vs[0]["h"] else 200)
        per_row = max(1, int(round(fps / step)))
        for name, frs in strips:
            if len(frs) < 2:
                continue
            st_tiles, _ = render_set(sw, sh_, frs)
            safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
            sheet(st_tiles, out / f"strip_{safe}.jpg", min(per_row, len(st_tiles)))
            P(f"motion strip '{name}': {frs[0] / fps:.2f}-{frs[-1] / fps:.2f}s, {len(frs)} frames -> check/strip_{safe}.jpg"
              + "".join(f"\n  {m}" for m in motion_notes(st_tiles, frs, fps, sh_)))
    if len(vs) > 1 and not a.no_variants:
        pick = sorted({min(nfr - 1, int(nfr * k)) for k in (0.1, 0.4, 0.7, 0.95)})
        for v in vs[1:]:
            vw, vh = size_for(v["w"], v["h"], 360)
            vt, _ = render_set(vw, vh, pick)
            sheet(vt, out / f"variant_{v['id']}.jpg", len(vt))
        P("other aspects: " + ", ".join(f"variant_{v['id']}.jpg" for v in vs[1:]))

    # text: html pages are probed every 0.25 s without screenshots (cheap); python only at the stills above
    tc = man.get("text_checks") or {}
    dense = []
    if eng == "html" and not a.times and not a.scene:
        src = vzrender.make_source(eng, w, h, meta["alpha"])
        k = 0
        while k < nfr:
            src.pg.evaluate("t => VZ.seek(t)", k / fps)
            dense.append({"t": k / fps, "items": src.end_probe() or []})
            k += max(1, int(round(fps / 4)))
        src.close()
        measured = {round(p_["t"], 4): p_["items"] for p_ in probe}
        for d_ in dense:                      # contrast from the stills where they coincide
            m = measured.get(round(d_["t"], 4))
            if m is not None:
                d_["items"] = m
    if dense or probe:
        vocab = "\n".join((ROOT / "input" / f).read_text(encoding="utf-8") for f in ("script.txt", "transcript.txt")
                           if (ROOT / "input" / f).exists()) + " " + " ".join(x[2] for x in words)
        iss, summ = vc.analyze_text(dense or probe, w, h, step=0.25 if dense else a.every, safe=tc.get("safe"),
                                    vocab_text=vocab, latin_only=bool(tc.get("latin_only")), min_run=2 if dense else 1)
        summ = None if not (dense or probe) else summ
        for line in vc.report_md(iss, summ):
            P("text: " + line)
        for i in vc.ranked([], iss):
            P(f"{'ERROR' if i['rank'] in ('P0', 'P1') else 'WARNING'} ({i['rank']}): {i['text']}")
    elif eng == "python":
        P("text: not checked - draw all on-screen text with text()/captions() from the template (they report it)")

    if eng == "python":
        cs = getattr(__import__("film"), "camera_state", None)
        if cs:
            c = va.camera_check(cs, dur, fps)
            P("camera: " + (c["error"] if c.get("error") else "smooth" if c["ok"] else
                            "issues: " + "; ".join(f"{t}s {k}" for t, k in c["issues"])))
        else:
            P("camera: camera_state(t) not defined -> smoothness not checked")

    if not a.no_audio:
        t1 = time.time()
        r = subprocess.run([sys.executable, "audio.py"], cwd=ep, capture_output=True, text=True)
        if r.returncode != 0:
            P("ERROR audio.py failed:\n" + r.stderr[-1500:]); return 1
        P(f"audio.py: {time.time() - t1:.1f}s")
        from scipy.io import wavfile
        sr, x = wavfile.read(ep / "mix.wav")
        if sr != 48000 or x.ndim != 2 or x.shape[1] != 2:
            P(f"ERROR mix.wav must be 48 kHz stereo (got {sr} Hz, shape {x.shape})")
        nar = next(iter(sorted((ROOT / "input").glob("narration.*"))), None)
        ar = va.analyze_audio(ep / "mix.wav", nar, dur, words, scenes, out / "audio_plot.png")
        P(f"audio (your mix.wav only; the app adds music/voice per the order): {ar.get('mix_lufs')} LUFS, "
          f"peak {ar.get('mix_true_peak')} dBTP, voice over it {ar.get('voice_over_bed_db')} dB -> check/audio_plot.png")
        for f in ar["flags"]:
            P("audio flag: " + f)
    (out / "report.txt").write_text("\n".join(rep), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
