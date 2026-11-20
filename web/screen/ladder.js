// Sign-Off, the decision screen. Products shown as products, cheapest first, each rejected with its reason
// until the first one that passes: that one is the pick. Left: the list as its author wrote it (the source of
// every requirement). Right: why this one, in the list's words and the store's words, and the signature.
// Everything is drawn from GET /api/state; the page decides nothing and assumes no particular sheet.
import { figureSpan, money, opSymbol, pickOf, simulate } from "/screen/model.js";
import * as fx from "/screen/motion.js";

const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const cap = (s) => String(s || "").charAt(0).toUpperCase() + String(s || "").slice(1);
const words = (s) => String(s || "").replace(/_/g, " ");
const clip = (t, n) => (String(t).length > n ? String(t).slice(0, n - 1).trimEnd() + "…" : String(t));
const g = (v) => (v === null || v === undefined ? "?" : String(+(+v).toFixed(2)));      // 10, 21.5, 1.28
const n_ = (n, one, many) => `${n} ${n === 1 ? one : many}`;                                 // "1 page", "3 pages"
const withUnit = (text, unit) => (unit && unit !== "count" ? `${text} ${unit}` : String(text));   // "85 dB", "70 sheets", "24"
/** How many of an item are bought, when the sheet says so (a class set of 24); else 1. */
const qty = (line) => (sheetLineOf(line) || {}).quantity || line.quantity || 1;
const times = (line) => (qty(line) > 1 ? ` × ${qty(line)}` : "");
const q = (sel, root = document) => root.querySelector(sel);
const params = new URLSearchParams(location.search);
const SIM = params.get("sim") === "1";
const FIXTURE = { 1: "/screen/fixture-state.json", signed: "/screen/fixture-signed.json", sheet2: "/screen/fixture-sheet2.json", sheet3: "/screen/fixture-sheet3.json" }[params.get("fixture")];

let server = null, state = null, raw = "";
// ?open=above,below unfolds the list; ?drawer=shopper|step:3|<candidate id> opens the side sheet; ?show=<candidate id> selects a row
const ui = { open: new Set((params.get("open") || "").split(",").filter(Boolean)), drawer: params.get("drawer"), show: params.get("show"),
  chat: [], busy: false, sim: { limits: {}, facts: {}, strikes: [] } };
const last = { line: null, pick: null, signed: null, quiet: false };
const aux = { egress: null, gate: null, enroll: null, trail: null, sheets: null, pages: {}, key: "" };
// The last two tabs show only when their page is served: from /api/health's `pages` when it has that key; until then
// from the routers it lists, for the pages known to be in the repo (asking for a page that is not there would log a 404).
const TABS = [["/", "Decision"], ["/trail/", "Trail"], ["/graph/", "Memory", "signoff.graph.api"], ["/talk/", "Conversations", "signoff.talk.api"], ["/seal/", "Signature", "signoff.sign.api"]];
const KNOWN_PAGES = new Set(["/talk/", "/graph/", "/seal/"]);      // pages that are in the repo on main; /seal/ joins when its folder lands, or at once through `pages`
let introUntil = 0;

if (SIM) {
  for (const pair of (params.get("set") || "").split(",").filter(Boolean)) {
    const [id, v] = pair.split(":");
    (id.includes(".") ? ui.sim.limits : ui.sim.facts)[id] = parseFloat(v);
  }
}
// For watching a change without a phone: ?sim=1&then=L1.capacity:400@3000 (a limit moves after 3 s), then=strike:1@3000,
// and ?fixture=1&sign=3000 (the signed fixture replaces the unsigned one after 3 s).
let fixtureUrl = FIXTURE;
if (FIXTURE && params.get("sign")) setTimeout(() => { fixtureUrl = "/screen/fixture-signed.json"; load(); }, parseInt(params.get("sign"), 10));
if (SIM && params.get("then")) {
  for (const item of params.get("then").split(",")) {
    const [pair, ms] = item.split("@"), [id, v] = pair.split(":");
    setTimeout(() => {
      if (!server) return;
      const line = theLine();
      if (id === "strike") ui.sim.strikes.push({ line_id: line.line_id, product_key: (pickOf(line) || { product: {} }).product.product_key, reason: "simulated strike" });
      else (id.includes(".") ? ui.sim.limits : ui.sim.facts)[id] = parseFloat(v);
      apply();
    }, parseInt(ms, 10) || 2000);
  }
}

document.body.innerHTML = `<div id="app">
  <header class="top" id="top"></header>
  <nav class="steps" id="steps" aria-label="The run, step by step"></nav>
  <aside class="doc card" id="doc" aria-label="The list, as written"></aside>
  <main class="list card" id="list"><p class="muted">Loading…</p></main>
  <aside class="side" id="side" aria-label="Why this one, and the signature"></aside>
  <aside class="drawer card" id="drawer" hidden aria-live="polite"></aside>
  <div class="replay" id="replay" hidden role="dialog" aria-modal="true" aria-label="How the agent got here"></div>
  <div class="toast" id="toast" hidden role="status"></div>
  <div class="tip" id="tip" hidden></div></div>`;

// ---------- data ----------
async function load() {
  try {
    const res = await fetch(fixtureUrl || "/api/state", { cache: "no-store" });
    if (!res.ok) throw new Error(res.status);
    const text = await res.text();
    if (text === raw) return;
    raw = text;
    server = JSON.parse(text);
    apply();
  } catch (error) {
    if (!state) q("#list").innerHTML = `<p class="muted">Waiting for the engine…</p>`;
  }
}
function apply() {
  const moved = SIM && (Object.keys(ui.sim.limits).length || Object.keys(ui.sim.facts).length || ui.sim.strikes.length);
  state = moved ? simulate(server, ui.sim) : server;
  render();
}
// Optional extras from their own routes; any may be missing, and the screen draws only what exists.
async function loadAux() {
  if (FIXTURE) {     // ?fixture=..&menu=1: a sample of the sheet menu, to look at it without the route
    if (params.get("c14") && state && !state.pick_rules) {
      state.pick_rules = [{ id: "cheapest", label: "cheapest that meets the list" }, { id: "best_reviewed", label: "best reviewed among those that pass" }, { id: "most_popular", label: "Most reviewed" }, { id: "best_value", label: "best value among those that pass" }];
      state.sheet.pick_rule = { ...state.sheet.pick_rule, id: params.get("c14") === "1" ? "cheapest" : params.get("c14") };
      const line = theLine(), pass = line.candidates.filter((c) => c.status === "inside").sort((a, b) => a.product.price_cents - b.product.price_cents);
      pass.forEach((c, i) => { c.rating = { found: true, rating: [4.1, 4.7, 4.4, 3.9][i % 4], out_of: 5, review_count: [58, 212, 96, 12][i % 4], rating_site: "sample.example", sentence: { quote: "Sample review text for the layout.", site: "sample.example", url: "#" } }; });
      if (pass[1]) pass[1].preferences = [{ id: "sample", label: "Sample preference: 100 sheets if they have them", status: "met" }];
      (sheetLineOf(line).preferences = [{ id: "sample", name: "sheets", label: "100 if they have them", terms: [], op: ">=", bound: { source: "issuer", value: 100 }, unit: "sheets", from_order: { quote: "100 sheets if they have them.", value: 100 } }]);
      if (!byPrice()) { const best = [...pass].sort((a, b) => b.rating.rating - a.rating.rating)[0]; pass.forEach((c) => { c.picked = c === best; }); line.pick = best.id; }
      const p = pickOf(line);
      if (p) p.picked_because = byPrice() ? "the cheapest that passes" : "rated 4.7 from 212 reviews, the highest that passes";
      last.quiet = true; render();
    }
    if (params.get("msg") && state && !state.sheet.shopper_facts.some((f) => f.suggested_from)) {
      state.sheet.shopper_facts.forEach((f, i) => { f.suggested_from = { message_id: "sample", from_label: "the sample message", at: "2026-11-20T10:41:00-08:00", quote: "Sample message: I measured it this morning.", matches: params.get("msg") === "1" || i > 0 }; });
      last.quiet = true; render();
    }
    if (params.get("tools") === "1" && state && !aux.tools) { aux.tools = { tools: [
      { name: "SingleStore", number: 1, words: "statement, 9 rows, same as the screen", route: "/api/sql/passing-box", detail: "Sample row: the one statement returns the rows the engine shows as passing." },
      { name: "Statsig", number: 1, words: "gate checked, reader switched back", route: "/api/gate/status", detail: "Sample row." },
      { name: "Amplitude", number: 212, words: "tool-call events sent", route: "/api/egress", detail: "Sample row." }] }; ui.drawer = "tools"; ui.open.add("tool:0"); last.quiet = true; render(); }
    if (params.get("menu") === "1" && state) { aux.sheets = { sheets: [{ id: state.sheet.id, title: state.sheet.title, items: state.lines.length }, { id: "sample", title: "Sample second list", items: 4 }] }; ui.menu = true; last.quiet = true; render(); }
    return;
  }
  const get = (url) => fetch(url, { cache: "no-store" }).then((r) => (r.ok ? r.json() : null)).catch(() => null);
  // Nothing is requested that might not exist: the app's own route list says which optional routes are there,
  // and /api/health says which pages are served (its `pages` key; until it has one, no page is probed).
  if (!aux.routes || !aux.routes.has("/api/tools")) aux.routes = new Set(Object.keys(((await get("/openapi.json")) || {}).paths || {}));
  const has = (path) => aux.routes.has(path);
  const health = (await get("/api/health")) || {};
  const served = Array.isArray(health.pages) ? health.pages.map((x) => "/" + String(x).replace(/^\/|\/$/g, "") + "/") : null;
  aux.pages = Object.fromEntries(TABS.slice(2).map(([href, , router]) => [href, served ? served.includes(href) : (health.routers || []).includes(router) && KNOWN_PAGES.has(href)]));
  // the tools route runs live queries and can take seconds: it never holds up the rest
  if (has("/api/tools") && !aux.toolsBusy) {
    aux.toolsBusy = true;
    get("/api/tools").then((t) => { aux.toolsBusy = false; const first = !aux.tools && t; aux.tools = t || aux.tools; if (first && state) { last.quiet = true; render(); } });
  }
  if (has("/api/reviews") && state) {
    const id = theLine().line_id, got = await get("/api/reviews?line_id=" + encodeURIComponent(id));
    const list = Array.isArray(got) ? got : got && (got.candidates || got.reviews || got.rows);
    aux.reviews = { line: id, rows: Array.isArray(list) ? list : [], offer: (got && got.best_reviewed) || null };
  }
  const needCode = state && !(state.issuer_key && state.issuer_key.enrolled) && !state.seal.signed;
  const opt = (path, url) => (has(path) ? get(url || path) : null);
  aux.asks = has("/api/asks") ? await get("/api/asks") : null;
  if (params.get("replay") === "show") aux.embed = true;       // to look at the overlay before the graph page has its embed mode
  if (aux.embed === undefined && aux.pages["/graph/"]) {
    const text = (url) => fetch(url, { cache: "no-store" }).then((r) => (r.ok ? r.text() : "")).catch(() => "");
    const html = await text("/graph/"), scripts = [...html.matchAll(/<script[^>]+src="([^"]+)"/g)].map((m) => new URL(m[1], location.origin + "/graph/").pathname);
    aux.embed = /\bembed\b/.test(html) || (await Promise.all(scripts.map(text))).some((js) => /[?&'"]embed\b|get\(["']embed["']\)/.test(js));
  }
  const [egress, gate, enroll, trail, sheets] = await Promise.all([opt("/api/egress", "/api/egress?limit=5000"), opt("/api/gate/status"),
    needCode ? opt("/api/issuer/enroll-code") : null, opt("/api/trail"), opt("/api/sheets")]);
  const key = JSON.stringify([aux.pages, aux.embed, aux.reviews, aux.asks, egress && egress.summary, gate && [gate.arm, gate.value, gate.verdict, (gate.history || []).length], enroll, trail && trail.summary, sheets]);
  Object.assign(aux, { egress, gate, enroll, trail, sheets });
  if (key !== aux.key && state) {       // redraw quietly, and never in the middle of the opening motion
    aux.key = key;
    setTimeout(() => { last.quiet = true; render(); }, Math.max(0, introUntil - performance.now()));
  }
}
setInterval(() => { if (!document.hidden) loadAux(); }, 5000);
let live = false;
if (params.get("live") !== "0") {
  // One stream per visible tab. A browser allows six connections to one host; a hidden tab that keeps its
  // stream open starves the others, so the stream closes when the tab is hidden and reopens when it is shown.
  let events = null;
  const openStream = () => {
    if (events || document.hidden) return;
    events = new EventSource("/api/events");
    events.onopen = () => { live = true; };
    events.onmessage = () => load();
    events.onerror = () => { live = false; };
  };
  const closeStream = () => { if (events) { events.close(); events = null; live = false; } };
  document.addEventListener("visibilitychange", () => { if (document.hidden) closeStream(); else { openStream(); load(); } });
  addEventListener("pagehide", closeStream);
  openStream();
}
setInterval(() => { if (!live && !document.hidden) load(); }, 2000);
let resizeTimer = null;
addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => { if (state) { last.quiet = true; render(); } }, 150); });
addEventListener("wheel", (e) => { if (e.target.closest && e.target.closest("#rows")) ui.scrolled = true; }, { passive: true });
addEventListener("hashchange", () => { ui.drawer = null; ui.show = null; ui.open.clear(); render(); loadAux(); });

