// The memory graph for one item. Everything drawn comes from GET /api/graph?line_id=; the page decides nothing.
// Five columns, left to right: who, what they said, the rule, the product's own words, the outcome.
// Click a node: its full text, owner and source. With nothing selected the side shows Cognee's answer.
// ?line_id=L5 picks the item, ?node=<id> opens a node, ?live=0 stops the refresh (for screenshots).
import * as XP from "/graph/explore.js";

const params = new URLSearchParams(location.search);
const MOTION = params.get("motion") !== "0" && !matchMedia("(prefers-reduced-motion: reduce)").matches && !navigator.webdriver;
const LIVE = params.get("live") !== "0";
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const cap = (s) => String(s || "").charAt(0).toUpperCase() + String(s || "").slice(1);

// Sizes follow the page's rem (style.css scales it with the window): column widths, node height, row pitch,
// space between products, right margin for the stores' lanes.
const REM = parseFloat(getComputedStyle(document.documentElement).fontSize) / 16;
const [WIDTHS, H, ROW, GROUP, BUS] = [[150, 150, 150, 124, 210].map((w) => w * REM), 42 * REM, 54 * REM, 14 * REM, 30 * REM];
const KIND = { event: "Event", context_person: "Person", context_message: "Message", context_fact: "Fact, quoted", sheet_value: "On the order",
  memory: "Memory", message: "Message to the store's agent", reply: "The store's reply", web: "Web search", review: "Review, quoted", gate: "The gate", cart: "Cart",
  person: "Person", store: "Store", order_item: "Order item", home_fact: "Home fact", limit: "Rule",
  statement: "Page quote", product: "Product", strike: "Strike", purchase: "Signature" };
const STATUS = { inside: "meets the order", outside: "outside", unclear: "unclear", not_stated: "not stated", struck: "struck" };

let data = null, cognee = null, answer = null, stamp = "", sel = params.get("node"), line = params.get("line_id");
// Two views of one item: the run growing as a graph (the default), and the five-column detail of the decision.
let whole = false;
let view = params.get("view") === "detail" ? "detail" : "explore", xdata = null, xkey = "", opened = false;
const active = () => (view === "explore" && xdata?.nodes ? xdata : data);

const ownerClass = (o) => (o === "issuer" || o === "shopper" ? o : o === "system" ? "" : "store");
const ownerName = (o) => (data.people[o] || (o === "system" ? "the agent's code" : o === "web" ? "another site" : o));
const dot = (o) => `<i class="od ${ownerClass(o)}"></i>`;
const clock = (at) => (at ? String(at).slice(11, 16) : "");
function dur(s) {
  if (s == null) return "";
  s = Math.round(s);
  return s < 60 ? s + " s" : Math.floor(s / 60) + " min" + (s % 60 ? " " + (s % 60) + " s" : "");
}

