"""Render all frames to MP4 using every worker evenly (small batches). GPU (CuPy) if it passes a self-test, else CPU.
usage: python render_all.py <width> <outdir> [crf]"""
import sys, os, subprocess, numpy as np, time
from multiprocessing import Pool
from ff import ffmpeg_exe

CHUNK = 24  # frames per batch (1 s of video)
_G = {}

def _init(w, h, outdir, crf, ff):
    import film, backend
    film.set_res(w, h)
    _G.update(film=film, backend=backend, w=w, h=h, outdir=outdir, crf=crf, ff=ff)

def _render_chunk(args):
    ci, frames = args
    g = _G; film = g["film"]
    out = os.path.join(g["outdir"], f"chunk{ci:04d}.mp4")
    p = subprocess.Popen([g["ff"], "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{g['w']}x{g['h']}", "-r", "24", "-i", "-", "-c:v", "libx264", "-preset", "medium",
                          "-crf", str(g["crf"]), "-pix_fmt", "yuv420p", "-r", "24", out], stdin=subprocess.PIPE)
    t0 = time.time()
    for i in frames:
        p.stdin.write(np.ascontiguousarray(film.render_frame(i)).tobytes())
    p.stdin.close(); p.wait()
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg failed on batch {ci}")
    return ci, time.time() - t0, g["backend"].device_name()

def gpu_selftest():
    code = ("import backend, film, sys\n"
            "if not backend.GPU: sys.exit(3)\n"
            "film.set_res(640, 360)\n"
            "for f in film.SELFTEST_FRAMES: film.render_frame(f)\n"
            "print(backend.device_name())\n")
    print("testing GPU (up to 3 min)...", flush=True)
    try:
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        print("GPU self-test timed out -> CPU."); return False
    if r.returncode == 0:
        print("GPU self-test passed:", r.stdout.strip()); return True
    if r.returncode == 3:
        print("No usable NVIDIA GPU / CuPy -> CPU."); return False
    print("GPU self-test FAILED -> CPU. Error:\n" + r.stderr[-1500:]); return False

if __name__ == "__main__":
    w = int(sys.argv[1]); h = w * 9 // 16; outdir = sys.argv[2]
    crf = int(sys.argv[3]) if len(sys.argv) > 3 else 18
    ff = ffmpeg_exe(); print("ffmpeg:", ff)
    import film
    print("preparing assets (first run can take ~1 min)...", flush=True)
    film.prepare_assets()
    use_gpu = os.environ.get("RENDER_CPU") != "1" and gpu_selftest()
    if not use_gpu:
        os.environ["RENDER_CPU"] = "1"
    for v in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
        os.environ.setdefault(v, "1")  # one math thread per worker
    nw = int(os.environ.get("WORKERS", 3 if use_gpu else min(os.cpu_count() or 2, 10)))
    os.makedirs(outdir, exist_ok=True)
    frames = list(range(film.NFR))
    chunks = [(k, frames[s:s + CHUNK]) for k, s in enumerate(range(0, len(frames), CHUNK))]
    print(("GPU" if use_gpu else "CPU"), f"render: {len(frames)} frames, {len(chunks)} batches, {nw} workers", flush=True)
    t0 = time.time(); done = 0
    with Pool(nw, initializer=_init, initargs=(w, h, outdir, crf, ff)) as pool:
        for ci, dt, dev in pool.imap_unordered(_render_chunk, chunks):
            done += 1
            el = time.time() - t0
            print(f"[{done}/{len(chunks)}] batch {ci} in {dt:.0f}s on {dev} | elapsed {el:.0f}s, "
                  f"~{el / done * (len(chunks) - done):.0f}s left", flush=True)
    lst = os.path.join(outdir, "list.txt")
    with open(lst, "w") as f:
        for k, _ in chunks:
            f.write(f"file 'chunk{k:04d}.mp4'\n")
    subprocess.run([ff, "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy",
                    os.path.join(outdir, "video.mp4")], check=True)
    for k, _ in chunks:
        os.remove(os.path.join(outdir, f"chunk{k:04d}.mp4"))
    print(f"done in {time.time() - t0:.0f}s -> {os.path.join(outdir, 'video.mp4')}")
