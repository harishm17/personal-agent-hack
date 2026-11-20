// Sign-Off, main view: how one order line was decided, left to right. Every product page is one dot.
// Read -> State the figures -> Inside limits -> Pick. Everything is drawn from GET /api/state; the page decides nothing.
import { figureSpan, marginText, money, niceDomain, num, opWords, pickOf, simulate } from "/screen/model.js";
import * as fx from "/screen/motion.js";

const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const words = (s) => String(s || "").replace(/_/g, " ");
const params = new URLSearchParams(location.search);
const SIM = params.get("sim") === "1";
const FIXTURE = { 1: "/screen/fixture-state.json", signed: "/screen/fixture-signed.json" }[params.get("fixture")];
const q = (sel, root = document) => root.querySelector(sel);

let server = null, state = null, raw = "";
// ?open=unstated,outside expands trays; ?drawer=pick|shopper opens the side sheet (so a view can be linked and pictured)
const ui = { open: new Set((params.get("open") || "").split(",").filter(Boolean)), drawer: params.get("drawer"), chat: [], busy: false,
  sim: { limits: {}, facts: {}, strikes: [] } };
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
      const line = state.lines.find((l) => l.line_id === lineId());
      if (id === "strike") ui.sim.strikes.push({ line_id: line.line_id, product_key: (pickOf(line) || { product: {} }).product.product_key, reason: "simulated strike" });
      else (id.includes(".") ? ui.sim.limits : ui.sim.facts)[id] = parseFloat(v);
      apply();
    }, parseInt(ms, 10) || 2000);
  }
}

