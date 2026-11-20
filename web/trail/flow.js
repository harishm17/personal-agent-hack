// The run of one item as a picture, drawn from feed.flow (signoff/trail/flow.py); the page decides nothing.
// The store's page goes INTO the model frame. The issuer's limit and the home's measurement travel AROUND it and
// meet the quoted figure only in code. Each element belongs to the step that brings it (data-s); the replay shows
// the elements of the steps played so far, so the last frame, and the page with motion off, is everything in place.
const params = new URLSearchParams(location.search);
const MOTION = params.get("motion") === "1"
  || (params.get("motion") !== "0" && !matchMedia("(prefers-reduced-motion: reduce)").matches && !navigator.webdriver);
const ARRIVE = "cubic-bezier(.2, .7, .2, 1)", TRAVEL = "cubic-bezier(.4, 0, .2, 1)";
const SECONDS = [3, 3, 5, 4, 3, 3, 3];          // one run of one item: 24 s
const W = 1392;                                   // the stage is laid out at this width and scaled to its place

const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const dot = (owner) => `<i class="od ${owner === "issuer" ? "issuer" : owner === "shopper" ? "shopper" : owner === "store" ? "store" : ""}"></i>`;
const quoted = (e) => `${esc(e.text.slice(0, e.quote[0]))}<mark>${esc(e.text.slice(e.quote[0], e.quote[1]))}</mark>${esc(e.text.slice(e.quote[1]))}`;
const clip = (s, n) => (s.length > n ? s.slice(0, n).replace(/\s+\S*$/, "") + " …" : s);

let root = null, flow = null, drawn = "", pos = 6, playing = false, timer = null, started = 0, left = 0, ticker = null;

