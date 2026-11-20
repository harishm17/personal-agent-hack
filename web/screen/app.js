// Sign-Off big screen. Everything drawn here comes from GET /api/state; the page decides nothing.
// (?sim=1 is the one exception: it moves a limit inside the page, clearly marked, to build the motion.)
// Layout: what the agent knew for this line (left) becomes the sums and the plot (right).
import {
  defaultLineId, figureSpan, marginText, money, num, opSymbol, ownerWords, pickOf, simulate, skeletonChecks, termNote,
} from "/screen/model.js";
import { drawPlot, plotIntro } from "/screen/plot.js";
import * as fx from "/screen/motion.js";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const params = new URLSearchParams(location.search);
const SIM = params.get("sim") === "1";
// ?fixture=1 draws the committed fixture run whatever the engine holds; ?fixture=signed the same run after a signature
const FIXTURE = { 1: "/screen/fixture-state.json", signed: "/screen/fixture-signed.json" }[params.get("fixture")];

let server = null;            // the last /api/state
let state = null;             // what is drawn: server, or the sim's recompute of it
let raw = "";
const ui = { inspect: null, panel: params.get("panel") || (SIM ? "sim" : "words"), sim: { limits: {}, facts: {} }, chat: [], busy: false };
let sized = "";
const last = { view: null, shown: null, signed: null, hadPick: null };   // what the previous draw showed, to animate only real changes

// ?sim=1&set=L2.capacity:325,toilet_rim_height:14 starts the sim with moved values (for screenshots)
if (SIM) {
  for (const pair of (params.get("set") || "").split(",").filter(Boolean)) {
    const [id, v] = pair.split(":");
    (id.includes(".") ? ui.sim.limits : ui.sim.facts)[id] = parseFloat(v);
  }
}

// ---------- fitting the 960 x 540 canvas to the window ----------
function fit() {
  const k = Math.min(innerWidth / 960, innerHeight / 540);
  $("stage").style.transform = `translate(${(innerWidth - 960 * k) / 2}px, ${(innerHeight - 540 * k) / 2}px) scale(${k})`;
}
addEventListener("resize", fit);
fit();

// ---------- data ----------
async function load() {
  try {
    const res = await fetch(FIXTURE || "/api/state", { cache: "no-store" });
    if (!res.ok) throw new Error(res.status);
    const text = await res.text();
    if (text === raw) return;
    raw = text;
    server = JSON.parse(text);
    apply();
  } catch (error) {
    if (!state) $("wait").textContent = "Cannot reach /api/state yet. Trying again every two seconds.";
  }
}

function apply() {
  const simActive = SIM && (Object.keys(ui.sim.limits).length || Object.keys(ui.sim.facts).length);
  state = simActive ? simulate(server, ui.sim) : server;
  render();
}

let live = false;
function listen() {
  if (params.get("live") === "0") return;        // screenshots: no open stream, polling only
  const events = new EventSource("/api/events");
  events.onopen = () => { live = true; };
  events.onmessage = () => load();
  events.onerror = () => { live = false; };
}
setInterval(() => { if (!live) load(); }, 2000);   // no event stream (fixture server, a dropped connection): poll

// ---------- which line ----------
function lineId() {
  const hash = location.hash.slice(1);
  return state.lines.some((l) => l.line_id === hash) ? hash : defaultLineId(state);
}
addEventListener("hashchange", () => { ui.inspect = null; render(); });

// ---------- render ----------
const LINE_VIEW = '<aside id="context" aria-label="What the agent knew for this line"></aside><div id="work">' +
  '<section id="sums" aria-label="The checks on this line as sums"></section>' +
  '<div id="plot"><svg id="box" role="img" aria-label="Every candidate of this line against its limits"></svg></div></div>';

