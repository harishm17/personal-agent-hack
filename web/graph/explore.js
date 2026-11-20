// The run explored as a graph that grows, for one item. Everything drawn comes from GET /api/graph/explore:
// nodes, edges and the stages in which nodes appear or are set aside. This file only places and moves them.
// Positions are computed per stage (never simulated) and tweened between stages, so any paused stage is exact.
const NS = "http://www.w3.org/2000/svg";
const REM = parseFloat(getComputedStyle(document.documentElement).fontSize) / 16;
const px = (n) => n * REM;
const CW = px(136), CH = px(36), SP = px(25), R = px(8), RS = px(5), RB = px(13);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const ownerClass = (o) => (o === "issuer" || o === "shopper" ? o : o === "system" || o === "web" ? "" : "store");
const short = (s, n) => (String(s || "").length > n ? String(s).slice(0, n - 1).trimEnd() + "…" : String(s || ""));
const clock = (at) => (at ? String(at).slice(11, 16) : "");
const FW = px(176);                                                // a fact quoted from a message is a wider card
const GW = px(214);                                                // the one node that stands for everything recalled
const boxW = (n) => (n.group ? GW : n.kind === "context_fact" || n.kind === "event" ? FW : CW);
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
  const iEvent = at("event"), iOrder = at("order"), eventPhase = iEvent >= 0 && k <= iOrder;
  const iSearch = at("search"), iRead = at("reading"), iWeb = at("web"), iRank = at("ranking"), iSign = at("signature"), iAsk = at("asking");
  const ranked = iRank >= 0 && k >= iRank, asking = iAsk >= 0 && k === iAsk;
  const nodes = new Map(data.nodes.map((n) => [n.id, n]));
  const added = new Map();                                        // node id -> the stage that adds it
  S.forEach((s, i) => s.node_ids_added.forEach((id) => added.set(id, i)));
  const asideAt = new Map();                                      // product id -> the stage that sets it aside
  S.forEach((s, i) => s.node_ids_set_aside.forEach((id) => asideAt.set(id, i)));
  const P = new Map(), lines = [], texts = [];
  let leftBottom = 2 * (CH + px(22));
  const put = (id, x, y, more = {}) => P.set(id, { x, y, ...more, o: (added.get(id) ?? 0) <= k ? more.o ?? 1 : 0 });
  const GAP = px(60), XI = CW + GAP, XS = XI + CW + GAP, PX0 = XS + CW + px(28), YROW = H * 0.56, YB = H * 0.77;

  // the order: who, the item, the measurement
  const people = data.nodes.filter((n) => n.kind === "person");
  const item = data.nodes.find((n) => n.kind === "order_item");
  const facts = data.nodes.filter((n) => n.kind === "home_fact");
  const limits = data.nodes.filter((n) => n.kind === "limit");
  const values = data.nodes.filter((n) => n.kind === "sheet_value");
  const known = data.nodes.filter((n) => n.kind === "context_fact");
  const notes = data.nodes.filter((n) => n.kind === "context_message");
  const around = data.nodes.filter((n) => n.kind === "context_person");
  if (eventPhase) {
    // the event fills the canvas: its people, the messages, the facts quoted from them; the order grows at the right
    put("event", 0, 0);
    if (nodes.get("event").held_by) texts.push({ x: px(2), y: CH + px(15), cls: "gs", html: esc(nodes.get("event").held_by) });
    around.forEach((n, i) => put(n.id, 0, CH + px(26) + i * (CH + px(10))));
    notes.forEach((n, i) => put(n.id, XI, i * (CH + px(10))));
    const fy = new Map();
    known.forEach((n, i) => { fy.set(n.id, i * (CH + px(6))); put(n.id, XS, fy.get(n.id), { w: FW, o: k >= iOrder && !n.used ? 0.4 : 1 }); });
    const XD = XS + FW + px(166), XE = XD + CW + px(24);
    const want = (id) => { const ys = data.edges.filter((e) => e.feeds && e.to === id).map((e) => fy.get(e.from)); return ys.length ? ys.reduce((a, b) => a + b, 0) / ys.length : null; };
    const issuer = people.find((n) => n.id === "person:issuer"), shopper = people.find((n) => n.id === "person:shopper");
    [item, ...limits].forEach((n, i) => put(n.id, XE, i * (CH + px(8))));          // prescribed: the order and its rules
    if (issuer) put(issuer.id, XD, 0);
    const below = (1 + limits.length) * (CH + px(8)) + px(22);
    const sy = Math.max(want(shopper?.id) ?? 0, below);
    if (shopper) put(shopper.id, XD, sy);
    let prev = -Infinity;                                                          // supplied: placed to face the facts that feed them
    [...values, ...facts].map((n, i) => ({ n, y: want(n.id) ?? below + i })).sort((a, b) => a.y - b.y)
      .forEach((o) => { const y = Math.max(o.y, below, prev + CH + px(10)); prev = y; put(o.n.id, XE, y); });
    if (k >= iOrder) {
      if (data.sources?.prescribed) texts.push({ x: XD, y: -px(5), cls: "src", html: esc(data.sources.prescribed) });
      if (data.sources?.supplied) texts.push({ x: XD, y: sy - px(7), cls: "src", html: esc(data.sources.supplied) });
    }
    const idle = known.find((n) => !n.used);
    if (idle && k >= iOrder) texts.push({ x: XS + FW + px(10), y: fy.get(idle.id) + CH / 2 + px(3), cls: "gs", html: "held · not used for this order" });
  } else {
    // the event is the root, top-left; what the family supplied grows under it; then the author's order
    const ROW = CH + px(22), supplied = [...facts, ...values];
    const issuer = people.find((n) => n.id === "person:issuer"), shopper = people.find((n) => n.id === "person:shopper");
    const yS = nodes.has("event") ? ROW : 0, yD = yS + Math.max(1, supplied.length) * ROW;
    if (nodes.has("event")) { put("event", 0, 0); if (shopper) lines.push({ raw: [px(22), CH, px(22), yS], cls: "" }); }
    if (shopper) put(shopper.id, 0, yS);
    supplied.forEach((n, i) => put(n.id, XI, yS + i * ROW));
    if (issuer) put(issuer.id, 0, yD);
    put(item.id, XI, yD);
    leftBottom = yD + ROW;
    if (data.sources?.supplied && supplied.length) texts.push({ x: XI, y: yS - px(7), cls: "src", html: esc(data.sources.supplied) });
    // the rules, above the products
    limits.forEach((n, i) => put(n.id, PX0 + i * (CW + px(56)), 0));
    // the event's people, messages and facts fold back into it
    [...around, ...notes, ...known].forEach((n) => put(n.id, 0, 0, { o: 0, w: boxW(n) }));
  }
  // what it already knows: one node for all of it, and on their own only the few that bear on this item's pick
  const memories = data.nodes.filter((n) => n.kind === "memory");
  const own = memories.filter((n) => n.own), all = memories.find((n) => n.group);
  if (all) put(all.id, 0, leftBottom + px(4), { w: GW });
  own.forEach((n, i) => put(n.id, 0, leftBottom + px(4) + (i + (all ? 1 : 0)) * (CH + px(6))));
  memories.filter((n) => !n.own && !n.group).forEach((n) => put(n.id, 0, leftBottom + px(4), { o: 0 }));

  // the stores and the products found at each
  const stores = data.nodes.filter((n) => n.kind === "store");
  const products = data.nodes.filter((n) => n.kind === "product");
  const cols = Math.max(6, Math.floor((W - PX0 - px(8)) / SP));
  let y = CH + px(44);
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
  const gcols = 9, gsp = px(13), RQ = px(2.5);
  let gx = ranked ? 0 : XS;
  const asidePos = new Map();
  for (const g of ordered) {
    if (ranked) {                                                   // one quiet row: a count, a reason, its dots
      const label = `${g.ids.length} ${g.reason}`, lw = label.length * px(5.4) + px(8);
      texts.push({ x: gx, y: H - px(4), cls: "gs", html: esc(label) });
      g.ids.forEach((id, i) => asidePos.set(id, { x: gx + lw + i * px(7), y: H - px(7), quiet: true }));
      gx += lw + g.ids.length * px(7) + px(18);
      continue;
    }
    const w = Math.max(px(112), Math.min(gcols, g.ids.length) * gsp + px(10));
    texts.push({ x: gx, y: YB + px(4), cls: "gh", html: `<tspan class="gc">${g.ids.length}</tspan> ${esc(g.reason)}` });
    texts.push({ x: gx, y: YB + px(18), cls: "gs", html: esc(S[g.stage].rule || S[g.stage].title) });
    g.ids.forEach((id, i) => asidePos.set(id, { x: gx + (i % gcols) * gsp + RS, y: YB + px(34) + Math.floor(i / gcols) * (gsp + px(3)) }));
    gx += w + px(14);
  }

  // the web row and the ranked line
  const web = nodes.get("web:search");
  const reviews = data.nodes.filter((n) => n.kind === "review");
  const searched = reviews.map((r) => r.product);
  const order = iRank >= 0 ? S[iRank].order : [];
  const webbed = iWeb >= 0 && k >= iWeb;
  const TOP = 5, BIGSTEP = px(84), RBIG = px(26), GS = 1.3, CY = H * 0.46;
  const gateX = W - CW * GS - px(2), leftEdge = XI + CW + px(64);
  const big = new Set(ranked ? order.slice(0, TOP) : webbed ? searched : []);
  const linePos = new Map();
  if (ranked) {
    const head = gateX - px(44) - RBIG, n = Math.min(TOP, order.length);
    const step = n > 1 ? Math.min(px(170), (head - leftEdge - RBIG) / (n - 1)) : 0;
    order.slice(0, TOP).forEach((id, i) => linePos.set(id, { x: head - i * step, y: CY }));
    // the rest that pass, in order, in a quiet block under them
    const tail = order.slice(TOP), trows = 2, tsp = px(10), ty = CY + RBIG + px(96);
    tail.forEach((id, i) => linePos.set(id, { x: leftEdge + Math.floor(i / trows) * tsp, y: ty + (i % trows) * tsp }));
    if (tail.length) texts.push({ x: leftEdge + Math.ceil(tail.length / trows) * tsp + px(8), y: ty + px(8), cls: "gs", html: `${tail.length} more that pass` });
  } else if (webbed) {
    const step = Math.min(px(120), Math.max(BIGSTEP, (W - PX0) / Math.max(1, searched.length)));
    searched.forEach((id, i) => linePos.set(id, { x: PX0 + step / 2 + i * step, y: YROW }));
  }

  if (asking) {
    const LANE = px(24), MW = px(84), RW = px(64), xp = PX0 + px(40), spine = xp + RB + px(24), xm = spine + px(14);
    const storeX = W - CW, xr2 = storeX - RW - px(36), xg = (xm + MW + xr2) / 2;
    let ly = YROW - px(46), kept = 0;
    const top = ly;
    for (const pid of S[iAsk].row || []) {
      const mine = data.nodes.filter((n) => n.kind === "message" && n.product === pid);
      const cy = ly + ((mine.length - 1) * LANE) / 2 + px(9), store = mine[0]?.store;
      linePos.set(pid, { x: xp, y: cy });
      big.add(pid);
      if (P.has(store)) P.set(store, { ...P.get(store), x: storeX, y: cy - CH / 2 });      // the store these messages go to
      lines.push({ raw: [xp + RB, cy, spine, cy], cls: "" }, { raw: [spine, ly + px(9), spine, ly + (mine.length - 1) * LANE + px(9)], cls: "" });
      for (const m of mine) {
        const y9 = ly + px(9), chips = m.removed || [];
        P.set(m.id, { x: xm, y: ly, o: 1, w: MW, h: px(18) });
        lines.push({ raw: [spine, y9, xm, y9], cls: "" }, { raw: [xm + MW, y9, xg, y9], cls: m.stopped ? "fails" : "lit" });
        // what the guard withheld sits on the guard line, struck
        if (chips.length) texts.push({ x: xg, y: y9 + px(3.5), cls: "chip on mid", html: chips.slice(0, 2).map((c) => esc(short(c.text, 10))).join(" · ") + (chips.length > 2 ? ` +${chips.length - 2}` : "") });
        const r = data.nodes.find((n) => n.kind === "reply" && n.message === m.id);
        if (r) {
          P.set(r.id, { x: xr2, y: ly, o: 1, w: RW, h: px(18) });
          kept += r.remembered ? 1 : 0;
          lines.push({ raw: [xg, y9, xr2, y9], cls: "lit" }, { raw: [xr2 + RW, y9, storeX, cy], cls: "lit" });
        } else if (m.stopped) texts.push({ x: xg + px(76), y: y9 + px(3.5), cls: "stop", html: "stopped" });
        else lines.push({ raw: [xg, y9, storeX, cy], cls: "lit" });
        ly += LANE;
      }
      ly += px(12);
    }
    lines.push({ raw: [xg, top - px(8), xg, ly - px(8)], cls: "guard" });
    texts.push({ x: xg, y: top - px(14), cls: "gs mid", html: "the guard" });
    if (kept) texts.push({ x: xr2, y: ly + px(4), cls: "gs", html: `${kept} ${kept === 1 ? "reply" : "replies"} remembered` });
  }
  data.nodes.filter((n) => (n.kind === "message" || n.kind === "reply") && !P.has(n.id)).forEach((n) => P.set(n.id, { x: PX0, y: YROW, o: 0, w: px(84), h: px(18) }));
  if (ranked) stores.forEach((n) => { P.get(n.id).o = 0; });          // the stores have done their part

  for (const p of products) {
    const h = home.get(p.id), born = k >= iSearch, gone = asidePos.get(p.id), line = linePos.get(p.id);
    const src = P.get(h.store);
    const where = !born ? { x: src.x + CW / 2, y: src.y + CH / 2 } : gone || line || h;
    P.set(p.id, { ...where, o: born ? (gone ? 0.75 : 1) : 0, r: gone ? (gone.quiet ? RQ : RS) : big.has(p.id) ? (ranked ? RBIG : RB) : ranked ? px(3.6) : R,
      big: big.has(p.id) && !gone, aside: !!gone, dashed: k >= iRead && (S[iRead]?.not_stated || []).includes(p.id),
      read: k >= iRead, pick: ranked && p.picked, checked: limits.filter((l) => { const i = S.findIndex((x) => x.limit === l.id); return i >= 0 && i <= k; }).map((l) => l.id) });
  }
  if (web) put(web.id, XS, YROW - CH / 2, ranked ? { o: 0 } : {});
  reviews.forEach((r) => {
    const p = P.get(r.product);
    P.set(r.id, { x: p.x - px(36), y: p.y + p.r + px(ranked ? 12 : 9), o: (added.get(r.id) ?? 99) <= k && p.big && !asking ? 1 : 0, pill: true });
  });
  // the gate, and the cart beyond it
  if (nodes.has("gate")) put("gate", gateX, CY - (CH * GS) / 2, { gate: true, s: GS, w: CW * GS, h: CH * GS });
  data.nodes.filter((n) => n.kind === "cart").forEach((n, i) => put(n.id, gateX, CY + CH * GS + px(14) + i * (CH + px(8))));

  // the lines of this stage
  const vis = (id) => P.get(id)?.o > 0;
  const card = (a, b, cls = "", label = "") => { if (vis(a) && vis(b)) lines.push({ a, b, cls, label, card: true }); };
  for (const e of data.edges) {
    if (e.feeds) { if (k >= iOrder && vis(e.from) && vis(e.to)) lines.push({ a: e.from, b: e.to, card: true, cls: e.matches === false ? "fails" : "lit",
      label: e.verb + (e.matches === true ? " · matches" : e.matches === false ? " · differs" : ""), lt: nodes.get(e.to)?.kind === "person" ? 0.5 : 0.27 }); }
    else if (e.verb === "says") card(e.from, e.to, "", "");
    else if (e.verb === "wrote" && nodes.get(e.to)?.kind === "context_message") { if (nodes.get(e.from)?.kind === "context_person") card(e.from, e.to, "", ""); }
    else if (e.prescribed) { if (eventPhase) card(e.from, e.to, "", ""); }
    else if (e.verb === "wrote" || e.verb === "measured") card(e.from, e.to, "", eventPhase ? "" : e.verb);
    else if (e.verb === "searches" && nodes.get(e.to)?.kind === "store" && k >= iSearch && !ranked && !asking) card(e.from, e.to, k === iSearch ? "lit" : "", "");
    else if (e.verb === "waits for" && k >= iSign && iSign >= 0) lines.push({ a: e.from, b: e.to, cls: "lit", toCard: true });
    else if (e.verb === "releases") card(e.from, e.to, "lit", "");
    else if (e.verb === "searches" && e.from === "web:search" && k === iWeb) lines.push({ a: e.from, b: e.to, cls: "", fromCard: true });
  }
  if (!eventPhase && data.sources) {
    if (data.sources.prescribed && limits.length) texts.push({ x: P.get(limits[0].id).x, y: -px(5), cls: "src", html: esc(data.sources.prescribed) });
    if (data.sources.stated && k >= iSearch && stores.length && !ranked && !asking) texts.push({ x: XS, y: P.get(stores[0].id).y - px(7), cls: "src", html: esc(data.sources.stated) });
  }
  const stage = S[k];
  if (k === iSearch && stores.length) {                             // the item's own queries, said once
    const q = data.edges.find((e) => e.verb === "searches" && e.label), last = P.get(stores[stores.length - 1].id);
    if (q) texts.push({ x: XS + px(2), y: last.y + CH + px(16), cls: "gs", html: "searched for: " + esc(q.label) });
  }
  if (stage.limit) {                                                // the rule reaches every product it judges
    for (const p of products) {
      const i = asideAt.get(p.id);
      if (i != null && i < k) continue;
      const v = p.checks[stage.limit.replace(/^limit:/, "")];
      lines.push({ a: stage.limit, b: p.id, cls: "ray " + (i === k ? (v === "fail" ? "fails" : "none") : "passes"), fromCardBottom: true });
    }
  }
  if (ranked) {
    order.slice(0, TOP).forEach((id) => {
      const n = nodes.get(id), p = P.get(id);
      const room = order.length > 1 ? Math.abs(P.get(order[0]).x - P.get(order[1]).x) : px(170);
      texts.push({ x: p.x, y: p.y - p.r - px(24), cls: "pn big mid", html: esc(short(n.label, Math.max(8, Math.min(18, Math.floor(room / px(8.2)))))) });
      texts.push({ x: p.x, y: p.y - p.r - px(9), cls: "pp big mid", html: esc((n.sub || "").split(" · ")[0]) + (n.picked ? " · the pick" : "") });
    });
  } else if (webbed) {
    searched.forEach((id) => { const p = P.get(id); if (p.big) texts.push({ x: p.x, y: p.y - RB - px(7), cls: "pn mid", html: esc(short(nodes.get(id).label, 13)) }); });
  }
  if (asking) (S[iAsk].row || []).forEach((id) => { const p = P.get(id); texts.push({ x: p.x, y: p.y + RB + px(14), cls: "pn mid", html: esc(short(nodes.get(id).label, 13)) }); });
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
  if (n.kind === "message") return `<title>${esc(n.sub || "")}</title><rect class="b pill${n.stopped ? " stopped" : ""}" width="${px(84)}" height="${px(18)}" rx="${px(9)}"/><text class="l mid" x="${px(42)}" y="${px(12.5)}">${esc(n.label)}</text>`;
  if (n.kind === "reply") return `<title>${esc(n.sub || "")}</title><rect class="b pill" width="${px(64)}" height="${px(18)}" rx="${px(9)}"/><circle class="od store" cx="${px(12)}" cy="${px(9)}" r="${px(3)}"/><text class="l" x="${px(21)}" y="${px(12.5)}">reply</text>`;
  if (n.kind === "review") return `<rect class="b pill" width="${px(72)}" height="${px(18)}" rx="${px(9)}"/><text class="l mid" x="${px(36)}" y="${px(12.5)}">${esc(short(n.label, 11))}</text><text class="s mid" x="${px(36)}" y="${px(30)}">${esc(short(n.sub, 14))}</text>`;
  const w = boxW(n), room = (w - tx - px(6)) / px(6.1);
  return `<title>${esc(n.label)}</title><rect class="b" width="${w}" height="${CH}" rx="${px(6)}"/>${dot}
    <text class="l" x="${tx}" y="${px(15.5)}">${esc(short(n.label, Math.floor(room)))}</text><text class="s" x="${tx}" y="${px(28.5)}">${esc(short(n.sub, Math.floor(room * 1.2)))}</text>
    ${n.kind === "gate" ? `<path class="bar" d="M${-px(12)} ${-px(14)}V${CH + px(14)}"/>` : ""}`;
}

