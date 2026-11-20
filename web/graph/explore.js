// The run explored as a graph that grows, for one item. Everything drawn comes from GET /api/graph/explore:
// nodes, edges and the stages in which nodes appear or are set aside. This file only places and moves them.
// Positions are computed per stage (never simulated) and tweened between stages, so any paused stage is exact.
const NS = "http://www.w3.org/2000/svg";
const REM = parseFloat(getComputedStyle(document.documentElement).fontSize) / 16;
const px = (n) => n * REM;
const CW = px(136), CH = px(36), SP = px(25), R = px(8), RS = px(4), RB = px(13);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const ownerClass = (o) => (o === "issuer" || o === "shopper" ? o : o === "system" || o === "web" ? "" : "store");
const short = (s, n) => (String(s || "").length > n ? String(s).slice(0, n - 1).trimEnd() + "…" : String(s || ""));
const clock = (at) => (at ? String(at).slice(11, 16) : "");
const REASONS = ["outside", "unclear", "not stated", "struck", "struck before"];

let X = null;      // the mounted exploration: data, elements, current stage and positions

function el(tag, attrs = {}, html = "") {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (html) e.innerHTML = html;
  return e;
}

// ---------- where everything is at stage k ----------
function plan(k) {
  const { data, W, H } = X, S = data.stages, at = (id) => S.findIndex((s) => s.id === id);
  const iSearch = at("search"), iRead = at("reading"), iWeb = at("web"), iRank = at("ranking"), iSign = at("signature");
  const nodes = new Map(data.nodes.map((n) => [n.id, n]));
  const added = new Map();                                        // node id -> the stage that adds it
  S.forEach((s, i) => s.node_ids_added.forEach((id) => added.set(id, i)));
  const asideAt = new Map();                                      // product id -> the stage that sets it aside
  S.forEach((s, i) => s.node_ids_set_aside.forEach((id) => asideAt.set(id, i)));
  const P = new Map(), lines = [], texts = [];
  const put = (id, x, y, more = {}) => P.set(id, { x, y, o: (added.get(id) ?? 0) <= k ? 1 : 0, ...more });
  const GAP = px(44), XI = CW + GAP, XS = XI + CW + GAP, PX0 = XS + CW + px(28), YROW = H * 0.56, YB = H * 0.72;

  // the order: who, the item, the measurement
  const people = data.nodes.filter((n) => n.kind === "person");
  const item = data.nodes.find((n) => n.kind === "order_item");
  const facts = data.nodes.filter((n) => n.kind === "home_fact");
  people.forEach((n, i) => put(n.id, 0, i * (CH + px(22))));
  put(item.id, XI, 0);
  facts.forEach((n, i) => put(n.id, XI, (i + 1) * (CH + px(22))));
  // the rules, above the products
  const limits = data.nodes.filter((n) => n.kind === "limit");
  limits.forEach((n, i) => put(n.id, PX0 + i * (CW + px(56)), 0));

  // the stores and the products found at each
  const stores = data.nodes.filter((n) => n.kind === "store");
  const products = data.nodes.filter((n) => n.kind === "product");
  const cols = Math.max(6, Math.floor((W - PX0 - px(8)) / SP));
  let y = CH + px(30);
  const home = new Map();
  for (const s of stores) {
    const mine = products.filter((p) => p.owner === s.owner);
    const rows = Math.ceil(mine.length / cols);
    put(s.id, XS, y + (rows * SP) / 2 - CH / 2);
    mine.forEach((p, i) => home.set(p.id, { x: PX0 + (i % cols) * SP + SP / 2, y: y + Math.floor(i / cols) * SP + SP / 2, store: s.id }));
    y += rows * SP + px(16);
  }

  // set aside: a quiet band, grouped by the rule and the reason, each group counted
  const groups = new Map();
  for (const p of products) {
    const i = asideAt.get(p.id);
    if (i == null || i > k) continue;
    const key = `${i}|${p.aside.reason}`;
    if (!groups.has(key)) groups.set(key, { stage: i, reason: p.aside.reason, ids: [] });
    groups.get(key).ids.push(p.id);
  }
  const ordered = [...groups.values()].sort((a, b) => a.stage - b.stage || REASONS.indexOf(a.reason) - REASONS.indexOf(b.reason));
  const gcols = 10, gsp = px(11);
  let gx = XS;
  const asidePos = new Map();
  for (const g of ordered) {
    const w = Math.max(px(112), Math.min(gcols, g.ids.length) * gsp + px(10));
    texts.push({ x: gx, y: YB + px(4), cls: "gh", html: `<tspan class="gc">${g.ids.length}</tspan> ${esc(g.reason)}` });
    texts.push({ x: gx, y: YB + px(18), cls: "gs", html: esc(S[g.stage].rule || S[g.stage].title) });
    g.ids.forEach((id, i) => asidePos.set(id, { x: gx + (i % gcols) * gsp + RS, y: YB + px(32) + Math.floor(i / gcols) * gsp }));
    gx += w + px(14);
  }

  // the web row and the ranked line
  const web = nodes.get("web:search");
  const reviews = data.nodes.filter((n) => n.kind === "review");
  const searched = reviews.map((r) => r.product);
  const order = iRank >= 0 ? S[iRank].order : [];
  const ranked = iRank >= 0 && k >= iRank;
  const xr = W - CW - px(40);                                       // the head of the line, next to the gate
  const big = new Set(ranked ? order.slice(0, 6) : k >= iWeb && iWeb >= 0 ? searched : []);
  const linePos = new Map();
  if (ranked) {
    let x = xr;
    order.forEach((id, i) => { x -= i === 0 ? RB : big.has(id) ? px(66) : i === 6 ? px(44) : px(9.2); linePos.set(id, { x, y: YROW }); });
  } else if (iWeb >= 0 && k >= iWeb) {
    const step = Math.min(px(120), (W - PX0) / Math.max(1, searched.length));
    searched.forEach((id, i) => linePos.set(id, { x: PX0 + step / 2 + i * step, y: YROW }));
  }

  for (const p of products) {
    const h = home.get(p.id), born = k >= iSearch, gone = asidePos.get(p.id), line = linePos.get(p.id);
    const src = P.get(h.store);
    const where = !born ? { x: src.x + CW / 2, y: src.y + CH / 2 } : gone || line || h;
    P.set(p.id, { ...where, o: born ? (gone ? 0.75 : 1) : 0, r: gone ? RS : big.has(p.id) ? RB : ranked ? px(4.2) : R,
      big: big.has(p.id) && !gone, aside: !!gone, dashed: k >= iRead && (S[iRead]?.not_stated || []).includes(p.id),
      read: k >= iRead, pick: ranked && p.picked, checked: limits.filter((l) => (added.get(l.id) ?? 99) <= k).map((l) => l.id) });
  }
  if (web) put(web.id, XS, YROW - CH / 2);
  reviews.forEach((r) => {
    const p = P.get(r.product);
    P.set(r.id, { x: p.x - px(34), y: p.y + RB + px(26), o: (added.get(r.id) ?? 99) <= k && p.big ? 1 : 0, pill: true });
  });
  // the gate, and the cart beyond it
  if (nodes.has("gate")) put("gate", W - CW, YROW - CH / 2, { gate: true });
  data.nodes.filter((n) => n.kind === "cart").forEach((n, i) => put(n.id, W - CW, YROW + CH + px(14) + i * (CH + px(8))));

  // the lines of this stage
  const vis = (id) => P.get(id)?.o > 0;
  const card = (a, b, cls = "", label = "") => { if (vis(a) && vis(b)) lines.push({ a, b, cls, label, card: true }); };
  for (const e of data.edges) {
    if (e.verb === "wrote" || e.verb === "measured") card(e.from, e.to, "", e.verb);
    else if (e.verb === "searches" && nodes.get(e.to)?.kind === "store" && k >= iSearch && !ranked) card(e.from, e.to, k === iSearch ? "lit" : "", k === iSearch ? e.label : "");
    else if (e.verb === "requires" && nodes.get(e.to)?.kind === "home_fact") { if (vis(e.to) && vis(e.from)) lines.push({ a: e.to, b: e.from, cls: "", toCorner: true, card: true }); }
    else if (e.verb === "waits for" && k >= iSign && iSign >= 0) lines.push({ a: e.from, b: e.to, cls: "lit", toCard: true });
    else if (e.verb === "releases") card(e.from, e.to, "lit", "");
    else if (e.verb === "searches" && e.from === "web:search" && k === iWeb) lines.push({ a: e.from, b: e.to, cls: "", fromCard: true });
  }
  const stage = S[k];
  if (stage.limit) {                                                // the rule reaches every product it judges
    for (const p of products) {
      const i = asideAt.get(p.id);
      if (i != null && i < k) continue;
      const v = p.checks[stage.limit.replace(/^limit:/, "")];
      lines.push({ a: stage.limit, b: p.id, cls: "ray " + (i === k ? (v === "fail" ? "fails" : "none") : "passes"), fromCardBottom: true });
    }
  }
  if (ranked) {
    order.slice(0, 6).forEach((id) => {
      const n = nodes.get(id), p = P.get(id);
      texts.push({ x: p.x, y: p.y - RB - px(20), cls: "pn mid", html: esc(short(n.label, 13)) });
      texts.push({ x: p.x, y: p.y - RB - px(7), cls: "pp mid", html: esc((n.sub || "").split(" · ")[0]) + (n.picked ? " · the pick" : "") });
    });
    if (order.length > 6) texts.push({ x: P.get(order[order.length - 1]).x, y: YROW + px(22), cls: "gs", html: `${order.length - 6} more that pass` });
  } else if (iWeb >= 0 && k >= iWeb) {
    searched.forEach((id) => { const p = P.get(id); if (p.big) texts.push({ x: p.x, y: p.y - RB - px(7), cls: "pn mid", html: esc(short(nodes.get(id).label, 13)) }); });
  }
  return { P, lines, texts };
}

