/* Vizavi Studio UI – talks to the local engine (studio/server.py). No frameworks, no network. */
const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const S = { since: 0, version: -1, projects: [], current: null, cur: null, meta: null, busy: false, status: null, job: "",
  running: "", busyProj: {}, stamp: null, navSig: "", viewSig: "", drafts: {}, ui: {}, fails: 0, dead: false, polled: false };

/* ---------- updates ---------- */
function dismissed() { try { return localStorage.getItem("vz-upd-later") || ""; } catch { return ""; } }
function renderUpdate(u) {
  const bar = $("#updBar"), show = !!u && dismissed() !== u.latest && !S.restartFrom;
  const key = show ? u.latest : "";
  if (bar.dataset.k === key) return;
  bar.dataset.k = key; bar.hidden = !show; S.update = u;
  if (!show) return;
  bar.innerHTML = `<span class="dot work"></span><span class="grow"><b>Vizavi Studio ${esc(u.latest)} is available.</b></span>
    <button class="link" data-u="notes">What's new</button><button class="btn small primary" data-u="go">Update now</button>
    <button class="link" data-u="later">Later</button>`;
}
$("#updBar").addEventListener("click", async e => {
  const b = e.target.closest("[data-u]"); if (!b || !S.update) return;
  const u = S.update;
  if (b.dataset.u === "later") { try { localStorage.setItem("vz-upd-later", u.latest); } catch {} renderUpdate(u); return; }
  if (b.dataset.u === "notes") return notesDialog(u);
  startUpdate();
});
function notesDialog(u) {
  openDialog(`<div class="dh"><h2>What's new in ${esc(u.latest)}</h2><button class="link" data-close>Close</button></div>
    <div class="db"><pre class="notes-text">${esc(u.notes || "No notes for this version.")}</pre></div>
    <div class="df"><button class="btn" data-close>Later</button><button class="btn primary" id="updGo">Update now</button></div>`,
    d => $("#updGo", d).onclick = () => { dlg.close(); startUpdate(); });
}
async function startUpdate() {
  if (S.busy) return toast("A job is running – update when it has finished.", "warn", 5000);
  try { await api("/api/act", { action: "apply_update" }); toast("Downloading the update – progress along the bottom", "info", 4000); $("#updBar").hidden = true; }
  catch (e) { toast(e.message, "error"); }
}

function engineGone() {
  if (S.dead) return;
  S.dead = true; $("#dead").hidden = false;
}
async function api(path, body) {
  let r;
  try { r = await fetch(path, body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }); }
  catch { throw new Error("Vizavi Studio is not responding"); }
  const j = await r.json().catch(() => ({}));
  if (r.status === 401) { engineGone(); throw new Error("This window is out of date – reopen Vizavi Studio"); }
  if (!r.ok) throw new Error(j.error || `Request failed (${r.status})`);
  return j;
}

/* Toasts: errors, warnings and "your move" messages stay until you close them; plain info fades away. */
function toast(text, kind = "info", ms) {
  if (ms === undefined) ms = kind === "info" ? 5000 : kind === "done" ? 15000 : 0;
  const box = $("#toasts");
  for (const o of box.children) if (o.dataset.text === text) { o.remove(); break; }      // no duplicates
  const t = document.createElement("div"); t.className = `toast ${kind}`; t.dataset.text = text; t.setAttribute("role", kind === "error" ? "alert" : "status");
  const sp = document.createElement("span"); sp.textContent = text;
  const x = document.createElement("button"); x.className = "x"; x.setAttribute("aria-label", "Dismiss"); x.textContent = "×"; x.onclick = () => t.remove();
  t.append(sp, x); box.append(t);
  while (box.children.length > 5) box.firstChild.remove();
  if (ms) setTimeout(() => t.remove(), ms);
}
async function copy(text, what = "Message copied – paste it in Claude with Ctrl+V") {
  try { await navigator.clipboard.writeText(text); toast(what, "info", 3500); } catch { toast("Couldn't copy – select the text manually", "warn", 6000); }
}
const fmtDur = s => s == null ? "" : s < 60 ? `${Math.round(s)} s` : `${Math.floor(s / 60)} min ${String(Math.round(s % 60)).padStart(2, "0")} s`;
const fmtMin = m => m == null ? "" : m < 1 ? "under a minute" : m < 60 ? `about ${Math.round(m)} min` : `about ${Math.floor(m / 60)} h ${String(Math.round(m % 60)).padStart(2, "0")} min`;

/* ---------- stages ---------- */
const STEP = { new: 0, transcribing: 0, failed: 0, request_ready: 1, rendering_preview: 2, preview_ready: 3, error: 3, rendering_final: 4, done: 5 };
const TURN = { request_ready: "you", preview_ready: "you", error: "bad", failed: "bad", stopped: "bad", done: "done" };
const STATIONS = [["Inputs", "voice, script, assets"], ["Claude", "builds the video"], ["Preview", "rendered here"],
                  ["Claude", "reviews and fixes"], ["Final", "all sizes and formats"]];
const turnOf = st => TURN[st] || "machine";
const stepOf = p => p.stage === "stopped" ? (p.failed_kind === "final" ? 4 : 2) : (STEP[p.stage] ?? 0);

/* ---------- polling ---------- */
async function poll() {
  if (S.dead) return;
  let delay;
  try {
    const p = await api(`/api/poll?since=${S.since}` + (S.current ? `&proj=${encodeURIComponent(S.current)}` : ""));
    S.fails = 0;
    if (S.restartFrom && p.app_version) {          // back after an update/undo: load the new page code
      if (p.app_version !== S.restartFrom || !p.restarting) { location.reload(); return; }
    }
    if (p.restarting && !S.restartFrom) { S.restartFrom = p.app_version; $("#restart").hidden = false; }
    renderUpdate(p.update);
    S.since = p.next; S.busy = p.busy; S.status = p.status; S.job = p.job; S.running = p.running_project || "";
    const bp = p.busy_projects || {}, bsig = JSON.stringify(bp);
    const busyChanged = bsig !== JSON.stringify(S.busyProj);
    S.busyProj = bp;
    if (p.logs.length) {
      const lg = $("#log"); lg.textContent += p.logs.map(l => l[1]).join("\n") + "\n";
      if (lg.textContent.length > 400000) lg.textContent = lg.textContent.slice(-250000);
      if (!lg.hidden) lg.scrollTop = lg.scrollHeight;
    }
    if (S.polled) p.toasts.forEach(t => toast(t[2], t[1]));       // a fresh window doesn't replay old ones
    S.polled = true;
    renderStatus(p);
    renderSetup(p);
    if (p.ready && !S.meta) { S.meta = await api("/api/meta"); applyFx(); }
    if (p.ready && p.version !== S.version) { S.version = p.version; await loadProjects(); }
    else if (p.ready && S.current && p.stamp) {                    // only reload the open project when its files changed
      if (S.stamp === null) S.stamp = p.stamp;
      else if (p.stamp !== S.stamp) { S.stamp = p.stamp; await loadProject(S.current); }
    }
    if (busyChanged) { renderNav(); applyBusy(); }
    if (p.focus) { S.current = p.focus; await loadProjects(); }
    if (p.pending && p.pending.length) handlePaths(p.pending);
    if (S.busy && S.current) liveTrack();
    delay = document.hidden ? 3000 : S.busy ? 600 : 1300;
  } catch (e) {
    if (S.dead) return;
    if (S.restartFrom) delay = 1500;                // the engine is restarting for an update: just wait
    else { if (++S.fails >= 3) $("#stLabel").textContent = "Engine not reachable – start Vizavi Studio again"; delay = 2000; }
  }
  setTimeout(poll, delay);
}

function renderSetup(p) {
  const el = $("#setup"), on = !p.ready;
  el.hidden = !on;
  if (on) { $("#empty").hidden = true; $("#view").hidden = true; } else if (!el.dataset.done) { el.dataset.done = 1; return; }
  if (!on) return;
  const failed = p.phase === "failed";
  const tail = $("#log").textContent.trim().split("\n").filter(l => l.trim()).slice(-5);
  el.innerHTML = `<h1>${failed ? "Setup stopped" : "Getting Vizavi Studio ready"}</h1>
    <p>${failed ? "Something went wrong while installing. Open the log at the bottom right and send it to whoever gave you the app."
      : "First start on this PC: it installs only what this computer can use. This takes 5–30 minutes depending on the internet; later starts are instant. Keep this window open."}</p>
    ${p.hw ? `<ul class="hw">${p.hw.map(l => `<li>${esc(l)}</li>`).join("")}</ul>` : ""}
    ${failed ? "" : `<div class="phase"><span class="bar indet"><i></i></span><b>${esc(p.phase || "Starting")}</b></div>`}
    <pre class="tail">${esc(tail.join("\n"))}</pre>`;
}

function renderStatus(p) {
  const dot = $("#stDot"); dot.className = "dot " + (p.busy ? "work" : p.ready ? "ok" : "");
  $("#status").classList.toggle("busy", p.busy);
  const st = p.status;
  $("#stBars").hidden = !p.busy;
  if (p.busy) {
    $("#stLabel").textContent = (st && st.label) || p.job;
    const sf = st && st.step_frac != null ? st.step_frac : null, f = (st && st.frac) || 0;
    $("#stStep").style.width = (sf || 0) * 100 + "%";
    $("#stStep").parentElement.classList.toggle("indet", sf == null);
    $("#stAll").style.width = f * 100 + "%";
    $("#stStepText").textContent = !st ? "" : st.step_eta != null ? `about ${fmtDur(st.step_eta)} left` : sf != null ? `${Math.round(sf * 100)}%` : "";
    $("#stAllText").textContent = !st ? "" : `All ${Math.round(f * 100)}%` + (st.eta != null && f < 0.999 ? `, about ${fmtDur(st.eta)} left` : "");
    document.title = st ? `${Math.round(f * 100)}% – Vizavi Studio` : "Vizavi Studio";
  } else {
    $("#stLabel").textContent = !p.ready ? "Starting – checking components…" :
      p.last_job && p.last_job.seconds >= 1 ? `Ready. Last job took ${fmtDur(p.last_job.seconds)}` : "Ready";
    document.title = "Vizavi Studio";
  }
  const bits = [];
  if (p.queue) bits.push(`${p.queue} waiting`);
  if (p.device && p.device !== "?") bits.push(`Renders on ${p.device}`);
  bits.push(p.watch ? "Watching Downloads" : "Downloads not watched");
  $("#stRight").textContent = p.busy && st && st.detail ? st.detail : bits.join("   ");
}

