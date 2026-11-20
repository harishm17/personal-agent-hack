// Sign-Off big screen. Everything drawn here comes from GET /api/state; the page decides nothing.
// (?sim=1 is the one exception: it moves a limit inside the page, clearly marked, to build the motion.)
import {
  defaultLineId, figureSpan, marginText, money, num, opSymbol, ownerWords, pickOf, simulate, skeletonChecks, termNote,
} from "/screen/model.js";
import { drawPlot } from "/screen/plot.js";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const params = new URLSearchParams(location.search);
const SIM = params.get("sim") === "1";
// ?fixture=1 draws the committed fixture run whatever the engine holds; ?fixture=signed the same run after a signature
const FIXTURE = { 1: "/screen/fixture-state.json", signed: "/screen/fixture-signed.json" }[params.get("fixture")];

let server = null;            // the last /api/state
let state = null;             // what is drawn: server, or the sim's recompute of it
let raw = "";
const ui = { inspect: null, panel: params.get("panel") || (SIM ? "sim" : "words"), sim: { limits: {}, facts: {} }, chat: [], busy: false, note: "" };

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
  const stage = $("stage");
  stage.style.transform = `translate(${(innerWidth - 960 * k) / 2}px, ${(innerHeight - 540 * k) / 2}px) scale(${k})`;
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
    ui.note = "cannot reach /api/state";
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
setInterval(() => { if (!live) load(); }, 2000);   // the fixture server has no event stream: poll instead

// ---------- which line ----------
function lineId() {
  const hash = location.hash.slice(1);
  return state.lines.some((l) => l.line_id === hash) ? hash : defaultLineId(state);
}
addEventListener("hashchange", () => { ui.inspect = null; render(); });

// ---------- render ----------
function render() {
  if (!state) return;
  $("stage").classList.add("ready");
  const sheetView = location.hash === "#sheet";
  $("stage").classList.toggle("sheet", sheetView);
  $("stage").classList.toggle("sql", !sheetView && ui.panel === "sql");
  if (sheetView) { renderSheet(); renderSeal(); flashChanges(); return; }
  if (!$("box")) $("mid").innerHTML = '<div id="plot"><svg id="box" role="img" aria-label="Every candidate of this line against its limits"></svg></div><div id="side"></div>';
  const id = lineId();
  const line = state.lines.find((l) => l.line_id === id);
  const sheetLine = state.sheet.lines.find((l) => l.id === id);
  const pick = pickOf(line);
  const shown = line.candidates.find((c) => c.id === ui.inspect) || pick;
  if (!line.candidates.some((c) => c.id === ui.inspect)) ui.inspect = null;
  const view = { line, sheetLine, pick, shown, index: state.lines.indexOf(line) };
  renderHead(view);
  renderSums(view);
  renderSide(view);
  renderTiles(view);
  renderSeal();
  drawPlot($("box"), line, shown ? shown.id : null, (cid) => {
    ui.inspect = pick && cid === pick.id ? null : cid;
    if (ui.panel !== "words") ui.panel = "words";
    render();
  });
  flashChanges();
}