// ---------- the model of one item ----------
const theLine = () => state.lines.find((l) => l.line_id === location.hash.slice(1)) || state.lines[0];
const sheetLineOf = (line) => state.sheet.lines.find((l) => l.id === line.line_id);
const needsDelivery = () => /delivery/.test(state.sheet.pick_rule.id || "");
const priced = (line) => [...line.candidates].sort((a, b) => a.product.price_cents - b.product.price_cents || (a.id < b.id ? -1 : 1));
const firstFail = (c) => c.checks.findIndex((ch) => !ch.pass);
const boundOf = (limit) => (limit.bound.source === "issuer" ? limit.bound.value : (state.sheet.shopper_facts.find((f) => f.id === limit.bound.fact) || {}).value);

/** A limit in symbols, from the sheet and its current value: "Rough-in = 10 in", "Weight capacity ≥ 300 lb". */
function limitHead(limit) {
  const only = limit.terms.length === 1 && limit.terms[0].source === "store" ? words(limit.terms[0].figure) : null;
  const name = only && limit.name.trim().split(/\s+/).length > 2 ? only : limit.name;
  return { name: cap(name), rule: `${opSymbol(limit.op)} ${withUnit(g(boundOf(limit)), limit.unit)}` };
}

/** The page's own figure behind a check that is unclear: read, quoted, but not one clear value. */
function unsureFigure(c, ch) {
  const t = ch.terms.find((x) => x.owner === "store") || {}, name = ch.missing_figure || t.figure;
  return (c.figures || []).find((f) => f.figure === name && (f.unsure || ch.state === "unclear" || c.status === "unclear")) || null;
}
const isUnclear = (c, ch) => ch.state === "unclear" || (ch.state === "not_stated" && (/stated, but not clearly/.test(ch.missing_why || "") || !!unsureFigure(c, ch)));

/** Every value a page states for one figure, when it states several ("three sound levels: 75, 85 or 94 dB"). */
function severalOf(term) {
  const many = term && (term.values || term.stated_values || term.all_values || term.stated);
  if (!Array.isArray(many) || many.length < 2) return null;
  return many.map((v) => (typeof v === "object" && v ? v.value : v)).filter((v) => v != null);
}
const meets = (op, v, b) => (op === ">=" ? v >= b : op === "==" ? Math.abs(v - b) < 1e-9 : v <= b);

/** A cell for a figure with several stated values: all of them, the ones that fail the limit marked. */
function severalHtml(ch) {
  const many = severalOf(ch.terms.find((x) => x.owner === "store")), unit = ch.bound.unit;
  if (!many) return null;
  const parts = many.map((v) => (meets(ch.op, v, ch.bound.value) ? esc(g(v)) : `<b class="bad">${esc(g(v))}</b>`));
  const list = parts.length > 1 ? parts.slice(0, -1).join(", ") + " or " + parts[parts.length - 1] : parts[0];
  return unit && unit !== "count" ? `${list} ${esc(unit)}` : list;
}

/** What a cell shows for one check: the value the page states, as the page gives it. */
function statedText(ch, c) {
  const t = ch.terms.find((x) => x.owner === "store") || {}, unit = ch.bound.unit;
  const f = c && ch.lhs == null ? unsureFigure(c, ch) : null;
  if (f && !(t.values || t.stated_values)) {
    const u = f.unit || "no unit";
    return f.low != null && f.high != null && f.low !== f.high ? `${g(f.low)} or ${g(f.high)} ${u}` : f.value != null || f.low != null ? `${g(f.value ?? f.low)} ${u}` : "";
  }
  const many = severalOf(t);
  if (many) return withUnit(many.map(g).join(", ").replace(/, ([^,]*)$/, " or $1"), unit);
  if (ch.stated_text || t.stated_text) return ch.stated_text || t.stated_text;
  if (ch.terms.length === 1 && t.low != null && t.high != null && t.low !== t.high) return withUnit(`${g(t.low)}${t.kind === "adjustable" ? "–" : " / "}${g(t.high)}`, unit);
  return ch.lhs == null ? "" : withUnit(g(ch.lhs), unit);
}

/** Two to four plain words for a check that did not pass. */
function failWords(ch) {
  const unit = ch.bound.unit, b = g(ch.bound.value);
  if (ch.state === "not_stated") return `never states ${words(ch.missing_figure || ch.name)}`;
  if (ch.state === "unclear") return "unclear";
  if (ch.lhs == null) return "not clear";
  const has = withUnit(g(ch.lhs), unit);
  return ch.op === "==" ? `${has}, needs ${b}` : ch.op === ">=" ? `${has}, under ${b}` : `${has}, over ${b}`;
}

/** The row's result: the pick, a rejection with its reason, or one that passes but was not needed. */
function verdict(c, line, pick) {
  if (c.picked) return { kind: "pick", text: line.picked_by === "shopper" ? `chosen by ${state.sheet.shopper.name}` : "Recommended", why: c.picked_because || "" };
  if (c.status === "struck") {
    const st = c.strike || {}, before = st.remembered || st.from_memory || c.remembered || c.from_memory;
    return { kind: "no", text: before ? "struck before" : `struck by ${state.sheet.issuer.name}`, why: c.reason };
  }
  const i = firstFail(c);
  if (i < 0 && c.status === "inside") {
    if (pick && (!byPrice() || line.picked_by === "shopper" || c.product.price_cents >= pick.product.price_cents)) return { kind: "also", text: "also passes" };
    return { kind: "no", text: needsDelivery() && !(c.arrival && c.arrival.status === "stated") ? "no delivery time stated" : "passes" };
  }
  const ch = c.checks[Math.max(0, i)], reason = c.reason || "";
  // the three kinds are different things: outside a limit, stated but not clearly, not on the page at all
  if (c.status === "unclear" || isUnclear(c, ch)) {
    const f = unsureFigure(c, ch) || {}, why = ch.unclear_why || ch.missing_why || f.unsure_reason || (reason.includes(":") ? reason.slice(reason.indexOf(":") + 1).trim() : reason);
    const many = (ch.terms.find((x) => x.owner === "store") || {}).values;
    const short = f.quote && !f.unit ? "no unit stated" : (f.low != null && f.high != null && f.low !== f.high) || (many && many.length > 1) ? (many && many.length > 2 ? "several values" : "two values") : "";
    const reason1 = ch.unclear_why || short;      // the engine's own words when it gives them
    return { kind: "no unclear", text: "unclear", why, extra: reason1 ? "· " + reason1.replace(/; the page/, ", page").replace(/ and (?=[^,]*$)/, ", ") : "" };
  }
  if (/quote not found/.test(reason)) return { kind: "no", text: "quote not in the page", why: reason };
  return { kind: "no", text: failWords(ch), why: reason };
}

// ---------- render ----------
let wasTimer = null;
function render() {
  const line = theLine(), id = line.line_id, pick = pickOf(line);
  const opening = last.line !== id, pickId = pick ? pick.id : null;
  const before = opening || last.quiet ? null : snapshot();
  const justSigned = last.signed === false && !!state.seal.signed;
  if (!line.candidates.some((c) => c.id === ui.show)) ui.show = null;
  if (!opening && last.pick && pickId !== last.pick && !last.quiet) {
    const old = line.candidates.find((c) => c.id === last.pick);
    ui.was = old ? { id: old.id, price: money(old.product.price_cents), store: old.product.store } : null;
    clearTimeout(wasTimer);
    wasTimer = setTimeout(() => { ui.was = null; last.quiet = true; render(); }, 3200);
  }
  renderTop();
  renderSteps(line, pick);
  renderDoc(line);
  renderList(line, pick);
  renderSide(line, line.candidates.find((c) => c.id === ui.show) || pick);
  renderDrawer(line, pick);
  if (fx.MOTION && !last.quiet) {
    if (opening) intro();
    else moveChanges(before, last.pick, pickId);
    if (justSigned) signedMotion();
  }
  if (opening) ui.scrolled = false;
  if (opening || pickId !== last.pick || !ui.scrolled) q("#rows > .rowx.picked")?.scrollIntoView({ block: "nearest" });    // the recommended row is never cut by the fold
  rollChanges(!opening && !last.quiet);
  Object.assign(last, { line: id, pick: pickId, signed: !!state.seal.signed, quiet: false });
}

function renderTop() {
  const { sheet, seal } = state;
  const mode = [state.mode === "fixture" ? "fixture data" : state.mode === "replay" ? "replay of cached store data" : "", SIM ? "simulation" : ""].filter(Boolean);
  const real = state.mode === "fixture" ? "" : ", real stores";
  const at = seal.signed_at || (seal.signature && seal.signature.at);
  const time = at ? new Date(at).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }) : "";
  q("#top").innerHTML = `<span class="brand">Sign-Off</span>
    ${sheetMenu()}
    <nav class="tabs" aria-label="Views">${TABS.filter(([href]) => href === "/" || href === "/trail/" || aux.pages[href]).map(([href, label]) => `<a href="${href}"${href === "/" ? ' aria-current="page"' : ""}>${label}</a>`).join("")}</nav>
    <span class="meta">${[sheet.invented ? "invented people" + real : n_(state.lines.length, "item", "items"), ...mode].filter(Boolean).join(" · ")}</span>
    <span class="grow"></span>
    ${toolRows().length ? `<button class="toolsbtn" data-open="tools" aria-expanded="${ui.drawer === "tools"}">Tools at work</button>` : ""}
    ${aux.pages["/seal/"] ? `<a class="pill ${seal.signed ? "signed" : ""}" href="/seal/" title="The signature, on its own page">${seal.signed ? "Signed" : "Not signed"}</a>`
      : `<span class="pill ${seal.signed ? "signed" : ""}">${seal.signed ? "Signed" : "Not signed"}</span>`}
    <span class="total"><span class="tl">Total</span> <span data-k="total">${money(state.total_cents)}</span></span>`;
}

