"""Universal Vizavi renderer: any size / aspect / fps, alpha, two engines.
  python engine: film.py (numpy/CuPy, kit contract)          -> GPU self-test, process pool
  html engine:   index.html + project.json + vz.js (Chromium)  -> pool of headless Chromium pages
usage:
  python vzrender.py OUT.mp4 --size 1920x1080 [--crf 18]              # H.264 (alpha composited on checker)
  python vzrender.py OUT.mov --size 1920x1080 --codec prores          # ProRes 4444 with alpha
  python vzrender.py --stills DIR --size 960x540 --times 0,2.5,7      # PNG stills (RGBA kept)
  python vzrender.py --meta                                            # print project meta as JSON
Env: WORKERS=n, RENDER_CPU=1 (python engine on CPU)."""
import argparse, hashlib, io, json, os, subprocess, sys, time
from multiprocessing import Pool
from pathlib import Path
import numpy as np

HERE = Path.cwd()
NOWIN = 0x08000000 if os.name == "nt" else 0
_G = {}


def ffmpeg():
    from ff import ffmpeg_exe
    return ffmpeg_exe()


# ------------------------------------------------------------------ project meta
def engine_of(wd=HERE):
    pj = Path(wd) / "project.json"
    if pj.exists():
        return json.loads(pj.read_text(encoding="utf-8")).get("engine", "html")
    return "python"


def load_meta(wd=HERE):
    if engine_of(wd) == "html":
        p = json.loads((Path(wd) / "project.json").read_text(encoding="utf-8"))
        return {"engine": "html", "W": int(p["width"]), "H": int(p["height"]), "fps": float(p["fps"]),
                "nfr": int(p["nfr"]), "alpha": bool(p.get("alpha", False)), "scenes": p.get("scenes", []),
                "cues": p.get("cues", []), "responsive": bool(p.get("responsive", False))}
    import film
    return {"engine": "python", "W": film.W, "H": film.H, "fps": float(film.FPS), "nfr": int(film.NFR),
            "alpha": bool(getattr(film, "ALPHA", False)),
            "scenes": [[str(s[0]), float(s[1]), float(s[2])] for s in getattr(film, "SCENES", [])],
            "cues": [[float(c[0])] + [str(x) for x in c[1:]] for c in getattr(film, "CUES", [])],
            "responsive": bool(getattr(film, "RESPONSIVE", False))}


# ------------------------------------------------------------------ frame sources
class PyFrames:
    def __init__(self, w, h):
        import film
        film.set_res(w, h)
        self.film, self.w, self.h = film, w, h
        import backend
        self.dev = backend.device_name()

    def frame(self, i, t):
        return self.film.render_frame(i)

    def begin_probe(self):
        if hasattr(self.film, "TEXT_LOG"):          # film.py's text()/captions() note what they draw
            self.film.TEXT_LOG = []

    def end_probe(self):
        items = getattr(self.film, "TEXT_LOG", None)
        if items is not None:
            self.film.TEXT_LOG = None
        return items

    def close(self):
        pass


