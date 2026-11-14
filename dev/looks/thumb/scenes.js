/* Ten look thumbnails, 960×540, each a pure function of t. */
const SCENES = {};

/* ---------------------------------------------------------------- 1 Glow Orb */
SCENES.glow_orb = {
  dur: 4.6, fonts: ['500 34px Outfit'],
  init() {
    const r = rng(5); this.circ = Array.from({ length: 7 }, (_, i) => {
      const a = i / 7 * Math.PI * 2 + r() * .6, d = 300 + r() * 260, z = .25 + r() * .75;
      return { x: 480 + Math.cos(a) * d * 1.25, y: 230 + Math.sin(a) * d * .62, r: 30 + z * 70, z };
    });
  },
  render(c, t) {
    c.fillStyle = '#070304'; c.fillRect(0, 0, 960, 540);
    const exhale = Math.sin(Math.PI * P(t, 2.9, 3.5));
    let r = t < .25 ? lerp(40, 37, P(t, 0, .25, E.sm)) : lerp(37, 62, SP(t, .25, 1.5, .1));
    r *= (1 + .025 * Math.sin(Math.max(0, t - 1.5) * 2.1)) * (1 - .06 * exhale);
    const ox = 480, oy = 215;
    const halo = c.createRadialGradient(ox, oy, r * .6, ox, oy, r * 5.2);
    halo.addColorStop(0, 'rgba(83,24,41,.95)'); halo.addColorStop(.45, 'rgba(19,5,11,.85)'); halo.addColorStop(1, 'rgba(7,3,4,0)');
    c.fillStyle = halo; c.fillRect(0, 0, 960, 540);
    /* drifting outline circles, pushed toward the orb */
    const push = .14 * E.expo(P(t, 0, 4.6));
    for (const k of this.circ) {
      const s = 1 - push * k.z;
      const x = ox + (k.x - ox) * s, y = oy + (k.y - oy) * s;
      c.beginPath(); c.arc(x, y, k.r * (1 + push * k.z * .6), 0, 7);
      c.strokeStyle = `rgba(246,239,242,${(.08 + .3 * k.z).toFixed(3)})`; c.lineWidth = .7 + 1.6 * k.z; c.stroke();
    }
    const og = c.createRadialGradient(ox - r * .25, oy - r * .3, 0, ox, oy, r);
    og.addColorStop(0, '#FBF6F8'); og.addColorStop(.55, '#F9C3EC'); og.addColorStop(1, '#F696DE');
    c.save(); c.shadowColor = 'rgba(246,150,222,.65)'; c.shadowBlur = r * 1.1;
    c.beginPath(); c.arc(ox, oy, r, 0, 7); c.fillStyle = og; c.fill(); c.restore();
    c.beginPath(); c.arc(ox, oy, r, 0, 7); c.strokeStyle = 'rgba(255,255,255,.85)'; c.lineWidth = 1.6; c.stroke();
    /* the rim lifts off as one ring */
    const kr = SP(t, 3.0, 4.0, .1);
    if (t > 3.0) { c.beginPath(); c.arc(ox, oy, r * (1 + kr), 0, 7); c.strokeStyle = 'rgba(251,246,248,.75)'; c.lineWidth = 1.4; c.stroke(); }
    /* one line of type rising letter by letter */
    c.font = '500 34px Outfit'; c.fillStyle = '#F6EFF2'; c.textBaseline = 'alphabetic';
    const s = 'Slow down.', sp = lerp(5, -1, P(t, .6, 2.4, E.out)), w = textWidth(c, s, sp), by = 392;
    c.save(); c.beginPath(); c.rect(0, by - 40, 960, 52); c.clip();
    letters(c, s, 480 - w / 2, by, sp, (i, ch, x) => { const k = SP(t, .6 + i * .085, 1.15 + i * .085, .12); c.fillText(ch, x, by + (1 - k) * 46); });
    c.restore();
    grain(c, t, .07, 'overlay');
  },
};

