"""Shows which device will be used and times one 2K frame (GPU probe runs with a timeout)."""
import os, sys, subprocess, time

probe = ("import cupy as cp, time; t=time.time()\n"
         "n=cp.cuda.runtime.getDeviceProperties(0)['name']; print('  GPU:', n.decode() if isinstance(n, bytes) else n, flush=True)\n"
         "print('  test kernel:', int(cp.arange(5).sum()), f'({time.time()-t:.1f}s)', flush=True)\n")
if os.environ.get("RENDER_CPU") != "1":
    print("probing GPU (timeout 120 s)...", flush=True)
    try:
        r = subprocess.run([sys.executable, "-c", probe], timeout=120, capture_output=True, text=True)
        print(r.stdout.strip())
        if r.returncode != 0:
            print("GPU NOT usable:", (r.stderr.strip().splitlines() or ["?"])[-1])
            os.environ["RENDER_CPU"] = "1"
    except subprocess.TimeoutExpired:
        print("GPU probe hung -> CuPy cannot run kernels.")
        os.environ["RENDER_CPU"] = "1"

import backend, film
print("device used:", backend.device_name(), flush=True)
film.prepare_assets()
film.set_res(2560, 1440)
film.render_frame(film.SELFTEST_FRAMES[0])
t = time.time(); film.render_frame(film.SELFTEST_FRAMES[-1]); print(f"one 2K frame: {time.time() - t:.2f}s")