function render() {
  if (!state) return;
  const stage = $("stage");
  stage.classList.add("ready");
  const sheetView = location.hash === "#sheet";
  stage.classList.toggle("sheet", sheetView);
  stage.classList.toggle("sql", !sheetView && ui.panel === "sql");
  const signedNow = !!state.seal.signed, justSigned = last.signed === false && signedNow;
  last.signed = signedNow;
  if (sheetView) {
    const opening = last.view !== "sheet";
    last.view = "sheet"; last.shown = null;
    renderSheet();
    renderSeal(justSigned);
    if (opening) document.querySelectorAll(".bigtile").forEach((t, i) => fx.arrive(t, 60 + i * 70, 300, 6));
    rollChanges(!opening);
    return;
  }
  if (!$("box")) $("main").innerHTML = LINE_VIEW;
  const id = lineId();
  const line = state.lines.find((l) => l.line_id === id);
  const sheetLine = state.sheet.lines.find((l) => l.id === id);
  const pick = pickOf(line);
  if (!line.candidates.some((c) => c.id === ui.inspect)) ui.inspect = null;
  const shown = line.candidates.find((c) => c.id === ui.inspect) || pick;
  const view = { line, sheetLine, pick, shown, index: state.lines.indexOf(line) };
  // a line "opens" when it is first shown, or when its first pick arrives; anything else is an update
  const opening = last.view !== id || (last.hadPick === false && !!pick);
  const shownChanged = !opening && (shown ? shown.id : null) !== last.shown;
  last.view = id; last.shown = shown ? shown.id : null; last.hadPick = !!pick;

  renderHead(view);
  renderTrail(view);
  renderContext(view);
  renderSums(view);
  renderTiles(view);
  renderSeal(justSigned);
  drawPlot($("box"), line, shown ? shown.id : null, (cid) => {
    ui.inspect = pick && cid === pick.id ? null : cid;
    if (ui.panel === "shopper" || ui.panel === "sim") ui.panel = "words";
    render();
  });
  if (opening) intro(view);
  else if (shownChanged) liftFigures(120);
  rollChanges(!opening);
  sized = $("plot").clientWidth + "x" + $("plot").clientHeight;
}

function renderHead({ line, index }) {
  const { issuer, shopper } = state.sheet;
  const mode = state.mode === "fixture" ? "FIXTURE" : state.mode === "replay" ? "REPLAY, CACHED" : "";
  const title = line ? cap(line.need) : state.sheet.title;
  const sub = line ? `<a href="#sheet" title="The whole sheet. Key: 0">line ${index + 1} of ${state.lines.length}</a>` : `${state.lines.length} lines, ${state.sheet.stores.length} stores`;
  $("head").innerHTML = `
    <h1>${esc(title)}</h1>
    <span class="sub">${sub}${state.sheet.invented ? " · invented people" : ""}</span>
    <span class="grow"></span>
    <span class="key issuer"><i class="dotk"></i>${esc(issuer.name)} set</span>
    <span class="key shopper"><i class="dotk"></i>${esc(shopper.name)} stated</span>
    <span class="key store"><i class="dotk"></i>the store's words</span>
    <span class="key unknown"><i class="dotk unknown"></i>not stated</span>
    <button id="sqlbtn" aria-pressed="${!!line && ui.panel === "sql"}" title="The one SQL statement that returns this line's passing box. Key: Q">SQL</button>
    <button id="elena" aria-pressed="${!!line && ui.panel === "shopper"}" title="${esc(shopper.name)}'s measurements and her chat with the agent. Key: E">${esc(shopper.name)}</button>
    ${SIM ? `<button id="simbtn" class="simbtn" aria-pressed="${ui.panel === "sim"}">SIMULATION</button>` : ""}
    ${mode ? `<span class="badge">${mode}</span>` : ""}`;
  $("elena").onclick = () => togglePanel("shopper");
  $("sqlbtn").onclick = () => togglePanel("sql");
  if (SIM) $("simbtn").onclick = () => togglePanel("sim");
}

function togglePanel(name) {
  ui.panel = ui.panel === name ? "words" : name;
  if (location.hash === "#sheet") { ui.panel = name; location.hash = lineId(); return; }
  render();
  if (ui.panel === "shopper") $("sayText")?.focus();
}