// ---------- layout ----------
function layout() {
  const nodes = new Map(data.nodes.map((n) => [n.id, n]));
  const out = (id, verb) => data.edges.filter((e) => e.from === id && e.verb === verb);
  const limits = data.nodes.filter((n) => n.kind === "limit");
  const limitAt = (id) => limits.findIndex((l) => l.id === id);
  const stage = $("#stage"), width = stage.clientWidth;
  const gap = (width - BUS - WIDTHS.reduce((a, b) => a + b, 0)) / 4;
  const x = (c) => WIDTHS.slice(0, c).reduce((a, b) => a + b, 0) + c * gap;
  const pos = new Map(), ghosts = [];
  let y = 0;
  const products = data.nodes.filter((n) => n.kind === "product")
    .sort((a, b) => (b.picked - a.picked) || (a.price_cents - b.price_cents));
  for (const p of products) {
    const slots = [
      ...out(p.id, "states").map((e) => ({ node: nodes.get(e.to), at: limitAt((data.edges.find((d) => d.from === e.to && nodes.get(d.to)?.kind === "limit") || {}).to) })),
      ...out(p.id, "does not state").map((e) => ({ ghost: e, at: limitAt(e.to) })),
    ].sort((a, b) => a.at - b.at);
    const rows = Math.max(1, slots.length), top = y;
    slots.forEach((s, i) => {
      const at = { x: x(3), w: WIDTHS[3], y: top + i * ROW };
      if (s.node) pos.set(s.node.id, at);
      else ghosts.push({ ...at, edge: s.ghost, product: p.id, limit: nodes.get(s.ghost.to) });
    });
    pos.set(p.id, { x: x(4), w: WIDTHS[4], y: top + ((rows - 1) * ROW) / 2 });
    y = top + rows * ROW;
    for (const e of data.edges.filter((d) => d.to === p.id && ["strike", "purchase"].includes(nodes.get(d.from)?.kind))) {
      if (!pos.has(e.from)) { pos.set(e.from, { x: x(4), w: WIDTHS[4], y }); y += ROW; }
    }
    y += GROUP;
  }
  const fold = data.folded.products ? { x: x(4), w: WIDTHS[4], y } : null;
  if (fold) y += ROW;
  const block = Math.max(y - GROUP, 3 * ROW);
  // who and what they said: one stack, centred beside the products; each rule spread to face its quotes
  const people = data.nodes.filter((n) => n.kind === "person");
  const said = [...data.nodes.filter((n) => n.kind === "order_item"), ...data.nodes.filter((n) => n.kind === "home_fact")];
  const stackTop = Math.max(0, (block - Math.max(people.length, said.length) * ROW) / 2);
  people.forEach((n, i) => pos.set(n.id, { x: x(0), w: WIDTHS[0], y: stackTop + i * ROW }));
  said.forEach((n, i) => pos.set(n.id, { x: x(1), w: WIDTHS[1], y: stackTop + i * ROW }));
  limits.forEach((n, i) => pos.set(n.id, { x: x(2), w: WIDTHS[2], y: (block * (i + 0.5)) / limits.length - H / 2 }));
  // the stores, below everything: each has its own lane along the bottom and up the right side
  const stores = [];                                                 // a store is named on its product, not drawn apart
  const height = block + GROUP;
  return { nodes, pos, ghosts, fold, width, height, gap, x, stores };
}

function curve(a, b) {
  const x1 = a.x + a.w, y1 = a.y + H / 2, x2 = b.x, y2 = b.y + H / 2, m = (x1 + x2) / 2;
  return { d: `M${x1} ${y1}C${m} ${y1} ${m} ${y2} ${x2} ${y2}`, lx: m, ly: (y1 + y2) / 2 + 3 };
}

function controls() {
  // drawn before the canvas is measured, so the canvas keeps its height
  if ($("#scrub")) return;
  $("#ctl").innerHTML = `<button class="chip" data-play>Play</button><button class="chip" data-step="-1" aria-label="Back">‹</button><button class="chip" data-step="1" aria-label="Next">›</button>
    <input type="range" id="scrub" min="0" max="1" step="1" aria-label="Stage"><span class="cap" id="count">1 of 1</span>`;
  $("#scrub").addEventListener("input", (e) => { XP.play(false); XP.jump(Number(e.target.value)); });
}

function renderStage(s, k, n) {
  $("#heads").innerHTML = `<span class="st"><b>${esc(s.title)}</b>${esc(s.caption)}${s.at ? `<i>${esc(clock(s.at))}</i>` : ""}</span>`;
  controls();
  $("#scrub").max = n - 1; $("#scrub").value = k;
  $("#count").textContent = `${k + 1} of ${n}`;
  $("[data-play]").textContent = XP.playing() ? "Pause" : "Play";
}