/* ---------- project list ---------- */
async function loadProjects() {
  const before = new Set(S.projects.map(p => p.name)), first = !S.projects.length;
  S.projects = await api("/api/projects");
  const added = S.projects.filter(p => !before.has(p.name));
  if (!first && added.length === 1) S.current = added[0].name;   // a project just created: show it
  if (!S.projects.find(p => p.name === S.current)) { S.current = S.projects[0]?.name || null; S.stamp = null; }
  renderNav();
  $("#empty").hidden = !!S.projects.length; $("#view").hidden = !S.projects.length; if (!S.projects.length) setWall(null);
  if (S.current) await loadProject(S.current);
}
function shortStage(st) {
  return { new: "Starting", transcribing: "Preparing", request_ready: "Your move: send to Claude", rendering_preview: "Rendering preview",
    preview_ready: "Your move: review the preview", rendering_final: "Rendering final", done: "Finished",
    error: "Render failed: send to Claude", failed: "Setup failed", stopped: "Stopped: press Retry" }[st] || st;
}
function renderNav() {
  const sig = JSON.stringify([S.current, S.projects.map(p => [p.name, p.stage, p.updated, p.thumb, !!S.busyProj[p.name]])]);
  if (sig === S.navSig) return;
  S.navSig = sig;
  const nav = $("#projects"), focused = document.activeElement && nav.contains(document.activeElement) ? document.activeElement.dataset.name : null;
  nav.innerHTML = S.projects.map(p => `
    <button class="proj" data-name="${esc(p.name)}" data-turn="${turnOf(p.stage)}" data-busy="${!!S.busyProj[p.name]}" aria-current="${p.name === S.current}">
      <span class="th" style="${p.thumb ? `background-image:url('/thumb?name=${encodeURIComponent(p.name)}&v=${encodeURIComponent(p.updated)}')` : ""}"></span>
      <span><span class="nm">${esc(p.name)}</span><span class="sg">${esc(S.busyProj[p.name] ? "Working…" : shortStage(p.stage))}</span></span>
    </button>`).join("");
  if (focused) { const b = [...nav.children].find(x => x.dataset.name === focused); if (b) b.focus({ preventScroll: true }); }
}
$("#projects").addEventListener("click", e => { const b = e.target.closest(".proj"); if (b) select(b.dataset.name); });
$("#projects").addEventListener("contextmenu", e => {
  const b = e.target.closest(".proj"); if (!b) return; e.preventDefault(); select(b.dataset.name);
  const r = b.getBoundingClientRect(), kb = !e.clientX && !e.clientY, busy = !!S.busyProj[b.dataset.name];
  menu(kb ? r.left + 20 : e.clientX, kb ? r.bottom : e.clientY, [["Open folder", () => act("open_folder")],
    ["Redo transcript…", redoDialog, "", busy], ["Delete project…", deleteDialog, "danger", busy]]);
});
$("#projects").addEventListener("keydown", e => {
  const b = e.target.closest(".proj"); if (!b) return;
  if (e.key === "Delete") { e.preventDefault(); select(b.dataset.name).then(deleteDialog); }
  else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault(); const all = [...document.querySelectorAll(".proj")], i = all.indexOf(b) + (e.key === "ArrowDown" ? 1 : -1);
    if (all[i]) all[i].focus();
  }
});
async function select(name) {
  S.current = name; S.stamp = null; S.navSig = "";
  renderNav();
  await loadProject(name);
}

/* ---------- project view ---------- */
async function loadProject(name) {
  const p = await api(`/api/project?name=${encodeURIComponent(name)}`);
  if (S.current !== name) return;                                  // switched to another project meanwhile
  if (p.error) { S.version = -1; return; }
  const keepVideo = S.cur && S.cur.name === p.name && S.cur.preview === p.preview;
  S.cur = p;
  renderView(p, keepVideo);
}

function track(p) {
  const k = stepOf(p), turn = turnOf(p.stage);
  return `<div class="track" id="track"><div class="fill" style="width:${Math.min(k, 4) * 20}%"></div>` +
    STATIONS.map(([t, s], i) => {
      let c = i < k ? "done" : i === k ? (turn === "you" ? "you" : turn === "bad" ? "bad" : "work") : "";
      if (p.stage === "done") c = "done";
      return `<div class="st ${c}" data-i="${i}"><b>${t}</b>${s}${c === "work" ? '<span class="seg"><i></i></span>' : ""}</div>`;
    }).join("") + `</div>`;
}

function liveTrack() {
  const seg = $("#track .st.work .seg i"); if (!seg || !S.cur) return;
  if (S.running === S.cur.name || /New project/.test(S.job)) seg.style.width = ((S.status && S.status.frac) || 0) * 100 + "%";
}

const RANK = { P0: "Broken", P1: "Serious", P2: "Worth fixing", P3: "Polish" };
const RANK_TIP = { P0: "The video is broken – fix before anything else", P1: "A viewer would stop watching or misread it here",
  P2: "Costs attention – fix if there is time", P3: "Finishing touches" };
const issuesOf = p => p.issues || (p.flags || []).map(t => ({ rank: "P2", text: t }));
const serious = p => issuesOf(p).filter(i => i.rank === "P0" || i.rank === "P1");
function checksCard(p) {
  const iss = issuesOf(p), est = p.est_final_min, cost = p.scene_cost || [];
  if (!["preview_ready", "rendering_final", "done"].includes(p.stage) || (!iss.length && est == null && !cost.length)) return "";
  const tot = cost.reduce((a, c) => a + c[1], 0) || 1;
  const n = r => iss.filter(i => i.rank === r).length;
  const pills = ["P0", "P1", "P2", "P3"].filter(n).map(r => `<span class="pill rk ${r}" title="${esc(RANK_TIP[r])}">${n(r)} ${esc(RANK[r].toLowerCase())}</span>`).join("");
  return `<div class="card checks"><h3>Automatic checks ${pills || `<span class="pill okp">nothing found</span>`}</h3>
    ${est != null && p.stage === "preview_ready" ? `<p class="quiet est">The final render will take ${esc(fmtMin(est))} on this PC.</p>` : ""}
    ${iss.length ? `<details data-k="flags" ${n("P0") + n("P1") ? "open" : ""}><summary>What was found</summary><ul class="issues">${iss.map(i =>
      `<li><span class="rk ${esc(i.rank)}" title="${esc(RANK_TIP[i.rank] || "")}">${esc(RANK[i.rank] || i.rank)}</span>${esc(i.text)}</li>`).join("")}</ul>
      <p class="quiet" style="margin:6px 0 0">Claude gets this list with the review package and fixes the serious ones first.</p></details>` : ""}
    ${cost.length ? `<details data-k="cost"><summary>Where the render time goes</summary><table class="cost">${cost.map(([n, s]) =>
      `<tr><td>${esc(n)}</td><td><i style="width:${Math.max(2, 100 * s / tot)}%"></i></td><td>${Math.round(s)} s</td></tr>`).join("")}</table></details>` : ""}</div>`;
}

function problemLine(p) {
  const why = p.stop_reason === "stopped" ? "You stopped it." : p.stop_reason === "interrupted" ? "The app was closed or crashed while it was working." : "";
  return (why ? `<p class="quiet" style="margin:-6px 0 12px">${why}</p>` : "") +
    (p.problem && p.problem.length > 2 ? `<p class="problem">${esc(p.problem.slice(0, 500))}</p>` : "");
}

function sizePicker(p) {     // lowering the final size is the biggest speed-up there is: render time follows the pixel count
  const m = /(\d+)\D+(\d+)/.exec(p.size || ""); if (!m) return "";
  const long = Math.max(+m[1], +m[2]), cur = p.final_long_side || 0;
  const opts = [[0, `As ordered (${p.size})`], ...[1920, 1280].filter(v => v < long).map(v => [v, `${v} px long side (about ${(long * long / (v * v)).toFixed(1)}× faster)`])];
  return `<label class="fsize">Final size <select id="fsize" data-idle>${opts.map(([v, t]) => `<option value="${v}" ${v === cur ? "selected" : ""}>${esc(t)}</option>`).join("")}</select></label>`;
}
/* quick notes: each adds one line Claude reads as one separate change (text after the colon says where / what) */
const CHIPS = [["Bolder", "Bolder: "], ["Quieter", "Quieter (less motion/glow/music): "], ["Faster", "Faster pacing: "],
  ["Shorter", "Shorter: "], ["Bigger text", "Bigger, easier to read text: "], ["Fix sound", "Sound: "],
  ["Polish", "Polish: fix the remaining smaller findings from the automatic checks, change nothing else"]];