function html(f) {
  const { order, home, page } = f.said, m = f.model;
  const rail = f.rail.map((s, i) => `<button class="st" data-go="${i}"><span>${esc(s.label)}</span><i>${esc(s.sub)}</i></button>`).join("");
  const orderCard = order ? `<div class="fc" data-s="0" id="fl-order"><div class="cap">${dot("issuer")}${esc(order.who)} · the order</div>
      <p>${order.sentences.map((s) => (s.marked ? `<mark data-s="0" data-a="sweep" data-d="700">${esc(s.text)}</mark>` : esc(s.text))).join(" ")}</p></div>` : none("No order record");
  const homeCards = home.map((h, i) => `<div class="fc" data-s="0" data-d="300" id="fl-home-${i}"><div class="cap two"><span>${dot("shopper")}${esc(h.who)} · the home</span>${h.recalled ? `<span>recalled from memory</span>` : ""}</div>
      <p>${esc(h.label.charAt(0).toUpperCase() + h.label.slice(1))} <b>${esc(h.value)}</b></p></div>`).join("");
  const pageCard = page ? `<div class="fc" data-s="1" data-a="slide" id="fl-page"><div class="cap">${dot("store")}${esc(page.store)} · product page</div>
      <div class="pr">${page.image ? `<img class="thumb" src="${esc(page.image)}" alt="">` : ""}<div><b>${esc(page.title)}</b><span>${esc(page.price)}</span></div></div>
      <p class="pg">${page.excerpt.map((e) => quoted({ ...e, text: e.text })).map((t) => t).join(" … ")}</p></div>` : none("No page record");
  const frame = m ? `<div class="fl-frame" id="fl-frame">
      <div class="hd"><b>What the model sees</b><span class="cap">${esc([m.reader, m.source === "ledger" ? `${m.calls} calls` : "prompt builder"].filter(Boolean).join(" · "))}</span></div>
      <div class="bd">
        <div class="fc in" data-s="2" data-a="from" data-from="#fl-page" id="fl-copy"><div class="cap">${dot("store")}one page of store text</div><p class="pg">${m.page.map(quoted).join(" … ")}</p></div>
        ${m.meanings.length ? `<div class="fc in" data-s="2" data-d="700"><div class="cap">what each figure means</div><p class="pg">${m.meanings.map((x) => `${esc(x.name)}: ${esc(clip(x.text, 64))}`).join(" · ")}</p></div>` : ""}
        <div class="qr"><span class="cap">quoted</span>${m.quoted.map((q, i) => `<span class="tok q" data-s="2" data-a="pop" data-d="${1500 + i * 500}" id="fl-q-${i}">${esc(q)}</span>`).join("")}</div>
      </div></div>` : none("No model record");
  const pills = f.bypass.map((b, i) => `<span class="tok by" data-s="0" data-a="from" data-from="${b.owner === "issuer" ? "#fl-order" : "#fl-home-0"}" data-d="${1500 + i * 300}" id="fl-by-${i}" style="left:${150 + i * 150}px;top:${28 + i * 18}px">${dot(b.owner)}${esc(b.text)}</span>`).join("");
  const outside = m && m.outside ? m.outside.map((o) => `<span class="chip">${esc(o)}</span>`).join("") : `<span class="chip">no ledger rows</span>`;
  const checks = f.checks.map((c, i) => `<span class="tok" data-s="3" data-a="from" data-from="#fl-q-${i}" id="fl-l-${i}">${dot(c.left.owner)}${esc(c.left.text)}</span>
      <span class="op" data-s="3" data-d="600">${esc(c.op)}</span>
      <span class="tok" data-s="3" data-a="from" data-from="#fl-by-${i}" data-d="900" id="fl-r-${i}">${dot(c.right.owner)}${esc(c.right.text)}</span>
      <span class="mg" data-s="3" data-d="${2000 + i * 300}">${c.ok === true ? `<span class="tickmark">✓</span> ${esc(c.margin)}` : c.ok === false ? `<span class="no">✕ outside</span>` : ""}</span>`).join("");
  const sig = f.signature;
  return `<div class="fl-head"><span class="fl-title">${esc(f.title)}</span><span class="grow"></span><span class="cap" id="fl-clock"></span>
      <button class="fb" data-step="-1" aria-label="Step back">‹</button><button class="fb" data-play aria-label="Play or pause">▶ Play</button><button class="fb" data-step="1" aria-label="Step on">›</button></div>
    <div class="fl-scale"><div class="fl-stage" id="fl-stage">
      <div class="fl-rail" role="group" aria-label="The steps of the run">${rail}</div>
      <div class="fl-cols">
        <div class="fl-col"><div class="cap up">What each party said</div>${orderCard}${homeCards}${pageCard}</div>
        <div class="fl-col">${frame}
          <div class="fl-by"><span class="cap">never enters a model call</span>${pills}<div class="chips">${outside}</div></div></div>
        <div class="fl-col"><div class="cap up">Checked in code</div>
          ${f.checks.length ? `<div class="fc"><div class="cap">the store's figure &nbsp;against&nbsp; the limit</div><div class="cmp">${checks}</div></div>` : none("No check record")}
          ${f.refused ? `<div class="fc rowc quiet" data-s="4"><span class="pc">${esc(f.refused.price)}</span><span class="tt">${esc(f.refused.title)}</span><span class="no">refused · ${esc(f.refused.reason)}</span></div>` : ""}
          ${f.pick ? `<div class="fc rowc pick" data-s="4" data-d="900"><b class="pc">${esc(f.pick.price)}</b><b class="tt">${esc(f.pick.title)}</b><span class="muted">${esc(f.pick.rule)}</span></div>` : none("No pick")}
          <div class="fc rowc ${sig.signed ? "" : "quiet"}" data-s="5">${dot("issuer")}<span class="tt">${esc(sig.who)} signs from the phone</span><span class="${sig.signed ? "" : "faint"}">${esc(sig.text)}</span></div>
        </div>
      </div>
      <div class="cap up">To the store's own agent</div>
      <div class="fl-guard">${guardRow(f)}</div>
      <div class="cap up">Memory · each fact has an owner</div>
      <div class="fl-mem">${f.memory ? f.memory.map(slot).join("") : none("No memory record")}</div>
      <svg class="fl-lines" id="fl-lines" aria-hidden="true"></svg>
    </div></div>`;
}
/** The draft with the spans the guard removed shown in it, in the order they stand. */
function draftHtml(t) {
  let text = String(t.draft || ""), out = "";
  for (const r of t.removed) {
    const i = r.text ? text.indexOf(r.text) : -1;
    if (i < 0) continue;
    out += esc(text.slice(0, i)) + `<span class="rm">${esc(r.text)}</span>`;
    text = text.slice(i + r.text.length);
  }
  return out + esc(text);
}

/** To the store's own agent: the draft, the guard as a line the message crosses, the store's reply.
 *  With a guard record (TALK's), the removed spans stop at the line; without one, the question and reply as saved. */
function guardRow(f) {
  const t = f.talk, a = f.asked;
  if (t) {
    const chips = t.removed.map((r, i) => `<span class="chip x" data-s="4" data-a="from" data-from="#fl-draft" data-d="${1300 + i * 110}" title="${esc(r.mark)}">${esc(r.text)}</span>`).join("");
    return `<div class="fc" data-s="4" data-d="900" id="fl-draft"><div class="cap">the agent's draft · ${esc(t.at)}</div><p class="dr">${draftHtml(t)}</p></div>
      <div class="gate" data-s="4" data-d="1100"><b class="cap">Guard · ${t.removed.length ? "stopped here" : "nothing stopped"}</b><div class="stopped">${chips}</div>
        ${t.left.length ? `<span class="cap">left: ${esc(t.left.join(" · "))}</span>` : ""}</div>
      <div class="fc" data-s="4" data-d="2300"><div class="cap">${dot("store")}${esc(t.store)}'s agent replied</div><p class="dr">“<mark>${esc(clip(t.reply, 170))}</mark>”</p></div>`;
  }
  return `${a ? `<div class="fc" data-s="4" data-d="900"><div class="cap">our agent wrote</div><p class="dr">${esc(a.question)}</p></div>` : none("No question record")}
    <div class="gate" data-s="4" data-d="1100"><b class="cap">Guard</b><span class="chip">no guard record</span></div>
    ${a ? `<div class="fc" data-s="4" data-d="2300"><div class="cap">${dot("store")}${esc(a.store)}'s agent replied</div><p class="dr">“<mark>${esc(clip(a.reply, 170))}</mark>”</p></div>` : none("No reply record")}`;
}