function build() {
  const { svg, data } = X;
  svg.innerHTML = `<g transform="translate(0 ${px(16)})"><g class="lines"></g><g class="texts"></g><g class="nodes"></g></g>`;
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
    g.setAttribute("transform", `translate(${p.x} ${p.y})${p.s ? ` scale(${p.s})` : ""}`);
    if (p.r != null) {
      const [c, img, ring, q0, q1] = [g.querySelector(".c"), g.querySelector(".ph"), g.querySelector(".ring"), g.querySelector(".q0"), g.querySelector(".q1")];
      c.setAttribute("r", p.r); ring.setAttribute("r", p.r + px(3));
      if (img) { img.setAttribute("x", -p.r); img.setAttribute("y", -p.r); img.setAttribute("width", 2 * p.r); img.setAttribute("height", 2 * p.r); img.style.clipPath = `circle(${p.r}px at ${p.r}px ${p.r}px)`; }
      [q0, q1].forEach((q, i) => { q.setAttribute("cx", (i ? 1 : -1) * p.r * 0.5); q.setAttribute("cy", -p.r - px(3.5)); q.setAttribute("r", Math.max(px(1.6), p.r * 0.24)); });
    }
  }
  const at = (id, l, end) => {
    const p = P.get(id), w = p.w || CW, h = p.h || CH;
    if (p.r != null) return [p.x, p.y];
    if (l.fromCardBottom && end === "a") return [p.x + w / 2, p.y + h];
    if (l.toCorner && end === "b") return [p.x + px(8), p.y + h];
    return end === "a" ? [p.x + (P.get(l.b).x < p.x ? 0 : w), p.y + h / 2] : [p.x + (P.get(l.a).x > p.x ? w : 0), p.y + h / 2];
  };
  X.lineEls.forEach(({ l, e, t }) => {
    const [x1, y1] = l.raw ? l.raw : at(l.a, l, "a"), [x2, y2] = l.raw ? l.raw.slice(2) : at(l.b, l, "b");
    e.setAttribute("x1", x1); e.setAttribute("y1", y1); e.setAttribute("x2", x2); e.setAttribute("y2", y2);
    if (t) { const u = l.lt ?? 0.5; t.setAttribute("x", x1 + (x2 - x1) * u); t.setAttribute("y", y1 + (y2 - y1) * u + px(3)); }
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
    if (n.kind === "context_fact") g.classList.toggle("lit", k === data.stages.findIndex((s) => s.id === "order") && !!n.feeds_here);
    if (n.kind !== "product") continue;
    g.classList.toggle("aside", p.aside); g.classList.toggle("dashed", p.dashed); g.classList.toggle("pick", !!p.pick);
    g.classList.toggle("big", p.big); g.classList.toggle("read", p.read && p.r > px(3.8) && p.r < px(20));
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
    return { l, e, t: l.label ? el("text", { class: "lt mid" }, esc(l.label)) : null };
  });
  X.lineEls.forEach(({ t }) => t && X.gl.appendChild(t));
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
  const t0 = performance.now(), ms = instant || !X.motion ? 0 : X.ms || 750;
  const ease = (t) => (t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2);
  let frames = 0;
  const frame = () => {
    // the page's own clock, kept inside 0..1, and never slower than half speed by frame count, so a tween always lands
    frames += 1;
    const t = ms ? Math.max(0, Math.min(1, Math.max((performance.now() - t0) / ms, (frames * 8) / ms))) : 1, u = ease(t), cur = new Map();
    for (const [id, b] of target.P) {
      const a = from.get(id) || b;
      cur.set(id, { ...b, x: a.x + (b.x - a.x) * u, y: a.y + (b.y - a.y) * u, o: a.o + (b.o - a.o) * u, r: b.r != null ? (a.r ?? b.r) + (b.r - (a.r ?? b.r)) * u : undefined });
    }
    paint(cur);
    X.P = cur;
    if (t < 1) X.raf = requestAnimationFrame(frame);
  };
  if (ms) X.raf = requestAnimationFrame(frame); else frame();
}

// ---------- the surface the page uses ----------
export function mount(host, data, hooks, opts = {}) {
  if (X) { clearInterval(X.timer); cancelAnimationFrame(X.raf); }   // one canvas, one clock
  host.innerHTML = "";
  const svg = el("svg", { class: "xp", width: host.clientWidth, height: host.clientHeight });
  host.appendChild(svg);
  X = { host, svg, data, hooks, W: host.clientWidth - px(4), H: host.clientHeight - px(24), sel: null, motion: opts.motion !== false, lineEls: [] };
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
export function play(on, every = 1700) {
  if (!X) return;
  clearInterval(X.timer); X.timer = null;
  if (on) {
    X.motion = true;                                                // pressing Play asks for motion
    X.ms = Math.min(1100, Math.round(every * 0.45));
    if (X.k >= X.data.stages.length - 1) go(0, true);
    X.timer = setInterval(() => { if (X.k >= X.data.stages.length - 1) { play(false); X.hooks.onStage(X.data.stages[X.k], X.k, X.data.stages.length); } else go(X.k + 1); }, every);
  }
}
export function select(id) { if (X) { X.sel = id; X.els.forEach((x, i) => x.classList.toggle("sel", i === id)); } }
export { clock };