// ---------- the sheet switcher: the title is a small menu when the engine offers more than one sheet (laptop only) ----------
function sheetList() {
  const raw = aux.sheets, list = Array.isArray(raw) ? raw : raw && (raw.sheets || raw.items);
  if (!Array.isArray(list)) return [];
  return list.filter((x) => typeof x === "string" || x.show !== false).map((x) => (typeof x === "string" ? { id: x, title: x } : { id: x.id || x.sheet_id, title: x.title || x.id, sub: x.items != null ? `${x.items} items` : x.lines != null ? `${Array.isArray(x.lines) ? x.lines.length : x.lines} items` : "" })).filter((x) => x.id);
}
function sheetMenu() {
  const { sheet } = state, list = sheetList();
  if (list.length < 2) return `<span class="sheet">${esc(sheet.title)}</span>`;
  return `<span class="sheetmenu"><button class="sheet pickable" data-menu aria-haspopup="menu" aria-expanded="${!!ui.menu}" title="Switch the list">${esc(sheet.title)} <span class="caret">▾</span></button>
    ${ui.menu && ui.confirm ? `<span class="menu ask" role="alertdialog" aria-label="Switching starts a new run"><span class="q"><b>Switching starts a new run.</b> It clears ${esc(ui.confirm.atStake)}.</span>
      <span class="acts"><button class="btn" data-menu>Stay</button><button class="btn go" data-sheet="${esc(ui.confirm.id)}" data-sure="1">Switch</button></span></span>`
    : ui.menu ? `<span class="menu" role="menu">${list.map((x) => `<button role="menuitem" data-sheet="${esc(x.id)}" aria-current="${x.id === sheet.id}"><span>${esc(x.title)}</span>${x.sub ? `<small>${esc(x.sub)}</small>` : ""}</button>`).join("")}</span>` : ""}</span>`;
}
async function useSheet(id, confirmed) {
  if (id === state.sheet.id) { ui.menu = false; ui.confirm = null; last.quiet = true; return render(); }
  const atStake = state.seal.signed ? "the signature and its carts" : state.issuer_key && state.issuer_key.enrolled ? "the phone's enrolment" : "";
  if (atStake && !confirmed) { ui.confirm = { id, atStake }; last.quiet = true; return render(); }     // ask once, in the menu
  ui.menu = false; ui.confirm = null;
  try {
    const res = await fetch("/api/admin/use-sheet", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sheet_id: id, sheet: id, id }) });
    if (!res.ok) throw new Error(res.status);
    Object.assign(ui, { drawer: null, show: null, was: null });
    ui.open.clear();
    last.line = null;                                   // the new sheet opens like a first load
    history.replaceState(null, "", location.pathname + location.search);
    raw = "";
    await load();
    loadAux();
  } catch (error) {
    toast(q("[data-menu]") || q("#top"), `Could not switch the list <span class="code2">${esc(error.message)}</span>`);
    last.quiet = true;
    render();
  }
}

// ---------- tools at work: one row per tool, one real number each, from GET /api/tools (drawn only when the route exists) ----------
function toolRows() {
  const t = aux.tools, list = Array.isArray(t) ? t : t && (t.tools || t.items || t.rows);
  if (!Array.isArray(list)) return [];
  return list.map((x) => ({ name: x.tool || x.name || x.id || "", job: x.job || "", number: x.number ?? x.value ?? x.count ?? "", words: x.unit || x.words || x.label || "",
    route: x.source || x.route || "", detail: x.detail || x.note || "", basis: x.basis || "", ok: x.ok !== false })).filter((x) => x.name);
}
function toolsSheet() {
  const rows = toolRows();
  return `<h2>Tools at work</h2>
    ${rows.map((r, i) => `<button class="tool" data-toggle="tool:${i}" aria-expanded="${ui.open.has("tool:" + i)}">
      <span class="tn"><i class="tm ${r.ok ? "ok" : ""}"></i>${esc(r.name)}</span><span class="tv">${r.number !== "" ? `<b>${esc(r.number)}</b> ` : ""}${esc(r.words)}</span></button>
      ${ui.open.has("tool:" + i) ? `<p class="small tooldetail">${r.job ? `<b>${esc(r.job)}.</b> ` : ""}${esc(r.detail)}${r.basis ? ` <span class="faint">${esc(cap(r.basis))}.</span>` : ""}${r.route ? `<br><code>${esc(r.route)}</code>` : ""}</p>` : ""}`).join("")}
`;
}

// ---------- how the agent got here: the run replayed (the graph page, embedded), then back to the list ----------
function openReplay() {
  const el = q("#replay"), line = theLine();
  el.innerHTML = `<div class="rpanel"><div class="rhead"><span>How the agent got here · ${esc(cap(line.need))}</span><button class="btn" data-replay-close>Back to the list</button></div>
    <iframe title="The run, replayed" src="/graph/?embed=1&autoplay=1&line_id=${encodeURIComponent(line.line_id)}"></iframe></div>`;
  el.hidden = false;
  if (fx.MOTION) el.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 220, easing: "ease-out" });
  q("[data-replay-close]").focus();
}
function closeReplay() {
  const el = q("#replay");
  if (el.hidden) return;
  const done = () => {
    el.hidden = true; el.innerHTML = "";
    const pick = q("#rows > .rowx.picked");            // the list is there, with the pick highlighted
    if (pick) { pick.scrollIntoView({ block: "nearest" }); if (fx.MOTION) pick.animate([{ boxShadow: "0 0 0 0.375rem var(--accent-pale)" }, { boxShadow: "0 0 0 0 transparent" }], { duration: 900, easing: "ease-out" }); }
  };
  if (fx.MOTION) el.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 220, easing: "ease-in" }).finished.then(done, done); else done();
}
addEventListener("message", (e) => { if (e.origin === location.origin && e.data && e.data.type === "signoff:replay-done") closeReplay(); });

// ---------- the stepper: the run across the top. Every number is from the state ----------
function stepList(line, pick) {
  const { sheet, seal, counts } = state, o = state.order;
  const limits = o && o.limits_derived != null ? o.limits_derived : sheet.lines.reduce((n, l) => n + l.limits.filter((x) => x.from_order).length, 0);
  const pages = counts.products_found != null ? counts.products_found : state.lines.reduce((n, l) => n + l.candidates.length, 0);
  const at = seal.signed_at || (seal.signature && seal.signature.at);
  const time = at ? new Date(at).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }) : "";
  return [
    { id: "list_read", label: "List read", small: limits ? `${n_(limits, "limit", "limits")}, quoted` : "limits on the sheet", done: true },
    { id: "stores_searched", label: "Stores searched", small: n_(sheet.stores.length, "store", "stores"), done: pages > 0 },
    { id: "pages_read", label: "Pages read", small: n_(pages, "page", "pages"), done: pages > 0 },
    { id: "checked", label: "Checked", small: `${line.candidates.filter((c) => c.status !== "inside").length} rejected`, done: state.lines.some((l) => l.candidates.length > 0), k: "step.rej" },
    { id: "picked", label: "Picked", small: pick || state.total_cents ? `${n_(state.lines.filter((l) => l.pick).length, "item", "items")} · ${money(state.total_cents)}` : "nothing passes", done: !!pick, k: "step.pick" },
    { id: "signs", label: `${cap(sheet.issuer.role || "approver")} signs`, small: seal.signed ? `signed by ${sheet.issuer.name}` : "from the phone", done: !!seal.signed },
    { id: "carts", label: "Carts", small: seal.signed ? `${(seal.carts || []).length} created` : "none exist yet", done: !!seal.signed && (seal.carts || []).length > 0 },
  ];
}

function renderSteps(line, pick) {
  const steps = stepList(line, pick), current = state.seal.signed ? -1 : steps.findIndex((s) => !s.done);
  const replayBtn = aux.embed ? `<button class="replaybtn" data-replay title="How the agent got here: replay the run">▶ Replay the run</button>` : "";
  q("#steps").innerHTML = replayBtn + steps.map((s, i) => `<button class="step ${s.done ? "done" : "todo"}${i === current ? " now" : ""}${s.id === "signs" || s.id === "carts" ? " key" : ""}" data-open="step:${s.id}" ${i === current ? 'aria-current="step"' : ""}>
    <span class="n">${s.done ? "✓" : i + 1}</span><span class="t"><span class="l">${esc(s.label)}</span><small ${s.k ? `data-k="${s.k}"` : ""}>${esc(s.small)}</small></span></button>`).join("");
}

// ---------- left: the list, as a document someone wrote ----------
/** The requirement in the list's own words, with the deciding number marked. Without a quote, the sheet's own label. */
function requirement(limit) {
  const o = limit.from_order, b = boundOf(limit);
  const changed = o && o.matches === false && limit.bound.source === "issuer" ? ` <span class="tag">changed to ${esc(withUnit(g(b), limit.unit))} by ${esc(state.sheet.issuer.name)}</span>` : "";
  if (o && o.quote) {
    const value = o.value ?? (limit.bound.source === "issuer" ? b : null);
    if (value == null) return esc(o.quote) + changed;
    const [s, e] = figureSpan(o.quote, { value });
    return (s === 0 && e === o.quote.length ? esc(o.quote) : `${esc(o.quote.slice(0, s))}<mark>${esc(o.quote.slice(s, e))}</mark>${esc(o.quote.slice(e))}`) + changed;
  }
  return limit.bound.source === "shopper" ? `${esc(cap(limit.label || limit.name))}.` : `${esc(cap(limit.name))}: ${esc(limit.label || "")} <mark>${esc(withUnit(g(b), limit.unit))}</mark>.`;
}

function renderDoc(current) {
  const { issuer, shopper } = state.sheet;
  const home = (limit) => {                           // a requirement that points at the house carries the measurement beside it
    const f = limit.bound.source === "shopper" && state.sheet.shopper_facts.find((x) => x.id === limit.bound.fact);
    const who = f && f.suggested_from ? "" : f && f.remembered ? ` · ${shopper.name} measured` : "";      // where it came from is said once, under the item's title
    return f ? ` <span class="home" title="from the home: ${esc(f.label)}">(${g(f.value)} ${esc(f.unit)}${esc(who)})</span>` : "";
  };
  q("#doc").innerHTML = `<div class="cap">${esc(issuer.name)}'s limits</div>
    <div class="paper">${state.lines.map((l) => {
      const p = pickOf(l), sl = sheetLineOf(l);
      const right = p ? (l.status === "pick_up" ? "pick up" : money(p.product.price_cents) + times(l)) : "open";
      const seen = new Set();
      const text = sl.limits.map((limit) => requirement(limit) + home(limit)).filter((t) => !seen.has(t) && seen.add(t)).join(" ")
        + (sl.preferences || []).map((pref) => ` <span class="prefers"><span class="pl">prefers</span> ${requirement(pref)}</span>`).join("");
      return `<a class="it" href="#${l.line_id}" aria-current="${l.line_id === current.line_id}">
        <span class="stt" data-k="doc.${l.line_id}">${right}</span><h4>${esc(cap(l.need))}</h4><p>${text}</p></a>`;
    }).join("")}</div>
`;
}