function addChip(label) {
  const ta = $("#notes"); if (!ta) return;
  const line = (CHIPS.find(c => c[0] === label) || [0, label + ": "])[1];
  ta.value = ta.value.replace(/\s*$/, "") + (ta.value.trim() ? "\n" : "") + "• " + line;
  ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length);
  ta.dispatchEvent(new Event("input", { bubbles: true }));
}
function ruleDialog() {
  const ta = $("#notes"), sel = ta && ta.selectionEnd > ta.selectionStart ? ta.value.slice(ta.selectionStart, ta.selectionEnd) : "";
  const first = (sel || (ta ? ta.value : "")).split("\n").map(l => l.replace(/^[•\-\s]+/, "").trim()).filter(Boolean);
  openDialog(`<div class="dh"><h2>Save as a rule</h2><button class="link" data-close>Close</button></div>
    <div class="db"><p class="quiet" style="margin-top:0">A rule is added to every new project (Settings → My rules). Write it so it is true for all your videos – e.g. “Captions sit above the bottom quarter”, not “move this caption”.</p>
    <textarea id="ruleTxt" style="min-height:90px" autofocus>${esc(first.length === 1 ? first[0] : sel.trim())}</textarea></div>
    <div class="df"><span class="err grow" id="ruleErr"></span><button class="btn" data-close>Cancel</button><button class="btn primary" id="ruleSave">Save rule</button></div>`,
    d => $("#ruleSave", d).onclick = async () => {
      try { const r = await api("/api/act", { action: "add_rule", text: $("#ruleTxt").value });
        S.meta = await api("/api/meta"); dlg.close(); toast(r.added ? "Rule saved – new projects follow it" : "You already have that rule", r.added ? "done" : "info", 4000); }
      catch (e) { $("#ruleErr").textContent = e.message; }
    });
}
function moveCard(p) {
  const zip = p.last_zip ? `<code>${esc(p.last_zip)}</code>` : "the zip";
  switch (p.stage) {
    case "request_ready": return `<div class="move"><h2>Send it to Claude</h2>
      <p>Drag ${zip} into a new Claude chat, paste the message and send. Download the zip Claude replies with – it's picked up here automatically.</p>
      <div class="row"><button class="btn primary" data-a="copy">Copy message</button><button class="btn" data-a="reveal_zip">Show zip</button>
      <button class="btn" data-a="open_claude">Open Claude</button></div></div>`;
    case "preview_ready": return `<div class="move"><h2>Watch the preview</h2>
      <p>Happy with it? Approve and the final renders right away. Want changes? Write them below and send the review zip to the same Claude chat.</p>
      <div class="row"><button class="btn primary" data-a="approve" data-idle>Approve and render final</button>
      <button class="btn" data-a="copy">Copy message</button><button class="btn" data-a="reveal_zip">Show review zip</button>${sizePicker(p)}</div>
      <div class="notes"><div class="chips" role="group" aria-label="Quick notes">${CHIPS.map(([t]) => `<button class="chip" data-chip="${esc(t)}">${esc(t)}</button>`).join("")}</div>
      <textarea id="notes" placeholder="What should change, what should stay – Claude reads this first. Saved as you type. One change per line works best."></textarea>
      <div class="row" style="margin-top:8px"><button class="btn" data-a="notes" data-idle>Build review package with these notes</button><span class="quiet grow" id="notesState"></span>
      <button class="link" data-a="add_rule" title="Keep a note for every future project (Settings → My rules)">Save as a rule…</button></div></div></div>`;
    case "error": return `<div class="move bad"><h2>The render failed</h2>
      <p>If a file was missing (e.g. your footage), add it and press <b>Retry render</b>. Otherwise drag ${zip} into the same Claude chat and paste the message – Claude sends back a fixed zip.</p>
      ${problemLine(p)}
      <div class="row"><button class="btn primary" data-a="retry" data-idle>Retry render${p.retry ? ` (${esc(p.retry)})` : ""}</button>
      <button class="btn" data-a="add_assets" data-idle>Add footage / assets…</button>
      <button class="btn" data-a="copy">Copy message</button><button class="btn" data-a="reveal_zip">Show error zip</button></div>
      <p class="quiet" style="margin-top:8px">Project assets: ${p.assets && p.assets.length ? p.assets.map(x => `${esc(x.name)} (${x.mb} MB)`).join(", ") : "none"}</p></div>`;
    case "stopped": return `<div class="move bad"><h2>Stopped</h2>
      <p>The ${p.failed_kind === "final" ? "final" : "preview"} render did not finish. Nothing is wrong with your project – press <b>Retry render</b> to run it again.</p>
      ${problemLine(p)}
      <div class="row"><button class="btn primary" data-a="retry" data-idle>Retry render${p.retry ? ` (${esc(p.retry)})` : ""}</button>
      <button class="btn" data-a="add_assets" data-idle>Add footage / assets…</button>${p.failed_kind === "final" ? sizePicker(p) : ""}</div></div>`;
    case "done": return `<div class="move done"><h2>Finished</h2><p>The final files are in the output folder.</p>
      <div class="row"><button class="btn primary" data-a="open_folder">Open output folder</button></div></div>`;
    case "failed": return `<div class="move bad"><h2>Setup failed</h2><p>Start a new project with the same files, then delete this one.</p>
      ${problemLine(p)}
      <div class="row"><button class="btn" data-a="new">New project</button><button class="btn danger" data-a="delete" data-idle>Delete project</button></div></div>`;
    default: return `<div class="move work"><h2>${esc({ rendering_preview: "Rendering the preview", rendering_final: "Rendering the final", transcribing: "Preparing the narration" }[p.stage] || "Working")}</h2>
      <p>Progress and time left are shown along the bottom. You can start other projects meanwhile – they queue up.</p></div>`;
  }
}