/** One owner's slot on the memory shelf: what a new run would recall, or that it is empty. */
function slot(s, i) {
  const items = s.items.map((it) => `<p class="mi">${esc(it.text)}</p>`).join("");
  const more = s.count > s.items.length ? `${s.count - s.items.length} more · ` : "";
  return `<div class="fc ms ${s.count ? "" : "empty"}" data-s="6" data-a="drop" data-d="${i * 200}"><div class="cap">${dot(s.owner)}${esc(s.label)}</div>
    ${s.count ? `${items}<div class="cap">${esc(more)}${esc(s.items[0].age ? "from " + s.items[0].age + " ago" : "")}</div>` : `<p class="faint">nothing yet</p>`}</div>`;
}

const none = (words) => `<div class="fc quiet absent">${esc(words)}</div>`;

// ---------- lines, measured from where the things really are ----------
function box(el) {
  const s = document.getElementById("fl-stage").getBoundingClientRect(), r = el.getBoundingClientRect(), k = s.width / W;
  return { x: (r.left - s.left) / k, y: (r.top - s.top) / k, w: r.width / k, h: r.height / k, r: (r.right - s.left) / k, b: (r.bottom - s.top) / k, cy: (r.top + r.height / 2 - s.top) / k, cx: (r.left + r.width / 2 - s.left) / k };
}
/** A path through the points with corners rounded to r. */
function route(pts, r = 10) {
  let d = `M${pts[0][0]} ${pts[0][1]}`;
  for (let i = 1; i < pts.length - 1; i++) {
    const [px, py] = pts[i - 1], [x, y] = pts[i], [nx, ny] = pts[i + 1];
    const a = Math.min(r, Math.hypot(x - px, y - py) / 2), b = Math.min(r, Math.hypot(nx - x, ny - y) / 2);
    const ax = x - Math.sign(x - px) * (px === x ? 0 : a), ay = y - Math.sign(y - py) * (py === y ? 0 : a);
    const bx = x + Math.sign(nx - x) * (nx === x ? 0 : b), by = y + Math.sign(ny - y) * (ny === y ? 0 : b);
    d += ` L${ax} ${ay} Q${x} ${y} ${bx} ${by}`;
  }
  const last = pts[pts.length - 1];
  return d + ` L${last[0]} ${last[1]}`;
}
function drawLines() {
  const q = (id) => document.getElementById(id), svg = q("fl-lines"), stage = q("fl-stage");
  if (!svg || !stage) return;
  svg.setAttribute("viewBox", `0 0 ${W} ${stage.offsetHeight}`);
  svg.style.height = stage.offsetHeight + "px";
  const frame = q("fl-frame"), paths = [];
  if (frame) {
    const fr = box(frame);
    if (q("fl-page") && q("fl-copy")) {            // the store's page goes into the frame
      const a = box(q("fl-page")), b = box(q("fl-copy")), mid = (a.r + fr.x) / 2;
      paths.push(`<path class="hot" data-s="2" data-a="draw" data-t="600" d="M${a.r} ${a.cy} C${mid} ${a.cy} ${mid} ${b.cy} ${fr.x} ${b.cy}"/>`);
    }
    flow.checks.forEach((c, i) => {
      const l = q(`fl-l-${i}`), r = q(`fl-r-${i}`), quote = q(`fl-q-${i}`), pill = q(`fl-by-${i}`);
      if (l && quote) {                            // the quoted figure leaves the frame for the check
        const a = box(quote), b = box(l), mid = (fr.r + b.x) / 2;
        paths.push(`<path class="hot" data-s="3" data-a="draw" data-t="700" d="M${fr.r} ${a.cy} C${mid} ${a.cy} ${mid} ${b.cy} ${b.x} ${b.cy}"/>`);
      }
      if (r && pill) {                             // the limit or the measurement goes round the frame, never through it
        const src = q(flow.bypass[i].owner === "issuer" ? "fl-order" : "fl-home-0");
        if (!src) return;
        const a = box(src), p = box(pill), b = box(r), gl = a.r + 10 + i * 8, gr = fr.r + 12 + i * 8, under = b.b + 5;
        paths.push(`<path data-s="3" data-a="draw" data-t="1300" d="${route([[a.r, a.cy], [gl, a.cy], [gl, p.cy], [gr, p.cy], [gr, under], [b.cx, under], [b.cx, b.b]])}"/>`);
      }
    });
  }
  svg.innerHTML = paths.join("");
}

