// The trail: the run's seven steps, opened up. Everything is drawn from GET /api/trail; the page decides nothing.
// A step is one row when closed; opened, it lists its events, one line each. Click an event: the side sheet.
// ?motion=0 (or reduced motion) draws the final state at once; ?live=0 opens no event stream (for screenshots).
import * as flow from "/trail/flow.js";

const params = new URLSearchParams(location.search);
const MOTION = params.get("motion") === "1"
  || (params.get("motion") !== "0" && !matchMedia("(prefers-reduced-motion: reduce)").matches && !navigator.webdriver);
const LIVE = params.get("live") !== "0";
const EASE = "cubic-bezier(.3, .1, .2, 1)";

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const cap = (s) => String(s || "").charAt(0).toUpperCase() + String(s || "").slice(1);

// One small mark per kind: lines of a source, a span in brackets, an equals sign, a signature, a move.
const ICON = {
  evidence: '<path d="M3 4.5h10M3 8h10M3 11.5h6"/>',
  reading: '<path d="M6 3H3.5v10H6M10 3h2.5v10H10"/>',
  check: '<path d="M4 6h8M4 10h8"/>',
  approval: '<path d="M2 10.5c1.6-6 3-6 4-2s2 3 3 0 2-2 3.2 0M2.5 13.5h11"/>',
  action: '<path class="f" d="M5.5 3.8v8.4L12 8z"/>',
  stop: '<path d="M4.5 4.5l7 7M11.5 4.5l-7 7"/>',
};
const icon = (k) => `<svg class="ki" viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">${ICON[k] || ""}</svg>`;
const TICK = '<svg viewBox="0 0 12 12" width="10" height="10" aria-hidden="true"><path d="M2.5 6.2 5 8.7 9.5 3.6" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const CROSS = '<svg viewBox="0 0 12 12" width="10" height="10" aria-hidden="true"><path d="M3 3l6 6M9 3l-6 6" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>';
const CHEV = '<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><path d="M6 3.5 10.5 8 6 12.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';

let feed = null, stamp = "", seen = null, sel = null, missing = false;
const open = new Set(), filter = new Set();

const key = (e) => [e.step, e.kind, e.mark, e.at, e.ref, e.detail].join("|");
const clock = (at, n = 8) => (at ? String(at).slice(11, 11 + n) : "");
function dur(ms) {
  if (ms == null) return "";
  if (ms < 1000) return ms + " ms";
  const s = Math.round(ms / 1000);
  return s < 60 ? s + " s" : Math.floor(s / 60) + " min" + (s % 60 ? " " + (s % 60) + " s" : "");
}
const short = (h) => String(h || "").slice(0, 10);
/** A detail for the surface: its facts (the parts between " · "), each cut at its colon and at five words.
 *  The whole text is in the side sheet. */
const brief = (detail) => String(detail || "").split(" · ").map((part) => {
  const words = part.split(": ")[0].replace(/_/g, " ").split(/\s+/);
  return words.length > 5 ? words.slice(0, 5).join(" ") + "…" : words.join(" ");
}).join(" · ");
const records = (e) => e.items.length + e.more;

// ---------- top bar and band ----------
function renderTop() {
  const s = feed.sheet || {};
  const mode = feed.mode === "fixture" ? "fixture data" : feed.mode === "replay" ? "replay of cached store data" : "";
  const meta = [s.items ? `${s.items} items` : "", s.invented ? "invented" : "", mode].filter(Boolean).join(" · ");
  $("#top").innerHTML = `<span class="brand">Sign-Off</span>
    <nav class="tabs" aria-label="Views"><a href="/">Decision</a><a href="/trail/" aria-current="page">Trail</a></nav>
    <span class="sheet">${esc(s.title || "")}</span><span class="meta">${esc(meta)}</span>
    <span class="grow"></span>
    <span class="pill ${feed.signed ? "signed" : ""}">${feed.signed ? "Signed " + clock(feed.signed_at, 5) : "Not signed"}</span>
    ${typeof s.total_cents === "number" ? `<span class="total">$${(s.total_cents / 100).toFixed(2)}</span>` : ""}`;
}