function renderHead({ line, index }) {
  const { issuer, shopper } = state.sheet;
  const mode = state.mode === "fixture" ? "FIXTURE DATA" : state.mode === "replay" ? "REPLAY OF CACHED STORE DATA" : "";
  const title = line ? cap(line.need) : state.sheet.title;
  const sub = line ? `<a href="#sheet" title="The whole sheet. Key: 0">line ${index + 1} of ${state.lines.length}</a>` : `${state.lines.length} lines`;
  $("head").innerHTML = `
    <h1>${esc(title)}</h1>
    <span class="sub">${sub}${state.sheet.invented ? " · invented people" : ""}</span>
    <span class="grow"></span>
    <span class="key issuer">${esc(issuer.name)} set</span>
    <span class="key shopper">${esc(shopper.name)} stated</span>
    <span class="key store">store's words</span>
    <span class="key unknown">not stated</span>
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

const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

function token(part, what, key) {
  const unknown = part.value === null || part.value === undefined;
  return `<span class="tok ${unknown ? "unknown" : part.owner}">
    <span class="who ${unknown ? "" : part.owner}">${esc(ownerWords(part))}</span>
    <span class="n" data-k="${key}">${unknown ? "not stated" : num(part.value, part.unit) + `<small>${esc(part.unit)}</small>`}</span>
    <span class="what">${esc(what)}</span></span>`;
}

function renderSums({ line, shown }) {
  const checks = shown ? shown.checks : skeletonChecks(state, line.line_id);
  const tightest = shown && shown.picked && line.tightest ? line.tightest.limit_id : null;
  $("sums").innerHTML = checks.map((ch) => {
    const terms = ch.terms.map((t, i) => token(t, t.owner === "store" ? termNote(t, ch.op) : t.label, `${ch.limit_id}.t${i}`));
    const result = ch.terms.length > 1 && ch.lhs !== null ? `<span class="res" data-k="${ch.limit_id}.lhs">= ${num(ch.lhs, ch.bound.unit)}</span>` : "";
    const boundWhat = ch.bound.owner === "shopper" ? ch.bound.label : ch.name;
    const mark = ch.state === "pass" ? "✓ " : ch.state === "fail" ? "✗ " : "";
    return `<div class="sum">
      ${terms.join('<span class="op">+</span>')}${result}
      <span class="op">${opSymbol(ch.op)}</span>
      ${token(ch.bound, boundWhat, `${ch.limit_id}.b`)}
      <span class="spare ${ch.state === "not_stated" ? "unknown" : ch.state}" data-k="${ch.limit_id}.m">${mark}${esc(marginText(ch))}${ch.limit_id === tightest ? "<b>the tightest check</b>" : ""}</span>
    </div>`;
  }).join("");
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
      parts.push(`“${esc(text.slice(0, s))}<mark>${esc(text.slice(s, e))}</mark>${esc(text.slice(e))}”`);
      if (t.kind === "spread") ends.push(`A stated spread: code uses ${num(t.value, t.unit)} ${esc(t.unit)}, the end that could fail.`);
      if (t.kind === "adjustable") ends.push(`An adjustable range: it passes when the limit lies inside it.`);
    }
  }
  return { parts, ends };
}

function renderSide(view) {
  if (ui.panel === "sql") return renderSqlPanel(view);
  if (ui.panel === "shopper") return renderShopperPanel(view);
  if (ui.panel === "sim") return renderSimPanel(view);
  const { line, shown, pick } = view;
  const why = line.why;
  const limitsWord = shown && shown.checks.length === 2 ? "both limits" : "every limit";
  let html = "";
  if (shown) {
    const { parts, ends } = storeWords(shown);
    html += `<div class="words">${parts.join(" ") || "No sentence with a figure was found on this page."}
        <a href="${esc(shown.product.url)}" target="_blank" rel="noopener" title="${esc(shown.product.title)}">${esc(shown.product.store)}'s page ↗</a>
        ${ends.map((e) => `<span class="end">${e}</span>`).join("")}</div>`;
  } else {
    html += `<div class="cap">Nothing is proposed for this line</div>
      <div class="none">${esc(cap(line.reason || "no candidate yet"))}. The agent does not guess a figure a page never states.</div>`;
  }
  html += `<p class="method">The model reads the figure; code checks that the quote is in the store's text and does the sums.</p>`;
  const rule = `<span class="shopper"><b>${esc(state.sheet.shopper.name)}'s rule, ${esc(why.rule)}</b></span>`;
  if (shown && pick && shown.id === pick.id) {
    const struck = line.struck.length ? `<span class="issuer"><b>${esc(state.sheet.issuer.name)} struck ${line.struck.length} before it:</b> “${esc(line.struck[0].reason)}”</span> ` : "";
    html += `<div class="why"><b>Why this one.</b> ${struck}<b>${why.inside} of ${why.total}</b> are inside ${limitsWord}${line.status === "pick_up"
      ? `. Nothing is shipped, so no delivery time is needed: ${esc(line.reason || "picked up locally")}. The cheapest inside is <b>${money(why.pick_price_cents)}</b>.`
      : `; <b>${why.with_delivery_time}</b> of those state a delivery time. ${rule}, picks <b>${money(why.pick_price_cents)}</b>.`}</div>`;
  } else if (shown) {
    const because = shown.status === "inside"
      ? (shown.arrival && shown.arrival.status !== "stated" ? "it is inside the limits, but its store states no delivery time" : "it is inside the limits, but is not the cheapest that states a delivery time")
      : shown.status === "struck" ? `${state.sheet.issuer.name} struck it: “${shown.reason}”` : shown.reason;
    html += `<div class="why"><b>Not the pick (${money(shown.product.price_cents)}):</b> ${esc(because)}.
      ${pick ? "Select the ringed dot to return to the pick." : ""}</div>`;
  } else {
    html += `<div class="why"><b>${why.inside} of ${why.total}</b> are inside ${limitsWord}. ${rule}, has nothing to choose from.</div>`;
  }
  if (shown) html += agentWords(shown);
  $("side").innerHTML = html;
}