/* ---------------------------------------------------------------- 2 Frosted Glass */
SCENES.frosted_glass = {
  dur: 5.2, fonts: ['500 24px "Plus Jakarta Sans"', '600 21px "Plus Jakarta Sans"', '400 15px "Plus Jakarta Sans"'],
  init() {
    const b = off(1100, 640), x = b.getContext('2d');
    const sky = x.createLinearGradient(0, 0, 0, 640); sky.addColorStop(0, '#0E2A3D'); sky.addColorStop(.55, '#1F5A6E'); sky.addColorStop(.62, '#2b5d6b'); sky.addColorStop(1, '#0b1d2a');
    x.fillStyle = sky; x.fillRect(0, 0, 1100, 640);
    const glow = (cx, cy, rx, ry, col) => { x.save(); x.translate(cx, cy); x.scale(rx / ry, 1); const g = x.createRadialGradient(0, 0, 0, 0, 0, ry); g.addColorStop(0, col); g.addColorStop(1, 'rgba(0,0,0,0)'); x.fillStyle = g; x.fillRect(-ry, -ry, ry * 2, ry * 2); x.restore(); };
    glow(600, 380, 520, 120, 'rgba(255,138,92,.85)'); glow(220, 300, 300, 160, 'rgba(227,85,138,.55)'); glow(900, 200, 260, 180, 'rgba(31,90,110,.7)');
    const r = rng(9);
    for (let i = 0; i < 70; i++) { const px = 200 + r() * 760, py = 385 + r() * 30; x.fillStyle = `rgba(255,${200 + r() * 55 | 0},${150 + r() * 80 | 0},${.5 + r() * .5})`; x.beginPath(); x.arc(px, py, 1.5 + r() * 3, 0, 7); x.fill(); }
    for (let i = 0; i < 9; i++) { const px = r() * 1100, py = 120 + r() * 420, rr = 30 + r() * 60; x.fillStyle = `rgba(255,${170 + r() * 60 | 0},${140 + r() * 60 | 0},${.08 + r() * .12})`; x.beginPath(); x.arc(px, py, rr, 0, 7); x.fill(); }
    const v = x.createRadialGradient(550, 320, 200, 550, 320, 700); v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,.55)'); x.fillStyle = v; x.fillRect(0, 0, 1100, 640);
    const blur = (px, smoke) => { const o = off(1100, 640), y = o.getContext('2d'); y.filter = `blur(${px}px)`; y.drawImage(b, 0, 0); y.filter = 'none'; if (smoke) { y.fillStyle = smoke; y.fillRect(0, 0, 1100, 640); } return o; };
    this.bg = blur(14); this.glass = blur(46, 'rgba(14,30,42,.32)');
  },
  render(c, t) {
    const dx = -60 - t * 4, dy = -50;
    c.drawImage(this.bg, dx, dy);
    const ks = SP(t, 0, .7, .08), bs = lerp(.9, 1, ks);
    const up = SP(t, 2.05, 2.75, .06), barY = lerp(150, 92, up), BW = 816, BH = 84, BX = 72;
    const glassAt = (x, y, w, h, r, sc = 1) => {
      c.save(); c.translate(480, y + h / 2); c.scale(sc, sc); c.translate(-480, -(y + h / 2));
      c.save(); c.shadowColor = 'rgba(0,0,0,.45)'; c.shadowBlur = 40; c.shadowOffsetY = 18; rrect(c, x, y, w, h, r); c.fillStyle = 'rgba(10,20,30,.4)'; c.fill(); c.restore();
      c.save(); rrect(c, x, y, w, h, r); c.clip(); c.drawImage(this.glass, dx, dy);
      const ig = c.createLinearGradient(x, y, x, y + h); ig.addColorStop(0, 'rgba(255,255,255,.10)'); ig.addColorStop(1, 'rgba(255,255,255,.03)'); c.fillStyle = ig; c.fillRect(x, y, w, h); c.restore();
      rrect(c, x + .5, y + .5, w - 1, h - 1, r); const rg = c.createLinearGradient(x, y, x + w * .6, y + h); rg.addColorStop(0, 'rgba(255,255,255,.75)'); rg.addColorStop(.4, 'rgba(255,255,255,.18)'); rg.addColorStop(1, 'rgba(255,255,255,.08)');
      c.strokeStyle = rg; c.lineWidth = 1.5; c.stroke();
      c.restore();
    };
    /* results panel unfolds from behind the bar */
    const kp = SP(t, 2.25, 3.0, .09), PH = 3 * 72 + 24, rows = ['Hook in three seconds', 'Show, then tell', 'End on one line'], labs = ['first impression', 'proof before claims', 'the line they repeat'];
    if (t > 2.25) {
      const py = barY + BH + 14, ph = Math.max(10, PH * kp);
      glassAt(BX, py, BW, ph, 22);
      c.save(); rrect(c, BX, py, BW, ph, 22); c.clip();
      const hlRow = t < 3.7 ? 0 : 1, kh = SP(t, 3.7, 4.15, .1), kh2 = SP(t, 3.7, 4.45, .04);
      const top = py + 12 + lerp(0, 72, kh) * (t >= 3.7 ? 1 : 0), bot = py + 12 + 72 + lerp(0, 72, kh2) * (t >= 3.7 ? 1 : 0);
      if (t > 3.15) { const press = 1 - .02 * Math.sin(Math.PI * P(t, 4.5, 4.7)); c.save(); c.translate(480, (top + bot) / 2); c.scale(press, press); c.translate(-480, -(top + bot) / 2);
        rrect(c, BX + 14, top, BW - 28, bot - top, 14); c.fillStyle = `rgba(255,255,255,${(.16 * P(t, 3.15, 3.35)).toFixed(3)})`; c.fill(); c.restore(); }
      rows.forEach((s, i) => {
        const k = SP(t, 2.45 + i * .1, 2.95 + i * .1, .1), y = py + 12 + i * 72 + (1 - k) * -24;
        c.globalAlpha = clamp(k * 4);
        rrect(c, BX + 30, y + 14, 44, 44, 12); c.fillStyle = 'rgba(255,255,255,.14)'; c.fill(); c.strokeStyle = 'rgba(255,255,255,.35)'; c.lineWidth = 1; c.stroke();
        c.fillStyle = '#F8F9FB'; c.font = '600 21px "Plus Jakarta Sans"'; c.fillText(s, BX + 92, y + 34);
        c.globalAlpha *= .65; c.font = '400 15px "Plus Jakarta Sans"'; c.fillText(labs[i], BX + 92, y + 54); c.globalAlpha = 1;
      });
      if (t > 4.55) { const kk = SP(t, 4.55, 4.9, .15); c.save(); c.translate(BX + BW - 60, py + 12 + 72 + 36); c.scale(kk, kk); rrect(c, -18, -16, 36, 32, 8); c.fillStyle = 'rgba(255,255,255,.25)'; c.fill(); c.fillStyle = '#fff'; c.font = '600 18px "Plus Jakarta Sans"'; c.textAlign = 'center'; c.fillText('↵', 0, 6); c.restore(); }
      c.restore();
    }
    glassAt(BX, barY, BW, BH, 42, bs);
    /* human typing */
    const q = 'best way to open a video', r = rng(3); let tt = .55, n = 0;
    for (let i = 0; i < q.length; i++) { tt += .043 + r() * .02 + (q[i] === ' ' ? .06 : 0); if (t >= tt) n = i + 1; }
    c.save(); c.translate(480, barY + BH / 2); c.scale(bs, bs); c.translate(-480, -(barY + BH / 2));
    c.font = '500 24px "Plus Jakarta Sans"'; c.fillStyle = '#F8F9FB'; c.shadowColor = 'rgba(0,0,0,.35)'; c.shadowBlur = 6;
    c.globalAlpha = .55; c.beginPath(); c.arc(BX + 44, barY + 40, 10, 0, 7); c.moveTo(BX + 51, barY + 47); c.lineTo(BX + 58, barY + 54); c.strokeStyle = '#F8F9FB'; c.lineWidth = 2.4; c.stroke(); c.globalAlpha = 1;
    const shown = q.slice(0, n); c.fillText(shown, BX + 76, barY + 51);
    const cx = BX + 76 + c.measureText(shown).width + 3, blink = n < q.length || Math.floor(t * 2) % 2 === 0;
    c.shadowBlur = 0; if (blink) { c.fillStyle = '#9FD8FF'; c.fillRect(cx, barY + 28, 2.5, 30); }
    c.restore();
    grain(c, t, .05, 'overlay');
  },
};

