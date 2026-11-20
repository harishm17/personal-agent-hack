// The run explored as a graph that grows, for one item. Everything drawn comes from GET /api/graph/explore:
// nodes, edges and the stages in which nodes appear or are set aside. This file only places and moves them.
// Positions are computed per stage (never simulated) and tweened between stages, so any paused stage is exact.
const NS = "http://www.w3.org/2000/svg";
const REM = parseFloat(getComputedStyle(document.documentElement).fontSize) / 16;
const px = (n) => n * REM;
const CW = px(160), CH = px(40), SP = px(29), R = px(13), RS = px(9), RB = px(22);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const ownerClass = (o) => (o === "issuer" || o === "shopper" ? o : o === "system" || o === "web" ? "" : "store");
const short = (s, n) => (String(s || "").length > n ? String(s).slice(0, n - 1).trimEnd() + "…" : String(s || ""));
const clock = (at) => (at ? String(at).slice(11, 16) : "");
const INK = document.createElement("canvas").getContext("2d");
const FACE = getComputedStyle(document.documentElement).getPropertyValue("--f") || "system-ui, sans-serif";
/** The width a text takes at a size (in the design's px) and weight, with a little room to spare. */
function wide(text, size, weight = 400) { INK.font = `${weight} ${px(size)}px ${FACE}`; return INK.measureText(String(text ?? "")).width * 1.05; }
/** Whole words onto as many lines as it takes for each to fit `max`; a word is never broken or cut. */
function wrap(text, size, weight, max) {
  const lines = [];
  for (const word of String(text ?? "").split(/\s+/).filter(Boolean)) {
    const last = lines[lines.length - 1];
    if (last != null && wide(last + " " + word, size, weight) <= max) lines[lines.length - 1] = last + " " + word;
    else lines.push(word);
  }
  return lines;
}
const WIDTHS = new Map();
/** A card is as wide as its words need. */
function boxW(n) {
  if (!WIDTHS.has(n.id)) {
    const one = n.kind === "store" || !n.sub;
    WIDTHS.set(n.id, Math.max(px(112), Math.max(wide(n.label, 13, 500), one ? 0 : wide(n.sub, 12)) + px(32)));
  }
  return WIDTHS.get(n.id);
}
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
  const put = (id, x, y, more = {}) => P.set(id, { x, y, w: nodes.has(id) && nodes.get(id).kind !== "product" ? boxW(nodes.get(id)) : undefined, ...more, o: (added.get(id) ?? 0) <= k ? more.o ?? 1 : 0 });
  const GAP = px(22), wOf = (kinds) => Math.max(px(112), ...data.nodes.filter((n) => kinds.includes(n.kind)).map(boxW));
  const XI = wOf(["person", "event", "context_person"]) + GAP, XS = XI + wOf(["order_item", "home_fact", "sheet_value", "context_message"]) + GAP;
  const PX0 = XS + wOf(["store", "web"]) + px(22), YROW = H * 0.57, YB = H * 0.77, FW = wOf(["context_fact"]);

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
    known.forEach((n, i) => { fy.set(n.id, i * (CH + px(6))); put(n.id, XS, fy.get(n.id), { o: k >= iOrder && !n.used ? 0.4 : 1 }); });
    const verbs = data.edges.filter((e) => e.feeds).map((e) => wide(e.verb + " ✓", 12));
    const XD = XS + FW + Math.max(px(120), ...verbs) + px(28), XE = XD + wOf(["person"]) + px(18);
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
    let lx = PX0;
    limits.forEach((n) => { put(n.id, lx, 0); lx += boxW(n) + px(24); });
    // the event's people, messages and facts fold back into it
    [...around, ...notes, ...known].forEach((n) => put(n.id, 0, 0, { o: 0, w: boxW(n) }));
  }
  // what it already knows: one node for all of it, and on their own only the few that bear on this item's pick
  const memories = data.nodes.filter((n) => n.kind === "memory");
  const own = memories.filter((n) => n.own), all = memories.find((n) => n.group);
  if (all) put(all.id, 0, leftBottom + px(4));
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
  const gcols = 8, gsp = px(20), RQ = px(5);
  let gx = ranked ? 0 : XS;
  const asidePos = new Map();
  for (const g of ordered) {
    if (ranked) {                                                   // one quiet row: a count, a reason, its dots
      const label = `${g.ids.length} ${g.reason}`, lw = label.length * px(6.6) + px(10);
      texts.push({ x: gx, y: H - px(3), cls: "gs", html: esc(label) });
      g.ids.forEach((id, i) => asidePos.set(id, { x: gx + lw + i * px(11) + RQ, y: H - px(7), quiet: true }));
      gx += lw + g.ids.length * px(11) + px(16);
      continue;
    }
    const w = Math.max(px(104), Math.min(gcols, g.ids.length) * gsp + px(6));
    texts.push({ x: gx, y: YB + px(4), cls: "gh", html: `<tspan class="gc">${g.ids.length}</tspan> ${esc(g.reason)}` });
    texts.push({ x: gx, y: YB + px(20), cls: "gs", html: esc(S[g.stage].rule || S[g.stage].title) });
    g.ids.forEach((id, i) => asidePos.set(id, { x: gx + (i % gcols) * gsp + RS, y: YB + px(38) + Math.floor(i / gcols) * (gsp + px(1)) }));
    gx += w + px(8);
  }

  // the web row and the ranked line
  const web = nodes.get("web:search");
  const reviews = data.nodes.filter((n) => n.kind === "review");
  const searched = reviews.map((r) => r.product);
  const order = iRank >= 0 ? S[iRank].order : [];
  const webbed = iWeb >= 0 && k >= iWeb;
  const RBIG = px(36), GS = 1.15, CY = H * 0.34;
  const gateW = nodes.has("gate") ? boxW(nodes.get("gate")) * GS : 0;
  const gateX = W - gateW - px(2), leftEdge = XS + px(40), head = gateX - px(52) - RBIG;
  let TOP = Math.min(5, order.length);
  while (TOP > 2 && (head - leftEdge - RBIG) / (TOP - 1) < px(132)) TOP -= 1;
  const big = new Set(ranked ? order.slice(0, TOP) : webbed ? searched : []);
  const linePos = new Map();
  if (ranked) {
    const n = TOP, step = n > 1 ? Math.min(px(170), (head - leftEdge - RBIG) / (n - 1)) : 0;
    order.slice(0, TOP).forEach((id, i) => linePos.set(id, { x: head - i * step, y: CY }));
    // the rest that pass, in order, in a quiet block under them
    const tail = order.slice(TOP), trows = 2, tsp = px(18), named0 = order.slice(0, TOP).map((id) => wrap(nodes.get(id).label, 14, 600, (TOP > 1 ? step : px(200)) - px(14)).length);
    const ty = CY + RBIG + px(32) + Math.max(1, ...named0) * px(17) + px(88);
    tail.forEach((id, i) => linePos.set(id, { x: leftEdge + px(8) + Math.floor(i / trows) * tsp, y: ty + (i % trows) * tsp }));
    if (tail.length) texts.push({ x: leftEdge + px(8) + Math.ceil(tail.length / trows) * tsp + px(6), y: ty + px(13), cls: "gs", html: `${tail.length} more that pass` });
  } else if (webbed) {
    const step = Math.min(px(120), (W - PX0 - px(6)) / Math.max(1, searched.length));   // all of them inside the canvas
    searched.forEach((id, i) => linePos.set(id, { x: PX0 + step / 2 + i * step, y: YROW }));
  }

  if (asking) {
    const LANE = px(24), MW = px(84), RW = px(64), xp = PX0 + RB, spine = xp + RB + px(10), xm = spine + px(10);
    const storeX = W - wOf(["store"]), xr2 = storeX - RW - px(36), xg = (xm + MW + xr2) / 2;
    const room = xg - (xm + MW);
    let ly = YROW - px(46), kept = 0, landed = 0;
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
        let shown = chips.length;                                   // as many whole parts as fit on the line, never a cut one
        while (shown > 1 && wide(chips.slice(0, shown).map((c) => c.text).join(" · ") + " +9", 12, 500) > 2 * room - px(16)) shown -= 1;
        P.set(m.id, { x: xm, y: ly, o: 1, w: MW, h: px(18) });
        lines.push({ raw: [spine, y9, xm, y9], cls: "" }, { raw: [xm + MW, y9, xg, y9], cls: m.stopped ? "fails" : "lit" });
        // what the guard withheld sits on the guard line, struck
        if (chips.length) texts.push({ x: xg, y: y9 + px(3.5), cls: "chip on mid", at: BEAT.chips + landed++ * BEAT.chip, html: chips.slice(0, shown).map((c) => esc(c.text)).join(" · ") + (chips.length > shown ? ` +${chips.length - shown}` : "") });
        const r = data.nodes.find((n) => n.kind === "reply" && n.message === m.id);
        if (r) {
          P.set(r.id, { x: xr2, y: ly, o: 1, w: RW, h: px(18) });
          kept += r.remembered ? 1 : 0;
          lines.push({ raw: [xg, y9, xr2, y9], cls: "lit" }, { raw: [xr2 + RW, y9, storeX, cy], cls: "lit" });
        } else if (!m.stopped) lines.push({ raw: [xg, y9, storeX, cy], cls: "lit" });
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
    const where = !born ? { x: src.x + src.w / 2, y: src.y + CH / 2 } : gone || line || h;
    P.set(p.id, { ...where, o: born ? (gone ? 0.75 : 1) : 0, r: gone ? (gone.quiet ? RQ : RS) : big.has(p.id) ? (ranked ? RBIG : RB) : ranked ? px(8) : R,
      big: big.has(p.id) && !gone, aside: !!gone, dashed: k >= iRead && (S[iRead]?.not_stated || []).includes(p.id),
      read: k >= iRead, pick: ranked && p.picked, checked: limits.filter((l) => { const i = S.findIndex((x) => x.limit === l.id); return i >= 0 && i <= k; }).map((l) => l.id) });
  }
  if (web) put(web.id, XS, YROW - CH / 2, ranked ? { o: 0 } : {});
  reviews.forEach((r) => {
    const p = P.get(r.product);
    P.set(r.id, { x: p.x - reviewW(r) / 2, y: p.y + p.r + px(10), w: reviewW(r), h: px(18), o: (added.get(r.id) ?? 99) <= k && p.big && !asking ? 1 : 0, pill: true });
  });
  // the gate, and the cart beyond it
  if (nodes.has("gate")) put("gate", gateX, CY - (CH * GS) / 2, { gate: true, s: GS, w: gateW, h: CH * GS });
  data.nodes.filter((n) => n.kind === "cart").forEach((n, i) => put(n.id, gateX, CY + CH * GS + px(14) + i * (CH + px(8))));

  // the lines of this stage
  const vis = (id) => P.get(id)?.o > 0;
  const card = (a, b, cls = "", label = "") => { if (vis(a) && vis(b)) lines.push({ a, b, cls, label, card: true }); };
  for (const e of data.edges) {
    if (e.feeds) { if (k >= iOrder && vis(e.from) && vis(e.to)) lines.push({ a: e.from, b: e.to, card: true, cls: e.matches === false ? "fails" : "lit",
      label: e.verb + (e.matches === true ? " ✓" : e.matches === false ? " ✕" : ""), lt: nodes.get(e.to)?.kind === "person" ? 0.5 : 0.3 }); }
    else if (e.verb === "says") card(e.from, e.to, "", "");
    else if (e.verb === "wrote" && nodes.get(e.to)?.kind === "context_message") { if (nodes.get(e.from)?.kind === "context_person") card(e.from, e.to, "", ""); }
    else if (e.prescribed) { if (eventPhase) card(e.from, e.to, "", ""); }
    else if (e.verb === "wrote" || e.verb === "measured") card(e.from, e.to, "", "");
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
    if (q) texts.push({ x: PX0, y: y + px(4), cls: "gs", html: "searched for: " + esc(q.label) });   // under the products found
  }
  if (stage.limit) {                                                // the rule reaches every product it judges
    for (const p of products) {
      const i = asideAt.get(p.id);
      if (i != null && i < k) continue;
      const v = p.checks[stage.limit.replace(/^limit:/, "")];
      const cls = i === k ? (v === "fail" ? "fails" : "none") : "passes";
      lines.push({ a: stage.limit, b: p.id, cls: "ray " + cls, fromCardBottom: true, at: BEAT.rays, op: cls === "fails" ? 0.7 : cls === "passes" ? 0.3 : 0.55 });
    }
  }
  if (ranked) {
    const room = (TOP > 1 ? Math.abs(P.get(order[0]).x - P.get(order[1]).x) : px(200)) - px(14), LH = px(17);
    const named = order.slice(0, TOP).map((id) => ({ id, lines: wrap(nodes.get(id).label, 14, 600, room) }));
    const most = Math.max(1, ...named.map((x) => x.lines.length));
    named.forEach(({ id, lines }) => {
      const n = nodes.get(id), p = P.get(id);
      lines.forEach((t, i) => texts.push({ x: p.x, y: p.y + p.r + px(20) + i * LH, cls: "pn big mid", html: esc(t) }));
      texts.push({ x: p.x, y: p.y + p.r + px(22) + most * LH, cls: "pp big mid", html: esc((n.sub || "").split(" · ")[0]) + (n.picked ? " · the pick" : "") });
      const r = reviews.find((x) => x.product === id);
      if (r && P.get(r.id)) Object.assign(P.get(r.id), { x: p.x - reviewW(r) / 2, y: p.y + p.r + px(32) + most * LH });
    });
    X.rankedBottom = CY + RBIG + px(32) + most * LH + px(52);
  }
  if (asking) (S[iAsk].row || []).forEach((id) => { const p = P.get(id); wrap(nodes.get(id).label, 13, 500, px(170)).forEach((t, i) => texts.push({ x: p.x + RB, y: p.y + RB + px(16) + i * px(16), cls: "pn end", html: esc(t) })); });
  return { P, lines, texts };
}

