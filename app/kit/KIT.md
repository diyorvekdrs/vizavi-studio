# Vizavi render kit (GPU/CPU)

Episode = 4 files written per video, placed next to the kit files:
  film.py   scene/timeline. MUST define: W,H,FPS,NFR, set_res(w,h), render_frame(i)->uint8 (H,W,3) numpy,
            prepare_assets(), SELFTEST_FRAMES=[...2 representative frame indices]
  engine.py renderer helpers (example: camera, lensed sky, stars, blur, tonemap, finish)
  audio.py  writes mix.wav (48 kHz stereo, exact video length; ambient + sparse SFX, NO voice)
  (+ any asset builders, e.g. sky.py, cached into ./cache)

Kit files (reuse as-is):
  backend.py   xp = CuPy on NVIDIA GPU else NumPy; ndi = cupyx/scipy.ndimage; asx() to device, cpu() to host
  render_all.py  GPU self-test (falls back to CPU), batches of 24 frames over WORKERS, progress + ETA, concat
  make_final.py  audio.py -> mix.wav, mux AAC -> final MP4
  check.py     device + seconds per 2K frame
  ff.py        finds ffmpeg (PATH or imageio-ffmpeg)
  fakegpu.py   strict NumPy stand-in for CuPy (RENDER_FAKEGPU=1) to catch host/device mixing without a GPU

GPU-safety rules for episode code:
  - all per-pixel arrays via xp / ndi; convert host data with asx(), results to numpy only with cpu()
  - never mix numpy arrays with xp arrays in one operation; no np.asarray() on device arrays
  - no xp.repeat with an array of counts (use cumsum + searchsorted); cairo/PIL work on numpy, then asx()
  - finish() returns numpy uint8; text overlays drawn after that on host

Local run (Windows, RTX 3060 tested):
  pip install numpy scipy pycairo pillow imageio-ffmpeg cupy-cuda12x
  python render_all.py 2560 out 14
  python make_final.py out <name>.mp4