/* ---------------------------------------------------------------- 3 Apple One-Take */
SCENES.one_take = {
  dur: 5.2, fonts: ['700 150px "Inter Tight"', '600 22px "Inter Tight"'],
  render(c, t) {
    c.fillStyle = '#EEEEEC'; c.fillRect(0, 0, 960, 540);
    const INK = '#111113', RED = '#FF3B30';
    c.font = '700 150px "Inter Tight"';
    const gw = c.measureText('G').width, ow = c.measureText('o').width, dw = c.measureText('.').width, sp = -6;
    const total = gw + ow + dw + 2 * sp, x0 = 480 - total / 2, base = 330;
    const oc = { x: x0 + gw + sp + ow / 2, y: base - 150 * .27, r: ow * .43 }, dot = { x: x0 + gw + ow + 2 * sp + dw / 2, y: base - 11, r: 12 };
    const shadow = (x, y, w, h, r, k) => { if (k <= 0) return; c.save(); rrect(c, x, y, w, h, r);
      c.shadowColor = `rgba(17,17,19,${(.10 * k).toFixed(3)})`; c.shadowBlur = 8; c.shadowOffsetY = 2; c.fillStyle = 'rgba(0,0,0,0)'; c.fill();
      c.shadowColor = `rgba(17,17,19,${(.14 * k).toFixed(3)})`; c.shadowBlur = 50; c.shadowOffsetY = 24; c.fill(); c.restore(); };
    /* state machine of one carrier object */
    let R, fill = INK, inner = 0, label = 0, content = 0, bezel = 0, sh = 1, dotP = null;
    const kPill = SP(t, .35, 1.0, .1), kOpen = SP(t, 1.55, 2.3, .05), kPhone = SP(t, 2.35, 3.05, .05), kBack = P(t, 3.15, 4.15);
    const pill = { x: 480, y: 270, w: lerp(24, 220, kPill), h: lerp(24, 64, kPill), r: 32 };
    if (t < 1.55) { R = pill; label = P(t, .75, 1.0); }
    else if (t < 2.35) { R = { x: 480, y: 270, w: lerp(220, 330, kOpen), h: lerp(64, 220, kOpen), r: lerp(32, 26, kOpen) }; inner = kOpen; content = P(t, 1.75, 2.1); }
    else if (t < 3.15) { R = { x: 480, y: 270, w: lerp(330, 170, kPhone), h: lerp(220, 340, kPhone), r: lerp(26, 30, kPhone) }; inner = 1; content = 1; bezel = kPhone; }
    else { const s = Math.pow(2, -6 * kBack) * (1 - kBack) + kBack * 0; const k = 1 - Math.pow(1 - kBack, 3);
      R = { x: lerp(480, oc.x, k), y: lerp(270, oc.y, k), w: lerp(170, oc.r * 2, k), h: lerp(340, oc.r * 2, k), r: lerp(30, oc.r, k) }; inner = 1; content = 1 - P(t, 3.15, 3.5); bezel = 1; sh = 1 - P(t, 3.4, 3.9); }
    const press = 1 - .06 * Math.sin(Math.PI * P(t, 1.3, 1.5));
    const x = R.x - R.w / 2 * press, y = R.y - R.h / 2 * press, w = R.w * press, h = R.h * press;
    shadow(x, y, w, h, R.r, sh);
    if (inner <= 0) { rrect(c, x, y, w, h, R.r); c.fillStyle = INK; c.fill(); }
    else {
      /* black floods to white: the dark edge thins from the inside out */
      const edge = lerp(h / 2, bezel ? Math.max(7, (t > 3.15 ? oc.r * .32 * P(t, 3.15, 4.15) + 7 * (1 - P(t, 3.15, 4.15)) : 7)) : 0, Math.min(1, inner * 1.4));
      rrect(c, x, y, w, h, R.r); c.fillStyle = INK; c.fill();
      const e = Math.max(0, Math.min(edge, Math.min(w, h) / 2 - .5));
      rrect(c, x + e, y + e, w - 2 * e, h - 2 * e, Math.max(0, R.r - e)); c.fillStyle = t > 3.2 ? `rgba(238,238,236,${P(t, 3.2, 3.6)})` : '#FBFBF9'; c.fill();
      if (t > 3.2 && t < 3.6) { rrect(c, x + e, y + e, w - 2 * e, h - 2 * e, Math.max(0, R.r - e)); c.fillStyle = `rgba(251,251,249,${1 - P(t, 3.2, 3.6)})`; c.fill(); }
      if (content > 0) {
        c.save(); rrect(c, x + e, y + e, w - 2 * e, h - 2 * e, Math.max(0, R.r - e)); c.clip(); c.globalAlpha = content;
        const pad = Math.max(10, e + 12), tw = w - 2 * pad, th = Math.min(h * .42, tw * .62);
        const g = c.createLinearGradient(x + pad, y + pad, x + pad + tw, y + pad + th); g.addColorStop(0, '#9CC3FF'); g.addColorStop(1, '#3E7BFA');
        rrect(c, x + pad, y + pad + 18, tw, th, 12); c.fillStyle = g; c.fill();
        c.fillStyle = 'rgba(17,17,19,.75)'; rrect(c, x + pad, y + pad + th + 34, tw * .7, 12, 6); c.fill();
        c.fillStyle = 'rgba(17,17,19,.3)'; rrect(c, x + pad, y + pad + th + 56, tw * .45, 10, 5); c.fill();
        c.restore();
      }
    }
    if (label > 0 && t < 1.6) { c.save(); c.globalAlpha = label * (1 - P(t, 1.5, 1.6)); c.fillStyle = '#FBFBF9'; c.font = '600 22px "Inter Tight"'; c.textAlign = 'center'; c.fillText('Start', R.x + 12, R.y + 8); c.restore(); }
    /* the red dot survives every state and lands as the full stop */
    let dp;
    if (t < .35) dp = { x: 480, y: 270, r: lerp(0, 12, SP(t, 0, .35, .1)) };
    else if (t < 1.55) dp = { x: pill.x - pill.w / 2 * press + 32, y: 270, r: 9 };
    else if (t < 3.15) dp = { x: x + Math.max(20, w * .09) + 4, y: y + 22, r: 7 };
    else { const k = SP(t, 3.6, 4.3, .1); dp = { x: lerp(x + 24, dot.x, k), y: lerp(y + 22, dot.y, k) - Math.sin(Math.PI * clamp(k)) * 60, r: lerp(7, dot.r, k) }; }
    c.beginPath(); c.arc(dp.x, dp.y, dp.r, 0, 7); c.fillStyle = RED; c.fill();
    /* pointer presses the pill */
    if (t > .95 && t < 1.75) { const k = SP(t, .95, 1.3, .06), px = lerp(640, 500, k), py = lerp(380, 282, k), a = 1 - P(t, 1.55, 1.75);
      c.save(); c.globalAlpha = a; c.translate(px, py); c.beginPath(); c.moveTo(0, 0); c.lineTo(0, 26); c.lineTo(7, 20); c.lineTo(12, 31); c.lineTo(17, 29); c.lineTo(12, 18); c.lineTo(21, 18); c.closePath();
      c.shadowColor = 'rgba(0,0,0,.25)'; c.shadowBlur = 8; c.shadowOffsetY = 3; c.fillStyle = '#fff'; c.fill(); c.shadowColor = 'transparent'; c.strokeStyle = INK; c.lineWidth = 1.5; c.stroke(); c.restore(); }
    /* the closing line grows around the ring */
    if (t > 3.55) { c.save(); c.font = '700 150px "Inter Tight"'; c.fillStyle = INK; c.beginPath(); c.rect(0, base - 160, 960, 192); c.clip();
      const k = SP(t, 3.6, 4.2, .1); c.fillText('G', x0, base + (1 - k) * 170); c.restore(); }
  },
};