/** A number with its tick. `ok` true: a black tick; false: a red cross; null: nothing to vouch for yet. */
function stat(ok, n, words) {
  const mark = ok === true ? `<span class="tk">✓</span>` : ok === false ? `<span class="tk bad">${CROSS}</span>` : `<span class="tk todo"></span>`;
  return `<span class="stat">${mark}<b>${esc(n)}</b>${esc(words)}</span>`;
}

function renderBand() {
  const m = feed.summary, src = feed.sources || [], gone = src.filter((s) => !s.ok);
  const have = (id) => src.some((s) => s.id === id && s.ok);
  const stats = [
    stat(m.events ? true : null, m.events, "events"),
    stat(have("egress") ? true : null, m.messages_out ?? "–", "messages out"),
    stat(m.limits_to_stores == null ? null : m.limits_to_stores === 0, m.limits_to_stores ?? "–", "limits sent to stores"),
    stat(m.receipts ? m.receipts_verified === m.receipts : null, `${m.receipts_verified} of ${m.receipts}`, "receipts verified"),
  ].join("");
  const all = filter.size === 0;
  const chips = feed.kinds.map((k) => `<button class="chip" data-kind="${k}" aria-pressed="${all || filter.has(k)}">${icon(k)}${cap(k)}<i>${m.kinds[k] || 0}</i></button>`).join("");
  const lost = gone.map((s) => `<span class="pill">${esc(s.id)} missing</span>`).join("") + (missing ? `<span class="pill">feed missing</span>` : "");
  $("#band").innerHTML = `${stats}${lost}<span class="grow"></span><div class="chips" role="group" aria-label="Kinds of event">${chips}</div>`;
}

// ---------- the steps ----------
const shown = (e) => filter.size === 0 || filter.has(e.kind);

function eventRow(e, fresh) {
  const k = key(e);
  const cls = ["ev", e.stopped ? "stop" : "", e.own_step === false ? "side" : "", sel === k ? "sel" : "", fresh.has(k) ? "new" : ""].filter(Boolean).join(" ");
  const when = [clock(e.at), e.duration_ms != null ? `<i>${dur(e.duration_ms)}</i>` : ""].filter(Boolean).join(" · ");
  const tick = e.receipt != null ? `<span class="rt ${e.verified === false ? "bad" : ""}" data-tip="receipt ${e.receipt}" data-code="${esc(short(e.hash))}">${e.verified === false ? CROSS : TICK}</span>` : "";
  return `<button class="${cls}" data-k="${esc(k)}" title="${esc(cap(e.kind))}">${icon(e.stopped ? "stop" : e.kind)}
    <span class="lb">${esc(e.label)}</span><span class="dt">${esc(brief(e.detail))}</span><span class="at">${when}</span><span class="er">${tick}</span></button>`;
}

function stepRow(s, fresh) {
  const mine = feed.events.filter((e) => e.step === s.id), rows = mine.filter(shown), isOpen = open.has(s.id);
  const tally = feed.kinds.filter((k) => s.kinds[k]).map((k) => `<span class="kt" title="${cap(k)}">${icon(k)}${s.kinds[k]}</span>`).join("");
  // a clock time only for a step of this run; cached evidence was read earlier and its time says nothing of the order
  const when = [s.in_run ? clock(s.first_at, 5) : "", s.duration_ms != null ? `<i>${dur(s.duration_ms)}</i>` : ""].filter(Boolean).join(" · ");
  const receipts = (s.refused ? `<em>${s.refused} refused</em>` : "") + (s.receipts ? `${s.receipts}<span class="rt">${TICK}</span>` : "");
  return `<div class="step ${s.done ? "done" : "todo"}${isOpen ? " open" : ""}" id="${s.id}">
    <button class="sr" data-step="${s.id}" aria-expanded="${isOpen}" ${mine.length ? "" : "disabled"}>
      <span class="tk ${s.done ? "" : "todo"}">${s.done ? "✓" : s.n}</span>
      <span class="nm"><b>${esc(s.label)}</b><small>${esc(s.sub)}</small></span>
      <span class="tally">${tally}</span><span class="when">${when}</span>
      <span class="rc" ${s.receipts ? `title="${s.receipts} receipts"` : ""}>${receipts}</span><span class="chev">${mine.length ? CHEV : ""}</span>
    </button>
    ${isOpen ? `<div class="evs">${s.context ? contextBlock(s.context, "model calls") : ""}${rows.map((e) => eventRow(e, fresh)).join("") || `<div class="none">None of this kind</div>`}</div>` : ""}
  </div>`;
}

