"""Progress/ETA tracking for jobs (no GUI code, testable). A job is a sequence of steps; each step owns
a slice [a, b] of the job's 0..1 progress. ETA comes from the renderer when it knows it, otherwise
from the measured speed of the current step and of the job so far."""
import time


def fmt(sec):
    if sec is None:
        return "…"
    sec = max(0, int(round(sec)))
    if sec < 60:
        return f"{sec}s"
    if sec < 3600:
        return f"{sec // 60}m {sec % 60:02d}s"
    return f"{sec // 3600}h {sec % 3600 // 60:02d}m"


class Tracker:
    def __init__(self):
        self.reset()

    def reset(self):
        self.job = None
        self.t0 = self.ts = None
        self.label, self.detail = "", ""
        self.a, self.b = 0.0, 1.0
        self.frac = 0.0
        self.hint = None          # seconds left in the current step, reported by the tool itself
        self.hint_t = None
        self._eta = None

    def start(self, job, now=None):
        self.reset()
        self.job = job
        self.t0 = self.ts = now or time.time()

    def update(self, frac=None, label=None, detail=None, until=None, eta=None, now=None):
        now = now or time.time()
        if self.t0 is None:
            self.start("job", now)
        if label:
            self.label, self.detail = label, ""
            self.a = frac if frac is not None else self.frac
            self.b = until if until is not None else max(self.a, min(1.0, self.a + 0.0001))
            if until is None:   # step without a declared end: stretch to the next step
                self.b = None
            self.ts, self.hint, self.hint_t, self._eta = now, None, None, None
        if frac is not None:
            self.frac = max(self.frac, min(1.0, frac))
        if detail is not None:
            self.detail = detail
        if eta is not None:
            self.hint, self.hint_t = float(eta), now

    def step_frac(self):
        if self.b is None or self.b - self.a <= 1e-6:
            return None
        return max(0.0, min(1.0, (self.frac - self.a) / (self.b - self.a)))

    def snapshot(self, now=None):
        now = now or time.time()
        if self.t0 is None:
            return None
        el, sel = now - self.t0, now - self.ts
        sf = self.step_frac()
        step_eta = None
        if self.hint is not None:
            step_eta = max(0.0, self.hint - (now - self.hint_t))
        elif sf is not None and sf >= 0.03 and sel >= 2:
            step_eta = sel * (1 - sf) / sf
        f = self.frac
        naive = el * (1 - f) / f if f >= 0.02 and el >= 3 else None
        eta = naive
        if step_eta is not None and self.b is not None:
            before = self.ts - self.t0                       # time spent on earlier steps
            if self.a > 0.01 and before > 0.5:
                rate = before / self.a                       # seconds per unit of progress outside this step
            elif f - self.a > 0.01:
                rate = 0.5 * sel / (f - self.a)              # first step: assume the rest is lighter
            else:
                rate = None
            eta = step_eta + ((1 - self.b) * rate if rate else 0.0)
        if eta is not None:   # smooth jumps (reset at every new step)
            self._eta = eta if self._eta is None else 0.5 * self._eta + 0.5 * eta
            eta = self._eta
        if f >= 0.999:
            eta = 0.0
        return {"job": self.job, "label": self.label, "detail": self.detail, "frac": f, "step_frac": sf,
                "elapsed": el, "step_elapsed": sel, "eta": eta, "step_eta": step_eta}

    def lines(self, now=None):
        s = self.snapshot(now)
        if not s:
            return None
        step = f"{int(s['step_frac'] * 100)}%" if s["step_frac"] is not None else ""
        if s["step_eta"] is not None:
            step += (" · " if step else "") + f"~{fmt(s['step_eta'])} left"
        overall = f"Overall {int(s['frac'] * 100)}% · {fmt(s['elapsed'])} elapsed"
        if s["eta"] is not None and s["frac"] < 0.999:
            overall += f" · ~{fmt(s['eta'])} left"
        detail = s["detail"] + (" · " if s["detail"] else "") + f"{fmt(s['step_elapsed'])} in this step"
        title = f"{int(s['frac'] * 100)}%" + (f" · ~{fmt(s['eta'])} left" if s["eta"] else "")
        return {"step": step, "overall": overall, "detail": detail, "title": title, **s}
