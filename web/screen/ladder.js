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
const q = (sel, root = document) => root.querySelector(sel);
const params = new URLSearchParams(location.search);
const SIM = params.get("sim") === "1";
const FIXTURE = { 1: "/screen/fixture-state.json", signed: "/screen/fixture-signed.json", sheet2: "/screen/fixture-sheet2.json" }[params.get("fixture")];

let server = null, state = null, raw = "";
// ?open=above,below unfolds the list; ?drawer=shopper|step:3|<candidate id> opens the side sheet; ?show=<candidate id> selects a row
const ui = { open: new Set((params.get("open") || "").split(",").filter(Boolean)), drawer: params.get("drawer"), show: params.get("show"),
  chat: [], busy: false, sim: { limits: {}, facts: {}, strikes: [] } };
const last = { line: null, pick: null, signed: null, quiet: false };
const aux = { egress: null, gate: null, enroll: null, trail: null, key: "" };
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
  if (FIXTURE) return;
  const get = (url) => fetch(url, { cache: "no-store" }).then((r) => (r.ok ? r.json() : null)).catch(() => null);
  const needCode = state && !(state.issuer_key && state.issuer_key.enrolled) && !state.seal.signed;
  const [egress, gate, enroll, trail] = await Promise.all([get("/api/egress?limit=5000"), get("/api/gate/status"),
    needCode ? get("/api/issuer/enroll-code") : null, get("/api/trail")]);
  const key = JSON.stringify([egress && egress.summary, gate && [gate.arm, gate.value, gate.verdict, (gate.history || []).length], enroll, trail && trail.summary]);
  Object.assign(aux, { egress, gate, enroll, trail });
  if (key !== aux.key && state) {       // redraw quietly, and never in the middle of the opening motion
    aux.key = key;
    setTimeout(() => { last.quiet = true; render(); }, Math.max(0, introUntil - performance.now()));
  }
}
setInterval(loadAux, 5000);
let live = false;
if (params.get("live") !== "0") {
  const events = new EventSource("/api/events");
  events.onopen = () => { live = true; };
  events.onmessage = () => load();
  events.onerror = () => { live = false; };
}
setInterval(() => { if (!live) load(); }, 2000);
addEventListener("hashchange", () => { ui.drawer = null; ui.show = null; ui.open.clear(); render(); });

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
  return { name: cap(name), rule: `${opSymbol(limit.op)} ${g(boundOf(limit))} ${limit.unit}` };
}

/** The page's own figure behind a check that is unclear: read, quoted, but not one clear value. */
function unsureFigure(c, ch) {
  const t = ch.terms.find((x) => x.owner === "store") || {}, name = ch.missing_figure || t.figure;
  return (c.figures || []).find((f) => f.figure === name && (f.unsure || ch.state === "unclear" || c.status === "unclear")) || null;
}
const isUnclear = (c, ch) => ch.state === "unclear" || (ch.state === "not_stated" && (/stated, but not clearly/.test(ch.missing_why || "") || !!unsureFigure(c, ch)));

/** What a cell shows for one check: the value the page states, as the page gives it. */
function statedText(ch, c) {
  const t = ch.terms.find((x) => x.owner === "store") || {}, unit = ch.bound.unit;
  const f = c && ch.lhs == null ? unsureFigure(c, ch) : null;
  if (f && !(t.values || t.stated_values)) {
    const u = f.unit || "no unit";
    return f.low != null && f.high != null && f.low !== f.high ? `${g(f.low)} or ${g(f.high)} ${u}` : f.value != null || f.low != null ? `${g(f.value ?? f.low)} ${u}` : "";
  }
  const many = t.values || t.stated_values || t.stated;
  if (Array.isArray(many) && many.length > 1) return `${many.map((v) => g(typeof v === "object" && v ? v.value : v)).join(" or ")} ${unit}`;
  if (ch.stated_text || t.stated_text) return ch.stated_text || t.stated_text;
  if (ch.terms.length === 1 && t.low != null && t.high != null && t.low !== t.high) return `${g(t.low)}${t.kind === "adjustable" ? "–" : " / "}${g(t.high)} ${unit}`;
  return ch.lhs == null ? "" : `${g(ch.lhs)} ${unit}`;
}