/** What the store's own agent answered about delivery and returns, in its words. */
function agentWords(c) {
  const bits = [];
  if (c.arrival && c.arrival.quote) bits.push(`delivery, stated not guaranteed: “${esc(c.arrival.quote)}”`);
  else if (c.arrival) bits.push("delivery time: not stated");
  const u = c.undo;
  if (u && u.quote) bits.push(`to undo${u.applies_to && u.applies_to !== "all" ? " (" + esc(u.applies_to) + ")" : ""}: “${esc(u.quote)}”${u.fee ? ", " + esc(u.fee) : ""}`);
  return bits.length ? `<p class="asked"><b>${esc(c.product.store)}'s agent, asked:</b> ${bits.join("; ")}</p>` : "";
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
      .finally(() => { if (ui.panel === "sql") renderSqlPanel({ line: state.lines.find((l) => l.line_id === lineId()) }); });
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
  $("side").innerHTML = `<div class="panel"><h2>SingleStore: this one statement is the passing box of this line</h2>${body}</div>`;
}

// ---------- Elena's controls ----------
function factsOfLine(sheetLine) {
  const ids = new Set();
  for (const limit of sheetLine.limits) {
    for (const t of limit.terms) if (t.source === "shopper") ids.add(t.fact);
    if (limit.bound.source === "shopper") ids.add(limit.bound.fact);
  }
  return state.sheet.shopper_facts.filter((f) => ids.has(f.id));
}

function slider(owner, id, label, value, unit, min, max, step) {
  return `<div class="slider ${owner}"><label for="s_${id}">${esc(label)}</label>
    <input id="s_${id}" data-id="${esc(id)}" data-owner="${owner}" data-unit="${esc(unit)}" type="range" min="${min}" max="${max}" step="${step}" value="${value}">
    <output>${num(value, unit)} ${esc(unit)}</output></div>`;
}

