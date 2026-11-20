// The candidates against the limits: a passing box for two limits, a strip for one.
// Elements are kept between draws and moved with CSS transitions, so a moved limit is seen to move.
// Products whose page never states a figure are not dots: they are counted in the dashed gutter.
import { money, niceDomain, num, opWords, plotAxes } from "/screen/model.js";
import { EASE, MOTION } from "/screen/motion.js";

const NS = "http://www.w3.org/2000/svg";
const R = 10;               // dot radius: 20 px across on the 960 canvas
const domains = new Map();  // axis ranges stay put while limits and measurements move; they only grow
const memory = new Map();   // per line: each candidate's last status and where the walls stood

function el(name, attrs = {}, parent) {
  const node = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (parent) parent.appendChild(node);
  return node;
}
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const move = (node, x, y) => { node.style.transform = `translate(${x}px, ${y}px)`; node.dataset.x = x; node.dataset.y = y; };
const known = (v) => v !== null && v !== undefined;

/** One axis: its values, range tails, wall and scale. */
function axis(line, index, from, to) {
  const checks = line.candidates.map((c) => c.checks[index]);
  const sample = checks[0];
  const values = [sample.bound.value];
  const tails = checks.map((ch) => {
    if (!known(ch.lhs)) return null;
    const t = ch.terms.find((term) => term.kind === "spread" || term.kind === "adjustable");
    const tail = t ? [ch.lhs - (t.value - t.low), ch.lhs + (t.high - t.value)] : [ch.lhs, ch.lhs];
    values.push(...tail);
    return tail;
  });
  const key = line.line_id + "|" + sample.limit_id;
  const d = niceDomain(values, domains.get(key));
  domains.set(key, d);
  const px = (v) => from + ((v - d.lo) / (d.hi - d.lo)) * (to - from);
  const ticks = [];
  for (let v = d.lo; v <= d.hi + 1e-9; v += d.step) ticks.push(+v.toFixed(6));
  return { index, checks, tails, sample, px, ticks, unit: sample.bound.unit, op: sample.op, bound: sample.bound,
    name: sample.terms.length === 1 ? sample.terms[0].label || sample.name : sample.name };
}

function axisTicks(line, index) {   // tick labels are needed before the scale exists, to size the tick column
  const ch = line.candidates.map((c) => c.checks[index]);
  const values = [ch[0].bound.value];
  for (const c of ch) if (known(c.lhs)) values.push(c.lhs);
  const d = niceDomain(values, domains.get(line.line_id + "|" + ch[0].limit_id));
  const out = [];
  for (let v = d.lo; v <= d.hi + 1e-9; v += d.step) out.push(num(+v.toFixed(6), ""));
  return out;
}

function wallLabel(a) {
  if (a.bound.owner === "shopper") return `${a.bound.owner_name}'s ${a.bound.label}: ${num(a.bound.value, a.unit)} ${a.unit}`;
  return `${a.bound.owner_name}: ${opWords(a.op)} ${num(a.bound.value, a.unit)} ${a.unit}`;
}