/* ---------------------------------------------------------------- 4 Retro CRT Glow */
SCENES.crt_glow = {
  dur: 4.8, fonts: ['700 70px Syncopate', '400 20px "Share Tech Mono"'],
  init() {
    const pic = off(), x = pic.getContext('2d');
    const core = off(), y = core.getContext('2d');
    y.font = '700 74px Syncopate'; y.textAlign = 'center'; y.fillStyle = '#FCFBF8'; y.letterSpacing = '4px';
    y.fillText('COMING', 480, 230); y.fillText('SOON', 480, 316);
    for (const [b, a] of [[40, .55], [14, .7], [4, .9]]) { x.filter = `blur(${b}px)`; x.globalAlpha = a; x.drawImage(core, 0, 0); }
    x.filter = 'none'; x.globalAlpha = 1; x.globalCompositeOperation = 'source-in'; x.fillStyle = '#FF9A90'; x.fillRect(0, 0, 960, 540);
    x.globalCompositeOperation = 'source-over'; x.drawImage(core, 0, 0);
    this.pic = pic;
  },
  render(c, t) {
    c.fillStyle = '#07090F'; c.fillRect(0, 0, 960, 540);
    const lift = c.createRadialGradient(480, 270, 50, 480, 270, 520); lift.addColorStop(0, '#0B0E16'); lift.addColorStop(1, '#07090F'); c.fillStyle = lift; c.fillRect(0, 0, 960, 540);
    const exitK = P(t, 4.2, 4.5, E.in), open = t < 4.2 ? SP(t, .18, .65, .1) : 1 - exitK;
    const hot = 1 - P(t, .35, .95);
    if (open > .001) {
      const h = 540 * open;
      c.save(); c.beginPath(); c.rect(0, 270 - h / 2, 960, h); c.clip();
      c.translate(480, 270); c.scale(1 + Math.sin(t * 40) * .004 * hot, open); c.translate(-480, -270);
      c.globalAlpha = 1; c.filter = `brightness(${(1 + .5 * hot + .01 * Math.sin(t * 50)).toFixed(3)})`;
      c.drawImage(this.pic, -1.5 * (1 + 3 * hot), 0); c.filter = 'none';
      c.globalCompositeOperation = 'lighter'; c.globalAlpha = .12 + .2 * hot; c.drawImage(this.pic, 2 * (1 + 3 * hot), 0); c.globalCompositeOperation = 'source-over'; c.globalAlpha = 1;
      /* system line types in behind a block cursor */
      c.font = '400 20px "Share Tech Mono"'; const sys = 'CH 03  ·  ON AIR', n = Math.floor(clamp((t - 1.0) / .05, 0, sys.length));
      c.fillStyle = 'rgba(252,251,248,.82)'; const sx = 380; c.fillText(sys.slice(0, n), sx + 20, 372);
      const cx = sx + 20 + c.measureText(sys.slice(0, n)).width + 3, done = n >= sys.length;
      if (!done || Math.floor(t * 2.2) % 2 === 0) { c.fillStyle = 'rgba(252,251,248,.85)'; c.fillRect(cx, 356, 10, 19); }
      if (done) { const k = SP(t, 1.0 + sys.length * .05, 1.3 + sys.length * .05, .2); c.beginPath(); c.arc(sx + 6, 366, 5 * k, 0, 7); c.fillStyle = '#F05A4A'; c.fill(); }
      /* hum bar */
      const hy = ((t * 70) % 700) - 80; const hb = c.createLinearGradient(0, hy - 60, 0, hy + 60); hb.addColorStop(0, 'rgba(255,240,235,0)'); hb.addColorStop(.5, 'rgba(255,240,235,.05)'); hb.addColorStop(1, 'rgba(255,240,235,0)'); c.fillStyle = hb; c.fillRect(0, hy - 60, 960, 120);
      c.restore();
    }
    /* the bright line / converging edges */
    if (t < .3 || t > 4.2) {
      const sw = t < .3 ? lerp(1.5, 5, P(t, 0, .18)) * (1 - P(t, .18, .3)) + .1 : lerp(1, 4, exitK) * (1 - P(t, 4.5, 4.8) * .7);
      const wid = t > 4.5 ? 960 * (1 - .6 * P(t, 4.5, 4.8)) : 960;
      const g = c.createLinearGradient(480 - wid / 2, 0, 480 + wid / 2, 0); g.addColorStop(0, 'rgba(255,154,144,0)'); g.addColorStop(.2, 'rgba(255,230,225,.9)'); g.addColorStop(.8, 'rgba(255,230,225,.9)'); g.addColorStop(1, 'rgba(255,154,144,0)');
      c.save(); c.shadowColor = '#FF9A90'; c.shadowBlur = 20; c.fillStyle = g; c.fillRect(480 - wid / 2, 270 - sw, wid, sw * 2); c.restore();
    }
    if (t > .18 && t < .7) { const e = 270 * open; c.save(); c.shadowColor = '#FF9A90'; c.shadowBlur = 16; c.fillStyle = 'rgba(255,240,235,.8)'; c.fillRect(0, 270 - e - 1.5, 960, 3); c.fillRect(0, 270 + e - 1.5, 960, 3); c.restore(); }
    /* scanlines, snow, vignette into a rounded tube */
    c.fillStyle = 'rgba(0,0,0,.28)'; for (let y = 0; y < 540; y += 3) c.fillRect(0, y, 960, 1);
    grain(c, t, .07, 'screen', 30);
    const v = c.createRadialGradient(480, 270, 260, 480, 270, 600); v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,.92)'); c.fillStyle = v; c.fillRect(0, 0, 960, 540);
    const sh = c.createLinearGradient(0, 0, 960, 540); sh.addColorStop(.25, 'rgba(255,255,255,0)'); sh.addColorStop(.32, 'rgba(255,255,255,.035)'); sh.addColorStop(.4, 'rgba(255,255,255,0)'); c.fillStyle = sh; c.fillRect(0, 0, 960, 540);
    c.save(); c.globalCompositeOperation = 'destination-in'; rrect(c, 14, 10, 932, 520, 60); c.fillStyle = '#000'; c.fill(); c.restore();
    c.save(); c.globalCompositeOperation = 'destination-over'; c.fillStyle = '#020305'; c.fillRect(0, 0, 960, 540); c.restore();
  },
};

/* ---------------------------------------------------------------- 5 Oscilloscope */
const GLY = { /* monoline capitals: start and end on the baseline (x 0..1, y 0 = baseline, 1 = cap height) */
  H: [[0, 0], [0, 1], [0, .5], [.75, .5], [.75, 1], [.75, 0]],
  E: [[0, 0], [0, 1], [.7, 1], [0, 1], [0, .5], [.55, .5], [0, .5], [0, 0], [.7, 0]],
  L: [[0, 0], [0, 1], [0, 0], [.65, 0]],
  O: Array.from({ length: 25 }, (_, i) => { const a = Math.PI / 2 + i / 24 * Math.PI * 2; return [.42 - Math.cos(a) * .42 * -1 + 0, .5 - Math.sin(a) * .5]; }),
};
SCENES.oscilloscope = {
  dur: 5.0, fonts: ['400 16px "Share Tech Mono"'],
  trace(t) {
    const N = 360, pts = [];
    const lock = 1 - P(t, 0, 1.1, E.out), phase = t * 9 * lock + 2.2;
    const m = P(t, 1.15, 1.75, E.io) * (1 - P(t, 2.35, 2.85, E.io));
    const ring = t < 2.8 ? 1 : Math.exp(-(t - 2.8) * 4.2) * Math.cos((t - 2.8) * 15);
    const amp = 92 * ring, rot = (t - 1.2) * .9;
    for (let i = 0; i <= N; i++) {
      const s = i / N, x = -30 + 1020 * s, y = 270 - amp * Math.sin(s * Math.PI * 2 * 3 - phase);
      const lx = 480 + 150 * Math.sin(2 * Math.PI * 2 * s + rot), ly = 270 - 150 * Math.sin(2 * Math.PI * 3 * s);
      pts.push([lerp(x, lx, m), lerp(y, ly, m)]);
    }
    if (t < 3.25) return pts;
    /* letters rise out of the flat line, left to right */
    const word = 'HELLO', capH = 100, gap = 34, wid = { H: .75, E: .7, L: .65, O: .84 };
    let tw = 0; for (const ch of word) tw += wid[ch] * capH * 1.0 + gap; tw -= gap;
    const out = [[-30, 270]]; let x = 480 - tw / 2;
    [...word].forEach((ch, i) => {
      const k = SP(t, 3.3 + i * .11, 3.85 + i * .11, .12);
      out.push([x, 270]);
      for (const [gx, gy] of GLY[ch]) out.push([x + gx * capH, 270 - gy * capH * k]);
      x += wid[ch] * capH; out.push([x, 270]); x += gap;
    });
    out.push([990, 270]); return out;
  },
  draw(c, pts, a) {
    const path = () => { c.beginPath(); pts.forEach(([x, y], i) => i ? c.lineTo(x, y) : c.moveTo(x, y)); };
    c.lineJoin = 'round'; c.lineCap = 'round';
    path(); c.strokeStyle = `rgba(70,255,140,${.18 * a})`; c.lineWidth = 10; c.stroke();
    path(); c.strokeStyle = `rgba(70,255,140,${.75 * a})`; c.lineWidth = 3.4; c.stroke();
    path(); c.strokeStyle = `rgba(215,255,243,${a})`; c.lineWidth = 1.3; c.stroke();
  },
  render(c, t) {
    c.fillStyle = '#030805'; c.fillRect(0, 0, 960, 540);
    const lift = c.createRadialGradient(480, 270, 30, 480, 270, 520); lift.addColorStop(0, '#09150E'); lift.addColorStop(1, '#030805'); c.fillStyle = lift; c.fillRect(0, 0, 960, 540);
    /* graticule fading toward the edges */
    const gr = off(), g = gr.getContext('2d'); g.strokeStyle = '#123822'; g.lineWidth = 1;
    for (let x = 480 % 80; x < 960; x += 80) { g.beginPath(); g.moveTo(x + .5, 0); g.lineTo(x + .5, 540); g.stroke(); }
    for (let y = 270 % 80; y < 540; y += 80) { g.beginPath(); g.moveTo(0, y + .5); g.lineTo(960, y + .5); g.stroke(); }
    for (let x = 480 % 16; x < 960; x += 16) g.fillRect.call(g, 0, 0, 0, 0), g.beginPath(), g.moveTo(x + .5, 266), g.lineTo(x + .5, 274), g.stroke();
    for (let y = 270 % 16; y < 540; y += 16) g.beginPath(), g.moveTo(476, y + .5), g.lineTo(484, y + .5), g.stroke();
    g.globalCompositeOperation = 'destination-in'; const m = g.createRadialGradient(480, 270, 120, 480, 270, 470); m.addColorStop(0, '#000'); m.addColorStop(1, 'rgba(0,0,0,0)'); g.fillStyle = m; g.fillRect(0, 0, 960, 540);
    c.drawImage(gr, 0, 0);
    c.save(); c.shadowColor = '#46FF8C'; c.shadowBlur = 14;
    for (const [d, a] of [[.1, .12], [.066, .22], [.033, .4]]) this.draw(c, this.trace(Math.max(0, t - d)), a);
    this.draw(c, this.trace(t), 1); c.restore();
    c.font = '400 16px "Share Tech Mono"'; c.fillStyle = 'rgba(70,255,140,.55)'; c.textAlign = 'center'; c.fillText('CH1  0.5 V/div   ·   2 ms', 480, 470);
    grain(c, t, .05, 'screen', 30);
  },
};