// ---------- ordering, ratings, preferences (all optional: each part is drawn only when the state or its route carries it) ----------
const ruleId = () => (state.sheet.pick_rule && state.sheet.pick_rule.id) || "cheapest";
const byPrice = () => !Array.isArray(state.pick_rules) || /^cheapest/.test(ruleId());
/** What reviewers say of a product, from GET /api/reviews for this item (or the candidate itself): only what a page states. */
function ratingOf(c) {
  const list = aux.reviews && aux.reviews.line === c.order_line.id ? aux.reviews.rows : [];
  const rev = list.find((x) => x.candidate_id === c.id) || {}, eng = c.rating && typeof c.rating === "object" ? c.rating : null;
  const value = eng ? eng.rating ?? eng.value : rev.found === false ? null : rev.rating, sentence = rev.sentence || {}, first = (rev.sources || [])[0] || {};
  if (value == null && !sentence.quote) return null;
  // usable for ordering only when the engine carries it on the candidate, or the reviews route says it was used
  const used = !!eng || (rev.ordering && rev.ordering.used === true);
  return { value: value == null ? null : +value, outOf: (eng || rev).out_of ?? null, count: (eng || rev).review_count ?? c.review_count ?? null, source: rev.rating_site || sentence.site || "",
    used, reason: used ? "" : (rev.ordering && rev.ordering.reason) || "", quote: sentence.quote || "", url: sentence.url || first.url || "", site: sentence.site || first.site || "", matched: first.matched_by || "" };
}
/** "★ 4.6 (58 on parentgiving.com)": the count and the site only when the page gave them. */
const ratingText = (r) => (r.value == null ? "" : `★ ${+(+r.value).toFixed(1)}${r.outOf && +r.outOf !== 5 ? "/" + g(r.outOf) : ""}${r.count != null || r.source ? ` (${[r.count != null ? r.count : "", r.source ? "on " + r.source : ""].filter((x) => x !== "").join(" ")})` : ""}`);
const prefsMet = (c) => (c.preferences || []).filter((x) => x.status === "met");
/** The order of the rows under the active rule: the engine's own rank when it gives one, else price, or the rule's key among those that pass. */
function ordered(line) {
  const rows = priced(line);
  if (byPrice()) return rows;
  const pass = rows.filter((c) => c.status === "inside"), rest = rows.filter((c) => c.status !== "inside");
  const key = (c) => (c.rank != null ? c.rank : /review/.test(ruleId()) ? -((ratingOf(c) || {}).value || 0) : c.value_score != null ? -c.value_score : 0);
  pass.sort((a, b) => (b.picked ? 1 : 0) - (a.picked ? 1 : 0) || key(a) - key(b) || prefsMet(b).length - prefsMet(a).length || a.product.price_cents - b.product.price_cents);
  return [...pass, ...rest];
}
async function setRule(id, anchor) {
  if (id === ruleId() || state.seal.signed) return;
  try {
    const res = await fetch("/api/shopper/pick_rule", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id }) });
    const out = await res.json().catch(() => ({}));
    if (!res.ok || out.ok === false) throw new Error(out.detail || out.error || res.status);
    await load();
  } catch (error) { toast(anchor, `Not changed <span class="code2">${esc(error.message)}</span>`); }
}
async function choose(candidateId, anchor) {
  try {
    const res = await fetch("/api/shopper/choose", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ line_id: theLine().line_id, candidate_id: candidateId || null }) });
    const out = await res.json().catch(() => ({}));
    if (!res.ok || out.ok === false) throw new Error(out.detail || out.error || res.status);
    ui.show = null;
    await load();
  } catch (error) { toast(anchor, `Not chosen <span class="code2">${esc(clip(error.message, 60))}</span>`); }
}

/** Where a home measurement came from, when the state says (`suggested_from`): the sender's own label and the date, or that it was changed since. */
function fromMessage(f) {
  const m = f.suggested_from;
  if (!m) return "";
  const who = state.sheet.shopper.name, at = m.at ? new Date(m.at) : null;
  const date = at && !isNaN(at) ? ", " + at.toLocaleDateString("en-US", { month: "short", day: "numeric" }) : "";
  return m.matches === false ? ` · changed by ${who} since the message` : ` · from ${m.from_label || who + "'s message"}${date}`;
}

// ---------- centre: the candidates, cheapest first ----------
/** What a run of rejected rows holds, by which limit failed and how, with the extreme value: a summary of the rows themselves. */
function foldSummary(rows) {
  const groups = new Map();
  const add = (key, text, value, unit, far) => {
    const gr = groups.get(key) || { n: 0, text, unit, far, extreme: null };
    gr.n += 1;
    if (value != null) gr.extreme = gr.extreme == null ? value : far === "lowest" ? Math.min(gr.extreme, value) : far === "highest" ? Math.max(gr.extreme, value) : gr.extreme;
    groups.set(key, gr);
  };
  for (const c of rows) {
    if (c.status === "struck") { add("struck", "struck"); continue; }
    const ch = c.checks[Math.max(0, firstFail(c))];
    if (!ch) continue;
    const b = withUnit(g(ch.bound.value), ch.bound.unit);
    if (c.status === "unclear" || isUnclear(c, ch)) add("unclear", "unclear");
    else if (ch.state === "not_stated") add("none", "never state it");
    else if (ch.lhs == null) add("unclear", "unclear");
    else if (ch.op === ">=") add(ch.limit_id, `under ${b}`, ch.lhs, ch.bound.unit, "lowest");
    else if (ch.op === "<=") add(ch.limit_id, `over ${b}`, ch.lhs, ch.bound.unit, "highest");
    else add(ch.limit_id, `not ${b}`);
  }
  const order = [...groups.values()].sort((a, b) => (a.far ? 0 : 1) - (b.far ? 0 : 1) || b.n - a.n);
  return order.map((gr) => `${gr.n} ${gr.text === "never state it" && gr.n === 1 ? "never states it" : gr.text}${gr.far && gr.n > 1 && gr.extreme != null ? ` (${gr.far} ${withUnit(g(gr.extreme), gr.unit)})` : ""}`).join(" · ");
}

function rowHtml(c, line, pick, limits) {
  const v = verdict(c, line, pick), fail = c.status === "struck" ? -1 : firstFail(c);
  const cells = c.checks.map((ch, i) => {
    if (fail >= 0 && i > fail) return `<span class="cell skip">—</span>`;
    if (isUnclear(c, ch)) return `<span class="cell"><span class="chip unclear">${esc((statedText(ch, c) || "unclear").replace(/ no unit$/, " ?"))}</span></span>`;
    if (ch.state === "not_stated") return `<span class="cell"><span class="chip none">not stated</span></span>`;
    const several = severalHtml(ch);
    if (several) return `<span class="cell">${several}</span>`;
    return `<span class="cell ${ch.pass ? "" : "bad"}">${esc(statedText(ch))}</span>`;
  }).join("");
  const option = c.product.variant_title && !/^default/i.test(c.product.variant_title) ? `${c.product.variant_title} · ` : "";
  const img = c.product.image_url ? `<img src="${esc(c.product.image_url)}" alt="" loading="lazy" width="44" height="44" onerror="this.outerHTML='<span class=ph></span>'">` : `<span class="ph" aria-hidden="true"></span>`;
  const r = c.status === "inside" ? ratingOf(c) : null, met = c.status === "inside" ? prefsMet(c) : [];
  const extra = (r && r.value != null && r.used && !byPrice() ? `<small class="rate">${esc(ratingText(r))}</small>` : "")      // on a row only a rating the engine orders by + (met.length ? `<small class="tag pref" title="${esc(met.map((x) => x.label).join("; "))}">preferred</small>` : "");
  const result = v.kind === "pick" ? `<span class="res"><span class="pickd" title="${esc(v.why || "")}">✓ ${esc(v.text)}</span>${extra}</span>`
    : v.kind === "also" ? `<span class="res also">✓ ${esc(v.text)}${extra}${canChoose(line, c) ? `<span class="choosebtn" role="button" tabindex="0" data-choose="${esc(c.id)}">Choose this one</span>` : ""}</span>`
    : `<span class="res no" title="${esc(v.why || "")}">✕ ${esc(v.text)}${v.extra ? ` <span class="faint">${esc(v.extra)}</span>` : ""}</span>`;
  const was = ui.was && ui.was.id === c.id && !c.picked ? `<span class="was">was recommended</span>` : "";
  return `<button class="rowx ${c.picked ? "picked" : v.kind === "also" ? "also" : "rej"}${c.id === ui.show ? " shown" : ""}${was ? " waspick" : ""}" data-id="${esc(c.id)}" style="--n:${limits.length}">${was}
    ${img}<span class="nm"><b>${esc(c.product.title)}</b><i>${esc(option + c.product.store)}</i></span>
    <span class="pr">${money(c.product.price_cents)}${qty(line) > 1 ? `<small>${esc(times(line).trim())}</small>` : ""}</span>${cells}${result}</button>`;
}