/** Two to four plain words for a check that did not pass. */
function failWords(ch) {
  const unit = ch.bound.unit, b = g(ch.bound.value);
  if (ch.state === "not_stated") return `never states ${words(ch.missing_figure || ch.name)}`;
  if (ch.state === "unclear") return "unclear";
  if (ch.lhs == null) return "not clear";
  return ch.op === "==" ? `${g(ch.lhs)} ${unit}, needs ${b}` : ch.op === ">=" ? `${g(ch.lhs)} ${unit}, under ${b}` : `${g(ch.lhs)} ${unit}, over ${b}`;
}

/** The row's result: the pick, a rejection with its reason, or one that passes but was not needed. */
function verdict(c, line, pick) {
  if (c.picked) return { kind: "pick", text: "picked" };
  if (c.status === "struck") return { kind: "no", text: `struck by ${state.sheet.issuer.name}`, why: c.reason };
  const i = firstFail(c);
  if (i < 0 && c.status === "inside") {
    if (pick && c.product.price_cents >= pick.product.price_cents) return { kind: "also", text: "also passes" };
    return { kind: "no", text: needsDelivery() && !(c.arrival && c.arrival.status === "stated") ? "no delivery time stated" : "passes" };
  }
  const ch = c.checks[Math.max(0, i)], reason = c.reason || "";
  // the three kinds are different things: outside a limit, stated but not clearly, not on the page at all
  if (c.status === "unclear" || isUnclear(c, ch)) {
    const f = unsureFigure(c, ch) || {}, why = ch.missing_why || f.unsure_reason || (reason.includes(":") ? reason.slice(reason.indexOf(":") + 1).trim() : reason);
    const many = (ch.terms.find((x) => x.owner === "store") || {}).values;
    const short = f.quote && !f.unit ? "no unit stated" : (f.low != null && f.high != null && f.low !== f.high) || (many && many.length > 1) ? "two values" : "";
    return { kind: "no unclear", text: "unclear", why, extra: short };
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
    ui.was = old ? { id: old.id, price: money(old.product.price_cents) } : null;
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
  if (opening || pickId !== last.pick) q("#rows > .rowx.picked")?.scrollIntoView({ block: "nearest" });    // the pick is never below the fold
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
    <span class="sheet">${esc(sheet.title)}</span>
    <nav class="tabs" aria-label="Views"><a href="/${location.search}${location.hash}" aria-current="page">Decision</a><a href="/trail/">Trail</a></nav>
    <span class="meta">${[`${state.lines.length} items`, sheet.invented ? "invented people" + real : "", ...mode].filter(Boolean).join(" · ")}</span>
    <span class="grow"></span>
    <span class="pill ${seal.signed ? "signed" : ""}">${seal.signed ? "Signed " + time : "Not signed"}</span>
    <span class="total" data-k="total">${money(state.total_cents)}</span>`;
}

// ---------- the stepper: the run across the top. Every number is from the state ----------
function stepList(line, pick) {
  const { sheet, seal, counts } = state, o = state.order;
  const limits = o && o.limits_derived != null ? o.limits_derived : sheet.lines.reduce((n, l) => n + l.limits.filter((x) => x.from_order).length, 0);
  const pages = counts.products_found != null ? counts.products_found : state.lines.reduce((n, l) => n + l.candidates.length, 0);
  const at = seal.signed_at || (seal.signature && seal.signature.at);
  const time = at ? new Date(at).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }) : "";
  return [
    { id: "list_read", label: "List read", small: limits ? `${limits} limits, quoted` : "limits on the sheet", done: true },
    { id: "stores_searched", label: "Stores searched", small: `${sheet.stores.length} stores`, done: pages > 0 },
    { id: "pages_read", label: "Pages read", small: `${pages} pages`, done: pages > 0 },
    { id: "checked", label: "Checked", small: "cheapest first", done: pages > 0 },
    { id: "picked", label: "Picked", small: pick ? money(pick.product.price_cents) : "nothing passes", done: !!pick, k: "step.pick" },
    { id: "signs", label: `${cap(sheet.issuer.role || "approver")} signs`, small: seal.signed ? `${sheet.issuer.name}, ${time}` : "from the phone", done: !!seal.signed },
    { id: "carts", label: "Carts", small: seal.signed ? `${(seal.carts || []).length} created` : "none exist yet", done: !!seal.signed && (seal.carts || []).length > 0 },
  ];
}

function renderSteps(line, pick) {
  const steps = stepList(line, pick), current = steps.findIndex((s) => !s.done);
  q("#steps").innerHTML = steps.map((s, i) => `<button class="step ${s.done ? "done" : "todo"}${i === current ? " now" : ""}" data-open="step:${s.id}" ${i === current ? 'aria-current="step"' : ""}>
    <span class="n">${s.done ? "✓" : i + 1}</span><span class="t"><span class="l">${esc(s.label)}</span><small ${s.k ? `data-k="${s.k}"` : ""}>${esc(s.small)}</small></span></button>`).join("");
}

// ---------- left: the list, as a document someone wrote ----------
/** The requirement in the list's own words, with the deciding number marked. Without a quote, the sheet's own label. */
function requirement(limit) {
  const o = limit.from_order, b = boundOf(limit);
  if (o && o.quote) {
    const value = o.value ?? (limit.bound.source === "issuer" ? b : null);
    if (value == null) return esc(o.quote);
    const [s, e] = figureSpan(o.quote, { value });
    return s === 0 && e === o.quote.length ? esc(o.quote) : `${esc(o.quote.slice(0, s))}<mark>${esc(o.quote.slice(s, e))}</mark>${esc(o.quote.slice(e))}`;
  }
  return limit.bound.source === "shopper" ? `${esc(cap(limit.label || limit.name))}.` : `${esc(cap(limit.label || limit.name))} <mark>${g(b)} ${esc(limit.unit)}</mark>.`;
}

function renderDoc(current) {
  const { issuer, shopper } = state.sheet;
  const home = (limit) => {                           // a requirement that points at the house carries the measurement beside it
    const f = limit.bound.source === "shopper" && state.sheet.shopper_facts.find((x) => x.id === limit.bound.fact);
    return f ? ` <span class="home" title="from the home: ${esc(f.label)}">(${g(f.value)} ${esc(f.unit)})</span>` : "";
  };
  q("#doc").innerHTML = `<div class="cap">${esc(issuer.name)}'s list · ${esc(issuer.role_label || issuer.role || "")}${issuer.invented ? " · invented" : ""}</div>
    <div class="paper">${state.lines.map((l) => {
      const p = pickOf(l), sl = sheetLineOf(l);
      const right = p ? (l.status === "pick_up" ? "pick up" : money(p.product.price_cents)) : "open";
      const seen = new Set();
      const text = sl.limits.map((limit) => requirement(limit) + home(limit)).filter((t) => !seen.has(t) && seen.add(t)).join(" ");
      return `<a class="it" href="#${l.line_id}" aria-current="${l.line_id === current.line_id}">
        <span class="stt" data-k="doc.${l.line_id}">${right}</span><h4>${esc(cap(l.need))}</h4><p>${text}</p></a>`;
    }).join("")}</div>
    <button class="link asker" data-open="shopper">${esc(shopper.name)}: measurements, chat</button>`;
}

// ---------- centre: the candidates, cheapest first ----------
function rowHtml(c, line, pick, limits) {
  const v = verdict(c, line, pick), fail = c.status === "struck" ? -1 : firstFail(c);
  const cells = c.checks.map((ch, i) => {
    if (fail >= 0 && i > fail) return `<span class="cell skip">—</span>`;
    if (isUnclear(c, ch)) return `<span class="cell"><span class="chip unclear">${esc(statedText(ch, c) || "unclear")}</span></span>`;
    if (ch.state === "not_stated") return `<span class="cell"><span class="chip none">not stated</span></span>`;
    return `<span class="cell ${ch.pass ? "" : "bad"}">${esc(statedText(ch))}</span>`;
  }).join("");
  const option = c.product.variant_title && !/^default/i.test(c.product.variant_title) ? `${c.product.variant_title} · ` : "";
  const img = c.product.image_url ? `<img src="${esc(c.product.image_url)}" alt="" loading="lazy" width="44" height="44" onerror="this.outerHTML='<span class=ph></span>'">` : `<span class="ph" aria-hidden="true"></span>`;
  const result = v.kind === "pick" ? `<span class="res pickd">✓ picked</span>`
    : v.kind === "also" ? `<span class="res also">✓ ${esc(v.text)}</span>`
    : `<span class="res no" title="${esc(v.why || "")}">✕ ${esc(v.text)}${v.extra ? ` <span class="faint">${esc(v.extra)}</span>` : ""}</span>`;
  const was = ui.was && ui.was.id === c.id && !c.picked ? `<span class="was">was picked</span>` : "";
  return `<button class="rowx ${c.picked ? "picked" : v.kind === "also" ? "also" : "rej"}${c.id === ui.show ? " shown" : ""}${was ? " waspick" : ""}" data-id="${esc(c.id)}" style="--n:${limits.length}">${was}
    ${img}<span class="nm"><b>${esc(c.product.title)}</b><i>${esc(option + c.product.store)}</i></span>
    <span class="pr">${money(c.product.price_cents)}</span>${cells}${result}</button>`;
}

function renderList(line, pick) {
  const limits = sheetLineOf(line).limits, rows = priced(line), at = pick ? rows.indexOf(pick) : -1;
  const cheaper = at >= 0 ? rows.slice(0, at) : rows, dearer = at >= 0 ? rows.slice(at + 1) : [];
  const also = dearer.filter((c) => c.status === "inside").length;
  let fold = cheaper.length > 6 && !ui.open.has("above") && at >= 0 ? cheaper.length - 6 : 0;
  if (fold && ui.was && cheaper.slice(0, fold).some((c) => c.id === ui.was.id)) fold = 0;      // keep the old pick in view while it says so
  const forged = (limit) => limit.bound.source === "issuer" && !state.seal.signed
    ? `<span class="forge" role="button" tabindex="0" data-forge="${esc(limit.id)}" title="Try to change this limit from here, without the approver's key" aria-label="Try to change this limit from here">change</span>` : "";
  const heads = limits.map((limit) => { const h = limitHead(limit); return `<span class="lh"><span>${esc(h.name)} <b data-k="head.${limit.id}">${esc(h.rule)}</b></span>${forged(limit)}</span>`; }).join("");
  const sub = at >= 0 ? `Cheapest first. ${rows.length} read · <span data-k="sub.rej">${cheaper.length}</span> cheaper ones rejected · <span data-k="sub.also">${also}</span> dearer ones also pass`
    : `Cheapest first. ${rows.length} read · nothing passes`;
  q("#list").innerHTML = `<div class="lhd"><h1>${esc(cap(line.need))}</h1><p class="sub">${sub}</p></div>
    <div class="hd" style="--n:${limits.length}"><span></span><span>Product</span><span>Price</span>${heads}<span>Result</span></div>
    <div class="rows" id="rows">
      ${fold ? `<button class="more" data-toggle="above">${fold} cheaper ones above, each rejected with its reason</button>` : ""}
      ${cheaper.slice(fold).map((c) => rowHtml(c, line, pick, limits)).join("")}
      ${pick ? rowHtml(pick, line, pick, limits) : `<div class="more none">Nothing passes: ${esc(line.reason || "no product meets every limit")}</div>`}
      ${dearer.length ? (ui.open.has("below") ? dearer.map((c) => rowHtml(c, line, pick, limits)).join("")
        : dearer.filter((c) => ui.was && ui.was.id === c.id).map((c) => rowHtml(c, line, pick, limits)).join("") + `<button class="more" data-toggle="below">+ ${dearer.length} dearer, not needed</button>`) : ""}
    </div>`;
}

// ---------- right: why this one, in the list's words and the store's words ----------
/** The part of a sentence around its figure, the figure marked and never cut off. */
function fragment(quote, term, before = 44, after = 30) {
  const text = quote || "";
  const [s, e] = figureSpan(text, term);
  if (s === 0 && e === text.length) return esc(clip(text, before + after));
  let from = Math.max(0, s - before);
  if (from > 0) from = text.indexOf(" ", from) + 1 || from;
  let to = Math.min(text.length, e + after);
  if (to < text.length) to = Math.max(e, text.lastIndexOf(" ", to));
  return `${from > 0 ? "…" : ""}${esc(text.slice(from, s).replace(/^[\s•\-:,;]+/, ""))}<mark>${esc(text.slice(s, e))}</mark>${esc(text.slice(e, to))}${to < text.length ? "…" : ""}`;
}

function pairHtml(ch, limit, c) {
  const order = limit && limit.from_order, t = ch.terms.find((x) => x.owner === "store") || {};
  const ok = ch.pass, word = ch.op === "==" ? "matches" : ch.op === "<=" ? "within" : "enough";
  const src = (label, html) => `<div class="k">${label}</div><div class="qt">${html}</div>`;
  const homeRow = (part) => src("from the home", `${esc(part.label)} <mark>${g(part.value)} ${esc(part.unit)}</mark>`);
  const head = limit ? limitHead(limit) : { name: cap(ch.name), rule: "" };
  let store;
  const f = unsureFigure(c, ch);
  if (isUnclear(c, ch)) {
    const quote = (f && f.quote) || t.quote, why = ch.missing_why || (f && f.unsure_reason) || "";
    store = src("the store states", quote ? fragment(quote, f || t) : `<span class="chip unclear">${esc(statedText(ch, c) || "unclear")}</span>`)
      + (why ? src("why it is unclear", esc(clip(why.replace(/^stated, but not clearly[^:]*:\s*/, ""), 120))) : "");
  } else if (ch.state === "not_stated") store = src("the store states", `<span class="chip none">not stated on the page</span>`);
  else store = t.quote ? src("the store states", fragment(t.quote, t)) : "";
  return `<div class="pair" data-open="${esc(c.id)}">
    <div class="ph2"><span>${esc(head.name)} <span class="faint">${esc(head.rule)}</span></span><span class="${ok ? "okw" : isUnclear(c, ch) || ch.state === "not_stated" ? "greyw" : "badw"}">${ok ? "✓ " + word : "✕ " + esc(isUnclear(c, ch) ? "unclear" : failWords(ch))}</span></div>
    ${order && order.quote ? src("the list says", fragment(order.quote, { value: order.value ?? (ch.bound.owner === "issuer" ? ch.bound.value : undefined) }) + orderTags(order, ch)) : ""}
    ${ch.bound.owner === "shopper" ? homeRow(ch.bound) : ""}${ch.terms.filter((x) => x.owner === "shopper").map(homeRow).join("")}
    ${store}</div>`;
}

/** Small quiet tags beside the list's sentence: the document's version at Senso, and whether the limit was changed since. */
function orderTags(order, ch) {
  const senso = (Array.isArray(state.senso) ? state.senso : []).find((r) => r && r.limit_id === ch.limit_id && (r.version_id || r.content_id)) || {};
  const id = order.version_id || order.content_id || senso.version_id || senso.content_id;
  return (order.matches === false ? ` <span class="tag">changed from the list</span>` : "") + (id ? ` <span class="tag" title="Senso ${esc(id)}">Senso ${esc(String(id).slice(0, 8))}</span>` : "");
}

function renderSide(line, c) {
  const limits = sheetLineOf(line).limits;
  let card;
  if (c) {
    const fail = c.status === "struck" ? -1 : firstFail(c), shown = fail >= 0 ? c.checks.slice(0, fail + 1) : c.checks;
    const option = c.product.variant_title && !/^default/i.test(c.product.variant_title) ? `${c.product.variant_title} · ` : "";
    const a = c.arrival, u = c.undo, scope = (x) => (x && x.scope ? ` <span class="faint">(${esc(x.scope)})</span>` : "");
    const agent = c.picked && ((a && a.quote) || (u && u.quote)) ? `<div class="pair agent" data-open="${esc(c.id)}"><div class="ph2"><span>The store's agent said</span></div>
        ${a && a.quote ? `<div class="k">delivery${scope(a)} · stated, not guaranteed</div><div class="qt">“${esc(clip(a.quote, 90))}”</div>` : ""}
        ${u && u.quote ? `<div class="k">returns${scope(u)}</div><div class="qt">“${esc(clip(u.quote, 90))}”</div>` : ""}</div>` : "";
    card = `<section class="card why"><div class="cap">${c.picked ? "Why this one" : "Why not this one"}</div>
      <h2 title="${esc(c.product.title)}">${esc(c.product.title)}</h2>
      <div class="meta2">${esc(option + c.product.store)} · <span data-k="why.price">${money(c.product.price_cents)}</span> · <a class="link" href="${esc(c.product.url)}" target="_blank" rel="noopener">store page ↗</a></div>
      ${c.status === "struck" ? `<div class="pair"><div class="ph2"><span>Struck by ${esc(state.sheet.issuer.name)}</span></div><div class="qt">“${esc(c.reason || "")}”</div></div>` : ""}
      ${shown.map((ch) => pairHtml(ch, limits.find((l) => l.id === ch.limit_id), c)).join("")}${agent}
      ${!c.picked && pickOf(line) ? `<button class="link" data-show="">Back to the pick</button>` : ""}</section>`;
  } else {
    card = `<section class="card why"><div class="cap">Why this one</div><h2>Nothing passes</h2><div class="muted">${esc(cap(line.reason || "no product meets every limit"))}. Select a row to read why.</div></section>`;
  }
  q("#side").innerHTML = card + signatureHtml();
}

/** The receipt chain, when the engine reports it: one tick per receipt and the count, on one line. */
function receiptsRow() {
  const r = state.receipts;
  if (!r || !r.count) return "";
  const good = typeof r.verified === "number" ? r.verified : r.verified ? r.count : (r.first_bad ? r.first_bad - 1 : 0);
  const n = Math.min(r.count, 48);
  return `<div class="rcpt" title="Tamper-evident: each receipt carries the hash of the one before"><span class="ticks">${Array.from({ length: n }, (_, i) => `<i class="${i < Math.round((good / r.count) * n) ? "" : "bad"}"></i>`).join("")}</span>
    <span class="muted small">${good === r.count ? `${r.count} ${r.count === 1 ? "receipt" : "receipts"} verified` : `${good} of ${r.count} receipts verified`}</span></div>`;
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

function signatureHtml() {
  const { sheet, seal } = state;
  if (!seal.signed) {
    const en = aux.enroll, enrolled = state.issuer_key && state.issuer_key.enrolled;
    const link = en && (en.url || en.link || en.phone_url || en.phone), qr = !enrolled && link ? qrSvg(link) : "";
    return `<section class="card sign"><div class="cap">Signature</div>
      <div class="who"><i class="pending"></i>${esc(sheet.issuer.name)} must sign · no cart exists</div>
      ${!enrolled && en && en.code ? `<div class="enrol">${qr ? `<a class="qr" href="${esc(link)}" target="_blank" rel="noopener" aria-label="Open the phone page">${qr}</a>` : ""}
        <div><div>Scan to enrol the phone</div><div class="muted">code <span class="code">${esc(en.code)}</span></div></div></div>`
        : enrolled ? `<div class="muted small">Phone enrolled · waiting for the signature</div>` : ""}
      ${receiptsRow()}</section>`;
  }
  const sig = seal.signature || {}, persona = sig.persona || (state.issuer_key && state.issuer_key.persona) || {};
  const who = seal.signer || (sig.signer && sig.signer.name) || sheet.issuer.name, hash = seal.sheet_hash || sig.sheet_hash || "";
  const at = seal.signed_at || sig.at, time = at ? new Date(at).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }) : "";
  // how the signer is known, from the state: the server's own label when it gives one, else from the identity check
  const identity = seal.signer_label || seal.identity || sig.identity || (sig.signer && (sig.signer.label || sig.signer.identity))
    || (persona.verified ? "identity checked (sandbox)" : "self-declared");
  const covers = Array.isArray(seal.covers) && seal.covers.length ? seal.covers.map(words) : [];
  const differs = (c) => c.signed_total_cents != null && c.total_cents != null && c.signed_total_cents !== c.total_cents;
  return `<section class="card sign signed"><div class="cap">Signature</div>
    <div class="row part"><span class="who"><span class="tickmark">✓</span> Signed by ${esc(who)}</span><span>${time}</span></div>
    <div class="muted small part">${esc(identity)}</div>
    ${hash ? `<div class="row part"><span class="muted">Sheet hash</span><code title="${esc(hash)}">${esc(hash.slice(0, 12))}</code></div>` : ""}
    ${covers.length ? `<div class="muted small part" title="${esc(covers.join(", "))}">Hash covers ${esc(covers.slice(0, 3).join(", "))}${covers.length > 3 ? ` +${covers.length - 3}` : ""}</div>` : ""}
    ${(seal.carts || []).map((c) => `<div class="row part cart"><a href="${esc(c.cart_url)}" target="_blank" rel="noopener">${esc(c.store)} cart ↗</a><span>${c.total_cents ? money(c.total_cents) : ""}</span></div>${differs(c) ? `<div class="badw small part">store total differs · signed ${money(c.signed_total_cents)} · store ${money(c.total_cents)}</div>` : ""}`).join("") || `<div class="muted part">No cart link came back</div>`}
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
  el.innerHTML = `${closeBtn}<h2>${esc(shopper.name)}${shopper.invented ? " · invented" : ""}</h2><p>${esc(cap(shopper.role_label || ""))}</p>
    ${facts.length ? `<h3>From the home</h3>` + facts.map((f) => slider("fact", f.id, f.label, f.value, f.unit, f)).join("") : ""}
    ${SIM ? `<h3>Simulation only, not ${esc(state.sheet.issuer.name)}'s phone</h3>` + sheetLine.limits.filter((l) => l.bound.source === "issuer").map((l) => slider("limit", l.id, l.label, l.bound.value, l.unit, l.bound)).join("") : ""}
    <h3>Ask the agent</h3>
    <form id="say"><input id="sayText" name="say" type="text" autocomplete="off" aria-label="Message to the agent" placeholder="Put the struck one back…"><button class="btn" type="submit">Send</button></form>
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
  return `<h3>Records of this step</h3>${rows.slice(0, 10).map((e) => `<p class="rec"><span>${e.stopped ? '<b class="badw">refused</b> ' : ""}${esc(e.label || e.kind || "")}${e.detail ? ` <span class="muted">${esc(clip(e.detail, 34))}</span>` : ""}</span><span class="faint">${time(e)}</span></p>`).join("")}
    <p class="small">${rows.length > 10 ? `${rows.length - 10} more. ` : ""}<a class="link" href="/trail/#${esc(id)}">Open on the Trail</a></p>`;
}

/** One step of the run: what the state holds for it. */
function stepSheet(id, line, pick) {
  const { sheet, counts } = state, o = state.order || {};
  const perStore = (list) => sheet.stores.map((s) => `<p class="rec">${esc(s)} <span class="muted">${list.filter((c) => c.product.store === s).length} pages for this item</span></p>`).join("");
  if (id === "list_read") {
    const all = sheet.lines.flatMap((l) => l.limits.filter((x) => x.from_order && x.from_order.quote).map((x) => ({ l, x })));
    return `<h2>${esc(o.title || sheet.issuer.name + "'s list")}</h2>
      ${o.limits_derived != null ? `<p><b>${o.limits_matching} of ${o.limits_derived} limits</b> read from the list match the sheet.</p>` : ""}
      ${all.map(({ l, x }) => `<h3>${esc(cap(l.need))} · ${esc(x.name)}${x.from_order.matches === false ? " · changed from the list" : ""}</h3><p>“${fragment(x.from_order.quote, { value: x.from_order.value ?? undefined }, 400, 400)}”</p>`).join("")}
      <h3>Method</h3><p>The model reads the figure; code checks that the quote is in the list's text.</p>${trailRows(id)}`;
  }
  if (id === "stores_searched") return `<h2>Stores searched</h2>${perStore(line.candidates)}${egressHtml()}${trailRows(id)}`;
  if (id === "pages_read") {
    const scan = state.instruction_scan;
    return `<h2>Pages read</h2><p><b>${counts.products_found} pages</b> across the sheet, ${line.candidates.length} for this item.</p>
      ${scan ? `<h3>Instructions to an agent</h3><p><b>${scan.pages_scanned} pages scanned, ${scan.instructions_found} found.</b></p>${(scan.examples || []).map((x) => `<p>“${esc(x.quote || x)}”</p>`).join("")}` : ""}
      ${readerHtml()}<h3>Method</h3><p>The model reads the figure; code checks that the quote is in the store's text and does the sums.</p>${trailRows(id)}`;
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
    quotes.push(`<h3>${esc(cap(words(t.figure)))} · the store states</h3><p>“${esc(text.slice(0, s))}<mark>${esc(text.slice(s, e))}</mark>${esc(text.slice(e))}”</p>`);
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
    ${(c.asked || []).map((a) => `<h3>Asked the store's agent</h3><p><b>${esc(a.question || "")}</b></p><p>“${esc(a.reply || "")}”</p>`).join("")}
    <h3>Method</h3><p>The model reads the figure; code checks that the quote is in the store's text and does the sums.</p>`;
}

function renderDrawer(line, pick) {
  const el = q("#drawer"), d = ui.drawer;
  if (d === "shopper") { el.hidden = false; return shopperSheet(el, line); }
  el.dataset.for = "";
  let html = null;
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
  fx.arrive(q("#side .why"), t + 80, 340, 4);
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
const REFUSAL = { unsigned: "not signed", not_enrolled: "not signed", bad_signature: "not signed", unknown_key: "not the approver's key", replayed_seq: "replayed request", bad_payload: "not a signed request" };
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
async function forgeChange(anchor) {
  const line = theLine(), limit = sheetLineOf(line).limits.find((l) => l.id === anchor.dataset.forge);
  const payload = JSON.stringify({ type: "set_limit", sheet_id: state.sheet.id, seq: Date.now(), at: new Date().toISOString(), limit_id: limit.id, value: limit.bound.min });
  const sig = btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(64)))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  let html;
  try {
    const res = await fetch("/api/issuer/request", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ payload, sig, key_id: (state.issuer_key && state.issuer_key.key_id) || "this-screen" }) });
    const out = await res.json().catch(() => ({}));
    html = res.ok && out.ok !== false ? `<b class="badw">Accepted</b> <span class="code2">${res.status}</span>`
      : `<b>Refused</b> · ${esc(REFUSAL[out.error] || words(out.error || "no reason given"))} <span class="code2" title="${esc(out.detail || "")}">${res.status}</span>`;
  } catch (error) {
    html = "No answer from the server";
  }
  toast(q(`[data-forge="${CSS.escape(limit.id)}"]`) || anchor, html);
  load();
}

// ---------- interaction ----------
document.addEventListener("click", (e) => {
  const t = e.target.closest("[data-forge], [data-toggle], [data-show], [data-open], [data-close], .rowx");
  if (!t || e.target.closest("a, input")) return;
  if (t.dataset.forge) return forgeChange(t);
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
  if (e.key === "Escape" && (ui.drawer || ui.show)) { ui.drawer = null; ui.show = null; last.quiet = true; render(); }
  if ((e.key === "Enter" || e.key === " ") && e.target.dataset && e.target.dataset.forge) { e.preventDefault(); forgeChange(e.target); }
  if (e.target.tagName === "INPUT" || e.metaKey || e.ctrlKey || e.altKey || !state) return;
  if (e.key === "e") { e.preventDefault(); ui.drawer = ui.drawer === "shopper" ? null : "shopper"; last.quiet = true; render(); q("#sayText")?.focus(); }
  const n = parseInt(e.key, 10);
  if (n >= 1 && n <= state.lines.length) location.hash = state.lines[n - 1].line_id;
});

load().then(loadAux).then(() => {       // ?forge=1 uses the control once after loading, for a picture of the server's answer
  const control = params.get("forge") === "1" && q("[data-forge]");
  if (control) forgeChange(control);
});