/* ---------------------------------------------------------------- 6 Magazine Layout and Note */
SCENES.magazine_note = {
  dur: 5.2, fonts: ['400 66px "Bodoni Moda"', 'italic 400 66px "Bodoni Moda"', '400 14px Newsreader', 'italic 400 13px Newsreader', '400 34px "La Belle Aurore"'],
  init() {
    const p = off(420, 260), x = p.getContext('2d');
    const sky = x.createLinearGradient(0, 0, 0, 150); sky.addColorStop(0, '#2c3752'); sky.addColorStop(1, '#a9b4c4'); x.fillStyle = sky; x.fillRect(0, 0, 420, 150);
    x.fillStyle = '#E2E7EC'; x.beginPath(); x.arc(250, 118, 26, 0, 7); x.fill();
    x.fillStyle = 'rgba(52,64,92,.85)'; for (let i = 0; i < 6; i++) { x.beginPath(); x.ellipse(120 + i * 50, 108 + (i % 2) * 6, 70, 9, 0, 0, 7); x.fill(); }
    x.fillStyle = 'rgba(36,46,70,.55)'; x.beginPath(); x.ellipse(90, 50, 110, 14, -.05, 0, 7); x.fill(); x.beginPath(); x.ellipse(330, 64, 90, 10, .04, 0, 7); x.fill();
    const sea = x.createLinearGradient(0, 150, 0, 260); sea.addColorStop(0, '#5c6a84'); sea.addColorStop(1, '#242E46'); x.fillStyle = sea; x.fillRect(0, 150, 420, 110);
    const r = rng(8); for (let i = 0; i < 160; i++) { const yy = 152 + Math.pow(r(), 1.6) * 105, spread = 6 + (yy - 150) * .9; x.fillStyle = `rgba(226,231,236,${(.35 + r() * .5).toFixed(2)})`; x.fillRect(250 + (r() - .5) * spread * 2, yy, 3 + r() * 9, 1.2); }
    const gi = x.getImageData(0, 0, 420, 260); for (let i = 0; i < gi.data.length; i += 4) { const n = (r() - .5) * 22; gi.data[i] += n; gi.data[i + 1] += n; gi.data[i + 2] += n; } x.putImageData(gi, 0, 0);
    this.photo = p;
  },
  render(c, t) {
    c.fillStyle = '#EAEDED'; c.fillRect(0, 0, 960, 540);
    const INK = '#1B1E25';
    const rise = (txt, font, x, y, t0, size, color = INK) => { const k = SP(t, t0, t0 + .5, .1); c.save(); c.beginPath(); c.rect(x - 10, y - size * 1.05, 900, size * 1.35); c.clip(); c.font = font; c.fillStyle = color; c.fillText(txt, x, y + (1 - k) * size * 1.2); c.restore(); };
    c.fillStyle = INK; c.fillRect(60, 56, 840 * (t < 0 ? 0 : 1), 1.4);
    c.font = '400 11px Newsreader'; c.fillStyle = INK; c.globalAlpha = .7; c.fillText('ISSUE 07  ·  ESSAYS', 60, 46); c.globalAlpha = 1;
    rise('The quiet', '400 66px "Bodoni Moda"', 60, 128, -.2, 66);
    rise('season.', 'italic 400 66px "Bodoni Moda"', 140, 190, .05, 66);
    /* photo opens upward like a blind and settles out of a push */
    const kp = SP(t, .35, 1.15, .06), ph = 230 * kp, px = 60, py = 222, pw = 400;
    c.save(); c.beginPath(); c.rect(px, py + 230 - ph, pw, ph); c.clip();
    const s = lerp(1.1, 1.0, SP(t, .35, 1.6, .03)) + .01 * P(t, 1.6, 5.2);
    c.translate(px + pw / 2, py + 115); c.scale(s, s); c.drawImage(this.photo, -210, -130); c.restore();
    rise('Low tide, early October.', 'italic 400 13px Newsreader', 60, 474, 1.0, 13, 'rgba(27,30,37,.8)');
    const body = ['Some places only make sense', 'when nobody is looking at', 'them. The coast after the', 'crowds is one of those: the', 'light goes flat, the water', 'goes quiet, and you start', 'to notice the small things.'];
    body.forEach((l, i) => rise(l, '400 14px Newsreader', 500, 240 + i * 22, .55 + i * .06, 14));
    /* the note writes itself, then an arrow with a small loop */
    const note = 'read this twice', t0 = 2.0, rate = 8;
    c.save(); c.translate(560, 438); c.rotate(-7 * Math.PI / 180); c.font = '400 34px "La Belle Aurore"'; c.fillStyle = '#C42E26';
    letters(c, note, 0, 0, 0, (i, ch, x, w) => { const a = t0 + i / rate + (note.slice(0, i).split(' ').length - 1) * .12, k = P(t, a, a + 1 / rate);
      if (k <= 0) return; c.save(); c.beginPath(); c.rect(x - 4, -40, (w + 8) * k, 60); c.clip(); c.fillText(ch, x, 0); c.restore(); });
    c.restore();
    const ka = P(t, 4.05, 4.6, E.io);
    if (ka > 0) {
      const pts = []; for (let i = 0; i <= 60; i++) { const s = i / 60; const bx = lerp(552, 420, s), by = lerp(446, 420, s) + Math.sin(s * Math.PI) * 26;
        const loop = s > .35 && s < .6 ? (s - .35) / .25 : -1; const lx = loop >= 0 ? Math.cos(loop * Math.PI * 2) * 12 - 12 : 0, ly = loop >= 0 ? Math.sin(loop * Math.PI * 2) * 12 : 0; pts.push([bx + lx, by + ly]); }
      const n = Math.floor(pts.length * ka); c.beginPath(); pts.slice(0, n + 1).forEach(([x, y], i) => i ? c.lineTo(x, y) : c.moveTo(x, y)); c.strokeStyle = '#C42E26'; c.lineWidth = 2; c.lineCap = 'round'; c.stroke();
      if (t > 4.65) { const [ex, ey] = pts[pts.length - 1]; c.beginPath(); c.moveTo(ex + 14, ey - 4); c.lineTo(ex, ey); c.lineTo(ex + 10, ey + 11); c.stroke(); }
    }
    grain(c, t, .07, 'multiply', 1);
  },
};

