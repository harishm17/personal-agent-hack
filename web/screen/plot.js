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
    name: sample.terms.length === 1 ? sample.terms[0].label || sample.name : sample.name,
    missingLabel: missing ? (missing.missing_figure || "figure").replace(/_/g, " ") : sample.name };
}

function wallLabel(a) {
  if (a.bound.owner === "shopper") return `${a.bound.owner_name}'s ${a.bound.label}: ${num(a.bound.value, a.unit)} ${a.unit}`;
  return `${a.bound.owner_name}: ${opWords(a.op)} ${num(a.bound.value, a.unit)} ${a.unit}`;
}

/** Greedy label placement: the pick first; a label that fits nowhere is left out. */
function placeLabels(dots, W, H, reserved, soft) {
  const taken = [...reserved, ...dots.map((d) => [d.x - R - 2, d.y - R - 2, d.x + R + 2, d.y + R + 2])];
  const over = (b, list) => list.some((t) => b[0] < t[2] && b[2] > t[0] && b[1] < t[3] && b[3] > t[1]);
  const out = (b) => b[0] < 0 || b[1] < 0 || b[2] > W || b[3] > H;
  const order = [...dots].sort((a, b) => b.rank - a.rank);
  for (const d of order) {
    for (const text of d.texts) {
      const w = text.length * (d.rank >= 3 ? 9.6 : 9) + 2;
      const spots = [
        { dx: R + 6, dy: 6, anchor: "start", box: [d.x + R + 4, d.y - 9, d.x + R + 6 + w, d.y + 9] },
        { dx: 0, dy: -R - 6, anchor: "middle", box: [d.x - w / 2, d.y - R - 22, d.x + w / 2, d.y - R - 3] },
        { dx: 0, dy: R + 18, anchor: "middle", box: [d.x - w / 2, d.y + R + 3, d.x + w / 2, d.y + R + 21] },
        { dx: -R - 6, dy: 6, anchor: "end", box: [d.x - R - 6 - w, d.y - 9, d.x - R - 4, d.y + 9] },
        { dx: R, dy: -R - 2, anchor: "start", box: [d.x + R, d.y - R - 18, d.x + R + w, d.y - R] },
        { dx: R, dy: R + 14, anchor: "start", box: [d.x + R, d.y + R - 2, d.x + R + w, d.y + R + 16] },
        { dx: -R, dy: -R - 2, anchor: "end", box: [d.x - R - w, d.y - R - 18, d.x - R, d.y - R] },
        { dx: -R, dy: R + 14, anchor: "end", box: [d.x - R - w, d.y + R - 2, d.x - R, d.y + R + 16] },
      ];
      // walls and their labels are soft: the pick's label may cross them (it has a white halo), others may not
      d.label = spots.find((s) => !out(s.box) && !over(s.box, taken) && !over(s.box, soft))
        || (d.rank >= 3 ? spots.find((s) => !out(s.box) && !over(s.box, taken)) : null);
      if (d.label) { d.text = text; taken.push(d.label.box); break; }
    }
    if (!d.label && d.rank >= 3) {     // the pick is always labelled
      const text = d.texts[d.texts.length - 1], right = d.x + R + 8 + text.length * 9.6 < W;
      d.text = text;
      d.label = right ? { dx: R + 6, dy: 6, anchor: "start", box: [d.x + R + 4, d.y - 9, d.x + R + 8 + text.length * 9.6, d.y + 9] }
        : { dx: -R - 6, dy: 6, anchor: "end", box: [d.x - R - 8 - text.length * 9.6, d.y - 9, d.x - R - 4, d.y + 9] };
      taken.push(d.label.box);
    }
  }
}