// ---------- drawing ----------
function reviewSays(n) {
  // only the parts the record has: "4.8 ★ · 28 reviews", "4.8 ★", or "a review" when it is one quoted sentence
  const parts = [n.rating != null ? `${n.rating} ★` : "", n.review_count != null ? `${n.review_count} ${n.review_count === 1 ? "review" : "reviews"}` : ""].filter(Boolean);
  return parts.length ? parts.join(" · ") : "a review";
}
function reviewWhere(n) {
  const product = X.data.nodes.find((p) => p.id === n.product), site = n.sub || "";
  return product && site && site === product.owner ? ["on the seller's", "own page"] : site ? ["reviews on", site] : [];
}
const reviewW = (n) => Math.max(px(72), wide(reviewSays(n), 12, 500) + px(22));

function thumb(url) {
  // ask the image host for a small copy; a host that does not know the parameter ignores it
  try { const u = new URL(url); u.searchParams.set("width", "240"); return u.href; } catch (e) { return url; }
}

function glyph(n) {
  if (n.kind === "product") {
    // a product is its photo; with no photo, a plain tile carrying the first word of its name
    const img = n.image_url ? `<image class="ph" href="${esc(thumb(n.image_url))}" preserveAspectRatio="xMidYMid slice"/>` : "";
    return `<title>${esc(n.label)} · ${esc(n.sub || "")}</title><rect class="c"/><text class="tw mid">${esc(String(n.label || "").split(/\s+/)[0].slice(0, 4))}</text>${img}<rect class="bd"/><rect class="ring"/><circle class="q q0"/><circle class="q q1"/>`;
  }
  const one = n.kind === "store" || !n.sub;                           // a store's card needs no second line
  const dot = n.kind === "web" || n.kind === "review" ? "" : `<circle class="od ${ownerClass(n.owner)}" cx="${px(11)}" cy="${one ? CH / 2 : px(13.5)}" r="${px(3)}"/>`;
  const tx = dot ? px(20) : px(10);
  if (n.kind === "message") return `<title>${esc(n.sub || "")}</title><rect class="b pill${n.stopped ? " stopped" : ""}" width="${px(84)}" height="${px(18)}" rx="${px(9)}"/><text class="l mid" x="${px(42)}" y="${px(12.5)}">${esc(n.label)}</text>`;
  if (n.kind === "reply") return `<title>${esc(n.sub || "")}</title><rect class="b pill" width="${px(64)}" height="${px(18)}" rx="${px(9)}"/><circle class="od store" cx="${px(12)}" cy="${px(9)}" r="${px(3)}"/><text class="l" x="${px(21)}" y="${px(12.5)}">reply</text>`;
  if (n.kind === "review") {
    const w = reviewW(n), where = reviewWhere(n);
    return `<rect class="b pill" width="${w}" height="${px(18)}" rx="${px(9)}"/><text class="l mid" x="${w / 2}" y="${px(12.5)}">${esc(reviewSays(n))}</text>${where.map((t, i) => `<text class="s mid" x="${w / 2}" y="${px(33) + i * px(14)}">${esc(t)}</text>`).join("")}`;
  }
  const w = boxW(n), room = (w - tx - px(6)) / px(6.9);
  return `<title>${esc(n.label)}</title><rect class="b" width="${w}" height="${CH}" rx="${px(6)}"/>${dot}
    <text class="l" x="${tx}" y="${one ? CH / 2 + px(4.5) : px(17)}">${esc(n.label)}</text>${one ? "" : `<text class="s" x="${tx}" y="${px(32)}">${esc(n.sub)}</text>`}
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
    if (n.kind === "product") {
      const img = g.querySelector(".ph");
      if (!img) g.classList.add("noimg"); else img.addEventListener("error", () => { g.classList.add("noimg"); img.remove(); });
    }
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
      const [c, bd, img, ring, q0, q1, tw] = [".c", ".bd", ".ph", ".ring", ".q0", ".q1", ".tw"].map((q) => g.querySelector(q));
      const box = (e, r, round) => { e.setAttribute("x", -r); e.setAttribute("y", -r); e.setAttribute("width", 2 * r); e.setAttribute("height", 2 * r); e.setAttribute("rx", round); };
      const round = Math.max(px(2), p.r * 0.2);
      box(c, p.r, round); box(bd, p.r, round); box(ring, p.r + px(3.5), round + px(3));
      if (img) { box(img, p.r, 0); img.style.clipPath = `inset(0 round ${round}px)`; }
      tw.setAttribute("y", px(4)); tw.style.visibility = p.r >= px(12) ? "" : "hidden";
      [q0, q1].forEach((q, i) => { q.setAttribute("cx", (i ? 1 : -1) * p.r * 0.45); q.setAttribute("cy", -p.r - px(4)); q.setAttribute("r", px(2.2)); });
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
    g.classList.toggle("big", p.big); g.classList.toggle("read", p.read && p.r >= px(12) && p.r < px(20));
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
  X.textEls = target.texts.map((t) => { const e = el("text", { class: t.cls, x: t.x, y: t.y }, t.html); X.gt.appendChild(e); return { t, e }; });
}

// ---------- time ----------
// How long each stage holds at 1x (ms), by what it shows. One table; the last stage holds until the viewer leaves.
const HOLD = { event: 1500, order: 1500, known: 2000, search: 4000, reading: 2500, rule: 5000, asking: 4000, web: 2500, ranking: 2500, signature: 2500 };
const hold = (s) => HOLD[s.id.split(":")[0]] ?? 2500;
// The beats inside a stage (ms at 1x): a store's products arrive in a quick run, one store after another; a rule lights,
// its lines reach the products, then the failing ones move aside together; the withheld parts land one after another.
const BEAT = { store: 1000, each: 22, rays: 700, sweep: 2300, sweepFor: 900, chips: 1200, chip: 500, fade: 300 };
const ease = (t) => (t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2);
const unit = (v) => Math.max(0, Math.min(1, v));

function choreograph(k) {
  // when each thing starts to move within the stage, and for how long
  const s = X.data.stages[k], kind = s.id.split(":")[0], T = new Map();
  if (kind === "search") {
    X.data.nodes.filter((n) => n.kind === "store").forEach((st, si) => {
      T.set(st.id, { delay: si * BEAT.store, dur: 350 });
      X.data.nodes.filter((n) => n.kind === "product" && n.owner === st.owner)
        .forEach((p, i) => T.set(p.id, { delay: 250 + si * BEAT.store + i * BEAT.each, dur: 420 }));
    });
  }
  if (kind === "rule") s.node_ids_set_aside.forEach((id) => T.set(id, { delay: BEAT.sweep, dur: BEAT.sweepFor }));
  return T;
}

const halt = () => { cancelAnimationFrame(X.raf); clearTimeout(X.to); };
const again = () => { halt(); X.raf = requestAnimationFrame(tick); X.to = setTimeout(tick, 40); };

function tick() {
  const A = X.anim, S = X.data.stages;
  halt();
  if (!A) return;
  // the page's own clock; a frame never counts for less than 8 ms, so a stage always finishes
  const now = performance.now(), dt = Math.max(8, Math.min(100, now - (X.last ?? now)));
  X.last = now;
  if (X.playing) A.elapsed += dt * X.speed;
  const cur = new Map();
  for (const [id, b] of A.target.P) {
    const a = A.from.get(id) || b, c = A.T.get(id);
    const u = A.still ? 1 : ease(unit((A.elapsed - (c?.delay ?? 0)) / (c?.dur ?? 750)));
    cur.set(id, { ...b, x: a.x + (b.x - a.x) * u, y: a.y + (b.y - a.y) * u, o: a.o + (b.o - a.o) * u, r: b.r != null ? (a.r ?? b.r) + (b.r - (a.r ?? b.r)) * u : undefined });
  }
  paint(cur);
  X.P = cur;
  const shown = (at) => (A.still || at == null ? 1 : unit((A.elapsed - at) / BEAT.fade));
  X.lineEls.forEach(({ l, e }) => { if (l.at != null) e.style.opacity = shown(l.at) * (l.op ?? 1); });
  X.textEls.forEach(({ t, e }) => { if (t.at != null) e.style.opacity = shown(t.at); });
  // the caption counts as the group moves aside (the numbers are the stage's own; read from its caption if not given apart)
  const said = /^(.*): (\d+) set aside, (\d+) left\.$/.exec(S[X.k].caption || "");
  const c = S[X.k].counting || (S[X.k].limit && said ? { lead: said[1], out: Number(said[2]), left: Number(said[3]) } : null);
  if (c && X.hooks.onCount) {
    const n = A.still ? c.out : Math.round(c.out * unit((A.elapsed - BEAT.sweep) / BEAT.sweepFor));
    if (n !== A.count) { A.count = n; X.hooks.onCount(`${c.lead}: ${n} set aside, ${c.left + c.out - n} left.`); }
  }
  if (X.playing && A.elapsed >= A.hold) {
    if (X.k < S.length - 1) return go(X.k + 1);
    X.playing = false;                                               // the last stage: it stays
    X.hooks.onStage(S[X.k], X.k, S.length);
  }
  if (X.playing) again();
}

function go(k, instant = false) {
  const S = X.data.stages;
  k = Math.max(0, Math.min(S.length - 1, k));
  const target = plan(k), from = X.P || target.P;
  X.k = k;
  halt();
  const still = instant || !X.motion || !X.playing;                  // a step or a scrub lands at once; nothing moves while paused
  X.anim = { target, from, T: still ? new Map() : choreograph(k), elapsed: 0, hold: hold(S[k]), still, count: -1 };
  dress(k, target);
  X.hooks.onStage(S[k], k, S.length);
  X.last = undefined;
  tick();
}

// ---------- the surface the page uses ----------
export function mount(host, data, hooks, opts = {}) {
  if (X) halt();                                                     // one canvas, one clock
  host.innerHTML = "";
  const cw = host.clientWidth, ch = host.clientHeight, DW = Math.max(cw, px(1036)), DH = Math.max(ch, px(580));
  const svg = el("svg", { class: "xp", width: cw, height: ch, viewBox: `0 0 ${DW} ${DH}`, preserveAspectRatio: "xMinYMin meet" });
  host.appendChild(svg);
  X = { host, svg, data, hooks, W: DW - px(4), H: DH - px(24), sel: null, motion: opts.motion !== false, lineEls: [], textEls: [],
    playing: false, speed: opts.speed === "slow" ? 0.5 : 1 };
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
export const playing = () => !!X?.playing;
/** Play, or pause: paused, the caption stays and nothing moves; playing again goes on from where it stopped. */
export function play(on) {
  if (!X) return;
  halt();
  X.playing = !!on;
  if (!on) return;
  X.motion = true;                                                  // pressing Play asks for motion
  const A = X.anim, last = X.data.stages.length - 1;
  if (X.k >= last && (!A || A.still || A.elapsed >= A.hold)) return go(0, true);   // from the end: once more from the start
  X.last = undefined;
  again();
}
export const step = (d) => { if (X) { play(false); go(X.k + d, true); } };
export const jump = (k) => { if (X) go(k, true); };
export const speed = (v) => { if (X) X.speed = v === "slow" ? 0.5 : 1; };
export function select(id) { if (X) { X.sel = id; X.els.forEach((x, i) => x.classList.toggle("sel", i === id)); } }
export { clock };