function renderList(line, pick) {
  const limits = sheetLineOf(line).limits, ladder = byPrice(), rows = ordered(line), at = pick ? rows.indexOf(pick) : -1;
  const passing = rows.filter((c) => c.status === "inside"), failing = rows.filter((c) => c.status !== "inside");
  // price order: the rows before the pick, the pick, the dearer ones. Another rule: the pick first, the others that pass, then those that do not.
  const before = ladder ? (at >= 0 ? rows.slice(0, at) : rows) : [];
  const after = ladder ? (at >= 0 ? rows.slice(at + 1) : []) : passing.filter((c) => c !== pick);
  const rejectedBefore = before.filter((c) => c.status !== "inside").length, also = after.filter((c) => c.status === "inside").length;
  // as many rows as fit around the pick without scrolling (one to eight), the rest behind a fold line
  const rem = parseFloat(getComputedStyle(document.documentElement).fontSize), room = q("#list").clientHeight - (innerWidth < 1180 ? 13.5 : 9.2) * rem;
  const fit = Math.max(innerWidth < 1180 ? 0 : 1, Math.min(8, Math.floor((room - 5.4 * rem - 5.6 * rem) / (4.7 * rem))));
  let fold = before.length > fit && !ui.open.has("above") && at >= 0 ? before.length - fit : 0;
  // while the old pick says "was picked" it stays in view: if it sits in a folded part, it is shown beside the fold line
  const pinned = fold && ui.was ? before.slice(0, fold).filter((c) => c.id === ui.was.id) : [];
  if (pinned.length) fold += 1;
  // a limit is the approver's: read-only on the laptop. Where the route exists, the shopper can ask for a change.
  const canAsk = aux.routes && aux.routes.has("/api/shopper/ask-change") && !state.seal.signed && !FIXTURE;
  const owned = (limit) => {         // beside the limit's value: whose it is (the way to ask, where the route exists), or the ask's outcome
    if (limit.bound.source !== "issuer") return "";
    const ask = askFor(limit.id), name = esc(state.sheet.issuer.name), open = canAsk ? ` role="button" tabindex="0" data-open="ask:${esc(limit.id)}"` : "";
    return ask ? `<span class="askst${canAsk ? " ask" : ""}"${open} title="${esc(ask.text || "")}">${esc(ask.outcome || ask.status)}</span>`
      : `<span class="${canAsk ? "ask" : "own"}"${open} title="${name}'s limit: it changes only from ${name}'s phone, with a signature${canAsk ? ". Select to ask " + name + " for a change." : ""}">${name}'s limit</span>`;
  };
  const heads = limits.map((limit) => { const h = limitHead(limit); return `<span class="lh"><span class="ln">${esc(h.name)}</span><span class="lr"><b data-k="head.${limit.id}">${esc(h.rule)}</b>${owned(limit) ? `<span class="ow"> · ${owned(limit)}</span>` : ""}</span></span>`; }).join("");
  const rules = Array.isArray(state.pick_rules) && state.pick_rules.length > 1 ? state.pick_rules : null;
  const cut = (r) => cap(String(r.short || r.label || r.id).replace(/:.*$/, "").replace(/ (that|inside|among) .*$/, "").replace(/_/g, " "));
  const short = (r) => ((rules || []).filter((x) => cut(x) === cut(r)).length > 1 && r.id !== (rules || []).find((x) => cut(x) === cut(r)).id ? cap(String(r.id).replace(/_/g, " ").replace(/ time$/, "")) : cut(r));
  const shownRules = (rules || []).filter((r) => r.id === ruleId() || (rules || []).find((x) => cut(x) === cut(r)).id === r.id);
  const seg = rules ? `<div class="seg" role="group" aria-label="Order of the products that pass">${shownRules.map((r) => `<button data-rule="${esc(r.id)}" aria-pressed="${r.id === ruleId()}" ${state.seal.signed ? "disabled" : ""} title="${esc(r.label || "")}">${esc(short(r))}</button>`).join("")}</div>` : "";
  const lead = ladder ? "Cheapest first" : `${short((rules || []).find((r) => r.id === ruleId()) || { id: ruleId() })} first`;
  const sub = !rows.length ? "No page has been read for this item yet" : at < 0 ? `${lead}. ${rows.length} read · nothing passes`
    : ladder ? `${rows.length} read · <span data-k="sub.rej">${failing.length}</span> rejected · <span data-k="sub.pass">${passing.length}</span> ${passing.length === 1 ? "passes" : "pass"}`
    : `${lead}. ${rows.length} read · <span data-k="sub.pass">${passing.length}</span> ${passing.length === 1 ? "passes" : "pass"} · <span data-k="sub.fail">${failing.length}</span> ${failing.length === 1 ? "does" : "do"} not`;
  const keep = q("#rows") && last.line === line.line_id ? q("#rows").scrollTop : 0;      // a redraw never moves the list under the viewer
  const row = (c) => rowHtml(c, line, pick, limits), wasRows = (list) => list.filter((c) => ui.was && ui.was.id === c.id).map(row).join("");
  let body;
  if (ladder) {
    body = `${fold ? `<button class="more" data-toggle="above" title="Show these rows"><b>${fold - pinned.length} cheaper above:</b> ${esc(foldSummary(before.slice(0, fold).filter((c) => !pinned.includes(c))))}</button>` : ""}
      ${pinned.map(row).join("")}${before.slice(fold).map(row).join("")}
      ${pick ? row(pick) : (rows.length ? `<div class="more none">Nothing passes: ${esc(line.reason || "no product meets every limit")}</div>` : "")}
      ${(() => {
        if (!after.length) return "";
        const pass = after.filter((c) => c.status === "inside"), fail = after.filter((c) => c.status !== "inside");
        const failLine = fail.length ? (ui.open.has("belowfail") ? fail.map(row).join("")
          : `<button class="more" data-toggle="belowfail" title="Show these rows"><b>${fail.length} dearer ${fail.length === 1 ? "does" : "do"} not pass:</b> ${esc(foldSummary(fail))}</button>`) : "";
        if (!pass.length) return wasRows(after) + failLine;
        return ui.open.has("below") ? pass.map(row).join("") + `<button class="more ctl" data-toggle="below">Hide them</button>` + failLine
          : wasRows(after) + `<button class="more ctl" data-toggle="below"><b>${pass.length} more ${pass.length === 1 ? "passes" : "pass"}</b> · <u>show ${pass.length === 1 ? "it" : "them"}</u></button>` + failLine;
      })()}`;
  } else {
    const showN = ui.open.has("below") ? after.length : Math.max(0, fit - 1), hidden = after.slice(showN);
    body = `${pick ? row(pick) : `<div class="more none">Nothing passes: ${esc(line.reason || "no product meets every limit")}</div>`}
      ${after.slice(0, showN).map(row).join("")}${wasRows(hidden)}
      ${hidden.length ? `<button class="more" data-toggle="below">+ ${hidden.length} more ${hidden.length === 1 ? "passes" : "pass"}</button>` : ""}
      ${failing.length ? (ui.open.has("above") ? failing.map(row).join("") : wasRows(failing) + `<button class="more" data-toggle="above" title="Show these rows"><b>${failing.length} ${failing.length === 1 ? "does" : "do"} not pass:</b> ${esc(foldSummary(failing))}</button>`) : ""}`;
  }
  const facts = factsOfLine(sheetLineOf(line)), shopper = state.sheet.shopper;
  const homeLine = `<button class="homeline" data-open="shopper" title="${esc(facts.map((f) => (f.suggested_from && f.suggested_from.quote ? `“${f.suggested_from.quote}”` : "")).filter(Boolean).join(" ") || shopper.name + "'s measurements and questions to the agent")}"><b>${esc(shopper.name)}</b>${facts.length
    ? ` · the home: ${facts.map((f) => `${esc(f.short || f.label)} <span data-k="home.${f.id}">${g(f.value)} ${esc(f.unit)}</span>${esc(fromMessage(f))}`).join(" · ")}` : " · no measurement needed"}</button>`;
  q("#list").innerHTML = `<div class="lhd"><div class="lht"><h1>${esc(cap(line.need))}</h1>${seg}</div><p class="sub">${sub}</p>${homeLine}</div>
    <div class="hd" style="--n:${limits.length}"><span></span><span>Product</span><span>Price</span>${heads}<span>Result</span></div>
    <div class="rows" id="rows">${body}</div>`;
  q("#rows").dataset.fit = `${fit} rows for ${Math.round(room)} px at ${rem} px`;      // for checking the fold at a given size
  q("#rows").scrollTop = keep;
}

// ---------- right: why this one, in the list's words and the store's words ----------
/** The part of a sentence around its figure, the figure marked and never cut off. */
function fragment(quote, term, before = 110, after = 110) {
  const text = quote || "";
  const [s, e] = figureSpan(text, term);
  if (s === 0 && e === text.length) return esc(clip(text, before + after + 40));
  let from = Math.max(0, s - before);
  if (from > 0) from = text.indexOf(" ", from) + 1 || from;
  let to = Math.min(text.length, e + after);
  if (to < text.length) to = Math.max(e, text.lastIndexOf(" ", to));
  return `${from > 0 ? "…" : ""}${esc(text.slice(from, s).replace(/^[\s•\-:,;]+/, ""))}<mark>${esc(text.slice(s, e))}</mark>${esc(text.slice(e, to))}${to < text.length ? "…" : ""}`;
}

/** What the state can show for one figure being the right number: two or three marks with two-word labels. Nothing is claimed that the state does not carry. */
function guards(c, ch, t) {
  const fig = (c.figures || []).find((f) => f.figure === t.figure && f.quote === t.quote) || (c.figures || []).find((f) => f.figure === t.figure) || {};
  const readers = t.readers || ch.readers || fig.readers;
  const names = Array.isArray(readers) && readers.length ? readers.filter((r) => r && r.agrees !== false && (r.value == null || t.value == null || +r.value === +t.value)).map((r) => r.extractor || r.reader || String(r))
    : Array.isArray(fig.agreed_by) ? fig.agreed_by : [];
  // one plain line: the quote is in the page (a figure counts only then), and how many models read the same number
  return `<div class="guards" title="${esc(names.join(", "))}"><span class="tickmark">✓</span> quoted from the page${names.length >= 2 ? ` · ${names.length} models agree` : ""}</div>`;
}
const optionOf = (c) => (c.product.variant_title && !/^default/i.test(c.product.variant_title) ? c.product.variant_title : "");

function pairHtml(ch, limit, c) {
  const order = limit && limit.from_order, t = ch.terms.find((x) => x.owner === "store") || {};
  const ok = ch.pass, word = ch.op === "==" ? "matches" : ch.op === "<=" ? "within" : "enough";
  const src = (label, html) => `<div class="kv"><span class="k">${label}</span><span class="qt">${html}</span></div>`;      // who says it, then the words
  const homeRow = (part) => src(esc(state.sheet.shopper.name), `${esc(part.label)} <mark>${g(part.value)} ${esc(part.unit)}</mark>`);
  const head = limit ? limitHead(limit) : { name: cap(ch.name), rule: "" };
  let store;
  const f = unsureFigure(c, ch);
  if (isUnclear(c, ch)) {
    const quote = (f && f.quote) || t.quote, why = ch.unclear_why || ch.missing_why || (f && f.unsure_reason) || "";
    store = src("the store", quote ? fragment(quote, f || t) : `<span class="chip unclear">${esc(statedText(ch, c) || "unclear")}</span>`)
      + (why ? src("why", esc(why.replace(/^stated, but not clearly[^:]*:\s*/, ""))) : "");
  } else if (ch.state === "not_stated") store = src("the store", `<span class="chip none">not stated on the page</span>`);
  else store = t.quote ? src(`<span title="${esc(optionOf(c) ? "option: " + optionOf(c) : "")}">the store</span>`, fragment(t.quote, t)) + (ch.pass ? guards(c, ch, t) : "") : "";
  return `<div class="pair" data-open="${esc(c.id)}">
    <div class="ph2"><span>${esc(head.name)} <span class="faint">${esc(head.rule)}</span></span><span class="${ok ? "okw" : isUnclear(c, ch) || ch.state === "not_stated" ? "greyw" : "badw"}">${ok ? "✓ " + word : "✕ " + esc(isUnclear(c, ch) ? "unclear" : failWords(ch))}</span></div>
    ${order && order.quote ? src(esc(state.sheet.issuer.name), fragment(order.quote, { value: order.value ?? (ch.bound.owner === "issuer" ? ch.bound.value : undefined) }) + orderTags(order, ch)) : ""}
    ${ch.bound.owner === "shopper" ? homeRow(ch.bound) : ""}${ch.terms.filter((x) => x.owner === "shopper").map(homeRow).join("")}
    ${store}</div>`;
}

const canChoose = (line, c) => !c.picked && c.status === "inside" && !state.seal.signed && !FIXTURE && aux.routes && aux.routes.has("/api/shopper/choose");
/** Under the limits: the preferences this product meets, and what its reviews say (the quote and its link). */
function extrasHtml(c) {
  const met = prefsMet(c), r = ratingOf(c);
  return (met.length ? `<div class="pair"><div class="ph2"><span>Preferred</span><span class="okw">✓ ${n_(met.length, "preference", "preferences")} met</span></div>${met.map((x) => `<div class="qt">${esc(x.label)}</div>`).join("")}</div>` : "")
    + (r ? `<div class="pair"><div class="ph2"><span>Reviewers say</span><span class="greyw">${esc(ratingText(r))}</span></div>
        ${r.value != null && !r.used ? `<div class="k">${esc(r.reason || "not used for ordering")}</div>` : ""}
        ${r.quote ? `<div class="qt">“${esc(r.quote)}”</div>` : ""}
        ${r.url ? `<div class="k"><a class="link" href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.site || "the page")} ↗</a>${r.matched ? ` · matched by ${esc(clip(r.matched, 70))}` : ""}</div>` : ""}</div>` : "");
}

