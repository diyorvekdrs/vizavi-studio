"""Loaded before Claude's audio.py runs (python -c "import vzfast; ..."): np.convolve of long signals is computed with
an FFT instead. Same result (to ~1e-12), but seconds instead of minutes - a 0.35 s smoothing window over a 2-minute
48 kHz track took ~8 minutes with plain np.convolve on a Windows PC (and ~9 s on Linux)."""
import runpy
import sys

import numpy as np

_convolve = np.convolve


def convolve(a, v, mode="full"):
    a_, v_ = np.asarray(a), np.asarray(v)
    try:
        big = a_.ndim == 1 and v_.ndim == 1 and min(a_.size, v_.size) > 64 and a_.size * v_.size > 2e7 \
            and np.result_type(a_, v_).kind in "fc"
    except TypeError:
        big = False
    if big:
        from scipy.signal import fftconvolve
        long_, short = (a_, v_) if a_.size >= v_.size else (v_, a_)      # convolution is symmetric; numpy's
        return fftconvolve(long_, short, mode=mode).astype(np.result_type(a_, v_), copy=False)   # 'same' = longer
    return _convolve(a, v, mode)


np.convolve = convolve


def run(script="audio.py"):
    sys.argv = [script]
    runpy.run_path(script, run_name="__main__")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "audio.py")