/* ---------------------------------------------------------------- 7 Blue Editorial */
SCENES.blue_editorial = {
  dur: 4.6, fonts: ['italic 400 200px "Instrument Serif"', '900 30px "Schibsted Grotesk"'],
  render(c, t) {
    const W = '#F4F5FA'; c.fillStyle = '#2433F0'; c.fillRect(0, 0, 960, 540);
    const ital = s => `italic 400 ${s}px "Instrument Serif"`, grot = s => `900 ${s}px "Schibsted Grotesk"`;
    const rule = (x0, x1, y, t0) => { const k = P(t, t0, t0 + .25, E.out); if (k > 0) { c.fillStyle = 'rgba(244,245,250,.55)'; c.fillRect(x0, y, (x1 - x0) * k, 2); } };
    /* beat 1: "make" huge, then snaps down to a kicker with motion blur */
    const snap = P(t, .75, 1.02, E.io);
    if (snap < 1) {
      c.save(); c.font = ital(250); c.fillStyle = W; c.beginPath(); c.rect(0, 0, 960, 380); c.clip();
      const sz = lerp(250, 30, snap), x = lerp(150, 120, snap), y = lerp(330, 74, snap);
      for (let g = snap > 0 && snap < 1 ? 4 : 0; g >= 0; g--) {
        const gs = clamp(snap - g * .06), gsz = lerp(250, 30, gs); c.globalAlpha = g ? .18 : 1; c.font = ital(gsz);
        letters(c, 'make', lerp(150, 120, gs), lerp(330, 74, gs), -gsz * .03, (i, ch, lx) => { const k = SP(t, i * .07, .45 + i * .07, .1); c.fillText(ch, lx, lerp(330, 74, gs) + (1 - k) * gsz * (snap > 0 ? 0 : 1)); });
      }
      c.restore();
    } else { c.font = grot(30); c.fillStyle = W; c.fillText('make', 120, 74); }
    rule(120, 840, 86, .95);
    /* beat 2: "every" revealed by a slanted wipe with a line on its edge */
    const kw = P(t, 1.1, 1.55, E.io);
    if (kw > 0) {
      c.save(); const ex = lerp(80, 920, kw); c.beginPath(); c.moveTo(0, 0); c.lineTo(ex + 60, 0); c.lineTo(ex - 60, 540); c.lineTo(0, 540); c.closePath(); c.clip();
      c.font = ital(210); c.fillStyle = W; c.fillText('every', 112, 262); c.restore();
      if (kw < 1) { c.strokeStyle = W; c.lineWidth = 2; c.beginPath(); c.moveTo(ex + 60 * (1 - kw), 86 + 0); c.lineTo(ex - 60 * (1 - kw) + 0, 300); c.stroke(); }
    }
    /* beat 3: "second" slides out from under "every" */
    const ks = SP(t, 1.75, 2.25, .1);
    if (ks > 0) { c.save(); c.beginPath(); c.rect(0, 272, 960, 60); c.clip(); c.font = grot(30); c.fillStyle = W; c.textAlign = 'right'; c.fillText('second', 840, 312 - (1 - ks) * 46); c.restore(); }
    rule(680, 840, 322, 1.9);
    /* beat 4: "count" in four slices from alternating sides, off-register, then locked */
    if (t > 2.4) {
      c.font = ital(210); const slices = 4, top = 330, h = 170;
      for (let i = 0; i < slices; i++) {
        const k = SP(t, 2.4 + i * .06, 2.9 + i * .06, .08), dir = i % 2 ? 1 : -1, lock = t > 3.15 ? 0 : 1;
        const xo = (1 - k) * dir * 700 + lock * dir * (k >= .97 ? 9 : 0);
        c.save(); c.beginPath(); c.rect(0, top + i * h / slices, 960, h / slices + .5); c.clip(); c.fillStyle = W; c.fillText('count', 300 + xo, 482); c.restore();
      }
    }
    rule(120, 840, 500, 3.2);
  },
};