// ---------- the replay ----------
function animate(el) {
  const delay = +el.dataset.d || 0, kind = el.dataset.a || "rise", opts = (duration, easing) => ({ duration, delay, easing, fill: "backwards" });
  if (kind === "draw") {
    const len = el.getTotalLength();
    el.style.strokeDasharray = len;
    el.animate([{ strokeDashoffset: len }, { strokeDashoffset: 0 }], opts(+el.dataset.t || 1300, TRAVEL));
  } else if (kind === "sweep") {
    el.animate([{ backgroundSize: "0% 100%" }, { backgroundSize: "100% 100%" }], opts(900, TRAVEL));
  } else if (kind === "from" && document.querySelector(el.dataset.from)) {
    const a = box(document.querySelector(el.dataset.from)), b = box(el);
    el.animate([{ transform: `translate(${a.cx - b.cx}px, ${a.cy - b.cy}px) scale(.9)`, opacity: 0 }, { opacity: 1, offset: 0.25 }, { transform: "none", opacity: 1 }], opts(700, TRAVEL));
  } else if (kind === "slide") {
    el.animate([{ transform: "translateX(-24px)", opacity: 0 }, { transform: "none", opacity: 1 }], opts(700, ARRIVE));
  } else if (kind === "drop") {
    el.animate([{ transform: "translateY(-20px)", opacity: 0 }, { transform: "none", opacity: 1 }], opts(700, ARRIVE));
  } else if (kind === "pop") {
    el.animate([{ transform: "scale(.8)", opacity: 0 }, { transform: "none", opacity: 1 }], opts(600, ARRIVE));
  } else {
    el.animate([{ transform: "translateY(8px)", opacity: 0 }, { transform: "none", opacity: 1 }], opts(600, ARRIVE));
  }
}

