/* small helpers shared by the look thumbnails */
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, k) => a + (b - a) * k;
const P = (t, a, b, e) => { const k = clamp((t - a) / (b - a)); return e ? e(k) : k; };
const E = {
  sm: k => k * k * (3 - 2 * k), out: k => 1 - Math.pow(1 - k, 3), in: k => k * k * k,
  io: k => k < .5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2,
  expo: k => k >= 1 ? 1 : 1 - Math.pow(2, -10 * k),
};
/* damped spring over a normalised 0..1 time, `ov` = overshoot (0.1 = 10 %) */
function spring(k, ov = .1) {
  if (k <= 0) return 0; if (k >= 1) return 1;
  const L = Math.log(ov), z = -L / Math.sqrt(Math.PI * Math.PI + L * L), w = 4.6 / z, wd = w * Math.sqrt(1 - z * z);
  return 1 - Math.exp(-z * w * k) * (Math.cos(wd * k) + z * w / wd * Math.sin(wd * k));
}
const SP = (t, a, b, ov) => spring(clamp((t - a) / (b - a)), ov);
function rng(seed) { let s = (seed >>> 0) || 1; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296); }
/* grain: a few noise tiles, picked per frame */
const GRAIN = [];
function grainTile(i) {
  if (!GRAIN[i]) {
    const c = document.createElement('canvas'); c.width = c.height = 256; const x = c.getContext('2d');
    const d = x.createImageData(256, 256), r = rng(11 + i * 7);
    for (let p = 0; p < d.data.length; p += 4) { const v = r() * 255; d.data[p] = d.data[p + 1] = d.data[p + 2] = v; d.data[p + 3] = 255; }
    x.putImageData(d, 0, 0); GRAIN[i] = c;
  }
  return GRAIN[i];
}
function grain(ctx, t, alpha = .06, mode = 'overlay', fps = 24) {
  const tile = grainTile(Math.floor(t * fps) % 6);
  ctx.save(); ctx.globalAlpha = alpha; ctx.globalCompositeOperation = mode;
  ctx.fillStyle = ctx.createPattern(tile, 'repeat'); ctx.fillRect(0, 0, 960, 540); ctx.restore();
}
function rrect(ctx, x, y, w, h, r) {
  r = Math.max(0, Math.min(r, w / 2, h / 2));
  ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}
function off(w = 960, h = 540) { const c = document.createElement('canvas'); c.width = w; c.height = h; return c; }
/* draw a string letter by letter; fn(i, ch, x) decides each letter's transform; returns total width */
function letters(ctx, s, x, y, spacing, fn) {
  let cx = x;
  for (let i = 0; i < s.length; i++) { const ch = s[i], w = ctx.measureText(ch).width; fn(i, ch, cx, w); cx += w + spacing; }
  return cx - x - spacing;
}
function textWidth(ctx, s, spacing) { let w = 0; for (const ch of s) w += ctx.measureText(ch).width + spacing; return w - spacing; }