// ---------- drawing ----------
function glyph(n) {
  if (n.kind === "product") {
    const img = n.image_url ? `<image class="ph" href="${esc(n.image_url)}" preserveAspectRatio="xMidYMid slice"/>` : "";
    return `<title>${esc(n.label)} · ${esc(n.sub || "")}</title><circle class="c"/>${img}<circle class="ring"/><circle class="q q0"/><circle class="q q1"/>`;
  }
  const dot = n.kind === "web" || n.kind === "review" ? "" : `<circle class="od ${ownerClass(n.owner)}" cx="${px(10)}" cy="${px(12.5)}" r="${px(3)}"/>`;
  const tx = dot ? px(18) : px(9);
  if (n.kind === "review") return `<rect class="b pill" width="${px(72)}" height="${px(18)}" rx="${px(9)}"/><text class="l mid" x="${px(36)}" y="${px(12.5)}">${esc(short(n.label, 11))}</text><text class="s mid" x="${px(36)}" y="${px(30)}">${esc(short(n.sub, 16))}</text>`;
  return `<title>${esc(n.label)}</title><rect class="b" width="${CW}" height="${CH}" rx="${px(6)}"/>${dot}
    <text class="l" x="${tx}" y="${px(15.5)}">${esc(short(n.label, 19))}</text><text class="s" x="${tx}" y="${px(28.5)}">${esc(short(n.sub, 24))}</text>
    ${n.kind === "gate" ? `<path class="bar" d="M${-px(12)} ${-px(14)}V${CH + px(14)}"/>` : ""}`;
}