function clock() {
  const el = document.getElementById("fl-clock");
  if (!el) return;
  const before = SECONDS.slice(0, Math.max(0, pos)).reduce((a, b) => a + b, 0), total = SECONDS.reduce((a, b) => a + b, 0);
  const into = pos < 0 ? 0 : playing ? Math.min(SECONDS[pos], (performance.now() - started) / 1000) : pos >= 6 && !playing ? SECONDS[6] : 0;
  const t = Math.floor(before + into), mmss = (n) => `0:${String(n).padStart(2, "0")}`;
  el.textContent = `step ${Math.max(1, pos + 1)} of 7 · ${mmss(t)} / ${mmss(total)}`;
}

function show(move) {
  for (const el of root.querySelectorAll("[data-s]")) {
    el.classList.toggle("later", +el.dataset.s > pos);
    if (move && MOTION && +el.dataset.s === pos) animate(el);
  }
  root.querySelectorAll(".st").forEach((b, i) => {
    b.classList.toggle("done", i < pos || (i === pos && !playing && pos === 6));
    b.classList.toggle("now", i === pos && (playing || pos < 6));
    b.classList.toggle("unmet", flow.rail[i] && !flow.rail[i].done);
  });
  const play = root.querySelector("[data-play]");
  if (play) play.textContent = playing ? "❚❚ Pause" : "▶ Play";
  clock();
}

function stop() {
  clearTimeout(timer);
  clearInterval(ticker);
  playing = false;
}
function advance() {
  if (pos >= 6) { stop(); show(false); return; }
  pos += 1;
  started = performance.now();
  show(true);
  timer = setTimeout(advance, SECONDS[pos] * 1000);
}
function play() {
  if (!MOTION) { pos = 6; show(false); return; }
  if (pos >= 6) pos = -1;
  playing = true;
  ticker = setInterval(clock, 250);
  advance();
}
function pause() {
  left = Math.max(0, SECONDS[pos] * 1000 - (performance.now() - started));
  stop();
  root.getAnimations({ subtree: true }).forEach((a) => a.pause());
  show(false);
}
function resume() {
  playing = true;
  root.getAnimations({ subtree: true }).forEach((a) => a.play());
  started = performance.now() - (SECONDS[pos] * 1000 - left);
  ticker = setInterval(clock, 250);
  timer = setTimeout(advance, left);
  show(false);
}
function go(to) {
  stop();
  root.getAnimations({ subtree: true }).forEach((a) => a.cancel());
  pos = Math.max(0, Math.min(6, to));
  started = performance.now();
  show(true);
}

function fit() {
  const scale = root.querySelector(".fl-scale"), stage = document.getElementById("fl-stage");
  if (!scale || !stage) return;
  const k = Math.min(1, scale.clientWidth / W);
  stage.style.transform = `scale(${k})`;
  scale.style.height = stage.offsetHeight * k + "px";
}

/** Draws the view into `el` from `feed.flow`. Redraws only when the records behind it changed. */
export function update(el, f) {
  root = el;
  const now = JSON.stringify(f || null);
  if (now === drawn) return;
  drawn = now;
  flow = f;
  if (!f) { el.hidden = true; return; }
  el.hidden = false;
  stop();
  el.innerHTML = html(f);
  fit();
  drawLines();
  fit();
  show(false);
  for (const img of el.querySelectorAll("img")) img.addEventListener("load", () => { fit(); drawLines(); show(false); }, { once: true });
}

document.addEventListener("click", (ev) => {
  if (!root || !flow) return;
  const t = ev.target.closest("#flow [data-play], #flow [data-step], #flow [data-go]");
  if (!t) return;
  if (t.dataset.go) go(+t.dataset.go);
  else if (t.dataset.step) go(pos + +t.dataset.step);
  else if (playing) pause();
  else if (left > 0 && pos < 6 && pos >= 0 && root.getAnimations({ subtree: true }).some((a) => a.playState === "paused")) resume();
  else play();
});
document.addEventListener("keydown", (ev) => {
  if (!root || !flow || ev.target.closest("input, textarea, select") || ev.metaKey || ev.ctrlKey || ev.altKey) return;
  if (ev.key === " " && !ev.target.closest("button, a")) { ev.preventDefault(); root.querySelector("[data-play]").click(); }
  else if (ev.key === "ArrowRight") go(pos + 1);
  else if (ev.key === "ArrowLeft") go(pos - 1);
});
addEventListener("resize", () => { if (root && flow) { fit(); drawLines(); show(false); } });