/** Labels for the pick and the next few only; a label that fits nowhere is left out (hover shows it). */
function placeLabels(dots, W, H, reserved, soft) {
  const taken = [...reserved, ...dots.map((d) => [d.x - R - 2, d.y - R - 2, d.x + R + 2, d.y + R + 2])];
  const over = (b, list) => list.some((t) => b[0] < t[2] && b[2] > t[0] && b[1] < t[3] && b[3] > t[1]);
  const out = (b) => b[0] < 0 || b[1] < 0 || b[2] > W || b[3] > H;
  for (const d of dots.filter((x) => x.texts.length).sort((a, b) => b.rank - a.rank || a.c.product.price_cents - b.c.product.price_cents)) {
    for (const text of d.texts) {
      const w = text.length * 9.4 + 4;
      const spots = [
        { dx: R + 6, dy: 6, anchor: "start", box: [d.x + R + 4, d.y - 9, d.x + R + 6 + w, d.y + 9] },
        { dx: 0, dy: -R - 6, anchor: "middle", box: [d.x - w / 2, d.y - R - 22, d.x + w / 2, d.y - R - 3] },
        { dx: 0, dy: R + 18, anchor: "middle", box: [d.x - w / 2, d.y + R + 3, d.x + w / 2, d.y + R + 21] },
        { dx: -R - 6, dy: 6, anchor: "end", box: [d.x - R - 6 - w, d.y - 9, d.x - R - 4, d.y + 9] },
        { dx: R, dy: -R - 2, anchor: "start", box: [d.x + R, d.y - R - 18, d.x + R + w, d.y - R] },
        { dx: R, dy: R + 14, anchor: "start", box: [d.x + R, d.y + R - 2, d.x + R + w, d.y + R + 16] },
      ];
      // walls are soft: only the pick's label may cross one (it has a white halo)
      d.label = spots.find((s) => !out(s.box) && !over(s.box, taken) && !over(s.box, soft))
        || (d.rank >= 3 ? spots.find((s) => !out(s.box) && !over(s.box, taken)) || spots.find((s) => !out(s.box)) : null);
      if (d.label) { d.text = text; taken.push(d.label.box); break; }
    }
  }
}

function layout(svg, line) {
  const W = svg.clientWidth, H = svg.clientHeight, axes = plotAxes(line), two = axes.length > 1;
  const tickH = 20, gutterH = 24, y0 = 2, x1 = W - 2, y1 = H - tickH - gutterH - 3;
  const tickW = two ? Math.max(...axisTicks(line, axes[1]).map((t) => t.length)) * 9.5 + 8 : 0;
  return { W, H, axes, two, tickH, gutterH, y0, y1, x0: tickW + 1, x1, gutterY: y1 + tickH + 2 + gutterH / 2 };
}

