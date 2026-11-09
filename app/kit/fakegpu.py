"""Strict NumPy stand-in for CuPy: raises when device arrays mix with host ndarrays (like CuPy does)."""
import numpy as _np, types

class Dev(_np.ndarray):
    def __array_ufunc__(self, ufunc, method, *inputs, **kw):
        for x in inputs:
            if type(x) is _np.ndarray and x.ndim >= 1:
                raise TypeError(f"host ndarray mixed into device op {ufunc.__name__} shape={x.shape}")
        inputs = tuple(x.view(_np.ndarray) if isinstance(x, Dev) else x for x in inputs)
        if "out" in kw:
            kw["out"] = tuple(o.view(_np.ndarray) if isinstance(o, Dev) else o for o in kw["out"])
        r = getattr(ufunc, method)(*inputs, **kw)
        return _wrap(r)
    def __array_function__(self, func, types_, args, kwargs):
        if not getattr(func, "_xp_ok", False) and func.__module__.startswith("numpy") and not _ALLOW[0]:
            def chk(a):
                if type(a) is _np.ndarray and a.ndim >= 1:
                    raise TypeError(f"host ndarray mixed into {func.__name__}")
                if isinstance(a, (list, tuple)):
                    for b in a: chk(b)
            for a in args: chk(a)
        return _wrap(super().__array_function__(func, tuple(_np.ndarray if t is Dev else t for t in types_) , _unwrap(args), _unwrap(kwargs)))
    def __setitem__(self, k, v):
        if type(v) is _np.ndarray and v.ndim >= 1:
            raise TypeError("host ndarray assigned into device array")
        _np.ndarray.__setitem__(self.view(_np.ndarray), _unwrap(k), _unwrap(v))
    def __getitem__(self, k):
        return _wrap(_np.ndarray.__getitem__(self.view(_np.ndarray), _unwrap(k)))
    def get(self):
        return _np.array(self.view(_np.ndarray))
    def __array__(self, *a, **k):
        if _ALLOW[0]:
            return self.view(_np.ndarray)
        raise TypeError("implicit device->host conversion (np.asarray on a device array)")

_ALLOW = [False]
def _unwrap(x):
    if isinstance(x, Dev): return x.view(_np.ndarray)
    if isinstance(x, tuple): return tuple(_unwrap(i) for i in x)
    if isinstance(x, list): return [_unwrap(i) for i in x]
    if isinstance(x, dict): return {k: _unwrap(v) for k, v in x.items()}
    return x
def _wrap(r):
    if type(r) is _np.ndarray: return r.view(Dev)
    if isinstance(r, tuple): return tuple(_wrap(i) for i in r)
    if isinstance(r, list): return [_wrap(i) for i in r]
    return r

xp = types.ModuleType("fakecupy")
def _mk(fn):
    def w(*a, **k):
        for x in list(a) + list(k.values()):
            if type(x) is _np.ndarray and x.ndim >= 1 and fn.__name__ not in ("asarray", "array"):
                raise TypeError(f"host ndarray passed to xp.{fn.__name__}")
        return _wrap(fn(*_unwrap(a), **_unwrap(k)))
    return w
for name in dir(_np):
    obj = getattr(_np, name)
    if callable(obj) and not isinstance(obj, type):
        setattr(xp, name, _mk(obj))
    elif not callable(obj):
        setattr(xp, name, obj)
for t in ("float32", "float64", "int32", "int64", "uint8", "bool_"):
    setattr(xp, t, getattr(_np, t))
xp.asarray = lambda a, dtype=None: _np.array(a.view(_np.ndarray) if isinstance(a, Dev) else a, dtype=dtype, copy=True).view(Dev)
class _RS:
    def __init__(self, seed): self.r = _np.random.RandomState(seed)
    def standard_normal(self, size): return self.r.standard_normal(size).view(Dev)
    def random_sample(self, size): return self.r.random_sample(size).view(Dev)
xp.random = types.SimpleNamespace(RandomState=_RS)

import scipy.ndimage as _ndi
ndi = types.SimpleNamespace(correlate1d=lambda x, k, axis, mode: _wrap(_ndi.correlate1d(_unwrap(x), _unwrap(k), axis=axis, mode=mode)) if not (type(x) is _np.ndarray) and not (type(k) is _np.ndarray) else (_ for _ in ()).throw(TypeError("host array into ndi")))