/** Small quiet tags beside the list's sentence: the document's version at Senso, and whether the limit was changed since. */
function orderTags(order, ch) {
  const senso = (Array.isArray(state.senso) ? state.senso : []).find((r) => r && r.limit_id === ch.limit_id && (r.version_id || r.content_id)) || {};
  const id = order.version_id || order.content_id || senso.version_id || senso.content_id;
  return (order.matches === false ? ` <span class="tag">changed to ${esc(withUnit(g(ch.bound.value), ch.bound.unit))} by ${esc(state.sheet.issuer.name)}</span>` : "") + (id ? ` <span class="tag" title="Senso ${esc(id)}">Senso ${esc(String(id).slice(0, 8))}</span>` : "");
}

function renderSide(line, c) {
  const limits = sheetLineOf(line).limits;
  let card;
  if (c) {
    const fail = c.status === "struck" ? -1 : firstFail(c), shown = fail >= 0 ? c.checks.slice(0, fail + 1) : c.checks;
    const option = c.product.variant_title && !/^default/i.test(c.product.variant_title) ? `${c.product.variant_title} · ` : "";
    const a = c.arrival, u = c.undo, scope = (x) => (x && x.scope ? ` <span class="faint">(${esc(x.scope)})</span>` : "");
    const agent = c.picked && ((a && a.quote) || (u && u.quote)) ? `<div class="pair agent" data-open="${esc(c.id)}"><div class="ph2"><span>The store's agent states</span></div>
        ${a && a.quote ? `<div class="kv"><span class="k">delivery</span><span class="qt">“${esc(a.quote)}”</span></div>` : ""}
        ${u && u.quote ? `<div class="kv"><span class="k">returns</span><span class="qt">“${esc(u.quote)}”</span></div>` : ""}</div>` : "";
    card = `<section class="card why"><div class="cap">${c.picked ? (line.picked_by === "shopper" ? `Chosen by ${esc(state.sheet.shopper.name)}` : "Recommended") : c.status === "inside" ? "Passes, not recommended" : "Why not this one"}${c.picked && ui.was && ui.was.store !== c.product.store ? ` <span class="nowat">now at ${esc(c.product.store)}</span>` : ""}</div>
      <h2 title="${esc(c.product.title)}">${esc(c.product.title)}</h2>
      <div class="meta2">${esc(option + c.product.store)} · <span data-k="why.price">${money(c.product.price_cents)}</span>${qty(line) > 1 ? `${esc(times(line))} = ${money(c.product.price_cents * qty(line))}` : ""} · <a class="link" href="${esc(c.product.url)}" target="_blank" rel="noopener" title="The store's page">page ↗</a></div>
      ${c.picked && c.picked_because && line.picked_by !== "shopper" ? `<div class="because">${esc(cap(c.picked_because))}</div>` : ""}
      ${c.status === "struck" ? `<div class="pair"><div class="ph2"><span>Struck by ${esc(state.sheet.issuer.name)}</span></div><div class="qt">“${esc(c.reason || "")}”</div></div>` : ""}
      ${shown.map((ch) => pairHtml(ch, limits.find((l) => l.id === ch.limit_id), c)).join("")}${agent}${ui.show === c.id || !byPrice() || prefsMet(c).length ? extrasHtml(c) : ""}
      ${canChoose(line, c) ? `<button class="btn choose" data-choose="${esc(c.id)}">Choose this one</button>` : ""}
      ${c.picked && line.picked_by === "shopper" && !state.seal.signed && aux.routes && aux.routes.has("/api/shopper/choose") ? `<button class="link" data-choose="">Back to the recommended one</button>` : ""}
      ${!c.picked && pickOf(line) ? `<button class="link" data-show="">Back to the recommended one</button>` : ""}</section>`;
  } else {
    card = `<section class="card why"><div class="cap">Why this one</div><h2>${line.candidates.length ? "Nothing passes" : "Nothing to show yet"}</h2><div class="muted">${line.candidates.length ? esc(cap(line.reason || "no product meets every limit")) + ". Select a row to read why." : "No page has been read for this item."}</div></section>`;
  }
  q("#side").innerHTML = card + signatureHtml();
}

/** The receipt chain, when the engine reports it: one tick per receipt and the count, on one line. */
function receiptsRow() {
  const r = state.receipts;
  if (!r || !r.count) return "";
  const good = typeof r.verified === "number" ? r.verified : r.verified ? r.count : (r.first_bad ? r.first_bad - 1 : 0), all = good === r.count;
  return `<div class="rcpt muted small" title="Tamper-evident: each receipt carries the hash of the one before"><span class="${all ? "tickmark" : "badw"}">${all ? "✓" : "✕"}</span> ${all ? `${n_(r.count, "receipt", "receipts")} verified` : `${good} of ${r.count} receipts verified`}</div>`;
}

/** The phone link as a code to scan (the vendored qrcode-generator), or nothing if the library is missing. */
function qrSvg(text) {
  try {
    const code = window.qrcode(0, "M");
    code.addData(text);
    code.make();
    return code.createSvgTag({ cellSize: 4, margin: 0, scalable: true });
  } catch (error) {
    return "";
  }
}

/** What the signature covers, counted from the state: the limits, the quotes, the picks and the total. */
function whatIsSigned() {
  const limits = state.sheet.lines.reduce((n, l) => n + l.limits.length, 0);
  const picks = state.lines.filter((l) => l.pick && l.status !== "pick_up").length;
  return `${n_(limits, "limit", "limits")} · ${n_(picks, "pick", "picks")} · <span data-k="sig.total">${money(state.total_cents)}</span>`;
}

function signatureHtml() {
  const { sheet, seal } = state, name = esc(sheet.issuer.name);
  if (!seal.signed) {
    const en = aux.enroll, enrolled = state.issuer_key && state.issuer_key.enrolled;
    const link = en && (en.url || en.link || en.phone_url || en.phone), qr = !enrolled && link ? qrSvg(link) : "";
    const pending = ((aux.asks && aux.asks.asks) || []).filter((x) => x.status === "pending").length;
    // one place says what happens next, in plain words
    const next = enrolled ? `<b>Waiting for ${name} to sign</b> · this sheet is on ${name}'s phone now` : `<b>Next:</b> ${name} reviews and signs on the phone`;
    return `<section class="card sign"><div class="cap">What happens next</div>
      <div class="enrol">${qr && en && en.code ? `<a class="qr" href="${esc(link)}" target="_blank" rel="noopener" aria-label="Open the phone page" title="Scan to open ${name}'s page on a phone · code ${esc(en.code)}">${qr}</a>` : ""}
        <div><div class="next">${next}</div>${pending ? `<div class="muted small">You asked ${name} about ${n_(pending, "limit", "limits")}</div>` : ""}
        ${!enrolled && en && en.code ? `<div class="muted small">Scan to open it · code <span class="code">${esc(en.code)}</span></div>` : ""}</div></div>
      <div class="signs"><b>${name} signs</b> ${whatIsSigned()}</div>
      <div class="muted small">No cart exists until then</div>
      ${receiptsRow()}</section>`;
  }
  const sig = seal.signature || {}, persona = sig.persona || (state.issuer_key && state.issuer_key.persona) || {};
  const who = (sig.signer && sig.signer.name) || String(seal.signer || sheet.issuer.name).replace(/\s*\(.*\)\s*$/, ""), hash = seal.sheet_hash || sig.sheet_hash || "";
  // how the signer is known, from the state: the server's own label when it gives one, else from the identity check
  const identity = persona.verified ? persona.label || "identity checked (sandbox)" : sig.name_basis || seal.signer_label || seal.identity || sig.identity || "self-declared";
  const differs = (c) => c.signed_total_cents != null && c.total_cents != null && c.signed_total_cents !== c.total_cents;
  const carts = seal.carts || [];
  // the carts are the action once signed: the most visible thing on the page
  return `<section class="card sign signed"><div class="cap">What happens next</div>
    <div class="next part"><span class="tickmark">✓</span> <b>Signed by ${esc(who)}.</b> ${carts.length ? `Your ${carts.length === 1 ? "cart is" : "carts are"} ready:` : "No cart link came back."}</div>
    ${carts.map((c) => `<a class="cartbtn part" href="${esc(c.cart_url)}" target="_blank" rel="noopener"><span>${esc(c.store)} cart</span><span>${c.total_cents ? money(c.total_cents) + " " : ""}→</span></a>${differs(c) ? `<div class="badw small part">store total differs · signed ${money(c.signed_total_cents)} · store ${money(c.total_cents)}</div>` : ""}`).join("")}
    ${carts.length ? `<div class="muted small part">You check out yourself; Sign-Off never pays.</div>` : ""}
    <div class="row part muted small"><span>${esc(identity)}</span>${hash ? `<span>code <code class="fp" title="${esc(hash)}">${esc(hash.slice(0, 12).replace(/(.{4})(?=.)/g, "$1 "))}</code></span>` : ""}</div>
    ${receiptsRow()}</section>`;
}

// ---------- the side sheet: everything longer than a label ----------
function factsOfLine(sheetLine) {
  const ids = new Set();
  for (const limit of sheetLine.limits) {
    for (const t of limit.terms) if (t.source === "shopper") ids.add(t.fact);
    if (limit.bound.source === "shopper") ids.add(limit.bound.fact);
  }
  return state.sheet.shopper_facts.filter((f) => ids.has(f.id));
}
const slider = (kind, id, label, value, unit, b) => `<label class="field"><span>${esc(cap(label))}</span><output>${g(value)} ${esc(unit)}</output>
  <input type="range" data-kind="${kind}" data-id="${esc(id)}" data-unit="${esc(unit)}" min="${b.min}" max="${b.max}" step="${b.step}" value="${value}"></label>`;
const chatHtml = (t) => `<p class="said">“${esc(t.text)}”</p><p>${t.refused ? '<span class="refused">Refused</span> ' : ""}${esc(t.reply)}</p>`;
const closeBtn = `<button class="x" data-close>Close</button>`;

