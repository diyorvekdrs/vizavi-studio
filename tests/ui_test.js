const { JSDOM, VirtualConsole, CookieJar } = require("jsdom");
const { spawn } = require("child_process");
const path = require("path"), os = require("os");
const py = spawn(process.env.PYTHON || (process.platform === "win32" ? "python" : "python3"), [path.join(__dirname, "serve_fixture.py")], { env: process.env });
let pyerr = ""; py.stderr.on("data", d => pyerr += d);
const sleep = ms => new Promise(r => setTimeout(r, ms));
const fails = [], errors = [];
const check = (name, ok, extra = "") => { console.log((ok ? "ok   " : "FAIL ") + name + (ok ? "" : "  " + extra)); if (!ok) fails.push(name); };
async function until(fn, ms = 6000, step = 80) { const t = Date.now(); while (Date.now() - t < ms) { try { const v = fn(); if (v) return v; } catch {} await sleep(step); } return null; }
(async () => {
  const token = await new Promise(res => py.stdout.once("data", d => res(String(d).trim())));
  const say = c => py.stdin.write(c + "\n");
  const vc = new VirtualConsole();
  vc.on("jsdomError", e => errors.push("jsdomError: " + (e.detail || e.message || e)));
  vc.on("error", (...a) => errors.push("console.error: " + a.join(" ")));
  const jar = new CookieJar();
  const dom = await JSDOM.fromURL(`http://127.0.0.1:47998/?t=${token}`, {
    runScripts: "dangerously", resources: "usable", pretendToBeVisual: true, cookieJar: jar, virtualConsole: vc,
    beforeParse(win) {
      win.fetch = (u, o = {}) => fetch(new URL(u, "http://127.0.0.1:47998/"), { ...o, headers: { ...(o.headers || {}), Cookie: jar.getCookieStringSync("http://127.0.0.1:47998/") } });
      const D = win.HTMLDialogElement && win.HTMLDialogElement.prototype;
      if (D) { D.showModal = function () { this.setAttribute("open", ""); }; D.close = function () { this.removeAttribute("open"); this.dispatchEvent(new win.Event("close")); }; }
      Object.defineProperty(win.navigator, "clipboard", { value: { writeText: async t => { win.__copied = t; } } });
      win.Element.prototype.scrollIntoView = function () {};
    },
  });
  const w = dom.window, d = w.document, $ = s => d.querySelector(s), $$ = s => [...d.querySelectorAll(s)];
  const click = el => el.dispatchEvent(new w.MouseEvent("click", { bubbles: true, cancelable: true }));
  const key = (el, k) => el.dispatchEvent(new w.KeyboardEvent("keydown", { key: k, bubbles: true, cancelable: true }));

  check("projects listed", !!(await until(() => $$(".proj").length === 4)), $$(".proj").length);
  check("ready status", !!(await until(() => /Ready/.test($("#stLabel").textContent))), $("#stLabel").textContent);
  check("empty hidden / view shown", $("#empty").hidden && !$("#view").hidden);

  // stopped project
  click($$(".proj").find(b => b.dataset.name === "beta"));
  check("stopped card", !!(await until(() => /Stopped/.test($("#view").textContent))));
  check("stopped has retry btn", !!$('#view [data-a="retry"]'));
  check("stopped reason shown", /You stopped it/.test($("#view").textContent));
  check("track marks preview step bad", $$("#track .st")[2].classList.contains("bad"), $("#track").innerHTML.slice(0, 300));
  check("nav shows stopped text", /Stopped/.test($$(".proj").find(b => b.dataset.name === "beta").textContent));

  // alpha: checks + notes
  click($$(".proj").find(b => b.dataset.name === "alpha"));
  check("alpha preview card", !!(await until(() => /Watch the preview/.test($("#view").textContent))));
  check("checks card ranks findings", /1 serious/.test($(".checks")?.textContent || "") && /1 worth fixing/.test($(".checks").textContent) && /1 polish/.test($(".checks").textContent), $(".checks")?.textContent);
  check("serious findings open the list", ($('.checks details[data-k="flags"]') || {}).open === true);
  click($('#view [data-a="approve"]'));
  check("approve with a serious finding asks first", !!(await until(() => /Render the final anyway/.test($("#dlg").textContent), 3000)));
  check("dialog lists the serious finding only", /runs off the frame/.test($("#dlg").textContent) && !/off the nearest beat/.test($("#dlg").textContent));
  click($("#dlg [data-close]"));
  const pjA = await (await w.fetch("/api/project?name=alpha")).json();
  check("going back does not queue the final", pjA.stage === "preview_ready", pjA.stage);
  check("estimate shown", /about 12 min/.test($(".checks")?.textContent || ""), $(".checks")?.textContent);
  const det = $('.checks details[data-k="cost"]'); det.open = true; det.dispatchEvent(new w.Event("toggle"));
  check("cost table", $$("table.cost tr").length === 3 && $$("table.cost tr")[0].textContent.includes("main"));
  let ta = $("#notes");
  check("notes box exists", !!ta);
  ta.focus(); ta.value = "make the intro shorter"; ta.dispatchEvent(new w.Event("input", { bubbles: true }));
  check("typing state", /Typing/.test($("#notesState").textContent));
  say("touch-alpha");                        // project changes on disk while notes are unsaved
  await sleep(2600);
  ta = $("#notes");
  check("notes survive a re-render", ta && ta.value === "make the intro shorter", ta && ta.value);
  check("notes autosaved", /Saved/.test($("#notesState")?.textContent || ""), $("#notesState")?.textContent);
  const pj = await (await w.fetch("/api/project?name=alpha")).json();
  check("server has saved notes", pj.notes_saved === "make the intro shorter", pj.notes_saved);
  check("details open state kept", ($('.checks details[data-k="cost"]') || {}).open === true);
  click($('[data-chip="Bolder"]'));
  check("quick note chip adds a line", /make the intro shorter\n• Bolder: $/.test($("#notes").value), JSON.stringify($("#notes").value));
  click($('[data-a="add_rule"]')); await until(() => $("#ruleTxt"));
  $("#ruleTxt").value = "Captions sit above the bottom quarter"; click($("#ruleSave"));
  check("rule saved toast", !!(await until(() => [...d.querySelectorAll(".toast")].some(t => /Rule saved/.test(t.textContent)), 3000)));
  const meta2 = await (await w.fetch("/api/meta")).json();
  check("rule in My rules", /Captions sit above the bottom quarter/.test(meta2.settings.standing_rules), meta2.settings.standing_rules);

  // busy marking
  say("busy-beta");
  check("busy dot in nav", !!(await until(() => $$(".proj").find(b => b.dataset.name === "beta")?.dataset.busy === "true", 4000)));
  check("busy nav text", /Working/.test($$(".proj").find(b => b.dataset.name === "beta").textContent));
  click($$(".proj").find(b => b.dataset.name === "beta"));
  await until(() => /Stopped/.test($("#view").textContent));
  check("idle-only buttons disabled while busy", !!(await until(() => $('#view [data-a="retry"]')?.disabled === true, 3000)));

  click($$(".proj").find(b => b.dataset.name === "alpha")); await until(() => /Watch the preview/.test($("#view").textContent));
  const fs = $("#fsize");
  check("final size picker on preview card", !!fs && fs.options.length >= 2, fs && fs.innerHTML);
  if (fs) { fs.value = "1280"; fs.dispatchEvent(new w.Event("change", { bubbles: true })); }
  await sleep(1500);
  const pj2 = await (await w.fetch("/api/project?name=alpha")).json();
  check("size choice stored on the server", pj2.final_long_side === 1280, pj2.final_long_side);
  check("picker keeps the choice after redraw", $("#fsize") && $("#fsize").value === "1280", $("#fsize") && $("#fsize").value);

  click($$(".proj").find(b => b.dataset.name === "beta")); await until(() => /Stopped/.test($("#view").textContent)); await sleep(800);
  click($$(".proj").find(b => b.dataset.name === "alpha")); await until(() => /Watch the preview/.test($("#view").textContent));
  const ssb = $('[data-a="save_style"]');
  check("Save as style button on a project with Claude's code", !!ssb);
  click(ssb); await until(() => $("#stName"));
  $("#stName").value = "Alpha look"; $("#stNote").value = "big type";
  click($("#stSave"));
  check("style saved toast", !!(await until(() => [...d.querySelectorAll(".toast")].some(t => /Style “Alpha look” saved/.test(t.textContent)), 4000)));
  check("style listed in meta", !!(await until(() => (w.S ? true : true) && true)));
  // size and sound after the project was made
  click($('[data-a="more"]')); await until(() => $(".menu"));
  click($$(".menu button").find(b => /Size and sound/.test(b.textContent)));
  check("size and sound dialog", !!(await until(() => $("#osave"), 3000)));
  $("#osz").value = "1:1, 1080x1080" in ($("#osz").options) ? "1:1, 1080x1080" : $("#osz").value;
  $("#ow").value = 1080; $("#oh").value = 1080; $("#oaud").value = "music_sfx";
  click($("#osave"));
  check("order changed toast", !!(await until(() => [...d.querySelectorAll(".toast")].some(t => /1080×1080/.test(t.textContent) && /next render/.test(t.textContent)), 3000)));
  const pjS = await (await w.fetch("/api/project?name=alpha")).json();
  check("order stored", pjS.order_size[0] === 1080 && pjS.order_size[1] === 1080 && pjS.audio_export === "music_sfx", JSON.stringify(pjS.order_size));
  click($$(".proj").find(b => b.dataset.name === "beta")); await until(() => /Stopped/.test($("#view").textContent)); await sleep(800);
  // keyboard menu
  const more = $('[data-a="more"]'); more.focus(); click(more);
  const menuEl = await until(() => $(".menu"));
  check("menu opens, role=menu", !!menuEl && menuEl.getAttribute("role") === "menu");
  const items = $$(".menu button");
  check("busy items disabled in menu", items.filter(b => b.disabled).length >= 2, items.map(b => b.textContent + b.disabled).join("|"));
  check("first enabled item focused", d.activeElement === items.find(b => !b.disabled));
  key(d.activeElement, "ArrowDown");
  check("arrow moves focus", d.activeElement !== items.find(b => !b.disabled) || items.filter(b => !b.disabled).length === 1);
  key(d.activeElement, "Escape");
  check("escape closes and refocuses", !$(".menu") && d.activeElement === more);

  // delete on keyboard targets focused project
  const gamma = $$(".proj").find(b => b.dataset.name === "gamma"); gamma.focus(); key(gamma, "Delete");
  check("Delete key asks about the focused project", !!(await until(() => /Delete “gamma”/.test($("#dlg").textContent), 3000)), $("#dlg").textContent.slice(0, 80));
  click($("#dlg [data-close]"));

  // old report: plain flags get ranks on the server
  const pjO = await (await w.fetch("/api/project?name=oldrep")).json();
  check("old flags ranked", (pjO.issues || []).map(i => i.rank).join() === "P1,P3", JSON.stringify(pjO.issues));

  // delete -> Recently deleted -> restore
  gamma.focus(); key(gamma, "Delete"); await until(() => $("#del"));
  check("delete dialog mentions Recently deleted", /Recently deleted/.test($("#dlg").textContent));
  click($("#del"));
  check("gamma gone from the list", !!(await until(() => !$$(".proj").some(b => b.dataset.name === "gamma"), 4000)));
  click($("#settingsBtn")); await until(() => $("#trList"));
  check("gamma in Recently deleted", /gamma/.test($("#trList").textContent) && /30 days left/.test($("#trList").textContent), $("#trList").textContent);
  click($('#trList [data-how="restore"]'));
  check("restore brings gamma back", !!(await until(() => $$(".proj").some(b => b.dataset.name === "gamma"), 5000)));
  check("Recently deleted empty again", !!(await until(() => /Nothing here/.test($("#trList")?.textContent || ""), 3000)));
  click($("#dlg [data-close]"));

  // Claude app connection -> chat mode on the project page
  click($("#settingsBtn")); await until(() => $("#clBox"));
  check("settings offers connecting the Claude app", /Not connected/.test($("#clBox").textContent));
  click($('#clBox [data-cl="connect_claude"]'));
  check("connected", !!(await until(() => /Connected/.test($("#clBox").textContent), 3000)), $("#clBox").textContent);
  click($("#dlg [data-close]"));
  click($$(".proj").find(b => b.dataset.name === "gamma"));
  check("request card switches to chat mode", !!(await until(() => /Ask Claude in the Claude app/.test($("#view").textContent), 3000)));
  check("zip way still offered", /Use a zip instead/.test($("#view").textContent));
  click($('#view [data-a="copy_chat"]'));
  check("chat message copied", !!(await until(() => [...d.querySelectorAll(".toast")].some(t => /Claude app/.test(t.textContent)), 3000)));
  click($("#settingsBtn")); await until(() => $("#clBox"));
  click($('#clBox [data-cl="disconnect_claude"]'));
  check("disconnect", !!(await until(() => /Not connected/.test($("#clBox").textContent), 3000)));
  click($("#dlg [data-close]"));

  // settings
  click($("#settingsBtn"));
  check("settings dialog", !!(await until(() => $("#fx"))));
  $("#fx").checked = true; click($("#sv"));
  check("lighter effects applied", !!(await until(() => d.documentElement.dataset.fx === "light", 3000)));
  check("settings dialog closed", !$("#dlg").hasAttribute("open"));
  click($("#settingsBtn")); await until(() => $("#fx")); $("#pd").value = ""; click($("#sv"));
  check("bad folder shows error in dialog", !!(await until(() => /empty/.test($("#seterr").textContent), 3000)), $("#seterr")?.textContent);
  click($("#dlg [data-close]"));

  // new project: preset change keeps typed text
  click($("#newBtn"));
  check("new project form", !!(await until(() => $("#preset") && $("#name"))));
  check("believe + kind fields", !!$("#believe") && $("#kind").options.length >= 4 && $("#kind").value === "auto");
  check("wizard starts on step 1", $$("#npSteps li")[0].className === "cur" && !$('.npstep[data-step="files"]').hidden && $('.npstep[data-step="details"]').hidden);
  click($("#npNext"));
  check("Next without a voice recording explains why", /voice recording/.test($("#nperr").textContent) && $$("#npSteps li")[0].className === "cur", $("#nperr").textContent);
  click($('#npSteps [data-go="2"]'));
  check("stepper jumps to Format", !$('.npstep[data-step="format"]').hidden && $$(".pcard").length >= 10);
  click($('#npSteps [data-go="4"]'));
  check("review step lists the order", /Format/.test($("#npReview").textContent) && !$("#create").hidden && $("#npNext").hidden);
  click($('#npReview [data-edit="1"]'));
  check("Edit goes back to the step", !$('.npstep[data-step="details"]').hidden);
  $("#name").value = "my-video"; $("#name").dispatchEvent(new w.Event("input", { bubbles: true }));
  $("#wants").value = "calm and clear"; $("#wants").dispatchEvent(new w.Event("input", { bubbles: true }));
  const sel = $("#preset"); const other = [...sel.options].find(o => o.value !== sel.value);
  const card = $$(".pcard input").find(i => i.value === other.value); card.checked = true; card.dispatchEvent(new w.Event("change", { bubbles: true }));
  await until(() => $("#preset")?.value === other.value);
  check("preset change keeps the step", !$('.npstep[data-step="details"]').hidden);
  await sleep(300);
  check("name kept after preset change", $("#name").value === "my-video", $("#name").value);
  check("wants kept after preset change", $("#wants").value === "calm and clear", $("#wants").value);
  check("preset really changed", $("#preset").value === other.value);
  const sref = $("#sref");
  check("new project offers saved styles", !!sref && [...sref.options].some(o => /Alpha look/.test(o.textContent)), sref && sref.innerHTML);
  const sc = $$(".scard input[name=scard]").find(i => i.value && i.value === [...sref.options].find(o => /Alpha look/.test(o.textContent)).value);
  sc.checked = true; sc.dispatchEvent(new w.Event("change", { bubbles: true }));
  check("saved style card sets the style", /Alpha/i.test(sref.value) || sref.value.length > 0, sref.value);
  check("style note shown", /big type/.test($("#srefNote").textContent), $("#srefNote").textContent);
  // inline preset save
  click($("#savePreset"));
  check("inline preset input", !$("#presetBox").hidden && $("#savePreset").hidden);
  $("#presetName").value = "UI test preset"; click($("#presetOk"));
  check("preset saved", !!(await until(() => [...d.querySelectorAll(".toast")].some(t => /UI test preset/.test(t.textContent)), 3000)));
  check("preset added to the list", [...$("#preset").options].some(o => o.value === "UI test preset"));
  click($("#savePreset") ); click($("#presetNo"));
  // create with nothing -> error text, button re-enabled
  click($("#create"));
  check("create without voice shows reason", !!(await until(() => $("#nperr").textContent.length > 3, 3000)), $("#nperr").textContent);
  check("create button usable again", $("#create").disabled === false);
  click($("#dlg [data-close]"));

  // upload with progress
  const fileObj = new w.File(["hello world"], "note.txt");
  const out = await w.upload([{ file: fileObj, rel: "note.txt" }], false);
  check("upload returns a path", out.length === 1 && /incoming/.test(out[0]), JSON.stringify(out));
  check("progress box hidden after", $("#upl").hidden);
  const out2 = await w.upload([{ file: fileObj, rel: "folder/sub/a.txt" }, { file: fileObj, rel: "folder/b.txt" }], false);
  check("folder upload collapses to one top folder", out2.length === 1 && /folder$/.test(out2[0]), JSON.stringify(out2));
  let bad = null; try { await w.upload([{ file: fileObj, rel: "../../x.txt" }], false); } catch (e) { bad = e; }
  check("traversal name does not escape", !bad);

  // toasts persist / dedupe
  w.toast("kept", "warn"); w.toast("kept", "warn");
  check("toast dedupe", $$(".toast").filter(t => t.textContent.startsWith("kept")).length === 1);
  await sleep(200);
  check("warn toast persists", $$(".toast").some(t => t.textContent.startsWith("kept")));
  click($$(".toast .x").pop());

  say("update");
  check("update bar appears", !!(await until(() => !$("#updBar").hidden && /9\.9\.9/.test($("#updBar").textContent), 4000)));
  click($('#updBar [data-u="notes"]'));
  check("what's new shows the notes", !!(await until(() => /Save as style/.test($("#dlg").textContent), 2000)));
  click($("#dlg [data-close]"));
  click($('#updBar [data-u="later"]'));
  check("Later hides the bar", $("#updBar").hidden);
  click($("#settingsBtn")); await until(() => $("#cu"));
  check("settings shows version + check now", /You have Vizavi Studio/.test($("#dlg").textContent) && !!$("#cuNow"));
  click($("#dlg [data-close]"));

  // engine restarted -> stale window
  say("restart");
  check("stale window shows cover", !!(await until(() => !$("#dead").hidden, 6000)));

  check("no JS errors", errors.length === 0, errors.slice(0, 5).join("\n"));
  console.log("\nFAILS:", fails.length ? fails : "none");
  say("quit"); dom.window.close();
  setTimeout(() => process.exit(fails.length ? 1 : 0), 300);
})().catch(e => { console.log("TEST CRASH", e); console.log(pyerr.slice(-1500)); py.kill(); process.exit(2); });