class HtmlFrames:
    """one headless Chromium page; VZ.seek(t) then screenshot."""
    def __init__(self, w, h, alpha=False, wd=HERE):
        from playwright.sync_api import sync_playwright
        self.w, self.h, self.alpha = w, h, alpha
        self.p = sync_playwright().start()
        self.b = self.p.chromium.launch(args=["--force-color-profile=srgb", "--font-render-hinting=none",
                                              "--allow-file-access-from-files", "--disable-lcd-text",
                                              "--autoplay-policy=no-user-gesture-required"])
        self.pg = self.b.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
        self.errors = []
        self.pg.on("pageerror", lambda e: self.errors.append(f"JS error: {e}"))
        self.pg.on("console", lambda m: self.errors.append(f"console.error: {m.text}") if m.type == "error" else None)
        proj = json.loads((Path(wd) / "project.json").read_text(encoding="utf-8"))
        self.pg.add_init_script(f"window.VZ_PROJECT = {json.dumps(proj)};")
        wt = Path(wd) / "input" / "words.tsv"      # final word timing (precise on the user's PC) -> VZ.words
        if wt.exists():
            ws = [[float(r[0]), float(r[1]), r[2]] for r in (l.split("\t") for l in wt.read_text(encoding="utf-8").splitlines())
                  if r and r[0][:1].isdigit() and len(r) >= 3]
            self.pg.add_init_script(f"window.VZ_WORDS = {json.dumps(ws, ensure_ascii=False)};")
        url = (Path(wd) / "index.html").resolve().as_uri() + f"?w={w}&h={h}&alpha={int(alpha)}"
        self.pg.goto(url, wait_until="load")
        try:
            self.pg.wait_for_function("() => window.VZ && VZ.isReady && VZ.isReady()", timeout=90000)
        except Exception:
            raise RuntimeError("page never became ready (VZ.isReady). " + " | ".join(self.errors[-5:]))
        self.dev = "Chromium"

    def frame(self, i, t):
        self.pg.evaluate("t => VZ.seek(t)", t)
        if self.errors:
            raise RuntimeError(" | ".join(self.errors[-5:]))
        png = self.pg.screenshot(type="png", omit_background=self.alpha, caret="hide")
        from PIL import Image
        return np.asarray(Image.open(io.BytesIO(png)).convert("RGBA" if self.alpha else "RGB"))

    def begin_probe(self):
        pass

    def end_probe(self):
        try:
            return self.pg.evaluate("() => (window.VZ && VZ.textLayout) ? VZ.textLayout() : null")
        except Exception:
            return None

    def close(self):
        try:
            self.b.close(); self.p.stop()
        except Exception:
            pass


def make_source(engine, w, h, alpha):
    return HtmlFrames(w, h, alpha) if engine == "html" else PyFrames(w, h)


_CHECK = {}


