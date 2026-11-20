// The candidates against the limits: a passing box for two limits, a strip for one.
// Elements are kept between draws and moved with CSS transitions, so a moved limit is seen to move.
import { money, niceDomain, num, opWords, plotAxes } from "/screen/model.js";

const NS = "http://www.w3.org/2000/svg";
const R = 10;            // dot radius: 20 px across on the 960 canvas
const domains = new Map(); // axis ranges stay put while limits and measurements move; they only grow

function el(name, attrs = {}, parent) {
  const node = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (parent) parent.appendChild(node);
  return node;
}
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const move = (node, x, y) => { node.style.transform = `translate(${x}px, ${y}px)`; };

/** One axis: its values, range tails, wall and scale. */
function axis(line, index, from, to) {
  const checks = line.candidates.map((c) => c.checks[index]);
  const sample = checks[0];
  const values = [sample.bound.value];
  const tails = checks.map((ch) => {
    if (ch.lhs === null || ch.lhs === undefined) return null;
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
  const missing = checks.find((ch) => ch.state === "not_stated");
  return { index, checks, tails, sample, px, ticks, from, to,
    unit: sample.bound.unit, op: sample.op, bound: sample.bound,
    missingLabel: missing ? (missing.missing_figure || "figure").replace(/_/g, " ") : sample.name };
}

function wallLabel(a) {
  const what = a.bound.owner === "shopper" ? `${a.bound.label} ${num(a.bound.value, a.unit)}` : num(a.bound.value, a.unit);
  return `${a.bound.owner_name}: ${opWords(a.op)} ${what} ${a.unit}`;
}

/** Greedy label placement: the pick first; a label that fits nowhere is left out. */
function placeLabels(dots, W, H) {
  const taken = dots.map((d) => [d.x - R - 2, d.y - R - 2, d.x + R + 2, d.y + R + 2]);
  const hits = (b) => b[0] < 0 || b[1] < 0 || b[2] > W || b[3] > H || taken.some((t) => b[0] < t[2] && b[2] > t[0] && b[1] < t[3] && b[3] > t[1]);
  const order = [...dots].sort((a, b) => b.rank - a.rank);
  for (const d of order) {
    const w = d.text.length * (d.rank >= 3 ? 9.6 : 9) + 2;
    const spots = [
      { dx: R + 6, dy: 6, anchor: "start", box: [d.x + R + 4, d.y - 9, d.x + R + 6 + w, d.y + 9] },
      { dx: 0, dy: -R - 6, anchor: "middle", box: [d.x - w / 2, d.y - R - 22, d.x + w / 2, d.y - R - 3] },
      { dx: 0, dy: R + 18, anchor: "middle", box: [d.x - w / 2, d.y + R + 3, d.x + w / 2, d.y + R + 21] },
      { dx: -R - 6, dy: 6, anchor: "end", box: [d.x - R - 6 - w, d.y - 9, d.x - R - 4, d.y + 9] },
    ];
    d.label = spots.find((s) => !hits(s.box)) || null;
    if (d.label) taken.push(d.label.box);
  }
}

export function drawPlot(svg, line, shownId, onInspect) {
  const W = svg.clientWidth, H = svg.clientHeight;
  if (!W || !H) return;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const axes = plotAxes(line);
  if (svg.dataset.line !== line.line_id || svg.dataset.size !== W + "x" + H || svg.dataset.axes !== axes.join()) {
    svg.dataset.line = line.line_id; svg.dataset.size = W + "x" + H; svg.dataset.axes = axes.join();
    svg.innerHTML = '<g class="frame"></g><rect class="passing"></rect><g class="walls"></g><g class="dots"></g><circle class="ring" r="15"></circle>';
  }
  const frame = svg.querySelector(".frame"), dotsLayer = svg.querySelector(".dots"), ring = svg.querySelector(".ring");
  const passing = svg.querySelector(".passing"), walls = svg.querySelector(".walls");
  if (!axes.length) {
    frame.innerHTML = `<text x="8" y="24">No candidate has been found for this line yet.</text>`;
    passing.style.display = "none"; ring.style.opacity = 0; dotsLayer.innerHTML = ""; walls.innerHTML = "";
    return;
  }
  passing.style.display = "";
  const two = axes.length > 1;
  // layout: left gutter (x never stated), plot, tick row, bottom gutter (y never stated)
  const gutterW = 30, tickW = two ? 34 : 0, tickH = 19, gutterH = two ? 26 : 0;
  const x0 = gutterW + 6 + tickW, x1 = W - 4, y0 = 2, y1 = H - tickH - (two ? gutterH + 3 : 0);
  const X = axis(line, axes[0], x0 + 14, x1 - 16);
  const Y = two ? axis(line, axes[1], y1 - 14, y0 + 14) : null;
  const midY = (y0 + y1) / 2, gutterX = gutterW / 2 + 1, gutterY = y1 + tickH + 2 + gutterH / 2;

  // frame: background, gutters, ticks, axis names
  let f = `<rect class="bg" x="${x0}" y="${y0}" width="${x1 - x0}" height="${y1 - y0}" rx="4"/>`;
  f += `<rect class="gutter" x="1" y="${y0 + 1}" width="${gutterW}" height="${y1 - y0 - 2}" rx="6"/>`;
  f += `<text transform="translate(${gutterX + 6} ${y1 - 6}) rotate(-90)">never states ${esc(X.missingLabel)}</text>`;
  for (const t of X.ticks) f += `<text class="tick" x="${X.px(t)}" y="${y1 + 16}" text-anchor="middle">${num(t, X.unit === "in" ? "" : X.unit)}</text>`;
  f += `<text x="${x1 - 6}" y="${y1 - 7}" text-anchor="end">${esc(X.sample.name)}, ${esc(X.unit)} →</text>`;
  if (two) {
    f += `<rect class="gutter" x="${x0}" y="${gutterY - gutterH / 2}" width="${x1 - x0}" height="${gutterH}" rx="6"/>`;
    f += `<text x="${x1 - 8}" y="${gutterY + 6}" text-anchor="end">never states ${esc(Y.missingLabel)}</text>`;
    for (const t of Y.ticks) f += `<text class="tick" x="${x0 - 5}" y="${Y.px(t) + 6}" text-anchor="end">${num(t, "")}</text>`;
    f += `<text x="${x0 + 6}" y="${y0 + 17}">↑ ${esc(Y.sample.name)}, ${esc(Y.unit)}</text>`;
  }
  frame.innerHTML = f;

  // the passing area and the walls
  const wx = X.px(X.bound.value), wy = two ? Y.px(Y.bound.value) : null;
  const px0 = X.op === ">=" ? wx : x0, px1 = X.op === ">=" ? x1 : wx;
  const py0 = !two ? y0 : Y.op === ">=" ? y0 : wy, py1 = !two ? y1 : Y.op === ">=" ? wy : y1;
  Object.assign(passing.style, { x: px0 + "px", y: py0 + "px", width: Math.max(0, px1 - px0) + "px", height: Math.max(0, py1 - py0) + "px" });
  if (!walls.children.length) {
    walls.innerHTML = '<g class="wall wx"><line></line><text></text></g>' + (two ? '<g class="wall wy"><line></line><text></text></g>' : "");
  }
  const wallX = walls.querySelector(".wx");
  wallX.setAttribute("class", "wall wx " + X.bound.owner);
  Object.entries({ x1: 0, x2: 0, y1: y0, y2: y1 }).forEach(([k, v]) => wallX.querySelector("line").setAttribute(k, v));
  const labelX = wallX.querySelector("text"), roomRight = x1 - wx > wallLabel(X).length * 8.2;
  const sideRight = X.op === ">=" ? roomRight : !(wx - x0 > wallLabel(X).length * 8.2);
  labelX.textContent = wallLabel(X);
  labelX.setAttribute("x", sideRight ? 8 : -8); labelX.setAttribute("y", two ? y0 + 38 : y0 + 18);
  labelX.setAttribute("text-anchor", sideRight ? "start" : "end");
  move(wallX, wx, 0);
  if (two) {
    const wallY = walls.querySelector(".wy");
    wallY.setAttribute("class", "wall wy " + Y.bound.owner);
    Object.entries({ x1: x0, x2: x1, y1: 0, y2: 0 }).forEach(([k, v]) => wallY.querySelector("line").setAttribute(k, v));
    const labelY = wallY.querySelector("text"), above = Y.op === ">=" ? wy - y0 > 44 : y1 - wy < 44;
    labelY.textContent = wallLabel(Y);
    labelY.setAttribute("x", x1 - 8); labelY.setAttribute("y", above ? -8 : 20); labelY.setAttribute("text-anchor", "end");
    move(wallY, 0, wy);
  }

  // the dots
  const seen = new Map();
  const dots = line.candidates.map((c, i) => {
    const cx = X.checks[i], cy = two ? Y.checks[i] : null;
    const xKnown = cx.lhs !== null && cx.lhs !== undefined, yKnown = !two || (cy.lhs !== null && cy.lhs !== undefined);
    let x = xKnown ? X.px(cx.lhs) : gutterX, y = !two ? midY : yKnown ? Y.px(cy.lhs) : gutterY;
    const spot = Math.round(x) + "," + Math.round(y), stack = seen.get(spot) || 0;   // same figures: fan the dots out
    seen.set(spot, stack + 1);
    x += stack * 7; y -= xKnown && yKnown ? stack * 7 : 0;
    const inside = c.status === "inside";
    const noDelivery = inside && c.arrival && c.arrival.status !== "stated";
    return { c, x, y, xKnown, yKnown,
      tailX: xKnown ? X.tails[i].map(X.px) : null, tailY: two && yKnown ? Y.tails[i].map(Y.px) : null,
      text: money(c.product.price_cents) + (c.picked ? " " + c.product.store : ""),
      rank: c.picked ? 3 : inside ? 2 : c.status === "outside" ? 1 : 0,
      cls: `dot ${c.status}${c.picked ? " picked" : ""}${noDelivery ? " nodelivery" : ""}${c.id === shownId ? " shown" : ""}` };
  });
  placeLabels(dots, W, H);
  const have = new Map([...dotsLayer.children].map((n) => [n.dataset.id, n]));
  for (const d of dots) {
    let node = have.get(d.c.id);
    if (!node) {
      node = el("g", { "data-id": d.c.id, tabindex: 0, role: "button" }, dotsLayer);
      el("rect", { class: "tail tx", y: -R, height: 2 * R, rx: R }, node);
      el("rect", { class: "tail ty", x: -R, width: 2 * R, rx: R }, node);
      el("circle", { class: "body", r: R }, node);
      el("line", { class: "strike", x1: -7, y1: -7, x2: 7, y2: 7 }, node);
      el("text", {}, node);
      el("title", {}, node);
      node.addEventListener("click", () => onInspect(node.dataset.id));
      node.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") onInspect(node.dataset.id); });
      move(node, d.x, d.y);
    }
    have.delete(d.c.id);
    node.setAttribute("class", d.cls);
    const [tx, ty] = node.querySelectorAll(".tail");
    const spanX = d.tailX ? [Math.min(...d.tailX) - d.x - R, Math.abs(d.tailX[1] - d.tailX[0]) + 2 * R] : [0, 0];
    const spanY = d.tailY ? [Math.min(...d.tailY) - d.y - R, Math.abs(d.tailY[1] - d.tailY[0]) + 2 * R] : [0, 0];
    tx.setAttribute("x", spanX[0]); tx.setAttribute("width", spanX[1] > 2 * R + 1 ? spanX[1] : 0);
    ty.setAttribute("y", spanY[0]); ty.setAttribute("height", spanY[1] > 2 * R + 1 ? spanY[1] : 0);
    node.querySelector(".strike").style.display = d.c.status === "struck" ? "" : "none";
    const text = node.querySelector("text");
    text.textContent = d.label ? d.text : "";
    if (d.label) { text.setAttribute("x", d.label.dx); text.setAttribute("y", d.label.dy); text.setAttribute("text-anchor", d.label.anchor); }
    const say = `${d.c.product.title}, ${money(d.c.product.price_cents)}, ${d.c.product.store}: ${d.c.reason || (d.c.picked ? "the pick" : "inside the limits")}`;
    node.querySelector("title").textContent = say;
    node.setAttribute("aria-label", say);
    move(node, d.x, d.y);
    if (d.c.picked) dotsLayer.appendChild(node);
  }
  for (const node of have.values()) node.remove();
  const picked = dots.find((d) => d.c.picked);
  ring.style.opacity = picked ? 1 : 0;
  if (picked) move(ring, picked.x, picked.y);
}
