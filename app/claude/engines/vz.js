/* Vizavi HTML engine runtime. Include in index.html:  <script src="vz.js"></script>
   Makes a page frame-exact: the renderer calls VZ.seek(t) for every frame, then screenshots.
   - Put everything inside <div id="stage">…</div>.
   - Animate ONLY as a function of t: VZ.onFrame((t, VZ) => {...}) for canvas/SVG/DOM,
     or CSS animations / Web Animations (they are paused and scrubbed to t automatically).
   - Never use requestAnimationFrame, setTimeout/setInterval, Date or performance.now for motion.
   - Random: VZ.rand(seed) (deterministic).  Video: VZ.video(el) (muted, seeked per frame).
   - Size: project.json "responsive": false -> fixed design canvas (width×height) scaled to the output;
           true -> #stage = output size, layout with CSS var --u (1% of the short side) and VZ.W/VZ.H/VZ.isPortrait.
   - Alpha projects: keep html/body/#stage background transparent (the runtime enforces it).
   Open index.html in a browser to preview: it plays in real time (?play=1 is default when not rendering). */
(function () {
  const P = window.VZ_PROJECT || { width: 1920, height: 1080, fps: 30, nfr: 300, responsive: false };
  const q = new URLSearchParams(location.search);
  const rendering = !!window.VZ_PROJECT;
  const VW = +q.get('w') || innerWidth, VH = +q.get('h') || innerHeight;
  const root = document.documentElement.style;
  const VZ = window.VZ = {
    project: P, W: VW, H: VH, fps: P.fps, duration: P.nfr / P.fps, t: 0,
    words: window.VZ_WORDS || [],          // [[start, end, word], ...] final narration timing (captions!)
    wordAt(t) { const w = this.words; let i = -1; for (let k = 0; k < w.length && w[k][0] <= t; k++) i = k; return i; },
    alpha: q.get('alpha') === '1', aspect: VW / VH, isPortrait: VH > VW, rendering,
    _draws: [], _videos: [], _waits: [], _ready: false,
    onFrame(fn) { this._draws.push(fn); return fn; },
    waitFor(p) { this._waits.push(p); return p; },
    video(el) { el.muted = true; el.playsInline = true; el.pause(); this._videos.push(el); return el; },
    isReady() { return this._ready; },
    async seek(t) {
      this.t = t;
      root.setProperty('--t', t);
      for (const a of document.getAnimations()) { a.pause(); a.currentTime = t * 1000; }
      for (const v of this._videos) {
        const vt = Math.min(t, (v.duration || 1e9) - 0.001);
        if (Math.abs(v.currentTime - vt) > 0.0005) {
          await new Promise(r => { v.addEventListener('seeked', r, { once: true }); v.currentTime = vt; });
        }
      }
      for (const fn of this._draws) fn(t, this);
      await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
    },
    clamp: (x, a = 0, b = 1) => Math.min(b, Math.max(a, x)),
    lerp: (a, b, k) => a + (b - a) * k,
    ease: {
      linear: k => k, smooth: k => k * k * (3 - 2 * k),
      in: k => k * k * k, out: k => 1 - Math.pow(1 - k, 3),
      inOut: k => k < .5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2,
      outBack: k => 1 + 2.70158 * Math.pow(k - 1, 3) + 1.70158 * Math.pow(k - 1, 2),
    },
    /* progress of t inside [a,b] -> 0..1 (eased) */
    prog(t, a, b, ease) { const x = VZ.clamp((t - a) / Math.max(1e-9, b - a)); return ease ? ease(x) : x; },
    rand(seed) { let s = (seed >>> 0) || 1; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296); },
    /* What text is visible right now, for the automatic checks (the renderer calls this a few times a second):
       one entry per text block with its box in output pixels, font size, colour, opacity, whether it is a caption
       and whether its container cuts it off. Mark captions with data-vz-caption (or id/class "captions"),
       decorative text that is not meant to be read with data-vz-ignore. */
    textLayout() {
      const st = document.getElementById('stage') || document.body, out = new Map();
      const tw = document.createTreeWalker(st, NodeFilter.SHOW_TEXT);
      const cache = new Map(), cs = e => { let c = cache.get(e); if (!c) { c = getComputedStyle(e); cache.set(e, c); } return c; };
      const shown = e => { let o = 1; for (; e && e.nodeType === 1; e = e.parentElement) {
        const c = cs(e); if (c.display === 'none' || c.visibility === 'hidden') return 0; o *= +c.opacity; } return o; };
      const blockOf = e => { for (let b = e; b && b !== st; b = b.parentElement) {
        const d = cs(b).display; if (!d.startsWith('inline') && d !== 'contents') return b; } return st; };
      const path = e => { const p = []; for (; e && e !== document.body; e = e.parentElement) {
        p.push(e.id ? '#' + e.id : e.tagName + ':' + [...(e.parentElement ? e.parentElement.children : [])].indexOf(e)); if (e.id) break; } return p.reverse().join('/'); };
      const rgba = s => { const m = String(s).match(/[\d.]+/g); return m ? m.map(Number) : null; };
      let n;
      while ((n = tw.nextNode())) {
        const txt = n.nodeValue; if (!txt || !txt.trim()) continue;
        const el = n.parentElement;
        if (!el || el.closest('[data-vz-ignore],script,style,noscript,defs,title')) continue;
        const op = shown(el); if (op < 0.15) continue;
        const r = document.createRange(); r.selectNodeContents(n);
        const rs = [...r.getClientRects()].filter(q => q.width > 0.5 && q.height > 0.5); if (!rs.length) continue;
        let x0 = Math.min(...rs.map(q => q.left)), y0 = Math.min(...rs.map(q => q.top));
        let x1 = Math.max(...rs.map(q => q.right)), y1 = Math.max(...rs.map(q => q.bottom));
        let hidden = false, clip = false;
        for (let a = el.parentElement; a && a !== document.documentElement; a = a.parentElement) {
          const c = cs(a); if (c.overflowX === 'visible' && c.overflowY === 'visible') continue;
          const ar = a.getBoundingClientRect();
          if (x1 <= ar.left || x0 >= ar.right || y1 <= ar.top || y0 >= ar.bottom) { hidden = true; break; }
          if (a !== st && a !== document.body && (x0 < ar.left - 2 || y0 < ar.top - 2 || x1 > ar.right + 2 || y1 > ar.bottom + 2)) clip = true;
        }
        if (hidden || x1 <= 0 || y1 <= 0 || x0 >= VW || y0 >= VH) continue;
        const c = cs(el);
        const br = el.getBoundingClientRect(), oh = el.offsetHeight;
        const scale = oh ? br.height / oh : 1;
        const px = parseFloat(c.fontSize) * (isFinite(scale) && scale > 0 ? scale : 1);
        let col = rgba(c.webkitTextFillColor && c.webkitTextFillColor !== c.color ? c.webkitTextFillColor : c.color);
        if (col && col.length > 3 && col[3] < 0.5) col = null;          // gradient / image-filled text
        const b = blockOf(el), k = path(b);
        const cap = !!el.closest('[data-vz-caption],#captions,.captions,.caption');
        const e = out.get(k);
        const last = rs[rs.length - 1], first = rs[0];
        if (!e) out.set(k, { k, text: txt.trim(), box: [x0, y0, x1, y1], px, color: col ? col.slice(0, 3) : null, op, cap, clip, _r: last.right, _t: last.top, _s: /\s$/.test(txt) });
        else {
          // spans of one word (letter by letter animation) join without a space; a gap or a new line is a space
          const gap = e._s || /^\s/.test(txt) || first.left - e._r > 0.18 * px || Math.abs(first.top - e._t) > 0.5 * px;
          e.text = (e.text + (gap ? ' ' : '') + txt.trim()).replace(/\s+/g, ' '); e._r = last.right; e._t = last.top; e._s = /\s$/.test(txt);
          e.box = [Math.min(e.box[0], x0), Math.min(e.box[1], y0), Math.max(e.box[2], x1), Math.max(e.box[3], y1)];
          e.px = Math.max(e.px, px); e.op = Math.max(e.op, op); e.cap = e.cap || cap; e.clip = e.clip || clip;
        }
      }
      return [...out.values()].map(({ _r, _t, _s, ...e }) => ({ ...e, box: e.box.map(v => Math.round(v * 10) / 10), px: Math.round(e.px * 10) / 10 }));
    },
  };

  function layout() {
    const st = document.getElementById('stage');
    root.setProperty('--W', VW); root.setProperty('--H', VH);
    if (!st) return;
    st.style.position = 'absolute'; st.style.left = '0'; st.style.top = '0'; st.style.overflow = 'hidden';
    if (P.responsive) {
      st.style.width = VW + 'px'; st.style.height = VH + 'px';
      root.setProperty('--u', (Math.min(VW, VH) / 100) + 'px');
    } else {
      const s = Math.min(VW / P.width, VH / P.height);
      st.style.width = P.width + 'px'; st.style.height = P.height + 'px';
      st.style.transformOrigin = '0 0';
      st.style.transform = `translate(${(VW - P.width * s) / 2}px, ${(VH - P.height * s) / 2}px) scale(${s})`;
      root.setProperty('--u', (Math.min(P.width, P.height) / 100) + 'px');
    }
  }

  addEventListener('DOMContentLoaded', () => {
    const b = document.body;
    b.style.margin = '0'; b.style.overflow = 'hidden';
    b.style.width = VW + 'px'; b.style.height = VH + 'px';
    if (VZ.alpha) { root.background = 'transparent'; b.style.background = 'transparent'; }
    layout();
  });
  addEventListener('load', async () => {
    layout();
    for (const a of document.getAnimations()) a.pause();
    await document.fonts.ready;
    await Promise.all([...document.images].map(i => i.decode().catch(() => {})));
    await Promise.all(VZ._videos.map(v => v.readyState >= 2 ? 0 :
      new Promise(r => v.addEventListener('loadeddata', r, { once: true }))));
    await Promise.all(VZ._waits);
    await VZ.seek(0);
    VZ._ready = true;
    if (!rendering && q.get('play') !== '0') {  // manual preview in a normal browser
      const t0 = performance.now();
      const tick = async () => { await VZ.seek(((performance.now() - t0) / 1000) % VZ.duration); requestAnimationFrame(tick); };
      requestAnimationFrame(tick);
    }
  });
})();
