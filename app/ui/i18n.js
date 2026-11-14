/* Two languages for the window: English (the code's own words) and Uzbek (Latin).
   The app keeps writing English; in Uzbek mode every text node, option and placeholder/title/aria-label that
   matches an entry of lang/uz.js is shown in Uzbek as soon as it appears (before the screen is painted).
   Entries are [English, Uzbek]; {0}, {1}… in the English stand for any text and come back where the Uzbek puts them.
   Elements with data-noi18n (and inputs, textareas, the log) are left alone. */
(() => {
  const KEY = "vz-lang";
  const saved = (() => { try { return localStorage.getItem(KEY); } catch { return null; } })();
  const lang = saved === "uz" || saved === "en" ? saved : /^uz\b/i.test(navigator.language || "") ? "uz" : "en";
  const I = window.VZI18N = {
    lang, missing: new Set(),
    set(l) { try { localStorage.setItem(KEY, l); } catch {} location.reload(); },
    t: s => s,
  };
  document.documentElement.lang = lang;
  if (lang !== "uz") return;

  const norm = s => s.replace(/\s+/g, " ").trim();
  const exact = new Map(), pats = [];
  const rx = s => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  for (const [en, uz] of (window.VZ_UZ || [])) {
    if (/\{\d\}/.test(en)) pats.push([new RegExp("^" + rx(norm(en)).replace(/\\\{(\d)\\\}/g, "([\\s\\S]+?)") + "$"), uz,
      [...en.matchAll(/\{(\d)\}/g)].map(m => +m[1])]);
    else exact.set(norm(en), uz);
  }
  pats.sort((a, b) => b[0].source.length - a[0].source.length);
  const word = /[A-Za-z]{2,}/;
  function tr(s) {
    const k = norm(s);
    if (!k || !word.test(k)) return null;
    const hit = exact.get(k);
    if (hit !== undefined) return hit;
    for (const [re, uz, idx] of pats) {
      const m = k.match(re);
      if (m) return uz.replace(/\{(\d)\}/g, (_, n) => { const v = m[idx.indexOf(+n) + 1] ?? ""; return exact.get(norm(v)) ?? v; });
    }
    I.missing.add(k);
    return null;
  }
  I.t = s => tr(s) ?? s;
  const skip = el => !el || el.closest("[data-noi18n],textarea,script,style,#log,code,pre");
  function doText(n) {
    if (n.__vz === n.nodeValue || skip(n.parentElement)) return;
    const v = n.nodeValue, out = tr(v);
    if (out == null) { n.__vz = v; return; }
    const lead = v.match(/^\s*/)[0], tail = v.match(/\s*$/)[0];
    n.__vz = n.nodeValue = lead + out + tail;
  }
  const ATTRS = ["placeholder", "title", "aria-label"];
  function doAttrs(el) {
    if (!el || el.closest("[data-noi18n],script,style")) return;
    for (const a of ATTRS) {
      const v = el.getAttribute(a); if (!v) continue;
      const mark = "__vz_" + a; if (el[mark] === v) continue;
      const out = tr(v); el[mark] = out ?? v; if (out != null) el.setAttribute(a, out);
    }
    if (el.tagName === "INPUT" && (el.type === "button" || el.type === "submit") && el.value) { const o = tr(el.value); if (o) el.value = o; }
  }
  function walk(root) {
    if (root.nodeType === 3) return doText(root);
    if (root.nodeType !== 1) return;
    doAttrs(root);
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    for (let n = w.nextNode(); n; n = w.nextNode()) n.nodeType === 3 ? doText(n) : doAttrs(n);
  }
  const mo = new MutationObserver(list => {
    for (const m of list) {
      if (m.type === "characterData") doText(m.target);
      else if (m.type === "attributes") doAttrs(m.target);
      else for (const n of m.addedNodes) walk(n);
    }
  });
  const start = () => { walk(document.documentElement); mo.observe(document.documentElement, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRS }); };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
  /* the confirm/alert/prompt texts, if any */
  for (const f of ["alert", "confirm", "prompt"]) { const o = window[f]; window[f] = (msg, ...a) => o.call(window, I.t(String(msg ?? "")), ...a); }
})();