function renderShopperPanel({ sheetLine }) {
  const shopper = state.sheet.shopper;
  const active = document.activeElement && document.activeElement.id;
  if (active === "sayText" || (active || "").startsWith("s_")) return refreshOutputs();
  const facts = factsOfLine(sheetLine);
  const last = ui.chat[ui.chat.length - 1];
  $("side").innerHTML = `<div class="panel">
    <h2 class="shopper">${esc(shopper.name)}, the shopper${shopper.invented ? " (invented)" : ""}: her measurements and her words</h2>
    ${facts.map((f) => slider("shopper", f.id, f.label, f.value, f.unit, f.min, f.max, f.step)).join("") || '<div class="none">This line uses none of her measurements.</div>'}
    <form id="say"><input id="sayText" name="say" type="text" autocomplete="off" aria-label="Say something to the agent" placeholder="Say something to the agent…">
      <button type="submit">Send</button></form>
    <div id="reply" aria-live="polite">${last ? chatHtml(last) : `She cannot move a limit or bring back a struck product. Try asking.`}</div></div>`;
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
    if (fact && input.dataset.owner === "shopper") input.nextElementSibling.textContent = `${num(fact.value, fact.unit)} ${fact.unit}`;
  }
  if ($("reply") && ui.chat.length && !ui.busy) $("reply").innerHTML = chatHtml(ui.chat[ui.chat.length - 1]);
}