function build() {
  const { svg, data } = X;
  svg.innerHTML = `<g class="lines"></g><g class="texts"></g><g class="nodes"></g>`;
  X.gl = svg.querySelector(".lines"); X.gt = svg.querySelector(".texts");
  const gn = svg.querySelector(".nodes");
  X.els = new Map();
  for (const n of data.nodes) {
    if (n.kind === "statement") continue;                           // a quote is drawn on its product
    const g = el("g", { class: `xn k-${n.kind}`, "data-id": n.id, tabindex: n.kind === "product" ? -1 : 0 }, glyph(n));
    gn.appendChild(g);
    X.els.set(n.id, g);
  }
}

function paint(P) {
  for (const [id, g] of X.els) {
    const p = P.get(id);
    if (!p) { g.style.display = "none"; continue; }
    g.style.display = p.o <= 0.01 ? "none" : "";
    g.setAttribute("opacity", p.o);
    g.setAttribute("transform", `translate(${p.x} ${p.y})`);
    if (p.r != null) {
      const [c, img, ring, q0, q1] = [g.querySelector(".c"), g.querySelector(".ph"), g.querySelector(".ring"), g.querySelector(".q0"), g.querySelector(".q1")];
      c.setAttribute("r", p.r); ring.setAttribute("r", p.r + px(3));
      if (img) { img.setAttribute("x", -p.r); img.setAttribute("y", -p.r); img.setAttribute("width", 2 * p.r); img.setAttribute("height", 2 * p.r); img.style.clipPath = `circle(${p.r}px at ${p.r}px ${p.r}px)`; }
      [q0, q1].forEach((q, i) => { q.setAttribute("cx", (i ? 1 : -1) * p.r * 0.5); q.setAttribute("cy", -p.r - px(3.5)); q.setAttribute("r", Math.max(px(1.6), p.r * 0.24)); });
    }
  }
  const at = (id, l, end) => {
    const p = P.get(id), n = X.els.get(id);
    if (p.r != null) return [p.x, p.y];
    if (l.fromCardBottom && end === "a") return [p.x + CW / 2, p.y + CH];
    if (l.toCorner && end === "b") return [p.x + px(8), p.y + CH];
    return end === "a" ? [p.x + (P.get(l.b).x < p.x ? 0 : CW), p.y + CH / 2] : [p.x + (P.get(l.a).x > p.x ? CW : 0), p.y + CH / 2];
  };
  X.lineEls.forEach(({ l, e, t }) => {
    const [x1, y1] = at(l.a, l, "a"), [x2, y2] = at(l.b, l, "b");
    e.setAttribute("x1", x1); e.setAttribute("y1", y1); e.setAttribute("x2", x2); e.setAttribute("y2", y2);
    if (t) { t.setAttribute("x", (x1 + x2) / 2); t.setAttribute("y", (y1 + y2) / 2 - px(4)); }
  });
}