export function drawPlot(svg, line, shownId, onInspect) {
  const L = layout(svg, line);
  const { W, H, axes, two, x0, x1, y0, y1, gutterH, gutterY } = L;
  if (!W || !H) return;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const stamp = line.line_id + "|" + W + "x" + H + "|" + axes.join();
  if (svg.dataset.stamp !== stamp) {
    svg.dataset.stamp = stamp;
    svg.innerHTML = '<g class="frame"></g><rect class="passing"></rect><g class="walls"></g><g class="dots"></g><circle class="ring" r="14"></circle><g class="walltext"></g><g class="ghosts"></g><text class="hover"></text>';
  }
  const q = (s) => svg.querySelector(s);
  const frame = q(".frame"), dotsLayer = q(".dots"), ring = q(".ring"), passing = q(".passing"), walls = q(".walls"), wallText = q(".walltext"), hover = q(".hover");
  if (!axes.length) {
    frame.innerHTML = `<text x="8" y="24">No product has been found for this line yet.</text>`;
    passing.style.display = "none"; ring.style.opacity = 0; dotsLayer.innerHTML = ""; walls.innerHTML = ""; wallText.innerHTML = "";
    return;
  }
  passing.style.display = "";
  const Y = two ? axis(line, axes[1], y1 - 14, y0 + 30) : null;
  const X = axis(line, axes[0], x0 + 16, x1 - 18);
  const midY = (y0 + y1) / 2;
  const mem = memory.get(line.line_id) || { status: new Map(), wall: {} };
  memory.set(line.line_id, mem);
  const reserved = [];

  // the walls: where they stand and what their labels say
  const wx = X.px(X.bound.value), wy = two ? Y.px(Y.bound.value) : null;
  const textX = wallLabel(X), widthX = textX.length * 7.4 + 8;
  const rightX = wx + widthX < x1;                       // the x wall's label sits in the tick row, under the wall
  const labelBoxX = rightX ? [wx - 4, wx + widthX] : [wx - widthX, wx + 4];

  // frame: background, ticks, axis names, and the gutter that counts what was never stated
  let f = `<rect class="bg" x="${x0}" y="${y0}" width="${x1 - x0}" height="${y1 - y0}" rx="3"/>`;
  for (const t of X.ticks) {
    const tx = X.px(t);
    if (tx + 22 > labelBoxX[0] && tx - 22 < labelBoxX[1]) continue;
    f += `<text class="tick" x="${tx}" y="${y1 + 16}" text-anchor="middle">${num(t, X.unit === "in" ? "" : X.unit)}</text>`;
  }
  const nameX = `${X.name}, ${X.unit} →`;
  f += `<text x="${x1 - 6}" y="${y1 - 7}" text-anchor="end">${esc(nameX)}</text>`;
  reserved.push([x1 - 10 - nameX.length * 6.8, y1 - 24, x1, y1]);
  if (two) {
    const every = Math.abs(Y.px(Y.ticks[1]) - Y.px(Y.ticks[0])) < 24 ? 2 : 1;   // tick labels never crowd
    Y.ticks.forEach((t, i) => { if (i % every === 0) f += `<text class="tick" x="${x0 - 6}" y="${Y.px(t) + 6}" text-anchor="end">${num(t, "")}</text>`; });
    const nameY = `↑ ${Y.name}, ${Y.unit}`;
    f += `<text x="${x0 + 6}" y="${y0 + 18}">${esc(nameY)}</text>`;
    reserved.push([x0, y0, x0 + 10 + nameY.length * 6.8, y0 + 24]);
  }
  const unstated = line.candidates.filter((c) => c.status === "not_stated");
  const byFigure = new Map();
  for (const c of unstated) {
    const miss = (c.checks.find((ch) => ch.state === "not_stated") || {}).missing_figure || "a figure";
    byFigure.set(miss, (byFigure.get(miss) || 0) + 1);
  }
  const detail = [...byFigure].map(([k, n]) => `${k.replace(/_/g, " ")} ${n}`).join(" · ");
  f += `<rect class="gutter" x="${x0}" y="${gutterY - gutterH / 2}" width="${x1 - x0}" height="${gutterH}" rx="5"/>`;
  const gutterLead = `${unstated.length} of ${line.candidates.length} pages never state a figure`;
  const fits = (gutterLead.length + detail.length + 2) * 6.9 + 20 < x1 - x0;
  f += `<text class="guttertext" x="${x0 + 10}" y="${gutterY + 6}"><tspan>${unstated.length}</tspan> of ${line.candidates.length} pages never state a figure${detail && fits ? ": " + esc(detail) : ""}</text>`;
  frame.innerHTML = f;

  // the passing area and the walls
  const px0 = X.op === ">=" ? wx : x0, px1 = X.op === ">=" ? x1 : wx;
  const py0 = !two ? y0 : Y.op === ">=" ? y0 : wy, py1 = !two ? y1 : Y.op === ">=" ? wy : y1;
  Object.assign(passing.style, { x: px0 + "px", y: py0 + "px", width: Math.max(0, px1 - px0) + "px", height: Math.max(0, py1 - py0) + "px" });
  if (!walls.children.length) {
    walls.innerHTML = '<g class="wall wx"><line></line></g>' + (two ? '<g class="wall wy"><line></line></g>' : "");
    wallText.innerHTML = '<g class="wall wx"><text></text></g>' + (two ? '<g class="wall wy"><text></text></g>' : "");
  }
  const wallX = walls.querySelector(".wx"), textGX = wallText.querySelector(".wx");
  wallX.setAttribute("class", "wall wx " + X.bound.owner);
  textGX.setAttribute("class", "wall wx " + X.bound.owner);
  Object.entries({ x1: 0, x2: 0, y1: y0, y2: y1 + 3 }).forEach(([k, v]) => wallX.querySelector("line").setAttribute(k, v));
  const labelX = textGX.querySelector("text");
  labelX.textContent = textX;
  labelX.setAttribute("x", rightX ? -2 : 2); labelX.setAttribute("y", y1 + 17);
  labelX.setAttribute("text-anchor", rightX ? "start" : "end");
  move(wallX, wx, 0); move(textGX, wx, 0);
  const soft = [[wx - 3, y0, wx + 3, y1]];
  const at = line.candidates.map((c, i) => [X.checks[i].lhs, two ? Y.checks[i].lhs : 0, c.status])
    .filter(([a, b, s]) => known(a) && known(b) && s !== "not_stated" && s !== "struck").map(([a, b]) => [X.px(a), two ? Y.px(b) : midY]);
  if (two) {
    const wallY = walls.querySelector(".wy"), textGY = wallText.querySelector(".wy");
    wallY.setAttribute("class", "wall wy " + Y.bound.owner);
    textGY.setAttribute("class", "wall wy " + Y.bound.owner);
    Object.entries({ x1: x0, x2: x1, y1: 0, y2: 0 }).forEach(([k, v]) => wallY.querySelector("line").setAttribute(k, v));
    const labelY = textGY.querySelector("text"), textY = wallLabel(Y), widthY = textY.length * 7.4 + 8;
    labelY.textContent = textY;
    // the y wall's label goes where no dot sits: passing side first, right end first
    const up = Y.op === ">=";
    const spots = [[true, up], [false, up], [true, !up], [false, !up]].map(([right, above]) => ({ right, above,
      box: [right ? x1 - 8 - widthY : x0 + 6, above ? wy - 24 : wy + 4, right ? x1 - 4 : x0 + 10 + widthY, above ? wy - 3 : wy + 24] }));
    const free = (b) => b[1] > y0 && b[3] < y1 - 20 && !at.some(([dx, dy]) => dx + R > b[0] && dx - R < b[2] && dy + R > b[1] && dy - R < b[3]);
    const spot = spots.find((sp) => free(sp.box)) || spots[0];
    labelY.setAttribute("x", spot.right ? x1 - 8 : x0 + 8); labelY.setAttribute("y", spot.above ? -8 : 20);
    labelY.setAttribute("text-anchor", spot.right ? "end" : "start");
    move(wallY, 0, wy); move(textGY, 0, wy);
    reserved.push(spot.box);
    soft.push([x0, wy - 3, x1, wy + 3]);
  }

  // the dots: every candidate that states the figures (struck ones are crossed out and leave)
  const seen = new Map();
  const dots = line.candidates.map((c, i) => {
    const cx = X.checks[i], cy = two ? Y.checks[i] : null;
    if (c.status === "not_stated" || !known(cx.lhs) || (two && !known(cy.lhs))) return null;
    const x = X.px(cx.lhs), y = two ? Y.px(cy.lhs) : midY, inside = c.status === "inside";
    const spot = Math.round(x) + "," + Math.round(y);
    if (c.status !== "struck") seen.set(spot, (seen.get(spot) || 0) + 1);
    const noDelivery = inside && line.status !== "pick_up" && c.arrival && c.arrival.status !== "stated";
    return { c, x, y, spot, tailX: X.tails[i].map(X.px), tailY: two ? Y.tails[i].map(Y.px) : null, texts: [],
      rank: c.picked ? 3 : inside ? 2 : c.status === "outside" ? 1 : 0,
      cls: `dot ${c.status}${c.picked ? " picked" : ""}${noDelivery ? " nodelivery" : ""}${c.id === shownId ? " shown" : ""}` };
  }).filter(Boolean);
  const lead = new Map();   // products with the same figures share a spot: the best one is drawn
  for (const d of dots) if (d.c.status !== "struck" && (!lead.has(d.spot) || d.rank > lead.get(d.spot).rank)) lead.set(d.spot, d);
  for (const d of dots) { d.hidden = d.c.status !== "struck" && lead.get(d.spot) !== d; d.more = (seen.get(d.spot) || 1) - 1; }
  const visible = dots.filter((d) => !d.hidden && d.c.status !== "struck");
  const price = (d) => money(d.c.product.price_cents) + (d.more ? ` +${d.more}` : "");
  const next = visible.filter((d) => d.rank === 2).sort((a, b) => a.c.product.price_cents - b.c.product.price_cents).slice(0, 3);
  for (const d of visible) {
    if (d.rank === 3) d.texts = [`${price(d)} ${d.c.product.store}`, price(d)];
    else if (next.includes(d)) d.texts = [price(d)];
  }
  placeLabels(visible, W, H, reserved, soft);

  const wallMoved = known(mem.wall.x) && Math.abs(mem.wall.x - wx) > 0.5 ? ["x", mem.wall.x, wx]
    : two && known(mem.wall.y) && Math.abs(mem.wall.y - wy) > 0.5 ? ["y", mem.wall.y, wy] : null;
  const have = new Map([...dotsLayer.children].map((n) => [n.dataset.id, n]));
  for (const d of dots) {
    let node = have.get(d.c.id);
    const fresh = !node, was = mem.status.get(d.c.id);
    if (fresh) {
      node = el("g", { "data-id": d.c.id, tabindex: 0, role: "button" }, dotsLayer);
      el("rect", { class: "tail tx", y: -R, height: 2 * R, rx: R }, node);
      el("rect", { class: "tail ty", x: -R, width: 2 * R, rx: R }, node);
      el("circle", { class: "body", r: R }, node);
      el("line", { class: "strike", x1: -8, y1: -8, x2: 8, y2: 8 }, node);
      el("text", {}, node);
      const show = () => showHover(hover, node, W);
      node.addEventListener("click", () => onInspect(node.dataset.id));
      node.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") onInspect(node.dataset.id); });
      node.addEventListener("mouseenter", show); node.addEventListener("focus", show);
      node.addEventListener("mouseleave", () => { hover.textContent = ""; }); node.addEventListener("blur", () => { hover.textContent = ""; });
      move(node, d.x, d.y);
    }
    have.delete(d.c.id);
    // a dot turns grey as the moving limit passes it, not all at once
    let pass = 0;
    if (wallMoved && was && was !== d.c.status) {
      const [ax, from, to] = wallMoved, p = ax === "x" ? d.x : d.y;
      pass = Math.max(0, Math.min(1, (p - from) / (to - from || 1))) * 260;
    }
    node.style.setProperty("--pass", Math.round(pass) + "ms");
    node.setAttribute("class", d.cls);
    node.style.display = d.hidden ? "none" : "";
    if (d.c.status === "struck" && was && was !== "struck" && MOTION) {   // crossed out, then it leaves
      node.animate([{ opacity: 1 }, { opacity: 1, offset: 0.55 }, { opacity: 0 }], { duration: 700, easing: "ease-in" });
      node.querySelector(".strike").animate([{ strokeDasharray: "0 24" }, { strokeDasharray: "24 0" }], { duration: 260, easing: "ease-out" });
    }
    const [tx, ty] = node.querySelectorAll(".tail");
    const spanX = [Math.min(...d.tailX) - d.x - R, Math.abs(d.tailX[1] - d.tailX[0]) + 2 * R];
    const spanY = d.tailY ? [Math.min(...d.tailY) - d.y - R, Math.abs(d.tailY[1] - d.tailY[0]) + 2 * R] : [0, 0];
    tx.setAttribute("x", spanX[0]); tx.setAttribute("width", spanX[1] > 2 * R + 1 ? spanX[1] : 0);
    ty.setAttribute("y", spanY[0]); ty.setAttribute("height", spanY[1] > 2 * R + 1 ? spanY[1] : 0);
    const text = node.querySelector("text");
    text.textContent = d.label ? d.text : "";
    if (d.label) { text.setAttribute("x", d.label.dx); text.setAttribute("y", d.label.dy); text.setAttribute("text-anchor", d.label.anchor); }
    const why = d.c.picked ? "the pick" : d.c.status === "inside" ? (/nodelivery/.test(d.cls) ? "inside, no delivery time stated" : "inside") : d.c.reason || d.c.status;
    node.dataset.say = `${money(d.c.product.price_cents)} ${d.c.product.store}: ${why}${d.more ? ` (+${d.more} more here)` : ""}`;
    node.setAttribute("aria-label", `${d.c.product.title}, ${node.dataset.say}`);
    move(node, d.x, d.y);
    if (d.c.picked) dotsLayer.appendChild(node);
    if (fresh && was === undefined && mem.status.size && MOTION) node.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 300 });
  }
  for (const node of have.values()) node.remove();
  mem.status = new Map(line.candidates.map((c) => [c.id, c.status]));
  mem.wall = { x: wx, y: wy };
  const picked = dots.find((d) => d.c.picked);
  ring.style.opacity = picked ? 1 : 0;
  if (picked) move(ring, picked.x, picked.y);
}