// ---------- the steps the agent took on this line, each count from the state ----------
function renderTrail({ line, pick }) {
  const n = (s) => line.candidates.filter((c) => c.status === s).length;
  const stores = new Set(line.candidates.map((c) => c.product.store)).size || state.sheet.stores.length;
  const limits = line.candidates[0] && line.candidates[0].checks.length === 2 ? "both limits" : "every limit";
  const steps = [
    ["stores", `<b>${stores}</b> stores searched`],
    ["read", `<b data-k="trail.read">${line.why.total}</b> pages read`],
    ["unstated", `<b data-k="trail.unstated">${n("not_stated")}</b> never state a figure`],
    ["outside", `<b data-k="trail.outside">${n("outside")}</b> outside a limit`],
    ["inside", `<b data-k="trail.inside">${line.why.inside}</b> inside ${limits}`],
  ];
  if (line.struck.length) steps.push(["struck", `<span class="issuer"><b class="issuer" data-k="trail.struck">${line.struck.length}</b> struck by ${esc(state.sheet.issuer.name)}</span>`]);
  if (line.status !== "pick_up") steps.push(["delivery", `<b data-k="trail.delivery">${line.why.with_delivery_time}</b> state a delivery time`]);
  steps.push(["picked", pick ? `picked <b data-k="trail.pick">${money(pick.product.price_cents)}</b>${line.status === "pick_up" ? ", to pick up locally" : ""}` : `<b>nothing proposed</b>`]);
  $("trail").innerHTML = steps.map(([k, html]) => `<span class="step" data-step="${k}">${html}</span>`).join('<span class="sep">›</span>');
}

// ---------- what it knew: the facts that exist for this line, each with its owner ----------
function factsOfLine(sheetLine) {
  const ids = new Set();
  for (const limit of sheetLine.limits) {
    for (const t of limit.terms) if (t.source === "shopper") ids.add(t.fact);
    if (limit.bound.source === "shopper") ids.add(limit.bound.fact);
  }
  return state.sheet.shopper_facts.filter((f) => ids.has(f.id));
}

function storeWords(c) {
  const seen = new Set(), parts = [], ends = [];
  for (const ch of c.checks) {
    for (const t of ch.terms) {
      if (t.owner !== "store" || !t.quote || seen.has(t.figure)) continue;
      seen.add(t.figure);
      const text = t.sentence || t.quote;
      const offset = t.sentence ? Math.max(0, t.sentence.indexOf(t.quote)) : 0;
      const [s, e] = figureSpan(t.quote, t).map((v) => v + offset);
      parts.push(`<span class="ci">“${esc(text.slice(0, s))}<mark data-src="q:${esc(t.figure)}">${esc(text.slice(s, e))}</mark>${esc(text.slice(e))}”</span>`);
      if (t.kind === "spread") ends.push(`A stated spread: code uses ${num(t.value, t.unit)} ${esc(t.unit)}, the end that could fail.`);
      if (t.kind === "adjustable") ends.push(`An adjustable range: it passes when the limit lies inside it.`);
    }
  }
  return { parts, ends };
}