const inl = t => esc(t).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\*(.+?)\*/g, "<em>$1</em>").replace(/`(.+?)`/g, "<code>$1</code>");
function mdLite(md) {
  md = md.replace(/^(#+\s.*)$/gm, "\n$1\n");
  let unsure = false;
  return md.split(/\n{2,}/).map(b => b.trim()).filter(Boolean).map(b => {
    if (/^#+\s/.test(b)) { const h = b.replace(/^#+\s*/, ""); unsure = /uncertain|unsure|ishonchsiz/i.test(h); return `<h4>${inl(h)}</h4>`; }
    if (/^\s*[-*]\s/m.test(b)) return `<ul${unsure ? ' class="unsure"' : ""}>${b.split("\n").filter(l => l.trim()).map(l => `<li>${inl(l.replace(/^\s*[-*]\s*/, ""))}</li>`).join("")}</ul>`;
    return `<p>${inl(b)}</p>`;
  }).join("");
}

function setWall(p) {   // the current project's frame, heavily blurred, sits behind the glass
  const i = $("#wall i"), url = p && p.thumb ? `url('/thumb?name=${encodeURIComponent(p.name)}&v=${encodeURIComponent(p.updated)}')` : "";
  if (i.dataset.url !== url) { i.dataset.url = url; i.style.backgroundImage = url; i.classList.toggle("on", !!url); }
}
function applyBusy() {
  const busy = !!(S.cur && S.busyProj[S.cur.name]);
  document.querySelectorAll("#view [data-idle]").forEach(b => { b.disabled = busy; b.title = busy ? "Wait until this project has finished (or press Stop)" : ""; });
}
function renderView(p, keepVideo) {
  const sig = JSON.stringify(p);
  if (sig === S.viewSig && $("#view").childElementCount) { applyBusy(); return; }       // nothing changed: leave the page alone
  S.viewSig = sig;
  setWall(p);
  const v = $("#view");
  const oldVideo = keepVideo ? $("#pv") : null;
  const oldNotes = $("#notes"), hadFocus = oldNotes && document.activeElement === oldNotes;
  if (oldNotes && v.dataset.name === p.name) S.drafts[p.name] = oldNotes.value;           // never lose what you were typing
  const sel = hadFocus ? [oldNotes.selectionStart, oldNotes.selectionEnd] : null;
  const txScroll = v.dataset.name === p.name && $(".tx") ? $(".tx").scrollTop : 0;
  v.dataset.name = p.name;
  const facts = [p.preset, p.size, `${p.fps} fps`, p.duration ? fmtDur(p.duration) : null,
    p.variants && p.variants.length > 1 ? `also ${p.variants.slice(1).join(", ")}` : null].filter(Boolean);
  const tx = p.transcript ? mdLite(p.transcript) : p.alignment ? mdLite(p.alignment.split("\n").slice(0, 30).join("\n")) : "<p>No transcript yet.</p>";
  v.innerHTML = `
    <div class="ph"><div><h1>${esc(p.name)}</h1><div class="facts">${facts.map(f => `<span class="pill">${esc(f)}</span>`).join("")}</div></div>
      <div class="ph-actions">${p.has_code ? `<button class="btn ghost small" data-a="save_style" title="Keep this video's look for new projects">Save as style…</button>` : ""}
      <button class="btn ghost small" data-a="open_folder">Open folder</button>
      <button class="btn ghost small" data-a="more" aria-label="More actions" aria-haspopup="menu">More</button></div></div>
    ${track(p)}
    ${moveCard(p)}
    ${checksCard(p)}
    <div class="grid2">
      <div class="card"><h3>${p.stage === "done" ? "Final" : "Preview"}</h3><div id="vidSlot">${p.preview ? "" : `<p class="quiet">The preview appears here after Claude's first zip is rendered.</p>`}</div>
        ${p.outputs.length ? `<ul class="outs" style="margin-top:12px">${p.outputs.map(o => `<li><button class="link" data-a="reveal_output" data-file="${esc(o.name)}">${esc(o.name)}</button><span class="mb">${o.mb != null ? o.mb + " MB" : ""}</span></li>`).join("")}</ul>` : ""}
      </div>
      <div class="card"><h3>Transcript ${p.has_narration ? `<button class="btn ghost small" data-a="redo" data-idle>Redo…</button>` : ""}</h3>
        <div class="tx">${tx}</div></div>
    </div>
    <div class="hist">${(p.history || []).slice().reverse().map(h => `<div><span>${esc(h[0])}</span><span>${esc(h[2])}</span></div>`).join("")}</div>`;
  const slot = $("#vidSlot");
  const src = p.stage === "done" && p.outputs.find(o => o.url) ? p.outputs.find(o => o.url).url : p.preview;
  if (src) {
    if (oldVideo && oldVideo.dataset.src === src) slot.append(oldVideo);
    else {
      const vid = document.createElement("video"); vid.id = "pv"; vid.controls = true; vid.preload = "metadata";
      vid.poster = `/thumb?name=${encodeURIComponent(p.name)}&v=${encodeURIComponent(p.updated)}`; vid.src = src; vid.dataset.src = src;
      const playing = on => document.documentElement.classList.toggle("playing", on);   // lighter effects while a video plays
      vid.onplay = () => playing(true); vid.onpause = vid.onended = () => playing(false);
      slot.append(vid);
    }
  }
  const ta = $("#notes");
  if (ta) {
    ta.value = S.drafts[p.name] ?? p.notes_saved ?? "";
    if (sel) { ta.focus({ preventScroll: true }); ta.setSelectionRange(sel[0], sel[1]); }
  }
  if ($(".tx") && txScroll) $(".tx").scrollTop = txScroll;
  document.querySelectorAll("#view details[data-k]").forEach(d => { d.open = d.dataset.k in S.ui ? !!S.ui[d.dataset.k] : d.hasAttribute("open"); d.addEventListener("toggle", () => { S.ui[d.dataset.k] = d.open; }); });
  liveTrack();
  applyBusy();
}

$("#view").addEventListener("change", async e => {
  if (e.target.id !== "fsize" || !S.cur) return;
  const r = await act("set_final_size", { value: +e.target.value });
  if (r) toast(+e.target.value ? "Final will be rendered at the smaller size" : "Final will be rendered at the ordered size", "info", 3500);
  else await loadProject(S.cur.name);
});

/* auto-save of the notes while typing (only the small notes file, no zip is built) */
let notesTimer = null;
$("#view").addEventListener("input", e => {
  if (e.target.id !== "notes" || !S.cur) return;
  const name = S.cur.name, v = e.target.value;
  S.drafts[name] = v; const st = $("#notesState"); if (st) st.textContent = "Typing…";
  clearTimeout(notesTimer);
  notesTimer = setTimeout(async () => {
    let ok = true;
    try { await api("/api/act", { action: "save_notes", name, text: v }); } catch { ok = false; }
    const s2 = $("#notesState"); if (s2 && S.cur && S.cur.name === name) s2.textContent = ok ? "Saved" : "Not saved yet";
  }, 1200);
});

/* ---------- actions ---------- */
async function act(action, extra = {}, name = S.current) {
  try { return await api("/api/act", { action, name, ...extra }); } catch (e) { toast(e.message, "error"); }
}
$("#view").addEventListener("click", async e => {
  const chip = e.target.closest("[data-chip]"); if (chip) return addChip(chip.dataset.chip);
  const b = e.target.closest("[data-a]"); if (!b || b.disabled) return;
  const a = b.dataset.a, p = S.cur;
  if (a === "copy") return copy(p.message);
  if (a === "approve") { const bad = serious(p); if (bad.length) return approveDialog(p, bad); return approveNow(); }
  if (a === "notes") {
    const t = ($("#notes").value || "").trim(); if (!t) return toast("Write your notes first", "warn", 3500);
    clearTimeout(notesTimer);
    const r = await act("notes", { text: t });
    if (r && r.message) copy(r.message, "Message copied – the review package with your notes follows in a moment");
    return;
  }
  if (a === "redo") return redoDialog();
  if (a === "add_rule") return ruleDialog();
  if (a === "save_style") return styleDialog();
  if (a === "delete") return deleteDialog();
  if (a === "new") return newProject({});
  if (a === "more") {
    const r = b.getBoundingClientRect(), busy = !!S.busyProj[p.name];
    return menu(r.left, r.bottom + 4, [["Show latest zip", () => act("reveal_zip")],
      ...(p.retry ? [[`Render again (${p.retry})`, retryRender, "", busy]] : []), ["Add footage / assets…", addAssets, "", busy],
      ...(p.has_code ? [["Save as style…", styleDialog]] : []),
      ["Redo transcript…", redoDialog, "", busy], ["Delete project…", deleteDialog, "danger", busy]]);
  }
  if (a === "reveal_output") return act("reveal_output", { file: b.dataset.file });
  if (a === "retry") return retryRender();
  if (a === "add_assets") return addAssets();
  act(a);
});
async function retryRender() {
  if (S.cur && S.busyProj[S.cur.name]) return toast("This project is already being processed", "warn", 4000);
  const r = await act("retry"); if (r) toast("Render queued – progress along the bottom", "info", 3500);
}
function addAssets() {
  const name = S.current;
  pick(false, async paths => {
    if (!paths.length) return;
    const r = await act("add_assets", { paths }, name);
    if (r && r.added) toast(r.added.length ? `Added: ${r.added.join(", ")} – now press Retry render` : "Nothing added", r.added.length ? "move" : "warn");
  });
}

/* menus: arrow keys, Home/End, Esc and Tab, focus returns to where it came from */
let menuOpener = null, menuOff = null;
function closeMenus(refocus) {
  document.querySelectorAll(".menu").forEach(m => m.remove());
  if (menuOff) { document.removeEventListener("click", menuOff); menuOff = null; }
  if (refocus && menuOpener && menuOpener.isConnected) menuOpener.focus({ preventScroll: true });
}
function menu(x, y, items) {
  closeMenus();
  menuOpener = document.activeElement;
  const m = document.createElement("div"); m.className = "menu"; m.setAttribute("role", "menu");
  items.forEach(([t, fn, cls, dis]) => {
    const b = document.createElement("button"); b.setAttribute("role", "menuitem"); b.textContent = t; b.disabled = !!dis;
    if (cls) b.className = cls; b.onclick = () => { closeMenus(true); fn(); }; m.append(b);
  });
  document.body.append(m);
  m.style.left = Math.max(8, Math.min(x, innerWidth - m.offsetWidth - 8)) + "px";
  m.style.top = Math.max(8, Math.min(y, innerHeight - m.offsetHeight - 8)) + "px";
  const live = () => [...m.children].filter(b => !b.disabled);
  (live()[0] || m).focus?.();
  m.addEventListener("keydown", e => {
    const l = live(), i = l.indexOf(document.activeElement);
    if (e.key === "ArrowDown") { e.preventDefault(); l[(i + 1) % l.length]?.focus(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); l[(i - 1 + l.length) % l.length]?.focus(); }
    else if (e.key === "Home") { e.preventDefault(); l[0]?.focus(); }
    else if (e.key === "End") { e.preventDefault(); l[l.length - 1]?.focus(); }
    else if (e.key === "Escape") { e.preventDefault(); closeMenus(true); }
    else if (e.key === "Tab") closeMenus();
  });
  setTimeout(() => { menuOff = ev => { if (!m.contains(ev.target)) closeMenus(); }; document.addEventListener("click", menuOff); }, 0);
}

/* ---------- dialogs ---------- */
const dlg = $("#dlg");
function openDialog(html, onMount) {
  if (dlg.open) dlg.close();
  dlg.innerHTML = html; dlg.showModal(); const r = onMount && onMount(dlg);
  Promise.resolve(r).then(() => { const db = dlg.querySelector(".db"); if (db) db.tabIndex = -1;
    const a = dlg.querySelector("[autofocus]"); (a || db || dlg).focus({ preventScroll: true }); });
}
dlg.addEventListener("click", e => { if (e.target.closest("[data-close]")) dlg.close(); });

function deleteDialog() {
  const p = S.cur; if (!p) return;
  openDialog(`<div class="dh"><h2>Delete “${esc(p.name)}”?</h2></div>
    <div class="db"><p>The whole project folder – narration copy, renders and zips – goes to <b>Recently deleted</b>. You can restore it from <b>Settings</b> for ${(S.meta && S.meta.trash_days) || 30} days.</p></div>
    <div class="df"><button class="btn" data-close autofocus>Keep it</button><button class="btn danger" id="del">Delete project</button></div>`,
    d => $("#del", d).onclick = async () => {
      dlg.close(); const r = await act("delete", {}, p.name);
      if (r) { toast(`Deleted “${p.name}” – restore it in Settings → Recently deleted`, "info", 5000); S.meta = await api("/api/meta").catch(() => S.meta); S.cur = null; S.viewSig = ""; if (S.current === p.name) { S.current = null; S.stamp = null; } await loadProjects().catch(() => {}); }
    });
}

async function approveNow(name = S.current) {
  const r = await act("approve", {}, name); if (r) toast("Final queued – progress along the bottom", "info", 3500);
}
function approveDialog(p, bad) {
  openDialog(`<div class="dh"><h2>Render the final anyway?</h2><button class="link" data-close>Close</button></div>
    <div class="db"><p>The automatic checks found ${bad.length} serious problem${bad.length === 1 ? "" : "s"} in this preview:</p>
    <ul class="issues">${bad.slice(0, 6).map(i => `<li><span class="rk ${esc(i.rank)}">${esc(RANK[i.rank])}</span>${esc(i.text)}</li>`).join("")}</ul>
    ${bad.length > 6 ? `<p class="quiet">…and ${bad.length - 6} more.</p>` : ""}
    <p class="quiet">Sending the review package to Claude fixes them first. If you checked and they are fine (an effect on purpose, for example), render anyway.</p></div>
    <div class="df"><button class="btn" id="apAny">Render final anyway</button><button class="btn primary" data-close autofocus>Go back</button></div>`,
    d => $("#apAny", d).onclick = () => { dlg.close(); approveNow(p.name); });
}

function redoDialog() {
  const p = S.cur; if (!p) return;
  openDialog(`<div class="dh"><h2>Redo transcript</h2><button class="link" data-close>Close</button></div>
    <div class="db"><p style="color:var(--quiet);margin-top:0">Paste the exact script for perfect spelling; timing still comes from the voice. Leave it empty to let the Uzbek speech model and Claude work it out.</p>
    <textarea id="rs" style="min-height:260px">${esc(p.script)}</textarea></div>
    <div class="df"><button class="btn" data-close>Cancel</button><button class="btn primary" id="go">Redo transcript</button></div>`,
    d => $("#go", d).onclick = async () => { const t = $("#rs").value; dlg.close(); const r = await act("redo", { text: t }, p.name); if (r) toast("Transcript queued – a new request zip follows", "info", 4000); });
}

function styleDialog() {
  const p = S.cur; if (!p) return;
  const taken = (S.meta && S.meta.saved_styles || []).map(s => s.name);
  openDialog(`<div class="dh"><h2>Save as style</h2><button class="link" data-close>Close</button></div>
    <div class="db"><p class="quiet" style="margin:0 0 14px">Keeps the look of “${esc(p.name)}” – its code, frames from the video and its fonts.
      Pick it under <b>Look → Match a saved style</b> in a new project and Claude makes the new video in the same style (new content).</p>
    <div class="fg"><label class="f s3"><span>Style name</span><input type="text" id="stName" maxlength="60" value="${esc(p.name.replace(/_/g, " "))}" autofocus></label>
    <label class="f s3"><span>What you like about it – Claude must keep this (optional)</span>
      <textarea id="stNote" rows="4" placeholder="e.g. the paper map look, the big bold type, the slow push-ins, soft pops on every beat"></textarea></label></div>
    <p class="err" id="stWarn" style="margin:10px 0 0"></p></div>
    <div class="df"><button class="btn" data-close>Cancel</button><button class="btn primary" id="stSave">Save style</button></div>`, d => {
    const warn = () => { $("#stWarn").textContent = taken.includes($("#stName").value.trim()) ? "A style with this name exists – saving replaces it." : ""; };
    $("#stName", d).oninput = warn; warn();
    $("#stSave", d).onclick = async () => {
      const name = $("#stName").value.trim(); if (!name) { $("#stWarn").textContent = "Give the style a name."; return; }
      $("#stSave").disabled = true;
      const r = await act("save_style", { style_name: name, note: $("#stNote").value }, p.name);
      if (r && r.style) { dlg.close(); S.meta = await api("/api/meta"); toast(`Style “${r.style.name}” saved – choose it under Look in a new project`, "done", 6000); }
      else $("#stSave").disabled = false;
    };
  });
}

function applyFx() {
  const on = !!(S.meta && S.meta.settings && S.meta.settings.light_effects);
  if (on) document.documentElement.dataset.fx = "light"; else delete document.documentElement.dataset.fx;
}
function settingsDialog() {
  const s = S.meta.settings;
  openDialog(`<div class="dh"><h2>Settings</h2><button class="link" data-close>Close</button></div><div class="db">
    <div class="fs"><h3>My rules<small>Added to every new project as must-follow rules.</small></h3>
      <textarea id="rules" style="min-height:120px" placeholder="On-screen text in Uzbek Latin only&#10;Scientifically accurate, no fantasy visuals">${esc(s.standing_rules || "")}</textarea></div>
    <div class="fs"><h3>Appearance</h3><div><div class="togs seg" id="theme">${[["", "Automatic"], ["light", "Light"], ["dark", "Dark"]].map(([v, t]) =>
      `<label class="chk tog"><input type="radio" name="theme" value="${v}" ${(theme() === v) ? "checked" : ""}>${t}</label>`).join("")}</div>
      <label class="chk sw" style="margin-top:8px"><input type="checkbox" id="fx" ${s.light_effects ? "checked" : ""}>Lighter visual effects (smoother on slower PCs)</label></div></div>
    <div class="fs"><h3>Updates<small>New versions come from GitHub; your projects and settings are never touched.</small></h3><div>
      <label class="chk sw"><input type="checkbox" id="cu" ${s.check_updates !== false ? "checked" : ""}>Check for updates automatically</label>
      <div class="row" style="margin-top:6px"><span class="quiet grow">You have Vizavi Studio ${esc(S.meta.version || "?")}</span>
      <button class="btn small" id="cuNow">Check now</button>${S.meta.can_undo_update ? `<button class="btn small" id="cuUndo">Undo last update</button>` : ""}</div></div></div>
    <div class="fs"><h3>Saved styles<small>Made with “Save as style…” on a project page.</small></h3><div id="stList">${styleList()}</div></div>
    <div class="fs"><h3>Recently deleted<small>Deleted projects and styles stay here for ${S.meta.trash_days || 30} days.</small></h3><div><div id="trList">${trashList()}</div>
      <div class="row" style="margin-top:6px"><span class="quiet grow">A small backup of your styles and project texts is made every day.</span><button class="btn small" id="bkOpen">Open backups</button></div></div></div>
    <div class="fs"><h3>Behaviour</h3><div>
      <label class="chk sw"><input type="checkbox" id="w" ${s.watch_downloads ? "checked" : ""}>Pick up Claude's zips from Downloads</label>
      <label class="chk sw"><input type="checkbox" id="pt" ${s.precise_timing ? "checked" : ""}>Precise word timing (MMS, non-commercial)</label></div></div>
    <div class="fs"><h3>Folders</h3><div class="fg">
      <label class="f s3"><span>Projects</span><input type="text" id="pd" value="${esc(s.projects_dir)}"></label>
      <label class="f s3"><span>Downloads (watched)</span><input type="text" id="dd" value="${esc(s.downloads_dir)}"></label></div></div>
    <div class="fs"><h3>Speech</h3><div class="fg">
      <label class="f"><span>Whisper model</span><input type="text" id="wm" value="${esc(s.whisper_model)}"></label>
      <label class="f s2"><span>Uzbek model (empty = off)</span><input type="text" id="um" value="${esc(s.uzbek_model || "")}"></label></div></div>
    <div class="fs"><h3>This PC<small>Speech models, render workers and what gets installed follow this.</small></h3><div>
      <ul class="hw">${(S.meta.hw || []).map(l => `<li>${esc(l)}</li>`).join("")}</ul>
      <ul class="hw where">${(S.meta.storage || []).map(x => `<li><b>${esc(x.what)}:</b> ${esc(x.path)}${x.free_gb != null ? ` <span class="quiet">(${x.free_gb} GB free)</span>` : ""}</li>`).join("")}</ul>
      <p class="quiet" style="margin:0 0 10px">To move Vizavi Studio to another drive, run the installer again and choose that drive – it takes everything along.</p>
      ${(S.meta.warnings || []).map(w => `<p class="err">${esc(w)}</p>`).join("")}
      <button class="btn" id="rc">Check and repair components</button></div></div>
    </div><div class="df"><span class="err grow" id="seterr"></span><button class="btn" data-close>Cancel</button><button class="btn primary" id="sv">Save settings</button></div>`, d => {
    $("#theme", d).onchange = e => setTheme(e.target.value);
    $("#cuNow", d).onclick = async () => {
      try { const r = await api("/api/act", { action: "check_update" });
        if (r.newer) { try { localStorage.removeItem("vz-upd-later"); } catch {} dlg.close(); toast(`Vizavi Studio ${r.latest} is available – see the bar at the top`, "move"); }
        else toast(`You have the newest version (${r.current}).`, "done", 5000);
      } catch (e) { toast(e.message, "error"); }
    };
    const undo = $("#cuUndo", d);
    if (undo) undo.onclick = async () => { try { await api("/api/act", { action: "undo_update" }); dlg.close(); } catch (e) { toast(e.message, "error"); } };
    $("#stList", d).onclick = async e => {
      const b = e.target.closest("[data-delstyle]"); if (!b) return;
      try { await api("/api/act", { action: "delete_style", id: b.dataset.delstyle }); S.meta = await api("/api/meta"); $("#stList").innerHTML = styleList(); toast("Style deleted", "info", 2500); }
      catch (err) { toast(err.message, "error"); }
    };
    $("#trList", d).onclick = async e => {
      const b = e.target.closest("[data-tr]"); if (!b) return;
      const purge = b.dataset.how === "purge";
      if (purge && !b.dataset.sure) { b.dataset.sure = "1"; b.textContent = "Sure? Click again"; return; }
      b.disabled = true;
      try {
        const r = await api("/api/act", { action: purge ? "purge_deleted" : "restore_deleted", id: b.dataset.tr });
        S.meta = await api("/api/meta"); $("#trList").innerHTML = trashList(); $("#stList").innerHTML = styleList();
        if (purge) toast("Removed for good", "info", 2500);
        else { toast(r.kind === "project" ? `Restored project “${r.name}”` : `Restored style “${r.name}”`, "done", 4000); if (r.kind === "project") loadProjects().catch(() => {}); }
      } catch (err) { b.disabled = false; toast(err.message, "error"); }
    };
    $("#bkOpen", d).onclick = () => act("open_backups", {}, null);
    $("#rc", d).onclick = async () => { const r = await act("recheck", {}, null); if (r) toast("Checking components – see the log", "info", 3000); };
    $("#sv", d).onclick = async () => {
      $("#sv").disabled = true; $("#seterr").textContent = "";
      try {
        await api("/api/settings", { standing_rules: $("#rules").value, watch_downloads: $("#w").checked, precise_timing: $("#pt").checked,
          light_effects: $("#fx").checked, check_updates: $("#cu").checked, projects_dir: $("#pd").value, downloads_dir: $("#dd").value, whisper_model: $("#wm").value, uzbek_model: $("#um").value });
        S.meta = await api("/api/meta"); applyFx(); dlg.close(); toast("Settings saved", "info", 2500);
      } catch (e) { $("#seterr").textContent = e.message; $("#sv").disabled = false; }
    };
  });
}

function trashList() {
  const L = (S.meta && S.meta.trash) || [];
  return L.length ? L.map(t => `<div class="strow"><span class="grow"><b>${esc(t.name)}</b><small class="quiet"> ${t.kind === "style" ? "style" : "project"} · deleted ${esc(t.deleted)} · ${t.days_left} day${t.days_left === 1 ? "" : "s"} left</small></span>
      <button class="btn small" data-tr="${esc(t.id)}" data-how="restore">Restore</button><button class="btn small danger" data-tr="${esc(t.id)}" data-how="purge">Delete for good</button></div>`).join("")
    : `<p class="quiet">Nothing here.</p>`;
}
function styleList() {
  const L = (S.meta && S.meta.saved_styles) || [];
  return L.length ? L.map(s => `<div class="strow">${s.thumb ? `<img class="sref" src="/style_thumb?id=${encodeURIComponent(s.id)}" alt="">` : ""}
      <span class="grow"><b>${esc(s.name)}</b><small class="quiet"> from ${esc(s.source_project)}${s.note ? " – " + esc(s.note) : ""}</small></span>
      <button class="btn small danger" data-delstyle="${esc(s.id)}">Delete</button></div>`).join("")
    : `<p class="quiet">None yet – open a project Claude has made a video for and press “Save as style…”.</p>`;
}

/* ---------- new project ---------- */
const NP = { narration: null, music: null, assets: [], script: "" };
const opt = (obj, sel) => Object.entries(obj).map(([k, v]) => `<option value="${esc(k)}" ${k == sel ? "selected" : ""}>${esc(v)}</option>`).join("");
const optl = (arr, sel, label = v => v) => arr.map(v => `<option value="${esc(v)}" ${v == sel ? "selected" : ""}>${esc(label(v))}</option>`).join("");
const LANG = { uz: "Uzbek", auto: "Detect automatically", en: "English", ru: "Russian", tr: "Turkish", kk: "Kazakh", ky: "Kyrgyz",
  tg: "Tajik", de: "German", fr: "French", es: "Spanish", ar: "Arabic", zh: "Chinese", ja: "Japanese", ko: "Korean" };
const nice = v => String(v).replace(/ · /g, ", ").replace(/_/g, " ").replace(/^./, c => c.toUpperCase());
const base = p => (p || "").split(/[\\/]/).pop();

/* New project: five short steps (like an upload wizard) instead of one long form.
   1 Voice & files  2 Details  3 Format  4 Look  5 Review. A preset (step 3) fills every technical setting; the
   fine controls sit under "Change size, captions, sound…" and keep the preset's values until you touch them. */
const NP_STEPS = [["files", "Voice & files"], ["details", "Details"], ["format", "Format"], ["look", "Look"], ["review", "Review"]];
async function newProject(prefill = {}) {
  if (!S.meta) return toast("Still starting – try again in a moment", "warn", 4000);
  Object.assign(NP, { narration: null, music: null, assets: [], script: "", step: 0, o: null }, prefill);
  const M = S.meta, preset = M.last_preset && M.presets.includes(M.last_preset) ? M.last_preset : M.presets[0];
  openDialog(`<div class="dh"><h2>New project</h2><button class="link" data-close>Close</button></div>
    <ol class="steps" id="npSteps" aria-label="Steps">${NP_STEPS.map(([k, t], i) =>
      `<li><button type="button" data-go="${i}" aria-label="Step ${i + 1}: ${esc(t)}"><i>${i + 1}</i><span>${esc(t)}</span></button></li>`).join("")}</ol>
    <div class="db" id="npb"></div>
    <div class="df"><span class="err grow" id="nperr" role="alert"></span>
    <span class="row" id="presetBox" hidden><input type="text" id="presetName" placeholder="Name this preset" maxlength="40" aria-label="Preset name" style="width:180px">
      <button class="btn small primary" id="presetOk">Save</button><button class="btn small" id="presetNo">Cancel</button></span>
    <button class="btn" id="savePreset" title="Keep these settings as a preset for next time">Save as preset</button>
    <button class="btn" id="npBack">Back</button>
    <button class="btn primary" id="npNext">Next</button>
    <button class="btn primary" id="create">Create package for Claude</button></div>`, async () => {
    try { await fillForm(await api(`/api/preset?name=${encodeURIComponent(preset)}`), preset); }
    catch (e) { $("#nperr").textContent = e.message; return; }
    $("#create").onclick = createProject; $("#savePreset").onclick = presetInput;
    $("#presetNo").onclick = () => { $("#presetBox").hidden = true; $("#savePreset").hidden = false; };
    $("#presetOk").onclick = savePreset;
    $("#presetName").onkeydown = e => { if (e.key === "Enter") { e.preventDefault(); savePreset(); } else if (e.key === "Escape") { e.stopPropagation(); $("#presetNo").click(); } };
    $("#npBack").onclick = () => goStep(NP.step - 1);
    $("#npNext").onclick = () => goStep(NP.step + 1, true);
    $("#npSteps").onclick = e => { const b = e.target.closest("[data-go]"); if (b) goStep(+b.dataset.go); };
  });
}
function goStep(i, guard) {      // guard: the Next button checks that step 1 has what the video needs
  i = Math.max(0, Math.min(NP_STEPS.length - 1, i));
  if (guard && i > NP.step && NP.step === 0 && !NP.narration && !NP.music && (NP.o && NP.o.duration.mode !== "fixed")) {
    $("#nperr").textContent = "Add the voice recording (or a music file) first – the length of the video comes from it.";
    return;
  }
  $("#nperr").textContent = "";
  NP.step = i;
  document.querySelectorAll("#npb .npstep").forEach(s => { s.hidden = s.dataset.step !== NP_STEPS[i][0]; });
  document.querySelectorAll("#npSteps li").forEach((li, k) => { li.className = k < i ? "done" : k === i ? "cur" : "";
    li.querySelector("button").setAttribute("aria-current", k === i ? "step" : "false"); });
  const last = i === NP_STEPS.length - 1;
  $("#npBack").hidden = i === 0; $("#npNext").hidden = last; $("#create").hidden = !last;
  $("#savePreset").hidden = !last || !$("#presetBox").hidden;
  if (last) renderReview();
  const db = $("#npb"); db.scrollTop = 0;
  const f = db.querySelector(`.npstep[data-step="${NP_STEPS[i][0]}"] [data-first]`);
  if (f && dlg.open) f.focus({ preventScroll: true });
}

const TEXTF = ["name", "wants", "care", "believe", "script"];
function typedText() {      // only what you typed yourself survives a change of preset
  const keep = {};
  for (const id of TEXTF) { const el = $("#" + id); if (el && el.dataset.dirty) keep[id] = el.value; }
  const sc = $("#script"); if (sc) NP.script = sc.value;
  return keep;
}
const presetTitle = n => n.replace(/\s*\(.*\)\s*$/, "");
const presetSub = n => (/\((.*)\)\s*$/.exec(n) || [])[1] || "";
function aspectBox(w, h) {     // a small frame of the right shape on each preset card
  const k = 26 / Math.max(w, h);
  return `<span class="ab" style="width:${Math.max(8, Math.round(w * k))}px;height:${Math.max(8, Math.round(h * k))}px"></span>`;
}
async function fillForm(o, preset, keep = {}) {
  const M = S.meta, sizeKey = Object.entries(M.sizes).find(([k, v]) => v[0] === o.size[0] && v[1] === o.size[1])?.[0] || "custom";
  for (const k of ["name", "wants", "care", "believe"]) if (keep[k] !== undefined) o[k] = keep[k];
  NP.o = o;
  const name = o.name || (NP.narration ? base(NP.narration).replace(/\.[^.]+$/, "") : "");
  const cards = M.preset_cards || {}, rules = (M.settings.standing_rules || "").split("\n").map(x => x.trim()).filter(Boolean);
  const styles = M.saved_styles || [];
  $("#npb").innerHTML = `
  <section class="npstep" data-step="files">
    <p class="lead">Start with the voice recording – everything is timed to it.</p>
    <div class="fg">
      <div class="f s3"><span>Voice recording</span><div class="slot big" id="slotN"></div></div>
      <label class="f"><span>Spoken language</span><select id="lang">${optl(M.langs, o.language, v => LANG[v] || v)}</select></label>
      <div class="f s2"><span>Music <small class="quiet">(optional)</small></span><div class="slot" id="slotM"></div></div>
      <label class="chk sw s3" id="gmRow"><input type="checkbox" id="gm" ${o.audio.generate_music ? "checked" : ""}>No music file? Let Claude compose a quiet music bed</label>
      <label class="f s3"><span>Script <small class="quiet">(optional – paste it for exact spelling of names and captions)</small></span><textarea id="script" rows="3" placeholder="The text you read in the recording">${esc(NP.script)}</textarea></label>
      <div class="f s3"><span>Pictures, clips, logos, fonts <small class="quiet">(optional – or drop them on this window)</small></span>
        <div class="chips" id="assets"></div>
        <div class="row"><button class="btn small" id="addFiles">Add files</button><button class="btn small" id="addFolder">Add a folder</button></div></div>
    </div>
  </section>
  <section class="npstep" data-step="details" hidden>
    <p class="lead">Tell Claude what the video is about. “What I want” matters most – everything else here is optional.</p>
    <div class="fg">
      <label class="f s2"><span>Project name</span><input type="text" id="name" value="${esc(name)}" placeholder="from the voice file" data-first></label>
      <label class="f"><span>Kind of video</span><select id="kind">${opt(M.kinds || { auto: "Let Claude decide" }, o.kind || "auto")}</select></label>
      <label class="f s3"><span>What I want</span><textarea id="wants" rows="4" placeholder="The story, the mood, moments that must be shown, videos you like">${esc(o.wants || "")}</textarea></label>
      <label class="f s3"><span>After watching, viewers should believe… <small class="quiet">(one sentence – Claude builds every scene around it)</small></span><input type="text" id="believe" value="${esc(o.believe || "")}" placeholder="e.g. a black hole would stretch Earth before swallowing it"></label>
      <label class="f s3"><span>Take care of <small class="quiet">(must-haves and must-nots – Claude has to tick off every one)</small></span><textarea id="care" rows="2" placeholder="e.g. the logo stays visible at the end; no fantasy visuals">${esc(o.care || "")}</textarea>
        <small class="quiet">${rules.length ? `Your ${rules.length} rule${rules.length === 1 ? "" : "s"} from Settings (“${esc(rules[0].slice(0, 60))}”${rules.length > 1 ? "…" : ""}) are added automatically – no need to repeat them.` : "Rules you want in every project go in Settings → My rules."}</small></label>
    </div>
  </section>
  <section class="npstep" data-step="format" hidden>
    <p class="lead">Where will it be watched? The choice sets size, frame rate, captions and sound – change them below if you need to.</p>
    <select id="preset" class="vh" aria-hidden="true" tabindex="-1">${optl(M.presets, preset)}</select>
    <div class="pcards" role="radiogroup" aria-label="Format">${M.presets.map(n => { const c = cards[n] || {};
      return `<label class="pcard"><input type="radio" name="pcard" value="${esc(n)}" ${n === preset ? "checked" : ""} ${n === preset ? "data-first" : ""}>
        ${c.w ? aspectBox(c.w, c.h) : ""}<b>${esc(presetTitle(n))}</b>${presetSub(n) ? `<small>${esc(presetSub(n))}</small>` : ""}<small class="quiet">${esc(c.line || "")}${c.user ? " · your preset" : ""}</small></label>`; }).join("")}</div>
    <details class="adv" id="advFmt"><summary>Change size, captions, sound…</summary>
    <div class="fs"><h3>Picture</h3><div class="fg">
      <label class="f"><span>Size</span><select id="size">${optl(Object.keys(M.sizes), sizeKey, nice)}<option value="custom" ${sizeKey === "custom" ? "selected" : ""}>Custom</option></select></label>
      <label class="f"><span>Width × height</span><span class="row" style="flex-wrap:nowrap"><input type="number" id="w" value="${o.size[0]}" min="64" step="2" aria-label="Width"><input type="number" id="h" value="${o.size[1]}" min="64" step="2" aria-label="Height"></span></label>
      <label class="f"><span>Frame rate</span><select id="fps">${optl(M.fps, o.fps)}</select></label>
      <div class="f s3"><span>Also deliver as</span><div class="togs">${M.extra_variants.map(v => `<label class="chk tog"><input type="checkbox" class="var" value="${v}" ${o.variants.includes(v) ? "checked" : ""}>${v}</label>`).join("")}
        <label class="chk tog"><input type="checkbox" id="alpha" ${o.alpha ? "checked" : ""}>Transparent background</label></div></div></div></div>
    <div class="fs"><h3>Length</h3><div class="fg">
      <label class="f"><span>Length</span><select id="dmode">${opt(M.duration, o.duration.mode)}</select></label>
      <label class="f" id="secsF"><span>Seconds</span><input type="number" id="secs" value="${o.duration.seconds}" step="0.5" min="1"></label>
      <label class="f" id="tailF"><span>Calm ending after the voice (s)</span><input type="number" id="tail" value="${o.duration.tail}" step="0.5" min="0"></label></div></div>
    <div class="fs"><h3>Text</h3><div class="fg">
      <label class="f"><span>Captions</span><select id="caps">${opt(M.captions, o.captions)}</select></label>
      <label class="f"><span>Keep clear of the app's buttons</span><select id="safe">${opt(M.safe_area, o.safe_area)}</select></label>
      <label class="f"><span>Other text on screen</span><input type="text" id="tamt" value="${esc(o.text_amount)}"></label></div></div>
    <div class="fs"><h3>Sound</h3><div class="fg">
      <label class="f s2"><span>Sound in the video</span><select id="aexp">${opt(M.audio_export, o.audio.export)}</select></label>
      <label class="f"><span>Loudness</span><select id="loud">${opt(M.loudness, String(o.audio.loudness))}</select></label></div></div>
    <div class="fs"><h3>Files and engine</h3><div class="fg">
      <div class="f s3"><span>Files</span><div class="togs">${Object.entries(M.formats).map(([k, v]) => `<label class="chk tog"><input type="checkbox" class="fmt" value="${k}" ${o.formats.includes(k) ? "checked" : ""}>${esc(v.split(" (")[0])}</label>`).join("")}</div></div>
      <label class="f"><span>Engine</span><select id="eng">${opt(M.engines, o.engine)}</select></label>
      <label class="f s2"><span>Workflow</span><select id="rev">${opt(M.review, o.review)}</select></label></div></div>
    </details>
  </section>
  <section class="npstep" data-step="look" hidden>
    <p class="lead">How should it look? Pick a style you saved from an earlier video, or a general style.</p>
    <select id="sref" class="vh" aria-hidden="true" tabindex="-1"><option value="">No – use the style below</option>${styles.map(s => `<option value="${esc(s.id)}" ${s.id === o.style_ref ? "selected" : ""}>${esc(s.name)} (from ${esc(s.source_project)})</option>`).join("")}</select>
    ${styles.length ? `<h3 class="sub">Your saved styles</h3><div class="scards" role="radiogroup" aria-label="Saved style">
      <label class="scard"><input type="radio" name="scard" value="" ${!o.style_ref ? "checked" : ""} data-first><span class="thumb none">—</span><b>None</b><small class="quiet">use a general style</small></label>
      ${styles.map(s => `<label class="scard"><input type="radio" name="scard" value="${esc(s.id)}" ${s.id === o.style_ref ? "checked" : ""}>
        ${s.thumb ? `<img class="thumb" src="/style_thumb?id=${encodeURIComponent(s.id)}" alt="">` : `<span class="thumb none">${esc(s.engine || "")}</span>`}<b>${esc(s.name)}</b><small class="quiet">from ${esc(s.source_project)}</small></label>`).join("")}</div>
      <small class="quiet" id="srefNote"></small>` : `<small class="quiet" id="srefNote"></small>`}
    <h3 class="sub" id="styHead">General style</h3>
    <select id="sty" class="vh" aria-hidden="true" tabindex="-1">${optl(M.styles, o.style_preset, nice)}</select>
    <div class="scards text" role="radiogroup" aria-label="General style" id="styCards">${M.styles.map(k => `<label class="scard"><input type="radio" name="sty" value="${esc(k)}" ${k === o.style_preset ? "checked" : ""} ${!styles.length && k === o.style_preset ? "data-first" : ""}>
      <b>${esc(nice(k))}</b><small class="quiet">${esc((M.style_desc || {})[k] || "")}</small></label>`).join("")}</div>
    <div class="fg" style="margin-top:12px">
      <label class="f s2"><span>Style notes <small class="quiet">(optional)</small></span><input type="text" id="snotes" value="${esc(o.style)}" placeholder="e.g. warm colours, big bold type, slow camera"></label>
      <label class="f"><span>Brand kit</span><select id="brand"><option value="">None</option>${optl(M.brands, o.brand)}</select></label></div>
  </section>
  <section class="npstep" data-step="review" hidden><div id="npReview"></div></section>`;
  for (const id of TEXTF) if (keep[id] !== undefined && $("#" + id)) $("#" + id).dataset.dirty = 1;
  $("#npb").oninput = e => { if (TEXTF.includes(e.target.id)) e.target.dataset.dirty = 1; };
  $("#npb").onchange = e => {
    const t = e.target;
    if (t.name === "pcard") { const s = $("#preset"); s.value = t.value; s.dispatchEvent(new Event("change", { bubbles: false })); }
    if (t.name === "scard") { $("#sref").value = t.value; showRef(); }
    if (t.name === "sty") $("#sty").value = t.value;
    if (t.id === "dmode") lengthFields();
  };
  $("#preset").onchange = async e => {
    const k = typedText(), step = NP.step, adv = $("#advFmt").open;
    try {
      await fillForm(await api(`/api/preset?name=${encodeURIComponent(e.target.value)}`), e.target.value, k);
      $("#advFmt").open = adv; goStep(step);
    } catch (err) { $("#nperr").textContent = err.message; }
  };
  const showRef = () => {
    const s = styles.find(x => x.id === $("#sref").value);
    $("#srefNote").textContent = s ? (s.note ? `You liked: ${s.note}` : "Claude gets its frames and code and makes the new video in the same look.") : "";
    $("#styCards").classList.toggle("muted", !!s);
    $("#styHead").textContent = s ? "General style (the saved style decides)" : "General style";
  };
  $("#sref").onchange = showRef; showRef();
  const lengthFields = () => { const m = $("#dmode").value; $("#secsF").hidden = m !== "fixed"; $("#tailF").hidden = m !== "narration"; };
  lengthFields();
  $("#size").onchange = e => { const v = M.sizes[e.target.value]; if (v) { $("#w").value = v[0]; $("#h").value = v[1]; } };
  $("#addFiles").onclick = () => pick(false, paths => { NP.assets.push(...paths); renderSlots(); });
  $("#addFolder").onclick = () => pick(true, paths => { NP.assets.push(...paths); renderSlots(); });
  renderSlots();
  goStep(NP.step || 0);
}

function renderSlots() {
  const slot = (key, el, label) => {
    const v = NP[key];
    $(el).innerHTML = v ? `<span class="chip"><span>${esc(base(v))}</span><button aria-label="Remove ${label}" data-rm="${key}">×</button></span>`
      : `<span class="none">${key === "narration" ? "Drop the voice recording here or anywhere on this window" : "Drop a music file, or leave it empty"}</span>`;
    const b = document.createElement("button"); b.className = "btn small"; b.textContent = v ? "Replace" : "Choose";
    if (key === "narration") b.dataset.first = "";
    b.onclick = () => pick(false, ps => { if (ps[0]) { NP[key] = ps[0]; renderSlots(); } }, "audio/*", false); $(el).append(b);
  };
  slot("narration", "#slotN", "narration"); slot("music", "#slotM", "music");
  const gm = $("#gmRow"); if (gm) gm.hidden = !!NP.music;
  const nm = $("#name"); if (nm && !nm.value && !nm.dataset.dirty && NP.narration) nm.value = base(NP.narration).replace(/\.[^.]+$/, "");
  $("#assets").innerHTML = NP.assets.length ? NP.assets.map((a, i) => `<span class="chip"><span>${esc(base(a))}</span><button aria-label="Remove" data-rma="${i}">×</button></span>`).join("")
    : `<span class="none" style="color:var(--quiet);font-size:13px">None yet</span>`;
  $("#npb").onclick = e => {
    const r = e.target.closest("[data-rm]"); if (r) { NP[r.dataset.rm] = null; renderSlots(); }
    const ra = e.target.closest("[data-rma]"); if (ra) { NP.assets.splice(+ra.dataset.rma, 1); renderSlots(); }
    const ed = e.target.closest("[data-edit]"); if (ed) goStep(+ed.dataset.edit);
  };
}

function renderReview() {
  const o = readForm(), M = S.meta;
  const st = (M.saved_styles || []).find(x => x.id === o.style_ref);
  const short = (t, n = 140) => { t = String(t || "").trim(); return t.length > n ? t.slice(0, n - 1) + "…" : t; };
  const rules = (M.settings.standing_rules || "").split("\n").filter(x => x.trim()).length;
  const row = (label, value, step, empty) => `<div class="rv"><span class="rl">${esc(label)}</span><span class="rvv ${value ? "" : "quiet"}">${value ? esc(value) : esc(empty || "–")}</span><button class="link" data-edit="${step}">Edit</button></div>`;
  const warn = [];
  if (!NP.narration) warn.push(NP.music ? "No voice recording – the video follows the music." : "No voice recording.");
  if (NP.narration && !($("#script").value || "").trim() && o.language === "uz") warn.push("No script: names and captions are spelled from speech recognition – Claude fixes what it can. Paste the script in step 1 for exact spelling.");
  if (!o.wants.trim() && !o.believe) warn.push("“What I want” is empty – Claude decides the story itself.");
  if (!o.name) warn.push("The project needs a name (step 2).");
  if (NP.narration && !/voice/.test(o.audio.export)) warn.push(`Your voice will not be heard in the exported video (“${(M.audio_export || {})[o.audio.export] || o.audio.export}”) – it only times the pictures. Change it in Format → Change size, captions, sound… if you want it in.`);
  $("#npReview").innerHTML = `<p class="lead">Check everything once – then the app prepares the package for Claude.</p>
    ${warn.length ? `<ul class="npwarn">${warn.map(w => `<li>${esc(w)}</li>`).join("")}</ul>` : ""}
    <div class="rvbox">
    ${row("Voice", NP.narration ? `${base(NP.narration)} · ${LANG[o.language] || o.language}` + (($("#script").value || "").trim() ? ` · script ${$("#script").value.trim().split(/\s+/).length} words` : " · no script") : "", 0, "none")}
    ${row("Music and files", [NP.music ? base(NP.music) : (o.audio.generate_music ? "Claude composes music" : "no music"),
      NP.assets.length ? `${NP.assets.length} file${NP.assets.length === 1 ? "" : "s"}` : "no files"].join(" · "), 0)}
    ${row("Name", o.name, 1)}
    ${row("What I want", short(o.wants), 1, "Claude decides")}
    ${row("Viewers should believe", short(o.believe), 1, "not set")}
    ${row("Take care of", short(o.care) + (rules ? `${o.care.trim() ? " + " : ""}${rules} rule${rules === 1 ? "" : "s"} from Settings` : ""), 1, "nothing extra")}
    ${row("Format", `${presetTitle(o.preset)} · ${o.size[0]}×${o.size[1]} · ${o.fps} fps${o.variants.length ? " · also " + o.variants.join(", ") : ""} · ${((M.captions || {})[o.captions] || o.captions).toLowerCase()}`, 2)}
    ${row("Sound", (M.audio_export || {})[o.audio.export] || o.audio.export, 2)}
    ${row("Look", st ? `Saved style “${st.name}”` : nice(o.style_preset) + (o.style ? ` · ${short(o.style, 60)}` : "") + (o.brand ? ` · brand ${o.brand}` : ""), 3)}
    </div>`;
}

function readForm() {
  const q = s => $(s).value, num = s => +$(s).value, base0 = NP.o || {};
  return {
    ...base0,          // what the preset set and this form doesn't show (e.g. "purpose" from an older preset)
    preset: q("#preset"), name: q("#name").trim(), size: [num("#w"), num("#h")],
    variants: [...document.querySelectorAll(".var:checked")].map(x => x.value), fps: +q("#fps"),
    duration: { mode: q("#dmode"), seconds: num("#secs"), tail: num("#tail") },
    audio: { ...(base0.audio || {}), export: q("#aexp"), loudness: q("#loud"), generate_music: $("#gm").checked && !NP.music },
    language: q("#lang"), captions: q("#caps"), safe_area: q("#safe"), text_amount: q("#tamt"),
    formats: [...document.querySelectorAll(".fmt:checked")].map(x => x.value), alpha: $("#alpha").checked,
    engine: q("#eng"), review: q("#rev"), style_preset: q("#sty"), brand: q("#brand"), style: q("#snotes"),
    purpose: base0.purpose || "", wants: q("#wants"), care: q("#care"), believe: q("#believe").trim(), kind: q("#kind"),
    style_ref: q("#sref") || "", style_ref_name: ((S.meta.saved_styles || []).find(x => x.id === q("#sref")) || {}).name || "",
    standing_rules: S.meta.settings.standing_rules || "",
  };
}
async function createProject() {
  const btn = $("#create"); btn.disabled = true; $("#nperr").textContent = "";
  try {
    await api("/api/new_project", { order: readForm(), narration: NP.narration, music: NP.music, assets: NP.assets, script: $("#script").value });
    dlg.close(); toast("Preparing the narration – the request package follows", "info", 4000);
  } catch (e) {
    $("#nperr").textContent = e.message; btn.disabled = false;
    if (/narration|voice|recording/i.test(e.message)) goStep(0), $("#nperr").textContent = e.message;
    else if (/name/i.test(e.message)) goStep(1), $("#nperr").textContent = e.message;
  }
}
function presetInput() {
  $("#savePreset").hidden = true; $("#presetBox").hidden = false; $("#presetName").focus();
}
async function savePreset() {
  const name = $("#presetName").value.trim();
  if (!name) { $("#nperr").textContent = "Give the preset a name."; return $("#presetName").focus(); }
  try {
    await api("/api/save_preset", { name, order: readForm() }); S.meta = await api("/api/meta");
    $("#presetNo").click(); $("#nperr").textContent = ""; toast(`Preset “${name}” saved`, "info", 2500);
    const sel = $("#preset"); if (sel && ![...sel.options].some(o => o.value === name)) sel.add(new Option(name, name));
    const pc = $(".pcards"); if (pc && ![...pc.querySelectorAll("input")].some(i => i.value === name)) pc.insertAdjacentHTML("beforeend",
      `<label class="pcard"><input type="radio" name="pcard" value="${esc(name)}"><b>${esc(name)}</b><small class="quiet">your preset</small></label>`);
  } catch (e) { $("#nperr").textContent = e.message; }
}

/* ---------- files: pick, drop, upload ---------- */
function pick(folder, cb, accept, multi = true) {
  const i = document.createElement("input"); i.type = "file"; i.multiple = multi && !folder;
  if (folder) i.webkitdirectory = true; if (accept) i.accept = accept;
  i.onchange = async () => {
    const files = [...i.files].map(f => ({ file: f, rel: f.webkitRelativePath || f.name })); if (!files.length) return;
    try { cb(await upload(files, folder)); } catch (e) { toast(e.message, "error"); }
  };
  i.click();
}
function uploadOne(file, rel, batch, onBytes) {
  return new Promise((resolve, reject) => {
    const x = new XMLHttpRequest();
    x.open("POST", `/api/upload?batch=${batch}&rel=${encodeURIComponent(rel)}`);
    x.upload.onprogress = e => onBytes(e.loaded);
    x.onload = () => {
      let j = {}; try { j = JSON.parse(x.responseText); } catch {}
      if (x.status === 401) engineGone();
      if (x.status >= 200 && x.status < 300 && j.path) resolve(j.path); else reject(new Error(j.error || `Adding “${base(rel)}” failed (${x.status})`));
    };
    x.onerror = () => reject(new Error("Adding files failed – Vizavi Studio is not responding"));
    x.send(file);
  });
}
function topOf(path, batch) {          // the first folder below the upload batch (a dropped folder is passed on as one item)
  const parts = path.split(/[\\/]/), i = parts.lastIndexOf(batch);
  return i >= 0 ? parts.slice(0, i + 2).join(path.includes("\\") ? "\\" : "/") : path;
}
async function upload(items, folderMode) {
  const batch = Math.random().toString(36).slice(2, 10), out = new Set(), box = $("#upl");
  const total = items.reduce((a, it) => a + it.file.size, 0) || 1; let doneBytes = 0;
  const show = (n, cur) => { box.hidden = false; $("#uplText").textContent = `Adding files ${n}/${items.length}`; $("#uplBar").style.width = Math.min(100, (doneBytes + cur) / total * 100) + "%"; };
  try {
    for (let n = 0; n < items.length; n++) {
      const it = items[n]; show(n + 1, 0);
      const path = await uploadOne(it.file, it.rel, batch, b => show(n + 1, b));
      doneBytes += it.file.size;
      out.add(folderMode || it.rel.includes("/") ? topOf(path, batch) : path);
    }
  } finally { box.hidden = true; }
  return [...out];
}
async function entriesToItems(dt) {
  const items = [], walk = async (entry, path) => {
    if (entry.isFile) { const f = await new Promise((res, rej) => entry.file(res, rej)); items.push({ file: f, rel: path + f.name }); }
    else if (entry.isDirectory) {
      const rd = entry.createReader(); let batch;
      do { batch = await new Promise((res, rej) => rd.readEntries(res, rej)); for (const e of batch) await walk(e, path + entry.name + "/"); } while (batch.length);
    }
  };
  const ents = [...dt.items].map(i => i.webkitGetAsEntry && i.webkitGetAsEntry()).filter(Boolean);
  if (!ents.length) return [...dt.files].map(f => ({ file: f, rel: f.name }));
  for (const e of ents) await walk(e, "");
  return items;
}
let dragDepth = 0;
addEventListener("dragenter", e => { if ([...e.dataTransfer.types].includes("Files")) { dragDepth++; $("#drop").hidden = false; } });
addEventListener("dragleave", () => { if (--dragDepth <= 0) { dragDepth = 0; $("#drop").hidden = true; } });
addEventListener("dragover", e => e.preventDefault());
addEventListener("drop", async e => {
  e.preventDefault(); dragDepth = 0; $("#drop").hidden = true;
  try {
    const items = await entriesToItems(e.dataTransfer); if (!items.length) return;
    const paths = await upload(items);
    handlePaths(paths, dlg.open && $("#npb"));
  } catch (err) { toast(err.message, "error"); }
});
async function handlePaths(paths, intoForm) {
  try {
    const c = await api("/api/classify", { paths });
    if (c.zips.length) {
      const r = await api("/api/process_zip", { paths: c.zips });
      toast(r.started ? "Zip received – rendering" : "That zip is already being handled", "info", 3500);
    }
    const media = c.narration || c.music || c.assets.length || c.script;
    if (!media) return;
    if (intoForm) {
      if (c.narration && !NP.narration) NP.narration = c.narration; else if (c.narration && !NP.music) NP.music = c.narration;
      if (c.music && !NP.music) NP.music = c.music;
      NP.assets.push(...c.assets); if (c.script) $("#script").value = c.script; renderSlots();
    } else newProject({ narration: c.narration, music: c.music, assets: c.assets, script: c.script });
  } catch (err) { toast(err.message, "error"); }
}

/* ---------- appearance (per window, remembered in this browser profile) ---------- */
function theme() { try { return localStorage.getItem("vz-theme") || ""; } catch { return ""; } }
function setTheme(v) {
  try { v ? localStorage.setItem("vz-theme", v) : localStorage.removeItem("vz-theme"); } catch {}
  if (v) document.documentElement.dataset.theme = v; else delete document.documentElement.dataset.theme;
}
setTheme(theme());

/* ---------- wiring ---------- */
const safe = fn => (...a) => Promise.resolve(fn(...a)).catch(e => toast(e.message, "error"));
$("#newBtn").onclick = () => newProject({});
$("#emptyNew").onclick = () => newProject({});
$("#settingsBtn").onclick = () => S.meta && settingsDialog();
$("#openProjects").onclick = safe(() => api("/api/act", { action: "open_projects" }));
$("#stopBtn").onclick = safe(() => api("/api/act", { action: "stop" }));
$("#logBtn").onclick = () => { const l = $("#log"); l.hidden = !l.hidden; $("#logBtn").setAttribute("aria-expanded", !l.hidden); l.scrollTop = l.scrollHeight; };
$("#deadBtn").onclick = () => location.reload();
addEventListener("keydown", e => { if ((e.ctrlKey || e.metaKey) && e.key === "n" && !dlg.open) { e.preventDefault(); newProject({}); } });
poll();