let factTimer = null;
function wireSliders() {
  for (const input of document.querySelectorAll(".slider input")) {
    input.oninput = () => {
      const value = parseFloat(input.value), id = input.dataset.id;
      input.nextElementSibling.textContent = `${num(value, input.dataset.unit)} ${input.dataset.unit}`;
      if (input.dataset.owner === "issuer") { ui.sim.limits[id] = value; return apply(); }
      if (SIM) { ui.sim.facts[id] = value; return apply(); }
      clearTimeout(factTimer);
      factTimer = setTimeout(() => postFact(id, value), 50);
    };
    input.onchange = () => input.blur();
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
  $("reply").innerHTML = chatHtml(ui.chat[ui.chat.length - 1]);
  load();
}

function renderSimPanel({ sheetLine }) {
  const active = document.activeElement && document.activeElement.id;
  if ((active || "").startsWith("s_")) return refreshOutputs();
  const limits = state.sheet.lines.find((l) => l.id === sheetLine.id).limits.filter((l) => l.bound.source === "issuer");
  $("side").innerHTML = `<div class="panel">
    <h2 style="color:var(--bad)">SIMULATION in this page. Not ${esc(state.sheet.issuer.name)}'s phone; nothing is signed.</h2>
    ${limits.map((l) => slider("issuer", l.id, l.label, l.bound.value, l.unit, l.bound.min, l.bound.max, l.bound.step)).join("")}
    ${factsOfLine(sheetLine).map((f) => slider("shopper", f.id, f.label, f.value, f.unit, f.min, f.max, f.step)).join("")}
    <button id="simreset">Back to the server's state</button></div>`;
  wireSliders();
  $("simreset").onclick = () => { ui.sim = { limits: {}, facts: {} }; document.activeElement.blur(); apply(); };
}

// ---------- the sheet strip ----------
const STATUS = { ready: "Ready", pick_up: "Pick up locally", open: "Open", next_candidate: "Next candidate" };

function renderTiles({ line }) {
  $("tiles").innerHTML = state.lines.map((l) => {
    const p = pickOf(l);
    const head = STATUS[l.status] || l.status;
    const price = p && l.status !== "pick_up" ? `<i>${money(p.product.price_cents)}</i>` : "";
    const body = l.tightest
      ? `<span class="status">${esc(head)}${price}</span><span data-k="tile.${l.line_id}">✓ ${esc(l.tightest.text)}</span>`
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
  $("sums").innerHTML = `<div class="counts">
    ${step(c.products_found, `products found<br>at ${stores} stores`, "found")}<span class="op">→</span>
    ${step(c.state_every_figure, `state every deciding figure<br>(read by the model; quote found<br>in the store's text by code)`, "every")}<span class="op">→</span>
    ${step(c.inside_limits, `are inside<br>the limits`, "inside")}
    <span class="grow"></span>
    ${step(`${c.lines_ready} of ${c.lines_total}`, `lines ready<br>(lines, not products)`, "ready")}
  </div>`;
  const dots = { inside: "inside", outside: "outside", not_stated: "never state a figure", struck: "struck" };
  $("mid").innerHTML = `<div class="big">${state.lines.map((l) => {
    const p = pickOf(l);
    const tally = Object.keys(dots).map((k) => [k, l.candidates.filter((x) => x.status === k).length]).filter(([, n]) => n)
      .map(([k, n]) => `<span class="tally"><i class="d ${k}"></i>${n} ${dots[k]}</span>`).join("");
    return `<a class="tile bigtile ${l.status}" href="#${l.line_id}">
      <span class="need">${esc(l.need)}</span>
      <span class="status">${esc(STATUS[l.status] || l.status)}${p && l.status !== "pick_up" ? `<i>${money(p.product.price_cents)}</i>` : ""}</span>
      <span class="wrap" data-k="big.${l.line_id}">${l.tightest ? `✓ ${esc(l.tightest.text)} on ${esc(l.tightest.name)}` : esc(cap(l.reason || "nothing proposed"))}</span>
      <span class="store">${p ? esc(p.product.store) : "&nbsp;"}</span>
      <span class="wrap tallies">${tally || "no product found yet"}</span>
    </a>`;
  }).join("")}</div>`;
}

// ---------- the seal ----------
function sensoSummary() {
  const rows = Array.isArray(state.senso) ? state.senso : [];
  if (!rows.length) return "";
  const blocked = rows.filter((r) => r.verdict === "conflict" || r.verdict === "unsupported").length;
  return `<span class="senso ${blocked ? "blocked" : ""}" title="Each sentence of the sheet, checked by Senso against the order and the handout">Senso: ${rows.length} sentences checked, ${blocked ? blocked + " block the signature" : "none in conflict"}</span>`;
}

function renderSeal() {
  const { seal, issuer_key: key, sheet } = state;
  const el = $("seal");
  el.classList.toggle("signed", !!seal.signed);
  if (!seal.signed) {
    el.innerHTML = `<span class="state">${esc(seal.text || "Not signed. No cart exists at any store.")}</span>
      <span class="issuer"><b>Only ${esc(sheet.issuer.name)}'s signature creates the carts.</b></span>
      <span class="grow"></span>${sensoSummary()}<span class="total">${state.counts.lines_ready} of ${state.counts.lines_total} lines ready${state.total_cents ? " · " + money(state.total_cents) : ""}</span>`;
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
  const carts = (seal.carts || []).map((c) => `<a href="${esc(c.cart_url)}" target="_blank" rel="noopener">${esc(c.store)}${c.total_cents ? " " + money(c.total_cents) : ""} ↗</a>${c.mode && c.mode !== "real" && c.mode !== "live" ? ` (${esc(c.mode)})` : ""}`);
  el.innerHTML = `<span class="state">Signed by ${esc(who)}${time ? " at " + time : ""}.</span>
    ${hash ? `<span>sheet hash <code title="${esc(hash)}">${esc(hash.slice(0, 8))}…</code></span>` : ""}
    <span>${identity}</span>
    <span class="carts">${carts.length ? "<b>Carts now exist; nothing is checked out or paid:</b> " + carts.join(" · ") : "No cart link came back."}</span>`;
}

// ---------- a short flash on every number that changed ----------
const before = new Map();
function flashChanges() {
  for (const node of document.querySelectorAll("[data-k]")) {
    const k = node.dataset.k, text = node.textContent;
    if (before.has(k) && before.get(k) !== text) node.classList.add("changed");
    before.set(k, text);
  }
}

addEventListener("keydown", (e) => {
  if (e.target.tagName === "INPUT" || e.metaKey || e.ctrlKey || e.altKey || !state) return;
  const n = parseInt(e.key, 10);
  if (n >= 1 && n <= state.lines.length) location.hash = state.lines[n - 1].line_id;
  if (e.key === "0" || e.key === "Escape") location.hash = "sheet";
  if (e.key === "e") { e.preventDefault(); togglePanel("shopper"); }
  if (e.key === "q") togglePanel("sql");
});

new ResizeObserver(() => state && render()).observe($("mid"));
load();
listen();