function renderContext(view) {
  if (ui.panel === "sql") return renderSqlPanel(view);
  if (ui.panel === "shopper") return renderShopperPanel(view);
  if (ui.panel === "sim") return renderSimPanel(view);
  const { line, sheetLine, shown, pick } = view;
  const { issuer, shopper } = state.sheet;
  const invented = (p) => p.invented ? `, invented ${esc(p.role || "person")}` : "";
  let html = "";
  // the issuer's limits
  html += `<div class="grp"><span class="who issuer ci"><i class="dotk"></i>${esc(issuer.name)} set${invented(issuer)}</span>
    ${sheetLine.limits.map((l) => l.bound.source === "issuer"
      ? `<span class="row ci"><span>${esc(l.label)}</span><span class="v" data-src="b:${l.id}" data-k="ctx.${l.id}">${num(l.bound.value, l.unit)} ${esc(l.unit)}</span></span>`
      : `<span class="row ci"><span>${esc(l.label)}</span><span class="note">${esc(shopper.name)}'s number</span></span>`).join("")}</div>`;
  // the shopper's measurements and her rule
  const facts = factsOfLine(sheetLine);
  html += `<div class="grp"><span class="who shopper ci"><i class="dotk"></i>${esc(shopper.name)} measured${invented(shopper)}</span>
    ${facts.map((f) => `<span class="row ci"><span>${esc(f.label)}</span><span class="v" data-src="f:${f.id}" data-k="ctx.${f.id}">${num(f.value, f.unit)} ${esc(f.unit)}</span></span>`).join("")}
    <span class="ci">her rule: ${esc(state.sheet.pick_rule.label)}</span></div>`;
  // the store's own words for the product shown, and its agent's answers
  if (shown) {
    const { parts, ends } = storeWords(shown);
    const notPick = !shown.picked;
    const because = shown.status === "inside"
      ? (shown.arrival && shown.arrival.status !== "stated" ? "inside the limits, but no delivery time is stated" : "inside the limits, but not the cheapest that states a delivery time")
      : shown.status === "struck" ? `${issuer.name} struck it: “${shown.reason}”` : shown.reason;
    html += `<div class="grp"><span class="who store ci"><i class="dotk"></i>${esc(shown.product.store)} states
        <a href="${esc(shown.product.url)}" target="_blank" rel="noopener" title="${esc(shown.product.title)}">its page ↗</a></span>
      ${notPick ? `<span class="looking ci">Not the pick (${money(shown.product.price_cents)}): ${esc(because)}.</span>` : ""}
      ${parts.join("") || '<span class="note ci">no sentence with a figure was found on this page</span>'}
      ${ends.map((e) => `<span class="note ci">${e}</span>`).join("")}</div>`;
    const a = shown.arrival, u = shown.undo, bits = [];
    if (a && a.quote) bits.push(`<span class="ci">delivery: “${esc(a.quote)}” <span class="note">stated, not guaranteed</span></span>`);
    else if (a) bits.push(`<span class="note ci">delivery time: not stated</span>`);
    if (u && u.quote) bits.push(`<span class="ci">to undo: “${esc(u.quote)}”${u.fee ? ` <span class="note">${esc(u.fee)}</span>` : ""}</span>`);
    if (bits.length) html += `<div class="grp"><span class="who store ci"><i class="dotk"></i>${esc(shown.product.store)}'s agent, asked</span>${bits.join("")}</div>`;
  } else {
    html += `<div class="none ci">Nothing is proposed: ${esc(line.reason || "no product yet")}. The agent does not guess a figure a page never states.</div>`;
  }
  html += `<p class="method ci">The model reads the figure; code checks that the quote is in the store's text and does the sums.</p>`;
  $("context").innerHTML = html;
}

// ---------- the sums: one row per limit, each term with its owner's name ----------
function token(part, what, key, src) {
  const unknown = part.value === null || part.value === undefined;
  return `<span class="tok ${unknown ? "unknown" : part.owner}">
    <span class="who ${unknown ? "" : part.owner}">${esc(ownerWords(part))}</span>
    <span class="n" data-dst="${esc(src)}">${unknown ? "not stated" : `<span data-k="${key}">${num(part.value, part.unit)}</span><small>${esc(part.unit)}</small>`}</span>
    <span class="what">${esc(what)}</span></span>`;
}

function renderSums({ line, shown }) {
  const checks = shown ? shown.checks : skeletonChecks(state, line.line_id);
  const tightest = shown && shown.picked && line.tightest ? line.tightest.limit_id : null;
  $("sums").innerHTML = checks.map((ch) => {
    const terms = ch.terms.map((t, i) => token(t, t.owner === "store" ? termNote(t, ch.op) : t.label, `${ch.limit_id}.t${i}`,
      t.owner === "store" ? "q:" + t.figure : "f:" + t.fact));
    const result = ch.terms.length > 1 && ch.lhs !== null ? `<span class="res">= <span data-k="${ch.limit_id}.lhs">${num(ch.lhs, ch.bound.unit)}</span></span>` : "";
    const boundWhat = ch.bound.owner === "shopper" ? ch.bound.label : ch.name;
    const mark = ch.state === "pass" ? "✓ " : ch.state === "fail" ? "✗ " : "";
    return `<div class="sum">
      ${terms.join('<span class="op">+</span>')}${result}
      <span class="op cmp">${opSymbol(ch.op)}</span>
      ${token(ch.bound, boundWhat, `${ch.limit_id}.b`, ch.bound.owner === "shopper" ? "f:" + ch.bound.fact : "b:" + ch.limit_id)}
      <span class="spare ${ch.state === "not_stated" ? "unknown" : ch.state}">${mark}<span data-k="${ch.limit_id}.m">${esc(marginText(ch))}</span>${ch.limit_id === tightest ? "<b>tightest</b>" : ""}</span>
    </div>`;
  }).join("");
  for (const row of document.querySelectorAll(".sum")) {   // a long row keeps its numerals and puts the margin under the comparison
    if (row.scrollWidth <= row.clientWidth + 1) continue;
    row.classList.add("tight");
    row.querySelector(".spare").style.left = (row.querySelector(".res") || row.querySelector(".cmp")).offsetLeft + "px";
  }
}