document.body.innerHTML = `<div id="app">
  <header class="top" id="top"></header>
  <nav class="rail" id="rail" aria-label="Items on the sheet"></nav>
  <main class="main" id="main"><p class="wait">Loading…</p></main>
  <aside class="side" id="side" aria-label="The pick and the signature"></aside>
  <aside class="drawer" id="drawer" hidden aria-live="polite"></aside>
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
    if (!state) q("#main").innerHTML = `<p class="wait">Waiting for the engine…</p>`;
  }
}
function apply() {
  state = SIM && (Object.keys(ui.sim.limits).length || Object.keys(ui.sim.facts).length || ui.sim.strikes.length) ? simulate(server, ui.sim) : server;
  render();
}
let live = false;
if (params.get("live") !== "0") {
  const events = new EventSource("/api/events");
  events.onopen = () => { live = true; };
  events.onmessage = () => load();
  events.onerror = () => { live = false; };
}
setInterval(() => { if (!live) load(); }, 2000);
addEventListener("hashchange", () => { ui.drawer = null; ui.open.clear(); render(); });
addEventListener("resize", () => { last.line = null; last.quiet = true; if (state) render(); });

const lineId = () => (state.lines.find((l) => l.line_id === location.hash.slice(1)) || state.lines[0]).line_id;
const STATUS = { ready: "Ready", pick_up: "Pick up locally", open: "Open", next_candidate: "Next candidate" };

/** The stages one line's candidates reached. */
function stages(line) {
  const stated = line.candidates.filter((c) => !c.checks.some((ch) => ch.state === "not_stated"));
  const unstated = line.candidates.filter((c) => !stated.includes(c));
  const inside = stated.filter((c) => c.status === "inside");
  const local = line.status === "pick_up";
  const eligible = inside.filter((c) => local || (c.arrival && c.arrival.status === "stated"));
  return { all: line.candidates, stated, unstated, inside, eligible, local,
    outside: stated.filter((c) => c.status === "outside"), struck: stated.filter((c) => c.status === "struck"),
    noDelivery: inside.filter((c) => !eligible.includes(c)), pick: pickOf(line) };
}

// ---------- render ----------
// What the previous draw showed, so that only real changes move.
const last = { line: null, pick: null, signed: null, quiet: false };

function render() {
  const id = lineId(), line = state.lines.find((l) => l.line_id === id), s = stages(line);
  const opening = last.line !== id, before = opening ? null : snapshot();
  const pickId = s.pick ? s.pick.id : null, pickChanged = !opening && pickId !== last.pick;
  const justSigned = last.signed === false && !!state.seal.signed;
  renderTop();
  renderRail(id);
  renderFlow(line, s);
  renderSide(line, s);
  renderDrawer(line);
  if (fx.MOTION && !last.quiet) {
    if (opening) intro();
    else {
      moveChanges(before);
      if (pickChanged) document.querySelectorAll("#side .card:first-child > *:not(.cap)").forEach((n, i) => fx.arrive(n, i * 40, 300, 4));
    }
    if (justSigned) document.querySelectorAll("#side .sign > *").forEach((n, i) => fx.arrive(n, 150 + i * 160, 320, 4));
  }
  rollChanges(!opening && !last.quiet);
  Object.assign(last, { line: id, pick: pickId, signed: !!state.seal.signed, quiet: false });
}

// ---------- motion: a line opens. The dots leave the stores and pass the gates in turn ----------
const centre = (n) => { const r = n.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; };

/** `node` arrives from where `from` sits (the same product, one gate earlier). Before its turn it is not shown. */
function travel(node, from, delay, duration = 460) {
  if (!from) return fx.appear(node, delay, 260);
  const [ax, ay] = centre(from), [bx, by] = centre(node);
  node.animate([{ transform: `translate(${ax - bx}px, ${ay - by}px)`, opacity: 0 }, { opacity: 1, offset: 0.15 }, { transform: "none", opacity: 1 }],
    { duration, delay, easing: fx.EASE, fill: "backwards" });
}

function intro() {
  const gates = [...document.querySelectorAll(".gate")];
  if (gates.length < 4) return;
  const byId = (root) => new Map([...root.querySelectorAll("[data-id]")].map((n) => [n.dataset.id, n]));
  const T = [0, 520, 1080, 1640, 2100];        // when each gate's dots set off; the last entry is the pick card
  // the frame (headers, rulers, ticks) is there from the first frame; counts and bars come up with their gate
  gates.forEach((g, i) => {
    fx.appear(g.querySelector(".n"), T[i] + 150, 300, 0.25);
    const bar = g.querySelector(".meter i");
    if (bar) bar.animate([{ transform: "scaleX(0)" }, { transform: "none" }], { duration: 420, delay: T[i] + 100, easing: fx.EASE, fill: "backwards" });
    g.querySelectorAll(".chip").forEach((c) => fx.appear(c, T[i] + 480, 260));
  });
  [...gates[0].querySelectorAll(".dot")].forEach((n, i) => fx.appear(n, T[0] + i * 9, 180));
  const read = byId(gates[0]);
  const stated = [...gates[1].querySelectorAll(":scope > .dots .dot")], waiting = [...gates[1].querySelectorAll(".tray .dot")];
  stated.forEach((n, i) => travel(n, read.get(n.dataset.id), T[1] + i * 10));
  waiting.forEach((n, i) => travel(n, read.get(n.dataset.id), T[1] + 160 + i * 10));
  const second = byId(gates[1]);
  const rulers = [...gates[2].querySelectorAll("svg.ruler")];
  rulers.forEach((svg, r) => [...svg.querySelectorAll("circle[data-id]")].forEach((n, i) => travel(n, second.get(n.dataset.id), T[2] + r * 120 + i * 12)));
  const third = rulers.length ? byId(rulers[rulers.length - 1]) : new Map();
  const price = gates[3].querySelector("svg.ruler");
  if (price) {
    [...price.querySelectorAll("circle[data-id]")].forEach((n, i) => travel(n, third.get(n.dataset.id), T[3] + i * 22));
    fx.appear(price.querySelector(".ring"), T[4] - 60, 260);
  }
  for (const svg of rulers) fx.appear(svg.querySelector(".ring"), T[3] - 100, 260);
  document.querySelectorAll("#side .card:first-child > *:not(.cap)").forEach((n, i) => fx.arrive(n, T[4] + i * 60, 320, 4));   // the card's frame is there throughout
}

// ---------- motion: the state changed. Only what changed moves ----------
function snapshot() {
  const snap = new Map();
  for (const svg of document.querySelectorAll("svg.ruler")) {
    const k = svg.dataset.ruler;
    for (const c of svg.querySelectorAll("circle[data-id]")) {
      snap.set(k + "|" + c.dataset.id, { x: +c.getAttribute("cx"), y: +c.getAttribute("cy"), cls: c.getAttribute("class"), fill: getComputedStyle(c).fill, at: centre(c) });
    }
    const tick = svg.querySelector(".tk"), ring = svg.querySelector(".ring");
    if (tick) snap.set(k + "|tick", { x: +tick.dataset.x });
    if (ring) snap.set(k + "|ring", { x: +ring.getAttribute("cx"), y: +ring.getAttribute("cy") });
  }
  return snap;
}

function moveChanges(before) {
  if (!before) return;
  const slide = (node, dx, dy, duration = 320, delay = 0) => node.animate([{ transform: `translate(${dx}px, ${dy}px)` }, { transform: "none" }],
    { duration, delay, easing: fx.EASE, fill: "backwards" });
  const rulers = [...document.querySelectorAll("svg.ruler")];
  for (const svg of rulers) {
    const k = svg.dataset.ruler, tick = svg.querySelector(".tk"), was = before.get(k + "|tick");
    const from = was ? was.x : null, to = tick ? +tick.dataset.x : null, tickMoved = from !== null && to !== null && Math.abs(from - to) > 0.5;
    if (tickMoved) {                              // the limit slides along its ruler
      slide(tick, from - to, 0, 340);
      const pass = svg.querySelector(".pass");
      if (pass) pass.animate([{ opacity: 0 }, { opacity: 0.035 }], { duration: 340, easing: "ease-out" });
    }
    const here = new Set();
    for (const c of svg.querySelectorAll("circle[data-id]")) {
      here.add(c.dataset.id);
      const old = before.get(k + "|" + c.dataset.id), x = +c.getAttribute("cx"), y = +c.getAttribute("cy");
      if (!old) {                                 // a dot that came back inside: it returns from its place on the last limit ruler
        const source = k === "price" ? [...rulers].reverse().find((r) => r.dataset.ruler !== "price") : null;
        const twin = source && source.querySelector(`circle[data-id="${CSS.escape(c.dataset.id)}"]`);
        travel(c, twin, 200, 380);
        continue;
      }
      if (Math.abs(old.x - x) > 0.5 || Math.abs(old.y - y) > 0.5) slide(c, old.x - x, old.y - y);
      if (old.cls !== c.getAttribute("class")) {   // it changes side as the tick passes it, not all at once
        const pass = tickMoved ? Math.max(0, Math.min(1, (x - from) / (to - from || 1))) * 300 : 180;
        c.animate([{ fill: old.fill }, { fill: getComputedStyle(c).fill }], { duration: 220, delay: pass, easing: "ease-out", fill: "backwards" });
      }
    }
    for (const [key, old] of before) {            // a dot that left this ruler fades where it stood
      const [rk, id] = [key.slice(0, key.indexOf("|")), key.slice(key.indexOf("|") + 1)];
      if (rk !== k || id === "tick" || id === "ring" || here.has(id)) continue;
      const ghost = document.createElementNS("http://www.w3.org/2000/svg", "g");
      const struck = state.lines.flatMap((l) => l.candidates).some((c) => c.id === id && c.status === "struck");
      ghost.innerHTML = `<circle class="${old.cls.replace("pick", "")}" cx="${old.x}" cy="${old.y}" r="4"/>` +
        (struck ? `<line class="tick" x1="${old.x - 6}" y1="${old.y - 6}" x2="${old.x + 6}" y2="${old.y + 6}"/>` : "");
      svg.appendChild(ghost);
      ghost.animate([{ opacity: 1 }, { opacity: 1, offset: struck ? 0.6 : 0.2 }, { opacity: 0 }], { duration: struck ? 700 : 380, fill: "forwards" })
        .finished.then(() => ghost.remove(), () => ghost.remove());
    }
    const ring = svg.querySelector(".ring"), oldRing = before.get(k + "|ring");   // the ring glides to the new pick
    if (ring && oldRing) {
      const dx = oldRing.x - ring.getAttribute("cx"), dy = oldRing.y - ring.getAttribute("cy");
      if (Math.abs(dx) > 0.5 || Math.abs(dy) > 0.5) slide(ring, dx, dy, 380, 80);
    } else if (ring) fx.appear(ring, 250, 260);
  }
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

function renderTop() {
  const { sheet, seal } = state;
  const mode = state.mode === "fixture" ? "Fixture data" : state.mode === "replay" ? "Replay, cached" : "";
  const at = seal.signed_at || (seal.signature && seal.signature.at);
  const time = at ? new Date(at).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }) : "";
  q("#top").innerHTML = `<span class="brand">Sign-Off</span><span class="sep">/</span>
    <span>${esc(sheet.title)}</span><span class="faint">${state.lines.length} items${sheet.invented ? " · invented" : ""}</span>
    <span class="grow"></span>
    ${mode ? `<span class="pill">${mode}</span>` : ""}${SIM ? `<span class="pill">Simulation</span>` : ""}
    <span class="pill ${seal.signed ? "signed" : ""}">${seal.signed ? "Signed " + time : "Not signed"}</span>
    <span class="total" data-k="total">${money(state.total_cents)}</span>
    <button class="ghost" data-open="shopper" title="${esc(sheet.shopper.name)}'s measurements and her chat with the agent">${esc(sheet.shopper.name)}</button>
    <a class="ghost" href="/?view=detail${location.hash}">Detail</a>`;
}

function renderRail(current) {
  q("#rail").innerHTML = `<div class="cap">Items</div>` + state.lines.map((l) => {
    const p = pickOf(l), s = stages(l);
    const right = l.status === "open" ? "open" : l.status === "pick_up" ? "pick up" : money(p.product.price_cents);
    return `<a class="item" href="#${l.line_id}" aria-current="${l.line_id === current}">
      <i class="st ${l.status}"></i><span class="name">${esc(cap(l.need))}</span><span class="amt" data-k="amt.${l.line_id}">${right}</span>
      <span class="sub">${s.all.length} › ${s.stated.length} › ${s.inside.length} › ${p ? 1 : 0}</span></a>`;
  }).join("");
}

const dot = (c, cls = "") => `<i class="dot ${cls}${c.picked ? " pick" : ""}" data-id="${esc(c.id)}" tabindex="-1"></i>`;

function renderFlow(line, s) {
  const stores = [...new Set(s.all.map((c) => c.product.store))];
  const sheetLine = state.sheet.lines.find((l) => l.id === line.line_id);
  const names = { issuer: state.sheet.issuer.name, shopper: state.sheet.shopper.name };
  // column 1: read, one stack per store
  const read = stores.map((store) => {
    const mine = s.all.filter((c) => c.product.store === store);
    return `<div class="grp"><div class="lab"><span>${esc(store)}</span><span>${mine.length}</span></div><div class="dots">${mine.map((c) => dot(c)).join("")}</div></div>`;
  }).join("");
  // column 2: the pages that state every deciding figure; the rest wait in the one dashed tray
  const missing = new Map();
  for (const c of s.unstated) {
    const k = words((c.checks.find((ch) => ch.state === "not_stated") || {}).missing_figure || "a figure");
    missing.set(k, (missing.get(k) || 0) + 1);
  }
  const trayOpen = ui.open.has("unstated");
  const tray = s.unstated.length ? `<div class="tray"><div class="dots">${s.unstated.map((c) => dot(c, "none")).join("")}</div>
      <button class="chip" data-toggle="unstated" aria-expanded="${trayOpen}">${s.unstated.length} not stated</button>
      ${trayOpen ? `<div class="more">${[...missing].map(([k, n]) => `<b>${n}</b><span>${esc(k)}</span>`).join("")}</div>` : ""}</div>` : "";
  // column 3: one ruler per limit
  const rulers = sheetLine.limits.map((limit, i) => {
    const b = limit.bound, owner = b.source === "issuer" ? "issuer" : "shopper";
    return `<div class="grp"><div class="lab"><span><i class="od ${owner}"></i>${esc(names[owner])} · ${esc(limit.name)}</span></div>
      <svg class="ruler" data-ruler="${i}" height="60"></svg></div>`;
  }).join("");
  const chips3 = [s.outside.length ? `<button class="chip" data-toggle="outside" aria-expanded="${ui.open.has("outside")}">${s.outside.length} outside</button>` : "",
    s.struck.length ? `<span class="chip"><i class="od issuer"></i>${s.struck.length} struck</span>` : ""].join("");
  const outsideBy = new Map();
  for (const c of s.outside) { const k = (c.checks.find((ch) => !ch.pass) || {}).name || "a limit"; outsideBy.set(k, (outsideBy.get(k) || 0) + 1); }
  // column 4: the shopper's rule
  const rule = s.local ? "cheapest, picked up" : "cheapest with delivery";
  const meter = (n) => `<div class="meter"><i style="width:${s.all.length ? (n / s.all.length) * 100 : 0}%"></i></div>`;
  q("#main").innerHTML = `<div class="head"><h1>${esc(cap(line.need))}</h1><span class="muted">${esc(STATUS[line.status] || line.status)}</span></div>
    <div class="gates">
      <section class="gate"><div class="gh"><span class="label">Read</span><span class="n" data-k="n.read">${s.all.length}</span></div>${meter(s.all.length)}
        <div class="by">${stores.length} stores</div>${read}</section>
      <section class="gate"><div class="gh"><span class="label">State the figures</span><span class="n" data-k="n.stated">${s.stated.length}</span></div>${meter(s.stated.length)}
        <div class="by"><i class="od store"></i>the store's words</div>
        <div class="dots">${s.stated.map((c) => dot(c)).join("")}</div>${tray}</section>
      <section class="gate"><div class="gh"><span class="label">Inside limits</span><span class="n" data-k="n.inside">${s.inside.length}</span></div>${meter(s.inside.length)}
        <div class="by">${sheetLine.limits.length} limits</div>${s.stated.length ? rulers : ""}
        <div class="chips">${chips3}</div>
        ${ui.open.has("outside") ? `<div class="more">${[...outsideBy].map(([k, n]) => `<b>${n}</b><span>${esc(k)}</span>`).join("")}</div>` : ""}</section>
      <section class="gate"><div class="gh"><span class="label">Pick</span><span class="n">${s.pick ? 1 : 0}</span></div>${meter(s.pick ? 1 : 0)}
        <div class="by"><i class="od shopper"></i>${esc(names.shopper)} · ${esc(rule)}</div>
        ${s.inside.length ? `<svg class="ruler" data-ruler="price" height="60"></svg>` : `<div class="muted">Nothing proposed</div>`}
        <div class="chips">${s.noDelivery.length ? `<span class="chip">${s.noDelivery.length} no delivery time</span>` : ""}</div></section>
    </div>`;
  // the rulers are drawn once their boxes have a width
  if (s.stated.length) {
    sheetLine.limits.forEach((limit, i) => {
      const sample = s.stated[0].checks[i];
      drawRuler(q(`[data-ruler="${i}"]`), s.stated.map((c) => ({ c, v: c.checks[i].lhs, cls: c.status === "inside" ? "" : "out" })),
        { v: sample.bound.value, op: sample.op, label: `${num(sample.bound.value, sample.bound.unit)} ${sample.bound.unit}` },
        (v) => num(v, sample.bound.unit === "in" ? "" : sample.bound.unit));
    });
  }
  if (s.inside.length) {
    drawRuler(q(`[data-ruler="price"]`), s.inside.map((c) => ({ c, v: c.product.price_cents / 100, cls: s.eligible.includes(c) ? "" : "nodel" })),
      null, (v) => "$" + Math.round(v));
  }
}

/** A thin horizontal axis; each dot sits at its value, equal values stack upward; the limit is a tick. */
const domains = new Map();   // a ruler keeps its range while a limit moves; it only grows
function drawRuler(svg, items, tick, fmt) {
  const W = svg.clientWidth || 240, pad = 8, step = 9, r = 4;
  const key = lineId() + "|" + svg.dataset.ruler;
  const dom = niceDomain(items.map((d) => d.v).concat(tick ? [tick.v] : []), domains.get(key));
  domains.set(key, dom);
  const px = (v) => pad + ((v - dom.lo) / (dom.hi - dom.lo)) * (W - 2 * pad);
  const columns = new Map();
  const rank = (d) => (d.c.picked ? 3 : d.cls === "" ? 2 : 1);
  const placed = [...items].sort((a, b) => rank(b) - rank(a)).map((d) => {
    const k = Math.round(px(d.v) / step), n = columns.get(k) || 0;
    columns.set(k, n + 1);
    return { ...d, x: k * step, n };
  });
  const tallest = Math.max(1, ...columns.values()), top = tick ? 18 : 6, base = top + tallest * step + 4, H = base + 18;
  svg.setAttribute("height", H);
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  let out = "";
  if (tick) {
    const tx = px(tick.v), right = tick.op === ">=";
    out += `<rect class="pass" x="${right ? tx : pad}" y="${top}" width="${Math.max(0, right ? W - pad - tx : tx - pad)}" height="${base - top}"/>`;
    const anchor = tx > W - 50 ? "end" : tx < 50 ? "start" : "middle";
    out += `<g class="tk" data-x="${tx}"><line class="tick" x1="${tx}" x2="${tx}" y1="${top - 2}" y2="${base}"/>
      <text class="ticklabel" x="${tx}" y="${top - 6}" text-anchor="${anchor}">${esc(tick.label)}</text></g>`;
  }
  out += `<line class="axis" x1="${pad}" x2="${W - pad}" y1="${base}" y2="${base}"/>`;
  out += `<text x="${pad}" y="${base + 14}">${esc(fmt(dom.lo))}</text><text x="${W - pad}" y="${base + 14}" text-anchor="end">${esc(fmt(dom.hi))}</text>`;
  for (const d of placed.reverse()) {
    const cy = base - r - 2 - d.n * step;
    if (d.c.picked) out += `<circle class="ring" cx="${d.x}" cy="${cy}" r="${r + 2.5}"/>`;
    out += `<circle class="${d.cls}${d.c.picked ? " pick" : ""}" data-id="${esc(d.c.id)}" cx="${d.x}" cy="${cy}" r="${r}"/>`;
  }
  svg.innerHTML = out;
}

/** The part of the store's sentence that carries the figure, with the figure marked. */
function fragment(term, max = 30) {
  const text = term.quote || "";
  const [s, e] = figureSpan(text, term);
  let from = Math.max(0, s - max);
  if (from > 0) from = text.indexOf(" ", from) + 1 || from;
  const before = text.slice(from, s).replace(/^[\s•\-:,;]+/, "");
  return `${from > 0 ? "…" : ""}${esc(before)}<mark>${esc(text.slice(s, e))}</mark>`;
}

/** The receipt chain, when the engine reports it: a thin strip of links and "14 of 14 receipts verified". */
function receiptsRow() {
  const r = state.receipts;
  if (!r || !r.count) return "";
  const ok = r.verified === true || r.verified === r.count, n = Math.min(r.count, 24);
  const good = typeof r.verified === "number" ? r.verified : ok ? r.count : (r.first_bad ? r.first_bad - 1 : 0);
  return `<div class="chain" title="Tamper-evident: each receipt carries the hash of the one before">${Array.from({ length: n }, (_, i) => `<i class="${i < Math.round((good / r.count) * n) ? "" : "bad"}"></i>`).join("")}</div>
    <div class="muted small">${good} of ${r.count} receipts verified</div>`;
}

function renderSide(line, s) {
  const { sheet, seal } = state, p = s.pick;
  let card;
  if (p) {
    const evidence = p.checks.map((ch, i) => {
      const term = ch.terms.find((t) => t.owner === "store");
      const all = s.stated.map((c) => c.checks[i].lhs).concat([ch.bound.value]);
      const dom = niceDomain(all), pc = (v) => Math.max(0, Math.min(100, ((v - dom.lo) / (dom.hi - dom.lo)) * 100));
      const a = pc(Math.min(ch.lhs, ch.bound.value)), b = pc(Math.max(ch.lhs, ch.bound.value));
      return `<div class="ev"><div class="row"><span>${esc(cap(ch.name))}</span><span class="margin"><span class="tickmark">✓</span> ${esc(marginText(ch))}</span></div>
        <div class="frag">${term ? fragment(term) : ""}</div>
        <div class="bar" title="${esc(ch.expr)}"><i class="fill" style="left:${a}%;width:${b - a}%"></i><i class="lim ${ch.bound.owner}" style="left:${pc(ch.bound.value)}%"></i><i class="val" style="left:${pc(ch.lhs)}%"></i></div></div>`;
    }).join("");
    card = `<section class="card"><div class="cap">Pick</div><h2 title="${esc(p.product.title)}">${esc(p.product.title)}</h2>
      <div class="row"><span class="muted"><i class="od store"></i>${esc(p.product.store)}</span><span class="price" data-k="pick.price">${money(p.product.price_cents)}</span></div>
      ${evidence}<button class="link" data-open="${esc(p.id)}">Evidence</button></section>`;
  } else {
    card = `<section class="card"><div class="cap">Pick</div><h2>Nothing proposed</h2><div class="muted">${esc(cap(line.reason || "no product yet"))}</div></section>`;
  }
  let sign;
  if (seal.signed) {
    const sig = seal.signature || {}, persona = sig.persona || (state.issuer_key && state.issuer_key.persona) || {};
    const who = seal.signer || (sig.signer && sig.signer.name) || sheet.issuer.name, hash = seal.sheet_hash || sig.sheet_hash || "";
    const at = seal.signed_at || sig.at, time = at ? new Date(at).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }) : "";
    const status = persona.inquiry_id ? (persona.verified ? "checked" : words(persona.status || "started")) : "not checked";
    sign = `<section class="card sign signed"><div class="cap">Signature</div>
      <div class="row"><span class="who"><span class="tickmark">\u2713</span> Signed by ${esc(who)}</span><span>${time}</span></div>
      ${hash ? `<div class="row"><span class="muted">Sheet hash</span><code title="${esc(hash)}">${esc(hash.slice(0, 12))}</code></div>` : ""}
      <div class="muted small">Covers limits, quotes, picks, total</div>
      <div class="row"><span class="muted">Persona</span><span title="${esc(persona.inquiry_id || "")}">${esc(status)} \u00b7 sandbox</span></div>
      ${receiptsRow()}
      ${(seal.carts || []).map((c) => `<div class="row cart"><a href="${esc(c.cart_url)}" target="_blank" rel="noopener">${esc(c.store)} cart \u2197</a><span>${c.total_cents ? money(c.total_cents) : ""}</span></div>`).join("") || `<div class="muted">No cart link</div>`}</section>`;
  } else {
    sign = `<section class="card sign"><div class="cap">Signature</div>
      <div class="who">${esc(sheet.issuer.name)} must sign</div><div class="muted">No cart exists</div>${receiptsRow()}</section>`;
  }
  q("#side").innerHTML = card + sign;
}

// ---------- the drawer: everything longer than a label ----------
function factsOfLine(sheetLine) {
  const ids = new Set();
  for (const limit of sheetLine.limits) {
    for (const t of limit.terms) if (t.source === "shopper") ids.add(t.fact);
    if (limit.bound.source === "shopper") ids.add(limit.bound.fact);
  }
  return state.sheet.shopper_facts.filter((f) => ids.has(f.id));
}
const slider = (kind, id, label, value, unit, b) => `<label class="field"><span>${esc(cap(label))}</span><output>${num(value, unit)} ${esc(unit)}</output>
  <input type="range" data-kind="${kind}" data-id="${esc(id)}" data-unit="${esc(unit)}" min="${b.min}" max="${b.max}" step="${b.step}" value="${value}"></label>`;
const chatHtml = (t) => `<p class="said">\u201c${esc(t.text)}\u201d</p><p>${t.refused ? '<span class="refused">Refused</span> ' : ""}${esc(t.reply)}</p>`;

/** The shopper's sheet: her measurements for this line and her chat with the agent. In ?sim=1 also the limits. */
function renderShopper(el, line) {
  if (el.dataset.for === "shopper:" + line.line_id && el.contains(document.activeElement) && document.activeElement !== document.body) {
    for (const input of el.querySelectorAll("input[type=range]")) {     // keep the control being used; refresh the readouts
      const f = state.sheet.shopper_facts.find((x) => x.id === input.dataset.id);
      if (f && input.dataset.kind === "fact") input.previousElementSibling.textContent = `${num(f.value, f.unit)} ${f.unit}`;
    }
    return;
  }
  el.dataset.for = "shopper:" + line.line_id;
  const sheetLine = state.sheet.lines.find((l) => l.id === line.line_id), shopper = state.sheet.shopper;
  const facts = factsOfLine(sheetLine), last = ui.chat[ui.chat.length - 1];
  el.innerHTML = `<button class="x" data-close>Close</button>
    <h2><i class="od shopper"></i>${esc(shopper.name)}${shopper.invented ? " \u00b7 invented shopper" : ""}</h2>
    ${facts.map((f) => slider("fact", f.id, f.label, f.value, f.unit, f)).join("") || `<p>No measurement on this item</p>`}
    ${SIM ? `<h3>Simulation only, not ${esc(state.sheet.issuer.name)}'s phone</h3>` + sheetLine.limits.filter((l) => l.bound.source === "issuer")
      .map((l) => slider("limit", l.id, l.label, l.bound.value, l.unit, l.bound)).join("") : ""}
    <h3>Ask the agent</h3>
    <form id="say"><input id="sayText" name="say" type="text" autocomplete="off" aria-label="Message to the agent" placeholder="Put the struck one back\u2026"><button class="ghost" type="submit">Send</button></form>
    <div id="reply" aria-live="polite">${last ? chatHtml(last) : ""}</div>`;
}

function renderDrawer(line) {
  const el = q("#drawer");
  if (ui.drawer === "shopper") { el.hidden = false; return renderShopper(el, line); }
  const c = ui.drawer === "pick" ? pickOf(line) : line.candidates.find((x) => x.id === ui.drawer);
  el.hidden = !c;
  el.dataset.for = "";
  if (!c) return;
  const seen = new Set(), quotes = [];
  for (const ch of c.checks) for (const t of ch.terms) {
    if (t.owner !== "store" || !t.quote || seen.has(t.figure)) continue;
    seen.add(t.figure);
    const [s, e] = figureSpan(t.quote, t);
    quotes.push(`<h3>${esc(cap(words(t.figure)))}</h3><p>“${esc(t.quote.slice(0, s))}<mark>${esc(t.quote.slice(s, e))}</mark>${esc(t.quote.slice(e))}”</p>`);
  }
  const why = c.picked ? "The pick" : c.status === "inside" ? "Inside the limits, not the pick" : cap(c.reason || c.status);
  el.innerHTML = `<button class="x" data-close>Close</button>
    <h2>${esc(c.product.title)}</h2>
    <p>${money(c.product.price_cents)} · ${esc(c.product.store)} · <a class="link" href="${esc(c.product.url)}" target="_blank" rel="noopener">Store page ↗</a></p>
    <p><b>${esc(why)}</b></p>
    ${c.checks.map((ch) => `<p>${esc(cap(ch.name))}: ${ch.expr ? esc(ch.expr.replace(">=", "≥").replace("<=", "≤")) + ", " : ""}${esc(marginText(ch))}</p>`).join("")}
    ${quotes.join("")}
    ${c.arrival ? `<h3>Delivery, stated not guaranteed</h3><p>${c.arrival.quote ? "“" + esc(c.arrival.quote) + "”" : "Not stated"}</p>` : ""}
    ${c.undo && c.undo.quote ? `<h3>Returns, in the store agent's words</h3><p>“${esc(c.undo.quote)}”</p>` : ""}
    <h3>Method</h3><p>The model reads the figure; code checks that the quote is in the store's text and does the sums.</p>
    <p><a class="link" href="/?view=detail&panel=sql#${line.line_id}">SQL for this line</a></p>`;
}

// ---------- the shopper's controls ----------
let factTimer = null;
document.addEventListener("input", (e) => {
  const input = e.target.closest("input[type=range]");
  if (!input) return;
  const value = parseFloat(input.value), id = input.dataset.id;
  input.previousElementSibling.textContent = `${num(value, input.dataset.unit)} ${input.dataset.unit}`;
  if (input.dataset.kind === "limit") { ui.sim.limits[id] = value; return apply(); }
  if (SIM) { ui.sim.facts[id] = value; return apply(); }
  clearTimeout(factTimer);
  factTimer = setTimeout(async () => {
    try {
      const res = await fetch("/api/shopper/fact", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ fact_id: id, value }) });
      if (!res.ok) throw new Error(res.status);
      load();
    } catch (error) { q("#reply").innerHTML = `<p>The engine did not take the change (${esc(error.message)}).</p>`; }
  }, 60);
});
document.addEventListener("submit", async (e) => {
  if (e.target.id !== "say") return;
  e.preventDefault();
  const box = q("#sayText"), text = box.value.trim();
  if (!text || ui.busy) return;
  ui.busy = true;
  q("#reply").innerHTML = `<p class="said">\u201c${esc(text)}\u201d</p><p>\u2026</p>`;
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

// ---------- interaction ----------
document.addEventListener("click", (e) => {
  const t = e.target.closest("[data-toggle], [data-open], [data-close], [data-id]");
  if (!t || t.matches("input")) return;
  if (t.dataset.toggle) { ui.open.has(t.dataset.toggle) ? ui.open.delete(t.dataset.toggle) : ui.open.add(t.dataset.toggle); }
  else if (t.dataset.close !== undefined) ui.drawer = null;
  else ui.drawer = t.dataset.open || t.dataset.id;
  render();
});
addEventListener("keydown", (e) => {
  if (e.key === "Escape" && ui.drawer) { ui.drawer = null; render(); }
  if (e.target.tagName === "INPUT") return;
  if (e.key === "e") { e.preventDefault(); ui.drawer = ui.drawer === "shopper" ? null : "shopper"; render(); q("#sayText")?.focus(); }
  const n = parseInt(e.key, 10);
  if (state && n >= 1 && n <= state.lines.length && !e.metaKey && !e.ctrlKey) location.hash = state.lines[n - 1].line_id;
});
const tip = q("#tip");
document.addEventListener("mouseover", (e) => {
  const t = e.target.closest("[data-id]");
  for (const n of document.querySelectorAll(".hl")) n.classList.remove("hl");
  if (!t || !state) { tip.hidden = true; return; }
  for (const n of document.querySelectorAll(`[data-id="${CSS.escape(t.dataset.id)}"]`)) n.classList.add("hl");
  const c = state.lines.flatMap((l) => l.candidates).find((x) => x.id === t.dataset.id);
  if (!c) return;
  const why = c.picked ? "the pick" : c.status === "inside" ? "inside" : c.reason || c.status;
  tip.textContent = `${c.product.title} · ${money(c.product.price_cents)} · ${c.product.store} · ${why}`;
  tip.hidden = false;
  const r = t.getBoundingClientRect();
  tip.style.left = Math.min(innerWidth - 330, Math.max(8, r.left - 20)) + "px";
  tip.style.top = (r.bottom + 8) + "px";
});

load();