/* ---------------------------------------------------------------- 8 Risograph */
SCENES.risograph = {
  dur: 4.6, fonts: ['800 120px "Bricolage Grotesque"'],
  plate(t, ink, slip, seed) {
    const p = off(), x = p.getContext('2d'), r = rng(seed);
    const stamp = (t0, fn) => { const k = SP(t, t0, t0 + .45, .09); if (t < t0) return; const s = lerp(1.14, 1, k), a = lerp(4, 0, k) * Math.PI / 180; fn(s, a); };
    x.fillStyle = ink;
    /* hero word */
    stamp(.08, (s, a) => { x.save(); x.translate(330, 150); x.rotate(a); x.scale(s, s); x.font = '800 132px "Bricolage Grotesque"'; x.textAlign = 'center'; x.letterSpacing = '6px';
      if (ink === PINK) x.fillText('LOUD', 0, 44); x.restore(); });
    /* two overlapping circles slide in */
    const k1 = SP(t, .55, 1.0, .1), k2 = SP(t, .75, 1.2, .1);
    if (ink === PINK && t > .55) { x.beginPath(); x.arc(lerp(1200, 690, k1), 190, 120, 0, 7); x.fill(); }
    if (ink === BLUE && t > .75) { const cx = lerp(1300, 790, k2); for (let yy = 70; yy < 330; yy += 11) for (let xx = cx - 130; xx < cx + 130; xx += 11) { const d = Math.hypot(xx - cx, yy - 230); if (d < 120) { x.beginPath(); x.arc(xx, yy, 5.6 * (1 - d / 160), 0, 7); x.fill(); } } }
    /* stripe band with a knocked-out word */
    stamp(1.35, (s, a) => { if (ink !== BLUE) return; x.save(); x.translate(330, 330); x.rotate(a); x.scale(s, s);
      x.beginPath(); x.rect(-260, -48, 520, 96); x.clip(); x.lineWidth = 9; x.strokeStyle = ink; for (let i = -40; i < 40; i++) { x.beginPath(); x.moveTo(i * 22, -60); x.lineTo(i * 22 + 60, 60); x.stroke(); }
      x.globalCompositeOperation = 'destination-out'; x.font = '800 78px "Bricolage Grotesque"'; x.textAlign = 'center'; x.fillText('ZINE', 0, 28); x.restore(); });
    stamp(1.6, (s, a) => { if (ink !== PINK) return; x.save(); x.translate(330, 330); x.rotate(a); x.scale(s, s); x.font = '800 78px "Bricolage Grotesque"'; x.textAlign = 'center'; x.fillText('ZINE', 0, 28); x.restore(); });
    /* dot ramp grows left to right */
    if (ink === BLUE) for (let i = 0; i < 18; i++) { const tt = 1.9 + i * .035; if (t < tt) break; const k = SP(t, tt, tt + .3, .1); x.beginPath(); x.arc(110 + i * 25, 420, (2 + i * .55) * k, 0, 7); x.fill(); }
    /* ink: mottled density, paper-white specks */
    x.globalCompositeOperation = 'destination-out';
    for (let i = 0; i < 1400; i++) { x.globalAlpha = .3 + r() * .7; x.fillRect(r() * 960, r() * 540, 1 + r() * 2.2, 1 + r() * 2.2); }
    x.globalAlpha = .18; x.drawImage(grainTile(seed % 6), 0, 0, 960, 540);
    return p;
  },
  render(c, t) {
    const tq = Math.floor(t * 12) / 12, d = Math.floor(t * 12);
    c.fillStyle = '#EDEFEE'; c.fillRect(0, 0, 960, 540);
    const slip = t < 2.8 ? 0 : (1 - SP(tq, 3.0, 3.5, .12)) * Math.min(1, (tq - 2.8) / .17);
    const r = rng(d * 13 + 5), j = () => (r() - .5) * 3;
    c.save(); c.globalCompositeOperation = 'multiply';
    c.drawImage(this.plate(tq, PINK, slip, d * 2 + 1), -26 * slip + j(), -6 * slip + j());
    c.drawImage(this.plate(tq, BLUE, slip, d * 2 + 2), 26 * slip + 3 + j(), 6 * slip + 2 + j());
    c.restore();
    const rr = rng(d + 99); c.fillStyle = 'rgba(50,85,164,.5)'; for (let i = 0; i < 12; i++) c.fillRect(rr() * 960, rr() * 540, 1.5, 1.5);
    grain(c, tq, .08, 'multiply', 12);
  },
};
const PINK = '#FF48B0', BLUE = '#3255A4';

/* ---------------------------------------------------------------- 9 Swiss Grid */
SCENES.swiss_grid = {
  dur: 4.6, fonts: ['800 84px "Public Sans"', '600 15px "Public Sans"'],
  render(c, t) {
    const INK = '#101010', RED = '#F03820', M = 90, X0 = 120, X1 = 840;
    c.fillStyle = '#F0F0E8'; c.fillRect(0, 0, 960, 540);
    /* red field opens out of the cell where the circle stops */
    const cell = { c: 5, r: 1 };
    const kx = SP(t, 1.55, 1.85, .09), ky = SP(t, 1.75, 2.05, .09), k0 = SP(t, 1.35, 1.55, .09);
    if (t > 1.35) {
      const cx0 = X0 + cell.c * M, cy0 = cell.r * M;
      const x0 = lerp(cx0, X0 + 4 * M, kx), x1 = lerp(cx0 + M * k0, 960, kx), y0 = lerp(cy0, -10, ky), y1 = lerp(cy0 + M * k0, 2 * M, ky);
      c.fillStyle = RED; c.fillRect(x0, y0, x1 - x0, y1 - y0);
    }
    /* the grid draws itself */
    c.fillStyle = 'rgba(16,16,16,.28)';
    for (let i = 0; i <= 8; i++) { const k = P(t, -.1 + i * .06, .45 + i * .06, E.out); c.fillRect(X0 + i * M - 1, 0, 2, 540 * k); }
    for (let j = 1; j <= 5; j++) { const k = P(t, .1 + j * .06, .65 + j * .06, E.out); c.fillRect(0, j * M - 1, 960 * k, 2); }
    /* circle steps cell to cell like a rook, then grows into a two-module slot */
    const path = [[1, 1], [3, 1], [3, 3], [5, 3], [5, 1]], steps = [.55, .8, 1.05, 1.25];
    let pos = path[0], prev = path[0], k = 1;
    for (let i = 0; i < steps.length; i++) if (t >= steps[i]) { prev = path[i]; pos = path[i + 1]; k = SP(t, steps[i], steps[i] + .25, .09); }
    let cx = X0 + lerp(prev[0], pos[0], k) * M + M / 2, cy = lerp(prev[1], pos[1], k) * M + M / 2, rad = M / 2 * .92;
    const kg = t < 2.6 ? 0 : SP(t, 2.6, 3.2, .1), wind = t > 2.45 && t < 2.6 ? 1 - .1 * Math.sin(Math.PI * P(t, 2.45, 2.6)) : 1;
    if (t > 2.45) { cx = lerp(X0 + 5 * M + M / 2, X0 + 6 * M, kg); cy = lerp(M + M / 2, 4 * M, kg); rad = lerp(M / 2 * .92, M * .96, kg) * wind; }
    if (t > .55 || t > 0) { c.beginPath(); c.arc(cx, cy, rad * clamp(SP(t, .25, .55, .1), 0, 1.1), 0, 7); c.fillStyle = INK; c.fill(); }
    /* type pushed out of the left margin line, baselines on grid lines */
    const lines = ['Say', 'one', 'thing.'];
    c.font = '800 84px "Public Sans"'; c.fillStyle = INK; c.letterSpacing = '-4px';
    lines.forEach((s, i) => { const k = SP(t, 1.95 + i * .2, 2.45 + i * .2, .08), base = (3 + i) * M - 10, w = c.measureText(s).width;
      c.save(); c.beginPath(); c.rect(X0, base - 90, 900, 110); c.clip(); c.fillText(s, X0 - 5 - (1 - k) * (w + 20), base); c.restore(); });
    c.letterSpacing = '0px';
    lines.forEach((s, i) => { const k = SP(t, 2.15 + i * .2, 2.5 + i * .2, .1); if (k <= 0) return; c.save(); c.beginPath(); c.rect(X0 + 4 * M, (2 + i) * M + 2, 200, 40); c.clip();
      c.font = '600 15px "Public Sans"'; c.fillStyle = INK; const y = (2 + i) * M + 22 - (1 - k) * 26; c.fillText('0' + (i + 1), X0 + 4 * M + 8, y); c.globalAlpha = .6; c.fillText(s.replace('.', ''), X0 + 4 * M + 36, y); c.restore(); });
  },
};