// ---------- motion: a line opens ----------
function liftFigures(t, only = "q:") {
  for (const n of document.querySelectorAll(`.sum .n[data-dst^="${only}"]`)) {
    fx.fly(document.querySelector(`#context [data-src="${CSS.escape(n.dataset.dst)}"]`), n, t);
  }
}

function intro({ line }) {
  if (!fx.MOTION) return;
  const light = (step, at) => fx.appear(document.querySelector(`#trail [data-step="${step}"]`), at, 260, 0.25);
  light("stores", 0); light("read", 120);
  // 1. the facts that exist for this line arrive in the context column
  let t = 150;
  const items = [...document.querySelectorAll("#context .ci")];
  items.forEach((item, i) => fx.arrive(item, t + i * 40));
  t += items.length * 40 + 160;
  // 2. each fact travels into its place in the sum; the store's figure lifts out of its sentence
  let end = t;
  [...document.querySelectorAll(".sum")].forEach((row, r) => {
    let at = t + r * 260;
    for (const child of row.children) {
      if (child.classList.contains("tok")) {
        const n = child.querySelector(".n"), src = document.querySelector(`#context [data-src="${CSS.escape(n.dataset.dst)}"]`);
        fx.appear(child.querySelector(".who"), at, 220);
        fx.appear(child.querySelector(".what"), at + 300, 220);
        if (src) fx.fly(src, n, at); else fx.appear(n, at + 150, 260);
        at += 150;
      } else if (child.classList.contains("spare")) {
        at += 330;                       // 3. the sum resolves: tick and margin
        fx.arrive(child, at, 280, 3);
        at += 280;
      } else fx.appear(child, at + 270, 200);
    }
    end = Math.max(end, at);
  });
  // 4. the candidates settle on the plot; the ones that never state a figure slide into the gutter
  const times = plotIntro($("box"), line, end - 150);
  light("unstated", times.unstated + 200); light("outside", times.dots + 300); light("inside", times.dots + 380);
  light("struck", times.pick - 200); light("delivery", times.pick - 100); light("picked", times.pick + 100);
}

// ---------- motion: numbers that changed roll to their new values ----------
const before = new Map();
function rollChanges(animate) {
  const now = new Map();
  for (const node of document.querySelectorAll("[data-k]")) {
    const k = node.dataset.k, text = node.textContent;
    now.set(k, text);
    if (animate && before.has(k) && before.get(k) !== text) fx.roll(node, before.get(k), text);
  }
  before.clear();
  for (const [k, v] of now) before.set(k, v);
}

// ---------- Elena's controls ----------
function slider(owner, id, label, value, unit, min, max, step) {
  return `<div class="slider ${owner}"><label for="s_${id}" class="${owner}">${esc(label)}</label><output>${num(value, unit)} ${esc(unit)}</output>
    <input id="s_${id}" data-id="${esc(id)}" data-owner="${owner}" data-unit="${esc(unit)}" type="range" min="${min}" max="${max}" step="${step}" value="${value}"></div>`;
}

function renderShopperPanel({ sheetLine }) {
  const shopper = state.sheet.shopper;
  const active = document.activeElement && document.activeElement.id;
  if ($("say") && (active === "sayText" || (active || "").startsWith("s_"))) return refreshOutputs();
  const facts = factsOfLine(sheetLine);
  const lastTurn = ui.chat[ui.chat.length - 1];
  $("context").innerHTML = `<div class="panel">
    <h2 class="shopper"><i class="dotk"></i>${esc(shopper.name)}, the shopper${shopper.invented ? " (invented)" : ""}: her measurements and her words</h2>
    ${facts.map((f) => slider("shopper", f.id, f.label, f.value, f.unit, f.min, f.max, f.step)).join("") || '<div class="none">This line uses none of her measurements.</div>'}
    <form id="say"><input id="sayText" name="say" type="text" autocomplete="off" aria-label="Say something to the agent" placeholder="Say something to the agent…">
      <button type="submit">Send</button></form>
    <div id="reply" aria-live="polite">${lastTurn ? chatHtml(lastTurn) : `She cannot move a limit or bring back a struck product. Try asking.`}</div></div>`;
  wireSliders();
  $("say").onsubmit = say;
}

