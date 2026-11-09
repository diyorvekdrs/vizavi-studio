"""Array backend: CuPy on an NVIDIA GPU when available, otherwise NumPy/SciPy.
Force CPU with env RENDER_CPU=1."""
import os
import numpy as np

GPU = False
xp = np
import scipy.ndimage as ndi

if os.environ.get("RENDER_FAKEGPU") == "1":
    import fakegpu as _fg
    xp = _fg.xp; ndi = _fg.ndi; GPU = True
elif os.environ.get("RENDER_CPU") != "1":
    try:
        import cupy as _cp
        if _cp.cuda.runtime.getDeviceCount() > 0:
            _cp.zeros(1).sum()  # make sure kernels actually run
            import cupyx.scipy.ndimage as _cndi
            xp = _cp; ndi = _cndi; GPU = True
    except Exception as e:  # no cupy / no CUDA / driver problem -> CPU
        if os.environ.get("RENDER_VERBOSE"):
            print("GPU unavailable, using CPU:", e)

def asx(a, dtype=None):
    """to backend array"""
    return xp.asarray(a, dtype=dtype) if dtype is not None else xp.asarray(a)

def cpu(a):
    """to numpy"""
    if GPU and type(a) is not np.ndarray:
        return a.get()
    return np.asarray(a)

def device_name():
    if not GPU:
        return "CPU (NumPy)"
    if os.environ.get("RENDER_FAKEGPU") == "1":
        return "fake GPU (strict NumPy)"
    p = xp.cuda.runtime.getDeviceProperties(xp.cuda.Device().id)
    n = p["name"]
    return "GPU: " + (n.decode() if isinstance(n, bytes) else str(n))