/* ---------------------------------------------------------------- 10 Pencil to Blueprint */
SCENES.blueprint = {
  dur: 5.2, fonts: ['600 40px "Barlow Semi Condensed"', '500 18px "Barlow Semi Condensed"'],
  init() {
    const L = (pts, w = 1) => ({ pts, w });
    const arc = (cx, cy, rx, ry, a0, a1, n = 24) => Array.from({ length: n + 1 }, (_, i) => { const a = a0 + (a1 - a0) * i / n; return [cx + Math.cos(a) * rx, cy + Math.sin(a) * ry]; });
    this.strokes = [
      { k: 'ground', ...L([[190, 430], [720, 430]]) },
      { k: 'axis', ...L([[400, 150], [400, 440]]) },
      { k: 'out', ...L([[310, 180], [322, 430]]) }, { k: 'out', ...L([[322, 430], [478, 430]]) }, { k: 'out', ...L([[478, 430], [490, 180]]) },
      { k: 'out', ...L(arc(400, 180, 90, 14, Math.PI, Math.PI * 2)) }, { k: 'out', ...L(arc(400, 180, 90, 14, 0, Math.PI)) },
      { k: 'out', ...L(arc(492, 290, 62, 70, -Math.PI / 2.2, Math.PI / 2.2)) }, { k: 'out', ...L(arc(492, 290, 36, 44, -Math.PI / 2.4, Math.PI / 2.4)) },
      { k: 'joint', ...L(arc(497, 225, 7, 7, 0, Math.PI * 2, 16)) }, { k: 'joint', ...L(arc(497, 355, 7, 7, 0, Math.PI * 2, 16)) },
      ...Array.from({ length: 7 }, (_, i) => ({ k: 'hatch', ...L([[440 + i * 6, 410], [470 + i * 2, 220 + i * 8]]) })),
    ];
    let tt = .05; this.strokes.forEach(s => { const len = s.pts.reduce((a, p, i) => i ? a + Math.hypot(p[0] - s.pts[i - 1][0], p[1] - s.pts[i - 1][1]) : 0, 0); s.t0 = tt; s.d = s.k === 'hatch' ? .06 : clamp(len / 900, .12, .35); tt += s.d + (s.k === 'hatch' ? .015 : .05); });
    this.sketchEnd = tt;
  },
  pencil(c, s, t) {
    const k = E.io(P(t, s.t0, s.t0 + s.d)); if (k <= 0) return;
    const r = rng(s.pts.length * 31 + s.pts[0][0] | 0);
    for (let pass = 0; pass < (s.k === 'axis' || s.k === 'hatch' ? 1 : 2); pass++) {
      const o = (r() - .5) * 2.2, n = Math.max(2, Math.ceil(s.pts.length * k));
      c.beginPath(); for (let i = 0; i < n; i++) { const [x, y] = s.pts[i]; const w = Math.sin(i * .9 + pass) * .9; i ? c.lineTo(x + o + w, y + o * .6) : c.moveTo(x + o, y + o); }
      if (k >= 1 && s.k === 'out') { const a = s.pts[s.pts.length - 2], b = s.pts[s.pts.length - 1], dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy) || 1; c.lineTo(b[0] + dx / l * 7 + o, b[1] + dy / l * 7 + o); }
      c.strokeStyle = s.k === 'axis' ? 'rgba(37,38,43,.35)' : 'rgba(37,38,43,.85)'; c.lineWidth = s.k === 'hatch' ? 1 : 1.5; c.stroke();
    }
  },
  ink(c, s) {
    c.beginPath(); s.pts.forEach(([x, y], i) => i ? c.lineTo(x, y) : c.moveTo(x, y));
    c.setLineDash(s.k === 'axis' ? [18, 5, 3, 5] : []); c.strokeStyle = s.k === 'hatch' ? 'rgba(238,244,251,.5)' : '#EEF4FB'; c.lineWidth = s.k === 'hatch' ? 1 : 2; c.stroke(); c.setLineDash([]);
  },
  flood(t) { const k = P(t, 2.05, 3.0, E.out), R = 700 * k, pts = [];
    for (let i = 0; i < 72; i++) { const a = i / 72 * Math.PI * 2, n = Math.sin(a * 5 + 1) * .06 + Math.sin(a * 11 + 2) * .04 + Math.sin(a * 3) * .05; pts.push([400 + Math.cos(a) * R * (1 + n), 300 + Math.sin(a) * R * (1 + n)]); }
    return { k, pts }; },
  render(c, t) {
    c.fillStyle = '#ECECE6'; c.fillRect(0, 0, 960, 540);
    c.strokeStyle = 'rgba(127,163,196,.32)'; c.lineWidth = 1;
    for (let x = 0; x < 960; x += 24) { c.beginPath(); c.moveTo(x + .5, 0); c.lineTo(x + .5, 540); c.stroke(); }
    for (let y = 0; y < 540; y += 24) { c.beginPath(); c.moveTo(0, y + .5); c.lineTo(960, y + .5); c.stroke(); }
    for (const s of this.strokes) this.pencil(c, s, t);
    const f = this.flood(t);
    if (f.k > 0) {
      c.save(); c.beginPath(); f.pts.forEach(([x, y], i) => i ? c.lineTo(x, y) : c.moveTo(x, y)); c.closePath(); c.fillStyle = '#1C4C8F'; c.fill();
      c.lineWidth = 10; c.strokeStyle = 'rgba(20,60,118,.9)'; c.save(); c.clip(); c.stroke(); for (const s of this.strokes) this.ink(c, s); c.restore(); c.restore();
    }
    /* dimensions land */
    if (t > 3.1) {
      c.strokeStyle = '#EEF4FB'; c.fillStyle = '#EEF4FB'; c.lineWidth = 1.2;
      const kx = P(t, 3.1, 3.35, E.out); c.beginPath(); c.moveTo(300, 180); c.lineTo(300 - 50 * kx, 180); c.moveTo(310, 430); c.lineTo(310 - 60 * kx, 430); c.stroke();
      const kd = P(t, 3.3, 3.65, E.out), mid = 305; c.beginPath(); c.moveTo(262, mid - 125 * kd); c.lineTo(262, mid + 125 * kd); c.stroke();
      if (t > 3.6) { const a = SP(t, 3.6, 3.8, .2); for (const [y, d] of [[180, 1], [430, -1]]) { c.beginPath(); c.moveTo(262, y); c.lineTo(262 - 6 * a, y + 14 * d * a); c.lineTo(262 + 6 * a, y + 14 * d * a); c.closePath(); c.fill(); } }
      c.font = '500 18px "Barlow Semi Condensed"'; c.fontVariantNumeric = 'tabular-nums';
      if (t > 3.6) { const v = Math.round(96 * P(t, 3.6, 4.1, E.out)); c.save(); c.translate(250, 315); c.rotate(-Math.PI / 2); c.textAlign = 'center'; c.fillText(v + ' mm', 0, 0); c.restore(); }
      const kw = P(t, 3.5, 3.85, E.out); c.beginPath(); c.moveTo(322, 438); c.lineTo(322, 438 + 40 * kw); c.moveTo(478, 438); c.lineTo(478, 438 + 40 * kw); c.moveTo(400 - 78 * P(t, 3.7, 4.0, E.out), 470); c.lineTo(400 + 78 * P(t, 3.7, 4.0, E.out), 470); c.stroke();
      if (t > 3.9) { const v = Math.round(82 * P(t, 3.9, 4.35, E.out)); c.textAlign = 'center'; c.fillText(v + ' mm', 400, 494); }
      /* label rises over a rule that draws first */
      const kr = P(t, 3.95, 4.25, E.out); c.fillRect(310, 132, 260 * kr, 1.5);
      const kl = SP(t, 4.15, 4.65, .1); c.save(); c.beginPath(); c.rect(300, 80, 600, 50); c.clip(); c.font = '600 40px "Barlow Semi Condensed"'; c.letterSpacing = '3px'; c.textAlign = 'left'; c.fillText('MUG · 01', 310, 124 + (1 - kl) * 48); c.restore();
    }
    grain(c, t, .06, 'multiply', 1);
  },
};