function dress(k, target) {
  // what a stage changes besides position: classes, the lines and the words
  const { data } = X, nodes = new Map(data.nodes.map((n) => [n.id, n]));
  for (const [id, g] of X.els) {
    const p = target.P.get(id), n = nodes.get(id);
    if (!p) continue;
    g.classList.toggle("sel", X.sel === id);
    if (n.kind === "limit") g.classList.toggle("lit", data.stages[k].limit === id);
    if (n.kind === "gate") g.classList.toggle("open", !!n.open);
    if (n.kind !== "product") continue;
    g.classList.toggle("aside", p.aside); g.classList.toggle("dashed", p.dashed); g.classList.toggle("pick", !!p.pick);
    g.classList.toggle("big", p.big); g.classList.toggle("read", p.read);
    const limits = data.nodes.filter((x) => x.kind === "limit");
    g.querySelectorAll(".q").forEach((q, i) => {
      const lim = limits[i], v = lim ? n.checks[lim.id.replace(/^limit:/, "")] : null;
      q.setAttribute("class", `q q${i} ${!lim ? "off" : v === "not_stated" ? "ns" : p.checked.includes(lim.id) ? v : "st"}`);
    });
  }
  X.gl.innerHTML = ""; X.gt.innerHTML = "";
  X.lineEls = target.lines.map((l) => {
    const e = el("line", { class: `ln ${l.cls}` });
    X.gl.appendChild(e);
    const t = l.label ? el("text", { class: "lt mid" }, esc(l.label)) : null;
    if (t) X.gl.appendChild(t);
    return { l, e, t };
  });
  target.texts.forEach((t) => X.gt.appendChild(el("text", { class: t.cls, x: t.x, y: t.y }, t.html)));
}

function go(k, instant = false) {
  const S = X.data.stages;
  k = Math.max(0, Math.min(S.length - 1, k));
  const target = plan(k), from = X.P || target.P;
  X.k = k;
  cancelAnimationFrame(X.raf);
  dress(k, target);
  X.hooks.onStage(S[k], k, S.length);
  const t0 = performance.now(), ms = instant || !X.motion ? 0 : 750;
  const ease = (t) => (t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2);
  const frame = (now) => {
    const t = ms ? Math.min(1, (now - t0) / ms) : 1, u = ease(t), cur = new Map();
    for (const [id, b] of target.P) {
      const a = from.get(id) || b;
      cur.set(id, { ...b, x: a.x + (b.x - a.x) * u, y: a.y + (b.y - a.y) * u, o: a.o + (b.o - a.o) * u, r: b.r != null ? (a.r ?? b.r) + (b.r - (a.r ?? b.r)) * u : undefined });
    }
    paint(cur);
    X.P = cur;
    if (t < 1) X.raf = requestAnimationFrame(frame);
  };
  if (ms) X.raf = requestAnimationFrame(frame); else frame(t0);
}

// ---------- the surface the page uses ----------
export function mount(host, data, hooks, opts = {}) {
  host.innerHTML = "";
  const svg = el("svg", { class: "xp", width: host.clientWidth, height: host.clientHeight });
  host.appendChild(svg);
  X = { host, svg, data, hooks, W: host.clientWidth - px(4), H: host.clientHeight - px(8), sel: null, motion: opts.motion !== false, lineEls: [] };
  build();
  go(Math.min(opts.stage ?? 0, data.stages.length - 1), true);
  svg.addEventListener("click", (e) => {
    const g = e.target.closest("[data-id]");
    X.sel = g ? g.dataset.id : null;
    X.els.forEach((x, id) => x.classList.toggle("sel", id === X.sel));
    hooks.onSelect(X.sel);
  });
}
export const stage = () => X?.k ?? 0;
export const step = (d) => X && go(X.k + d);
export const jump = (k, instant) => X && go(k, instant);
export const playing = () => !!X?.timer;
export function play(on) {
  if (!X) return;
  clearInterval(X.timer); X.timer = null;
  if (on) {
    if (X.k >= X.data.stages.length - 1) go(0, true);
    X.timer = setInterval(() => { if (X.k >= X.data.stages.length - 1) { play(false); X.hooks.onStage(X.data.stages[X.k], X.k, X.data.stages.length); } else go(X.k + 1); }, 1700);
  }
}
export function select(id) { if (X) { X.sel = id; X.els.forEach((x, i) => x.classList.toggle("sel", i === id)); } }
export { clock };