// ---------- context: what each model call was given, and what it was not ----------
const count = (n, calls) => (n === calls ? "" : `<i>${n}</i>`);   // a number only when it is not every call
const size = (b) => (b >= 10000 ? (b / 1000).toFixed(0) + " kB" : b.toLocaleString("en-US") + " bytes");

/** Two short rows of marks from the ledger's own record of a set of messages. With the sender's own `parts` and
 *  `withheld` lists on the rows, those are shown; otherwise the fact classes it declared. A sealed value that the
 *  ledger's search met in the text sent is its own row, in red: it is a finding, whatever the reason. */
function contextBlock(c, noun, full = false) {
  const given = c.parts.length ? c.parts.map((p) => `<span class="cm">${esc(p.name)}${p.chars != null ? `<i>${p.chars.toLocaleString("en-US")}</i>` : ""}</span>`)
    : c.given.map((g) => `<span class="cm">${esc(g.label)}${count(g.calls, c.calls)}</span>`);
  const not = c.withheld.length ? c.withheld.map((w) => `<span class="cm no">${esc(w.name)}</span>`) : c.not_given.map((g) => `<span class="cm no">${esc(g.label)}</span>`);
  const hits = c.found.map((f) => `<span class="cm hit">${esc(f.label)}<i>${f.calls}</i></span>`);
  const b = c.bytes;
  const row = (k, v) => (v ? `<span class="k">${k}</span><div class="v">${v}</div>` : "");
  return `<div class="ctx">${row(`${c.calls} ${c.calls === 1 ? noun.replace(/s$/, "") : noun}`, b ? `<span class="sz">${size(b.median)} each${b.min !== b.max ? `, ${size(b.min)} to ${size(b.max)}` : ""}</span>` : "")}
    ${row("given", given.join("") || `<span class="cm no">nothing declared</span>`)}${row("also in text", hits.join(""))}${row("not given", not.join(""))}
    ${full && c.found.length ? `<p class="why">The ledger's search met ${esc(c.found.map((f) => f.matches.join(", ")).join("; "))} in the text that was sent. A page that states the same number as a limit shows here; the ledger cannot tell the two apart.</p>` : ""}</div>`;
}

/** One line over the steps: how many model calls, how many carried no limit, measurement or person, and the rest. */
function contextLine() {
  const c = feed.summary.model_calls;
  if (!c) return "";
  const declared = (id) => (c.given.find((g) => g.id === id) || {}).calls || 0, found = (id) => (c.found.find((f) => f.id === id) || {}).calls || 0;
  const parts = [`<b>${c.calls}</b> model call${c.calls === 1 ? "" : "s"}`];
  if (c.calls) {
    parts.push(`<b>${declared("store_text")}</b> given page text`);
    parts.push(declared("limit") || found("limit") ? [declared("limit") ? `<b>${declared("limit")}</b> given limits` : "", found("limit") ? `<b class="hit">${found("limit")}</b> with a limit's number in the text` : ""].filter(Boolean).join(" · ") : "none saw a limit");
    parts.push(declared("person") || found("person") ? `<b>${declared("person") + found("person")}</b> saw a person's name` : "none saw a person");
  } else parts.push("none in the ledger");
  return `<div class="ctxline">${parts.join('<span class="sep">·</span>')}</div>`;
}

function renderSteps(fresh = new Set()) {
  $("#steps").innerHTML = contextLine() + feed.steps.map((s) => stepRow(s, fresh)).join("");
  if (!MOTION) return;
  for (const row of document.querySelectorAll(".ev.new")) {       // a new event slides in under its step
    row.animate([{ height: "0px", opacity: 0, transform: "translateY(-4px)" }, { height: row.offsetHeight + "px", opacity: 1, transform: "none" }],
      { duration: 250, easing: EASE });
  }
}

// ---------- side sheet ----------
function marked(text, quote) {
  const t = String(text ?? ""), q = String(quote ?? ""), i = q ? t.indexOf(q) : -1;
  return i < 0 ? esc(t) : `${esc(t.slice(0, i))}<mark>${esc(q)}</mark>${esc(t.slice(i + q.length))}`;
}