function drawExplore() {
  $("#ctl").hidden = false;
  controls();
  if (!$("#heads").innerHTML) $("#heads").innerHTML = `<span class="st"><b>&nbsp;</b></span>`;
  if (!xdata?.stages) { $("#stage").innerHTML = ""; $("#heads").innerHTML = ""; return; }
  const key = JSON.stringify([xdata, innerWidth, innerHeight]);
  if (key === xkey) return;
  const same = xkey && JSON.parse(xkey)[0].line_id === xdata.line_id;
  xkey = key;
  // a new item opens at the start and plays; fresh records for the same item keep the stage on screen
  const asked = params.get("stage"), last = xdata.stages.length - 1;
  const at = same ? XP.stage() : asked != null ? Number(asked) : MOTION ? 0 : last;
  XP.mount($("#stage"), xdata, { onSelect: (id) => { sel = id; renderSide(); }, onStage: renderStage }, { stage: at, motion: MOTION });
  if (!same && asked == null && MOTION) XP.play(true);
}

function draw() {
  if (view === "explore") return drawExplore();
  $("#ctl").hidden = true; xkey = "";
  const L = layout(), { nodes, pos } = L;
  const near = new Set();
  if (sel && nodes.has(sel)) {
    near.add(sel);
    data.edges.forEach((e) => { if (e.from === sel) near.add(e.to); if (e.to === sel) near.add(e.from); });
  }
  const lit = (e) => sel && (e.from === sel || e.to === sel);
  const state = (e) => (!sel || !nodes.has(sel) ? "" : lit(e) ? " lit" : " dim");
  let paths = "", labels = "";
  for (const e of data.edges) {
    let a = pos.get(e.from), b = pos.get(e.to);
    if (!a || !b) continue;
    if (e.verb === "sold by") {
      // the store's lane: along the bottom, up the right margin, into the product from the right
      const i = L.stores.findIndex((s) => s.id === e.to), bx = L.x(4) + WIDTHS[4] + 10 + i * 7, sy = b.y + H / 2, py = a.y + H / 2, r = 6;
      paths += `<path class="far${state(e)}" d="M${b.x + b.w} ${sy}H${bx - r}Q${bx} ${sy} ${bx} ${sy - r}V${py + r}Q${bx} ${py} ${bx - r} ${py}H${a.x + a.w}"/>`;
      continue;
    }
    if (e.verb === "does not state") continue;                      // drawn with its empty slot below
    if (a.x > b.x) [a, b] = [b, a];
    const c = curve(a, b), cls = ["passes", "fails", "unclear"].includes(e.verb) ? e.verb : "";
    paths += `<path class="${cls}${state(e)}" d="${c.d}"/>`;
    // a verdict is written beside the quote it judges, where no other line passes; other verbs at the middle
    const at = cls ? { x: b.x - 24, y: b.y + H / 2 + 3 } : { x: c.lx, y: c.ly };
    labels += `<text class="${cls}${state(e)}" x="${at.x}" y="${at.y}">${esc(e.verb)}</text>`;
  }
  let html = "";
  for (const g of L.ghosts) {                                        // a figure the page does not state: an empty slot
    const lim = pos.get(g.edge.to), prod = pos.get(g.product);
    if (lim) paths += `<path class="none${state(g.edge)}" d="${curve(lim, g).d}"/>`;
    if (prod) paths += `<path class="none${state(g.edge)}" d="${curve(g, prod).d}"/>`;
    html += `<div class="n ghost" style="left:${g.x}px;top:${g.y}px;width:${g.w}px;height:${H}px"><span class="l"><b>does not state</b></span><span class="s">${esc(g.limit?.label || "")}</span></div>`;
  }
  L.stores.forEach((s) => {
    const p = pos.get(s.id);
    labels += `<text class="${sel && !near.has(s.id) ? "dim" : ""}" x="${p.x + p.w + 26}" y="${p.y + H / 2 - 5}">sold by</text>`;
  });
  for (const n of data.nodes) {
    const p = pos.get(n.id);
    if (!p) continue;
    let sub = n.sub || "", mark = "";
    if (n.kind === "product") sub = [n.picked ? "the pick" : STATUS[n.status] || n.status, (n.sub || "").split(" · ")[0], n.owner].filter(Boolean).join(" · ");
    if (n.kind === "statement" && n.state) mark = `<span class="v ${n.state}">${n.state === "pass" ? "✓" : n.state === "fail" ? "✕" : "?"}</span>`;
    if (n.kind === "product" && n.picked) mark = `<span class="v pass">✓</span>`;
    const cls = ["n", n.picked ? "pick" : "", sel === n.id ? "sel" : "", sel && nodes.has(sel) && !near.has(n.id) ? "dim" : ""].filter(Boolean).join(" ");
    html += `<button class="${cls}" data-id="${esc(n.id)}" title="${esc(KIND[n.kind])}: ${esc(n.label)}" style="left:${p.x}px;top:${p.y}px;width:${p.w}px;height:${H}px">
      <span class="l">${dot(n.owner)}<b>${esc(n.label)}</b>${mark}</span><span class="s">${esc(sub)}</span></button>`;
  }
  if (L.fold) {
    const by = Object.entries(data.folded.by_status).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${v} ${STATUS[k] || k}`).join(" · ");
    html += `<button class="n fold${sel === "fold" ? " sel" : ""}" data-id="fold" title="${esc(by)}" style="left:${L.fold.x}px;top:${L.fold.y}px;width:${L.fold.w}px;height:${H}px"><span class="l"><b>${data.folded.products} more products</b></span><span class="s">${esc(by)}</span></button>`;
  }
  $("#stage").innerHTML = `<svg width="${L.width}" height="${L.height}">${paths}${labels}</svg>${html}<div style="position:absolute;top:${L.height}px;height:1px;width:1px"></div>`;
  $("#heads").innerHTML = data.columns.map((c, i) => `<span style="left:${L.x(i)}px">${esc(cap(c))}</span>`).join("");
}

// ---------- top bar, band, side ----------
function renderTop() {
  const s = data.sheet || {}, b = data.bar || {};
  const mode = b.mode === "fixture" ? "fixture data" : b.mode === "replay" ? "replay of cached store data" : "";
  const meta = [b.items ? `${b.items} items` : "", s.invented ? "invented people, real stores" : "", mode].filter(Boolean).join(" · ");
  $("#top").innerHTML = `<span class="brand">Sign-Off</span><span class="sheet">${esc(s.title || "")}</span>
    <nav class="tabs" aria-label="Views"><a href="/">Decision</a><a href="/trail/">Trail</a><a href="/graph/" aria-current="page">Memory</a><a href="/talk/">Conversations</a><a href="/seal/">Signature</a></nav>
    <span class="meta">${esc(meta)}</span><span class="grow"></span>
    <span class="pill ${b.signed ? "signed" : ""}">${b.signed ? "Signed " + clock(b.signed_at) : "Not signed"}</span>
    ${typeof b.total_cents === "number" ? `<span class="total">$${(b.total_cents / 100).toFixed(2)}</span>` : ""}`;
}

function renderBand() {
  const chips = data.lines.map((l) => `<button class="chip" data-line="${esc(l.line_id)}" aria-pressed="${l.line_id === data.line_id}">${esc(cap(l.need))}</button>`).join("")
    + `<span class="seg"><button class="chip" data-view="explore" aria-pressed="${view === "explore"}">The run</button><button class="chip" data-view="detail" aria-pressed="${view === "detail"}">The decision</button></span>`;
  const who = [["issuer", data.people.issuer], ["shopper", data.people.shopper], ["store", "a store"]]
    .map(([c, n]) => `<span><i class="od ${c}"></i>${esc(n)}</span>`).join("");
  $("#band").innerHTML = `${chips}<span class="grow"></span>
    <span class="legend" title="The mark shows whose knowledge it is">${who}</span>
    <span class="pill" title="${esc(data.backend_note)}">Graph: the run's records</span>
    <span class="pill ${answer?.answered ? "signed" : ""}">${answer?.answered ? "Answer: Cognee" : "Cognee: no answer"}</span>`;
}

function sourceLine(s) {
  if (!s) return "";
  const span = s.start != null ? ` · characters ${s.start}–${s.end}` : "";
  if (s.record === "order") return `<code>${esc(s.file)}</code>${span}`;
  if (s.record === "sheet") return `<code>${esc(s.file)}</code> · <code>${esc(s.pointer)}</code>`;
  if (s.record === "receipt") return `receipt ${s.n} · <code>${esc(String(s.hash).slice(0, 16))}</code> · ${esc(clock(s.at))}`;
  if (s.record === "store_page") return `<a class="link" href="${esc(s.url)}" target="_blank" rel="noopener">${esc(String(s.url).replace(/^https?:\/\/(www\.)?/, ""))}</a>${span} · read ${esc(clock(s.fetched_at))}`;
  if (s.record === "context") return `${s.from_label ? esc(s.from_label) + " · " + esc(s.channel || "") + " · " + esc(String(s.at || "").slice(0, 10)) + " " + esc(clock(s.at)) + " · " : ""}<code>${esc(s.file)}</code>${s.pointer ? " · <code>" + esc(s.pointer) + "</code>" : ""}${span}`;
  if (s.record === "talk") return `conversation <code>${esc(s.thread)}</code> · message ${esc(s.n)} · ${esc(clock(s.at))} · <a class="link" href="/talk/">conversations</a>`;
  if (s.record === "web_page") return `<a class="link" href="${esc(s.url)}" target="_blank" rel="noopener">${esc(String(s.url).replace(/^https?:\/\/(www\.)?/, "").slice(0, 60))}</a> · read ${esc(clock(s.fetched_at))}`;
  if (s.record === "ledger") return `outbound ledger · rows ${esc((s.rows || []).join(", "))} · <a class="link" href="/trail/">trail</a>`;
  if (s.record === "memory") return `memory <code>${esc(s.memory_id)}</code> · ${s.hash ? "receipt <code>" + esc(String(s.hash).slice(0, 12)) + "</code>" : "<code>" + esc(s.file || "") + "</code>"} · ${esc(clock(s.at))}`;
  if (s.record === "store_answer") return `${esc(s.store)}'s agent · asked ${esc(clock(s.asked_at))}`;
  return `<code>${esc(JSON.stringify(s))}</code>`;
}

function quoted(n) {
  const text = n.text || n.label || "";
  const at = n.quote ? text.indexOf(n.quote) : -1;
  if (at < 0) return esc(text);
  return esc(text.slice(0, at)) + "<mark>" + esc(n.quote) + "</mark>" + esc(text.slice(at + n.quote.length));
}

function renderSide() {
  const src = active(), el = $("#side"), nodes = new Map(src.nodes.map((n) => [n.id, n]));
  const n = nodes.get(sel);
  if (sel === "fold") {
    const rows = Object.entries(data.folded.by_status).sort((a, b) => b[1] - a[1]).map(([k, v]) => `<li><span class="grow">${esc(cap(STATUS[k] || k))}</span><b>${v}</b></li>`).join("");
    el.innerHTML = `<div class="cap">Not drawn<button class="x" data-close aria-label="Close">×</button></div><h2>${data.folded.products} more products</h2><ul>${rows}</ul><div class="cap">${esc(cap(data.folded.rule))}</div>`;
    return;
  }
  if (n) {
    const mark = { pass: ["yes", "✓"], fail: ["no", "✕"] };
    const quotes = n.kind !== "product" ? "" : src.edges.filter((e) => e.from === n.id && e.verb === "states").map((e) => nodes.get(e.to)).filter((q) => q?.quote)
      .map((q) => `<li><span class="${(mark[q.state] || ["when", "?"])[0]}">${(mark[q.state] || ["when", "?"])[1]}</span><span class="grow"><mark>${esc(q.quote)}</mark></span></li>`).join("");
    const links = src.edges.filter((e) => (e.from === n.id || e.to === n.id) && !(quotes && e.verb === "states") && nodes.has(e.from) && nodes.has(e.to)).slice(0, 12).map((e) => {
      const other = nodes.get(e.from === n.id ? e.to : e.from);
      return `<li>${dot(other.owner)}<span class="grow">${e.from === n.id ? esc(e.verb) + " " + esc(other.label) : esc(other.label) + " " + esc(e.verb) + " this"}</span></li>`;
    }).join("");
    const extra = [n.expr ? `<dt>Check</dt><dd>${esc(n.expr)}${n.why ? " · " + esc(n.why) : ""}</dd>` : "",
      n.kind === "product" && n.reason ? `<dt>Why not</dt><dd>${esc(n.reason)}</dd>` : "",
      n.more_on_page ? `<dt>Also</dt><dd>${n.more_on_page} more on the page</dd>` : "",
      n.class ? `<dt>Sharing</dt><dd>${esc(n.sub || n.class)}</dd>` : "",
      n.removed?.length ? `<dt>Withheld</dt><dd>${n.removed.map((c) => `<s>${esc(c.text)}</s> <span class="when">${esc(c.mark || "")}</span>`).join("<br>")}</dd>` : "",
      n.why && n.kind === "message" ? `<dt>Why</dt><dd>${esc(n.why)}</dd>` : "",
      n.aside ? `<dt>Set aside</dt><dd>${esc(n.aside.reason)} · ${esc(nodes.get(n.aside.limit)?.label || "")}</dd>` : "",
      n.href ? `<dt>Open</dt><dd><a class="link" href="${esc(n.href)}">the signature</a></dd>` : ""].join("");
    el.innerHTML = `<div class="cap">${esc(KIND[n.kind])}<button class="x" data-close aria-label="Close">×</button></div>
      <h2>${esc(n.label)}</h2><p class="quote">${quoted(n)}</p>
      <dl><dt>Owner</dt><dd>${dot(n.owner)}${esc(ownerName(n.owner))}</dd><dt>Source</dt><dd>${sourceLine(n.source)}</dd>${extra}</dl>
      ${quotes ? `<hr><div class="cap">The page's own words</div><ul>${quotes}</ul>` : ""}<hr><ul>${links}</ul>`;
    return;
  }
  // nothing selected: what Cognee answered for this item, and its permission record
  const need = (data.lines.find((l) => l.line_id === data.line_id) || {}).need || "item";
  const refused = (cognee?.refused || []).slice(-1)[0], ingest = (cognee?.ingests || []).slice(-1)[0];
  const parts = (answer?.parts?.length ? answer.parts : [{ owner: "system", text: answer?.answer || "" }])
    .map((p) => ({ owner: p.owner, text: String(p.text || "").replace(/\*\*/g, "").trim() })).filter((p) => p.text);
  const first = (t) => { const line = t.split("\n")[0]; return line.split(/(?<=[.!?])\s+/)[0] || line; };
  const brief = parts.filter((p) => !/^I could not find/i.test(p.text)).slice(0, 3).map((p) => ({ owner: p.owner, text: first(p.text) }));
  const body = answer?.answered
    ? `<p class="quote answer">${(whole ? parts : brief).map((p) => `${dot(p.owner)}${esc(p.text)}`).join("\n\n")}</p>
       <div class="cap">Answered by Cognee<button class="link more" data-whole>${whole ? "shorter" : "the whole answer"}</button></div>`
    : `<p class="quote muted">${esc(answer?.error || answer?.note || "Cognee has not answered.")}</p>`;
  const perm = refused
    ? `<li><span class="no">✕</span><span class="grow">${esc(data.people[refused.identity] || refused.identity)}'s key writes to ${esc(data.people[refused.dataset_owner] || refused.dataset_owner)}'s dataset</span><span class="when">refused</span></li>` : "";
  const own = refused && (cognee?.log || []).filter((e) => e.action === "write" && e.accepted && e.identity === refused.dataset_owner && e.dataset_owner === refused.dataset_owner).slice(-1)[0];
  const ok = own ? `<li><span class="yes">✓</span><span class="grow">${esc(data.people[own.identity] || own.identity)}'s key writes to ${esc(data.people[own.identity] || own.identity)}'s dataset</span><span class="when">accepted</span></li>` : "";
  el.innerHTML = `<div class="cap">Asked of Cognee</div><h2>What decides the ${esc(need)}, and from whom?</h2>${body}
    <hr><div class="cap">One dataset per owner</div><ul>${perm}${ok}</ul>
`;
}

function render() { renderTop(); renderBand(); draw(); renderSide(); }

async function load() {
  const q = line ? `?line_id=${encodeURIComponent(line)}` : "";
  let body = await (await fetch("/api/graph" + q)).json();
  if (!body.nodes && body.lines?.length) {                           // no item named: the one with the most found
    line = [...body.lines].sort((a, b) => (b.products || 0) - (a.products || 0))[0].line_id;
    body = await (await fetch(`/api/graph?line_id=${encodeURIComponent(line)}`)).json();
  }
  const [a, c, x] = await Promise.all([
    fetch(`/api/graph/ask?line_id=${encodeURIComponent(line)}`).then((r) => r.json()).catch(() => null),
    fetch("/api/graph/cognee").then((r) => r.json()).catch(() => null),
    fetch(`/api/graph/explore?line_id=${encodeURIComponent(line)}`).then((r) => r.json()).catch(() => null)]);
  const next = JSON.stringify([body, a, c, x]);
  if (next === stamp) return;
  stamp = next; data = body; answer = a; cognee = c; xdata = x;
  if (data.nodes) render();
}

document.addEventListener("click", (e) => {
  const chip = e.target.closest("[data-line]"), node = e.target.closest("[data-id]"), seg = e.target.closest("[data-view]");
  if (e.target.closest("[data-whole]")) { whole = !whole; renderSide(); return; }
  if (seg) { view = seg.dataset.view; sel = null; XP.play(false); render(); return; }
  if (e.target.closest("[data-play]")) { XP.play(!XP.playing()); e.target.closest("[data-play]").textContent = XP.playing() ? "Pause" : "Play"; return; }
  if (e.target.closest("[data-step]")) { XP.play(false); XP.step(Number(e.target.closest("[data-step]").dataset.step)); return; }
  if (e.target.closest("#ctl") || (view === "explore" && e.target.closest("#stage"))) return;   // the canvas handles its own clicks
  if (chip) { XP.play(false); line = chip.dataset.line; sel = null; stamp = ""; params.delete("stage"); history.replaceState(null, "", `?line_id=${line}`); load(); return; }
  if (e.target.closest("[data-close]")) sel = null;
  else if (node) sel = sel === node.dataset.id ? null : node.dataset.id;
  else if (e.target.closest("#stage")) sel = null;
  else return;
  draw(); renderSide();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && sel) { sel = null; XP.select(null); draw(); renderSide(); }
  if (view === "explore" && e.key === "ArrowRight") { XP.play(false); XP.step(1); }
  if (view === "explore" && e.key === "ArrowLeft") { XP.play(false); XP.step(-1); }
  if (view === "explore" && e.key === " " && e.target === document.body) { e.preventDefault(); XP.play(!XP.playing()); renderStageLabel(); }
});
const renderStageLabel = () => { const b = $("[data-play]"); if (b) b.textContent = XP.playing() ? "Pause" : "Play"; };
addEventListener("resize", () => data && draw());
load();
if (LIVE) setInterval(load, 4000);
