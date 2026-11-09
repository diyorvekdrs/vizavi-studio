/* PROJECT TITLE – HTML engine starter (Vizavi). Everything is a function of t (VZ.seek(t) per frame).
   Replace the demo scenes; keep: scene dispatcher, captions from VZ.words, safe area, grain. */
const $ = s => document.querySelector(s);
const E = VZ.ease, P = (t, a, b, e) => VZ.prog(t, a, b, e);
const SCENES = VZ.project.scenes;
const CAPTIONS = true;                     // per the spec (burned-in captions)

/* ---------- narration timing (never hard-code): word start by text ---------- */
const norm = s => s.toLowerCase().replace(/[‘ʻ’`]/g, "'").replace(/[^\p{L}\p{N}']/gu, "");
function wordT(w, n = 1, dflt = 0) { let k = 0; for (const x of VZ.words) if (norm(x[2]) === norm(w) && ++k === n) return x[0]; return dflt; }

/* ---------- kinetic type helper: words of a line enter with a stagger ---------- */
function typeLine(el, text, t, t0, { stagger = 0.045, dur = 0.5, rise = 3 } = {}) {
  if (el.dataset.text !== text) { el.dataset.text = text; el.innerHTML = text.split(" ").map(w => `<span class="word">${w} </span>`).join(""); }
  [...el.children].forEach((s, i) => {
    const k = P(t, t0 + i * stagger, t0 + i * stagger + dur, E.out);
    s.style.opacity = k; s.style.transform = `translateY(calc(var(--u) * ${(1 - k) * rise}))`;
  });
}

/* ---------- captions: groups of ≤ 28 chars, active word highlighted ---------- */
const GROUPS = (() => { const g = []; let cur = [];
  for (const w of VZ.words) {
    const len = cur.map(x => x[2]).join(" ").length + w[2].length + 1;
    if (cur.length && (len > 28 || w[0] - cur[cur.length - 1][1] > 0.6 || /[.!?]$/.test(cur[cur.length - 1][2]))) { g.push(cur); cur = []; }
    cur.push(w);
  } if (cur.length) g.push(cur); return g; })();
function captions(t) {
  const el = $("#captions"); if (!CAPTIONS) { el.textContent = ""; return; }
  const g = GROUPS.find(g => t >= g[0][0] - 0.05 && t <= g[g.length - 1][1] + 0.25);
  if (!g) { el.innerHTML = ""; return; }
  const act = VZ.wordAt(t), aw = VZ.words[act];            // exactly one active word: the latest started
  el.innerHTML = g.map(w => `<span class="${w === aw && t <= w[1] + 0.25 ? "on" : ""}">${w[2]}</span>`).join(" ");
  const k = P(t, g[0][0] - 0.05, g[0][0] + 0.12, E.out);
  el.style.transform = `scale(${0.96 + 0.04 * k})`; el.style.opacity = k;
}

/* ---------- background canvas (redrawn fully every frame) ---------- */
const bg = $("#bg"), g2 = bg.getContext("2d");
const rand = VZ.rand(7), DUST = Array.from({ length: 160 }, () => [rand(), rand(), rand()]);
function drawBg(t) {
  bg.width = VZ.W; bg.height = VZ.H; const u = Math.min(VZ.W, VZ.H) / 100;
  for (const [x, y, z] of DUST) {              // parallax dust: depth z sets speed, size, brightness
    const px = ((x + t * 0.01 * (0.3 + z)) % 1) * VZ.W, py = ((y - t * 0.006 * (0.3 + z)) % 1 + 1) % 1 * VZ.H;
    g2.fillStyle = `rgba(255,240,220,${0.15 + 0.5 * z * z})`;
    g2.beginPath(); g2.arc(px, py, (0.12 + 0.35 * z) * u, 0, 7); g2.fill();
  }
}

/* ---------- grain (static texture, offset per frame; deterministic) ---------- */
(() => { const c = document.createElement("canvas"); c.width = c.height = 256; const x = c.getContext("2d");
  const d = x.createImageData(256, 256), r = VZ.rand(3);
  for (let i = 0; i < d.data.length; i += 4) { const v = r() * 255; d.data[i] = d.data[i + 1] = d.data[i + 2] = v; d.data[i + 3] = 255; }
  x.putImageData(d, 0, 0); $("#grain").style.backgroundImage = `url(${c.toDataURL()})`; })();

/* ---------- scenes: one function per beat/scene ---------- */
const content = $("#content");
function sceneHook(tl, t) {
  if (!$("#h")) content.innerHTML = '<div class="head" id="h"></div>';
  typeLine($("#h"), "Sarlavha shu yerda", t, 0.2);
}
function scenePoint(tl, t, a) {
  if (!$("#p")) content.innerHTML = '<div class="head" id="p" style="margin-top:20%"></div><div class="body" id="b"></div>';
  typeLine($("#p"), "Asosiy fikr", t, a);
  typeLine($("#b"), "Qisqa izoh matni bu yerda bo‘ladi.", t, a + 0.4, { stagger: 0.03 });
}
const SCENE_FN = { hook: sceneHook, point: scenePoint };

VZ.onFrame(t => {
  const s = SCENES.find(s => t >= s[1] && t < s[2]) || SCENES[SCENES.length - 1];
  if (content.dataset.scene !== s[0]) { content.dataset.scene = s[0]; content.innerHTML = ""; }
  SCENE_FN[s[0]](t - s[1], t, s[1]);
  drawBg(t); captions(t);
  $("#grain").style.transform = `translate(${(Math.floor(t * VZ.fps) * 37) % 128}px, ${(Math.floor(t * VZ.fps) * 71) % 128}px)`;
});