function itemHtml(it, e) {
  const src = it.link ? `<a href="${esc(it.link)}" target="_blank" rel="noopener">${esc(it.source || "source")}</a>` : esc(it.source || "");
  const read = it.at ? "read " + clock(it.at) : it.page_at ? "page read " + clock(it.page_at) : "";
  const meta = [it.about ? esc(it.about) : "", src, esc(it.price || ""), read, it.by ? "by " + esc(String(it.by).split(":").pop()) : "",
    it.bytes != null ? `${it.bytes} bytes` : "", (it.facts || []).map((f) => esc(f.replace(/_/g, " "))).join(", ")].filter(Boolean).join(" · ");
  const status = it.status ? ` <span class="g">· ${esc(it.status)}</span>` : "";
  const title = it.title && it.title.toLowerCase() !== e.label.toLowerCase() ? `<div class="ti">${esc(it.title)}${status}</div>` : "";
  const hashes = [["hash", it.hash], ["previous", it.prev_hash], ["request", it.body_hash]].filter(([, v]) => v)
    .map(([k, v]) => `<span>${k}</span><code>${esc(v)}</code>`).join("");
  return `<div class="it">${title}${it.quote ? `<q>${esc(it.quote)}</q>` : ""}${meta ? `<div class="meta">${meta}</div>` : ""}
    ${hashes ? `<div class="hashes" title="SHA-256">${hashes}</div>` : ""}</div>`;
}

/** The receipt before and after an event: by number for a receipt, by time for anything else with a time. */
function nearHtml(e) {
  const c = feed.chain || [];
  if (!c.length) return "";
  let before, now, after;
  if (e.receipt != null) {
    const i = c.findIndex((r) => r.n === e.receipt);
    [before, now, after] = [c[i - 1], c[i], c[i + 1]];
  } else if (e.t != null) {
    const i = c.findIndex((r) => Date.parse(r.at) > e.t);
    [before, after] = i < 0 ? [c[c.length - 1], null] : [c[i - 1], c[i]];
  } else return "";
  const row = (word, r, self) => (r ? `<${self ? 'div class="now"' : `button data-receipt="${r.n}"`}><span>${word}</span><span>${r.n} · ${esc(String(r.type).replace(/_/g, " "))}</span><code>${esc(short(r.hash))}</code></${self ? "div" : "button"}>` : "");
  const body = row("before", before) + row("this", now, true) + row("after", after);
  return body ? `<div class="cap">Receipts</div><div class="near">${body}</div>` : "";
}

function renderSheet() {
  const e = sel && feed.events.find((x) => key(x) === sel), el = $("#sheet");
  $("#wrap").classList.toggle("with", !!e);
  el.hidden = !e;
  if (!e) return;
  const step = feed.steps.find((s) => s.id === e.step) || {}, lane = (id) => (feed.lanes.find((l) => l.id === id) || {}).label || id;
  const facts = [
    ["when", [clock(e.at), e.end_at ? "to " + clock(e.end_at) : "", dur(e.duration_ms)].filter(Boolean).join(" · ")],
    ["from", e.lane === e.to_lane ? lane(e.lane) : `${lane(e.lane)}, to ${lane(e.to_lane)}`],
    ["records", String(records(e))],
    ["checked", e.verified_count != null && e.proof ? `${e.verified_count} of ${e.source === "receipt" ? 1 : records(e)} · ${e.proof}` : ""],
    ["ref", e.ref || ""],
  ].filter(([, v]) => v).map(([k, v]) => `<span>${k}</span><div>${esc(v)}</div>`).join("");
  el.innerHTML = `<div class="cap">${icon(e.stopped ? "stop" : e.kind)}${cap(e.kind)} · ${esc(step.label || "")}<button class="x" data-close aria-label="Close">${CROSS}</button></div>
    <h2 class="${e.stopped ? "stop" : ""}">${esc(e.label)}</h2>
    ${e.detail ? `<p class="detail">${esc(e.detail)}</p>` : ""}
    <div class="facts">${facts}</div>
    ${e.context && (e.to_lane === "reader" || e.to_lane === "stores") ? contextBlock(e.context, e.to_lane === "reader" ? "model calls" : "messages", true) : ""}
    <div class="items">${e.items.map((it) => itemHtml(it, e)).join("")}</div>
    ${e.more ? `<div class="more">and ${e.more} more</div>` : ""}
    ${nearHtml(e)}`;
}