/** The shopper's sheet: the home's measurements for this item and the chat with the agent. In ?sim=1 also the limits. */
function shopperSheet(el, line) {
  if (el.dataset.for === "shopper:" + line.line_id && el.contains(document.activeElement) && document.activeElement !== document.body) {
    for (const input of el.querySelectorAll("input[type=range]")) {     // keep the control in use; refresh the readouts
      const f = state.sheet.shopper_facts.find((x) => x.id === input.dataset.id);
      if (f && input.dataset.kind === "fact") input.previousElementSibling.textContent = `${g(f.value)} ${f.unit}`;
    }
    return;
  }
  el.dataset.for = "shopper:" + line.line_id;
  const sheetLine = sheetLineOf(line), shopper = state.sheet.shopper, facts = factsOfLine(sheetLine), turn = ui.chat[ui.chat.length - 1];
  el.innerHTML = `${closeBtn}<h2>${esc(shopper.name)}</h2><p>${esc(cap(shopper.role_label || ""))}</p>
    ${facts.length ? `<h3>From the home</h3>` + facts.map((f) => slider("fact", f.id, f.label, f.value, f.unit, f) + (f.suggested_from && f.suggested_from.quote ? `<p class="small">“${esc(f.suggested_from.quote)}”${esc(fromMessage(f))}</p>` : "")).join("") : ""}
    ${SIM ? `<h3>Simulation only, not ${esc(state.sheet.issuer.name)}'s phone</h3>` + sheetLine.limits.filter((l) => l.bound.source === "issuer").map((l) => slider("limit", l.id, l.label, l.bound.value, l.unit, l.bound)).join("") : ""}
    <form id="say"><input id="sayText" name="say" type="text" autocomplete="off" aria-label="Message to the agent" placeholder="Ask about this item…"><button class="btn" type="submit">Send</button></form>
    <div id="reply" aria-live="polite">${turn ? chatHtml(turn) : ""}</div>`;
}

const CLASS_ROWS = [["limit", "limits"], ["home_measurement", "home measurements"], ["person", "people"], ["order", "the list"], ["store_text", "store text"], ["product", "products"], ["price", "prices"]];
function egressHtml() {
  if (!aux.egress) return "";
  const { rows, summary } = aux.egress;
  const group = (row) => (row.kind === "store" ? "stores" : row.kind === "model" ? "reading model" : row.recipient);
  const cols = [...new Set(rows.map(group))].sort((a, b) => (a === "stores" ? -1 : b === "stores" ? 1 : a === "reading model" ? -1 : b === "reading model" ? 1 : a.localeCompare(b)));
  const has = (col, cls) => rows.some((row) => group(row) === col && (row.fact_classes || []).includes(cls));
  const kinds = CLASS_ROWS.filter(([cls]) => cols.some((c) => has(c, cls)));
  return `<h3>Sent out</h3><p><b>${summary.limits_in_store_messages} limits in ${summary.to_stores} ${summary.to_stores === 1 ? "message" : "messages"} to stores.</b> ${summary.messages} ${summary.messages === 1 ? "message" : "messages"} left this machine in all. Limits are compared locally; no store is told a limit.</p>
    ${cols.length && kinds.length ? `<table class="grid"><tr><th></th>${cols.map((c) => `<th><span>${esc(c)}</span></th>`).join("")}</tr>
      ${kinds.map(([cls, label]) => `<tr><td>${label}</td>${cols.map((c) => `<td>${has(c, cls) ? '<i class="gd"></i>' : ""}</td>`).join("")}</tr>`).join("")}
      <tr class="count"><td>messages</td>${cols.map((c) => `<td>${rows.filter((row) => group(row) === c).length}</td>`).join("")}</tr></table>
      <p class="small">A dot: that kind of fact was in at least one message. Checked by code on every payload.</p>` : ""}`;
}
function readerHtml() {
  const gate = aux.gate;
  if (!gate || !gate.arm) return "";
  const arms = (gate.outcome && gate.outcome.arms) || {}, reference = gate.arm === "sonnet" || gate.value === false;
  const back = reference && (gate.history || []).some((h) => h.value === true || (h.arm && h.arm !== "sonnet"));
  return `<h3>Reader</h3><p><b>${reference ? "Reference reader" : "Small model"} decides now${back ? " · the small model was switched back" : ""}.</b></p>
    ${Object.entries(arms).map(([k, a]) => `<p>${esc(a.reader || k)}: ${a.same_as_reference} of ${a.figures_counted} figures agree with the reference, ${a.seconds_per_product_median} s a page.</p>`).join("")}
    <p class="small">${esc((gate.outcome && gate.outcome.note) || "")}</p>`;
}
/** The Trail's own records for one step (GET /api/trail), one line each; record-keeping messages are left to the Trail page. */
function trailRows(id) {
  const t = aux.trail;
  if (!t || !Array.isArray(t.events)) return "";
  const rows = t.events.filter((e) => e.step === id && e.own_step !== false);
  if (!rows.length) return "";
  const time = (e) => (e.at ? String(e.at).slice(11, 19) : "");
  return `<h3>Records of this step</h3>${rows.slice(0, 10).map((e) => `<p class="rec"><span>${e.stopped ? '<b class="badw">refused</b> ' : ""}${esc(e.label || e.kind || "")}${e.detail ? ` <span class="muted">${esc(clip(e.detail, 34))}</span>` : ""}</span></p>`).join("")}
    <p class="small">${rows.length > 10 ? `${rows.length - 10} more. ` : ""}<a class="link" href="/trail/#${esc(id)}">Open on the Trail</a></p>`;
}

/** One step of the run: what the state holds for it. */
function stepSheet(id, line, pick) {
  const { sheet, counts } = state, o = state.order || {};
  const perStore = (list) => sheet.stores.map((s) => `<p class="rec">${esc(s)} <span class="muted">${list.filter((c) => c.product.store === s).length} pages for this item</span></p>`).join("");
  if (id === "list_read") {
    const all = sheet.lines.flatMap((l) => l.limits.filter((x) => x.from_order && x.from_order.quote).map((x) => ({ l, x })));
    return `<h2>${esc(o.title || sheet.issuer.name + "'s list")}</h2>
      ${o.limits_derived != null ? `<p><b>${o.limits_matching} of ${n_(o.limits_derived, "limit", "limits")}</b> read from the list ${o.limits_derived === 1 ? "matches" : "match"} the sheet.</p>` : ""}
      ${all.map(({ l, x }) => `<h3>${esc(cap(l.need))} · ${esc(x.name)}${x.from_order.matches === false ? " · changed from the list" : ""}</h3><p>“${fragment(x.from_order.quote, { value: x.from_order.value ?? undefined }, 400, 400)}”</p>`).join("")}${trailRows(id)}`;
  }
  if (id === "stores_searched") return `<h2>Stores searched</h2>${perStore(line.candidates)}${egressHtml()}${trailRows(id)}`;
  if (id === "pages_read") {
    const scan = state.instruction_scan;
    return `<h2>Pages read</h2><p><b>${counts.products_found} pages</b> across the sheet, ${line.candidates.length} for this item.</p>
      ${scan ? `<h3>Instructions to an agent</h3><p><b>${scan.pages_scanned} pages scanned, ${scan.instructions_found} found.</b></p>${(scan.examples || []).map((x) => `<p>“${esc(x.quote || x)}”</p>`).join("")}` : ""}
      ${readerHtml()}${trailRows(id)}`;
  }
  if (id === "checked") {
    const n = (s) => line.candidates.filter((c) => c.status === s).length, sa = counts.store_agent;
    return `<h2>Checked, cheapest first</h2><p>For this item: <b>${n("inside")}</b> pass every limit, <b>${n("outside")}</b> are outside a limit, <b>${n("unclear")}</b> state the figure unclearly, <b>${n("not_stated")}</b> do not state it${n("struck") ? `, <b>${n("struck")}</b> struck` : ""}.</p>
      <p>Each row's reason is its own; select a row to read the sentence behind it.</p>
      ${sa && sa.questions ? `<h3>The store's agent</h3><p>${sa.delivery_time_stated} of ${sa.about_delivery_and_returns} questions on delivery and returns came back with a delivery time. It is asked about delivery and returns only.</p>` : ""}${trailRows(id)}`;
  }
  if (id === "picked") return null;      // the pick's own sheet
  if (id === "signs") return `<h2>${esc(cap(sheet.issuer.role || "approver"))} signs</h2><p>${state.seal.signed ? "Signed." : `${esc(sheet.issuer.name)} signs on a phone that holds the only key. No cart exists until then.`}</p>
      ${state.receipts ? `<h3>Receipts</h3>${receiptsRow()}<p class="small">Every signed request, accepted or refused, leaves a receipt that carries the hash of the one before.</p>` : ""}${trailRows(id)}`;
  if (id === "carts") return `<h2>Carts</h2>${(state.seal.carts || []).map((c) => `<p class="rec"><a class="link" href="${esc(c.cart_url)}" target="_blank" rel="noopener">${esc(c.store)} cart ↗</a> ${c.total_cents ? money(c.total_cents) : ""}</p>`).join("") || "<p>None exist yet. A cart is created only after a verified signature on this exact sheet. Nothing is checked out or paid.</p>"}${trailRows(id)}`;
  return null;
}

/** One product: its figures in the page's own words, the store agent's replies, the method. */
function productSheet(c) {
  const seen = new Set(), quotes = [];
  for (const ch of c.checks) for (const t of ch.terms) {
    if (t.owner !== "store" || !t.quote || seen.has(t.figure)) continue;
    seen.add(t.figure);
    const text = t.sentence || t.quote, off = t.sentence ? Math.max(0, t.sentence.indexOf(t.quote)) : 0;
    const [s, e] = figureSpan(t.quote, t).map((v) => v + off);
    quotes.push(`<h3>${esc(cap(words(t.figure)))} · the store states${optionOf(c) ? ` · option: ${esc(optionOf(c))}` : ""}</h3><p>“${esc(t.quote.slice(0, s - off))}<mark>${esc(t.quote.slice(s - off, e - off))}</mark>${esc(t.quote.slice(e - off))}”</p>${ch.pass ? guards(c, ch, t) : ""}
      ${text !== t.quote ? `<p class="small">Around it on the page: “${esc(clip(text, 220))}”</p>` : ""}`);
  }
  for (const f of c.figures || []) {
    if (!f.unsure || !f.quote || seen.has(f.figure)) continue;
    seen.add(f.figure);
    quotes.push(`<h3>${esc(cap(words(f.figure)))} · the store states, unclear</h3><p>“${fragment(f.quote, f, 400, 400)}”</p><p>${esc(f.unsure_reason || "")}</p>`);
  }
  const v = verdict(c, theLine(), pickOf(theLine()));
  return `<h2>${esc(c.product.title)}</h2>
    <p>${money(c.product.price_cents)} · ${esc(c.product.store)} · <a class="link" href="${esc(c.product.url)}" target="_blank" rel="noopener">store page ↗</a></p>
    <p><b>${c.picked ? "The pick" : esc(cap(v.text))}</b>${v.why ? ` · ${esc(v.why)}` : ""}</p>
    ${quotes.join("")}
    ${c.arrival && c.arrival.quote ? `<h3>Delivery · the store's agent said, not guaranteed</h3><p>“${esc(c.arrival.quote)}”</p>` : ""}
    ${c.undo && c.undo.quote ? `<h3>Returns · the store's agent said</h3><p>“${esc(c.undo.quote)}”</p>` : ""}
    ${(c.asked || []).map((a) => `<h3>Asked the store's agent</h3><p><b>${esc(a.question || "")}</b></p><p>“${esc(a.reply || "")}”</p>`).join("")}`;
}

function renderDrawer(line, pick) {
  const el = q("#drawer"), d = ui.drawer;
  if (d === "shopper") { el.hidden = false; return shopperSheet(el, line); }
  el.dataset.for = "";
  let html = null;
  if (d === "tools") html = toolRows().length ? toolsSheet() : null;
  if (d && d.startsWith("ask:")) { if (el.dataset.for === d && !el.hidden) return; html = askSheet(d.slice(4), line); el.dataset.for = d; el.hidden = !html; if (html) el.innerHTML = closeBtn + html; return; }
  if (d && d.startsWith("step:")) html = stepSheet(d.slice(5), line, pick);
  const c = d === "pick" || d === "step:picked" ? pick : line.candidates.find((x) => x.id === d);
  if (!html && c) html = productSheet(c);
  if (!html && d === "step:picked") html = `<h2>Picked</h2><p>Nothing passes for this item, so nothing is proposed.</p>`;
  el.hidden = !html;
  if (html) el.innerHTML = closeBtn + html;
}

// ---------- motion ----------
/** Opening an item: the rows are checked from the cheapest down, one after another; at the first that passes the highlight lands. */
function intro() {
  const rows = [...document.querySelectorAll("#rows > .rowx, #rows > .more")];
  if (!rows.length) return;
  const stepMs = Math.min(150, 1900 / rows.length);
  let t = 150;
  for (const row of rows) {
    if (row.classList.contains("more")) { fx.appear(row, t, 240); t += 60; continue; }
    const picked = row.classList.contains("picked");
    // the product is there from the start; its cells fill, the failing one marks, the reason appears, the row settles to grey
    row.animate([{ opacity: 0.35 }, { opacity: 1 }], { duration: 160, delay: t, fill: "backwards" });
    row.querySelectorAll(".cell").forEach((cell, i) => fx.appear(cell, t + i * 45, 160));
    fx.appear(row.querySelector(".res"), t + 110, 200);
    if (picked) row.animate([{ borderColor: "transparent", backgroundColor: "transparent" }, {}], { duration: 320, delay: t + 80, easing: fx.EASE, fill: "backwards" });
    else row.querySelectorAll(".nm, .pr, img, .ph").forEach((n) => n.animate([{ opacity: 1 }, { opacity: 1, offset: 0.5 }, {}], { duration: 420, delay: t, fill: "backwards" }));
    t += stepMs;
  }
  introUntil = performance.now() + t + 700;
  // the right column fills when the pick is found: the card and its content come in together
  document.querySelectorAll("#side .why > *:not(.cap)").forEach((n) => fx.arrive(n, t + 80, 340, 4));
  fx.appear(q('#steps [data-open="step:picked"] small'), t, 300, 0.2);
}

/** Before a redraw: where the pick sits and what every cell says, so that only what changed moves. */
function snapshot() {
  const snap = { cells: new Map(), pick: null };
  for (const row of document.querySelectorAll("#rows > .rowx")) {
    snap.cells.set(row.dataset.id, [...row.querySelectorAll(".cell, .res")].map((n) => n.className + "|" + n.textContent));
    if (row.classList.contains("picked")) snap.pick = { id: row.dataset.id, top: row.getBoundingClientRect().top, price: (row.querySelector(".pr") || {}).textContent };
  }
  return snap;
}

function moveChanges(before, oldPick, newPick) {
  if (!before) return;
  // cells re-evaluate where they stand: rows never re-sort, the order is price
  for (const row of document.querySelectorAll("#rows > .rowx")) {
    const was = before.cells.get(row.dataset.id);
    if (!was) { fx.appear(row, 0, 260); continue; }
    [...row.querySelectorAll(".cell, .res")].forEach((n, i) => { if (was[i] !== n.className + "|" + n.textContent) n.animate([{ opacity: 0.15 }, { opacity: 1 }], { duration: 320, delay: 120 + i * 40, easing: "ease-out", fill: "backwards" }); });
  }
  if (oldPick === newPick) return;
  const row = q("#rows > .rowx.picked"), old = [...document.querySelectorAll("#rows > .rowx")].find((r) => r.dataset.id === oldPick);
  if (row && before.pick) {            // the highlight glides from the old pick's row to the new one
    const dy = before.pick.top - row.getBoundingClientRect().top;
    const glide = document.createElement("div");
    glide.className = "glide";
    const r = row.getBoundingClientRect(), host = q("#app").getBoundingClientRect();
    Object.assign(glide.style, { left: r.left - host.left + "px", top: r.top - host.top + "px", width: r.width + "px", height: r.height + "px" });
    q("#app").appendChild(glide);
    glide.animate([{ transform: `translateY(${dy}px)`, opacity: 1 }, { transform: "none", opacity: 1, offset: 0.85 }, { transform: "none", opacity: 0 }], { duration: 420, easing: fx.EASE })
      .finished.then(() => glide.remove(), () => glide.remove());
    row.animate([{ borderColor: "transparent", backgroundColor: "transparent" }, { borderColor: "transparent", backgroundColor: "transparent", offset: 0.8 }, {}], { duration: 420 });
  }
  if (old) fx.appear(old.querySelector(".was"), 100, 260);
  fx.arrive(q("#side .why"), 180, 320, 4);
}

function signedMotion() {       // the last two steps fill, the signature block fills, the cart links arrive
  document.querySelectorAll('#steps [data-open="step:signs"], #steps [data-open="step:carts"]').forEach((n, i) => n.animate([{ opacity: 0.3 }, { opacity: 1 }], { duration: 400, delay: i * 260, fill: "backwards" }));
  document.querySelectorAll("#side .sign .part, #side .sign .rcpt").forEach((n, i) => fx.arrive(n, 250 + i * 170, 320, 4));
}

/** Numbers that changed roll to their new value. */
const shown = new Map();
function rollChanges(animate) {
  const now = new Map();
  for (const node of document.querySelectorAll("[data-k]")) {
    const k = node.dataset.k, text = node.textContent;
    now.set(k, text);
    if (animate && shown.has(k) && shown.get(k) !== text) fx.roll(node, shown.get(k), text);
  }
  shown.clear();
  for (const [k, v] of now) shown.set(k, v);
}

// ---------- the shopper's controls ----------
let factTimer = null;
document.addEventListener("input", (e) => {
  const input = e.target.closest("input[type=range]");
  if (!input) return;
  const value = parseFloat(input.value), id = input.dataset.id;
  input.previousElementSibling.textContent = `${g(value)} ${input.dataset.unit}`;
  if (input.dataset.kind === "ask") return;
  if (input.dataset.kind === "limit") { ui.sim.limits[id] = value; return apply(); }
  if (SIM) { ui.sim.facts[id] = value; return apply(); }
  clearTimeout(factTimer);
  factTimer = setTimeout(async () => {
    try {
      const res = await fetch("/api/shopper/fact", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ fact_id: id, value }) });
      if (!res.ok) throw new Error(res.status);
      load();
    } catch (error) { if (q("#reply")) q("#reply").innerHTML = `<p>The engine did not take the change (${esc(error.message)}).</p>`; }
  }, 60);
});
document.addEventListener("submit", async (e) => {
  if (e.target.id === "askform") {
    e.preventDefault();
    const form = e.target, body = { limit_id: form.dataset.limit, value: parseFloat(form.elements.value.value), note: form.elements.note.value.trim() };
    try {
      const res = await fetch("/api/shopper/ask-change", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const out = await res.json().catch(() => ({}));
      if (!res.ok || out.ok === false) throw new Error(out.detail || out.error || res.status);
      ui.drawer = null;
      await loadAux();
      last.quiet = true; render();
    } catch (error) { q("#askReply").innerHTML = `<p>Not sent: ${esc(error.message)}</p>`; }
    return;
  }
  if (e.target.id !== "say") return;
  e.preventDefault();
  const box = q("#sayText"), text = box.value.trim();
  if (!text || ui.busy) return;
  ui.busy = true;
  q("#reply").innerHTML = `<p class="said">“${esc(text)}”</p><p>…</p>`;
  try {
    const res = await fetch("/api/shopper/say", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
    if (!res.ok) throw new Error(res.status);
    const out = await res.json();
    ui.chat.push({ text, reply: out.reply, refused: !!out.refused });
    box.value = "";
  } catch (error) {
    ui.chat.push({ text, reply: `The agent is not connected (${error.message}).`, refused: false });
  }
  ui.busy = false;
  if (q("#reply")) q("#reply").innerHTML = chatHtml(ui.chat[ui.chat.length - 1]);
  load();
});

// ---------- a change to a limit sent from this screen, without the approver's key. The server's answer, in a toast ----------
let toastTimer = null;
function toast(anchor, html) {
  const el = q("#toast"), r = anchor.getBoundingClientRect();
  el.innerHTML = html;
  el.hidden = false;
  el.style.left = Math.max(8, Math.min(innerWidth - el.offsetWidth - 8, r.left)) + "px";
  el.style.top = r.bottom + 6 + "px";
  fx.arrive(el, 0, 220, 3);
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 6000);
}
/** The shopper's asks to the approver (GET /api/asks), newest last; the latest one for a limit. */
function askFor(limitId) {
  const list = (aux.asks && aux.asks.asks) || [];
  return list.filter((x) => x.limit_id === limitId && x.status !== "replaced").slice(-1)[0] || null;
}
function askSheet(limitId, line) {
  const limit = sheetLineOf(line).limits.find((l) => l.id === limitId);
  if (!limit) return null;
  const name = esc(state.sheet.issuer.name), b = limit.bound;
  return `<h2>Ask ${name}</h2><p>${esc(state.sheet.shopper.name)} proposes; ${name} decides on the phone.</p>
    <form id="askform" data-limit="${esc(limit.id)}">
      <label class="field"><span>${esc(cap(limit.label || limit.name))}</span><output>${esc(withUnit(g(b.value), limit.unit))}</output>
        <input type="range" data-kind="ask" data-unit="${esc(limit.unit)}" name="value" min="${b.min}" max="${b.max}" step="${b.step}" value="${b.value}"></label>
      <input id="askNote" name="note" type="text" autocomplete="off" maxlength="300" aria-label="A short note" placeholder="A short note…">
      <button class="btn" type="submit">Send to ${name}</button></form><div id="askReply" aria-live="polite"></div>`;
}

// ---------- interaction ----------
document.addEventListener("click", (e) => {
  if (e.target.id === "replay") return closeReplay();             // a click on the dimmed page
  const t = e.target.closest("[data-replay], [data-replay-close], [data-rule], [data-choose], [data-sheet], [data-menu], [data-toggle], [data-show], [data-open], [data-close], .rowx");
  if (ui.menu && !(t && (t.dataset.sheet || t.dataset.menu !== undefined))) { ui.menu = false; ui.confirm = null; if (!t) { last.quiet = true; render(); return; } }
  if (!t || e.target.closest("a, input")) return;
  if (t.dataset.replay !== undefined) return openReplay();
  if (t.dataset.replayClose !== undefined) return closeReplay();
  if (t.dataset.rule) return setRule(t.dataset.rule, t);
  if (t.dataset.choose !== undefined) return choose(t.dataset.choose, t);
  if (t.dataset.sheet) return useSheet(t.dataset.sheet, t.dataset.sure === "1");
  if (t.dataset.menu !== undefined) { ui.menu = !ui.menu; ui.confirm = null; last.quiet = true; return render(); }
  if (t.dataset.toggle) { ui.open.has(t.dataset.toggle) ? ui.open.delete(t.dataset.toggle) : ui.open.add(t.dataset.toggle); }
  else if (t.dataset.close !== undefined) ui.drawer = null;
  else if (t.dataset.show !== undefined) ui.show = null;
  else if (t.dataset.open) ui.drawer = ui.drawer === t.dataset.open ? null : t.dataset.open;
  else if (t.classList.contains("rowx")) { ui.show = t.classList.contains("picked") ? null : t.dataset.id; ui.drawer = null; }
  last.quiet = true;
  render();
  if (ui.drawer === "shopper") q("#sayText")?.focus();
});
addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !q("#replay").hidden) return closeReplay();
  if (e.key === "Escape" && (ui.drawer || ui.show || ui.menu)) { ui.drawer = null; ui.show = null; ui.menu = false; last.quiet = true; render(); }
  if ((e.key === "Enter" || e.key === " ") && e.target.classList && e.target.classList.contains("choosebtn")) { e.preventDefault(); return choose(e.target.dataset.choose, e.target); }
  if ((e.key === "Enter" || e.key === " ") && e.target.classList && e.target.classList.contains("ask")) { e.preventDefault(); e.target.click(); }
  if (e.target.tagName === "INPUT" || e.metaKey || e.ctrlKey || e.altKey || !state) return;
  if (e.key === "e") { e.preventDefault(); ui.drawer = ui.drawer === "shopper" ? null : "shopper"; last.quiet = true; render(); q("#sayText")?.focus(); }
  const n = parseInt(e.key, 10);
  if (n >= 1 && n <= state.lines.length) location.hash = state.lines[n - 1].line_id;
});

load().then(loadAux);