export function drawPlot(svg, line, shownId, onInspect) {
  const W = svg.clientWidth, H = svg.clientHeight;
  if (!W || !H) return;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const axes = plotAxes(line);
  if (svg.dataset.line !== line.line_id || svg.dataset.size !== W + "x" + H || svg.dataset.axes !== axes.join()) {
    svg.dataset.line = line.line_id; svg.dataset.size = W + "x" + H; svg.dataset.axes = axes.join();
    svg.innerHTML = '<g class="frame"></g><rect class="passing"></rect><g class="walls"></g><g class="dots"></g><circle class="ring" r="15"></circle><g class="walltext"></g>';
  }
  const frame = svg.querySelector(".frame"), dotsLayer = svg.querySelector(".dots"), ring = svg.querySelector(".ring");
  const passing = svg.querySelector(".passing"), walls = svg.querySelector(".walls"), wallText = svg.querySelector(".walltext");
  if (!axes.length) {
    frame.innerHTML = `<text x="8" y="24">No candidate has been found for this line yet.</text>`;
    passing.style.display = "none"; ring.style.opacity = 0; dotsLayer.innerHTML = ""; walls.innerHTML = ""; wallText.innerHTML = "";
    return;
  }
  passing.style.display = "";
  const two = axes.length > 1;
  // layout: left gutter (x never stated), plot, tick row, bottom gutter (y never stated)
  const gutterW = 62, tickH = 20, gutterH = two ? 26 : 0;
  const y0 = 2, y1 = H - tickH - (two ? gutterH + 3 : 0), x1 = W - 2;
  const Y = two ? axis(line, axes[1], y1 - 14, y0 + (two ? 30 : 14)) : null;
  const tickW = two ? Math.max(...Y.ticks.map((t) => num(t, "").length)) * 9.5 + 8 : 0;
  const x0 = gutterW + 4 + tickW;
  const X = axis(line, axes[0], x0 + 14, x1 - 16);
  const reserved = [[gutterW + 2, y0, x0, H]];   // boxes no dot label may cover
  const midY = (y0 + y1) / 2, gutterX = gutterW / 2 + 1, gutterY = y1 + tickH + 2 + gutterH / 2;

  // the walls: where they stand and what their labels say
  const wx = X.px(X.bound.value), wy = two ? Y.px(Y.bound.value) : null;
  const textX = wallLabel(X), widthX = textX.length * 7.6 + 8;
  const rightX = wx + widthX < x1;                       // the x wall's label sits in the tick row, under the wall
  const labelBoxX = rightX ? [wx - 4, wx + widthX] : [wx - widthX, wx + 4];

  // frame: background, gutters, ticks, axis names
  let f = `<rect class="bg" x="${x0}" y="${y0}" width="${x1 - x0}" height="${y1 - y0}" rx="4"/>`;
  f += `<rect class="gutter" x="1" y="${y0 + 1}" width="${gutterW}" height="${(two ? H : y1) - y0 - 2}" rx="6"/>`;
  f += `<text x="${gutterX}" y="${y0 + 19}" text-anchor="middle">not stated</text>`;
  reserved.push([0, y0, gutterW, y0 + 24]);
  for (const t of X.ticks) {
    const tx = X.px(t);
    if (tx + 20 > labelBoxX[0] && tx - 20 < labelBoxX[1]) continue;
    f += `<text class="tick" x="${tx}" y="${y1 + 16}" text-anchor="middle">${num(t, X.unit === "in" ? "" : X.unit)}</text>`;
  }
  const nameX = `${X.name}, ${X.unit} \u2192`;
  f += `<text x="${x1 - 6}" y="${y1 - 7}" text-anchor="end">${esc(nameX)}</text>`;
  reserved.push([x1 - 8 - nameX.length * 7, y1 - 24, x1, y1]);
  if (two) {
    f += `<rect class="gutter" x="${x0}" y="${gutterY - gutterH / 2}" width="${x1 - x0}" height="${gutterH}" rx="6"/>`;
    const inGutter = line.candidates.map((c, i) => [X.checks[i].lhs, Y.checks[i].lhs]).filter(([a, b]) => a != null && b == null).map(([a]) => X.px(a));
    const busyRight = (w) => inGutter.some((gx) => gx > x1 - w - 90), busyLeft = (w) => inGutter.some((gx) => gx < x0 + w + 90);
    let gutterText = `${Y.missingLabel}: not stated`, gutterTextW = gutterText.length * 7 + 12;
    if (busyRight(gutterTextW) && busyLeft(gutterTextW)) { gutterText = "not stated"; gutterTextW = 82; }
    if (busyRight(gutterTextW - 60) && busyLeft(gutterTextW - 60)) { gutterText = ""; gutterTextW = 0; }
    const atLeft = busyRight(gutterTextW) && !busyLeft(gutterTextW);
    f += `<text x="${atLeft ? x0 + 8 : x1 - 8}" y="${gutterY + 6}" text-anchor="${atLeft ? "start" : "end"}">${esc(gutterText)}</text>`;
    reserved.push(atLeft ? [x0, gutterY - gutterH / 2, x0 + gutterTextW, H] : [x1 - gutterTextW, gutterY - gutterH / 2, x1, H]);
    reserved.push([x0, y1, x1, y1 + tickH]);
    for (const t of Y.ticks) f += `<text class="tick" x="${x0 - 5}" y="${Y.px(t) + 6}" text-anchor="end">${num(t, "")}</text>`;
    const nameY = `\u2191 ${Y.name}, ${Y.unit}`;
    f += `<text x="${x0 + 6}" y="${y0 + 18}">${esc(nameY)}</text>`;
    reserved.push([x0, y0, x0 + 10 + nameY.length * 7, y0 + 24]);
  }
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
  let wallYBox = null;
  if (two) {
    const wallY = walls.querySelector(".wy"), textGY = wallText.querySelector(".wy");
    wallY.setAttribute("class", "wall wy " + Y.bound.owner);
    textGY.setAttribute("class", "wall wy " + Y.bound.owner);
    Object.entries({ x1: x0, x2: x1, y1: 0, y2: 0 }).forEach(([k, v]) => wallY.querySelector("line").setAttribute(k, v));
    const labelY = textGY.querySelector("text"), textY = wallLabel(Y), widthY = textY.length * 7.6 + 8;
    labelY.textContent = textY;
    // the y wall's label goes where no dot sits: passing side first, right end first
    const up = Y.op === ">=";
    const spots = [[true, up], [false, up], [true, !up], [false, !up]].map(([right, above]) => ({ right, above,
      box: [right ? x1 - 8 - widthY : x0 + 6, above ? wy - 24 : wy + 4, right ? x1 - 4 : x0 + 10 + widthY, above ? wy - 3 : wy + 24] }));
    const dotAt = line.candidates.map((c, i) => [X.checks[i].lhs, Y.checks[i].lhs]).filter(([a, b]) => a != null && b != null).map(([a, b]) => [X.px(a), Y.px(b)]);
    const free = (b) => b[1] > y0 && b[3] < y1 && !dotAt.some(([dx, dy]) => dx + R > b[0] && dx - R < b[2] && dy + R > b[1] && dy - R < b[3]);
    const spot = spots.find((sp) => free(sp.box)) || spots[0];
    labelY.setAttribute("x", spot.right ? x1 - 8 : x0 + 8); labelY.setAttribute("y", spot.above ? -8 : 20);
    labelY.setAttribute("text-anchor", spot.right ? "end" : "start");
    move(wallY, 0, wy); move(textGY, 0, wy);
    wallYBox = spot.box;
    reserved.push(wallYBox);
    soft.push([x0, wy - 3, x1, wy + 3]);
  }

  // the dots
  const seen = new Map();
  const dots = line.candidates.map((c, i) => {
    const cx = X.checks[i], cy = two ? Y.checks[i] : null;
    const xKnown = cx.lhs !== null && cx.lhs !== undefined, yKnown = !two || (cy.lhs !== null && cy.lhs !== undefined);
    let x = xKnown ? X.px(cx.lhs) : gutterX, y = !two ? midY : yKnown ? Y.px(cy.lhs) : gutterY;
    const spot = Math.round(x) + "," + Math.round(y);
    seen.set(spot, (seen.get(spot) || 0) + 1);
    const inside = c.status === "inside";
    const noDelivery = inside && line.status !== "pick_up" && c.arrival && c.arrival.status !== "stated";
    return { c, x, y, xKnown, yKnown, spot,
      tailX: xKnown ? X.tails[i].map(X.px) : null, tailY: two && yKnown ? Y.tails[i].map(Y.px) : null,
      texts: c.picked ? [money(c.product.price_cents) + " " + c.product.store, money(c.product.price_cents)] : [money(c.product.price_cents)],
      rank: c.picked ? 3 : inside ? 2 : c.status === "outside" ? 1 : 0,
      cls: `dot ${c.status}${c.picked ? " picked" : ""}${noDelivery ? " nodelivery" : ""}${c.id === shownId ? " shown" : ""}` };
  });
  // products with the same figures share a spot: the best one is drawn, with a count
  const lead = new Map();
  for (const d of dots) if (!lead.has(d.spot) || d.rank > lead.get(d.spot).rank) lead.set(d.spot, d);
  for (const d of dots) {
    d.hidden = lead.get(d.spot) !== d;
    const n = seen.get(d.spot);
    if (!d.hidden && n > 1) d.texts = d.xKnown && d.yKnown ? d.texts.map((t) => `${t} +${n - 1}`) : [`\u00d7${n}`];
  }
  placeLabels(dots.filter((d) => !d.hidden), W, H, reserved, soft);
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
    node.style.display = d.hidden ? "none" : "";
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