function chatHtml(turn) {
  return `<span class="said">“${esc(turn.text)}”</span><br>
    ${turn.refused ? '<span class="refused">REFUSED</span>' : ""}${esc(turn.reply)}`;
}

function refreshOutputs() {
  for (const input of document.querySelectorAll(".slider input")) {
    const fact = state.sheet.shopper_facts.find((f) => f.id === input.dataset.id);
    if (fact && input.dataset.owner === "shopper") input.previousElementSibling.textContent = `${num(fact.value, fact.unit)} ${fact.unit}`;
  }
  if ($("reply") && ui.chat.length && !ui.busy) $("reply").innerHTML = chatHtml(ui.chat[ui.chat.length - 1]);
}

let factTimer = null;
function wireSliders() {
  for (const input of document.querySelectorAll(".slider input")) {
    input.oninput = () => {
      const value = parseFloat(input.value), id = input.dataset.id;
      input.previousElementSibling.textContent = `${num(value, input.dataset.unit)} ${input.dataset.unit}`;
      if (input.dataset.owner === "issuer") { ui.sim.limits[id] = value; return apply(); }
      if (SIM) { ui.sim.facts[id] = value; return apply(); }
      clearTimeout(factTimer);
      factTimer = setTimeout(() => postFact(id, value), 50);
    };
  }
}

async function postFact(fact_id, value) {
  try {
    const res = await fetch("/api/shopper/fact", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ fact_id, value }) });
    if (!res.ok) throw new Error(res.status);
    await load();
  } catch (error) {
    if ($("reply")) $("reply").textContent = "The engine is not connected on this port, so the measurement did not change. (" + error.message + ")";
  }
}