def flatten(img, w, h):
    """RGBA -> RGB over a dark checkerboard (preview / H.264)."""
    if img.shape[2] == 3:
        return img
    key = (w, h)
    if key not in _CHECK:
        yy, xx = np.mgrid[0:h, 0:w]
        c = (((yy // 16) + (xx // 16)) % 2).astype(np.float32)
        _CHECK[key] = (28 + 14 * c)[..., None].repeat(3, 2)
    a = img[..., 3:4].astype(np.float32) / 255.0
    return (img[..., :3] * a + _CHECK[key] * (1 - a)).astype(np.uint8)


# ------------------------------------------------------------------ text probe (for the automatic checks)

def _lum(rgb):
    c = np.asarray(rgb, dtype=np.float32) / 255.0
    c = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * c[..., 0] + 0.7152 * c[..., 1] + 0.0722 * c[..., 2]


def measure(items, img):
    """adds 'contrast' to each item: the text colour against the median of the pixels in its box that are not
    text-coloured (the background, shadows and outlines included - an outline helps reading, so it should count)"""
    H, W = img.shape[:2]
    rgb = img[..., :3]
    for it in items:
        it.pop("contrast", None)
        col = it.get("color")
        b = it.get("box")
        if not col or not b:
            continue
        x0, y0 = max(0, int(b[0])), max(0, int(b[1]))
        x1, y1 = min(W, int(b[2] + 0.999)), min(H, int(b[3] + 0.999))
        if x1 - x0 < 2 or y1 - y0 < 2:
            continue
        reg = rgb[y0:y1, x0:x1].reshape(-1, 3)
        if len(reg) > 40000:
            reg = reg[:: len(reg) // 40000 + 1]
        lf = float(_lum(np.asarray(col[:3], dtype=np.float32)))
        lr = _lum(reg.astype(np.float32))
        bg = lr[np.abs(lr - lf) > 0.06]
        if len(bg) < 0.15 * len(lr):         # glyphs cover 20-40 % of a text box: a box that is nearly all
            it["contrast"] = 1.0             # text-coloured means the text sits on its own colour (invisible)
            continue
        lb = float(np.median(bg))
        it["contrast"] = round((max(lf, lb) + 0.05) / (min(lf, lb) + 0.05), 2)
    return items



# ------------------------------------------------------------------ workers
def _init(engine, w, h, alpha, codec, crf, fps, outdir, ff, probe_n=0, reuse=None):
    _G.update(engine=engine, w=w, h=h, alpha=alpha, codec=codec, crf=crf, fps=fps, outdir=outdir, ff=ff, probe_n=probe_n,
              reuse=reuse or {})
    _G["src"] = make_source(engine, w, h, alpha)


def _enc_cmd(out, w, h, fps, codec, crf, rgba_in, ff):
    pix = "rgba" if rgba_in else "rgb24"
    cmd = [ff, "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", pix, "-s", f"{w}x{h}", "-r", str(fps), "-i", "-"]
    if codec == "prores":
        cmd += ["-c:v", "prores_ks", "-profile:v", "4", "-pix_fmt", "yuva444p10le" if rgba_in else "yuv444p10le",
                "-vendor", "apl0"]
    else:
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p"]
    return cmd + ["-r", str(fps), out]


def sample_frames(frames):
    """the frames that stand for a batch when deciding whether it changed: first, two inside, last"""
    n = len(frames)
    return sorted({frames[0], frames[n // 3], frames[(2 * n) // 3], frames[-1]})


def frame_hash(img):
    return hashlib.blake2b(np.ascontiguousarray(img).tobytes(), digest_size=16).hexdigest()


def _one(i):
    """render frame i (+ what text it shows, on the frames the text probe samples)"""
    g = _G
    pn = g.get("probe_n") or 0
    sample = pn and i % pn == 0
    if sample:
        g["src"].begin_probe()
    img = g["src"].frame(i, i / g["fps"])
    if img.shape[0] != g["h"] or img.shape[1] != g["w"] or img.dtype != np.uint8:
        raise RuntimeError(f"frame {i}: got {img.shape} {img.dtype}, need ({g['h']},{g['w']},3|4) uint8")
    items = None
    if sample:
        items = g["src"].end_probe()
        try:
            items = measure([dict(x) for x in items], flatten(img, g["w"], g["h"])) if items is not None else None
        except Exception as e:               # the checks must never break a render
            items = None
            print(f"text probe skipped at frame {i}: {e}", flush=True)
    return img, items, sample


def _render_chunk(args):
    ci, frames = args
    g = _G
    ext = ".mov" if g["codec"] == "prores" else ".mp4"
    out = os.path.join(g["outdir"], f"chunk{ci:05d}{ext}")
    rgba = g["codec"] == "prores" and g["alpha"]
    t0 = time.time()
    keys = sample_frames(frames)
    hashes, pre = {}, {}
    old = g["reuse"].get(ci)
    if old and old.get("frames") == [frames[0], frames[-1]]:
        # the same second rendered last time: if its sample frames come out identical, the old batch is reused
        same = True
        for i in keys:
            pre[i] = _one(i)
            hashes[str(i)] = frame_hash(pre[i][0])
            if hashes[str(i)] != old["hashes"].get(str(i)):
                same = False
                break
        if same:
            import shutil
            shutil.copyfile(old["file"], out)
            if g.get("probe_n") and old.get("text") and os.path.exists(old["text"]):
                shutil.copyfile(old["text"], os.path.join(g["outdir"], f"text{ci:05d}.json"))
            elif g.get("probe_n"):
                with open(os.path.join(g["outdir"], f"text{ci:05d}.json"), "w", encoding="utf-8") as f:
                    json.dump({str(i): it for i, (_, it, smp) in pre.items() if smp}, f, ensure_ascii=False)
            return ci, time.time() - t0, "reused", hashes
    p = subprocess.Popen(_enc_cmd(out, g["w"], g["h"], g["fps"], g["codec"], g["crf"], rgba, g["ff"]),
                         stdin=subprocess.PIPE, creationflags=NOWIN)
    probe = {}
    for i in frames:
        img, items, smp = pre.pop(i) if i in pre else _one(i)
        if i in keys and str(i) not in hashes:
            hashes[str(i)] = frame_hash(img)
        if smp:
            probe[i] = items
        if rgba:
            if img.shape[2] == 3:
                img = np.concatenate([img, np.full(img.shape[:2] + (1,), 255, np.uint8)], 2)
        else:
            img = flatten(img, g["w"], g["h"])
        p.stdin.write(np.ascontiguousarray(img).tobytes())
    p.stdin.close(); p.wait()
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg failed on batch {ci}")
    if g.get("probe_n"):
        with open(os.path.join(g["outdir"], f"text{ci:05d}.json"), "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in probe.items()}, f, ensure_ascii=False)
    return ci, time.time() - t0, g["src"].dev, hashes


# ------------------------------------------------------------------ reuse of unchanged batches
def cache_key(engine, w, h, fps, codec, crf, alpha, probe):
    return hashlib.sha1(json.dumps([engine, w, h, fps, codec, int(crf), bool(alpha), bool(probe)]).encode()).hexdigest()[:16]


def load_reuse(cdir, chunks):
    """{batch: {frames, hashes, file, text}} from the last render of this size, only batches that cover the same frames"""
    try:
        idx = json.loads((cdir / "index.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    want = {k: [fr[0], fr[-1]] for k, fr in chunks}
    out = {}
    for k, e in (idx.get("chunks") or {}).items():
        k = int(k)
        f = cdir / e.get("file", "")
        if want.get(k) == e.get("frames") and f.is_file() and e.get("hashes"):
            out[k] = {"frames": e["frames"], "hashes": e["hashes"], "file": str(f),
                      "text": str(cdir / e["text"]) if e.get("text") else ""}
    return out


def save_reuse(cdir, tmp, chunks, results, ext):
    """keep this render's batches for next time (one set per size); what is no longer used goes"""
    import shutil
    cdir.mkdir(parents=True, exist_ok=True)
    idx = {"chunks": {}}
    keep = {"index.json"}
    for k, fr in chunks:
        r = results.get(k)
        if not r:
            continue
        name, tname = f"chunk{k:05d}{ext}", f"text{k:05d}.json"
        src, tsrc = tmp / name, tmp / tname
        if r["dev"] != "reused" or not (cdir / name).exists():
            os.replace(src, cdir / name) if src.exists() else None
        if tsrc.exists() and (r["dev"] != "reused" or not (cdir / tname).exists()):
            shutil.copyfile(tsrc, cdir / tname)
        idx["chunks"][str(k)] = {"frames": [fr[0], fr[-1]], "hashes": r["hashes"], "file": name,
                                 "text": tname if (cdir / tname).exists() else ""}
        keep |= {name, tname}
    for f in cdir.iterdir():
        if f.name not in keep:
            try:
                f.unlink()
            except OSError:
                pass
    (cdir / "index.json").write_text(json.dumps(idx), encoding="utf-8")


def _selftest_key():
    """identifies 'this exact project code on this exact Python and graphics card'"""
    h = hashlib.sha1()
    for f in sorted(HERE.glob("*.py")):
        h.update(f.name.encode()); h.update(f.read_bytes())
    h.update(sys.executable.encode()); h.update(sys.version.encode())
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
                           capture_output=True, text=True, timeout=8, creationflags=NOWIN)
        h.update(r.stdout.encode())
    except Exception:
        pass
    return h.hexdigest()[:24]


def gpu_selftest(meta):
    """A passed self-test is remembered for the same code/Python/GPU, so preview -> final (and one render per
    aspect version) do not each pay for it again. A failed test is never remembered."""
    key, mark = _selftest_key(), HERE / ".gpu_ok"
    try:
        k, _, dev = mark.read_text(encoding="utf-8").partition("\n")
        if k == key:
            print("GPU self-test passed (remembered for this project code):", dev.strip(), flush=True)
            return True
    except OSError:
        pass
    code = ("import backend, film, sys\nif not backend.GPU: sys.exit(3)\n"
            "film.set_res(640, int(640 * film.H / film.W) // 2 * 2)\n"
            "for f in getattr(film, 'SELFTEST_FRAMES', [0]): film.render_frame(f)\nprint(backend.device_name())\n")
    print("testing GPU (up to 3 min)...", flush=True)
    try:
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=180, creationflags=NOWIN)
    except subprocess.TimeoutExpired:
        print("GPU self-test timed out -> CPU."); return False
    if r.returncode == 0:
        print("GPU self-test passed:", r.stdout.strip())
        try:
            mark.write_text(key + "\n" + r.stdout.strip(), encoding="utf-8")
        except OSError:
            pass
        return True
    if r.returncode == 3:
        print("No usable NVIDIA GPU / CuPy -> CPU."); return False
    print("GPU self-test FAILED -> CPU. Error:\n" + r.stderr[-1500:]); return False


def write_probe(path, tmp, chunks, engine, w, h, fps, probe_n):
    samples, supported = [], False
    for k, _ in chunks:
        try:
            d = json.loads((tmp / f"text{k:05d}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for i, items in d.items():
            supported = supported or items is not None
            samples.append({"t": round(int(i) / fps, 4), "items": items or []})
    samples.sort(key=lambda s: s["t"])
    Path(path).write_text(json.dumps({"engine": engine, "W": w, "H": h, "step": probe_n / fps, "supported": supported,
                                      "samples": samples}, ensure_ascii=False), encoding="utf-8")


def parse_size(s, meta):
    if not s:
        return meta["W"], meta["H"]
    w, h = (int(x) for x in s.lower().split("x"))
    return w, h


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?")
    ap.add_argument("--size", default="")
    ap.add_argument("--codec", default="", choices=["", "h264", "prores"])
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--stills", default="")
    ap.add_argument("--times", default="")
    ap.add_argument("--meta", action="store_true")
    ap.add_argument("--textprobe", default="", help="write what text is on screen every 0.25 s (for the checks)")
    a = ap.parse_args()
    meta = load_meta()
    if a.meta:
        print("VZMETA" + json.dumps(meta)); return
    engine = meta["engine"]
    w, h = parse_size(a.size, meta)
    if engine == "python":
        import film
        print("preparing assets...", flush=True)
        film.prepare_assets()

    if a.stills:
        os.makedirs(a.stills, exist_ok=True)
        src = make_source(engine, w, h, meta["alpha"])
        from PIL import Image
        for t in [float(x) for x in a.times.split(",") if x.strip()]:
            i = min(meta["nfr"] - 1, max(0, int(round(t * meta["fps"]))))
            img = src.frame(i, i / meta["fps"])
            Image.fromarray(img).save(os.path.join(a.stills, f"f{i:05d}.png"))
            print(f"still f{i} ({t:.2f}s)", flush=True)
        src.close()
        return

    out = Path(a.out)
    codec = a.codec or ("prores" if out.suffix.lower() == ".mov" else "h264")
    ff = ffmpeg()
    use_gpu = False
    if engine == "python":
        use_gpu = os.environ.get("RENDER_CPU") != "1" and gpu_selftest(meta)
        if not use_gpu:
            os.environ["RENDER_CPU"] = "1"
        for v in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
            os.environ.setdefault(v, "1")
        nw = int(os.environ.get("WORKERS") or (os.environ.get("GPU_WORKERS") or 3 if use_gpu else
                                               os.environ.get("CPU_WORKERS") or min(os.cpu_count() or 2, 10)))
    else:
        nw = int(os.environ.get("WORKERS") or os.environ.get("HTML_WORKERS") or max(1, min(6, (os.cpu_count() or 2) // 2)))
    tmp = out.parent / (out.stem + "_chunks")
    tmp.mkdir(parents=True, exist_ok=True)
    fps = meta["fps"]
    frames = list(range(meta["nfr"]))
    if not frames:
        raise SystemExit("the project has no frames (NFR = 0)")
    # 1 s per batch (as before): scenes differ a lot in cost, and small batches keep all workers busy to the end
    # instead of two waiting while the third finishes one long batch
    chunk = max(12, int(round(fps)))
    chunks = [(k, frames[s:s + chunk]) for k, s in enumerate(range(0, len(frames), chunk))]
    if len(chunks) > 1 and len(chunks[-1][1]) < chunk // 2:
        # a tiny tail would become its own few-frame video; joined to the others it skews the file's timestamps
        # (a 1-frame tail made a correct 24 fps file report 23.93 fps), so it is merged into the previous batch
        _, tail = chunks.pop()
        chunks[-1] = (chunks[-1][0], chunks[-1][1] + tail)
    kind = "GPU" if use_gpu else ("Chromium" if engine == "html" else "CPU")
    print(f"{kind} render ({engine} engine): {len(frames)} frames {w}x{h} @ {fps:g} fps, {len(chunks)} batches of {chunk} frames, "
          f"{nw} workers, {codec}", flush=True)
    t0 = time.time(); done = 0
    probe_n = max(1, int(round(fps / 4))) if a.textprobe else 0
    ext = ".mov" if codec == "prores" else ".mp4"
    # VZ_CHUNK_CACHE: seconds whose picture did not change since the last render of this size are copied, not rendered
    cdir = None
    if os.environ.get("VZ_CHUNK_CACHE") and os.environ.get("VZ_NO_REUSE") != "1":
        cdir = Path(os.environ["VZ_CHUNK_CACHE"]) / cache_key(engine, w, h, fps, codec, a.crf, meta["alpha"], probe_n)
    reuse = load_reuse(cdir, chunks) if cdir else {}
    if reuse:
        print(f"{len(reuse)} of {len(chunks)} batches were rendered at this size before: unchanged ones are reused", flush=True)
    results, reused = {}, 0
    with Pool(nw, initializer=_init, initargs=(engine, w, h, meta["alpha"], codec, a.crf, fps, str(tmp), ff, probe_n,
                                               reuse)) as pool:
        for ci, dt, dev, hashes in pool.imap_unordered(_render_chunk, chunks):
            done += 1
            results[ci] = {"dev": dev, "hashes": hashes}
            el = time.time() - t0
            # the first batches finish together (one per worker) and include each worker's warm-up, so until a
            # full round is done, the work in flight counts as done: avoids a "45 min left" that is really ~15
            left = el / max(done, min(nw, len(chunks))) * (len(chunks) - done)
            if dev == "reused":
                reused += 1
                print(f"[{done}/{len(chunks)}] batch {ci} unchanged, reused | elapsed {el:.0f}s, ~{left:.0f}s left", flush=True)
            else:
                print(f"[{done}/{len(chunks)}] batch {ci} in {dt:.0f}s on {dev} | elapsed {el:.0f}s, "
                      f"~{left:.0f}s left", flush=True)
    lst = tmp / "list.txt"
    lst.write_text("".join(f"file 'chunk{k:05d}{ext}'\n" for k, _ in chunks), encoding="utf-8")
    subprocess.run([ff, "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)],
                   check=True, creationflags=NOWIN)
    if probe_n:
        write_probe(a.textprobe, tmp, chunks, engine, w, h, fps, probe_n)
    if cdir:
        try:
            save_reuse(cdir, tmp, chunks, results, ext)
        except OSError as e:
            print(f"(couldn't keep the batches for next time: {e})", flush=True)
    if reused:
        print(f"reused {reused} unchanged batch(es) of {len(chunks)} from the last render", flush=True)
    for f in tmp.iterdir():
        f.unlink()
    tmp.rmdir()
    print(f"done in {time.time() - t0:.0f}s -> {out}", flush=True)


if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
    main()