function render(fresh) {
  flow.update($("#flow"), feed.flow);
  renderTop();
  renderBand();
  renderSteps(fresh);
  renderSheet();
}

// ---------- data ----------
async function load() {
  let next = null;
  try {
    const res = await fetch("/api/trail", { cache: "no-store" });
    if (res.ok) next = await res.json();
  } catch { /* shown below as "feed missing" */ }
  if (!next) {
    if (!missing && feed) { missing = true; renderBand(); }
    return;
  }
  const now = JSON.stringify([next.events.map((e) => [key(e), e.count, e.verified, e.duration_ms]), next.chain.map((c) => [c.hash, c.verified]),
    next.summary, next.steps.map((s) => [s.done, s.sub, s.label]), next.signed, next.sources, next.sheet, next.mode]);
  if (now === stamp && !missing) return;
  stamp = now;
  missing = false;
  const first = !feed;
  feed = next;
  const keys = new Set(feed.events.map(key));
  const fresh = new Set(seen ? [...keys].filter((k) => !seen.has(k)) : []);
  seen = keys;
  if (first) {                       // open the step named in the address, or the latest step that has events
    const named = feed.steps.find((s) => s.id === location.hash.slice(1) && s.events);
    const latest = [...feed.steps].reverse().find((s) => s.events);
    if (named || latest) open.add((named || latest).id);
    const asked = feed.events.find((e) => String(e.n) === params.get("event"));   // /trail/?event=12 opens that event
    if (asked) { sel = key(asked); open.add(asked.step); }
  }
  for (const e of feed.events) if (fresh.has(key(e))) open.add(e.step);   // a new event opens its step
  render(fresh);
  if (first && MOTION) {
    [...document.querySelectorAll(".step")].forEach((n, i) => n.animate([{ opacity: 0, transform: "translateY(4px)" }, { opacity: 1, transform: "none" }],
      { duration: 260, delay: i * 50, easing: EASE, fill: "backwards" }));
  }
}

// ---------- input ----------
document.addEventListener("click", (ev) => {
  const t = ev.target.closest("[data-step], [data-k], [data-kind], [data-close], [data-receipt]");
  if (!t || !feed) return;
  if (t.dataset.step) {
    open.has(t.dataset.step) ? open.delete(t.dataset.step) : open.add(t.dataset.step);
    renderSteps();
  } else if (t.dataset.k) {
    sel = sel === t.dataset.k ? null : t.dataset.k;
    renderSteps();
    renderSheet();
  } else if (t.dataset.kind) {       // all shown at first; a click narrows to that kind, more clicks add or remove
    const k = t.dataset.kind;
    if (filter.size === 0) filter.add(k); else if (filter.has(k)) filter.delete(k); else filter.add(k);
    if (filter.size === feed.kinds.length) filter.clear();
    renderBand();
    renderSteps();
  } else if (t.dataset.receipt) {
    const e = feed.events.find((x) => String(x.receipt) === t.dataset.receipt);
    if (e) { sel = key(e); open.add(e.step); renderSteps(); renderSheet(); }
  } else {
    sel = null;
    renderSteps();
    renderSheet();
  }
});
document.addEventListener("keydown", (ev) => {
  if (ev.key === "Escape" && sel) { sel = null; renderSteps(); renderSheet(); }
});

const tip = $("#tip");
document.addEventListener("mouseover", (ev) => {
  const el = ev.target.closest("[data-tip]");
  if (!el) { tip.hidden = true; return; }
  tip.innerHTML = `${esc(el.dataset.tip)}${el.dataset.code ? `<code>${esc(el.dataset.code)}</code>` : ""}`;
  tip.hidden = false;
  const r = el.getBoundingClientRect();
  tip.style.left = Math.max(8, Math.min(innerWidth - tip.offsetWidth - 8, r.right - tip.offsetWidth)) + "px";
  tip.style.top = (r.top - tip.offsetHeight - 6 < 8 ? r.bottom + 6 : r.top - tip.offsetHeight - 6) + "px";
});

await load();
if (LIVE) {
  const stream = new EventSource("/api/events");   // the state changed: read the feed again
  stream.onmessage = () => load();
  setInterval(load, 5000);                          // ledger rows arrive without a state change
}