async function say(event) {
  event.preventDefault();
  const text = $("sayText").value.trim();
  if (!text || ui.busy) return;
  ui.busy = true;
  $("reply").innerHTML = `<span class="said">“${esc(text)}”</span><br>…`;
  try {
    const res = await fetch("/api/shopper/say", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
    if (!res.ok) throw new Error(res.status);
    const out = await res.json();
    ui.chat.push({ text, reply: out.reply, refused: !!out.refused });
    $("sayText").value = "";
  } catch (error) {
    ui.chat.push({ text, reply: "The agent is not connected on this port. (" + error.message + ")", refused: false });
  }
  ui.busy = false;
  if ($("reply")) { $("reply").innerHTML = chatHtml(ui.chat[ui.chat.length - 1]); fx.arrive($("reply"), 0, 280, 3); }
  load();
}

function renderSimPanel({ sheetLine }) {
  const active = document.activeElement && document.activeElement.id;
  if ($("simreset") && (active || "").startsWith("s_")) return refreshOutputs();
  const limits = sheetLine.limits.filter((l) => l.bound.source === "issuer");
  $("context").innerHTML = `<div class="panel">
    <h2 style="color:var(--bad)">SIMULATION in this page. Not ${esc(state.sheet.issuer.name)}'s phone; nothing is signed.</h2>
    ${limits.map((l) => slider("issuer", l.id, l.label, l.bound.value, l.unit, l.bound.min, l.bound.max, l.bound.step)).join("")}
    ${factsOfLine(sheetLine).map((f) => slider("shopper", f.id, f.label, f.value, f.unit, f.min, f.max, f.step)).join("")}
    <button id="simreset">Back to the server's state</button></div>`;
  wireSliders();
  $("simreset").onclick = () => { ui.sim = { limits: {}, facts: {} }; document.activeElement.blur(); $("context").innerHTML = ""; apply(); };
}

// ---------- the SQL view: one statement returns the passing box ----------
const sql = { key: null, data: null, error: null };

function renderSqlPanel({ line }) {
  const key = line.line_id + "|" + state.version;
  if (sql.key !== key && !FIXTURE && !SIM) {
    sql.key = key;
    fetch("/api/sql/passing-box?line_id=" + encodeURIComponent(line.line_id))
      .then((res) => res.ok ? res.json() : Promise.reject(new Error(res.status === 503 ? "SingleStore is not reachable" : "HTTP " + res.status)))
      .then((data) => { sql.data = data; sql.error = null; })
      .catch((error) => { sql.data = null; sql.error = error.message; })
      .finally(() => { if (ui.panel === "sql" && location.hash !== "#sheet") renderSqlPanel({ line: state.lines.find((l) => l.line_id === lineId()) }); });
  }
  let body;
  if (FIXTURE || SIM) body = `<div class="none">The SQL view needs the live engine and SingleStore; this page is drawing ${FIXTURE ? "fixture data" : "a simulation"}.</div>`;
  else if (sql.error) body = `<div class="none">${esc(sql.error)}. The screen and the checks do not depend on the database.</div>`;
  else if (!sql.data || sql.data.line_id !== line.line_id) body = `<div class="none">Asking SingleStore…</div>`;
  else {
    const id = (store, pid) => store + "|" + pid;
    const rows = new Set(sql.data.rows.map((r) => id(r.store, r.product_id)));
    const inside = new Set(line.candidates.filter((c) => c.status === "inside").map((c) => id(c.product.store, c.product.product_id)));
    const same = rows.size === inside.size && [...rows].every((r) => inside.has(r));
    const onlySql = [...rows].filter((r) => !inside.has(r)).length, onlyEngine = [...inside].filter((r) => !rows.has(r)).length;
    body = `<pre class="sqltext">${esc(sql.data.sql)}</pre>
      <p class="sqlresult ${same ? "same" : "differ"}"><b>${rows.size} rows</b> came back. The engine, in Python, has <b>${inside.size}</b> amber dots.
      ${same ? "<b>They are the same products.</b>" : `<b>They differ:</b> ${onlySql} only in the query, ${onlyEngine} only in the engine.`}</p>`;
  }
  $("context").innerHTML = `<div class="panel"><h2>SingleStore: this one statement is the passing box of this line</h2>${body}</div>`;
}

// ---------- the sheet strip ----------
const STATUS = { ready: "Ready", pick_up: "Pick up locally", open: "Open", next_candidate: "Next candidate" };

function renderTiles({ line }) {
  $("tiles").innerHTML = state.lines.map((l) => {
    const p = pickOf(l);
    const head = STATUS[l.status] || l.status;
    const price = p && l.status !== "pick_up" ? `<i data-k="tile.price.${l.line_id}">${money(p.product.price_cents)}</i>` : "";
    const body = l.tightest
      ? `<span class="status">${esc(head)}${price}</span><span><span class="tick">✓</span> <span data-k="tile.${l.line_id}">${esc(l.tightest.text)}</span></span>`
      : `<span class="wrap"><b class="status">${esc(head)}:</b> ${esc(l.reason || "nothing proposed")}</span>`;
    return `<a class="tile ${l.status}" href="#${l.line_id}" aria-current="${l.line_id === line.line_id}">
      <span class="need">${esc(l.need)}</span>${body}</a>`;
  }).join("");
}

// ---------- the whole sheet: the counts and six large tiles ----------
function renderSheet() {
  renderHead({ line: null });
  const c = state.counts, stores = state.sheet.stores.length;
  const step = (n, words, k) => `<div class="count"><span class="n" data-k="count.${k}">${n}</span><span>${words}</span></div>`;
  const dots = { inside: "inside", outside: "outside", not_stated: "never state a figure", struck: "struck" };
  $("main").innerHTML = `<div class="sheetview"><div class="counts">
    ${step(c.products_found, `products found<br>at ${stores} stores`, "found")}<span class="sep">›</span>
    ${step(c.state_every_figure, `state every deciding figure<br>(read by the model; quote found<br>in the store's text by code)`, "every")}<span class="sep">›</span>
    ${step(c.inside_limits, `are inside<br>the limits`, "inside")}
    <span class="grow"></span>
    ${step(`${c.lines_ready} of ${c.lines_total}`, `lines ready<br>(lines, not products)`, "ready")}
  </div><div class="big">${state.lines.map((l) => {
    const p = pickOf(l);
    const tally = Object.keys(dots).map((k) => [k, l.candidates.filter((x) => x.status === k).length]).filter(([, n]) => n)
      .map(([k, n]) => `<span class="tally"><i class="d ${k}"></i>${n} ${dots[k]}</span>`).join("");
    return `<a class="tile bigtile ${l.status}" href="#${l.line_id}">
      <span class="need">${esc(l.need)}</span>
      <span class="status">${esc(STATUS[l.status] || l.status)}${p && l.status !== "pick_up" ? `<i data-k="big.price.${l.line_id}">${money(p.product.price_cents)}</i>` : ""}</span>
      <span class="wrap">${l.tightest ? `<span class="tick">✓</span> ${esc(l.tightest.text)} on ${esc(l.tightest.name)}` : esc(cap(l.reason || "nothing proposed"))}</span>
      <span class="store">${p ? `<i class="dotk"></i>${esc(p.product.store)}` : "&nbsp;"}</span>
      <span class="wrap tallies">${tally || "no product found yet"}</span>
    </a>`;
  }).join("")}</div></div>`;
}

// ---------- the seal ----------
function sensoSummary() {
  const rows = Array.isArray(state.senso) ? state.senso : [];
  if (!rows.length) return "";
  const blocked = rows.filter((r) => r.verdict === "conflict" || r.verdict === "unsupported").length;
  return `<span class="senso ${blocked ? "blocked" : ""}" title="Each sentence of the sheet, checked by Senso against the order and the handout">Senso: ${rows.length} sentences checked, ${blocked ? blocked + " block the signature" : "none in conflict"}</span>`;
}

function renderSeal(justSigned) {
  const { seal, issuer_key: key, sheet } = state;
  const el = $("seal");
  el.classList.toggle("signed", !!seal.signed);
  if (!seal.signed) {
    el.innerHTML = `<span class="state">${esc(seal.text || "Not signed. No cart exists at any store.")}</span>
      <span class="issuer">Only ${esc(sheet.issuer.name)}'s signature creates the carts.</span>
      <span class="grow"></span>${sensoSummary()}<span class="total">${state.counts.lines_ready} of ${state.counts.lines_total} lines ready${state.total_cents ? ` · <span data-k="total">${money(state.total_cents)}</span>` : ""}</span>`;
    return;
  }
  const sig = seal.signature || {};
  const persona = sig.persona || (key && key.persona) || {};
  const who = seal.signer || (sig.signer && sig.signer.name) || sig.name || sheet.issuer.name;
  const at = seal.signed_at || sig.at || sig.signed_at;
  const time = at ? new Date(at).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }) : "";
  const hash = seal.sheet_hash || sig.sheet_hash || "";
  const identity = persona.inquiry_id
    ? `Persona <code>${esc(persona.inquiry_id)}</code> ${esc(persona.label || persona.status || "")}`
    : `Persona: ${esc(persona.label || "identity not checked")}`;
  const carts = (seal.carts || []).map((c) => `<span class="part"><a href="${esc(c.cart_url)}" target="_blank" rel="noopener">${esc(c.store)}${c.total_cents ? " " + money(c.total_cents) : ""} ↗</a>${c.mode && c.mode !== "real" && c.mode !== "live" ? ` (${esc(c.mode)})` : ""}</span>`);
  el.innerHTML = `<span class="state issuer part">Signed by ${esc(who)}${time ? " at " + time : ""}.</span>
    ${hash ? `<span class="part">sheet hash <code title="${esc(hash)}">${esc(hash.slice(0, 8))}…</code></span>` : ""}
    <span class="part">${identity}</span>
    <span class="carts"><span class="part">${carts.length ? "Carts now exist; nothing is checked out or paid:" : "No cart link came back."}</span> ${carts.join(" · ")}</span>`;
  // the seal closes: signer, hash and identity appear, then the cart links arrive one per store
  if (justSigned) el.querySelectorAll(".part").forEach((part, i) => fx.arrive(part, 250 + i * 180, 320, 3));
}

addEventListener("keydown", (e) => {
  if (e.target.tagName === "INPUT" || e.metaKey || e.ctrlKey || e.altKey || !state) return;
  const n = parseInt(e.key, 10);
  if (n >= 1 && n <= state.lines.length) location.hash = state.lines[n - 1].line_id;
  if (e.key === "0" || e.key === "Escape") location.hash = "sheet";
  if (e.key === "e") { e.preventDefault(); togglePanel("shopper"); }
  if (e.key === "q") togglePanel("sql");
});

new ResizeObserver(() => {       // the plot is drawn in pixels: redraw when its box changes size
  const p = $("plot"), size = p ? p.clientWidth + "x" + p.clientHeight : "";
  if (state && size !== sized) { sized = size; render(); }
}).observe($("main"));
load();
listen();