function showHover(hover, node, W) {
  const text = node.dataset.say || "", w = text.length * 8.6, x = +node.dataset.x, y = +node.dataset.y;
  hover.textContent = text;
  hover.setAttribute("x", Math.max(4, Math.min(W - w - 4, x - w / 2)));
  hover.setAttribute("y", y > 36 ? y - R - 8 : y + R + 20);
}

/**
 * A line opens: the limits appear, the candidates settle from the left, the ones that never state a figure
 * slide into the dashed gutter, the ring lands on the pick. Returns when each part happens (ms).
 */
export function plotIntro(svg, line, t0) {
  const times = { walls: t0, dots: t0 + 220, unstated: t0 + 520, pick: t0 + 900, end: t0 + 1200 };
  if (!MOTION || !svg.querySelector(".dots")) return times;
  const L = layout(svg, line);
  const fade = (node, delay, duration = 260) => node && node.animate([{ opacity: 0 }, { opacity: node.classList.contains("passing") ? 0.09 : 1 }],
    { duration, delay, easing: "ease-out", fill: "backwards" });
  for (const s of [".walls", ".walltext", ".passing"]) fade(svg.querySelector(s), times.walls);
  const origin = [L.x0 - 6, (L.y0 + L.y1) / 2];
  const nodes = [...svg.querySelectorAll(".dot")].filter((n) => n.style.display !== "none" && !n.classList.contains("struck"));
  nodes.sort((a, b) => a.dataset.x - b.dataset.x).forEach((node, i) => {
    node.animate([{ transform: `translate(${origin[0]}px, ${origin[1]}px)`, opacity: 0 }, { opacity: 1, offset: 0.3 },
      { transform: `translate(${node.dataset.x}px, ${node.dataset.y}px)`, opacity: 1 }],
      { duration: 420, delay: times.dots + i * 22, easing: EASE, fill: "backwards" });
  });
  times.unstated = times.dots + Math.min(nodes.length, 12) * 22 + 260;
  const ghosts = svg.querySelector(".ghosts");
  ghosts.innerHTML = "";
  const n = Math.min(10, line.candidates.filter((c) => c.status === "not_stated").length);
  for (let i = 0; i < n; i++) {
    const g = el("circle", { class: "ghost", r: R - 1 }, ghosts);
    const tx = L.x0 + 24 + i * 9;
    g.animate([{ transform: `translate(${origin[0]}px, ${origin[1]}px)`, opacity: 0 }, { opacity: 1, offset: 0.25 }, { opacity: 1, offset: 0.75 },
      { transform: `translate(${tx}px, ${L.gutterY}px)`, opacity: 0 }],
      { duration: 480, delay: times.unstated + i * 28, easing: EASE, fill: "both" }).finished.then(() => g.remove(), () => g.remove());
  }
  fade(svg.querySelector(".guttertext"), times.unstated + 200);
  fade(svg.querySelector(".gutter"), times.walls);
  times.pick = times.unstated + n * 28 + 380;
  const ring = svg.querySelector(".ring");
  if (ring.style.opacity !== "0") ring.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 300, delay: times.pick, easing: "ease-out", fill: "backwards" });
  times.end = times.pick + 300;
  return times;
}
